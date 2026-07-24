"""Trusted local Web service for investment-review product projections.

HTTP callers provide only canonical IDs and bounded JSON values.  Artifact
paths are resolved exclusively through ``ReviewRunCatalog`` and never cross
the API boundary.  All mutations are append-only and remain in the selected
review sidecar or its checkout-local revision root.
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
import threading
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.investment_review.artifact_io import (
    ArtifactIOError,
    atomic_create_bytes,
    pretty_json_bytes,
)
from src.investment_review.episode_portfolio_context import (
    validate_episode_portfolio_context,
)
from src.investment_review.episode_review import validate_episode_review
from src.investment_review.episode_revision import (
    EpisodeRevisionError,
    apply_human_review,
    list_episode_review_revisions,
    save_new_episode_review,
    validate_revision_chain,
)
from src.investment_review.models import (
    DecisionRecord,
    FeeCorrectionRecord,
    ModelValidationError,
    canonical_json,
)
from src.investment_review.review_input_bundle import validate_review_input_bundle
from src.investment_review.review_runner import (
    RUN_CATALOG_SCHEMA_VERSION,
    RUN_SCOPES,
    ReviewRunCatalog,
    ReviewRunnerError,
)
from src.investment_review.store import (
    DataConflictError,
    ReviewStore,
    ReviewStoreError,
)
from src.investment_review.sync_service import ReviewSyncService


API_SCHEMA_VERSION = "investment_review.web_api.v1"
API_BOUNDARY = {
    "advice": False,
    "source": "validated_review_artifacts_and_candidate_sidecar",
    "portfolio_source_write": False,
}

_RUN_ID = re.compile(r"^reviewrun_[0-9a-f]{32}$")
_REVIEW_ID = re.compile(r"^review:[0-9a-f]{32}$")
_EPISODE_ID = re.compile(r"^te_[0-9a-f]{32}$")
_EVENT_ID = re.compile(r"^evt_[0-9a-f]{32}$")
_DECISION_ID = re.compile(r"^dec_[0-9a-f]{32}$")
_CONTENT_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_UTC_SECOND = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_REVISION_FILE = re.compile(
    r"^r(?P<revision_no>\d{4})_"
    r"(?P<content_hash>[0-9a-f]{32}(?:[0-9a-f]{32})?)\.json$"
)
_RETROSPECTIVE_LINK_FILE = re.compile(r"^retrolink_[0-9a-f]{32}\.json$")
_DECIMAL_TEXT = re.compile(r"^(?:0|[1-9]\d*)(?:\.\d{1,8})?$")
_RETROSPECTIVE_LINK_FIELDS = frozenset(
    {
        "schema_version",
        "link_id",
        "run_id",
        "review_id",
        "episode_id",
        "event_id",
        "decision_id",
        "relation",
        "known_at",
        "linked_at",
        "actor_ref",
        "source",
        "content_id",
    }
)


class InvestmentReviewServiceError(RuntimeError):
    """Safe API-facing failure without local path or SQL disclosure."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = int(status)
        self.code = code


def _error(status: int, code: str, message: str) -> InvestmentReviewServiceError:
    return InvestmentReviewServiceError(status, code, message)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _resolve_from_root(value: str | Path, root: Path) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve(strict=False)


