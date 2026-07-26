"""Deterministic episode-scoped review checkpoints.

This module is deliberately artifact-only.  It does not open SQLite, read a
portfolio source, call a market provider, or mutate an existing checkpoint.
Callers must freeze and validate the source projections before passing them
here, then persist the returned ``OperationCheckpointRecord`` through the
create-only review store.
"""

from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence

from .artifact_io import canonical_json_bytes
from .episodes import validate_episode
from .knowledge_provenance import validate_knowledge_provenance
from .ledger_snapshot_reconstruction import (
    validate_ledger_snapshot_reconstruction,
)
from .models import (
    OPERATION_CHECKPOINT_SCHEMA_VERSION,
    OperationCheckpointRecord,
)
from .operation_review import validate_operation_review
from .time_utils import parse_datetime, utc_iso


METHOD_VERSION = "episode_scoped_append_only_checkpoint_v1"
VALIDATION_SCHEMA_VERSION = "investment_review.review_checkpoint.validation.v1"
REPLAY_SCHEMA_VERSION = "investment_review.review_checkpoint.replay.v1"
APPEND_PLAN_SCHEMA_VERSION = "investment_review.review_checkpoint.append_plan.v1"

CHECKPOINT_TYPES = frozenset(
    {"entry", "active_checkpoint", "adjustment", "exit", "postmortem"}
)
_AWARE_TIMESTAMP = re.compile(r"(?:Z|[+-]\d{2}:\d{2})$")
_ROOT_FIELDS = {
    "schema_version",
    "checkpoint_id",
    "checkpoint_key",
    "content_id",
    "episode_id",
    "position_case_id",
    "review_kind",
    "checkpoint_type",
    "perspective",
    "as_of",
    "knowledge_cutoff",
    "time_provenance",
    "status_axes",
    "market_fallback",
    "gaps",
    "source_refs",
    "governance",
}
_GAP_FIELDS = {
    "gap_id",
    "axis",
    "code",
    "severity",
    "blocks_axis",
    "owner",
    "next_step",
    "source_refs",
}
_GAP_INPUT_FIELDS = _GAP_FIELDS - {"gap_id"}
_AXES = {
    "operation",
    "decision",
    "snapshot_cash_valuation",
    "market",
    "lifecycle",
    "outcome",
}
_ADJUSTMENT_OPERATION_TYPES = {
    "position_increase",
    "position_reduce",
    "special_quantity_adjustment",
}
_BINDING_PREFIXES = (
    "operation_review:",
    "knowledge_provenance:",
    "ledger_snapshot_reconstruction:",
)
_GOVERNANCE = {
    "facts_only": True,
    "no_motive": True,
    "no_advice": True,
    "no_score": True,
    "no_diagnosis": True,
}


class ReviewCheckpointError(ValueError):
    """Raised when a checkpoint cannot be derived from proven source facts."""


class ReviewCheckpointConflictError(ReviewCheckpointError):
    """Raised when an immutable semantic checkpoint already has other content."""


def _mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReviewCheckpointError(f"{name} must be a mapping")
    return value


