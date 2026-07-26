"""Deterministic, facts-only investment-review orchestration.

The runner composes the existing sync, P2C, P2E-3 and P2F contracts without
weakening any of their validators.  The portfolio database is always treated
as a read-only source.  Mutable run metadata and immutable artifacts belong to
the explicitly selected review sidecar and checkout-local artifact directory.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from .artifact_io import (
    atomic_create_bytes,
    canonical_json_bytes,
    load_json_object,
    pretty_json_bytes,
)
from .episode_portfolio_context import (
    build_episode_portfolio_context,
    replay_validate_episode_portfolio_context,
    validate_episode_portfolio_context,
)
from .episode_review import (
    build_facts_only_episode_review,
    render_episode_review_markdown,
    replay_validate_episode_review,
    validate_episode_review,
)
from .episodes import (
    build_episode_collection,
    query_episode_collection,
    validate_episode_collection,
)
from .models import canonical_json, sha256_text
from .operation_review import (
    METHOD_VERSION as OPERATION_REVIEW_METHOD_VERSION,
    SCHEMA_VERSION as OPERATION_REVIEW_SCHEMA_VERSION,
    build_operation_review,
    replay_validate_operation_review,
    validate_operation_review,
)
from .portfolio_snapshot_adapter import inspect_portfolio_snapshots
from .review_input_bundle import (
    build_review_input_bundle,
    replay_validate_review_input_bundle,
    validate_review_input_bundle,
)
from .store import ReviewStore, ReviewStoreError
from .sync_service import (
    project_review_fees,
    review_sync_status,
    sync_review_events,
)
from .time_utils import parse_datetime, utc_iso


RUNNER_VERSION = "investment_review.review_runner.v1"
RUN_RECEIPT_SCHEMA_VERSION = "investment_review.review_run_receipt.v1"
RUN_CATALOG_SCHEMA_VERSION = "investment_review.review_catalog.v1"
RUN_SCOPES = frozenset({"single", "weekly", "monthly"})
TERMINAL_RUN_STATUSES = frozenset({"succeeded", "partial", "blocked", "failed"})
COMPLETED_STAGE_NAMES = (
    "sync",
    "fee",
    "snapshot",
    "episode",
    "context",
    "review_input",
    "facts_only",
    "source_replay",
)


class ReviewRunnerError(RuntimeError):
    """Raised when orchestration cannot preserve the frozen contracts."""


class ImmutableArtifactConflict(ReviewRunnerError):
    """Raised when a stable artifact path already contains different bytes."""


class CanonicalGateBlocked(ReviewRunnerError):
    """Raised when an existing canonical validator or source replay blocks."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _utc(value: object, *, field: str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ReviewRunnerError(
                f"{field} must include an explicit timezone or Z suffix"
            )
    else:
        text = str(value).strip()
        if not text:
            raise ReviewRunnerError(f"{field} is required")
        normalized = (
            text[:-1] + "+00:00"
            if text.endswith(("Z", "z"))
            else text
        )
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ReviewRunnerError(
                f"{field} must be an ISO 8601 timestamp with timezone"
            ) from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ReviewRunnerError(
                f"{field} must include an explicit timezone or Z suffix"
            )
    try:
        return parse_datetime(value, "UTC")
    except Exception as exc:
        raise ReviewRunnerError(f"{field} must be an aware timestamp: {exc}") from exc


def _utc_text(value: datetime | str) -> str:
    return utc_iso(value, "UTC")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _resolve_artifact_root(
    value: str | Path | None, *, repo_root: Path
) -> Path:
    candidate = (
        Path(value)
        if value is not None and str(value).strip()
        else Path(".codex_tmp") / "investment_review_runs"
    )
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    resolved = candidate.resolve(strict=False)
    if not _inside(resolved, repo_root):
        raise ReviewRunnerError(
            "review artifacts must remain inside the selected checkout: "
            f"{resolved}"
        )
    return resolved


def _immutable_write(path: Path, data: bytes) -> dict[str, Any]:
    """Create one artifact or verify byte-identical replay."""

    resolved = path.resolve(strict=False)
    if path.exists():
        existing = path.read_bytes()
        if existing != data:
            raise ImmutableArtifactConflict(
                f"IMMUTABLE_ARTIFACT_CONFLICT: {resolved}"
            )
        write_status = "available"
    else:
        try:
            atomic_create_bytes(path, data)
            write_status = "available"
        except FileExistsError:
            existing = path.read_bytes()
            if existing != data:
                raise ImmutableArtifactConflict(
                    f"IMMUTABLE_ARTIFACT_CONFLICT: {resolved}"
                )
            write_status = "available"
    return {
        "path": str(resolved),
        "sha256": _sha256_bytes(data),
        "size_bytes": len(data),
        "write_status": write_status,
    }


def _json_artifact(
    path: Path, value: Mapping[str, Any], *, content_id: str | None = None
) -> dict[str, Any]:
    descriptor = _immutable_write(path, pretty_json_bytes(value))
    if content_id is not None:
        descriptor["content_id"] = content_id
    return descriptor


def _validation_status(value: Mapping[str, Any]) -> str:
    return str(value.get("validation_status") or "blocked")


def _is_blocked(value: Mapping[str, Any]) -> bool:
    return _validation_status(value) == "blocked"


def _finding_codes(value: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            str(item.get("code"))
            for item in value.get("findings", [])
            if isinstance(item, Mapping) and item.get("code")
        }
    )


def _source_verification_ready(value: Mapping[str, Any]) -> bool:
    verification = value.get("source_verification")
    return (
        isinstance(verification, Mapping)
        and verification.get("status") == "verified"
    )