def _is_link_like(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        junction_check = getattr(path, "is_junction", None)
        if callable(junction_check) and junction_check():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        return bool(reparse_flag and attributes & reparse_flag)
    except FileNotFoundError:
        return False
    except OSError:
        return True


def _required_id(value: object, field: str, pattern: re.Pattern[str]) -> str:
    text = str(value or "").strip()
    if not pattern.fullmatch(text):
        raise _error(400, f"invalid_{field}", f"{field} 格式无效")
    return text


def _request_id(value: object) -> str:
    text = str(value or "").strip()
    if not _REQUEST_ID.fullmatch(text):
        raise _error(400, "invalid_request_id", "request_id 格式无效")
    return text


def _timestamp(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not _UTC_SECOND.fullmatch(text):
        raise _error(
            400,
            f"invalid_{field}",
            f"{field} 必须是 UTC 整秒时间，例如 2026-07-24T01:02:03Z",
        )
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _error(400, f"invalid_{field}", f"{field} 不是有效时间") from exc
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _bounded_text(
    value: object,
    field: str,
    *,
    required: bool = False,
    maximum: int = 4000,
) -> str | None:
    if value is None:
        if required:
            raise _error(400, f"missing_{field}", f"{field} 不能为空")
        return None
    if not isinstance(value, str):
        raise _error(400, f"invalid_{field}", f"{field} 必须是字符串")
    text = value.strip()
    if required and not text:
        raise _error(400, f"missing_{field}", f"{field} 不能为空")
    if len(text) > maximum:
        raise _error(400, f"{field}_too_long", f"{field} 超过长度上限")
    if any(ord(character) == 0 for character in text):
        raise _error(400, f"invalid_{field}", f"{field} 含非法字符")
    return text or None


def _object_payload(
    payload: object,
    *,
    required: set[str],
    optional: set[str] = frozenset(),
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise _error(400, "object_required", "请求体必须是对象")
    value = dict(payload)
    unknown = sorted(set(value) - required - optional)
    if unknown:
        raise _error(
            400,
            "unexpected_field",
            "不支持的字段: " + ", ".join(unknown),
        )
    missing = sorted(field for field in required if field not in value)
    if missing:
        raise _error(400, "missing_field", "缺少字段: " + ", ".join(missing))
    return value


def _envelope(
    *,
    status: str,
    data: Mapping[str, Any],
    ref: Mapping[str, Any] | None = None,
    gaps: Sequence[object] = (),
) -> dict[str, Any]:
    return {
        "schema_version": API_SCHEMA_VERSION,
        "status": status,
        "ref": dict(ref or {}),
        "data": dict(data),
        "gaps": list(gaps),
        "boundary": dict(API_BOUNDARY),
    }


def _current_status(value: object) -> str:
    status = str(value or "unknown").lower()
    if status == "succeeded":
        return "ready"
    return (
        status
        if status in {
            "ready",
            "partial",
            "blocked",
            "failed",
            "queued",
            "running",
            "unknown",
            "healthy",
            "lagging",
            "missing_sidecar",
            "schema_not_initialized",
            "invalid_sidecar",
            "missing",
            "complete",
            "available",
            "unavailable",
        }
        else "unknown"
    )


def _stable_id(prefix: str, value: object) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:32]}"


def _public_projection(value: object) -> Any:
    """Remove checkout-local locations while preserving evidence identities."""

    if isinstance(value, Mapping):
        projected: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            normalized = key.lower()
            if (
                normalized in {"path", "uri", "database", "database_path", "db_path"}
                or normalized.endswith("_path")
                or normalized.endswith("_uri")
            ):
                continue
            projected[key] = _public_projection(item)
        return projected
    if isinstance(value, (list, tuple)):
        return [_public_projection(item) for item in value]
    if isinstance(value, str) and (
        re.match(r"^[A-Za-z]:[\\/]", value)
        or value.startswith(("\\\\", "/", "file:"))
    ):
        return "[local_path_redacted]"
    return value


class _TrustedReviewCatalog:
    """P4 read adapter over the frozen P3 runner/catalog contract."""

    def __init__(self, catalog: Any) -> None:
        self._catalog = catalog
        self.runner = catalog.runner
        self.store = catalog.store

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(65536), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _json_object(path: Path, *, artifact_name: str) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            raise ReviewRunnerError(
                f"{artifact_name} artifact is unreadable"
            ) from exc
        if not isinstance(value, dict):
            raise ReviewRunnerError(f"{artifact_name} artifact must be an object")
        return value

    def _trusted_file(
        self,
        raw_path: object,
        *,
        artifact_name: str,
    ) -> Path:
        if not isinstance(raw_path, str) or not raw_path:
            raise ReviewRunnerError(f"{artifact_name} artifact has no trusted path")
        try:
            path = Path(raw_path).resolve(strict=False)
            if not _inside(path, self.runner.artifact_root):
                raise ReviewRunnerError(
                    f"{artifact_name} path is outside the trusted root"
                )
            if not path.is_file():
                raise ReviewRunnerError(f"{artifact_name} artifact is missing")
        except ReviewRunnerError:
            raise
        except OSError as exc:
            raise ReviewRunnerError(
                f"{artifact_name} artifact is unavailable"
            ) from exc
        return path

    def get_receipt(self, run_ref: str) -> dict[str, Any]:
        run = self.store.get_review_run(run_ref)
        if run["run"]["scope"] not in RUN_SCOPES:
            raise ReviewRunnerError("run is not a facts-only review run")
        event = run.get("status_event")
        details = (
            event.get("details")
            if isinstance(event, Mapping)
            and isinstance(event.get("details"), Mapping)
            else {}
        )
        raw_path = str(details.get("receipt_path") or "")
        if not raw_path:
            raise ReviewRunnerError("run has no completed receipt")
        path = self._trusted_file(raw_path, artifact_name="receipt")
        try:
            receipt_sha256 = self._sha256_file(path)
        except OSError as exc:
            raise ReviewRunnerError("receipt artifact is unavailable") from exc
        if receipt_sha256 != details.get("receipt_sha256"):
            raise ReviewRunnerError(
                "receipt hash does not match the immutable run ledger"
            )
        receipt = self._json_object(path, artifact_name="receipt")
        try:
            validation = self.runner.validate_receipt(
                receipt,
                expected_path=path,
            )
        except (OSError, UnicodeError, ValueError) as exc:
            raise ReviewRunnerError(
                "receipt artifact validation could not complete"
            ) from exc
        if validation.get("validation_status") == "blocked":
            raise ReviewRunnerError("receipt validation blocked")
        if (
            receipt.get("run_id") != run["run"].get("run_id")
            or receipt.get("run_key") != run["run"].get("run_key")
            or receipt.get("scope") != run["run"].get("scope")
            or receipt.get("content_id")
            != details.get("receipt_content_id")
        ):
            raise ReviewRunnerError(
                "receipt identity does not match the immutable run ledger"
            )
        return receipt

    def list_receipts(self) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        invalid_runs: list[dict[str, Any]] = []
        for scope in sorted(RUN_SCOPES):
            for run in self.store.list_review_runs(scope=scope):
                if run["status"] not in {"succeeded", "partial"}:
                    continue
                parameters = run["run"].get("parameters")
                configured_root = (
                    str(parameters.get("artifact_root") or "")
                    if isinstance(parameters, Mapping)
                    else ""
                )
                try:
                    matches_root = (
                        bool(configured_root)
                        and Path(configured_root).resolve(strict=False)
                        == self.runner.artifact_root
                    )
                except OSError:
                    matches_root = False
                if not matches_root:
                    continue
                try:
                    receipt = self.get_receipt(str(run["run"]["run_id"]))
                except (ReviewRunnerError, ReviewStoreError):
                    invalid_runs.append(
                        {
                            "run_id": str(run["run"].get("run_id") or ""),
                            "run_key": str(run["run"].get("run_key") or ""),
                            "scope": str(run["run"].get("scope") or scope),
                            "status": "failed",
                            "requested_at": run["run"].get("requested_at"),
                            "gap_codes": ["RUN_RECEIPT_INVALID"],
                        }
                    )
                    continue
                items.append(
                    {
                        "run_id": receipt["run_id"],
                        "run_key": receipt["run_key"],
                        "scope": receipt["scope"],
                        "status": receipt["status"],
                        "cutoffs": receipt["cutoffs"],
                        "episode_count": len(receipt["episodes"]),
                        "gaps": receipt["gaps"],
                        "content_id": receipt["content_id"],
                    }
                )
        items.sort(key=lambda item: (item["scope"], item["run_key"]))
        invalid_runs.sort(
            key=lambda item: (
                str(item.get("requested_at") or ""),
                str(item.get("run_id") or ""),
            )
        )
        return {
            "schema_version": RUN_CATALOG_SCHEMA_VERSION,
            "count": len(items),
            "runs": items,
            "invalid_runs": invalid_runs,
        }

    def list_run_statuses(self) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for scope in sorted(RUN_SCOPES):
            for item in self.store.list_review_runs(scope=scope):
                run = item.get("run")
                if not isinstance(run, Mapping):
                    continue
                parameters = run.get("parameters")
                configured_root = (
                    str(parameters.get("artifact_root") or "")
                    if isinstance(parameters, Mapping)
                    else ""
                )
                try:
                    matches_root = (
                        bool(configured_root)
                        and Path(configured_root).resolve(strict=False)
                        == self.runner.artifact_root
                    )
                except OSError:
                    matches_root = False
                if not matches_root:
                    continue
                status_event = item.get("status_event")
                items.append(
                    {
                        "run_id": str(run.get("run_id") or ""),
                        "run_key": str(run.get("run_key") or ""),
                        "scope": str(run.get("scope") or ""),
                        "status": str(item.get("status") or "unknown"),
                        "requested_at": run.get("requested_at"),
                        "source_cutoff": run.get("source_cutoff"),
                        "trigger": run.get("trigger"),
                        "status_occurred_at": (
                            status_event.get("occurred_at")
                            if isinstance(status_event, Mapping)
                            else None
                        ),
                        "status_known_at": (
                            status_event.get("known_at")
                            if isinstance(status_event, Mapping)
                            else None
                        ),
                    }
                )
        items.sort(
            key=lambda item: (
                str(item.get("requested_at") or ""),
                str(item.get("run_id") or ""),
            )
        )
        return {
            "schema_version": "investment_review.review_run_status_catalog.v1",
            "count": len(items),
            "runs": items,
        }

    def _load_episode_artifact(
        self,
        *,
        descriptor: Mapping[str, Any],
        artifact_name: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        path = self._trusted_file(
            descriptor.get("path"),
            artifact_name=artifact_name,
        )
        try:
            expected_size = descriptor.get("size_bytes")
            if (
                not isinstance(expected_size, int)
                or isinstance(expected_size, bool)
                or expected_size < 0
                or path.stat().st_size != expected_size
            ):
                raise ReviewRunnerError(
                    f"{artifact_name} artifact size mismatch"
                )
            if self._sha256_file(path) != descriptor.get("sha256"):
                raise ReviewRunnerError(
                    f"{artifact_name} artifact hash mismatch"
                )
        except ReviewRunnerError:
            raise
        except OSError as exc:
            raise ReviewRunnerError(
                f"{artifact_name} artifact is unavailable"
            ) from exc
        artifact = self._json_object(path, artifact_name=artifact_name)
        content_id = descriptor.get("content_id")
        if (
            not isinstance(content_id, str)
            or not content_id
            or artifact.get("content_id") != content_id
        ):
            raise ReviewRunnerError(
                f"{artifact_name} artifact content identity mismatch"
            )
        if artifact_name == "context":
            validation = validate_episode_portfolio_context(artifact)
        elif artifact_name == "input":
            validation = validate_review_input_bundle(artifact)
        elif artifact_name == "review":
            validation = validate_episode_review(artifact)
        else:
            raise ReviewRunnerError(
                f"unsupported trusted artifact kind: {artifact_name}"
            )
        if validation.get("validation_status") == "blocked":
            raise ReviewRunnerError(
                f"{artifact_name} artifact validation blocked"
            )
        return artifact, validation

    def get_episode_bundle(
        self,
        run_id: str,
        review_id: str,
        *,
        episode_id: str | None = None,
    ) -> dict[str, Any]:
        receipt = self.get_receipt(run_id)
        if receipt.get("run_id") != run_id:
            raise ReviewRunnerError(
                "run reference did not resolve to exact run ID"
            )
        matches = [
            item
            for item in receipt.get("episodes", [])
            if isinstance(item, Mapping)
            and item.get("review_id") == review_id
            and (episode_id is None or item.get("episode_id") == episode_id)
        ]
        if not matches:
            raise ReviewRunnerError("run-qualified review was not found")
        if len(matches) != 1:
            raise ReviewRunnerError(
                "run-qualified review resolved ambiguously"
            )
        episode_summary = dict(matches[0])
        artifacts = episode_summary.pop("artifacts", None)
        if not isinstance(artifacts, Mapping):
            raise ReviewRunnerError("episode artifact descriptors are missing")

        loaded: dict[str, dict[str, Any]] = {}
        validations: dict[str, dict[str, Any]] = {}
        for artifact_name in ("context", "input", "review"):
            descriptor = artifacts.get(artifact_name)
            if not isinstance(descriptor, Mapping):
                raise ReviewRunnerError(
                    f"{artifact_name} artifact descriptor is missing"
                )
            loaded[artifact_name], validations[artifact_name] = (
                self._load_episode_artifact(
                    descriptor=descriptor,
                    artifact_name=artifact_name,
                )
            )

        frozen_sources = loaded["input"].get("frozen_sources")
        episode = (
            frozen_sources.get("episode")
            if isinstance(frozen_sources, Mapping)
            else None
        )
        if not isinstance(episode, Mapping):
            raise ReviewRunnerError("review input has no frozen episode")
        if (
            episode.get("episode_id") != episode_summary.get("episode_id")
            or loaded["review"].get("review_id") != review_id
            or loaded["review"].get("content_id")
            != episode_summary.get("review_content_id")
            or loaded["input"].get("content_id")
            != episode_summary.get("input_content_id")
            or loaded["context"].get("content_id")
            != episode_summary.get("context_content_id")
        ):
            raise ReviewRunnerError(
                "run-qualified episode artifact identities do not agree"
            )
        bundle = {
            "schema_version": "investment_review.review_episode_bundle.v1",
            "receipt": receipt,
            "episode_summary": episode_summary,
            "episode": dict(episode),
            "context": loaded["context"],
            "input": loaded["input"],
            "review": loaded["review"],
            "validations": validations,
        }
        transform = getattr(self._catalog, "transform_episode_bundle", None)
        if callable(transform):
            transformed = transform(bundle)
            if not isinstance(transformed, Mapping):
                raise ReviewRunnerError(
                    "catalog bundle transform returned an invalid value"
                )
            bundle = dict(transformed)
        return bundle


class InvestmentReviewWebService:
    """Curated, run-qualified service used by the loopback-only dashboard."""

    def __init__(
        self,
        *,
        review_db: str | Path | None = None,
        portfolio_db: str | Path | None = None,
        mapping_path: str | Path | None = None,
        artifact_root: str | Path | None = None,
        repo_root: str | Path | None = None,
        revision_root: str | Path | None = None,
        catalog: Any | None = None,
        store: ReviewStore | None = None,
        sync_service: ReviewSyncService | None = None,
        automation_status_provider: (
            Callable[[], Mapping[str, Any]] | None
        ) = None,
    ) -> None:
        root = (
            Path(repo_root).resolve()
            if repo_root is not None
            else Path(__file__).resolve().parents[2]
        )
        if catalog is None:
            if review_db is None or portfolio_db is None:
                raise _error(
                    503,
                    "review_configuration_missing",
                    "复盘服务需要显式 review_db 与 portfolio_db",
                )
            catalog = ReviewRunCatalog(
                review_db=review_db,
                portfolio_db=portfolio_db,
                artifact_root=artifact_root,
                repo_root=root,
            )
        self.catalog = (
            catalog
            if isinstance(catalog, _TrustedReviewCatalog)
            else _TrustedReviewCatalog(catalog)
        )
        selected_store = store or self.catalog.store
        try:
            selected_store_path = Path(selected_store.path).resolve(
                strict=False
            )
            catalog_store_path = Path(self.catalog.store.path).resolve(
                strict=False
            )
        except (AttributeError, OSError, TypeError) as exc:
            raise _error(
                503,
                "review_store_identity_invalid",
                "候选复盘数据库身份无法验证",
            ) from exc
        if selected_store_path != catalog_store_path:
            raise _error(
                503,
                "review_store_identity_mismatch",
                "候选复盘数据库与受信任目录不一致",
            )
        if review_db is not None:
            try:
                configured_review_db = _resolve_from_root(review_db, root)
            except (OSError, TypeError) as exc:
                raise _error(
                    503,
                    "review_store_identity_invalid",
                    "候选复盘数据库身份无法验证",
                ) from exc
            if configured_review_db != selected_store_path:
                raise _error(
                    503,
                    "review_store_identity_mismatch",
                    "候选复盘数据库与受信任目录不一致",
                )
        if portfolio_db is not None:
            try:
                configured_portfolio_db = _resolve_from_root(
                    portfolio_db,
                    root,
                )
                catalog_portfolio_db = Path(
                    self.catalog.runner.portfolio_db
                ).resolve(strict=False)
            except (AttributeError, OSError, TypeError) as exc:
                raise _error(
                    503,
                    "portfolio_source_identity_invalid",
                    "正式来源数据库身份无法验证",
                ) from exc
            if configured_portfolio_db != catalog_portfolio_db:
                raise _error(
                    503,
                    "portfolio_source_identity_mismatch",
                    "正式来源数据库与受信任目录不一致",
                )
        self.store = selected_store
        self.sync_service = sync_service
        if self.sync_service is None and portfolio_db is not None:
            self.sync_service = ReviewSyncService(
                portfolio_db,
                review_db=review_db or self.store.path,
                mapping_path=mapping_path,
                repo_root=root,
            )
        self.automation_status_provider = automation_status_provider

        configured_revision_root = (
            Path(revision_root)
            if revision_root is not None
            else self.catalog.runner.artifact_root / "human_revisions"
        )
        if not configured_revision_root.is_absolute():
            configured_revision_root = root / configured_revision_root
        resolved_revision_root = configured_revision_root.resolve(strict=False)
        trusted_root = self.catalog.runner.artifact_root.resolve(strict=False)
        if not _inside(resolved_revision_root, trusted_root):
            raise _error(
                503,
                "revision_root_not_trusted",
                "复盘修订目录必须位于受信任产物目录内",
            )
        self.revision_root = resolved_revision_root
        self.retrospective_link_root = (
            self.revision_root / "retrospective_links"
        ).resolve(strict=False)
        if not _inside(self.retrospective_link_root, self.revision_root):
            raise _error(
                503,
                "retrospective_link_root_not_trusted",
                "回顾性关联目录必须位于受信任修订目录内",
            )
        self._lock_guard = threading.Lock()
        self._revision_locks: dict[str, threading.Lock] = {}
        self._decision_locks: dict[str, threading.Lock] = {}

    def set_automation_status_provider(
        self,
        provider: Callable[[], Mapping[str, Any]] | None,
    ) -> None:
        """Attach a process-local status source without changing the sidecar."""

        self.automation_status_provider = provider

    @staticmethod
    def _ref(bundle: Mapping[str, Any]) -> dict[str, Any]:
        receipt = bundle["receipt"]
        summary = bundle["episode_summary"]
        review = bundle["review"]
        return {
            "run_id": receipt["run_id"],
            "review_id": review["review_id"],
            "episode_id": summary["episode_id"],
            "content_id": review["content_id"],
        }

    def _bundle(self, run_id: object, review_id: object) -> dict[str, Any]:
        run = _required_id(run_id, "run_id", _RUN_ID)
        review = _required_id(review_id, "review_id", _REVIEW_ID)
        try:
            return self.catalog.get_episode_bundle(run, review)
        except ReviewRunnerError as exc:
            message = str(exc).lower()
            if "not found" in message or "was not found" in message:
                raise _error(404, "review_not_found", "指定复盘不存在") from exc
            raise _error(
                409,
                "review_artifact_invalid",
                "指定复盘未通过受信任产物校验",
            ) from exc
        except ReviewStoreError as exc:
            message = str(exc).lower()
            if "not found" in message:
                raise _error(404, "review_not_found", "指定复盘不存在") from exc
            raise _error(
                503,
                "review_catalog_unavailable",
                "复盘目录不可用",
            ) from exc

    def _revision_directory(self, run_id: str, review_id: str) -> Path:
        digest = hashlib.sha256(f"{run_id}\0{review_id}".encode("utf-8")).hexdigest()
        path = self.revision_root / digest[:32]
        try:
            if _is_link_like(self.revision_root) or _is_link_like(path):
                raise _error(
                    409,
                    "revision_path_invalid",
                    "复盘修订目录无效",
                )
            resolved = path.resolve(strict=False)
        except InvestmentReviewServiceError:
            raise
        except OSError as exc:
            raise _error(
                409,
                "revision_path_invalid",
                "复盘修订目录无效",
            ) from exc
        if not _inside(resolved, self.revision_root):
            raise _error(409, "revision_path_invalid", "复盘修订目录无效")
        return path

    def _retrospective_directory(self, run_id: str, review_id: str) -> Path:
        root = self.retrospective_link_root
        try:
            if _is_link_like(self.revision_root) or _is_link_like(root):
                raise _error(
                    409,
                    "retrospective_link_path_invalid",
                    "回顾性关联目录无效",
                )
            resolved_root = root.resolve(strict=False)
        except InvestmentReviewServiceError:
            raise
        except OSError as exc:
            raise _error(
                409,
                "retrospective_link_path_invalid",
                "回顾性关联目录无效",
            ) from exc
        if not _inside(resolved_root, self.revision_root):
            raise _error(
                409,
                "retrospective_link_path_invalid",
                "回顾性关联目录无效",
            )
        digest = hashlib.sha256(
            f"{run_id}\0{review_id}".encode("utf-8")
        ).hexdigest()
        path = root / digest[:32]
        try:
            if _is_link_like(path):
                raise _error(
                    409,
                    "retrospective_link_path_invalid",
                    "回顾性关联目录无效",
                )
            resolved = path.resolve(strict=False)
        except InvestmentReviewServiceError:
            raise
        except OSError as exc:
            raise _error(
                409,
                "retrospective_link_path_invalid",
                "回顾性关联目录无效",
            ) from exc
        if not _inside(resolved, resolved_root):
            raise _error(
                409,
                "retrospective_link_path_invalid",
                "回顾性关联目录无效",
            )
        return path

    @staticmethod
    def _retrospective_link_id(
        *,
        run_id: str,
        review_id: str,
        episode_id: str,
        event_id: str,
        decision_id: str,
    ) -> str:
        return _stable_id(
            "retrolink",
            {
                "run_id": run_id,
                "review_id": review_id,
                "episode_id": episode_id,
                "event_id": event_id,
                "decision_id": decision_id,
                "relation": "retrospective_context",
            },
        )

    @staticmethod
    def _retrospective_content_id(value: Mapping[str, Any]) -> str:
        material = {
            key: item
            for key, item in value.items()
            if key != "content_id"
        }
        digest = hashlib.sha256(
            canonical_json(material).encode("utf-8")
        ).hexdigest()
        return "sha256:" + digest

    def _retrospective_links(
        self,
        bundle: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        ref = self._ref(bundle)
        directory = self._retrospective_directory(
            str(ref["run_id"]),
            str(ref["review_id"]),
        )
        if not directory.exists():
            return []
        if not directory.is_dir() or _is_link_like(directory):
            raise _error(
                409,
                "retrospective_link_artifact_invalid",
                "回顾性关联目录未通过校验",
            )
        try:
            paths = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            raise _error(
                409,
                "retrospective_link_artifact_invalid",
                "回顾性关联目录无法读取",
            ) from exc

        allowed_events = self._episode_event_ids(bundle)
        links: list[dict[str, Any]] = []
        for path in paths:
            if _is_link_like(path):
                raise _error(
                    409,
                    "retrospective_link_artifact_invalid",
                    "回顾性关联目录包含不允许的符号链接",
                )
            if (
                path.suffix.lower() == ".json"
                and not _RETROSPECTIVE_LINK_FILE.fullmatch(path.name)
            ):
                raise _error(
                    409,
                    "retrospective_link_artifact_invalid",
                    "回顾性关联目录包含未登记的 JSON 文件",
                )
            if not _RETROSPECTIVE_LINK_FILE.fullmatch(path.name):
                continue
            try:
                resolved = path.resolve(strict=False)
                if (
                    not _inside(resolved, directory)
                    or not resolved.is_file()
                    or resolved.stat().st_size > 250_000
                ):
                    raise _error(
                        409,
                        "retrospective_link_artifact_invalid",
                        "回顾性关联文件未通过路径或大小校验",
                    )
                value = json.loads(resolved.read_text(encoding="utf-8"))
            except InvestmentReviewServiceError:
                raise
            except (OSError, UnicodeError, ValueError) as exc:
                raise _error(
                    409,
                    "retrospective_link_artifact_invalid",
                    "回顾性关联文件无法验证",
                ) from exc
            if not isinstance(value, dict) or set(value) != set(
                _RETROSPECTIVE_LINK_FIELDS
            ):
                raise _error(
                    409,
                    "retrospective_link_artifact_invalid",
                    "回顾性关联字段集合无效",
                )
            if (
                value.get("schema_version")
                != "investment_review.retrospective_link.v1"
                or not _RUN_ID.fullmatch(str(value.get("run_id") or ""))
                or not _REVIEW_ID.fullmatch(str(value.get("review_id") or ""))
                or not _EPISODE_ID.fullmatch(str(value.get("episode_id") or ""))
                or not _EVENT_ID.fullmatch(str(value.get("event_id") or ""))
                or not _DECISION_ID.fullmatch(
                    str(value.get("decision_id") or "")
                )
                or not _CONTENT_ID.fullmatch(str(value.get("content_id") or ""))
                or value.get("relation") != "retrospective_context"
                or value.get("actor_ref") != "workspace_user"
                or value.get("source") != "investment_review_web"
                or not _UTC_SECOND.fullmatch(str(value.get("known_at") or ""))
                or not _UTC_SECOND.fullmatch(str(value.get("linked_at") or ""))
            ):
                raise _error(
                    409,
                    "retrospective_link_artifact_invalid",
                    "回顾性关联身份或语义无效",
                )
            parsed_timestamps: dict[str, datetime] = {}
            try:
                for timestamp_field in ("known_at", "linked_at"):
                    parsed = datetime.fromisoformat(
                        str(value[timestamp_field]).replace("Z", "+00:00")
                    )
                    if parsed.utcoffset() is None:
                        raise ValueError("timezone is required")
                    parsed_timestamps[timestamp_field] = parsed.astimezone(
                        timezone.utc
                    )
            except (KeyError, TypeError, ValueError) as exc:
                raise _error(
                    409,
                    "retrospective_link_artifact_invalid",
                    "回顾性关联时间字段无效",
                ) from exc
            if (
                parsed_timestamps["known_at"]
                > parsed_timestamps["linked_at"]
            ):
                raise _error(
                    409,
                    "retrospective_link_artifact_invalid",
                    "回顾性关联时间顺序无效",
                )
            expected_link_id = self._retrospective_link_id(
                run_id=str(value["run_id"]),
                review_id=str(value["review_id"]),
                episode_id=str(value["episode_id"]),
                event_id=str(value["event_id"]),
                decision_id=str(value["decision_id"]),
            )
            if (
                value.get("run_id") != ref["run_id"]
                or value.get("review_id") != ref["review_id"]
                or value.get("episode_id") != ref["episode_id"]
                or value.get("event_id") not in allowed_events
                or value.get("link_id") != expected_link_id
                or path.name != f"{expected_link_id}.json"
                or value.get("content_id")
                != self._retrospective_content_id(value)
            ):
                raise _error(
                    409,
                    "retrospective_link_artifact_invalid",
                    "回顾性关联内容身份不一致",
                )
            links.append(dict(value))
        return sorted(links, key=lambda item: str(item["link_id"]))

    def _append_retrospective_link(
        self,
        *,
        bundle: Mapping[str, Any],
        event_id: str,
        decision: Mapping[str, Any],
    ) -> tuple[dict[str, Any], str]:
        ref = self._ref(bundle)
        link_id = self._retrospective_link_id(
            run_id=str(ref["run_id"]),
            review_id=str(ref["review_id"]),
            episode_id=str(ref["episode_id"]),
            event_id=event_id,
            decision_id=str(decision["decision_id"]),
        )
        with self._decision_lock("link:" + link_id):
            for existing in self._retrospective_links(bundle):
                if existing["link_id"] == link_id:
                    return existing, "SKIPPED"
            linked_at = datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            ).replace("+00:00", "Z")
            try:
                decision_known_datetime = datetime.fromisoformat(
                    str(decision["known_at"]).replace("Z", "+00:00")
                ).astimezone(timezone.utc)
                linked_datetime = datetime.fromisoformat(
                    linked_at.replace("Z", "+00:00")
                ).astimezone(timezone.utc)
                if decision_known_datetime > linked_datetime:
                    raise ValueError(
                        "decision known_at cannot be after linked_at"
                    )
                decision_known_at = decision_known_datetime.isoformat(
                    timespec="seconds"
                ).replace("+00:00", "Z")
            except (KeyError, TypeError, ValueError) as exc:
                raise _error(
                    422,
                    "retrospective_decision_time_invalid",
                    "回顾性关联引用的决策时间无效",
                ) from exc
            artifact: dict[str, Any] = {
                "schema_version": "investment_review.retrospective_link.v1",
                "link_id": link_id,
                "run_id": ref["run_id"],
                "review_id": ref["review_id"],
                "episode_id": ref["episode_id"],
                "event_id": event_id,
                "decision_id": decision["decision_id"],
                "relation": "retrospective_context",
                "known_at": decision_known_at,
                "linked_at": linked_at,
                "actor_ref": "workspace_user",
                "source": "investment_review_web",
            }
            artifact["content_id"] = self._retrospective_content_id(artifact)
            directory = self._retrospective_directory(
                str(ref["run_id"]),
                str(ref["review_id"]),
            )
            try:
                directory.mkdir(parents=True, exist_ok=True)
                if (
                    _is_link_like(self.revision_root)
                    or _is_link_like(self.retrospective_link_root)
                    or _is_link_like(directory)
                ):
                    raise _error(
                        409,
                        "retrospective_link_path_invalid",
                        "回顾性关联目录无效",
                    )
                verified_root = self.retrospective_link_root.resolve(
                    strict=True
                )
                verified_directory = directory.resolve(strict=True)
                if (
                    not _inside(verified_root, self.revision_root)
                    or not _inside(verified_directory, verified_root)
                ):
                    raise _error(
                        409,
                        "retrospective_link_path_invalid",
                        "回顾性关联目录无效",
                    )
                atomic_create_bytes(
                    verified_directory / f"{link_id}.json",
                    pretty_json_bytes(artifact),
                )
            except InvestmentReviewServiceError:
                raise
            except (ArtifactIOError, OSError) as exc:
                replay = next(
                    (
                        item
                        for item in self._retrospective_links(bundle)
                        if item["link_id"] == link_id
                    ),
                    None,
                )
                if replay is not None:
                    return replay, "SKIPPED"
                raise _error(
                    409,
                    "retrospective_link_write_conflict",
                    "回顾性关联 create-only 写入发生冲突",
                ) from exc
            return artifact, "LINKED"

    def _review_chain(self, bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
        base = dict(bundle["review"])
        ref = self._ref(bundle)
        directory = self._revision_directory(ref["run_id"], ref["review_id"])
        revisions: list[dict[str, Any]] = []
        try:
            directory_exists = directory.exists()
        except OSError as exc:
            raise _error(
                409,
                "revision_artifact_invalid",
                "复盘修订目录无法验证",
            ) from exc
        if directory_exists:
            try:
                if _is_link_like(directory) or not directory.is_dir():
                    raise _error(
                        409,
                        "revision_artifact_invalid",
                        "复盘修订目录未通过路径校验",
                    )
                paths = sorted(
                    directory.iterdir(), key=lambda item: item.name
                )
            except InvestmentReviewServiceError:
                raise
            except OSError as exc:
                raise _error(
                    409,
                    "revision_artifact_invalid",
                    "复盘修订目录无法读取",
                ) from exc
            for path in paths:
                if _is_link_like(path):
                    raise _error(
                        409,
                        "revision_artifact_invalid",
                        "复盘修订目录包含不允许的符号链接",
                    )
                filename_match = _REVISION_FILE.fullmatch(path.name)
                if path.suffix.lower() == ".json" and filename_match is None:
                    raise _error(
                        409,
                        "revision_artifact_invalid",
                        "复盘修订目录包含未登记的 JSON 文件",
                    )
                if filename_match is None:
                    continue
                try:
                    resolved = path.resolve(strict=False)
                    valid_file = (
                        _inside(resolved, directory)
                        and resolved.is_file()
                        and resolved.stat().st_size <= 5_000_000
                    )
                except OSError as exc:
                    raise _error(
                        409,
                        "revision_artifact_invalid",
                        "复盘修订文件无法验证",
                    ) from exc
                if not valid_file:
                    raise _error(
                        409,
                        "revision_artifact_invalid",
                        "复盘修订文件未通过路径或大小校验",
                    )
                try:
                    value = json.loads(resolved.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise _error(
                        409,
                        "revision_artifact_invalid",
                        "复盘修订产物无法验证",
                    ) from exc
                if not isinstance(value, dict):
                    raise _error(
                        409,
                        "revision_artifact_invalid",
                        "复盘修订产物必须是对象",
                    )
                content_id = str(value.get("content_id") or "")
                revision = value.get("revision")
                revision = revision if isinstance(revision, Mapping) else {}
                revision_no = revision.get("revision_no")
                if (
                    not content_id.removeprefix("sha256:").startswith(
                        filename_match.group("content_hash")
                    )
                    or isinstance(revision_no, bool)
                    or not isinstance(revision_no, int)
                    or revision_no != int(filename_match.group("revision_no"))
                ):
                    raise _error(
                        409,
                        "revision_artifact_invalid",
                        "复盘修订文件名与内容身份不一致",
                    )
                revisions.append(value)
        chain_by_content = {str(base.get("content_id")): base}
        for revision in revisions:
            if revision.get("review_id") != base.get("review_id"):
                raise _error(
                    409,
                    "revision_identity_mismatch",
                    "复盘修订身份不一致",
                )
            content_id = str(revision.get("content_id") or "")
            if content_id in chain_by_content and canonical_json(
                chain_by_content[content_id]
            ) != canonical_json(revision):
                raise _error(
                    409,
                    "revision_content_conflict",
                    "复盘修订 content_id 冲突",
                )
            chain_by_content[content_id] = revision
        chain = list(chain_by_content.values())
        validation = validate_revision_chain(chain)
        if validation["validation_status"] == "blocked":
            raise _error(
                409,
                "revision_chain_invalid",
                "复盘修订链未通过校验",
            )
        return sorted(
            chain,
            key=lambda item: int(item.get("revision", {}).get("revision_no", 0)),
        )

    def _latest_review(self, bundle: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        chain = self._review_chain(bundle)
        return dict(chain[-1]), chain

    @staticmethod
    def _episode_event_ids(bundle: Mapping[str, Any]) -> set[str]:
        return {
            str(item.get("event_id") or "")
            for item in bundle["episode"].get("event_refs", [])
            if isinstance(item, Mapping) and item.get("event_id")
        }

    def _projection_events(
        self, bundle: Mapping[str, Any]
    ) -> dict[str, dict[str, Any]]:
        episode = bundle["episode"]
        scope = episode.get("scope")
        account = scope.get("account_id") if isinstance(scope, Mapping) else None
        symbol = scope.get("symbol") if isinstance(scope, Mapping) else None
        allowed_ids = self._episode_event_ids(bundle)
        try:
            rows = self.store.list_episode_projection_inputs(
                account=str(account) if account else None,
                symbol=str(symbol) if symbol else None,
            )
        except ReviewStoreError as exc:
            raise _error(503, "sidecar_unavailable", "候选复盘数据库不可用") from exc
        return {
            str(row["event_id"]): row
            for row in rows
            if str(row.get("event_id") or "") in allowed_ids
        }

    def _current_decisions(
        self, bundle: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        result: dict[tuple[str, str, str], dict[str, Any]] = {}

        def project(
            decision: Mapping[str, Any],
            *,
            event_id: str,
            relation: str,
            link: Mapping[str, Any],
        ) -> dict[str, Any]:
            return {
                "decision_id": decision.get("decision_id"),
                "event_id": event_id,
                "relation": relation,
                "symbol": decision.get("symbol"),
                "market": decision.get("market"),
                "occurred_at": decision.get("occurred_at"),
                "known_at": decision.get("known_at"),
                "status": decision.get("status"),
                "thesis": decision.get("thesis"),
                "trigger_text": decision.get("trigger_text"),
                "invalidation_text": decision.get("invalidation_text"),
                "expected_horizon": decision.get("expected_horizon"),
                "portfolio_role": decision.get("portfolio_role"),
                "direct_reason": decision.get("direct_reason"),
                "risk_notes": decision.get("risk_notes"),
                "raw_note": decision.get("raw_note"),
                "temporal_role": (
                    "retrospective_context"
                    if relation == "retrospective_context"
                    else "decision_time_candidate"
                ),
                "link": dict(link),
            }

        for event_id, event in self._projection_events(bundle).items():
            for link in event.get("decision_refs", []):
                if not isinstance(link, Mapping):
                    continue
                decision_id = str(link.get("decision_id") or "")
                try:
                    decision = self.store.get_decision(decision_id)
                except ReviewStoreError:
                    continue
                relation = str(link.get("relation") or "")
                key = (decision_id, event_id, relation)
                result[key] = project(
                    decision,
                    event_id=event_id,
                    relation=relation,
                    link=link,
                )
        for link in self._retrospective_links(bundle):
            decision_id = str(link["decision_id"])
            try:
                decision = self.store.get_decision(decision_id)
            except ReviewStoreError as exc:
                raise _error(
                    409,
                    "retrospective_decision_missing",
                    "回顾性关联引用的决策不存在",
                ) from exc
            event_id = str(link["event_id"])
            relation = "retrospective_context"
            key = (decision_id, event_id, relation)
            result[key] = project(
                decision,
                event_id=event_id,
                relation=relation,
                link=link,
            )
        return [result[key] for key in sorted(result)]

    def _summary(
        self,
        bundle: Mapping[str, Any],
        *,
        latest: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        review = dict(latest or bundle["review"])
        receipt = bundle["receipt"]
        episode = bundle["episode"]
        run_summary = bundle["episode_summary"]
        scope = episode.get("scope")
        scope = scope if isinstance(scope, Mapping) else {}
        revision = review.get("revision")
        revision = revision if isinstance(revision, Mapping) else {}
        governance = review.get("governance")
        governance = governance if isinstance(governance, Mapping) else {}
        generation_mode = str(governance.get("generation_mode") or "facts_only")
        return {
            "run_id": receipt["run_id"],
            "run_key": receipt["run_key"],
            "review_id": review["review_id"],
            "episode_id": episode["episode_id"],
            "symbol": scope.get("symbol"),
            "market": scope.get("market"),
            "account_id": scope.get("account_id"),
            "opened_at": episode.get("opened_at"),
            "closed_at": episode.get("closed_at"),
            "episode_status": episode.get("status"),
            "scope": receipt.get("scope"),
            "status": run_summary.get("status", receipt.get("status")),
            "run_status": receipt.get("status"),
            "gap_codes": list(run_summary.get("gap_codes", [])),
            "fact_count": run_summary.get("fact_count"),
            "decision_status": run_summary.get("decision_status"),
            "content_id": review.get("content_id"),
            "revision_no": revision.get("revision_no"),
            "generation_mode": generation_mode,
            "correctable": generation_mode in {"model_assisted", "human_authored"},
        }

    def list_reviews(
        self,
        *,
        scope: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        if scope is not None and scope not in {"single", "weekly", "monthly"}:
            raise _error(400, "invalid_scope", "scope 必须是 single/weekly/monthly")
        if status is not None and status not in {
            "ready",
            "partial",
            "blocked",
            "failed",
            "unknown",
            "queued",
            "running",
        }:
            raise _error(400, "invalid_status", "status 筛选值无效")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
            raise _error(400, "invalid_limit", "limit 必须在 1 到 200 之间")

        reviews: list[dict[str, Any]] = []
        try:
            receipt_catalog = self.catalog.list_receipts()
            run_status_catalog = self.catalog.list_run_statuses()
        except (ReviewRunnerError, ReviewStoreError) as exc:
            raise _error(503, "review_catalog_unavailable", "复盘目录不可用") from exc
        receipt_run_ids: set[str] = set()
        for run_item in receipt_catalog["runs"]:
            if scope is not None and run_item["scope"] != scope:
                continue
            try:
                receipt = self.catalog.get_receipt(str(run_item["run_id"]))
            except (ReviewRunnerError, ReviewStoreError):
                if status is None or status == "failed":
                    reviews.append(
                        {
                            "run_id": run_item.get("run_id"),
                            "run_key": run_item.get("run_key"),
                            "review_id": None,
                            "episode_id": None,
                            "symbol": None,
                            "market": None,
                            "account_id": None,
                            "opened_at": None,
                            "closed_at": None,
                            "episode_status": "unknown",
                            "scope": run_item.get("scope"),
                            "status": "failed",
                            "run_status": "failed",
                            "gap_codes": ["RUN_RECEIPT_INVALID"],
                            "fact_count": 0,
                            "decision_status": "unknown",
                            "content_id": None,
                            "revision_no": None,
                            "generation_mode": "facts_only",
                            "correctable": False,
                            "requested_at": None,
                        }
                    )
                receipt_run_ids.add(str(run_item.get("run_id") or ""))
                continue
            receipt_run_ids.add(str(receipt["run_id"]))
            if status is not None and run_item["status"] != status:
                continue
            for episode in receipt.get("episodes", []):
                if not isinstance(episode, Mapping):
                    continue
                try:
                    bundle = self._bundle(
                        receipt["run_id"],
                        episode.get("review_id"),
                    )
                    latest, _ = self._latest_review(bundle)
                except InvestmentReviewServiceError as exc:
                    raise _error(
                        503,
                        "review_artifact_validation_failed",
                        "复盘产物校验失败，无法安全展示",
                    ) from exc
                reviews.append(self._summary(bundle, latest=latest))

        for run in receipt_catalog.get("invalid_runs", []):
            if not isinstance(run, Mapping):
                continue
            run_status = "failed"
            if scope is not None and run.get("scope") != scope:
                continue
            if status is not None and run_status != status:
                continue
            receipt_run_ids.add(str(run.get("run_id") or ""))
            reviews.append(
                {
                    "run_id": run.get("run_id"),
                    "run_key": run.get("run_key"),
                    "review_id": None,
                    "episode_id": None,
                    "symbol": None,
                    "market": None,
                    "account_id": None,
                    "opened_at": None,
                    "closed_at": None,
                    "episode_status": "unknown",
                    "scope": run.get("scope"),
                    "status": run_status,
                    "run_status": run_status,
                    "gap_codes": list(
                        run.get("gap_codes") or ["RUN_RECEIPT_INVALID"]
                    ),
                    "fact_count": 0,
                    "decision_status": "unknown",
                    "content_id": None,
                    "revision_no": None,
                    "generation_mode": "facts_only",
                    "correctable": False,
                    "requested_at": run.get("requested_at"),
                }
            )

        for run in run_status_catalog["runs"]:
            run_status = str(run.get("status") or "unknown")
            if run.get("run_id") in receipt_run_ids:
                continue
            if scope is not None and run.get("scope") != scope:
                continue
            if status is not None and run_status != status:
                continue
            if run_status not in {"queued", "running", "blocked", "failed"}:
                continue
            reviews.append(
                {
                    "run_id": run.get("run_id"),
                    "run_key": run.get("run_key"),
                    "review_id": None,
                    "episode_id": None,
                    "symbol": None,
                    "market": None,
                    "account_id": None,
                    "opened_at": None,
                    "closed_at": None,
                    "episode_status": "unknown",
                    "scope": run.get("scope"),
                    "status": run_status,
                    "run_status": run_status,
                    "gap_codes": [f"RUN_{run_status.upper()}"],
                    "fact_count": 0,
                    "decision_status": "unknown",
                    "content_id": None,
                    "revision_no": None,
                    "generation_mode": "facts_only",
                    "correctable": False,
                    "requested_at": run.get("requested_at"),
                }
            )
        reviews.sort(
            key=lambda item: (
                str(item.get("opened_at") or item.get("requested_at") or ""),
                str(item.get("run_id") or ""),
                str(item.get("episode_id") or ""),
            ),
            reverse=True,
        )
        selected = reviews[:limit]
        aggregate = (
            "failed"
            if any(item["status"] == "failed" for item in selected)
            else "blocked"
            if any(item["status"] == "blocked" for item in selected)
            else "partial"
            if any(item["status"] == "partial" for item in selected)
            else "ready"
            if selected
            else "unknown"
        )
        return _envelope(
            status=aggregate,
            data={
                "count": len(selected),
                "total_count": len(reviews),
                "reviews": selected,
            },
            gaps=sorted(
                {
                    gap
                    for item in selected
                    for gap in item.get("gap_codes", [])
                }
            ),
        )

    def get_review_detail(
        self, run_id: object, review_id: object
    ) -> dict[str, Any]:
        bundle = self._bundle(run_id, review_id)
        latest, chain = self._latest_review(bundle)
        summary = self._summary(bundle, latest=latest)
        governance = latest.get("governance")
        governance = governance if isinstance(governance, Mapping) else {}
        mode = str(governance.get("generation_mode") or "facts_only")
        history = list_episode_review_revisions(chain)
        revision = latest.get("revision")
        revision = revision if isinstance(revision, Mapping) else {}
        return _envelope(
            status=_current_status(summary["status"]),
            ref={
                **self._ref(bundle),
                "content_id": latest.get("content_id"),
            },
            data={
                "summary": summary,
                "revision": {
                    **dict(revision),
                    "content_id": latest.get("content_id"),
                    "generation_mode": mode,
                    "history": history,
                },
                "correction_capability": {
                    "correctable": mode in {"model_assisted", "human_authored"},
                    "reason": (
                        "interpreted_revision_available"
                        if mode in {"model_assisted", "human_authored"}
                        else "facts_only_has_no_interpretation_to_correct"
                    ),
                },
                "current_decisions": self._current_decisions(bundle),
                "frozen_decision_linkage": bundle["episode"].get(
                    "decision_linkage"
                ),
                "interpretation_sections": latest.get("interpretation_sections"),
                "warnings": latest.get("warnings", []),
            },
            gaps=summary["gap_codes"],
        )

    def get_timeline(self, run_id: object, review_id: object) -> dict[str, Any]:
        bundle = self._bundle(run_id, review_id)
        receipt = bundle["receipt"]
        episode = bundle["episode"]
        projection_events = self._projection_events(bundle)
        cutoffs = receipt.get("cutoffs")
        cutoffs = cutoffs if isinstance(cutoffs, Mapping) else {}
        events: list[dict[str, Any]] = []
        for raw in episode.get("event_refs", []):
            if not isinstance(raw, Mapping):
                continue
            event = dict(raw)
            event_id = str(event.get("event_id") or "")
            try:
                current_fee = self.store.get_effective_fee(event_id)
                frozen_fee = self.store.get_effective_fee(
                    event_id,
                    as_of=cutoffs.get("review_cutoff"),
                    knowledge_cutoff=cutoffs.get("knowledge_cutoff"),
                )
            except ReviewStoreError:
                current_fee = {
                    "event_id": event_id,
                    "status": "unknown",
                    "amount": None,
                    "currency": "CNY",
                    "source": "missing",
                }
                frozen_fee = dict(current_fee)
            projected = projection_events.get(event_id, {})
            event.pop("source_refs", None)
            events.append(
                {
                    **event,
                    "fee": current_fee,
                    "frozen_fee": frozen_fee,
                    "decision_refs": [
                        {
                            "decision_id": item.get("decision_id"),
                            "relation": item.get("relation"),
                            "known_at": item.get("known_at"),
                            "status": item.get("status"),
                        }
                        for item in projected.get("decision_refs", [])
                        if isinstance(item, Mapping)
                    ],
                }
            )
        events.sort(
            key=lambda item: (
                str(item.get("effective_at") or ""),
                str(item.get("event_id") or ""),
            )
        )
        summary = self._summary(bundle)
        return _envelope(
            status=_current_status(summary["status"]),
            ref=self._ref(bundle),
            data={
                "events": events,
                "snapshot_links": list(episode.get("snapshot_links", [])),
                "frozen_cutoffs": {
                    "as_of": cutoffs.get("as_of"),
                    "knowledge_cutoff": cutoffs.get("knowledge_cutoff"),
                },
            },
            gaps=summary["gap_codes"],
        )

    def get_context(self, run_id: object, review_id: object) -> dict[str, Any]:
        bundle = self._bundle(run_id, review_id)
        context = bundle["context"]
        contexts = list(context.get("contexts", []))
        snapshot_statuses = {
            str(item.get("portfolio_snapshot", {}).get("status") or "missing")
            for item in contexts
            if isinstance(item, Mapping)
        }
        status = (
            "missing"
            if not contexts or snapshot_statuses == {"missing"}
            else "partial"
            if snapshot_statuses - {"ready", "available"}
            else "ready"
        )
        return _envelope(
            status=status,
            ref=self._ref(bundle),
            data={
                "status": status,
                "as_of": context.get("as_of"),
                "knowledge_cutoff": context.get("knowledge_cutoff"),
                "contexts": _public_projection(contexts),
                "deltas": _public_projection(context.get("deltas", [])),
                "warnings": _public_projection(context.get("warnings", [])),
                "source_binding": _public_projection(
                    context.get("source_binding")
                ),
            },
            gaps=[
                warning.get("code")
                for warning in context.get("warnings", [])
                if isinstance(warning, Mapping) and warning.get("code")
            ],
        )

    def get_evidence(self, run_id: object, review_id: object) -> dict[str, Any]:
        bundle = self._bundle(run_id, review_id)
        latest, _ = self._latest_review(bundle)
        sections: list[dict[str, Any]] = []
        fact_sections = latest.get("fact_sections")
        if isinstance(fact_sections, Mapping):
            for name in sorted(fact_sections):
                section = fact_sections[name]
                if not isinstance(section, Mapping):
                    continue
                sections.append(
                    {
                        "name": name,
                        "status": section.get(
                            "status", section.get("availability", "unknown")
                        ),
                        "reason": section.get("reason"),
                        "gap_codes": list(section.get("gap_codes", [])),
                        "warning_codes": list(section.get("warning_codes", [])),
                        "facts": _public_projection(
                            list(section.get("facts", []))
                        ),
                    }
                )
        inventory = []
        for item in bundle["input"].get("source_inventory", []):
            if not isinstance(item, Mapping):
                continue
            inventory.append(
                {
                    key: item.get(key)
                    for key in (
                        "source_id",
                        "source_kind",
                        "content_id",
                        "effective_at",
                        "knowledge_at",
                        "status",
                        "warning_codes",
                    )
                }
            )
        summary = self._summary(bundle, latest=latest)
        return _envelope(
            status=_current_status(summary["status"]),
            ref={
                **self._ref(bundle),
                "content_id": latest.get("content_id"),
            },
            data={
                "sections": sections,
                "source_inventory": inventory,
                "warnings": _public_projection(
                    latest.get("warnings", [])
                ),
            },
            gaps=summary["gap_codes"],
        )

    @staticmethod
    def _run_health_projection(value: object) -> dict[str, Any] | None:
        if not isinstance(value, Mapping):
            return None
        run = value.get("run")
        event = value.get("status_event")
        return {
            "run_id": run.get("run_id") if isinstance(run, Mapping) else None,
            "scope": run.get("scope") if isinstance(run, Mapping) else None,
            "status": value.get("status"),
            "requested_at": (
                run.get("requested_at") if isinstance(run, Mapping) else None
            ),
            "status_occurred_at": (
                event.get("occurred_at") if isinstance(event, Mapping) else None
            ),
        }

    @staticmethod
    def _automation_health_projection(value: object) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            return {
                "enabled": False,
                "state": "failed",
                "worker_alive": False,
                "queue_depth": 0,
                "run_count": 0,
                "latest": None,
                "last_success": None,
                "last_completed": None,
                "last_failure": {
                    "status": "failed",
                    "error_type": "AutomationHealthUnavailable",
                },
            }

        def count(item: object) -> int:
            try:
                return max(0, int(item or 0))
            except (TypeError, ValueError):
                return 0

        def project_run(item: object) -> dict[str, Any] | None:
            if not isinstance(item, Mapping):
                return None
            scopes: list[dict[str, Any]] = []
            raw_scopes = item.get("scope_runs")
            if isinstance(raw_scopes, list):
                for scope in raw_scopes:
                    if not isinstance(scope, Mapping):
                        continue
                    scopes.append(
                        {
                            key: scope.get(key)
                            for key in (
                                "scope",
                                "run_id",
                                "run_key",
                                "status",
                                "content_id",
                            )
                        }
                    )
            return {
                key: item.get(key)
                for key in (
                    "run_id",
                    "run_key",
                    "status",
                    "requested_at",
                    "source_cutoff",
                    "status_occurred_at",
                    "source_cutoff_id",
                    "projection_sha256",
                    "attempt",
                    "retryable",
                    "error_type",
                )
            } | {"scope_runs": scopes}

        return {
            "enabled": value.get("enabled") is True,
            "state": str(value.get("state") or "unknown"),
            "worker_alive": value.get("worker_alive") is True,
            "queue_depth": count(value.get("queue_depth")),
            "run_count": count(value.get("run_count")),
            "latest": project_run(value.get("latest")),
            "last_success": project_run(value.get("last_success")),
            "last_completed": project_run(value.get("last_completed")),
            "last_failure": project_run(value.get("last_failure")),
        }

    def get_health(self) -> dict[str, Any]:
        if self.sync_service is None:
            sync = {
                "status": "unknown",
                "counts": {
                    "source_seen": None,
                    "sidecar_seen": None,
                    "unsynced": None,
                },
                "lag": {"unsynced": None, "source_cutoff_id": None},
                "fees": {"actual": 0, "estimated": 0, "unknown": 0},
                "last_success": None,
                "last_failure": None,
            }
        else:
            try:
                raw = self.sync_service.status()
            except Exception:
                raw = {
                    "status": "failed",
                    "counts": {},
                    "lag": {},
                    "fees": {},
                }
            counts = raw.get("counts")
            counts = counts if isinstance(counts, Mapping) else {}
            lag = raw.get("lag")
            lag = lag if isinstance(lag, Mapping) else {}
            fees = raw.get("fees")
            fees = fees if isinstance(fees, Mapping) else {}
            sync = {
                "status": _current_status(raw.get("status")),
                "counts": {
                    "source_seen": counts.get("source_seen"),
                    "sidecar_seen": counts.get("sidecar_seen"),
                    "unsynced": counts.get("unsynced"),
                },
                "lag": {
                    "unsynced": lag.get("unsynced", counts.get("unsynced")),
                    "source_cutoff_id": lag.get("source_cutoff_id"),
                },
                "fees": {
                    "actual": fees.get("actual", 0),
                    "estimated": fees.get("estimated", 0),
                    "unknown": fees.get("unknown", 0),
                },
                "last_success": self._run_health_projection(
                    raw.get("last_success")
                ),
                "last_failure": self._run_health_projection(
                    raw.get("last_failure")
                ),
            }
        try:
            runs = self.catalog.list_run_statuses()["runs"]
        except (ReviewRunnerError, ReviewStoreError):
            runs = []
        counts_by_status = Counter(str(item.get("status") or "unknown") for item in runs)
        review_health = {
            "count": len(runs),
            "by_status": dict(sorted(counts_by_status.items())),
            "latest": runs[-1] if runs else None,
            "last_failure": next(
                (
                    item
                    for item in reversed(runs)
                    if item.get("status") in {"failed", "blocked"}
                ),
                None,
            ),
        }
        try:
            if self.automation_status_provider is not None:
                raw_automation = self.automation_status_provider()
            else:
                from .review_integration import review_automation_health

                raw_automation = review_automation_health(
                    self.store,
                    enabled=False,
                )
        except Exception:
            raw_automation = {
                "enabled": True,
                "state": "failed",
                "last_failure": {
                    "status": "failed",
                    "error_type": "AutomationHealthUnavailable",
                },
            }
        automation = self._automation_health_projection(raw_automation)
        status = str(sync["status"])
        latest_run_status = (
            str(runs[-1].get("status") or "unknown") if runs else None
        )
        if status == "healthy" and latest_run_status in {
            "failed",
            "blocked",
            "queued",
            "running",
        }:
            status = latest_run_status
        automation_state = str(automation.get("state") or "unknown")
        severity = {
            "healthy": 0,
            "ready": 0,
            "complete": 0,
            "available": 0,
            "unknown": 1,
            "missing": 2,
            "missing_sidecar": 3,
            "schema_not_initialized": 3,
            "unavailable": 3,
            "queued": 4,
            "running": 4,
            "partial": 5,
            "lagging": 5,
            "blocked": 6,
            "invalid_sidecar": 7,
            "failed": 8,
        }
        if automation.get("enabled") is True and automation_state in {
            "failed",
            "blocked",
            "queued",
            "running",
            "partial",
        } and severity.get(automation_state, 1) > severity.get(status, 1):
            status = automation_state
        health_gaps: list[str] = []
        if sync["lag"].get("unsynced"):
            health_gaps.append("REVIEW_SYNC_LAG")
        if automation.get("enabled") is True and automation_state in {
            "failed",
            "blocked",
            "partial",
        }:
            health_gaps.append(
                "REVIEW_AUTOMATION_" + automation_state.upper()
            )
        return _envelope(
            status=_current_status(status),
            data={
                "status": _current_status(status),
                "counts": sync["counts"],
                "lag": sync["lag"],
                "fees": sync["fees"],
                "last_success": sync["last_success"],
                "last_failure": sync["last_failure"],
                "reviews": review_health,
                "automation": automation,
                "boundary": dict(API_BOUNDARY),
            },
            gaps=health_gaps,
        )

    def _event_for_command(
        self,
        payload: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        bundle = self._bundle(payload.get("run_id"), payload.get("review_id"))
        event_id = _required_id(payload.get("event_id"), "event_id", _EVENT_ID)
        events = self._projection_events(bundle)
        event = events.get(event_id)
        if event is None:
            raise _error(
                404,
                "event_not_in_review",
                "指定成交不属于该复盘",
            )
        return bundle, event

    def _decision_lock(self, decision_id: str) -> threading.Lock:
        with self._lock_guard:
            return self._decision_locks.setdefault(
                decision_id,
                threading.Lock(),
            )

    def create_decision(self, payload: object) -> dict[str, Any]:
        value = _object_payload(
            payload,
            required={
                "request_id",
                "run_id",
                "review_id",
                "event_id",
                "occurred_at",
                "known_at",
                "thesis",
                "status",
            },
            optional={
                "trigger_text",
                "invalidation_text",
                "expected_horizon",
                "portfolio_role",
                "direct_reason",
                "risk_notes",
                "raw_note",
            },
        )
        request_id = _request_id(value["request_id"])
        bundle, event = self._event_for_command(value)
        occurred_at = _timestamp(value["occurred_at"], "occurred_at")
        known_at = _timestamp(value["known_at"], "known_at")
        if known_at < occurred_at:
            raise _error(
                422,
                "decision_time_order_invalid",
                "known_at 不能早于 occurred_at",
            )
        status = _bounded_text(value["status"], "status", required=True, maximum=16)
        if status not in {"OPEN", "CLOSED", "INVALIDATED", "WATCHING"}:
            raise _error(422, "decision_status_invalid", "决策状态无效")
        note_fields = {
            field: _bounded_text(value.get(field), field)
            for field in (
                "trigger_text",
                "invalidation_text",
                "expected_horizon",
                "portfolio_role",
                "direct_reason",
                "risk_notes",
                "raw_note",
            )
        }
        material = {
            "request_id": request_id,
            "run_id": value["run_id"],
            "review_id": value["review_id"],
            "event_id": value["event_id"],
            "occurred_at": occurred_at,
            "known_at": known_at,
            "thesis": _bounded_text(
                value["thesis"], "thesis", required=True
            ),
            "status": status,
            **note_fields,
        }
        decision_id = _stable_id(
            "dec",
            {
                "request_id": request_id,
                "run_id": value["run_id"],
                "review_id": value["review_id"],
                "event_id": value["event_id"],
            },
        )
        decision = DecisionRecord(
            decision_id=decision_id,
            symbol=str(event["symbol"]).strip().upper(),
            market=(
                str(event["market"]).strip().upper()
                if event.get("market")
                else None
            ),
            occurred_at=occurred_at,
            known_at=known_at,
            thesis=str(material["thesis"]),
            status=status,
            **note_fields,
        )
        try:
            decision.validate()
        except ModelValidationError as exc:
            raise _error(
                422,
                "decision_rejected",
                "决策记录未通过校验",
            ) from exc
        expected = {
            "decision_id": decision_id,
            "symbol": decision.symbol,
            "market": decision.market,
            "occurred_at": decision.occurred_at,
            "known_at": decision.known_at,
            "status": decision.status,
            "thesis": decision.thesis,
            "trigger_text": decision.trigger_text,
            "invalidation_text": decision.invalidation_text,
            "expected_horizon": decision.expected_horizon,
            "portfolio_role": decision.portfolio_role,
            "direct_reason": decision.direct_reason,
            "risk_notes": decision.risk_notes,
            "raw_note": decision.raw_note,
        }
        with self._decision_lock(decision_id):
            try:
                existing = self.store.get_decision(decision_id)
            except ReviewStoreError:
                existing = None
            if existing is None:
                try:
                    self.store.add_decision(decision)
                except (ReviewStoreError, ModelValidationError) as exc:
                    raise _error(
                        422,
                        "decision_rejected",
                        "决策记录未通过校验",
                    ) from exc
                write_status = "INSERTED"
            else:
                if any(
                    existing.get(key) != item
                    for key, item in expected.items()
                ):
                    raise _error(
                        409,
                        "decision_idempotency_conflict",
                        "request_id 已用于不同的决策内容",
                    )
                write_status = "SKIPPED"
        return _envelope(
            status="ready",
            ref=self._ref(bundle),
            data={
                "status": write_status,
                "decision_id": decision_id,
                "event_id": event["event_id"],
                "linked": False,
                "message": "决策已保存；关联和复盘重跑是独立步骤",
            },
        )

    def link_decision(self, payload: object) -> dict[str, Any]:
        value = _object_payload(
            payload,
            required={
                "run_id",
                "review_id",
                "event_id",
                "decision_id",
                "relation",
            },
        )
        bundle, event = self._event_for_command(value)
        decision_id = _required_id(
            value["decision_id"], "decision_id", _DECISION_ID
        )
        relation = _bounded_text(
            value["relation"], "relation", required=True, maximum=32
        )
        if relation not in {"execution", "retrospective_context"}:
            raise _error(422, "relation_invalid", "决策关联类型无效")
        try:
            decision = self.store.get_decision(decision_id)
        except ReviewStoreError as exc:
            raise _error(404, "decision_not_found", "指定决策不存在") from exc
        if decision.get("symbol") != event.get("symbol"):
            raise _error(
                422,
                "decision_symbol_mismatch",
                "决策与成交证券不一致",
            )
        event_time = str(event.get("occurred_at") or event.get("known_at") or "")
        if relation == "execution" and str(decision.get("known_at") or "") > event_time:
            raise _error(
                422,
                "execution_link_backdating_forbidden",
                "当前补充内容不能伪装为成交前已知；请使用 retrospective_context",
            )
        link_artifact: dict[str, Any] | None = None
        if relation == "retrospective_context":
            link_artifact, link_status = self._append_retrospective_link(
                bundle=bundle,
                event_id=str(event["event_id"]),
                decision=decision,
            )
        else:
            try:
                self.store.link_decision_event(
                    decision_id,
                    event["event_id"],
                    relation,
                )
            except ReviewStoreError as exc:
                raise _error(
                    422,
                    "decision_link_rejected",
                    "决策关联未通过校验",
                ) from exc
            link_status = "LINKED"
        return _envelope(
            status="ready",
            ref=self._ref(bundle),
            data={
                "status": link_status,
                "decision_id": decision_id,
                "event_id": event["event_id"],
                "relation": relation,
                "link_id": (
                    link_artifact.get("link_id")
                    if link_artifact is not None
                    else None
                ),
                "link_content_id": (
                    link_artifact.get("content_id")
                    if link_artifact is not None
                    else None
                ),
                "current_decisions": self._current_decisions(bundle),
                "message": (
                    "回顾性关联已追加保存；不会进入 decision-time P2C"
                    if relation == "retrospective_context"
                    else "成交时点关联已保存；冻结复盘产物尚未重跑"
                ),
            },
        )

    def correct_fee(self, payload: object) -> dict[str, Any]:
        value = _object_payload(
            payload,
            required={
                "request_id",
                "run_id",
                "review_id",
                "event_id",
                "status",
                "amount",
                "currency",
                "effective_at",
                "known_at",
                "reviewer_ref",
                "reason",
                "supersedes_correction_id",
            },
        )
        request_id = _request_id(value["request_id"])
        bundle, event = self._event_for_command(value)
        status = _bounded_text(value["status"], "status", required=True, maximum=16)
        if status not in {"actual", "unknown"}:
            raise _error(422, "fee_status_invalid", "手续费纠正状态无效")
        amount = value["amount"]
        if status == "actual":
            if not isinstance(amount, str) or not _DECIMAL_TEXT.fullmatch(amount):
                raise _error(
                    422,
                    "fee_amount_invalid",
                    "actual 手续费必须是正十进制字符串",
                )
            if Decimal(amount) <= 0:
                raise _error(
                    422,
                    "fee_amount_invalid",
                    "actual 手续费必须大于零",
                )
        elif amount is not None:
            raise _error(
                422,
                "fee_amount_must_be_missing",
                "unknown 手续费必须保留金额缺失",
            )
        currency = _bounded_text(
            value["currency"], "currency", required=True, maximum=8
        )
        if currency != "CNY":
            raise _error(422, "fee_currency_invalid", "当前仅支持 CNY")
        effective_at = _timestamp(value["effective_at"], "effective_at")
        known_at = _timestamp(value["known_at"], "known_at")
        if known_at < effective_at:
            raise _error(
                422,
                "fee_time_order_invalid",
                "known_at 不能早于 effective_at",
            )
        reviewer_ref = _bounded_text(
            value["reviewer_ref"], "reviewer_ref", required=True, maximum=128
        )
        reason = _bounded_text(
            value["reason"], "reason", required=True, maximum=2000
        )
        expected_parent = value["supersedes_correction_id"]
        if expected_parent is not None:
            expected_parent = _bounded_text(
                expected_parent,
                "supersedes_correction_id",
                required=True,
                maximum=128,
            )
        material = {
            "request_id": request_id,
            "run_id": value["run_id"],
            "review_id": value["review_id"],
            "event_id": event["event_id"],
            "status": status,
            "amount": amount,
            "currency": currency,
            "effective_at": effective_at,
            "known_at": known_at,
            "reviewer_ref": reviewer_ref,
            "reason": reason,
            "supersedes_correction_id": expected_parent,
        }
        correction_id = _stable_id(
            "feecorr",
            {
                "request_id": request_id,
                "run_id": value["run_id"],
                "review_id": value["review_id"],
                "event_id": event["event_id"],
            },
        )
        record = FeeCorrectionRecord.from_mapping(
            {
                "correction_id": correction_id,
                "event_id": event["event_id"],
                "status": status,
                "amount": amount,
                "currency": currency,
                "effective_at": effective_at,
                "known_at": known_at,
                "reviewer_ref": reviewer_ref,
                "reason": reason,
                "supersedes_correction_id": expected_parent,
                "provenance": {
                    "request_id": request_id,
                    "run_id": value["run_id"],
                    "review_id": value["review_id"],
                    "source": "investment_review_web",
                },
            }
        )
        corrections = self.store.list_fee_corrections(event_id=event["event_id"])
        replay = next(
            (
                item
                for item in corrections
                if item.get("correction_id") == correction_id
            ),
            None,
        )
        if replay is not None:
            if replay != record.to_dict():
                raise _error(
                    409,
                    "fee_correction_conflict",
                    "手续费纠正内容发生冲突",
                )
            return _envelope(
                status="ready",
                ref=self._ref(bundle),
                data={
                    "correction_id": correction_id,
                    "event_id": event["event_id"],
                    "payload_sha256": hashlib.sha256(
                        canonical_json(replay).encode("utf-8")
                    ).hexdigest(),
                    "status": "SKIPPED",
                    "effective_fee": self.store.get_effective_fee(
                        event["event_id"]
                    ),
                },
            )
        current_parent = (
            corrections[-1].get("correction_id") if corrections else None
        )
        if expected_parent != current_parent:
            raise _error(
                409,
                "stale_fee_correction_parent",
                "手续费纠正父版本已变化，请刷新后重试",
            )
        try:
            saved = self.store.append_fee_correction(record)
        except DataConflictError as exc:
            raise _error(
                409,
                "fee_correction_conflict",
                "手续费纠正内容发生冲突",
            ) from exc
        except (ReviewStoreError, ModelValidationError) as exc:
            raise _error(
                422,
                "fee_correction_rejected",
                "手续费纠正未通过校验",
            ) from exc
        return _envelope(
            status="ready",
            ref=self._ref(bundle),
            data={
                **saved,
                "effective_fee": self.store.get_effective_fee(event["event_id"]),
            },
        )

    def _revision_lock(self, run_id: str, review_id: str) -> threading.Lock:
        key = f"{run_id}\0{review_id}"
        with self._lock_guard:
            return self._revision_locks.setdefault(key, threading.Lock())

    def correct_review(self, payload: object) -> dict[str, Any]:
        value = _object_payload(
            payload,
            required={
                "run_id",
                "review_id",
                "expected_parent_content_id",
                "request",
            },
        )
        run_id = _required_id(value["run_id"], "run_id", _RUN_ID)
        review_id = _required_id(value["review_id"], "review_id", _REVIEW_ID)
        expected_parent = _required_id(
            value["expected_parent_content_id"],
            "expected_parent_content_id",
            _CONTENT_ID,
        )
        request = value["request"]
        if not isinstance(request, Mapping):
            raise _error(400, "review_request_invalid", "request 必须是对象")
        lock = self._revision_lock(run_id, review_id)
        with lock:
            bundle = self._bundle(run_id, review_id)
            latest, _ = self._latest_review(bundle)
            if latest.get("content_id") != expected_parent:
                raise _error(
                    409,
                    "stale_review_parent",
                    "复盘父版本已变化，请刷新后重试",
                )
            mode = str(
                latest.get("governance", {}).get("generation_mode")
                if isinstance(latest.get("governance"), Mapping)
                else ""
            )
            if mode not in {"model_assisted", "human_authored"}:
                raise _error(
                    409,
                    "facts_only_not_correctable",
                    "facts_only 复盘没有可纠正的解释项",
                )
            try:
                revised = apply_human_review(latest, dict(request))
            except EpisodeRevisionError as exc:
                raise _error(
                    422,
                    "review_correction_rejected",
                    "复盘修订未通过既有 P2F 校验",
                ) from exc
            revision = revised.get("revision")
            revision = revision if isinstance(revision, Mapping) else {}
            revision_no = int(revision.get("revision_no", 0))
            content_id = str(revised.get("content_id") or "")
            _required_id(content_id, "content_id", _CONTENT_ID)
            directory = self._revision_directory(run_id, review_id)
            # Keep the deterministic create-only filename short enough for
            # Windows atomic temp-file creation while the full content hash
            # remains inside the validated artifact.
            content_hash = content_id.removeprefix("sha256:")
            output = directory / f"r{revision_no:04d}_{content_hash[:32]}.json"
            try:
                directory.mkdir(parents=True, exist_ok=True)
                if (
                    _is_link_like(self.revision_root)
                    or _is_link_like(directory)
                ):
                    raise _error(
                        409,
                        "revision_path_invalid",
                        "复盘修订目录无效",
                    )
                verified_directory = directory.resolve(strict=True)
                if not _inside(verified_directory, self.revision_root):
                    raise _error(
                        409,
                        "revision_path_invalid",
                        "复盘修订目录无效",
                    )
                output = (
                    verified_directory
                    / f"r{revision_no:04d}_{content_hash[:32]}.json"
                )
                save_new_episode_review(output, revised)
            except InvestmentReviewServiceError:
                raise
            except (EpisodeRevisionError, OSError) as exc:
                raise _error(
                    409,
                    "review_revision_write_conflict",
                    "复盘修订 create-only 写入发生冲突",
                ) from exc
            reloaded, chain = self._latest_review(bundle)
            if reloaded.get("content_id") != content_id:
                raise _error(
                    409,
                    "review_revision_replay_mismatch",
                    "复盘修订重放结果不一致",
                )
            return _envelope(
                status="ready",
                ref={
                    **self._ref(bundle),
                    "content_id": content_id,
                },
                data={
                    "status": "INSERTED",
                    "review_id": review_id,
                    "revision_no": revision_no,
                    "content_id": content_id,
                    "supersedes_content_id": revision.get(
                        "supersedes_content_id"
                    ),
                    "history": list_episode_review_revisions(chain),
                },
            )


__all__ = [
    "API_BOUNDARY",
    "API_SCHEMA_VERSION",
    "InvestmentReviewServiceError",
    "InvestmentReviewWebService",
]
