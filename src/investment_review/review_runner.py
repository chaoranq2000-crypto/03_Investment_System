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
from typing import Any, Callable, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from .artifact_io import (
    atomic_create_bytes,
    canonical_json_bytes,
    load_json_object,
    pretty_json_bytes,
)
from .episode_portfolio_context import (
    build_episode_portfolio_context,
    build_ledger_snapshot_supplemental_source,
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
from .models import (
    OPERATION_CHECKPOINT_SCHEMA_VERSION,
    canonical_json,
    sha256_text,
)
from .knowledge_provenance import (
    METHOD_VERSION as KNOWLEDGE_PROVENANCE_METHOD_VERSION,
    SCHEMA_VERSION as KNOWLEDGE_PROVENANCE_SCHEMA_VERSION,
    build_knowledge_provenance,
    project_perspective_event_inputs,
    replay_validate_knowledge_provenance,
    validate_knowledge_provenance,
)
from .operation_review import (
    METHOD_VERSION as OPERATION_REVIEW_METHOD_VERSION,
    SCHEMA_VERSION as OPERATION_REVIEW_SCHEMA_VERSION,
    build_operation_review,
    replay_validate_operation_review,
    validate_operation_review,
)
from .ledger_snapshot_reconstruction import (
    LEDGER_SNAPSHOT_RECONSTRUCTION_SCHEMA_VERSION,
    build_ledger_snapshot_reconstruction,
    replay_validate_ledger_snapshot_reconstruction,
    validate_ledger_snapshot_reconstruction,
)
from .portfolio_snapshot_adapter import (
    inspect_portfolio_snapshots,
    load_cash_baseline_proof,
)
from .review_checkpoint import (
    METHOD_VERSION as REVIEW_CHECKPOINT_METHOD_VERSION,
    build_review_checkpoint,
    canonical_review_checkpoint_bytes,
    replay_validate_review_checkpoint,
    validate_review_checkpoint,
)
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
RUN_PERSPECTIVES = frozenset({"user", "system"})
TERMINAL_RUN_STATUSES = frozenset({"succeeded", "partial", "blocked", "failed"})
LEDGER_RECONSTRUCTION_PROJECTION_MANIFEST_VERSION = (
    "investment_review.ledger_snapshot_projection_manifest.v1"
)
REVIEW_CHECKPOINT_PROJECTION_MANIFEST_VERSION = (
    "investment_review.review_checkpoint_projection_manifest.v1"
)
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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    """Freeze the event/link/Decision inputs that can affect P2C or P2F."""

    events = store.list_episode_projection_inputs()
    observation_rows = store.list_event_observation_evidence(
        event_ids=[
            str(event.get("event_id") or "")
            for event in events
            if event.get("event_id")
        ]
    )
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
                "event_observation_evidence": observation_rows,
                "linked_decisions": decisions,
            }
        )
    )
    return events, observation_rows, digest


def _ledger_reconstruction_artifact_projection(
    artifact: Mapping[str, Any],
    *,
    supplemental_source: Mapping[str, Any],
) -> dict[str, Any]:
    availability = str(supplemental_source.get("availability") or "")
    status_by_availability = {
        "available": "available",
        "ambiguous": "partial",
        "missing": "missing",
        "invalid": "blocked",
    }
    if availability not in status_by_availability:
        raise CanonicalGateBlocked(
            "ledger snapshot supplemental source has invalid availability"
        )
    content_id = str(artifact.get("content_id") or "")
    checkpoints = [
        item
        for item in artifact.get("anchors", [])
        if isinstance(item, Mapping)
        and item.get("anchor_type") == "checkpoint"
    ]
    if len(checkpoints) != 1:
        raise CanonicalGateBlocked(
            "ledger snapshot reconstruction requires one checkpoint anchor"
        )
    checkpoint_axis = (
        checkpoints[0].get("snapshot_cash_valuation")
        if isinstance(
            checkpoints[0].get("snapshot_cash_valuation"),
            Mapping,
        )
        else {}
    )
    checkpoint_fields = (
        checkpoint_axis.get("fields")
        if isinstance(checkpoint_axis.get("fields"), Mapping)
        else {}
    )
    quantity_field = (
        checkpoint_fields.get("position_quantity")
        if isinstance(
            checkpoint_fields.get("position_quantity"),
            Mapping,
        )
        else {}
    )
    reconstructed_ending_quantity = quantity_field.get("value")
    if (
        quantity_field.get("status") not in {"available", "partial"}
        or reconstructed_ending_quantity in (None, "")
    ):
        raise CanonicalGateBlocked(
            "reconstructed checkpoint quantity is unavailable"
        )
    ending_quantity = str(reconstructed_ending_quantity)
    if not content_id.startswith("sha256:") or not ending_quantity:
        raise CanonicalGateBlocked(
            "ledger snapshot reconstruction lacks receipt identity or quantity"
        )
    try:
        reconstruction_as_of = _utc_text(
            _utc(
                artifact.get("as_of"),
                field="ledger_snapshot_reconstruction.as_of",
            )
        )
    except ReviewRunnerError as exc:
        raise CanonicalGateBlocked(
            "ledger snapshot reconstruction lacks a valid as_of"
        ) from exc
    return {
        "schema_version": LEDGER_SNAPSHOT_RECONSTRUCTION_SCHEMA_VERSION,
        "content_id": content_id,
        "status": status_by_availability[availability],
        "ending_quantity": ending_quantity,
        "as_of": reconstruction_as_of,
    }


def _ledger_reconstruction_receipt_projection(
    artifact: Mapping[str, Any],
    *,
    episode: Mapping[str, Any],
    supplemental_source: Mapping[str, Any],
    request_as_of: str,
) -> dict[str, Any]:
    projection = _ledger_reconstruction_artifact_projection(
        artifact,
        supplemental_source=supplemental_source,
    )
    if projection["ending_quantity"] != str(
        episode.get("ending_quantity") or ""
    ):
        raise CanonicalGateBlocked(
            "reconstructed checkpoint quantity does not close to the episode"
        )
    if projection["as_of"] != _episode_reconstruction_as_of(
        episode,
        request_as_of=request_as_of,
    ):
        raise CanonicalGateBlocked(
            "reconstruction as_of does not match the episode boundary"
        )
    return projection