def _stage(
    name: str,
    status: str,
    *,
    details: Mapping[str, Any] | None = None,
    gaps: Iterable[str] = (),
    artifacts: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    if status not in {"ready", "partial", "blocked", "failed"}:
        raise ReviewRunnerError(f"unsupported stage status: {status}")
    return {
        "name": name,
        "status": status,
        "gaps": sorted({str(item) for item in gaps if str(item)}),
        "details": dict(details or {}),
        "artifacts": [dict(item) for item in artifacts],
    }


def _stable_sync_stage(
    payload: Mapping[str, Any], *, mode: str, action: str
) -> dict[str, Any]:
    source = payload.get("source") if isinstance(payload.get("source"), Mapping) else {}
    cutoff = source.get("cutoff") if isinstance(source.get("cutoff"), Mapping) else {}
    counts = payload.get("counts") if isinstance(payload.get("counts"), Mapping) else {}
    fees = payload.get("fees") if isinstance(payload.get("fees"), Mapping) else {}
    fee_counts = (
        fees.get("status_counts")
        if isinstance(fees.get("status_counts"), Mapping)
        else {
            key: fees.get(key, 0)
            for key in ("actual", "estimated", "unknown")
        }
    )
    return {
        "mode": mode,
        "action": action,
        "service_status": str(payload.get("status") or "unknown"),
        "source_path": str(source.get("path") or ""),
        "source_sha256": str(source.get("sha256") or ""),
        "mapping_sha256": str(source.get("mapping_sha256") or ""),
        "cutoff": dict(cutoff),
        "counts": {
            key: int(counts.get(key, 0) or 0)
            for key in (
                "source_seen",
                "sidecar_seen",
                "unsynced",
                "conflicts",
                "inserted",
                "skipped",
            )
        },
        "fee_status_counts": {
            key: int(fee_counts.get(key, 0) or 0)
            for key in ("actual", "estimated", "unknown")
        },
    }


def _stable_fee_stage(payload: Mapping[str, Any], *, mode: str) -> dict[str, Any]:
    source = payload.get("source") if isinstance(payload.get("source"), Mapping) else {}
    counts = payload.get("counts") if isinstance(payload.get("counts"), Mapping) else {}
    fees = payload.get("fees") if isinstance(payload.get("fees"), Mapping) else {}
    fee_counts = (
        fees.get("status_counts")
        if isinstance(fees.get("status_counts"), Mapping)
        else {
            key: fees.get(key, 0)
            for key in ("actual", "estimated", "unknown")
        }
    )
    return {
        "mode": mode,
        "service_status": str(payload.get("status") or "unknown"),
        "cutoff_id": str(
            (
                source.get("cutoff")
                if isinstance(source.get("cutoff"), Mapping)
                else {}
            ).get("cutoff_id")
            or ""
        ),
        "unsynced": int(counts.get("unsynced", 0) or 0),
        "fee_status_counts": {
            key: int(fee_counts.get(key, 0) or 0)
            for key in ("actual", "estimated", "unknown")
        },
        "profile_count": int(
            fees.get("profile_count", fees.get("profiles_inserted", 0)) or 0
        ),
        "projection_count": int(
            fees.get("projection_count", fees.get("projections_inserted", 0)) or 0
        ),
    }


def _select_episodes(
    collection: Mapping[str, Any],
    *,
    scope: str,
    cutoff: datetime,
    episode_id: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if scope not in RUN_SCOPES:
        raise ReviewRunnerError(f"unsupported review scope: {scope}")
    if episode_id and scope != "single":
        raise ReviewRunnerError("--episode-id is only valid for scope=single")

    if episode_id:
        selected = query_episode_collection(
            collection, episode_id=str(episode_id)
        )
        if not selected:
            raise ReviewRunnerError(f"episode was not found at cutoff: {episode_id}")
        window_start = None
        selection_mode = "explicit_episode"
    elif scope == "single":
        all_episodes = query_episode_collection(collection)
        selected = (
            [
                max(
                    all_episodes,
                    key=lambda item: (
                        str(item.get("opened_at") or ""),
                        str(item.get("episode_id") or ""),
                    ),
                )
            ]
            if all_episodes
            else []
        )
        window_start = None
        selection_mode = "latest_episode"
    else:
        days = 7 if scope == "weekly" else 30
        window_start_dt = cutoff - timedelta(days=days)
        selected = query_episode_collection(
            collection,
            interval_start=_utc_text(window_start_dt),
            interval_end=_utc_text(cutoff),
        )
        window_start = _utc_text(window_start_dt)
        selection_mode = "interval_overlap"

    selected.sort(key=lambda item: str(item.get("episode_id") or ""))
    return selected, {
        "mode": selection_mode,
        "scope": scope,
        "window_start": window_start,
        "window_end": _utc_text(cutoff),
        "requested_episode_id": episode_id,
        "selected_episode_ids": [
            str(item.get("episode_id") or "") for item in selected
        ],
    }


def _decision_sources(
    store: ReviewStore, episode: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return only explicitly recorded, canonically linked decision sources."""

    linkage = (
        episode.get("decision_linkage")
        if isinstance(episode.get("decision_linkage"), Mapping)
        else {}
    )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in linkage.get("decision_links", []):
        if isinstance(item, Mapping) and item.get("decision_id"):
            grouped[str(item["decision_id"])].append(dict(item))

    result: list[dict[str, Any]] = []
    gaps: list[str] = []
    for decision_id, links in sorted(grouped.items()):
        relations = sorted(
            {str(item.get("relation") or "") for item in links}
        )
        if len(relations) != 1 or not relations[0]:
            gaps.append(f"DECISION_LINK_AMBIGUOUS:{decision_id}")
            continue
        try:
            row = store.get_decision(decision_id)
        except ReviewStoreError:
            gaps.append(f"DECISION_SOURCE_MISSING:{decision_id}")
            continue
        event_ids = sorted(
            {
                str(item.get("event_id") or "")
                for item in links
                if item.get("event_id")
            }
        )
        payload = {
            key: row.get(key)
            for key in (
                "decision_id",
                "symbol",
                "market",
                "occurred_at",
                "known_at",
                "status",
                "thesis",
                "trigger_text",
                "invalidation_text",
                "expected_horizon",
                "portfolio_role",
                "direct_reason",
                "risk_notes",
                "raw_note",
            )
        }
        result.append(
            {
                "source_id": decision_id,
                "decision_id": decision_id,
                "source_kind": "decision",
                "effective_at": str(row["occurred_at"]),
                "knowledge_at": str(row["known_at"]),
                "locator": f"review-sidecar:decisions/{decision_id}",
                "status": "available",
                "warning_codes": [],
                "event_ids": event_ids,
                "relation": relations[0],
                "payload": payload,
            }
        )
    if not grouped:
        gaps.append("RECORDED_DECISION_MISSING")
    return result, sorted(gaps)


def _sidecar_projection_state(
    store: ReviewStore,
) -> tuple[list[dict[str, Any]], str]:
    """Freeze the event/link/Decision inputs that can affect P2C or P2F."""

    events = store.list_episode_projection_inputs()
    linked_decision_ids = sorted(
        {
            str(ref.get("decision_id") or "")
            for event in events
            for ref in event.get("decision_refs", [])
            if isinstance(ref, Mapping) and ref.get("decision_id")
        }
    )
    decisions = [
        store.get_decision(decision_id)
        for decision_id in linked_decision_ids
    ]
    digest = sha256_text(
        canonical_json(
            {
                "events": events,
                "linked_decisions": decisions,
            }
        )
    )
    return events, digest


def _section_gap_codes(review: Mapping[str, Any]) -> list[str]:
    result: set[str] = set()
    sections = review.get("fact_sections")
    if not isinstance(sections, Mapping):
        return ["FACT_SECTIONS_MISSING"]
    for section in sections.values():
        if not isinstance(section, Mapping):
            continue
        result.update(
            str(item)
            for item in section.get("gap_codes", [])
            if str(item)
        )
        section_status = str(
            section.get("status") or section.get("availability") or ""
        )
        if section_status in {
            "missing",
            "partial",
            "ambiguous",
            "invalid",
            "unlinked",
            "withheld_by_cutoff",
        }:
            result.add("SECTION_" + section_status.upper())
    return sorted(result)


def _receipt_content_id(receipt: Mapping[str, Any]) -> str:
    material = deepcopy(dict(receipt))
    material["content_id"] = ""
    return "sha256:" + _sha256_bytes(canonical_json_bytes(material))


class ReviewRunner:
    """Stable service interface for single, weekly and monthly facts-only runs."""

    def __init__(
        self,
        *,
        review_db: str | Path,
        portfolio_db: str | Path,
        mapping_path: str | Path | None = None,
        artifact_root: str | Path | None = None,
        repo_root: str | Path | None = None,
    ) -> None:
        self.repo_root = (
            Path(repo_root).resolve()
            if repo_root is not None
            else _repo_root()
        )
        review_candidate = Path(review_db).expanduser()
        if not review_candidate.is_absolute():
            review_candidate = self.repo_root / review_candidate
        self.review_db = review_candidate.resolve(strict=False)
        portfolio_candidate = Path(portfolio_db).expanduser()
        if not portfolio_candidate.is_absolute():
            portfolio_candidate = self.repo_root / portfolio_candidate
        self.portfolio_db = portfolio_candidate.resolve(strict=False)
        mapping_candidate = (
            Path(mapping_path).expanduser()
            if mapping_path is not None and str(mapping_path).strip()
            else Path("config")
            / "investment_review.portfolio.reviewed.json"
        )
        if not mapping_candidate.is_absolute():
            mapping_candidate = self.repo_root / mapping_candidate
        self.mapping_path = mapping_candidate.resolve(strict=False)
        self.artifact_root = _resolve_artifact_root(
            artifact_root, repo_root=self.repo_root
        )
        if not _inside(self.review_db, self.repo_root):
            raise ReviewRunnerError(
                "review sidecar must remain inside the selected checkout"
            )
        if self.review_db == self.portfolio_db:
            raise ReviewRunnerError(
                "portfolio source and review sidecar must be different files"
            )

    def _append_status(
        self,
        store: ReviewStore,
        *,
        run_id: str,
        status: str,
        details: Mapping[str, Any],
    ) -> dict[str, Any]:
        existing = store.get_review_run(run_id)
        last_time = None
        if existing["history"]:
            last_time = _utc(
                existing["history"][-1]["occurred_at"],
                field="last run status time",
            )
        event_time = datetime.now(timezone.utc).replace(microsecond=0)
        if last_time is not None and event_time <= last_time:
            event_time = last_time + timedelta(seconds=1)
        timestamp = _utc_text(event_time)
        event_id = "runstatus_" + sha256_text(
            canonical_json(
                {
                    "run_id": run_id,
                    "status": status,
                    "occurred_at": timestamp,
                    "details": dict(details),
                }
            )
        )[:32]
        return store.append_review_run_status(
            {
                "run_event_id": event_id,
                "run_id": run_id,
                "status": status,
                "occurred_at": timestamp,
                "known_at": timestamp,
                "details": dict(details),
            }
        )

    def _existing_terminal_receipt(
        self, store: ReviewStore, *, run_key: str
    ) -> dict[str, Any] | None:
        try:
            run = store.get_review_run(run_key)
        except ReviewStoreError:
            return None
        if run["status"] not in {"succeeded", "partial"}:
            return None
        event = run.get("status_event")
        details = (
            event.get("details")
            if isinstance(event, Mapping)
            and isinstance(event.get("details"), Mapping)
            else {}
        )
        receipt_path = Path(str(details.get("receipt_path") or "")).resolve(
            strict=False
        )
        if not str(details.get("receipt_path") or ""):
            raise ReviewRunnerError(
                f"terminal run has no receipt path: {run_key}"
            )
        if not _inside(receipt_path, self.artifact_root):
            raise ReviewRunnerError(
                f"terminal receipt escaped the trusted artifact root: {receipt_path}"
            )
        receipt_sha256 = _sha256_file(receipt_path)
        if receipt_sha256 != details.get("receipt_sha256"):
            raise CanonicalGateBlocked(
                "terminal receipt hash does not match the run ledger"
            )
        receipt = load_json_object(receipt_path)
        validation = self.validate_receipt(
            receipt, expected_path=receipt_path
        )
        if _is_blocked(validation):
            raise CanonicalGateBlocked(
                "terminal receipt validation blocked: "
                + ",".join(validation["findings"])
            )
        if receipt.get("run_key") != run_key:
            raise ReviewRunnerError("stored receipt run_key does not match run ledger")
        if (
            receipt.get("run_id") != run["run"].get("run_id")
            or receipt.get("scope") != run["run"].get("scope")
            or receipt.get("content_id")
            != details.get("receipt_content_id")
        ):
            raise CanonicalGateBlocked(
                "terminal receipt identity does not match the run ledger"
            )
        return receipt

    def validate_receipt(
        self,
        receipt: Mapping[str, Any],
        *,
        expected_path: Path | None = None,
    ) -> dict[str, Any]:
        findings: list[str] = []
        required_fields = {
            "schema_version",
            "runner_version",
            "content_id",
            "run_id",
            "run_key",
            "scope",
            "mode",
            "status",
            "trigger",
            "cutoffs",
            "selection",
            "source_proof",
            "review_sidecar",
            "stages",
            "episodes",
            "gaps",
            "retry",
            "governance",
        }
        if set(receipt) != required_fields:
            findings.append("MALFORMED_RECEIPT_SHAPE")
        if receipt.get("schema_version") != RUN_RECEIPT_SCHEMA_VERSION:
            findings.append("UNSUPPORTED_RECEIPT_SCHEMA")
        if receipt.get("runner_version") != RUNNER_VERSION:
            findings.append("UNSUPPORTED_RUNNER_VERSION")
        if receipt.get("scope") not in RUN_SCOPES:
            findings.append("INVALID_SCOPE")
        if receipt.get("mode") not in {"dry_run", "apply"}:
            findings.append("INVALID_MODE")
        if receipt.get("status") not in {
            "ready",
            "partial",
            "blocked",
            "failed",
        }:
            findings.append("INVALID_STATUS")
        if not str(receipt.get("run_id") or "").startswith("reviewrun_"):
            findings.append("INVALID_RUN_ID")
        if not str(receipt.get("run_key") or "").startswith("review:"):
            findings.append("INVALID_RUN_KEY")
        if receipt.get("content_id") != _receipt_content_id(receipt):
            findings.append("RECEIPT_CONTENT_ID_MISMATCH")
        stages = receipt.get("stages", [])
        if not isinstance(stages, list):
            findings.append("MALFORMED_STAGES")
            stages = []
        stage_names = [
            str(stage.get("name") or "")
            for stage in stages
            if isinstance(stage, Mapping)
        ]
        if receipt.get("status") in {"ready", "partial"} and tuple(
            stage_names
        ) != COMPLETED_STAGE_NAMES:
            findings.append("INCOMPLETE_STAGE_SET")
        source_proof = receipt.get("source_proof")
        if not isinstance(source_proof, Mapping):
            findings.append("MALFORMED_SOURCE_PROOF")
        elif (
            source_proof.get("read_only") is not True
            or source_proof.get("unchanged") is not True
            or source_proof.get("sha256_before")
            != source_proof.get("sha256_after")
        ):
            findings.append("INVALID_SOURCE_PROOF")
        governance = receipt.get("governance")
        if not isinstance(governance, Mapping):
            findings.append("MALFORMED_GOVERNANCE")
        elif (
            governance.get("facts_only") is not True
            or governance.get("model_called") is not False
            or governance.get("historical_decisions_inferred") is not False
            or governance.get("portfolio_source_written") is not False
            or governance.get("no_advice") is not True
        ):
            findings.append("INVALID_GOVERNANCE")
        selection = receipt.get("selection")
        episodes = receipt.get("episodes")
        if not isinstance(selection, Mapping) or not isinstance(episodes, list):
            findings.append("MALFORMED_SELECTION")
        else:
            selected_ids = selection.get("selected_episode_ids", [])
            episode_ids = [
                str(item.get("episode_id") or "")
                for item in episodes
                if isinstance(item, Mapping)
            ]
            if (
                not isinstance(selected_ids, list)
                or selected_ids != sorted(set(episode_ids))
            ):
                findings.append("EPISODE_SELECTION_MISMATCH")
        for stage in stages:
            if not isinstance(stage, Mapping):
                findings.append("MALFORMED_STAGE")
                continue
            if stage.get("status") not in {
                "ready",
                "partial",
                "blocked",
                "failed",
            }:
                findings.append("INVALID_STAGE_STATUS")
            for artifact in stage.get("artifacts", []):
                if not isinstance(artifact, Mapping):
                    findings.append("MALFORMED_ARTIFACT_DESCRIPTOR")
                    continue
                if receipt.get("mode") == "dry_run":
                    if artifact.get("write_status") != "dry_run":
                        findings.append("INVALID_DRY_RUN_ARTIFACT")
                    if artifact.get("path"):
                        findings.append("DRY_RUN_ARTIFACT_HAS_PATH")
                    digest = str(artifact.get("sha256") or "")
                    if len(digest) != 64:
                        findings.append("INVALID_ARTIFACT_HASH")
                    continue
                path = Path(str(artifact.get("path") or "")).resolve(
                    strict=False
                )
                if not _inside(path, self.artifact_root):
                    findings.append("ARTIFACT_PATH_OUTSIDE_TRUSTED_ROOT")
                    continue
                if not path.is_file():
                    findings.append("ARTIFACT_MISSING")
                elif _sha256_file(path) != artifact.get("sha256"):
                    findings.append("ARTIFACT_HASH_MISMATCH")
                if artifact.get("write_status") != "available":
                    findings.append("INVALID_ARTIFACT_WRITE_STATUS")
        if expected_path is not None and not expected_path.is_file():
            findings.append("RECEIPT_MISSING")
        return {
            "schema_version": "investment_review.review_run_receipt.validation.v1",
            "validation_status": "accepted" if not findings else "blocked",
            "findings": sorted(set(findings)),
        }

    def run(
        self,
        *,
        scope: str,
        as_of: str,
        knowledge_cutoff: str,
        episode_id: str | None = None,
        dry_run: bool = False,
        trigger: str = "manual",
    ) -> dict[str, Any]:
        if scope not in RUN_SCOPES:
            raise ReviewRunnerError(f"unsupported review scope: {scope}")
        as_of_time = _utc(as_of, field="as_of")
        knowledge_time = _utc(
            knowledge_cutoff, field="knowledge_cutoff"
        )
        episode_cutoff = min(as_of_time, knowledge_time)
        review_cutoff = max(as_of_time, knowledge_time)
        mode = "dry_run" if dry_run else "apply"
        stages: list[dict[str, Any]] = []
        source_hash_before = _sha256_file(self.portfolio_db)
        current_stage = "sync"
        preflight_material = {
            "runner_version": RUNNER_VERSION,
            "phase": "preflight",
            "scope": scope,
            "source_path": str(self.portfolio_db),
            "source_sha256": source_hash_before,
            "mapping_path": str(self.mapping_path),
            "review_db": str(self.review_db),
            "artifact_namespace": str(
                self.artifact_root.relative_to(self.repo_root)
            ).replace("\\", "/"),
            "as_of": _utc_text(as_of_time),
            "knowledge_cutoff": _utc_text(knowledge_time),
            "episode_id": episode_id,
        }
        run_key: str | None = (
            "review:preflight:"
            + sha256_text(canonical_json(preflight_material))
        )
        run_id: str | None = "reviewrun_" + sha256_text(run_key)[:32]
        final_run_bound = False
        store: ReviewStore | None = None
        canonical_trigger = "dry_run" if dry_run else trigger

        try:
            preview = sync_review_events(
                self.portfolio_db,
                review_db=self.review_db,
                mapping_path=self.mapping_path,
                dry_run=True,
                trigger=f"review_runner_{trigger}",
                repo_root=self.repo_root,
            )
            preview_counts = preview.get("counts") or {}
            unsynced = int(preview_counts.get("unsynced", 0) or 0)
            if dry_run:
                sync_payload = preview
                sync_action = "validated_without_write"
            elif unsynced:
                sync_payload = sync_review_events(
                    self.portfolio_db,
                    review_db=self.review_db,
                    mapping_path=self.mapping_path,
                    dry_run=False,
                    trigger=f"review_runner_{trigger}",
                    repo_root=self.repo_root,
                )
                sync_action = "reconciled"
            else:
                health = review_sync_status(
                    self.portfolio_db,
                    review_db=self.review_db,
                    mapping_path=self.mapping_path,
                    repo_root=self.repo_root,
                )
                if health.get("status") not in {"healthy"}:
                    sync_payload = sync_review_events(
                        self.portfolio_db,
                        review_db=self.review_db,
                        mapping_path=self.mapping_path,
                        dry_run=False,
                        trigger=f"review_runner_{trigger}",
                        repo_root=self.repo_root,
                    )
                    sync_action = "health_reconciled"
                else:
                    sync_payload = health
                    sync_action = "already_reconciled"

            sync_details = _stable_sync_stage(
                sync_payload, mode=mode, action=sync_action
            )
            sync_counts = sync_details["counts"]
            if (
                sync_counts["unsynced"] != 0
                or sync_counts["source_seen"] != sync_counts["sidecar_seen"]
            ):
                stages.append(
                    _stage(
                        "sync",
                        "blocked",
                        details=sync_details,
                        gaps=["SIDECAR_NOT_RECONCILED_AT_SOURCE_CUTOFF"],
                    )
                )
                return self._early_receipt(
                    scope=scope,
                    mode=mode,
                    as_of=as_of_time,
                    knowledge_cutoff=knowledge_time,
                    episode_cutoff=episode_cutoff,
                    stages=stages,
                    status="blocked",
                    source_hash_before=source_hash_before,
                    run_id=run_id,
                    run_key=run_key,
                    trigger=canonical_trigger,
                )
            stages.append(_stage("sync", "ready", details=sync_details))

            cutoff = sync_details["cutoff"]
            cutoff_id = str(cutoff.get("cutoff_id") or "")
            store = ReviewStore(self.review_db)
            store.status()
            event_inputs, sidecar_projection_sha256 = (
                _sidecar_projection_state(store)
            )
            key_material = {
                "runner_version": RUNNER_VERSION,
                "scope": scope,
                "source_cutoff_id": cutoff_id,
                "source_sha256": sync_details["source_sha256"],
                "mapping_sha256": sync_details["mapping_sha256"],
                "sidecar_projection_sha256": sidecar_projection_sha256,
                "operation_review_schema_version": (
                    OPERATION_REVIEW_SCHEMA_VERSION
                ),
                "operation_review_method_version": (
                    OPERATION_REVIEW_METHOD_VERSION
                ),
                "artifact_namespace": str(
                    self.artifact_root.relative_to(self.repo_root)
                ).replace("\\", "/"),
                "as_of": _utc_text(as_of_time),
                "knowledge_cutoff": _utc_text(knowledge_time),
                "episode_id": episode_id,
            }
            run_key = "review:" + sha256_text(canonical_json(key_material))
            run_id = "reviewrun_" + sha256_text(run_key)[:32]
            final_run_bound = True

            if not dry_run:
                existing = self._existing_terminal_receipt(
                    store, run_key=run_key
                )
                if existing is not None:
                    existing_source = existing.get("source_proof") or {}
                    if (
                        existing_source.get("sha256_before")
                        != source_hash_before
                        or existing_source.get("sha256_after")
                        != source_hash_before
                    ):
                        raise ReviewRunnerError(
                            "completed run source proof does not match the "
                            "current source SHA-256"
                        )
                    if _sha256_file(self.portfolio_db) != source_hash_before:
                        raise ReviewRunnerError(
                            "portfolio source changed while replaying a completed run"
                        )
                    return existing
                try:
                    store.get_review_run(run_key)
                except ReviewStoreError:
                    store.save_review_run(
                        {
                            "run_id": run_id,
                            "run_key": run_key,
                            "scope": scope,
                            "requested_at": _now(),
                            "source_cutoff": (
                                cutoff.get("max_known_at")
                                or _utc_text(episode_cutoff)
                            ),
                            "trigger": trigger,
                            "parameters": {
                                **key_material,
                                "portfolio_db": str(self.portfolio_db),
                                "review_db": str(self.review_db),
                                "mapping_path": str(self.mapping_path),
                                "artifact_root": str(self.artifact_root),
                            },
                        }
                    )
                canonical_trigger = str(
                    store.get_review_run(run_key)["run"]["trigger"]
                )
                self._append_status(
                    store,
                    run_id=run_id,
                    status="running",
                    details={
                        "current_stage": "fee",
                        "attempt_trigger": trigger,
                    },
                )

            current_stage = "fee"
            fee_payload = project_review_fees(
                self.portfolio_db,
                review_db=self.review_db,
                mapping_path=self.mapping_path,
                dry_run=dry_run,
                repo_root=self.repo_root,
            )
            fee_details = _stable_fee_stage(fee_payload, mode=mode)
            if fee_details["unsynced"] != 0:
                raise ReviewRunnerError(
                    "fee projection observed a non-reconciled sidecar"
                )
            stages.append(_stage("fee", "ready", details=fee_details))

            current_stage = "snapshot"
            snapshot_inventory = inspect_portfolio_snapshots(
                self.portfolio_db,
                as_of=as_of_time.astimezone(
                    ZoneInfo("Asia/Shanghai")
                ).date().isoformat(),
                knowledge_cutoff=_utc_text(knowledge_time),
            )
            snapshot_status = str(
                (snapshot_inventory.get("quality") or {}).get("status")
                or snapshot_inventory.get("status")
                or "missing"
            )

            current_stage = "episode"
            collection = build_episode_collection(
                event_inputs,
                cutoff_at=_utc_text(episode_cutoff),
                snapshot_references=snapshot_inventory.get(
                    "snapshot_references", []
                ),
            )
            episode_validation = validate_episode_collection(collection)
            if _is_blocked(episode_validation):
                raise CanonicalGateBlocked(
                    "P2C validation blocked: "
                    + ",".join(_finding_codes(episode_validation))
                )
            operation_review = build_operation_review(
                collection,
                event_inputs=event_inputs,
            )
            operation_validation = validate_operation_review(operation_review)
            if _is_blocked(operation_validation):
                raise CanonicalGateBlocked(
                    "operation review validation blocked: "
                    + ",".join(_finding_codes(operation_validation))
                )
            operation_replay = replay_validate_operation_review(
                operation_review,
                episode_collection=collection,
                event_inputs=event_inputs,
            )
            if (
                _is_blocked(operation_replay)
                or not _source_verification_ready(operation_replay)
            ):
                raise CanonicalGateBlocked(
                    "operation review source replay failed"
                )
            operation_episode_index = {
                str(item.get("episode_id") or ""): dict(item)
                for item in operation_review.get("episode_reviews", [])
                if isinstance(item, Mapping) and item.get("episode_id")
            }
            selected, selection = _select_episodes(
                collection,
                scope=scope,
                cutoff=episode_cutoff,
                episode_id=episode_id,
            )

            run_dir = self.artifact_root / run_id
            artifact_descriptors: list[dict[str, Any]] = []
            if not dry_run:
                snapshot_descriptor = _json_artifact(
                    run_dir / "snapshot_inventory.json",
                    snapshot_inventory,
                    content_id=str(snapshot_inventory.get("content_id") or ""),
                )
                collection_descriptor = _json_artifact(
                    run_dir / "episode_collection.json",
                    collection,
                    content_id="sha256:"
                    + str(collection.get("collection_digest") or ""),
                )
                operation_descriptor = _json_artifact(
                    run_dir / "operation_review.json",
                    operation_review,
                    content_id=str(
                        operation_review.get("content_id") or ""
                    ),
                )
                artifact_descriptors.extend(
                    [
                        snapshot_descriptor,
                        collection_descriptor,
                        operation_descriptor,
                    ]
                )
            else:
                snapshot_descriptor = {
                    "content_id": str(snapshot_inventory.get("content_id") or ""),
                    "sha256": _sha256_bytes(
                        pretty_json_bytes(snapshot_inventory)
                    ),
                    "write_status": "dry_run",
                }
                collection_descriptor = {
                    "content_id": "sha256:"
                    + str(collection.get("collection_digest") or ""),
                    "sha256": _sha256_bytes(pretty_json_bytes(collection)),
                    "write_status": "dry_run",
                }
                operation_descriptor = {
                    "content_id": str(
                        operation_review.get("content_id") or ""
                    ),
                    "sha256": _sha256_bytes(
                        pretty_json_bytes(operation_review)
                    ),
                    "write_status": "dry_run",
                }

            snapshot_gaps = [
                str(item.get("code") or "SNAPSHOT_QUALITY_WARNING")
                if isinstance(item, Mapping)
                else str(item)
                for item in (
                    (snapshot_inventory.get("quality") or {}).get(
                        "warnings", []
                    )
                )
            ]
            stages.append(
                _stage(
                    "snapshot",
                    "ready" if snapshot_status == "complete" else "partial",
                    details={
                        "quality_status": snapshot_status,
                        "snapshot_count": len(
                            snapshot_inventory.get("snapshot_references", [])
                        ),
                        "content_id": snapshot_inventory.get("content_id"),
                        "lineage": snapshot_inventory.get("lineage"),
                    },
                    gaps=snapshot_gaps,
                    artifacts=[snapshot_descriptor],
                )
            )
            stages.append(
                _stage(
                    "episode",
                    (
                        "ready"
                        if _validation_status(episode_validation) == "accepted"
                        else "partial"
                    ),
                    details={
                        "validation_status": _validation_status(
                            episode_validation
                        ),
                        "finding_codes": _finding_codes(episode_validation),
                        "episode_count": len(collection.get("episodes", [])),
                        "selected_count": len(selected),
                        "selection": selection,
                        "collection_digest": collection.get(
                            "collection_digest"
                        ),
                        "operation_review_content_id": (
                            operation_review.get("content_id")
                        ),
                        "operation_review_validation_status": (
                            _validation_status(operation_validation)
                        ),
                        "operation_review_source_replay": "verified",
                        "operation_review_summary": operation_review.get(
                            "summary"
                        ),
                    },
                    gaps=(
                        ["NO_EPISODE_IN_SCOPE"] if not selected else []
                    ),
                    artifacts=[
                        collection_descriptor,
                        operation_descriptor,
                    ],
                )
            )

            episode_results: list[dict[str, Any]] = []
            context_artifacts: list[dict[str, Any]] = []
            input_artifacts: list[dict[str, Any]] = []
            review_artifacts: list[dict[str, Any]] = []
            replay_details: list[dict[str, Any]] = []

            for episode in selected:
                selected_id = str(episode["episode_id"])
                operation_episode = operation_episode_index.get(selected_id)
                if operation_episode is None:
                    raise CanonicalGateBlocked(
                        "operation review omitted selected episode: "
                        + selected_id
                    )
                # Keep nested names deliberately short.  The evidence root and
                # content-addressed IDs are already long enough to hit the
                # legacy Windows MAX_PATH limit once atomic temp suffixes are
                # added.
                episode_dir = run_dir / "e" / selected_id
                current_stage = f"context:{selected_id}"
                context = build_episode_portfolio_context(
                    collection,
                    portfolio_db=self.portfolio_db,
                    as_of=_utc_text(as_of_time),
                    knowledge_cutoff=_utc_text(knowledge_time),
                    episode_ids=[selected_id],
                )
                context_validation = validate_episode_portfolio_context(
                    context
                )
                if _is_blocked(context_validation):
                    raise CanonicalGateBlocked(
                        f"P2E-3 validation blocked for {selected_id}: "
                        + ",".join(_finding_codes(context_validation))
                    )
                context_replay = replay_validate_episode_portfolio_context(
                    context,
                    episode_collection=collection,
                    portfolio_db=self.portfolio_db,
                )
                if (
                    _is_blocked(context_replay)
                    or not _source_verification_ready(context_replay)
                ):
                    raise CanonicalGateBlocked(
                        f"P2E-3 source replay failed for {selected_id}"
                    )

                current_stage = f"review_input:{selected_id}"
                decisions, decision_gaps = _decision_sources(store, episode)
                input_bundle = build_review_input_bundle(
                    collection,
                    context,
                    portfolio_db=self.portfolio_db,
                    episode_id=selected_id,
                    review_cutoff=_utc_text(review_cutoff),
                    decision_sources=decisions,
                    supplemental_sources=[],
                )
                input_validation = validate_review_input_bundle(input_bundle)
                if (
                    _is_blocked(input_validation)
                    or input_bundle.get("release_readiness", {}).get("status")
                    != "ready"
                    or input_bundle.get("source_verification", {}).get("status")
                    != "verified"
                ):
                    raise CanonicalGateBlocked(
                        f"P2F input validation blocked for {selected_id}: "
                        + ",".join(_finding_codes(input_validation))
                    )
                input_replay = replay_validate_review_input_bundle(
                    input_bundle,
                    episode_collection=collection,
                    episode_portfolio_context=context,
                    portfolio_db=self.portfolio_db,
                    decision_sources=decisions,
                    supplemental_sources=[],
                )
                if (
                    _is_blocked(input_replay)
                    or not _source_verification_ready(input_replay)
                ):
                    raise CanonicalGateBlocked(
                        f"P2F input source replay failed for {selected_id}"
                    )

                current_stage = f"facts_only:{selected_id}"
                review = build_facts_only_episode_review(input_bundle)
                review_validation = validate_episode_review(review)
                if _is_blocked(review_validation):
                    raise CanonicalGateBlocked(
                        f"P2F facts validation blocked for {selected_id}: "
                        + ",".join(_finding_codes(review_validation))
                    )
                review_replay = replay_validate_episode_review(
                    review, input_bundle=input_bundle
                )
                if (
                    _is_blocked(review_replay)
                    or not _source_verification_ready(review_replay)
                ):
                    raise CanonicalGateBlocked(
                        f"P2F facts source replay failed for {selected_id}"
                    )

                if dry_run:
                    context_descriptor = {
                        "content_id": context.get("content_id"),
                        "sha256": _sha256_bytes(pretty_json_bytes(context)),
                        "write_status": "dry_run",
                    }
                    input_descriptor = {
                        "content_id": input_bundle.get("content_id"),
                        "sha256": _sha256_bytes(
                            pretty_json_bytes(input_bundle)
                        ),
                        "write_status": "dry_run",
                    }
                    review_descriptor = {
                        "content_id": review.get("content_id"),
                        "sha256": _sha256_bytes(pretty_json_bytes(review)),
                        "write_status": "dry_run",
                    }
                    markdown_descriptor = {
                        "sha256": _sha256_bytes(
                            render_episode_review_markdown(review).encode(
                                "utf-8"
                            )
                        ),
                        "write_status": "dry_run",
                    }
                else:
                    context_descriptor = _json_artifact(
                        episode_dir / "context.json",
                        context,
                        content_id=str(context.get("content_id") or ""),
                    )
                    input_descriptor = _json_artifact(
                        episode_dir / "input.json",
                        input_bundle,
                        content_id=str(
                            input_bundle.get("content_id") or ""
                        ),
                    )
                    review_descriptor = _json_artifact(
                        episode_dir / "review.json",
                        review,
                        content_id=str(review.get("content_id") or ""),
                    )
                    markdown_descriptor = _immutable_write(
                        episode_dir / "review.md",
                        render_episode_review_markdown(review).encode("utf-8"),
                    )

                context_artifacts.append(context_descriptor)
                input_artifacts.append(input_descriptor)
                review_artifacts.extend(
                    [review_descriptor, markdown_descriptor]
                )
                review_gaps = sorted(
                    set(decision_gaps + _section_gap_codes(review))
                )
                episode_results.append(
                    {
                        "episode_id": selected_id,
                        "review_id": review.get("review_id"),
                        "status": (
                            "partial" if review_gaps else "ready"
                        ),
                        "decision_status": str(
                            episode.get("decision_linkage", {}).get(
                                "status", "unlinked"
                            )
                        ),
                        "operation_review_status": str(
                            operation_episode.get(
                                "operation_review_status", "blocked"
                            )
                        ),
                        "decision_context_status": str(
                            operation_episode.get(
                                "decision_context_status", "blocked"
                            )
                        ),
                        "operation_count": len(
                            operation_episode.get("operations", [])
                        ),
                        "decision_source_count": len(decisions),
                        "fact_count": sum(
                            len(section.get("facts", []))
                            for section in review.get(
                                "fact_sections", {}
                            ).values()
                            if isinstance(section, Mapping)
                        ),
                        "gap_codes": review_gaps,
                        "context_content_id": context.get("content_id"),
                        "input_content_id": input_bundle.get("content_id"),
                        "review_content_id": review.get("content_id"),
                        "operation_review_content_id": (
                            operation_review.get("content_id")
                        ),
                        "artifacts": {
                            "context": context_descriptor,
                            "input": input_descriptor,
                            "review": review_descriptor,
                            "markdown": markdown_descriptor,
                        },
                    }
                )
                replay_details.append(
                    {
                        "episode_id": selected_id,
                        "context": {
                            "validation_status": _validation_status(
                                context_replay
                            ),
                            "source_verification": "verified",
                            "content_id": context.get("content_id"),
                        },
                        "review_input": {
                            "validation_status": _validation_status(
                                input_replay
                            ),
                            "source_verification": "verified",
                            "content_id": input_bundle.get("content_id"),
                        },
                        "facts_only_review": {
                            "validation_status": _validation_status(
                                review_replay
                            ),
                            "source_verification": "verified",
                            "content_id": review.get("content_id"),
                        },
                        "operation_review": {
                            "validation_status": _validation_status(
                                operation_replay
                            ),
                            "source_verification": "verified",
                            "content_id": operation_review.get("content_id"),
                            "operation_review_status": (
                                operation_episode.get(
                                    "operation_review_status"
                                )
                            ),
                            "decision_context_status": (
                                operation_episode.get(
                                    "decision_context_status"
                                )
                            ),
                        },
                    }
                )

            stages.append(
                _stage(
                    "context",
                    (
                        "partial"
                        if snapshot_status != "complete" or not selected
                        else "ready"
                    ),
                    details={
                        "context_count": len(context_artifacts),
                        "source_replay_verified": len(context_artifacts),
                    },
                    gaps=(
                        snapshot_gaps
                        if selected
                        else ["NO_EPISODE_IN_SCOPE"]
                    ),
                    artifacts=context_artifacts,
                )
            )
            p2f_gaps = sorted(
                {
                    gap
                    for item in episode_results
                    for gap in item["gap_codes"]
                }
            )
            stages.append(
                _stage(
                    "review_input",
                    "partial" if p2f_gaps or not selected else "ready",
                    details={
                        "bundle_count": len(input_artifacts),
                        "release_ready_count": len(input_artifacts),
                    },
                    gaps=p2f_gaps or (
                        ["NO_EPISODE_IN_SCOPE"] if not selected else []
                    ),
                    artifacts=input_artifacts,
                )
            )
            stages.append(
                _stage(
                    "facts_only",
                    "partial" if p2f_gaps or not selected else "ready",
                    details={
                        "review_count": len(episode_results),
                        "generation_mode": "facts_only",
                        "model_called": False,
                        "no_advice": True,
                    },
                    gaps=p2f_gaps or (
                        ["NO_EPISODE_IN_SCOPE"] if not selected else []
                    ),
                    artifacts=review_artifacts,
                )
            )
            stages.append(
                _stage(
                    "source_replay",
                    "ready" if selected else "partial",
                    details={
                        "verified_episode_count": len(replay_details),
                        "episodes": replay_details,
                    },
                    gaps=(
                        ["NO_EPISODE_IN_SCOPE"] if not selected else []
                    ),
                )
            )

            source_hash_after = _sha256_file(self.portfolio_db)
            if source_hash_after != source_hash_before:
                raise CanonicalGateBlocked(
                    "portfolio source SHA-256 changed during review run"
                )
            _, sidecar_projection_after = _sidecar_projection_state(store)
            if sidecar_projection_after != sidecar_projection_sha256:
                raise CanonicalGateBlocked(
                    "review sidecar event/decision projection changed during "
                    "review run"
                )

            overall = (
                "partial"
                if any(stage["status"] == "partial" for stage in stages)
                else "ready"
            )
            receipt: dict[str, Any] = {
                "schema_version": RUN_RECEIPT_SCHEMA_VERSION,
                "runner_version": RUNNER_VERSION,
                "content_id": "",
                "run_id": run_id,
                "run_key": run_key,
                "scope": scope,
                "mode": mode,
                "status": overall,
                "trigger": canonical_trigger,
                "cutoffs": {
                    "as_of": _utc_text(as_of_time),
                    "knowledge_cutoff": _utc_text(knowledge_time),
                    "episode_cutoff": _utc_text(episode_cutoff),
                    "review_cutoff": _utc_text(review_cutoff),
                    "source_cutoff_id": cutoff_id,
                    "sidecar_projection_sha256": (
                        sidecar_projection_sha256
                    ),
                },
                "selection": selection,
                "source_proof": {
                    "path": str(self.portfolio_db),
                    "sha256_before": source_hash_before,
                    "sha256_after": source_hash_after,
                    "unchanged": True,
                    "read_only": True,
                },
                "review_sidecar": {
                    "path": str(self.review_db),
                    "mutated": not dry_run,
                },
                "stages": stages,
                "episodes": episode_results,
                "gaps": sorted(
                    {
                        gap
                        for stage in stages
                        for gap in stage.get("gaps", [])
                    }
                ),
                "retry": {
                    "run_key": run_key,
                    "idempotent": True,
                    "retryable": overall in {"partial"},
                },
                "governance": {
                    "facts_only": True,
                    "model_called": False,
                    "historical_decisions_inferred": False,
                    "portfolio_source_written": False,
                    "no_advice": True,
                },
            }
            receipt["content_id"] = _receipt_content_id(receipt)

            if not dry_run:
                receipt_descriptor = _json_artifact(
                    run_dir / "receipt.json",
                    receipt,
                    content_id=receipt["content_id"],
                )
                self._append_status(
                    store,
                    run_id=run_id,
                    status="partial" if overall == "partial" else "succeeded",
                    details={
                        "receipt_path": receipt_descriptor["path"],
                        "receipt_sha256": receipt_descriptor["sha256"],
                        "receipt_content_id": receipt["content_id"],
                        "episode_count": len(episode_results),
                        "gap_codes": receipt["gaps"],
                    },
                )
            return receipt
        except Exception as exc:
            source_hash_after = (
                _sha256_file(self.portfolio_db)
                if self.portfolio_db.is_file()
                else None
            )
            terminal_status = (
                "blocked"
                if isinstance(
                    exc, (CanonicalGateBlocked, ImmutableArtifactConflict)
                )
                else "failed"
            )
            stages.append(
                _stage(
                    current_stage,
                    terminal_status,
                    details={
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                    gaps=[
                        (
                            "CANONICAL_GATE_BLOCKED"
                            if terminal_status == "blocked"
                            else "RUN_STAGE_FAILED"
                        )
                    ],
                )
            )
            receipt = self._early_receipt(
                scope=scope,
                mode=mode,
                as_of=as_of_time,
                knowledge_cutoff=knowledge_time,
                episode_cutoff=episode_cutoff,
                stages=stages,
                status=terminal_status,
                source_hash_before=source_hash_before,
                source_hash_after=source_hash_after,
                run_id=run_id,
                run_key=run_key,
                trigger=canonical_trigger,
            )
            if not dry_run and not final_run_bound:
                try:
                    preflight_store = ReviewStore(self.review_db)
                    preflight_store.status()
                    try:
                        preflight_store.get_review_run(str(run_key))
                    except ReviewStoreError:
                        preflight_store.save_review_run(
                            {
                                "run_id": str(run_id),
                                "run_key": str(run_key),
                                "scope": scope,
                                "requested_at": _now(),
                                "source_cutoff": _utc_text(episode_cutoff),
                                "trigger": trigger,
                                "parameters": preflight_material,
                            }
                        )
                    store = preflight_store
                except Exception:
                    store = None
            if not dry_run and store is not None and run_id is not None:
                try:
                    self._append_status(
                        store,
                        run_id=run_id,
                        status=terminal_status,
                        details={
                            "failed_stage": current_stage,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                            "attempt_trigger": trigger,
                            "retryable": not isinstance(
                                exc,
                                (
                                    CanonicalGateBlocked,
                                    ImmutableArtifactConflict,
                                ),
                            ),
                        },
                    )
                except Exception:
                    pass
            return receipt

    def _early_receipt(
        self,
        *,
        scope: str,
        mode: str,
        as_of: datetime,
        knowledge_cutoff: datetime,
        episode_cutoff: datetime,
        stages: Sequence[Mapping[str, Any]],
        status: str,
        source_hash_before: str,
        source_hash_after: str | None = None,
        run_id: str | None = None,
        run_key: str | None = None,
        trigger: str = "manual",
    ) -> dict[str, Any]:
        after = (
            source_hash_after
            if source_hash_after is not None
            else _sha256_file(self.portfolio_db)
        )
        receipt: dict[str, Any] = {
            "schema_version": RUN_RECEIPT_SCHEMA_VERSION,
            "runner_version": RUNNER_VERSION,
            "content_id": "",
            "run_id": run_id,
            "run_key": run_key,
            "scope": scope,
            "mode": mode,
            "status": status,
            "trigger": trigger,
            "cutoffs": {
                "as_of": _utc_text(as_of),
                "knowledge_cutoff": _utc_text(knowledge_cutoff),
                "episode_cutoff": _utc_text(episode_cutoff),
                "review_cutoff": _utc_text(max(as_of, knowledge_cutoff)),
                "source_cutoff_id": None,
            },
            "selection": {
                "mode": "not_completed",
                "scope": scope,
                "selected_episode_ids": [],
            },
            "source_proof": {
                "path": str(self.portfolio_db),
                "sha256_before": source_hash_before,
                "sha256_after": after,
                "unchanged": source_hash_before == after,
                "read_only": True,
            },
            "review_sidecar": {
                "path": str(self.review_db),
                "mutated": not mode == "dry_run",
            },
            "stages": [dict(item) for item in stages],
            "episodes": [],
            "gaps": sorted(
                {
                    gap
                    for stage in stages
                    for gap in stage.get("gaps", [])
                }
            ),
            "retry": {
                "run_key": run_key,
                "idempotent": True,
                "retryable": status in {"failed", "partial"},
            },
            "governance": {
                "facts_only": True,
                "model_called": False,
                "historical_decisions_inferred": False,
                "portfolio_source_written": False,
                "no_advice": True,
            },
        }
        receipt["content_id"] = _receipt_content_id(receipt)
        return receipt


class ReviewRunCatalog:
    """Trusted, ID-only read surface over validated runner receipts."""

    def __init__(
        self,
        *,
        review_db: str | Path,
        portfolio_db: str | Path,
        artifact_root: str | Path | None = None,
        repo_root: str | Path | None = None,
    ) -> None:
        self.runner = ReviewRunner(
            review_db=review_db,
            portfolio_db=portfolio_db,
            artifact_root=artifact_root,
            repo_root=repo_root,
        )
        self.store = ReviewStore(self.runner.review_db)

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
        path = Path(raw_path).resolve(strict=False)
        if not _inside(path, self.runner.artifact_root):
            raise ReviewRunnerError("receipt path is outside the trusted root")
        receipt_sha256 = _sha256_file(path)
        if receipt_sha256 != details.get("receipt_sha256"):
            raise ReviewRunnerError(
                "receipt hash does not match the immutable run ledger"
            )
        receipt = load_json_object(path)
        validation = self.runner.validate_receipt(
            receipt, expected_path=path
        )
        if _is_blocked(validation):
            raise ReviewRunnerError(
                "receipt validation blocked: "
                + ",".join(validation["findings"])
            )
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
                if (
                    Path(configured_root).resolve(strict=False)
                    != self.runner.artifact_root
                ):
                    continue
                receipt = self.get_receipt(run["run"]["run_id"])
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
        return {
            "schema_version": RUN_CATALOG_SCHEMA_VERSION,
            "count": len(items),
            "runs": items,
        }

    def _review_descriptor(
        self, review_id: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for item in self.list_receipts()["runs"]:
            receipt = self.get_receipt(str(item["run_id"]))
            for episode in receipt["episodes"]:
                if episode.get("review_id") == review_id:
                    descriptor = episode.get("artifacts", {}).get("review")
                    if isinstance(descriptor, Mapping):
                        matches.append((receipt, dict(descriptor)))
        unique = {
            str(descriptor.get("content_id") or ""): (receipt, descriptor)
            for receipt, descriptor in matches
        }
        if not unique:
            raise ReviewRunnerError(f"review was not found: {review_id}")
        if len(unique) != 1:
            raise ReviewRunnerError(
                f"review ID resolved to multiple revisions: {review_id}"
            )
        return next(iter(unique.values()))

    def get_review(self, review_id: str) -> dict[str, Any]:
        receipt, descriptor = self._review_descriptor(review_id)
        path = Path(str(descriptor["path"])).resolve(strict=False)
        if not _inside(path, self.runner.artifact_root):
            raise ReviewRunnerError("review path is outside the trusted root")
        if _sha256_file(path) != descriptor.get("sha256"):
            raise ReviewRunnerError("review artifact hash mismatch")
        artifact = load_json_object(path)
        validation = validate_episode_review(artifact)
        if _is_blocked(validation):
            raise ReviewRunnerError(
                "review artifact validation blocked: "
                + ",".join(_finding_codes(validation))
            )
        return {
            "schema_version": "investment_review.review_catalog.detail.v1",
            "run_id": receipt["run_id"],
            "run_status": receipt["status"],
            "review": artifact,
            "validation": validation,
        }


__all__ = [
    "CanonicalGateBlocked",
    "ImmutableArtifactConflict",
    "RUNNER_VERSION",
    "RUN_CATALOG_SCHEMA_VERSION",
    "RUN_RECEIPT_SCHEMA_VERSION",
    "RUN_SCOPES",
    "ReviewRunCatalog",
    "ReviewRunner",
    "ReviewRunnerError",
]