def _text(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewCheckpointError(f"{name} must be non-empty text")
    return value.strip()


def _timestamp(value: object, *, name: str) -> str:
    text = _text(value, name=name)
    if _AWARE_TIMESTAMP.search(text) is None:
        raise ReviewCheckpointError(f"{name} must include an explicit timezone")
    try:
        return utc_iso(text, "UTC")
    except Exception as exc:
        raise ReviewCheckpointError(f"{name} is not a valid timestamp") from exc


def _dt(value: str) -> datetime:
    return parse_datetime(value, "UTC")


def _content_id(value: object, *, name: str) -> str:
    text = _text(value, name=name)
    if re.fullmatch(r"sha256:[0-9a-f]{64}", text) is None:
        raise ReviewCheckpointError(f"{name} must be a canonical SHA-256 content ID")
    return text


def _validation_accepted(
    receipt: object,
    *,
    name: str,
) -> None:
    result = _mapping(receipt, name=f"{name} validation")
    if result.get("validation_status") != "accepted":
        codes = sorted(
            {
                str(item.get("code") or "")
                for item in result.get("findings", [])
                if isinstance(item, Mapping) and item.get("code")
            }
        )
        suffix = f": {','.join(codes)}" if codes else ""
        raise ReviewCheckpointError(f"{name} validation is blocked{suffix}")


def _episode_event_refs(episode: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = episode.get("event_refs")
    if not isinstance(raw, list) or not raw:
        raise ReviewCheckpointError("episode must contain material event_refs")
    refs: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        event_ref = _mapping(item, name="episode event_ref")
        event_id = _text(event_ref.get("event_id"), name="episode event_id")
        if event_id in seen:
            raise ReviewCheckpointError("episode event_refs contain duplicate IDs")
        seen.add(event_id)
        refs.append(event_ref)
    return refs


def _matched_episode_review(
    operation_review: Mapping[str, Any],
    *,
    episode_id: str,
) -> Mapping[str, Any]:
    reviews = operation_review.get("episode_reviews")
    if not isinstance(reviews, list):
        raise ReviewCheckpointError("operation_review episode_reviews must be an array")
    matches = [
        item
        for item in reviews
        if isinstance(item, Mapping) and item.get("episode_id") == episode_id
    ]
    if len(matches) != 1:
        raise ReviewCheckpointError(
            "operation_review must contain exactly one matching episode review"
        )
    return matches[0]


def _operations_by_event(
    episode_review: Mapping[str, Any],
    *,
    expected_event_ids: Sequence[str],
) -> dict[str, Mapping[str, Any]]:
    raw = episode_review.get("operations")
    if not isinstance(raw, list):
        raise ReviewCheckpointError("episode operation facts must be an array")
    result: dict[str, Mapping[str, Any]] = {}
    for item in raw:
        operation = _mapping(item, name="episode operation")
        event_id = _text(operation.get("event_id"), name="operation event_id")
        if event_id in result:
            raise ReviewCheckpointError(
                "episode operation facts contain duplicate event IDs"
            )
        result[event_id] = operation
    if set(result) != set(expected_event_ids):
        raise ReviewCheckpointError(
            "operation facts do not exactly cover the checkpoint episode events"
        )
    return result


def _knowledge_events(
    knowledge_provenance: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    raw = knowledge_provenance.get("events")
    if not isinstance(raw, list):
        raise ReviewCheckpointError("knowledge_provenance events must be an array")
    result: dict[str, Mapping[str, Any]] = {}
    for item in raw:
        event = _mapping(item, name="knowledge event")
        event_id = _text(event.get("event_id"), name="knowledge event_id")
        if event_id in result:
            raise ReviewCheckpointError(
                "knowledge_provenance contains duplicate event IDs"
            )
        result[event_id] = event
    return result


def _source_ref_strings(operation: Mapping[str, Any]) -> list[str]:
    refs = operation.get("source_refs")
    result = [_text(operation.get("event_id"), name="operation event_id")]
    if not isinstance(refs, Mapping):
        return result
    source_id = refs.get("source_id")
    if source_id:
        result.append(f"source:{source_id}")
    source_record_id = refs.get("source_record_id")
    if source_id and source_record_id:
        result.append(f"source_record:{source_id}:{source_record_id}")
    payload_sha256 = refs.get("payload_sha256")
    if payload_sha256:
        result.append(f"payload_sha256:{payload_sha256}")
    source_keys = refs.get("source_keys")
    if isinstance(source_keys, list):
        result.extend(str(item) for item in source_keys if str(item))
    return sorted(set(result))


def _normalize_gap(value: object) -> dict[str, Any]:
    item = _mapping(value, name="checkpoint gap")
    if set(item) != _GAP_INPUT_FIELDS and set(item) != _GAP_FIELDS:
        raise ReviewCheckpointError("checkpoint gap uses an unsupported field set")
    axis = _text(item.get("axis"), name="gap axis")
    if axis not in _AXES:
        raise ReviewCheckpointError(f"unsupported checkpoint gap axis: {axis}")
    code = _text(item.get("code"), name="gap code").upper()
    if code == "OPEN_EPISODE_OUTCOME_NOT_FINAL":
        raise ReviewCheckpointError(
            "open/interim maturity is informational and must not be stored as a gap"
        )
    severity = _text(item.get("severity"), name="gap severity").lower()
    if severity not in {"info", "warning", "blocker"}:
        raise ReviewCheckpointError("unsupported checkpoint gap severity")
    blocks_axis = item.get("blocks_axis")
    if not isinstance(blocks_axis, bool):
        raise ReviewCheckpointError("gap blocks_axis must be boolean")
    if (severity == "blocker") != blocks_axis:
        raise ReviewCheckpointError(
            "blocker severity and blocks_axis must agree"
        )
    source_refs = item.get("source_refs")
    if not isinstance(source_refs, (list, tuple)):
        raise ReviewCheckpointError("gap source_refs must be an array")
    refs = sorted({_text(ref, name="gap source_ref") for ref in source_refs})
    material = {
        "axis": axis,
        "code": code,
        "severity": severity,
        "blocks_axis": blocks_axis,
        "owner": _text(item.get("owner"), name="gap owner"),
        "next_step": _text(item.get("next_step"), name="gap next_step"),
        "source_refs": refs,
    }
    gap_id = "review_gap_" + hashlib.sha256(
        canonical_json_bytes(material)
    ).hexdigest()[:32]
    if item.get("gap_id") not in (None, gap_id):
        raise ReviewCheckpointError(
            "checkpoint gap_id does not match canonical gap content"
        )
    return {"gap_id": gap_id, **material}


def _new_gap(
    *,
    axis: str,
    code: str,
    severity: str,
    source_refs: Iterable[str],
    owner: str,
    next_step: str,
) -> dict[str, Any]:
    return _normalize_gap(
        {
            "axis": axis,
            "code": code,
            "severity": severity,
            "blocks_axis": severity == "blocker",
            "owner": owner,
            "next_step": next_step,
            "source_refs": sorted(set(source_refs)),
        }
    )


def _event_time(event_ref: Mapping[str, Any]) -> str:
    raw = event_ref.get("effective_at")
    if raw is None:
        raw = event_ref.get("occurred_at")
    return _timestamp(raw, name="episode event effective_at")


def _checkpoint_semantics(
    episode: Mapping[str, Any],
    *,
    checkpoint_type: str,
    checkpoint_as_of: str,
    operations: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    if checkpoint_type not in CHECKPOINT_TYPES:
        raise ReviewCheckpointError(
            f"unsupported checkpoint_type: {checkpoint_type!r}"
        )
    episode_id = _text(episode.get("episode_id"), name="episode_id")
    status = _text(episode.get("status"), name="episode status").lower()
    if status not in {"open", "closed"}:
        raise ReviewCheckpointError(
            "P5 checkpoints require a proven open or closed episode lifecycle"
        )
    event_refs = _episode_event_refs(episode)
    opening_id = _text(
        episode.get("opening_event_ref"), name="episode opening_event_ref"
    )
    closing_raw = episode.get("closing_event_ref")
    closing_id = (
        None
        if closing_raw is None
        else _text(closing_raw, name="episode closing_event_ref")
    )
    event_ids = [_text(item.get("event_id"), name="episode event_id") for item in event_refs]
    if opening_id != event_ids[0]:
        raise ReviewCheckpointError("episode opening event is not the first event")

    opened_at = _timestamp(episode.get("opened_at"), name="episode opened_at")
    closed_at = (
        None
        if episode.get("closed_at") is None
        else _timestamp(episode.get("closed_at"), name="episode closed_at")
    )
    if status == "open" and (closed_at is not None or closing_id is not None):
        raise ReviewCheckpointError("open episode cannot expose a closing event")
    if status == "closed" and (
        closed_at is None or closing_id is None or closing_id != event_ids[-1]
    ):
        raise ReviewCheckpointError(
            "closed episode requires an exact final closing event"
        )

    if checkpoint_type in {"entry", "active_checkpoint", "adjustment"}:
        if status != "open":
            raise ReviewCheckpointError(
                f"{checkpoint_type} requires an open episode projection"
            )
        lifecycle = "open"
        outcome = "interim"
    else:
        if status != "closed":
            raise ReviewCheckpointError(
                f"{checkpoint_type} requires a closed episode projection"
            )
        lifecycle = "closed"
        outcome = "final"

    if checkpoint_type == "entry":
        if checkpoint_as_of != opened_at:
            raise ReviewCheckpointError(
                "entry checkpoint_as_of must equal episode opened_at"
            )
        anchor_event_id = opening_id
        if operations[anchor_event_id].get("operation_type") != "position_open":
            raise ReviewCheckpointError(
                "entry requires a proven position_open operation"
            )
        review_kind = "operation_review"
    elif checkpoint_type == "active_checkpoint":
        visible_refs = [
            item for item in event_refs if _dt(_event_time(item)) <= _dt(checkpoint_as_of)
        ]
        if not visible_refs:
            raise ReviewCheckpointError(
                "active checkpoint requires at least one effective episode event"
            )
        anchor_event_id = _text(
            visible_refs[-1].get("event_id"), name="active anchor event_id"
        )
        review_kind = "active_checkpoint"
    elif checkpoint_type == "adjustment":
        matching = [
            item
            for item in event_refs
            if _event_time(item) == checkpoint_as_of
            and item.get("event_id") != opening_id
        ]
        if not matching:
            raise ReviewCheckpointError(
                "adjustment checkpoint must coincide with a non-entry operation"
            )
        anchor_event_id = _text(
            matching[-1].get("event_id"), name="adjustment anchor event_id"
        )
        if (
            operations[anchor_event_id].get("operation_type")
            not in _ADJUSTMENT_OPERATION_TYPES
        ):
            raise ReviewCheckpointError(
                "adjustment checkpoint requires a proven increase, reduce or explicit adjustment"
            )
        review_kind = "operation_review"
    elif checkpoint_type == "exit":
        if checkpoint_as_of != closed_at:
            raise ReviewCheckpointError(
                "exit checkpoint_as_of must equal episode closed_at"
            )
        anchor_event_id = str(closing_id)
        if operations[anchor_event_id].get("operation_type") != "position_close":
            raise ReviewCheckpointError(
                "exit requires a proven position_close operation"
            )
        review_kind = "operation_review"
    else:
        if checkpoint_as_of != closed_at:
            raise ReviewCheckpointError(
                "postmortem checkpoint_as_of must equal episode closed_at"
            )
        anchor_event_id = str(closing_id)
        review_kind = "postmortem"

    return {
        "episode_id": episode_id,
        "position_case_id": f"position_case:{episode_id}",
        "review_kind": review_kind,
        "checkpoint_type": checkpoint_type,
        "lifecycle": lifecycle,
        "outcome": outcome,
        "anchor_event_id": anchor_event_id,
    }


def derive_checkpoint_semantics(
    episode: Mapping[str, Any],
    *,
    operation_review: Mapping[str, Any],
    checkpoint_type: str,
    checkpoint_as_of: str,
) -> dict[str, str]:
    """Return the closed lifecycle/type projection without creating an artifact."""

    _validation_accepted(validate_episode(episode), name="episode")
    _validation_accepted(
        validate_operation_review(operation_review), name="operation_review"
    )
    canonical_as_of = _timestamp(checkpoint_as_of, name="checkpoint_as_of")
    episode_id = _text(episode.get("episode_id"), name="episode_id")
    episode_review = _matched_episode_review(
        operation_review, episode_id=episode_id
    )
    event_ids = [
        _text(item.get("event_id"), name="episode event_id")
        for item in _episode_event_refs(episode)
    ]
    operations = _operations_by_event(
        episode_review, expected_event_ids=event_ids
    )
    if episode_review.get("episode_status") != episode.get("status"):
        raise ReviewCheckpointError(
            "operation review lifecycle does not match the episode"
        )
    return _checkpoint_semantics(
        episode,
        checkpoint_type=checkpoint_type,
        checkpoint_as_of=canonical_as_of,
        operations=operations,
    )


def _checkpoint_anchor(
    reconstruction: Mapping[str, Any],
) -> Mapping[str, Any]:
    anchors = reconstruction.get("anchors")
    if not isinstance(anchors, list):
        raise ReviewCheckpointError("ledger reconstruction anchors must be an array")
    matches = [
        item
        for item in anchors
        if isinstance(item, Mapping) and item.get("anchor_type") == "checkpoint"
    ]
    if len(matches) != 1:
        raise ReviewCheckpointError(
            "ledger reconstruction must contain one checkpoint anchor"
        )
    return matches[0]


def _source_bindings(
    *,
    episode: Mapping[str, Any],
    operation_review: Mapping[str, Any],
    knowledge_provenance: Mapping[str, Any],
    reconstruction: Mapping[str, Any],
) -> list[str]:
    episode_id = _text(episode.get("episode_id"), name="episode_id")
    refs = {
        f"episode:{episode_id}",
        f"method:{METHOD_VERSION}",
        "operation_review:"
        + _content_id(
            operation_review.get("content_id"),
            name="operation_review.content_id",
        ),
        "knowledge_provenance:"
        + _content_id(
            knowledge_provenance.get("content_id"),
            name="knowledge_provenance.content_id",
        ),
        "ledger_snapshot_reconstruction:"
        + _content_id(
            reconstruction.get("content_id"),
            name="ledger_snapshot_reconstruction.content_id",
        ),
    }
    lineage = episode.get("lineage")
    if isinstance(lineage, Mapping) and lineage.get("canonical_content_digest"):
        digest = str(lineage["canonical_content_digest"])
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ReviewCheckpointError(
                "episode canonical_content_digest must be SHA-256"
            )
        refs.add(f"episode_digest:{digest}")
    return sorted(refs)


def build_review_checkpoint(
    *,
    episode: Mapping[str, Any],
    operation_review: Mapping[str, Any],
    knowledge_provenance: Mapping[str, Any],
    ledger_snapshot_reconstruction: Mapping[str, Any],
    perspective: str,
    checkpoint_as_of: str,
    knowledge_cutoff: str,
    checkpoint_type: str,
    market_axis: Mapping[str, Any],
    market_fallback: Mapping[str, Any],
    market_gaps: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build one immutable checkpoint from already frozen, offline sources.

    ``market_axis`` and ``market_fallback`` are intentionally mandatory.  P5
    cannot truthfully invent ``not_needed``, ``provider_unavailable`` or any
    other market state before an actual local-coverage/fallback projection has
    been frozen.
    """

    episode = _mapping(episode, name="episode")
    operation_review = _mapping(operation_review, name="operation_review")
    knowledge_provenance = _mapping(
        knowledge_provenance, name="knowledge_provenance"
    )
    reconstruction = _mapping(
        ledger_snapshot_reconstruction,
        name="ledger_snapshot_reconstruction",
    )
    market_axis = _mapping(market_axis, name="market_axis")
    market_fallback = _mapping(market_fallback, name="market_fallback")

    _validation_accepted(validate_episode(episode), name="episode")
    _validation_accepted(
        validate_operation_review(operation_review), name="operation_review"
    )
    _validation_accepted(
        validate_knowledge_provenance(knowledge_provenance),
        name="knowledge_provenance",
    )
    _validation_accepted(
        validate_ledger_snapshot_reconstruction(reconstruction),
        name="ledger_snapshot_reconstruction",
    )

    canonical_as_of = _timestamp(checkpoint_as_of, name="checkpoint_as_of")
    canonical_cutoff = _timestamp(knowledge_cutoff, name="knowledge_cutoff")
    if _dt(canonical_as_of) > _dt(canonical_cutoff):
        raise ReviewCheckpointError(
            "checkpoint_as_of cannot be later than knowledge_cutoff"
        )
    perspective = _text(perspective, name="perspective").lower()
    if perspective not in {"user", "system"}:
        raise ReviewCheckpointError("perspective must be user or system")

    episode_id = _text(episode.get("episode_id"), name="episode_id")
    event_refs = _episode_event_refs(episode)
    event_ids = [
        _text(item.get("event_id"), name="episode event_id")
        for item in event_refs
    ]
    episode_review = _matched_episode_review(
        operation_review, episode_id=episode_id
    )
    if episode_review.get("episode_status") != episode.get("status"):
        raise ReviewCheckpointError(
            "operation review lifecycle does not match the episode"
        )
    operations = _operations_by_event(
        episode_review, expected_event_ids=event_ids
    )
    semantics = _checkpoint_semantics(
        episode,
        checkpoint_type=checkpoint_type,
        checkpoint_as_of=canonical_as_of,
        operations=operations,
    )

    if knowledge_provenance.get("perspective") != perspective:
        raise ReviewCheckpointError(
            "knowledge_provenance perspective does not match checkpoint"
        )
    if _timestamp(
        knowledge_provenance.get("as_of"),
        name="knowledge_provenance.as_of",
    ) != canonical_as_of:
        raise ReviewCheckpointError(
            "knowledge_provenance as_of must equal checkpoint_as_of"
        )
    if _timestamp(
        knowledge_provenance.get("knowledge_cutoff"),
        name="knowledge_provenance.knowledge_cutoff",
    ) != canonical_cutoff:
        raise ReviewCheckpointError(
            "knowledge_provenance cutoff does not match checkpoint"
        )
    knowledge_events = _knowledge_events(knowledge_provenance)
    if not set(event_ids).issubset(set(knowledge_events)):
        raise ReviewCheckpointError(
            "every checkpoint episode event must be visible in knowledge provenance"
        )
    for event_ref in event_refs:
        event_id = str(event_ref["event_id"])
        knowledge_time = knowledge_events[event_id].get("time_provenance")
        knowledge_effective = (
            knowledge_time.get("effective_at")
            if isinstance(knowledge_time, Mapping)
            else None
        )
        operation_effective = operations[event_id].get("effective_at")
        if (
            not isinstance(knowledge_effective, Mapping)
            or _timestamp(
                knowledge_effective.get("value"),
                name=f"{event_id} knowledge effective_at",
            )
            != _event_time(event_ref)
            or _timestamp(
                operation_effective,
                name=f"{event_id} operation effective_at",
            )
            != _event_time(event_ref)
            or str(operations[event_id].get("side") or "")
            != str(event_ref.get("side") or "")
            or str(operations[event_id].get("qty_before") or "")
            != str(event_ref.get("quantity_before") or "")
            or str(operations[event_id].get("qty_after") or "")
            != str(event_ref.get("quantity_after") or "")
            or str(operations[event_id].get("signed_quantity") or "")
            != str(event_ref.get("signed_quantity") or "")
        ):
            raise ReviewCheckpointError(
                "episode, operation and knowledge event projections do not agree"
            )
    anchor_event = knowledge_events[semantics["anchor_event_id"]]
    time_provenance = _mapping(
        anchor_event.get("time_provenance"),
        name="anchor event time_provenance",
    )
    if (
        not isinstance(time_provenance.get("recorded_at"), Mapping)
        or time_provenance["recorded_at"].get("value") is None
    ):
        raise ReviewCheckpointError(
            "checkpoint anchor requires a proven recorded_at value"
        )
    if (
        not isinstance(time_provenance.get("effective_at"), Mapping)
        or _timestamp(
            time_provenance["effective_at"].get("value"),
            name="anchor effective_at",
        )
        != _event_time(
            next(
                item
                for item in event_refs
                if item.get("event_id") == semantics["anchor_event_id"]
            )
        )
    ):
        raise ReviewCheckpointError(
            "knowledge anchor effective time does not match the episode event"
        )

    if reconstruction.get("episode_id") != episode_id:
        raise ReviewCheckpointError(
            "ledger reconstruction episode_id does not match checkpoint"
        )
    if reconstruction.get("perspective") != perspective:
        raise ReviewCheckpointError(
            "ledger reconstruction perspective does not match checkpoint"
        )
    if _timestamp(
        reconstruction.get("as_of"),
        name="ledger_snapshot_reconstruction.as_of",
    ) != canonical_as_of:
        raise ReviewCheckpointError(
            "ledger reconstruction as_of must equal checkpoint_as_of"
        )
    if _timestamp(
        reconstruction.get("knowledge_cutoff"),
        name="ledger_snapshot_reconstruction.knowledge_cutoff",
    ) != canonical_cutoff:
        raise ReviewCheckpointError(
            "ledger reconstruction cutoff does not match checkpoint"
        )
    cursor = _mapping(
        reconstruction.get("event_cursor"),
        name="ledger reconstruction event_cursor",
    )
    included_event_ids = cursor.get("included_event_ids")
    visible_event_ids = cursor.get("visible_event_ids")
    excluded_event_ids = cursor.get("excluded_by_episode_cursor_ids")
    if (
        not isinstance(included_event_ids, list)
        or not isinstance(visible_event_ids, list)
        or not isinstance(excluded_event_ids, list)
        or not set(event_ids).issubset(set(included_event_ids))
        or not set(event_ids).issubset(set(visible_event_ids))
        or set(event_ids).intersection(set(excluded_event_ids))
    ):
        raise ReviewCheckpointError(
            "ledger reconstruction cursor does not include the exact episode facts"
        )
    anchor = _checkpoint_anchor(reconstruction)
    snapshot_axis = _mapping(
        anchor.get("snapshot_cash_valuation"),
        name="checkpoint snapshot_cash_valuation",
    )

    bindings = _source_bindings(
        episode=episode,
        operation_review=operation_review,
        knowledge_provenance=knowledge_provenance,
        reconstruction=reconstruction,
    )
    operation_refs = set(bindings)
    for operation in operations.values():
        operation_refs.update(_source_ref_strings(operation))
    operation_refs = set(sorted(operation_refs))

    operation_status = _text(
        episode_review.get("operation_review_status"),
        name="operation_review_status",
    ).lower()
    if operation_status not in {"ready", "partial", "blocked"}:
        raise ReviewCheckpointError(
            "unsupported operation review status for checkpoint"
        )
    decision_status = _text(
        episode_review.get("decision_context_status"),
        name="decision_context_status",
    ).lower()
    if decision_status not in {
        "complete",
        "partial",
        "not_recorded",
        "not_applicable",
        "blocked",
    }:
        raise ReviewCheckpointError(
            "unsupported decision context status for checkpoint"
        )

    lifecycle_refs = sorted(
        ref
        for ref in bindings
        if ref.startswith(("episode:", "episode_digest:"))
    )
    status_axes: dict[str, Any] = {
        "operation": {
            "status": operation_status,
            "summary": (
                "账户操作事实已完成复盘。"
                if operation_status == "ready"
                else "账户操作事实存在明确的局部限制。"
                if operation_status == "partial"
                else "账户操作事实存在阻断性冲突。"
            ),
            "source_refs": sorted(operation_refs),
        },
        "decision": {
            "status": decision_status,
            "summary": (
                "未记录决策理由；不影响操作事实。"
                if decision_status == "not_recorded"
                else "该操作不适用决策理由复核。"
                if decision_status == "not_applicable"
                else "决策背景按独立证据轴展示。"
            ),
            "source_refs": (
                []
                if decision_status in {"not_recorded", "not_applicable"}
                else sorted(operation_refs)
            ),
        },
        "snapshot_cash_valuation": deepcopy(dict(snapshot_axis)),
        "market": deepcopy(dict(market_axis)),
        "lifecycle": {
            "status": semantics["lifecycle"],
            "summary": (
                "持仓周期仍在进行。"
                if semantics["lifecycle"] == "open"
                else "持仓周期已由明确退出事件关闭。"
            ),
            "source_refs": lifecycle_refs,
        },
        "outcome": {
            "status": semantics["outcome"],
            "summary": (
                "结果为阶段性状态，尚未形成最终结果。"
                if semantics["outcome"] == "interim"
                else "持仓周期已结束；本字段不生成或暗示最终损益。"
            ),
            "source_refs": lifecycle_refs,
        },
    }

    gaps: list[dict[str, Any]] = []
    raw_snapshot_gaps = anchor.get("gaps")
    if not isinstance(raw_snapshot_gaps, list):
        raise ReviewCheckpointError("checkpoint anchor gaps must be an array")
    gaps.extend(_normalize_gap(item) for item in raw_snapshot_gaps)
    gaps.extend(_normalize_gap(item) for item in market_gaps)
    reason_codes = episode_review.get("reason_codes")
    if not isinstance(reason_codes, list):
        raise ReviewCheckpointError(
            "operation review reason_codes must be an array"
        )
    if operation_status == "partial":
        for code in reason_codes or ["OPERATION_REVIEW_PARTIAL"]:
            gaps.append(
                _new_gap(
                    axis="operation",
                    code=str(code),
                    severity="warning",
                    source_refs=operation_refs,
                    owner="data_owner",
                    next_step="复核歧义操作事实或补充显式事件证据。",
                )
            )
    elif operation_status == "blocked":
        gaps.append(
            _new_gap(
                axis="operation",
                code="OPERATION_REVIEW_BLOCKED",
                severity="blocker",
                source_refs=operation_refs,
                owner="data_owner",
                next_step="解决数量链或显式事件事实的阻断性冲突。",
            )
        )
    if decision_status == "blocked":
        gaps.append(
            _new_gap(
                axis="decision",
                code="DECISION_CONTEXT_BLOCKED",
                severity="blocker",
                source_refs=operation_refs,
                owner="review_owner",
                next_step="复核冲突的显式 Decision 关联；不得推断缺失理由。",
            )
        )
    elif decision_status == "partial":
        gaps.append(
            _new_gap(
                axis="decision",
                code="DECISION_CONTEXT_PARTIAL",
                severity="warning",
                source_refs=operation_refs,
                owner="review_owner",
                next_step="复核现有 Decision 关联的局部歧义。",
            )
        )
    gaps = sorted(
        {item["gap_id"]: item for item in gaps}.values(),
        key=lambda item: item["gap_id"],
    )

    root_refs = set(bindings)
    for axis in status_axes.values():
        refs = axis.get("source_refs")
        if isinstance(refs, list):
            root_refs.update(str(item) for item in refs)
    for item in time_provenance.values():
        if isinstance(item, Mapping) and isinstance(item.get("source_refs"), list):
            root_refs.update(str(ref) for ref in item["source_refs"])
    for gap in gaps:
        root_refs.update(gap["source_refs"])
    root_refs.update(str(ref) for ref in market_fallback.get("cache_refs", []))

    raw_checkpoint = {
        "schema_version": OPERATION_CHECKPOINT_SCHEMA_VERSION,
        "episode_id": episode_id,
        "position_case_id": semantics["position_case_id"],
        "review_kind": semantics["review_kind"],
        "checkpoint_type": semantics["checkpoint_type"],
        "perspective": perspective,
        "as_of": canonical_as_of,
        "knowledge_cutoff": canonical_cutoff,
        "time_provenance": deepcopy(dict(time_provenance)),
        "status_axes": status_axes,
        "market_fallback": deepcopy(dict(market_fallback)),
        "gaps": gaps,
        "source_refs": sorted(root_refs),
        "governance": deepcopy(_GOVERNANCE),
    }
    try:
        checkpoint = OperationCheckpointRecord.from_mapping(raw_checkpoint).to_dict()
    except Exception as exc:
        raise ReviewCheckpointError(
            f"checkpoint failed the closed operation contract: {type(exc).__name__}"
        ) from exc
    validation = validate_review_checkpoint(checkpoint)
    if validation["validation_status"] != "accepted":
        raise ReviewCheckpointError(
            "built checkpoint failed validation: "
            + ",".join(item["code"] for item in validation["findings"])
        )
    return checkpoint


def _finding(
    code: str,
    message: str,
    *,
    related_refs: Iterable[str] = (),
) -> dict[str, Any]:
    return {
        "severity": "blocker",
        "code": code,
        "message": message,
        "related_refs": sorted({str(item) for item in related_refs if str(item)}),
    }


def _semantic_validation_findings(
    checkpoint: Mapping[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    episode_id = str(checkpoint.get("episode_id") or "")
    expected_case = f"position_case:{episode_id}"
    if checkpoint.get("position_case_id") != expected_case:
        findings.append(
            _finding(
                "NON_EPISODE_SCOPED_POSITION_CASE",
                "position_case_id must remain rooted in exactly one episode",
                related_refs=[episode_id],
            )
        )
    source_refs = checkpoint.get("source_refs")
    refs = set(source_refs) if isinstance(source_refs, list) else set()
    for prefix in _BINDING_PREFIXES:
        matches = [ref for ref in refs if isinstance(ref, str) and ref.startswith(prefix)]
        if len(matches) != 1:
            findings.append(
                _finding(
                    "MISSING_OR_AMBIGUOUS_SOURCE_BINDING",
                    f"checkpoint requires exactly one {prefix} binding",
                    related_refs=matches,
                )
            )
    if f"method:{METHOD_VERSION}" not in refs:
        findings.append(
            _finding(
                "MISSING_CHECKPOINT_METHOD_BINDING",
                "checkpoint source refs do not bind the P5 method version",
            )
        )
    nested_refs: set[str] = set()
    axes = checkpoint.get("status_axes")
    if isinstance(axes, Mapping):
        for axis in axes.values():
            if isinstance(axis, Mapping) and isinstance(axis.get("source_refs"), list):
                nested_refs.update(str(item) for item in axis["source_refs"])
    time_provenance = checkpoint.get("time_provenance")
    if isinstance(time_provenance, Mapping):
        for item in time_provenance.values():
            if isinstance(item, Mapping) and isinstance(item.get("source_refs"), list):
                nested_refs.update(str(ref) for ref in item["source_refs"])
    gaps = checkpoint.get("gaps")
    if isinstance(gaps, list):
        for gap in gaps:
            if isinstance(gap, Mapping) and isinstance(gap.get("source_refs"), list):
                nested_refs.update(str(ref) for ref in gap["source_refs"])
    fallback = checkpoint.get("market_fallback")
    if isinstance(fallback, Mapping) and isinstance(fallback.get("cache_refs"), list):
        nested_refs.update(str(ref) for ref in fallback["cache_refs"])
    if not nested_refs.issubset(refs):
        findings.append(
            _finding(
                "ROOT_SOURCE_REFS_INCOMPLETE",
                "root source_refs must cover every nested material reference",
                related_refs=sorted(nested_refs - refs),
            )
        )

    checkpoint_type = checkpoint.get("checkpoint_type")
    as_of = checkpoint.get("as_of")
    effective_at = None
    if isinstance(time_provenance, Mapping):
        effective = time_provenance.get("effective_at")
        if isinstance(effective, Mapping):
            effective_at = effective.get("value")
    if checkpoint_type in {"entry", "adjustment", "exit", "postmortem"}:
        if effective_at != as_of:
            findings.append(
                _finding(
                    "CHECKPOINT_EVENT_TIME_MISMATCH",
                    f"{checkpoint_type} must be anchored to its material event time",
                )
            )
    elif checkpoint_type == "active_checkpoint":
        try:
            valid = _dt(str(effective_at)) <= _dt(str(as_of))
        except Exception:
            valid = False
        if not valid:
            findings.append(
                _finding(
                    "ACTIVE_CHECKPOINT_PRECEDES_ANCHOR",
                    "active checkpoint cannot precede its latest material event",
                )
            )
    if isinstance(gaps, list) and any(
        isinstance(gap, Mapping)
        and str(gap.get("code") or "").upper()
        == "OPEN_EPISODE_OUTCOME_NOT_FINAL"
        for gap in gaps
    ):
        findings.append(
            _finding(
                "INTERIM_OUTCOME_MISCLASSIFIED_AS_GAP",
                "open/interim outcome is normal and must not be a gap",
            )
        )
    return findings


def validate_review_checkpoint(artifact: object) -> dict[str, Any]:
    """Validate a canonical, closed checkpoint without reading any source."""

    findings: list[dict[str, Any]] = []
    if not isinstance(artifact, Mapping):
        findings.append(
            _finding(
                "MALFORMED_REVIEW_CHECKPOINT",
                "review checkpoint must be a mapping",
            )
        )
    else:
        if set(artifact) != _ROOT_FIELDS:
            findings.append(
                _finding(
                    "MALFORMED_REVIEW_CHECKPOINT_SHAPE",
                    "review checkpoint uses an unexpected root field set",
                )
            )
        try:
            normalized = OperationCheckpointRecord.from_mapping(artifact).to_dict()
        except Exception as exc:
            normalized = None
            findings.append(
                _finding(
                    "INVALID_OPERATION_CHECKPOINT_CONTRACT",
                    f"closed operation checkpoint validation failed: {type(exc).__name__}",
                )
            )
        if normalized is not None:
            if dict(artifact) != normalized:
                findings.append(
                    _finding(
                        "NON_CANONICAL_REVIEW_CHECKPOINT",
                        "checkpoint is not the exact canonical closed projection",
                    )
                )
            findings.extend(_semantic_validation_findings(normalized))
    findings = sorted(
        {
            canonical_json_bytes(item).decode("utf-8"): item
            for item in findings
        }.values(),
        key=lambda item: (
            str(item.get("code") or ""),
            canonical_json_bytes(item.get("related_refs") or []).decode("utf-8"),
        ),
    )
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "validation_status": "accepted" if not findings else "blocked",
        "findings": findings,
    }


def canonical_review_checkpoint_bytes(artifact: Mapping[str, Any]) -> bytes:
    """Return canonical bytes only for a fully accepted checkpoint."""

    validation = validate_review_checkpoint(artifact)
    if validation["validation_status"] != "accepted":
        raise ReviewCheckpointError(
            "review checkpoint validation blocked: "
            + ",".join(item["code"] for item in validation["findings"])
        )
    return OperationCheckpointRecord.from_mapping(artifact).canonical_bytes


def replay_validate_review_checkpoint(
    artifact: object,
    *,
    episode: Mapping[str, Any],
    operation_review: Mapping[str, Any],
    knowledge_provenance: Mapping[str, Any],
    ledger_snapshot_reconstruction: Mapping[str, Any],
    perspective: str,
    checkpoint_as_of: str,
    knowledge_cutoff: str,
    checkpoint_type: str,
    market_axis: Mapping[str, Any],
    market_fallback: Mapping[str, Any],
    market_gaps: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Rebuild from the frozen source set and require byte-identical output."""

    findings = list(validate_review_checkpoint(artifact)["findings"])
    try:
        rebuilt = build_review_checkpoint(
            episode=episode,
            operation_review=operation_review,
            knowledge_provenance=knowledge_provenance,
            ledger_snapshot_reconstruction=ledger_snapshot_reconstruction,
            perspective=perspective,
            checkpoint_as_of=checkpoint_as_of,
            knowledge_cutoff=knowledge_cutoff,
            checkpoint_type=checkpoint_type,
            market_axis=market_axis,
            market_fallback=market_fallback,
            market_gaps=market_gaps,
        )
    except Exception as exc:
        rebuilt = None
        findings.append(
            _finding(
                "REVIEW_CHECKPOINT_REBUILD_FAILED",
                f"checkpoint rebuild failed: {type(exc).__name__}",
            )
        )
    if rebuilt is not None:
        try:
            matches = (
                canonical_review_checkpoint_bytes(rebuilt)
                == canonical_review_checkpoint_bytes(artifact)  # type: ignore[arg-type]
            )
        except Exception:
            matches = False
        if not matches:
            findings.append(
                _finding(
                    "REVIEW_CHECKPOINT_SOURCE_REPLAY_MISMATCH",
                    "rebuilt checkpoint is not byte-identical",
                )
            )
    findings = sorted(
        {
            canonical_json_bytes(item).decode("utf-8"): item
            for item in findings
        }.values(),
        key=lambda item: str(item.get("code") or ""),
    )
    verified = not findings
    return {
        "schema_version": REPLAY_SCHEMA_VERSION,
        "validation_status": "accepted" if verified else "blocked",
        "source_verification": {
            "status": "verified" if verified else "blocked",
            "content_id": (
                artifact.get("content_id")
                if isinstance(artifact, Mapping)
                else None
            ),
        },
        "findings": findings,
    }


def plan_review_checkpoint_append(
    checkpoint: Mapping[str, Any],
    *,
    existing_checkpoints: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Plan a create-only append without mutating the supplied history.

    Persistence code must enforce the same checkpoint-key uniqueness in its
    write transaction.  This pure planner provides the deterministic
    ``INSERTED``/``SKIPPED``/conflict contract used by runner/store wiring.
    """

    candidate_validation = validate_review_checkpoint(checkpoint)
    if candidate_validation["validation_status"] != "accepted":
        raise ReviewCheckpointError(
            "candidate checkpoint is not valid for append"
        )
    candidate_bytes = canonical_review_checkpoint_bytes(checkpoint)
    candidate_key = str(checkpoint["checkpoint_key"])
    candidate_id = str(checkpoint["checkpoint_id"])
    for existing in existing_checkpoints:
        validation = validate_review_checkpoint(existing)
        if validation["validation_status"] != "accepted":
            raise ReviewCheckpointError(
                "existing checkpoint history contains an invalid artifact"
            )
        same_key = existing.get("checkpoint_key") == candidate_key
        same_id = existing.get("checkpoint_id") == candidate_id
        if same_key or same_id:
            if canonical_review_checkpoint_bytes(existing) == candidate_bytes:
                status = "SKIPPED"
                break
            raise ReviewCheckpointConflictError(
                "immutable checkpoint semantic identity already has different content"
            )
    else:
        status = "INSERTED"
    return {
        "schema_version": APPEND_PLAN_SCHEMA_VERSION,
        "status": status,
        "checkpoint_id": checkpoint["checkpoint_id"],
        "checkpoint_key": checkpoint["checkpoint_key"],
        "content_id": checkpoint["content_id"],
    }