def _ledger_reconstruction_projection_manifest(
    projections_by_episode: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    episodes = [
        {
            "episode_id": episode_id,
            **dict(projections_by_episode[episode_id]),
        }
        for episode_id in sorted(projections_by_episode)
    ]
    material = {
        "schema_version": (
            LEDGER_RECONSTRUCTION_PROJECTION_MANIFEST_VERSION
        ),
        "episodes": episodes,
    }
    return {
        **material,
        "content_id": "sha256:"
        + _sha256_bytes(canonical_json_bytes(material)),
    }


def _review_checkpoint_receipt_projection(
    checkpoint: Mapping[str, Any],
) -> dict[str, Any]:
    validation = validate_review_checkpoint(checkpoint)
    if _is_blocked(validation):
        raise CanonicalGateBlocked(
            "review checkpoint validation blocked: "
            + ",".join(_finding_codes(validation))
        )
    axes = checkpoint.get("status_axes")
    if not isinstance(axes, Mapping):
        raise CanonicalGateBlocked("review checkpoint status axes are missing")
    projections: dict[str, Mapping[str, Any]] = {}
    for name in (
        "operation",
        "decision",
        "snapshot_cash_valuation",
        "market",
        "lifecycle",
        "outcome",
    ):
        axis = axes.get(name)
        if not isinstance(axis, Mapping):
            raise CanonicalGateBlocked(
                f"review checkpoint axis is missing: {name}"
            )
        projections[name] = axis
    lifecycle = str(projections["lifecycle"].get("status") or "")
    outcome = str(projections["outcome"].get("status") or "")
    notices = (
        ["OPEN_EPISODE_OUTCOME_NOT_FINAL"]
        if lifecycle == "open" and outcome == "interim"
        else []
    )
    return {
        "schema_version": OPERATION_CHECKPOINT_SCHEMA_VERSION,
        "checkpoint_id": str(checkpoint.get("checkpoint_id") or ""),
        "checkpoint_key": str(checkpoint.get("checkpoint_key") or ""),
        "content_id": str(checkpoint.get("content_id") or ""),
        "position_case_id": str(
            checkpoint.get("position_case_id") or ""
        ),
        "review_kind": str(checkpoint.get("review_kind") or ""),
        "checkpoint_type": str(checkpoint.get("checkpoint_type") or ""),
        "perspective": str(checkpoint.get("perspective") or ""),
        "as_of": str(checkpoint.get("as_of") or ""),
        "knowledge_cutoff": str(
            checkpoint.get("knowledge_cutoff") or ""
        ),
        "review_readiness": str(
            projections["operation"].get("status") or ""
        ),
        "decision_context_status": str(
            projections["decision"].get("status") or ""
        ),
        "snapshot_cash_valuation_status": str(
            projections["snapshot_cash_valuation"].get("status") or ""
        ),
        "market_status": str(
            projections["market"].get("status") or ""
        ),
        "episode_lifecycle": lifecycle,
        "outcome_maturity": outcome,
        "lifecycle_notices": notices,
    }


def _review_checkpoint_projection_manifest(
    projections_by_episode: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    episodes = [
        {
            "episode_id": episode_id,
            **dict(projections_by_episode[episode_id]),
        }
        for episode_id in sorted(projections_by_episode)
    ]
    material = {
        "schema_version": REVIEW_CHECKPOINT_PROJECTION_MANIFEST_VERSION,
        "episodes": episodes,
    }
    return {
        **material,
        "content_id": "sha256:"
        + _sha256_bytes(canonical_json_bytes(material)),
    }


def _episode_reconstruction_identity(
    episode: Mapping[str, Any],
) -> dict[str, Any]:
    scope = (
        episode.get("scope")
        if isinstance(episode.get("scope"), Mapping)
        else {}
    )
    return {
        "episode_id": str(episode.get("episode_id") or ""),
        "status": str(episode.get("status") or ""),
        "closed_at": episode.get("closed_at"),
        "ending_quantity": str(episode.get("ending_quantity") or ""),
        "scope": {
            key: scope.get(key)
            for key in (
                "account_id",
                "instrument_id",
                "symbol",
                "market",
                "currency",
            )
        },
        "episode_event_ids": [
            str(item.get("event_id") or "")
            for item in episode.get("event_refs", [])
            if isinstance(item, Mapping)
        ],
        "episode_event_ordering_keys": [
            deepcopy(item.get("ordering_key"))
            for item in episode.get("event_refs", [])
            if isinstance(item, Mapping)
        ],
    }


def _episode_reconstruction_as_of(
    episode: Mapping[str, Any],
    *,
    request_as_of: str,
) -> str:
    canonical_request_as_of = _utc(
        request_as_of,
        field="ledger_reconstruction.request_as_of",
    )
    status = str(episode.get("status") or "")
    if status == "open":
        if episode.get("closed_at") not in (None, ""):
            raise CanonicalGateBlocked(
                "open episode has an unexpected closed boundary"
            )
        return _utc_text(canonical_request_as_of)
    if status != "closed":
        raise CanonicalGateBlocked(
            "selected episode has an invalid reconstruction status"
        )
    closed_at = _utc(
        episode.get("closed_at"),
        field="ledger_reconstruction.episode.closed_at",
    )
    if closed_at > canonical_request_as_of:
        raise CanonicalGateBlocked(
            "closed episode boundary exceeds reconstruction request as_of"
        )
    return _utc_text(closed_at)


def _runner_event_ordering_key(
    event: Mapping[str, Any],
) -> tuple[datetime, int, str, str]:
    event_id = str(event.get("event_id") or "")
    if not event_id:
        raise CanonicalGateBlocked(
            "reconstruction input event lacks canonical identity"
        )
    raw = event.get("raw_payload", event.get("raw_payload_json"))
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CanonicalGateBlocked(
                f"reconstruction event {event_id} has invalid raw payload"
            ) from exc
    if not isinstance(raw, Mapping):
        raw = {}
    row = raw.get("source_row", raw)
    if not isinstance(row, Mapping):
        row = raw
    sequence_rank = 2
    sequence_value = str(
        event.get("source_record_id") or event_id
    )
    for key in (
        "source_sequence",
        "source_row",
        "entry_id",
        "row_index",
    ):
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            sequence_rank = 0
            sequence_value = f"{int(value):020d}"
        except (TypeError, ValueError):
            sequence_rank = 1
            sequence_value = str(value)
        break
    return (
        _utc(
            event.get("occurred_at"),
            field=f"reconstruction.event[{event_id}].occurred_at",
        ),
        sequence_rank,
        sequence_value,
        event_id,
    )


def _episode_event_ordering_key(
    event_ref: Mapping[str, Any],
) -> tuple[datetime, int, str, str]:
    event_id = str(event_ref.get("event_id") or "")
    ordering_key = event_ref.get("ordering_key")
    if (
        not event_id
        or not isinstance(ordering_key, list)
        or len(ordering_key) != 4
        or str(ordering_key[3] or "") != event_id
        or isinstance(ordering_key[1], bool)
    ):
        raise CanonicalGateBlocked(
            "closed episode lacks a canonical P2C event cursor"
        )
    try:
        sequence_rank = int(ordering_key[1])
    except (TypeError, ValueError) as exc:
        raise CanonicalGateBlocked(
            "closed episode has an invalid P2C event cursor"
        ) from exc
    sequence_value = str(ordering_key[2] or "")
    if sequence_rank not in {0, 1, 2} or not sequence_value:
        raise CanonicalGateBlocked(
            "closed episode has an invalid P2C source order"
        )
    return (
        _utc(
            ordering_key[0],
            field=f"episode.event_refs[{event_id}].ordering_key",
        ),
        sequence_rank,
        sequence_value,
        event_id,
    )


def _event_inputs_with_episode_boundary_provenance(
    event_inputs: Sequence[Mapping[str, Any]],
    *,
    episode: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    """Validate the P2C cursor while preserving all peer provenance."""

    if str(episode.get("status") or "") == "open":
        return list(event_inputs)
    if str(episode.get("status") or "") != "closed":
        raise CanonicalGateBlocked(
            "selected episode has an invalid cursor status"
        )
    closing_event_id = str(episode.get("closing_event_ref") or "")
    event_refs = [
        item
        for item in episode.get("event_refs", [])
        if isinstance(item, Mapping)
    ]
    closing_refs = [
        item
        for item in event_refs
        if str(item.get("event_id") or "") == closing_event_id
    ]
    if len(closing_refs) != 1:
        raise CanonicalGateBlocked(
            "closed episode lacks one closing event cursor"
        )
    boundary = _episode_event_ordering_key(closing_refs[0])
    ordered_inputs: dict[str, tuple[datetime, int, str, str]] = {}
    input_by_id: dict[str, Mapping[str, Any]] = {}
    for event in event_inputs:
        event_id = str(event.get("event_id") or "")
        if not event_id or event_id in input_by_id:
            raise CanonicalGateBlocked(
                "reconstruction inputs lack unique event identities"
            )
        ordered_inputs[event_id] = _runner_event_ordering_key(event)
        input_by_id[event_id] = event
    if (
        closing_event_id not in ordered_inputs
        or ordered_inputs[closing_event_id] != boundary
    ):
        raise CanonicalGateBlocked(
            "P2C closing cursor does not match reconstruction source order"
        )
    selected_event_ids = {
        str(item.get("event_id") or "") for item in event_refs
    }
    included_ids = {
        event_id
        for event_id, ordering_key in ordered_inputs.items()
        if ordering_key <= boundary
    }
    if not selected_event_ids.issubset(included_ids):
        raise CanonicalGateBlocked(
            "closed episode events exceed its reconstruction cursor"
        )
    return [
        input_by_id[event_id]
        for event_id in sorted(
            input_by_id,
            key=lambda item: ordered_inputs[item],
        )
    ]


def _build_runner_ledger_reconstruction(
    *,
    portfolio_db: Path,
    event_inputs: Sequence[Mapping[str, Any]],
    episode: Mapping[str, Any],
    perspective: str,
    as_of: str,
    knowledge_cutoff: str,
    portfolio_source_sha256: str,
    sync_source_sha256: str,
    mapping_sha256: str,
    source_cutoff_id: str,
    sidecar_projection_sha256: str,
    knowledge_provenance: Mapping[str, Any],
) -> dict[str, Any]:
    reconstruction_as_of = _episode_reconstruction_as_of(
        episode,
        request_as_of=as_of,
    )
    reconstruction_event_inputs = (
        _event_inputs_with_episode_boundary_provenance(
            event_inputs,
            episode=episode,
        )
    )
    event_refs = [
        item
        for item in episode.get("event_refs", [])
        if isinstance(item, Mapping)
    ]
    if not event_refs:
        raise CanonicalGateBlocked(
            "selected episode has no event references for reconstruction"
        )
    pre_event_at = min(
        str(item.get("effective_at") or "") for item in event_refs
    )
    if not pre_event_at:
        raise CanonicalGateBlocked(
            "selected episode has no effective event boundary"
        )
    scope = (
        episode.get("scope")
        if isinstance(episode.get("scope"), Mapping)
        else {}
    )
    episode_event_ids = [
        str(item.get("event_id") or "") for item in event_refs
    ]
    if any(not item for item in episode_event_ids):
        raise CanonicalGateBlocked(
            "selected episode has an empty event identity"
        )
    cash_evidence = load_cash_baseline_proof(
        portfolio_db,
        account_id=str(scope.get("account_id") or ""),
        as_of=reconstruction_as_of,
        knowledge_cutoff_at=knowledge_cutoff,
        pre_event_at=pre_event_at,
    )
    cash_evidence_content_id = str(cash_evidence.get("content_id") or "")
    baseline_proof = cash_evidence.get("baseline_proof")
    if (
        not cash_evidence_content_id.startswith("sha256:")
        or not isinstance(baseline_proof, Mapping)
    ):
        raise CanonicalGateBlocked(
            "cash baseline adapter returned an unbound proof"
        )
    source_binding = {
        "portfolio_source_sha256": portfolio_source_sha256,
        "sync_source_sha256": sync_source_sha256,
        "mapping_sha256": mapping_sha256,
        "source_cutoff_id": source_cutoff_id,
        "sidecar_projection_sha256": sidecar_projection_sha256,
        "knowledge_provenance_content_id": (
            str(knowledge_provenance.get("content_id") or "")
        ),
        "cash_baseline_proof_content_id": cash_evidence_content_id,
    }
    reconstruction = build_ledger_snapshot_reconstruction(
        reconstruction_event_inputs,
        episode=episode,
        perspective=perspective,
        as_of=reconstruction_as_of,
        knowledge_cutoff=knowledge_cutoff,
        source_binding=source_binding,
        baseline_proof=baseline_proof,
    )
    validation = validate_ledger_snapshot_reconstruction(reconstruction)
    if _is_blocked(validation):
        raise CanonicalGateBlocked(
            "ledger snapshot reconstruction validation blocked: "
            + ",".join(_finding_codes(validation))
        )
    replay = replay_validate_ledger_snapshot_reconstruction(
        reconstruction,
        event_inputs=reconstruction_event_inputs,
        episode=episode,
        baseline_proof=baseline_proof,
    )
    if _is_blocked(replay) or not _source_verification_ready(replay):
        raise CanonicalGateBlocked(
            "ledger snapshot reconstruction source replay failed"
        )
    supplemental = build_ledger_snapshot_supplemental_source(
        reconstruction
    )
    projection = _ledger_reconstruction_receipt_projection(
        reconstruction,
        episode=episode,
        supplemental_source=supplemental,
        request_as_of=as_of,
    )
    return {
        "artifact": reconstruction,
        "validation": validation,
        "replay": replay,
        "cash_evidence": cash_evidence,
        "supplemental_source": supplemental,
        "receipt_projection": projection,
    }


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
        checkpoint_market_resolver: (
            Callable[..., Mapping[str, Any]] | None
        ) = None,
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
        self.checkpoint_market_resolver = checkpoint_market_resolver
        if not _inside(self.review_db, self.repo_root):
            raise ReviewRunnerError(
                "review sidecar must remain inside the selected checkout"
            )
        if self.review_db == self.portfolio_db:
            raise ReviewRunnerError(
                "portfolio source and review sidecar must be different files"
            )

    def _checkpoint_market_inputs(
        self,
        *,
        episode: Mapping[str, Any],
        operation_review: Mapping[str, Any],
        knowledge_provenance: Mapping[str, Any],
        ledger_snapshot_reconstruction: Mapping[str, Any],
        perspective: str,
        as_of: str,
        knowledge_cutoff: str,
    ) -> dict[str, Any]:
        resolver = self.checkpoint_market_resolver
        if resolver is None:
            raise CanonicalGateBlocked(
                "CHECKPOINT_MARKET_PROJECTION_UNPROVEN"
            )
        resolved = resolver(
            portfolio_db=self.portfolio_db,
            review_db=self.review_db,
            episode=deepcopy(dict(episode)),
            operation_review=deepcopy(dict(operation_review)),
            knowledge_provenance=deepcopy(dict(knowledge_provenance)),
            ledger_snapshot_reconstruction=deepcopy(
                dict(ledger_snapshot_reconstruction)
            ),
            perspective=perspective,
            as_of=as_of,
            knowledge_cutoff=knowledge_cutoff,
        )
        if not isinstance(resolved, Mapping):
            raise CanonicalGateBlocked(
                "CHECKPOINT_MARKET_PROJECTION_UNPROVEN"
            )
        if set(resolved) - {
            "market_axis",
            "market_fallback",
            "market_gaps",
        }:
            raise CanonicalGateBlocked(
                "checkpoint market resolver returned unsupported fields"
            )
        market_axis = resolved.get("market_axis")
        market_fallback = resolved.get("market_fallback")
        market_gaps = resolved.get("market_gaps", [])
        if (
            not isinstance(market_axis, Mapping)
            or not isinstance(market_fallback, Mapping)
            or not isinstance(market_gaps, (list, tuple))
            or any(not isinstance(item, Mapping) for item in market_gaps)
        ):
            raise CanonicalGateBlocked(
                "CHECKPOINT_MARKET_PROJECTION_UNPROVEN"
            )
        return {
            "market_axis": deepcopy(dict(market_axis)),
            "market_fallback": deepcopy(dict(market_fallback)),
            "market_gaps": [
                deepcopy(dict(item)) for item in market_gaps
            ],
        }

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
        if (
            not isinstance(receipt.get("scope"), str)
            or receipt.get("scope") not in RUN_SCOPES
        ):
            findings.append("INVALID_SCOPE")
        if (
            not isinstance(receipt.get("mode"), str)
            or receipt.get("mode") not in {"dry_run", "apply"}
        ):
            findings.append("INVALID_MODE")
        if not isinstance(receipt.get("status"), str) or receipt.get(
            "status"
        ) not in {"ready", "partial", "blocked", "failed"}:
            findings.append("INVALID_STATUS")
        if not str(receipt.get("run_id") or "").startswith("reviewrun_"):
            findings.append("INVALID_RUN_ID")
        if not str(receipt.get("run_key") or "").startswith("review:"):
            findings.append("INVALID_RUN_KEY")
        try:
            expected_content_id = _receipt_content_id(receipt)
        except (TypeError, UnicodeError, ValueError):
            expected_content_id = None
            findings.append("NON_CANONICAL_RECEIPT_VALUE")
        if receipt.get("content_id") != expected_content_id:
            findings.append("RECEIPT_CONTENT_ID_MISMATCH")
        cutoffs = receipt.get("cutoffs")
        receipt_perspective: str | None = None
        if not isinstance(cutoffs, Mapping):
            findings.append("MALFORMED_CUTOFFS")
        elif "perspective" in cutoffs:
            if (
                not isinstance(cutoffs.get("perspective"), str)
                or cutoffs.get("perspective") not in RUN_PERSPECTIVES
            ):
                findings.append("INVALID_PERSPECTIVE")
            else:
                receipt_perspective = str(cutoffs["perspective"])
        stages = receipt.get("stages", [])
        if not isinstance(stages, list):
            findings.append("MALFORMED_STAGES")
            stages = []
        stage_names = [
            str(stage.get("name") or "")
            for stage in stages
            if isinstance(stage, Mapping)
        ]
        completed_status = (
            isinstance(receipt.get("status"), str)
            and receipt.get("status") in {"ready", "partial"}
        )
        if completed_status and tuple(
            stage_names
        ) != COMPLETED_STAGE_NAMES:
            findings.append("INCOMPLETE_STAGE_SET")
        completed_v3_receipt = (
            receipt_perspective is not None
            and completed_status
            and tuple(stage_names) == COMPLETED_STAGE_NAMES
        )
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
        v3_knowledge_signal = (
            isinstance(cutoffs, Mapping)
            and "knowledge_provenance_content_id" in cutoffs
        )
        for stage in stages:
            details = (
                stage.get("details")
                if isinstance(stage, Mapping)
                and isinstance(stage.get("details"), Mapping)
                else {}
            )
            if (
                "knowledge_provenance_content_id" in details
                or "knowledge_provenance_source_replay" in details
                or (
                    stage.get("name") == "source_replay"
                    and any(
                        isinstance(item, Mapping)
                        and "knowledge_provenance" in item
                        for item in (
                            details.get("episodes", [])
                            if isinstance(details.get("episodes", []), list)
                            else []
                        )
                    )
                )
            ):
                v3_knowledge_signal = True
        if isinstance(episodes, list) and any(
            isinstance(item, Mapping)
            and (
                "perspective" in item
                or "knowledge_provenance_content_id" in item
            )
            for item in episodes
        ):
            v3_knowledge_signal = True
        if (
            isinstance(cutoffs, Mapping)
            and "perspective" not in cutoffs
            and v3_knowledge_signal
        ):
            findings.append("MISSING_PERSPECTIVE")
        for stage in stages:
            if not isinstance(stage, Mapping):
                findings.append("MALFORMED_STAGE")
                continue
            if not isinstance(stage.get("status"), str) or stage.get(
                "status"
            ) not in {"ready", "partial", "blocked", "failed"}:
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
        if completed_v3_receipt:
            stage_index = {
                str(stage.get("name") or ""): stage
                for stage in stages
                if isinstance(stage, Mapping)
            }
            sync_stage = stage_index.get("sync")
            episode_stage = stage_index.get("episode")
            replay_stage = stage_index.get("source_replay")
            sync_details = (
                sync_stage.get("details")
                if isinstance(sync_stage, Mapping)
                and isinstance(sync_stage.get("details"), Mapping)
                else None
            )
            episode_details = (
                episode_stage.get("details")
                if isinstance(episode_stage, Mapping)
                and isinstance(episode_stage.get("details"), Mapping)
                else None
            )
            replay_stage_details = (
                replay_stage.get("details")
                if isinstance(replay_stage, Mapping)
                and isinstance(replay_stage.get("details"), Mapping)
                else None
            )
            knowledge_content_id = (
                cutoffs.get("knowledge_provenance_content_id")
                if isinstance(cutoffs, Mapping)
                else None
            )
            if (
                not isinstance(knowledge_content_id, str)
                or not knowledge_content_id.startswith("sha256:")
                or len(knowledge_content_id) != 71
            ):
                findings.append("INVALID_KNOWLEDGE_PROVENANCE_CONTENT_ID")
            if (
                episode_details is None
                or episode_details.get("perspective")
                != receipt_perspective
                or episode_details.get("knowledge_provenance_content_id")
                != knowledge_content_id
            ):
                findings.append("EPISODE_STAGE_PERSPECTIVE_BINDING_MISMATCH")
            for episode in episodes if isinstance(episodes, list) else []:
                if (
                    not isinstance(episode, Mapping)
                    or episode.get("perspective") != receipt_perspective
                    or episode.get("knowledge_provenance_content_id")
                    != knowledge_content_id
                ):
                    findings.append("EPISODE_PERSPECTIVE_BINDING_MISMATCH")
            replay_items = (
                replay_stage_details.get("episodes")
                if isinstance(replay_stage_details, Mapping)
                else None
            )
            if not isinstance(replay_items, list):
                findings.append("MALFORMED_KNOWLEDGE_SOURCE_REPLAY")
                replay_items = []
            for replay_item in replay_items:
                knowledge_replay = (
                    replay_item.get("knowledge_provenance")
                    if isinstance(replay_item, Mapping)
                    else None
                )
                if (
                    not isinstance(knowledge_replay, Mapping)
                    or knowledge_replay.get("perspective")
                    != receipt_perspective
                    or knowledge_replay.get("content_id")
                    != knowledge_content_id
                    or knowledge_replay.get("source_verification")
                    != "verified"
                ):
                    findings.append(
                        "KNOWLEDGE_SOURCE_REPLAY_PERSPECTIVE_BINDING_MISMATCH"
                    )
            receipt_episode_ids = sorted(
                str(item.get("episode_id") or "")
                for item in episodes
                if isinstance(item, Mapping)
            )
            replay_episode_ids = sorted(
                str(item.get("episode_id") or "")
                for item in replay_items
                if isinstance(item, Mapping)
            )
            if replay_episode_ids != receipt_episode_ids:
                findings.append("KNOWLEDGE_SOURCE_REPLAY_MEMBERSHIP_MISMATCH")
            reconstruction_version = (
                cutoffs.get(
                    "ledger_snapshot_reconstruction_schema_version"
                )
                if isinstance(cutoffs, Mapping)
                else None
            )
            reconstruction_signal = (
                reconstruction_version is not None
                or any(
                    isinstance(item, Mapping)
                    and "ledger_snapshot_reconstruction" in item
                    for item in episodes
                )
                or any(
                    isinstance(item, Mapping)
                    and "ledger_snapshot_reconstruction" in item
                    for item in replay_items
                )
            )
            if reconstruction_signal:
                if (
                    not isinstance(cutoffs, Mapping)
                    or cutoffs.get("reviewability_schema_version") != 1
                    or reconstruction_version
                    != LEDGER_SNAPSHOT_RECONSTRUCTION_SCHEMA_VERSION
                ):
                    findings.append(
                        "INVALID_LEDGER_RECONSTRUCTION_VERSION_BINDING"
                    )
                snapshot_stage = stage_index.get("snapshot")
                snapshot_details = (
                    snapshot_stage.get("details")
                    if isinstance(snapshot_stage, Mapping)
                    and isinstance(snapshot_stage.get("details"), Mapping)
                    else {}
                )
                episode_projection_by_id: dict[str, Mapping[str, Any]] = {}
                for episode_item in (
                    episodes if isinstance(episodes, list) else []
                ):
                    episode_item_id = (
                        str(episode_item.get("episode_id") or "")
                        if isinstance(episode_item, Mapping)
                        else ""
                    )
                    projection = (
                        episode_item.get(
                            "ledger_snapshot_reconstruction"
                        )
                        if isinstance(episode_item, Mapping)
                        else None
                    )
                    if (
                        not episode_item_id
                        or not isinstance(projection, Mapping)
                        or set(projection)
                        != {
                            "schema_version",
                            "content_id",
                            "status",
                            "ending_quantity",
                            "as_of",
                        }
                        or projection.get("schema_version")
                        != LEDGER_SNAPSHOT_RECONSTRUCTION_SCHEMA_VERSION
                        or not str(
                            projection.get("content_id") or ""
                        ).startswith("sha256:")
                        or projection.get("status")
                        not in {
                            "available",
                            "partial",
                            "missing",
                            "blocked",
                        }
                        or not str(
                            projection.get("ending_quantity") or ""
                        )
                    ):
                        findings.append(
                            "MALFORMED_LEDGER_RECONSTRUCTION_PROJECTION"
                        )
                        continue
                    try:
                        projection_as_of_valid = (
                            _utc(
                                projection.get("as_of"),
                                field="projection.as_of",
                            )
                            <= _utc(
                                cutoffs.get("as_of"),
                                field="receipt.as_of",
                            )
                        )
                    except ReviewRunnerError:
                        projection_as_of_valid = False
                    if not projection_as_of_valid:
                        findings.append(
                            "MALFORMED_LEDGER_RECONSTRUCTION_PROJECTION"
                        )
                        continue
                    episode_projection_by_id[episode_item_id] = projection
                reconstruction_ids = sorted(
                    str(item.get("content_id") or "")
                    for item in episode_projection_by_id.values()
                )
                receipt_projection_manifest = (
                    _ledger_reconstruction_projection_manifest(
                        episode_projection_by_id
                    )
                )
                claimed_projection_sha256 = cutoffs.get(
                    "ledger_snapshot_reconstruction_projection_sha256"
                )
                if (
                    cutoffs.get(
                        "ledger_snapshot_projection_manifest_version"
                    )
                    != LEDGER_RECONSTRUCTION_PROJECTION_MANIFEST_VERSION
                    or claimed_projection_sha256
                    != str(
                        receipt_projection_manifest["content_id"]
                    ).removeprefix("sha256:")
                ):
                    findings.append(
                        "LEDGER_RECONSTRUCTION_PROJECTION_BINDING_MISMATCH"
                    )
                cash_proof_ids = snapshot_details.get(
                    "cash_baseline_proof_content_ids"
                )
                if (
                    snapshot_details.get(
                        "ledger_snapshot_reconstruction_count"
                    )
                    != len(receipt_episode_ids)
                    or snapshot_details.get(
                        "ledger_snapshot_reconstruction_content_ids"
                    )
                    != reconstruction_ids
                    or len(episode_projection_by_id)
                    != len(receipt_episode_ids)
                    or not isinstance(cash_proof_ids, list)
                    or cash_proof_ids != sorted(set(cash_proof_ids))
                    or len(cash_proof_ids) != len(receipt_episode_ids)
                    or any(
                        not str(item).startswith("sha256:")
                        for item in cash_proof_ids
                    )
                ):
                    findings.append(
                        "LEDGER_RECONSTRUCTION_MEMBERSHIP_MISMATCH"
                    )
                snapshot_artifacts = (
                    snapshot_stage.get("artifacts", [])
                    if isinstance(snapshot_stage, Mapping)
                    else []
                )
                descriptors_by_content_id = {
                    str(item.get("content_id") or ""): item
                    for item in snapshot_artifacts
                    if isinstance(item, Mapping) and item.get("content_id")
                }
                if not set(
                    [*reconstruction_ids, *(cash_proof_ids or [])]
                ).issubset(descriptors_by_content_id):
                    findings.append(
                        "LEDGER_RECONSTRUCTION_ARTIFACT_BINDING_MISMATCH"
                    )
                replay_by_id = {
                    str(item.get("episode_id") or ""): item
                    for item in replay_items
                    if isinstance(item, Mapping)
                    and item.get("episode_id")
                }
                for episode_item_id, projection in (
                    episode_projection_by_id.items()
                ):
                    replay_projection = (
                        replay_by_id.get(episode_item_id, {}).get(
                            "ledger_snapshot_reconstruction"
                        )
                        if isinstance(
                            replay_by_id.get(episode_item_id), Mapping
                        )
                        else None
                    )
                    if (
                        not isinstance(replay_projection, Mapping)
                        or replay_projection.get("validation_status")
                        != "accepted"
                        or replay_projection.get("source_verification")
                        != "verified"
                        or {
                            key: replay_projection.get(key)
                            for key in (
                                "schema_version",
                                "content_id",
                                "status",
                                "ending_quantity",
                                "as_of",
                            )
                        }
                        != dict(projection)
                    ):
                        findings.append(
                            "LEDGER_RECONSTRUCTION_SOURCE_REPLAY_MISMATCH"
                        )
                    if receipt.get("mode") == "apply":
                        descriptor = descriptors_by_content_id.get(
                            str(projection.get("content_id") or "")
                        )
                        artifact_path = (
                            Path(str(descriptor.get("path") or ""))
                            if isinstance(descriptor, Mapping)
                            else None
                        )
                        if (
                            artifact_path is None
                            or not artifact_path.is_file()
                        ):
                            findings.append(
                                "LEDGER_RECONSTRUCTION_ARTIFACT_MISSING"
                            )
                            continue
                        try:
                            reconstructed_artifact = load_json_object(
                                artifact_path
                            )
                            reconstruction_validation = (
                                validate_ledger_snapshot_reconstruction(
                                    reconstructed_artifact
                                )
                            )
                        except Exception:
                            findings.append(
                                "LEDGER_RECONSTRUCTION_ARTIFACT_INVALID"
                            )
                            continue
                        artifact_source_binding = (
                            reconstructed_artifact.get(
                                "source_binding", {}
                            ).get("proof")
                            if isinstance(
                                reconstructed_artifact.get(
                                    "source_binding"
                                ),
                                Mapping,
                            )
                            else {}
                        )
                        receipt_source_proof = (
                            source_proof
                            if isinstance(source_proof, Mapping)
                            else {}
                        )
                        try:
                            reconstruction_cutoffs_match = (
                                _utc(
                                    reconstructed_artifact.get("as_of"),
                                    field="reconstruction.as_of",
                                )
                                == _utc(
                                    projection.get("as_of"),
                                    field="projection.as_of",
                                )
                                and _utc(
                                    reconstructed_artifact.get("as_of"),
                                    field="reconstruction.as_of",
                                )
                                <= _utc(
                                    cutoffs.get("as_of"),
                                    field="receipt.as_of",
                                )
                                and _utc(
                                    reconstructed_artifact.get(
                                        "knowledge_cutoff"
                                    ),
                                    field=(
                                        "reconstruction.knowledge_cutoff"
                                    ),
                                )
                                == _utc(
                                    cutoffs.get("knowledge_cutoff"),
                                    field="receipt.knowledge_cutoff",
                                )
                            )
                        except ReviewRunnerError:
                            reconstruction_cutoffs_match = False
                        try:
                            artifact_projection = (
                                _ledger_reconstruction_artifact_projection(
                                    reconstructed_artifact,
                                    supplemental_source=(
                                        build_ledger_snapshot_supplemental_source(
                                            reconstructed_artifact
                                        )
                                    ),
                                )
                            )
                        except Exception:
                            artifact_projection = None
                        if (
                            _is_blocked(reconstruction_validation)
                            or reconstructed_artifact.get("content_id")
                            != projection.get("content_id")
                            or reconstructed_artifact.get("episode_id")
                            != episode_item_id
                            or reconstructed_artifact.get("perspective")
                            != receipt_perspective
                            or not reconstruction_cutoffs_match
                            or artifact_source_binding.get(
                                "portfolio_source_sha256"
                            )
                            != receipt_source_proof.get("sha256_before")
                            or artifact_source_binding.get(
                                "sync_source_sha256"
                            )
                            != sync_details.get("source_sha256")
                            or artifact_source_binding.get(
                                "mapping_sha256"
                            )
                            != sync_details.get("mapping_sha256")
                            or artifact_source_binding.get(
                                "source_cutoff_id"
                            )
                            != cutoffs.get("source_cutoff_id")
                            or artifact_source_binding.get(
                                "sidecar_projection_sha256"
                            )
                            != cutoffs.get("sidecar_projection_sha256")
                            or artifact_source_binding.get(
                                "knowledge_provenance_content_id"
                            )
                            != knowledge_content_id
                            or artifact_projection != dict(projection)
                        ):
                            findings.append(
                                "LEDGER_RECONSTRUCTION_ARTIFACT_INVALID"
                            )
                if receipt.get("mode") == "apply":
                    for cash_content_id in cash_proof_ids or []:
                        cash_descriptor = descriptors_by_content_id.get(
                            str(cash_content_id)
                        )
                        cash_path = (
                            Path(str(cash_descriptor.get("path") or ""))
                            if isinstance(cash_descriptor, Mapping)
                            else None
                        )
                        if cash_path is None or not cash_path.is_file():
                            findings.append(
                                "CASH_BASELINE_PROOF_ARTIFACT_INVALID"
                            )
                            continue
                        try:
                            cash_artifact = load_json_object(cash_path)
                            cash_material = deepcopy(cash_artifact)
                            supplied_cash_content_id = cash_material.pop(
                                "content_id", None
                            )
                            expected_cash_content_id = (
                                "sha256:"
                                + sha256_text(
                                    canonical_json(cash_material)
                                )
                            )
                        except Exception:
                            findings.append(
                                "CASH_BASELINE_PROOF_ARTIFACT_INVALID"
                            )
                            continue
                        cash_source_binding = (
                            cash_artifact.get("source_binding")
                            if isinstance(
                                cash_artifact.get("source_binding"),
                                Mapping,
                            )
                            else {}
                        )
                        receipt_source_proof = (
                            source_proof
                            if isinstance(source_proof, Mapping)
                            else {}
                        )
                        if (
                            cash_artifact.get("schema_version")
                            != "investment_review.cash_baseline_proof.v1"
                            or supplied_cash_content_id
                            != cash_content_id
                            or supplied_cash_content_id
                            != expected_cash_content_id
                            or cash_source_binding.get(
                                "source_sha256_before"
                            )
                            != receipt_source_proof.get("sha256_before")
                            or cash_source_binding.get(
                                "source_sha256_after"
                            )
                            != receipt_source_proof.get("sha256_after")
                            or cash_source_binding.get("sqlite_mode")
                            != "ro"
                            or cash_source_binding.get("query_only") is not True
                        ):
                            findings.append(
                                "CASH_BASELINE_PROOF_ARTIFACT_INVALID"
                            )
            checkpoint_version = (
                cutoffs.get("operation_checkpoint_schema_version")
                if isinstance(cutoffs, Mapping)
                else None
            )
            checkpoint_signal = (
                checkpoint_version is not None
                or any(
                    isinstance(item, Mapping)
                    and "review_checkpoint" in item
                    for item in episodes
                )
                or any(
                    isinstance(item, Mapping)
                    and "review_checkpoint" in item
                    for item in replay_items
                )
            )
            if checkpoint_signal:
                if (
                    not isinstance(cutoffs, Mapping)
                    or checkpoint_version
                    != OPERATION_CHECKPOINT_SCHEMA_VERSION
                    or cutoffs.get("review_checkpoint_method_version")
                    != REVIEW_CHECKPOINT_METHOD_VERSION
                    or cutoffs.get(
                        "review_checkpoint_projection_manifest_version"
                    )
                    != REVIEW_CHECKPOINT_PROJECTION_MANIFEST_VERSION
                ):
                    findings.append(
                        "INVALID_REVIEW_CHECKPOINT_VERSION_BINDING"
                    )
                expected_projection_fields = {
                    "schema_version",
                    "checkpoint_id",
                    "checkpoint_key",
                    "content_id",
                    "position_case_id",
                    "review_kind",
                    "checkpoint_type",
                    "perspective",
                    "as_of",
                    "knowledge_cutoff",
                    "review_readiness",
                    "decision_context_status",
                    "snapshot_cash_valuation_status",
                    "market_status",
                    "episode_lifecycle",
                    "outcome_maturity",
                    "lifecycle_notices",
                }
                checkpoint_projection_by_id: dict[
                    str, Mapping[str, Any]
                ] = {}
                for episode_item in (
                    episodes if isinstance(episodes, list) else []
                ):
                    episode_item_id = (
                        str(episode_item.get("episode_id") or "")
                        if isinstance(episode_item, Mapping)
                        else ""
                    )
                    projection = (
                        episode_item.get("review_checkpoint")
                        if isinstance(episode_item, Mapping)
                        else None
                    )
                    if projection is None:
                        continue
                    if (
                        not episode_item_id
                        or not isinstance(projection, Mapping)
                        or set(projection) != expected_projection_fields
                        or projection.get("schema_version")
                        != OPERATION_CHECKPOINT_SCHEMA_VERSION
                        or not str(
                            projection.get("checkpoint_id") or ""
                        ).startswith("review_checkpoint_")
                        or not str(
                            projection.get("checkpoint_key") or ""
                        ).startswith("review_checkpoint_key_")
                        or not str(
                            projection.get("content_id") or ""
                        ).startswith("sha256:")
                        or projection.get("perspective")
                        != receipt_perspective
                        or projection.get("as_of")
                        != cutoffs.get("as_of")
                        or projection.get("knowledge_cutoff")
                        != cutoffs.get("knowledge_cutoff")
                        or projection.get("review_kind")
                        != "active_checkpoint"
                        or projection.get("checkpoint_type")
                        != "active_checkpoint"
                        or projection.get("episode_lifecycle") != "open"
                        or projection.get("outcome_maturity") != "interim"
                        or projection.get("lifecycle_notices")
                        != ["OPEN_EPISODE_OUTCOME_NOT_FINAL"]
                    ):
                        findings.append(
                            "MALFORMED_REVIEW_CHECKPOINT_PROJECTION"
                        )
                        continue
                    checkpoint_projection_by_id[
                        episode_item_id
                    ] = projection
                receipt_checkpoint_manifest = (
                    _review_checkpoint_projection_manifest(
                        checkpoint_projection_by_id
                    )
                )
                if (
                    cutoffs.get(
                        "review_checkpoint_projection_sha256"
                    )
                    != str(
                        receipt_checkpoint_manifest["content_id"]
                    ).removeprefix("sha256:")
                ):
                    findings.append(
                        "REVIEW_CHECKPOINT_PROJECTION_BINDING_MISMATCH"
                    )
                checkpoint_ids = sorted(
                    str(item.get("content_id") or "")
                    for item in checkpoint_projection_by_id.values()
                )
                checkpoint_stage_artifacts = (
                    episode_stage.get("artifacts", [])
                    if isinstance(episode_stage, Mapping)
                    else []
                )
                checkpoint_descriptors = {
                    str(item.get("content_id") or ""): item
                    for item in checkpoint_stage_artifacts
                    if isinstance(item, Mapping)
                    and item.get("content_id")
                }
                if (
                    episode_details is None
                    or episode_details.get(
                        "operation_checkpoint_schema_version"
                    )
                    != OPERATION_CHECKPOINT_SCHEMA_VERSION
                    or episode_details.get(
                        "review_checkpoint_method_version"
                    )
                    != REVIEW_CHECKPOINT_METHOD_VERSION
                    or episode_details.get("review_checkpoint_count")
                    != len(checkpoint_projection_by_id)
                    or episode_details.get(
                        "review_checkpoint_content_ids"
                    )
                    != checkpoint_ids
                    or not set(checkpoint_ids).issubset(
                        checkpoint_descriptors
                    )
                ):
                    findings.append(
                        "REVIEW_CHECKPOINT_MEMBERSHIP_MISMATCH"
                    )
                replay_by_id = {
                    str(item.get("episode_id") or ""): item
                    for item in replay_items
                    if isinstance(item, Mapping)
                    and item.get("episode_id")
                }
                for episode_item_id, projection in (
                    checkpoint_projection_by_id.items()
                ):
                    replay_projection = (
                        replay_by_id.get(episode_item_id, {}).get(
                            "review_checkpoint"
                        )
                        if isinstance(
                            replay_by_id.get(episode_item_id), Mapping
                        )
                        else None
                    )
                    if (
                        not isinstance(replay_projection, Mapping)
                        or replay_projection.get("validation_status")
                        != "accepted"
                        or replay_projection.get("source_verification")
                        != "verified"
                        or {
                            key: replay_projection.get(key)
                            for key in expected_projection_fields
                        }
                        != dict(projection)
                    ):
                        findings.append(
                            "REVIEW_CHECKPOINT_SOURCE_REPLAY_MISMATCH"
                        )
                    if receipt.get("mode") != "apply":
                        continue
                    descriptor = checkpoint_descriptors.get(
                        str(projection.get("content_id") or "")
                    )
                    artifact_path = (
                        Path(str(descriptor.get("path") or ""))
                        if isinstance(descriptor, Mapping)
                        else None
                    )
                    try:
                        checkpoint_artifact = (
                            load_json_object(artifact_path)
                            if artifact_path is not None
                            and artifact_path.is_file()
                            else None
                        )
                        checkpoint_validation = (
                            validate_review_checkpoint(
                                checkpoint_artifact
                            )
                        )
                        stored_checkpoint = ReviewStore(
                            self.review_db
                        ).get_operation_checkpoint(
                            str(projection.get("checkpoint_key") or "")
                        )
                    except Exception:
                        checkpoint_artifact = None
                        checkpoint_validation = {
                            "validation_status": "blocked"
                        }
                        stored_checkpoint = None
                    if (
                        checkpoint_validation.get(
                            "validation_status"
                        )
                        != "accepted"
                        or not isinstance(checkpoint_artifact, Mapping)
                        or checkpoint_artifact.get("episode_id")
                        != episode_item_id
                        or _review_checkpoint_receipt_projection(
                            checkpoint_artifact
                        )
                        != dict(projection)
                        or not isinstance(stored_checkpoint, Mapping)
                        or canonical_review_checkpoint_bytes(
                            stored_checkpoint
                        )
                        != canonical_review_checkpoint_bytes(
                            checkpoint_artifact
                        )
                    ):
                        findings.append(
                            "REVIEW_CHECKPOINT_ARTIFACT_INVALID"
                        )
            if sync_details is None or not isinstance(cutoffs, Mapping):
                findings.append("RUN_KEY_BINDING_INPUT_MISSING")
            else:
                selection_mapping = (
                    selection if isinstance(selection, Mapping) else {}
                )
                expected_key_material = {
                    "runner_version": RUNNER_VERSION,
                    "scope": receipt.get("scope"),
                    "perspective": receipt_perspective,
                    "source_cutoff_id": cutoffs.get("source_cutoff_id"),
                    "source_sha256": sync_details.get("source_sha256"),
                    "mapping_sha256": sync_details.get("mapping_sha256"),
                    "sidecar_projection_sha256": cutoffs.get(
                        "sidecar_projection_sha256"
                    ),
                    "knowledge_provenance_schema_version": (
                        KNOWLEDGE_PROVENANCE_SCHEMA_VERSION
                    ),
                    "knowledge_provenance_method_version": (
                        KNOWLEDGE_PROVENANCE_METHOD_VERSION
                    ),
                    "knowledge_provenance_content_id": knowledge_content_id,
                    "operation_review_schema_version": (
                        OPERATION_REVIEW_SCHEMA_VERSION
                    ),
                    "operation_review_method_version": (
                        OPERATION_REVIEW_METHOD_VERSION
                    ),
                    "artifact_namespace": str(
                        self.artifact_root.relative_to(self.repo_root)
                    ).replace("\\", "/"),
                    "as_of": cutoffs.get("as_of"),
                    "knowledge_cutoff": cutoffs.get("knowledge_cutoff"),
                    "episode_id": selection_mapping.get(
                        "requested_episode_id"
                    ),
                }
                receipt_reviewability_version = cutoffs.get(
                    "reviewability_schema_version"
                )
                receipt_reconstruction_version = cutoffs.get(
                    "ledger_snapshot_reconstruction_schema_version"
                )
                if (
                    receipt_reviewability_version is not None
                    or receipt_reconstruction_version is not None
                ):
                    if (
                        receipt_reviewability_version != 1
                        or receipt_reconstruction_version
                        != LEDGER_SNAPSHOT_RECONSTRUCTION_SCHEMA_VERSION
                    ):
                        findings.append(
                            "INVALID_LEDGER_RECONSTRUCTION_VERSION_BINDING"
                        )
                    expected_key_material.update(
                        {
                            "reviewability_schema_version": (
                                receipt_reviewability_version
                            ),
                            "ledger_snapshot_reconstruction_schema_version": (
                                receipt_reconstruction_version
                            ),
                            "ledger_snapshot_projection_manifest_version": (
                                cutoffs.get(
                                    "ledger_snapshot_projection_manifest_version"
                                )
                            ),
                            "ledger_snapshot_reconstruction_projection_sha256": (
                                cutoffs.get(
                                    "ledger_snapshot_reconstruction_projection_sha256"
                                )
                            ),
                        }
                    )
                receipt_checkpoint_version = cutoffs.get(
                    "operation_checkpoint_schema_version"
                )
                if (
                    receipt_checkpoint_version is not None
                    or cutoffs.get(
                        "review_checkpoint_method_version"
                    )
                    is not None
                    or cutoffs.get(
                        "review_checkpoint_projection_manifest_version"
                    )
                    is not None
                    or cutoffs.get(
                        "review_checkpoint_projection_sha256"
                    )
                    is not None
                ):
                    expected_key_material.update(
                        {
                            "operation_checkpoint_schema_version": (
                                receipt_checkpoint_version
                            ),
                            "review_checkpoint_method_version": (
                                cutoffs.get(
                                    "review_checkpoint_method_version"
                                )
                            ),
                            "review_checkpoint_projection_manifest_version": (
                                cutoffs.get(
                                    "review_checkpoint_projection_manifest_version"
                                )
                            ),
                            "review_checkpoint_projection_sha256": (
                                cutoffs.get(
                                    "review_checkpoint_projection_sha256"
                                )
                            ),
                        }
                    )
                expected_run_key = "review:" + sha256_text(
                    canonical_json(expected_key_material)
                )
                expected_run_id = (
                    "reviewrun_" + sha256_text(expected_run_key)[:32]
                )
                retry = receipt.get("retry")
                retry_run_key = (
                    retry.get("run_key")
                    if isinstance(retry, Mapping)
                    else None
                )
                if (
                    receipt.get("run_key") != expected_run_key
                    or receipt.get("run_id") != expected_run_id
                    or retry_run_key != expected_run_key
                ):
                    findings.append("RUN_KEY_PERSPECTIVE_BINDING_MISMATCH")
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
        perspective: str = "user",
        episode_id: str | None = None,
        dry_run: bool = False,
        trigger: str = "manual",
    ) -> dict[str, Any]:
        if scope not in RUN_SCOPES:
            raise ReviewRunnerError(f"unsupported review scope: {scope}")
        if perspective not in RUN_PERSPECTIVES:
            raise ReviewRunnerError(
                f"unsupported review perspective: {perspective}"
            )
        as_of_time = _utc(as_of, field="as_of")
        knowledge_time = _utc(
            knowledge_cutoff, field="knowledge_cutoff"
        )
        if as_of_time > knowledge_time:
            raise ReviewRunnerError(
                "as_of must not be later than knowledge_cutoff"
            )
        episode_cutoff = as_of_time
        review_cutoff = knowledge_time
        mode = "dry_run" if dry_run else "apply"
        stages: list[dict[str, Any]] = []
        source_hash_before = _sha256_file(self.portfolio_db)
        current_stage = "sync"
        provenance_request_content_id = (
            "sha256:"
            + _sha256_bytes(
                canonical_json_bytes(
                    {
                        "schema_version": (
                            KNOWLEDGE_PROVENANCE_SCHEMA_VERSION
                        ),
                        "method_version": (
                            KNOWLEDGE_PROVENANCE_METHOD_VERSION
                        ),
                        "perspective": perspective,
                        "as_of": _utc_text(as_of_time),
                        "knowledge_cutoff": _utc_text(knowledge_time),
                        "source_sha256": source_hash_before,
                        "mapping_path": str(self.mapping_path),
                    }
                )
            )
        )
        preflight_material = {
            "runner_version": RUNNER_VERSION,
            "phase": "preflight",
            "scope": scope,
            "perspective": perspective,
            "knowledge_provenance_schema_version": (
                KNOWLEDGE_PROVENANCE_SCHEMA_VERSION
            ),
            "knowledge_provenance_method_version": (
                KNOWLEDGE_PROVENANCE_METHOD_VERSION
            ),
            "knowledge_provenance_request_content_id": (
                provenance_request_content_id
            ),
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
                    perspective=perspective,
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
            store_status = store.status()
            reviewability_schema_version = store_status.get(
                "reviewability_schema_version"
            )
            reviewability_enabled = reviewability_schema_version == 1
            checkpointing_enabled = (
                reviewability_enabled
                and self.checkpoint_market_resolver is not None
            )
            (
                event_inputs,
                event_observation_rows,
                sidecar_projection_sha256,
            ) = (
                _sidecar_projection_state(store)
            )
            knowledge_provenance = build_knowledge_provenance(
                event_inputs,
                observation_evidence=event_observation_rows,
                perspective=perspective,
                as_of=_utc_text(as_of_time),
                knowledge_cutoff=_utc_text(knowledge_time),
            )
            knowledge_validation = validate_knowledge_provenance(
                knowledge_provenance
            )
            if _is_blocked(knowledge_validation):
                raise CanonicalGateBlocked(
                    "knowledge provenance validation blocked: "
                    + ",".join(_finding_codes(knowledge_validation))
                )
            knowledge_replay = replay_validate_knowledge_provenance(
                knowledge_provenance,
                event_inputs=event_inputs,
                observation_evidence=event_observation_rows,
            )
            if (
                _is_blocked(knowledge_replay)
                or not _source_verification_ready(knowledge_replay)
            ):
                raise CanonicalGateBlocked(
                    "knowledge provenance source replay failed"
                )
            perspective_event_inputs = project_perspective_event_inputs(
                knowledge_provenance,
                event_inputs,
            )
            snapshot_inventory: dict[str, Any] | None = None
            if checkpointing_enabled:
                snapshot_inventory = inspect_portfolio_snapshots(
                    self.portfolio_db,
                    as_of=as_of_time.astimezone(
                        ZoneInfo("Asia/Shanghai")
                    ).date().isoformat(),
                    knowledge_cutoff=_utc_text(knowledge_time),
                )
            ledger_reconstructions: dict[str, dict[str, Any]] = {}
            ledger_projection_manifest = (
                _ledger_reconstruction_projection_manifest({})
            )
            review_checkpoints: dict[str, dict[str, Any]] = {}
            checkpoint_projection_manifest = (
                _review_checkpoint_projection_manifest({})
            )
            preview_selected: list[dict[str, Any]] = []
            if reviewability_enabled:
                preview_collection = build_episode_collection(
                    perspective_event_inputs,
                    cutoff_at=_utc_text(episode_cutoff),
                    snapshot_references=(
                        snapshot_inventory.get(
                            "snapshot_references", []
                        )
                        if snapshot_inventory is not None
                        else []
                    ),
                )
                preview_validation = validate_episode_collection(
                    preview_collection
                )
                if _is_blocked(preview_validation):
                    raise CanonicalGateBlocked(
                        "P2C reconstruction preview validation blocked: "
                        + ",".join(_finding_codes(preview_validation))
                    )
                preview_selected, _ = _select_episodes(
                    preview_collection,
                    scope=scope,
                    cutoff=episode_cutoff,
                    episode_id=episode_id,
                )
                current_stage = "snapshot"
                for selected_episode in preview_selected:
                    selected_episode_id = str(
                        selected_episode.get("episode_id") or ""
                    )
                    ledger_reconstructions[selected_episode_id] = (
                        _build_runner_ledger_reconstruction(
                            portfolio_db=self.portfolio_db,
                            event_inputs=perspective_event_inputs,
                            episode=selected_episode,
                            perspective=perspective,
                            as_of=_utc_text(as_of_time),
                            knowledge_cutoff=_utc_text(knowledge_time),
                            portfolio_source_sha256=source_hash_before,
                            sync_source_sha256=str(
                                sync_details.get("source_sha256") or ""
                            ),
                            mapping_sha256=str(
                                sync_details.get("mapping_sha256") or ""
                            ),
                            source_cutoff_id=cutoff_id,
                            sidecar_projection_sha256=(
                                sidecar_projection_sha256
                            ),
                            knowledge_provenance=knowledge_provenance,
                        )
                    )
                ledger_projection_manifest = (
                    _ledger_reconstruction_projection_manifest(
                        {
                            selected_episode_id: state[
                                "receipt_projection"
                            ]
                            for selected_episode_id, state in (
                                ledger_reconstructions.items()
                            )
                        }
                    )
                )
                if checkpointing_enabled:
                    preview_operation_review = build_operation_review(
                        preview_collection,
                        event_inputs=perspective_event_inputs,
                    )
                    preview_operation_validation = (
                        validate_operation_review(
                            preview_operation_review
                        )
                    )
                    if _is_blocked(preview_operation_validation):
                        raise CanonicalGateBlocked(
                            "checkpoint operation-review preview blocked: "
                            + ",".join(
                                _finding_codes(
                                    preview_operation_validation
                                )
                            )
                        )
                    preview_operation_replay = (
                        replay_validate_operation_review(
                            preview_operation_review,
                            episode_collection=preview_collection,
                            event_inputs=perspective_event_inputs,
                        )
                    )
                    if (
                        _is_blocked(preview_operation_replay)
                        or not _source_verification_ready(
                            preview_operation_replay
                        )
                    ):
                        raise CanonicalGateBlocked(
                            "checkpoint operation-review preview replay failed"
                        )
                    for selected_episode in preview_selected:
                        if selected_episode.get("status") != "open":
                            continue
                        selected_episode_id = str(
                            selected_episode.get("episode_id") or ""
                        )
                        reconstruction = ledger_reconstructions[
                            selected_episode_id
                        ]["artifact"]
                        market_inputs = self._checkpoint_market_inputs(
                            episode=selected_episode,
                            operation_review=preview_operation_review,
                            knowledge_provenance=knowledge_provenance,
                            ledger_snapshot_reconstruction=reconstruction,
                            perspective=perspective,
                            as_of=_utc_text(as_of_time),
                            knowledge_cutoff=_utc_text(knowledge_time),
                        )
                        checkpoint = build_review_checkpoint(
                            episode=selected_episode,
                            operation_review=preview_operation_review,
                            knowledge_provenance=knowledge_provenance,
                            ledger_snapshot_reconstruction=reconstruction,
                            perspective=perspective,
                            checkpoint_as_of=_utc_text(as_of_time),
                            knowledge_cutoff=_utc_text(knowledge_time),
                            checkpoint_type="active_checkpoint",
                            market_axis=market_inputs["market_axis"],
                            market_fallback=market_inputs[
                                "market_fallback"
                            ],
                            market_gaps=market_inputs["market_gaps"],
                        )
                        checkpoint_replay = (
                            replay_validate_review_checkpoint(
                                checkpoint,
                                episode=selected_episode,
                                operation_review=preview_operation_review,
                                knowledge_provenance=knowledge_provenance,
                                ledger_snapshot_reconstruction=(
                                    reconstruction
                                ),
                                perspective=perspective,
                                checkpoint_as_of=_utc_text(as_of_time),
                                knowledge_cutoff=_utc_text(knowledge_time),
                                checkpoint_type="active_checkpoint",
                                market_axis=market_inputs["market_axis"],
                                market_fallback=market_inputs[
                                    "market_fallback"
                                ],
                                market_gaps=market_inputs["market_gaps"],
                            )
                        )
                        if (
                            _is_blocked(checkpoint_replay)
                            or not _source_verification_ready(
                                checkpoint_replay
                            )
                        ):
                            raise CanonicalGateBlocked(
                                "review checkpoint source replay failed: "
                                + selected_episode_id
                            )
                        review_checkpoints[selected_episode_id] = {
                            "artifact": checkpoint,
                            "market_inputs": market_inputs,
                            "replay": checkpoint_replay,
                            "receipt_projection": (
                                _review_checkpoint_receipt_projection(
                                    checkpoint
                                )
                            ),
                        }
                    checkpoint_projection_manifest = (
                        _review_checkpoint_projection_manifest(
                            {
                                selected_episode_id: state[
                                    "receipt_projection"
                                ]
                                for selected_episode_id, state in (
                                    review_checkpoints.items()
                                )
                            }
                        )
                    )
            key_material = {
                "runner_version": RUNNER_VERSION,
                "scope": scope,
                "perspective": perspective,
                "source_cutoff_id": cutoff_id,
                "source_sha256": sync_details["source_sha256"],
                "mapping_sha256": sync_details["mapping_sha256"],
                "sidecar_projection_sha256": sidecar_projection_sha256,
                "knowledge_provenance_schema_version": (
                    KNOWLEDGE_PROVENANCE_SCHEMA_VERSION
                ),
                "knowledge_provenance_method_version": (
                    KNOWLEDGE_PROVENANCE_METHOD_VERSION
                ),
                "knowledge_provenance_content_id": (
                    knowledge_provenance.get("content_id")
                ),
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
            if reviewability_enabled:
                key_material.update(
                    {
                        "reviewability_schema_version": 1,
                        "ledger_snapshot_reconstruction_schema_version": (
                            LEDGER_SNAPSHOT_RECONSTRUCTION_SCHEMA_VERSION
                        ),
                        "ledger_snapshot_projection_manifest_version": (
                            LEDGER_RECONSTRUCTION_PROJECTION_MANIFEST_VERSION
                        ),
                        "ledger_snapshot_reconstruction_projection_sha256": (
                            str(
                                ledger_projection_manifest["content_id"]
                            ).removeprefix("sha256:")
                        ),
                    }
                )
            if checkpointing_enabled:
                key_material.update(
                    {
                        "operation_checkpoint_schema_version": (
                            OPERATION_CHECKPOINT_SCHEMA_VERSION
                        ),
                        "review_checkpoint_method_version": (
                            REVIEW_CHECKPOINT_METHOD_VERSION
                        ),
                        "review_checkpoint_projection_manifest_version": (
                            REVIEW_CHECKPOINT_PROJECTION_MANIFEST_VERSION
                        ),
                        "review_checkpoint_projection_sha256": str(
                            checkpoint_projection_manifest["content_id"]
                        ).removeprefix("sha256:"),
                    }
                )
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
            if snapshot_inventory is None:
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
                perspective_event_inputs,
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
                event_inputs=perspective_event_inputs,
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
                event_inputs=perspective_event_inputs,
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
            if reviewability_enabled:
                actual_identities = [
                    _episode_reconstruction_identity(item)
                    for item in selected
                ]
                preview_identities = [
                    _episode_reconstruction_identity(item)
                    for item in preview_selected
                ]
                if (
                    actual_identities != preview_identities
                    or sorted(ledger_reconstructions)
                    != [
                        str(item.get("episode_id") or "")
                        for item in selected
                    ]
                ):
                    raise CanonicalGateBlocked(
                        "snapshot-linked P2C selection drifted from the "
                        "run-key reconstruction preview"
                    )
                current_stage = "snapshot"
            if checkpointing_enabled:
                selected_open_ids = sorted(
                    str(item.get("episode_id") or "")
                    for item in selected
                    if item.get("status") == "open"
                )
                if selected_open_ids != sorted(review_checkpoints):
                    raise CanonicalGateBlocked(
                        "open checkpoint membership drifted from the run key"
                    )
                for selected_episode in selected:
                    if selected_episode.get("status") != "open":
                        continue
                    selected_episode_id = str(
                        selected_episode.get("episode_id") or ""
                    )
                    checkpoint_state = review_checkpoints[
                        selected_episode_id
                    ]
                    market_inputs = checkpoint_state["market_inputs"]
                    rebuilt_checkpoint = build_review_checkpoint(
                        episode=selected_episode,
                        operation_review=operation_review,
                        knowledge_provenance=knowledge_provenance,
                        ledger_snapshot_reconstruction=(
                            ledger_reconstructions[
                                selected_episode_id
                            ]["artifact"]
                        ),
                        perspective=perspective,
                        checkpoint_as_of=_utc_text(as_of_time),
                        knowledge_cutoff=_utc_text(knowledge_time),
                        checkpoint_type="active_checkpoint",
                        market_axis=market_inputs["market_axis"],
                        market_fallback=market_inputs[
                            "market_fallback"
                        ],
                        market_gaps=market_inputs["market_gaps"],
                    )
                    if canonical_review_checkpoint_bytes(
                        rebuilt_checkpoint
                    ) != canonical_review_checkpoint_bytes(
                        checkpoint_state["artifact"]
                    ):
                        raise CanonicalGateBlocked(
                            "checkpoint content drifted from the run key: "
                            + selected_episode_id
                        )
                    rebuilt_replay = replay_validate_review_checkpoint(
                        rebuilt_checkpoint,
                        episode=selected_episode,
                        operation_review=operation_review,
                        knowledge_provenance=knowledge_provenance,
                        ledger_snapshot_reconstruction=(
                            ledger_reconstructions[
                                selected_episode_id
                            ]["artifact"]
                        ),
                        perspective=perspective,
                        checkpoint_as_of=_utc_text(as_of_time),
                        knowledge_cutoff=_utc_text(knowledge_time),
                        checkpoint_type="active_checkpoint",
                        market_axis=market_inputs["market_axis"],
                        market_fallback=market_inputs[
                            "market_fallback"
                        ],
                        market_gaps=market_inputs["market_gaps"],
                    )
                    if (
                        _is_blocked(rebuilt_replay)
                        or not _source_verification_ready(rebuilt_replay)
                    ):
                        raise CanonicalGateBlocked(
                            "checkpoint actual source replay failed: "
                            + selected_episode_id
                        )
                    checkpoint_state["artifact"] = rebuilt_checkpoint
                    checkpoint_state["replay"] = rebuilt_replay
            artifact_descriptors: list[dict[str, Any]] = []
            reconstruction_descriptors: dict[str, dict[str, Any]] = {}
            cash_evidence_descriptors: dict[str, dict[str, Any]] = {}
            checkpoint_descriptors: dict[str, dict[str, Any]] = {}
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
                knowledge_descriptor = _json_artifact(
                    run_dir / "knowledge_provenance.json",
                    knowledge_provenance,
                    content_id=str(
                        knowledge_provenance.get("content_id") or ""
                    ),
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
                        knowledge_descriptor,
                        operation_descriptor,
                    ]
                )
                for selected_episode_id in sorted(
                    ledger_reconstructions
                ):
                    reconstruction_state = ledger_reconstructions[
                        selected_episode_id
                    ]
                    reconstruction = reconstruction_state["artifact"]
                    cash_evidence = reconstruction_state["cash_evidence"]
                    episode_dir = (
                        run_dir / "e" / selected_episode_id
                    )
                    reconstruction_descriptors[selected_episode_id] = (
                        _json_artifact(
                            episode_dir / "snapshot.json",
                            reconstruction,
                            content_id=str(
                                reconstruction.get("content_id") or ""
                            ),
                        )
                    )
                    cash_evidence_descriptors[selected_episode_id] = (
                        _json_artifact(
                            episode_dir / "cash.json",
                            cash_evidence,
                            content_id=str(
                                cash_evidence.get("content_id") or ""
                            ),
                        )
                    )
                    artifact_descriptors.extend(
                        [
                            reconstruction_descriptors[
                                selected_episode_id
                            ],
                            cash_evidence_descriptors[
                                selected_episode_id
                            ],
                        ]
                    )
                for selected_episode_id in sorted(review_checkpoints):
                    checkpoint = review_checkpoints[
                        selected_episode_id
                    ]["artifact"]
                    checkpoint_descriptors[selected_episode_id] = (
                        _json_artifact(
                            run_dir
                            / "e"
                            / selected_episode_id
                            / "checkpoint.json",
                            checkpoint,
                            content_id=str(
                                checkpoint.get("content_id") or ""
                            ),
                        )
                    )
                    artifact_descriptors.append(
                        checkpoint_descriptors[selected_episode_id]
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
                knowledge_descriptor = {
                    "content_id": str(
                        knowledge_provenance.get("content_id") or ""
                    ),
                    "sha256": _sha256_bytes(
                        pretty_json_bytes(knowledge_provenance)
                    ),
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
                for selected_episode_id in sorted(
                    ledger_reconstructions
                ):
                    reconstruction_state = ledger_reconstructions[
                        selected_episode_id
                    ]
                    reconstruction = reconstruction_state["artifact"]
                    cash_evidence = reconstruction_state["cash_evidence"]
                    reconstruction_descriptors[selected_episode_id] = {
                        "content_id": str(
                            reconstruction.get("content_id") or ""
                        ),
                        "sha256": _sha256_bytes(
                            pretty_json_bytes(reconstruction)
                        ),
                        "write_status": "dry_run",
                    }
                    cash_evidence_descriptors[selected_episode_id] = {
                        "content_id": str(
                            cash_evidence.get("content_id") or ""
                        ),
                        "sha256": _sha256_bytes(
                            pretty_json_bytes(cash_evidence)
                        ),
                        "write_status": "dry_run",
                    }
                for selected_episode_id in sorted(review_checkpoints):
                    checkpoint = review_checkpoints[
                        selected_episode_id
                    ]["artifact"]
                    checkpoint_descriptors[selected_episode_id] = {
                        "content_id": str(
                            checkpoint.get("content_id") or ""
                        ),
                        "sha256": _sha256_bytes(
                            pretty_json_bytes(checkpoint)
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
            if reviewability_enabled:
                snapshot_gaps = sorted(
                    {
                        *snapshot_gaps,
                        *(
                            str(gap.get("code") or "")
                            for state in ledger_reconstructions.values()
                            for gap in state["artifact"].get("gaps", [])
                            if isinstance(gap, Mapping)
                            and str(gap.get("code") or "")
                        ),
                        *(
                            str(gap.get("code") or "")
                            for state in ledger_reconstructions.values()
                            for gap in state["cash_evidence"].get(
                                "gaps", []
                            )
                            if isinstance(gap, Mapping)
                            and str(gap.get("code") or "")
                        ),
                    }
                )
            snapshot_stage_status = (
                "ready" if snapshot_status == "complete" else "partial"
            )
            snapshot_stage_details: dict[str, Any] = {
                "quality_status": snapshot_status,
                "snapshot_count": len(
                    snapshot_inventory.get("snapshot_references", [])
                ),
                "content_id": snapshot_inventory.get("content_id"),
                "lineage": snapshot_inventory.get("lineage"),
            }
            snapshot_stage_artifacts = [snapshot_descriptor]
            if reviewability_enabled:
                reconstruction_projections = [
                    state["receipt_projection"]
                    for _, state in sorted(
                        ledger_reconstructions.items()
                    )
                ]
                if selected:
                    snapshot_stage_status = (
                        "ready"
                        if all(
                            item.get("status") == "available"
                            for item in reconstruction_projections
                        )
                        else "partial"
                    )
                snapshot_stage_details.update(
                    {
                        "ledger_snapshot_reconstruction_count": len(
                            reconstruction_projections
                        ),
                        "ledger_snapshot_reconstruction_content_ids": sorted(
                            str(item.get("content_id") or "")
                            for item in reconstruction_projections
                        ),
                        "cash_baseline_proof_content_ids": sorted(
                            str(
                                state["cash_evidence"].get(
                                    "content_id"
                                )
                                or ""
                            )
                            for state in ledger_reconstructions.values()
                        ),
                    }
                )
                for selected_episode_id in sorted(
                    ledger_reconstructions
                ):
                    snapshot_stage_artifacts.extend(
                        [
                            reconstruction_descriptors[
                                selected_episode_id
                            ],
                            cash_evidence_descriptors[
                                selected_episode_id
                            ],
                        ]
                    )
            stages.append(
                _stage(
                    "snapshot",
                    snapshot_stage_status,
                    details=snapshot_stage_details,
                    gaps=snapshot_gaps,
                    artifacts=snapshot_stage_artifacts,
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
                        "perspective": perspective,
                        "knowledge_provenance_content_id": (
                            knowledge_provenance.get("content_id")
                        ),
                        "knowledge_provenance_validation_status": (
                            _validation_status(knowledge_validation)
                        ),
                        "knowledge_provenance_source_replay": "verified",
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
                        **(
                            {
                                "operation_checkpoint_schema_version": (
                                    OPERATION_CHECKPOINT_SCHEMA_VERSION
                                ),
                                "review_checkpoint_method_version": (
                                    REVIEW_CHECKPOINT_METHOD_VERSION
                                ),
                                "review_checkpoint_count": len(
                                    review_checkpoints
                                ),
                                "review_checkpoint_content_ids": sorted(
                                    str(
                                        state["artifact"].get(
                                            "content_id"
                                        )
                                        or ""
                                    )
                                    for state in review_checkpoints.values()
                                ),
                            }
                            if checkpointing_enabled
                            else {}
                        ),
                    },
                    gaps=(
                        ["NO_EPISODE_IN_SCOPE"] if not selected else []
                    ),
                    artifacts=[
                        collection_descriptor,
                        knowledge_descriptor,
                        operation_descriptor,
                        *[
                            checkpoint_descriptors[
                                selected_episode_id
                            ]
                            for selected_episode_id in sorted(
                                checkpoint_descriptors
                            )
                        ],
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
                reconstruction_state = ledger_reconstructions.get(
                    selected_id
                )
                checkpoint_state = review_checkpoints.get(selected_id)
                supplemental_sources = (
                    [reconstruction_state["supplemental_source"]]
                    if reconstruction_state is not None
                    else []
                )
                input_bundle = build_review_input_bundle(
                    collection,
                    context,
                    portfolio_db=self.portfolio_db,
                    episode_id=selected_id,
                    review_cutoff=_utc_text(review_cutoff),
                    decision_sources=decisions,
                    supplemental_sources=supplemental_sources,
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
                    supplemental_sources=supplemental_sources,
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
                if checkpoint_state is not None:
                    review_gaps = [
                        code
                        for code in review_gaps
                        if code != "OPEN_EPISODE_OUTCOME_NOT_FINAL"
                    ]
                episode_result: dict[str, Any] = {
                        "episode_id": selected_id,
                        "perspective": perspective,
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
                        "knowledge_provenance_content_id": (
                            knowledge_provenance.get("content_id")
                        ),
                        "artifacts": {
                            "context": context_descriptor,
                            "input": input_descriptor,
                            "review": review_descriptor,
                            "markdown": markdown_descriptor,
                        },
                    }
                if reconstruction_state is not None:
                    episode_result[
                        "ledger_snapshot_reconstruction"
                    ] = deepcopy(
                        reconstruction_state["receipt_projection"]
                    )
                    episode_result["artifacts"].update(
                        {
                            "snapshot_reconstruction": (
                                reconstruction_descriptors[selected_id]
                            ),
                            "cash_baseline_proof": (
                                cash_evidence_descriptors[selected_id]
                            ),
                        }
                    )
                if checkpoint_state is not None:
                    episode_result["review_checkpoint"] = deepcopy(
                        checkpoint_state["receipt_projection"]
                    )
                    episode_result["artifacts"]["review_checkpoint"] = (
                        checkpoint_descriptors[selected_id]
                    )
                episode_results.append(episode_result)
                replay_detail: dict[str, Any] = {
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
                        "knowledge_provenance": {
                            "validation_status": _validation_status(
                                knowledge_replay
                            ),
                            "source_verification": "verified",
                            "content_id": knowledge_provenance.get(
                                "content_id"
                            ),
                            "perspective": perspective,
                        },
                    }
                if reconstruction_state is not None:
                    replay_detail[
                        "ledger_snapshot_reconstruction"
                    ] = {
                        **deepcopy(
                            reconstruction_state[
                                "receipt_projection"
                            ]
                        ),
                        "validation_status": _validation_status(
                            reconstruction_state["replay"]
                        ),
                        "source_verification": "verified",
                    }
                if checkpoint_state is not None:
                    replay_detail["review_checkpoint"] = {
                        **deepcopy(
                            checkpoint_state["receipt_projection"]
                        ),
                        "validation_status": _validation_status(
                            checkpoint_state["replay"]
                        ),
                        "source_verification": "verified",
                    }
                replay_details.append(replay_detail)

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
            (
                _,
                _,
                sidecar_projection_after,
            ) = _sidecar_projection_state(store)
            if sidecar_projection_after != sidecar_projection_sha256:
                raise CanonicalGateBlocked(
                    "review sidecar event/decision projection changed during "
                    "review run"
                )
            checkpoint_save_receipts: list[dict[str, Any]] = []
            if not dry_run:
                for selected_episode_id in sorted(review_checkpoints):
                    current_stage = (
                        f"review_checkpoint:{selected_episode_id}"
                    )
                    checkpoint = review_checkpoints[
                        selected_episode_id
                    ]["artifact"]
                    save_receipt = store.save_operation_checkpoint(
                        checkpoint
                    )
                    stored_checkpoint = store.get_operation_checkpoint(
                        str(checkpoint["checkpoint_key"])
                    )
                    if canonical_review_checkpoint_bytes(
                        stored_checkpoint
                    ) != canonical_review_checkpoint_bytes(checkpoint):
                        raise CanonicalGateBlocked(
                            "stored checkpoint failed immutable readback: "
                            + selected_episode_id
                        )
                    checkpoint_save_receipts.append(
                        dict(save_receipt)
                    )

            overall = (
                "partial"
                if any(stage["status"] == "partial" for stage in stages)
                else "ready"
            )
            receipt_cutoffs = {
                "perspective": perspective,
                "as_of": _utc_text(as_of_time),
                "knowledge_cutoff": _utc_text(knowledge_time),
                "episode_cutoff": _utc_text(episode_cutoff),
                "review_cutoff": _utc_text(review_cutoff),
                "source_cutoff_id": cutoff_id,
                "sidecar_projection_sha256": sidecar_projection_sha256,
                "knowledge_provenance_content_id": (
                    knowledge_provenance.get("content_id")
                ),
            }
            if reviewability_enabled:
                receipt_cutoffs.update(
                    {
                        "reviewability_schema_version": 1,
                        "ledger_snapshot_reconstruction_schema_version": (
                            LEDGER_SNAPSHOT_RECONSTRUCTION_SCHEMA_VERSION
                        ),
                        "ledger_snapshot_projection_manifest_version": (
                            LEDGER_RECONSTRUCTION_PROJECTION_MANIFEST_VERSION
                        ),
                        "ledger_snapshot_reconstruction_projection_sha256": (
                            str(
                                ledger_projection_manifest["content_id"]
                            ).removeprefix("sha256:")
                        ),
                    }
                )
            if checkpointing_enabled:
                receipt_cutoffs.update(
                    {
                        "operation_checkpoint_schema_version": (
                            OPERATION_CHECKPOINT_SCHEMA_VERSION
                        ),
                        "review_checkpoint_method_version": (
                            REVIEW_CHECKPOINT_METHOD_VERSION
                        ),
                        "review_checkpoint_projection_manifest_version": (
                            REVIEW_CHECKPOINT_PROJECTION_MANIFEST_VERSION
                        ),
                        "review_checkpoint_projection_sha256": str(
                            checkpoint_projection_manifest["content_id"]
                        ).removeprefix("sha256:"),
                    }
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
                "cutoffs": receipt_cutoffs,
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
                        "checkpoint_ids": sorted(
                            str(
                                state["artifact"].get(
                                    "checkpoint_id"
                                )
                                or ""
                            )
                            for state in review_checkpoints.values()
                        ),
                        "checkpoint_save_status_counts": {
                            status: sum(
                                1
                                for item in checkpoint_save_receipts
                                if item.get("status") == status
                            )
                            for status in ("INSERTED", "SKIPPED")
                        },
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
                perspective=perspective,
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
        perspective: str,
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
                "perspective": perspective,
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
        parameters = run["run"].get("parameters")
        recorded_perspective = (
            parameters.get("perspective")
            if isinstance(parameters, Mapping)
            else None
        )
        receipt_cutoffs = receipt.get("cutoffs")
        receipt_perspective = (
            receipt_cutoffs.get("perspective")
            if isinstance(receipt_cutoffs, Mapping)
            else None
        )
        if (
            recorded_perspective is not None
            or receipt_perspective is not None
        ) and recorded_perspective != receipt_perspective:
            raise ReviewRunnerError(
                "receipt perspective does not match the immutable run ledger"
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
                        "perspective": (
                            receipt.get("cutoffs", {}).get("perspective")
                            or "legacy"
                        ),
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
    "RUN_PERSPECTIVES",
    "RUN_SCOPES",
    "ReviewRunCatalog",
    "ReviewRunner",
    "ReviewRunnerError",
]
