"""Closed, deterministic knowledge-time projection for reviewability v3.

This module is an additive adapter over legacy canonical trade events.  It does
not change ``event_id`` or reinterpret the legacy ``known_at`` column.  Instead,
it projects effective, user-known, system-observed, and recorded times from
explicit event and first-ingest evidence, then selects unchanged event mappings
for one explicit knowledge perspective.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo


SCHEMA_VERSION = "investment_review.knowledge_provenance.v1"
METHOD_VERSION = "account_event_knowledge_projection_v1"
VALIDATION_SCHEMA_VERSION = "investment_review.knowledge_provenance.validation.v1"
REPLAY_SCHEMA_VERSION = "investment_review.knowledge_provenance.replay.v1"
PERSPECTIVES = frozenset({"user", "system"})

_ROOT_FIELDS = {
    "schema_version",
    "method_version",
    "content_id",
    "perspective",
    "as_of",
    "knowledge_cutoff",
    "source_binding",
    "events",
    "visibility_ledger",
    "visible_event_ids",
    "withheld_event_ids",
    "governance",
}
_SOURCE_BINDING_FIELDS = {
    "event_input_count",
    "event_projection_content_id",
    "full_event_input_content_id",
    "event_input_manifest",
    "observation_evidence_count",
    "observation_evidence_content_id",
}
_INPUT_MANIFEST_FIELDS = {
    "event_id",
    "effective_at",
    "event_input_content_id",
    "source_refs",
}
_EVENT_FIELDS = {
    "event_id",
    "fact_domain",
    "fact_kind",
    "owner_action_default_applied",
    "time_provenance",
    "visibility",
    "withheld_evidence",
    "gaps",
    "source_refs",
}
_TIME_FIELDS = {
    "effective_at",
    "user_known_at",
    "system_observed_at",
    "recorded_at",
}
_TIME_PROJECTION_FIELDS = {"value", "basis", "source_refs"}
_VISIBILITY_FIELDS = {
    "status",
    "reason",
    "selected_time_field",
    "selected_time_value",
    "source_refs",
}
_WITHHELD_EVIDENCE_FIELDS = {
    "field",
    "status",
    "evidence_content_id",
    "source_refs",
}
_LEDGER_FIELDS = {
    "event_id",
    "status",
    "reason",
    "event_projection_content_id",
    "source_refs",
}
_GAP_FIELDS = {
    "code",
    "severity",
    "owner",
    "next_step",
    "source_refs",
}
_GAP_DETAILS = {
    "RECORDED_TIME_NOT_PROVEN": (
        "warning",
        "data_provenance",
        "capture a cutoff-safe source recorded time or immutable ingest evidence",
    ),
    "RECORDED_TIME_WITHHELD_BY_CUTOFF": (
        "info",
        "data_provenance",
        "rerun at a knowledge cutoff that includes the recorded evidence",
    ),
}
_VISIBILITY_REASONS = {
    "visible_at_perspective_cutoff",
    "user_knowledge_not_proven",
    "system_observation_withheld_by_cutoff",
    "system_observation_not_proven",
    "recorded_time_not_proven",
    "recorded_after_knowledge_cutoff",
}
_LEDGER_REASONS = {*_VISIBILITY_REASONS, "effective_after_as_of"}
_EFFECTIVE_BASES = {"source_occurred_at", "source_effective_at"}
_USER_BASES = {
    "owner_action_default",
    "explicit_user_record",
    "source_occurred_at",
    "source_effective_at",
    "not_observed",
    "unknown",
}
_SYSTEM_BASES = {
    "system_observation",
    "recorded_later",
    "ingest_observation",
    "not_observed",
    "unknown",
}
_RECORDED_BASES = {
    "recorded_later",
    "ingest_observation",
    "system_observation",
    "unknown",
}
_OWNER_ACTION_PAIRS = {
    ("fill", "BUY"),
    ("fill", "SELL"),
    ("buy", "BUY"),
    ("sell", "SELL"),
    ("trade", "BUY"),
    ("trade", "SELL"),
    ("transfer", "TRANSFER_IN"),
    ("transfer", "TRANSFER_OUT"),
}
_MARKET_EVENT_TYPES = {
    "market_data",
    "price",
    "quote",
    "close_price",
    "daily_bar",
    "minute_bar",
    "adjustment_factor",
}
_GOVERNANCE = {
    "facts_only": True,
    "event_identity_preserved": True,
    "legacy_known_at_unchanged": True,
    "owner_action_default_account_only": True,
    "market_owner_action_default": False,
    "system_observation_requires_first_ingest_evidence": True,
    "raw_created_at_is_system_observation": False,
    "motive_inferred": False,
    "advice_generated": False,
    "model_called": False,
}


class KnowledgeProvenanceError(ValueError):
    """Raised when knowledge provenance cannot be projected safely."""


def _assert_strict_json(value: object, *, path: str = "$") -> None:
    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise KnowledgeProvenanceError(
                f"lone surrogate is forbidden in knowledge provenance at {path}"
            )
        return
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        raise KnowledgeProvenanceError(
            f"binary float is forbidden in knowledge provenance at {path}"
        )
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, item in enumerate(value):
            _assert_strict_json(item, path=f"{path}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise KnowledgeProvenanceError(
                    f"non-string object key in knowledge provenance at {path}"
                )
            _assert_strict_json(item, path=f"{path}.{key}")
        return
    raise KnowledgeProvenanceError(
        f"non-JSON value {type(value).__name__} in knowledge provenance at {path}"
    )


def _canonical_bytes(value: object) -> bytes:
    _assert_strict_json(value)
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (UnicodeEncodeError, ValueError) as exc:
        raise KnowledgeProvenanceError(
            "knowledge provenance cannot be encoded as strict canonical UTF-8 JSON"
        ) from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _content_id(value: Mapping[str, Any]) -> str:
    material = deepcopy(dict(value))
    material["content_id"] = ""
    return "sha256:" + _digest(material)


def canonical_knowledge_provenance_bytes(
    artifact: Mapping[str, Any],
) -> bytes:
    """Return strict canonical bytes used by identity and source replay."""

    if not isinstance(artifact, Mapping):
        raise KnowledgeProvenanceError(
            "knowledge provenance artifact must be a mapping"
        )
    return _canonical_bytes(dict(artifact))


def _text(value: object) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _timestamp(
    value: object,
    *,
    field: str,
    allow_naive_source: bool = False,
) -> str:
    text = _text(value)
    if text is None:
        raise KnowledgeProvenanceError(f"{field} is required")
    normalized = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except (OverflowError, ValueError) as exc:
        raise KnowledgeProvenanceError(
            f"{field} is not a valid timestamp: {text!r}"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        if not allow_naive_source:
            raise KnowledgeProvenanceError(
                f"{field} must include an explicit timezone: {text!r}"
            )
        parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    try:
        return parsed.astimezone(timezone.utc).isoformat()
    except (OverflowError, ValueError) as exc:
        raise KnowledgeProvenanceError(
            f"{field} is outside the canonical UTC range"
        ) from exc


def _timestamp_or_none(
    value: object,
    *,
    field: str,
    allow_naive_source: bool = False,
) -> str | None:
    if value in (None, ""):
        return None
    return _timestamp(
        value,
        field=field,
        allow_naive_source=allow_naive_source,
    )


def _safe_source_recorded_timestamp(
    value: object,
    *,
    field: str,
) -> str | None:
    """Return only an explicitly zoned source recording time.

    A legacy raw value may be naive, malformed, or unrelated rebuild text.  It
    is not allowed to abort projection or acquire an assumed timezone; callers
    fall back to true sidecar ingest evidence instead.
    """

    try:
        return _timestamp_or_none(value, field=field)
    except KnowledgeProvenanceError:
        return None


def _as_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _raw_payload(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise KnowledgeProvenanceError(
                "raw_payload_json is not valid JSON"
            ) from exc
        if isinstance(decoded, Mapping):
            return decoded
    return {}


def _source_row(value: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = _raw_payload(
        value.get("raw_payload", value.get("raw_payload_json"))
    )
    row = raw.get("source_row")
    return row if isinstance(row, Mapping) else {}


def _source_refs(event: Mapping[str, Any]) -> list[str]:
    event_id = _text(event.get("event_id"))
    source_id = _text(event.get("source_id"))
    source_record_id = _text(event.get("source_record_id"))
    payload_sha256 = _text(event.get("payload_sha256"))
    refs = {
        event_id,
        f"source:{source_id}" if source_id else None,
        (
            f"source_record:{source_id or 'unknown'}:{source_record_id}"
            if source_record_id
            else None
        ),
        f"payload_sha256:{payload_sha256}" if payload_sha256 else None,
    }
    return sorted(item for item in refs if item)


def _event_projection(event: Mapping[str, Any]) -> dict[str, Any]:
    event_id = _text(event.get("event_id"))
    if event_id is None:
        raise KnowledgeProvenanceError("event_id is required")
    source_id = _text(event.get("source_id"))
    if source_id is None:
        raise KnowledgeProvenanceError(f"{event_id}.source_id is required")
    payload_sha256 = _text(event.get("payload_sha256"))
    if (
        payload_sha256 is None
        or len(payload_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in payload_sha256
        )
    ):
        raise KnowledgeProvenanceError(
            f"{event_id}.payload_sha256 must be a lowercase SHA-256"
        )
    occurred_at = _timestamp(
        event.get("occurred_at", event.get("effective_at")),
        field=f"{event_id}.occurred_at",
    )
    known_at = _timestamp(
        event.get("known_at", event.get("occurred_at")),
        field=f"{event_id}.known_at",
    )
    if _as_datetime(known_at) < _as_datetime(occurred_at):
        raise KnowledgeProvenanceError(
            f"{event_id}.known_at precedes occurred_at"
        )
    return {
        "event_id": event_id,
        "source_id": source_id,
        "source_record_id": _text(event.get("source_record_id")),
        "payload_sha256": payload_sha256,
        "event_type": (_text(event.get("event_type")) or "fill").lower(),
        "occurred_at": occurred_at,
        "known_at": known_at,
        "account": _text(event.get("account")),
        "market": _text(event.get("market")),
        "symbol": _text(event.get("symbol")),
        "side": (_text(event.get("side")) or "").upper(),
        "first_ingest_run_id": _text(event.get("first_ingest_run_id")),
        "ingested_at": _timestamp_or_none(
            event.get("ingested_at"),
            field=f"{event_id}.ingested_at",
        ),
        "source_created_at": _safe_source_recorded_timestamp(
            _source_row(event).get("created_at"),
            field=f"{event_id}.source_created_at",
        ),
        "fact_domain": (
            "market"
            if (
                str(event.get("fact_domain") or "").strip().lower()
                == "market"
                or str(event.get("event_type") or "").strip().lower()
                in _MARKET_EVENT_TYPES
            )
            else "account"
        ),
        "source_refs": _source_refs(event),
    }


def _dedupe_event_inputs(
    event_inputs: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    buckets: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for index, raw in enumerate(event_inputs):
        if not isinstance(raw, Mapping):
            raise KnowledgeProvenanceError("event inputs must be mappings")
        original = deepcopy(dict(raw))
        _assert_strict_json(original, path=f"$event_inputs[{index}]")
        projection = _event_projection(original)
        buckets.setdefault(projection["event_id"], []).append(
            (projection, original)
        )
    projections: list[dict[str, Any]] = []
    originals: dict[str, dict[str, Any]] = {}
    for event_id in sorted(buckets):
        projection_variants = {
            _digest(projection): projection
            for projection, _original in buckets[event_id]
        }
        original_variants = {
            _digest(original): original
            for _projection, original in buckets[event_id]
        }
        if len(projection_variants) != 1 or len(original_variants) != 1:
            raise KnowledgeProvenanceError(
                f"conflicting duplicate event_id in knowledge inputs: {event_id}"
            )
        projection = next(iter(projection_variants.values()))
        original = next(iter(original_variants.values()))
        projections.append(projection)
        originals[event_id] = original
    return projections, originals


def _event_input_manifest(
    event_projections: Sequence[Mapping[str, Any]],
    originals: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "event_id": str(event["event_id"]),
            "effective_at": str(event["occurred_at"]),
            "event_input_content_id": "sha256:"
            + _digest(originals[str(event["event_id"])]),
            "source_refs": list(event["source_refs"]),
        }
        for event in event_projections
    ]


def _evidence_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    event_id = _text(value.get("event_id"))
    if event_id is None:
        raise KnowledgeProvenanceError(
            "observation evidence event_id is required"
        )
    first = value.get("first_ingest")
    first_ingest = first if isinstance(first, Mapping) else {}
    return {
        "event_id": event_id,
        "source_id": _text(value.get("source_id")),
        "source_record_id": _text(value.get("source_record_id")),
        "payload_sha256": _text(value.get("payload_sha256")),
        "ingested_at": _timestamp_or_none(
            value.get("ingested_at"),
            field=f"{event_id}.evidence.ingested_at",
        ),
        "source_created_at": _safe_source_recorded_timestamp(
            _source_row(value).get("created_at"),
            field=f"{event_id}.evidence.source_created_at",
        ),
        "first_ingest": {
            "run_id": _text(first_ingest.get("run_id")),
            "outcome": _text(first_ingest.get("outcome")),
            "observed_at": _timestamp_or_none(
                first_ingest.get("observed_at"),
                field=f"{event_id}.first_ingest.observed_at",
            ),
            "observation_payload_sha256": _text(
                first_ingest.get("observation_payload_sha256")
            ),
            "source_id": _text(first_ingest.get("source_id")),
            "source_fingerprint": _text(
                first_ingest.get("source_fingerprint")
            ),
            "status": _text(first_ingest.get("status")),
        },
    }


def _dedupe_evidence(
    observation_evidence: Iterable[Mapping[str, Any]],
    *,
    event_index: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for raw in observation_evidence:
        if not isinstance(raw, Mapping):
            raise KnowledgeProvenanceError(
                "observation evidence entries must be mappings"
            )
        projected = _evidence_projection(raw)
        buckets.setdefault(projected["event_id"], []).append(projected)
    projections: list[dict[str, Any]] = []
    result: dict[str, dict[str, Any]] = {}
    for event_id in sorted(buckets):
        if event_id not in event_index:
            raise KnowledgeProvenanceError(
                f"orphan observation evidence: {event_id}"
            )
        variants = {
            _digest(projection): projection
            for projection in buckets[event_id]
        }
        if len(variants) != 1:
            raise KnowledgeProvenanceError(
                f"conflicting observation evidence: {event_id}"
            )
        projection = next(iter(variants.values()))
        event = event_index[event_id]
        for field in ("source_id", "source_record_id", "payload_sha256"):
            evidence_value = projection.get(field)
            event_value = event.get(field)
            if evidence_value != event_value:
                raise KnowledgeProvenanceError(
                    f"observation evidence {field} mismatch: {event_id}"
                )
        if (
            projection.get("ingested_at")
            and event.get("ingested_at")
            and projection["ingested_at"] != event["ingested_at"]
        ):
            raise KnowledgeProvenanceError(
                f"observation evidence ingested_at mismatch: {event_id}"
            )
        if (
            projection.get("source_created_at")
            and event.get("source_created_at")
            and projection["source_created_at"]
            != event["source_created_at"]
        ):
            raise KnowledgeProvenanceError(
                f"observation evidence source_created_at mismatch: {event_id}"
            )
        projections.append(projection)
        result[event_id] = projection
    return projections, result


def _valid_first_ingest(
    event: Mapping[str, Any],
    evidence: Mapping[str, Any] | None,
) -> tuple[str | None, list[str]]:
    if evidence is None:
        return None, []
    first = evidence.get("first_ingest")
    if not isinstance(first, Mapping):
        return None, []
    has_any = any(value not in (None, "") for value in first.values())
    if not has_any:
        return None, []
    event_id = str(event["event_id"])
    event_run_id = _text(event.get("first_ingest_run_id"))
    if (
        event_run_id is None
        or
        first.get("outcome") != "INSERTED"
        or first.get("status") != "COMPLETED"
        or not first.get("observed_at")
        or not first.get("run_id")
        or first.get("source_id") != event.get("source_id")
        or not first.get("source_fingerprint")
        or first.get("observation_payload_sha256")
        != event.get("payload_sha256")
        or first.get("run_id") != event_run_id
    ):
        raise KnowledgeProvenanceError(
            f"first-ingest observation binding is invalid: {event_id}"
        )
    if _as_datetime(str(first["observed_at"])) < _as_datetime(
        str(event["occurred_at"])
    ):
        raise KnowledgeProvenanceError(
            f"first-ingest observation precedes effective time: {event_id}"
        )
    refs = sorted(
        {
            event_id,
            f"ingest_run:{first['run_id']}",
            f"ingest_observation:{first['run_id']}:{event_id}",
            f"payload_sha256:{event.get('payload_sha256')}",
        }
    )
    return str(first["observed_at"]), refs


def _recorded_projection(
    event: Mapping[str, Any],
    evidence: Mapping[str, Any] | None,
    *,
    effective_at: str,
) -> tuple[str | None, str, list[str]]:
    event_id = str(event["event_id"])
    effective_dt = _as_datetime(effective_at)
    source_created_at = (
        evidence.get("source_created_at")
        if evidence is not None and evidence.get("source_created_at")
        else event.get("source_created_at")
    )
    if (
        source_created_at
        and _as_datetime(str(source_created_at)) >= effective_dt
    ):
        return (
            str(source_created_at),
            "recorded_later",
            sorted(
                {
                    event_id,
                    f"source_recorded:{event_id}:created_at",
                    *event.get("source_refs", []),
                }
            ),
        )
    ingested_at = (
        evidence.get("ingested_at")
        if evidence is not None and evidence.get("ingested_at")
        else event.get("ingested_at")
    )
    if ingested_at and _as_datetime(str(ingested_at)) >= effective_dt:
        return (
            str(ingested_at),
            "ingest_observation",
            sorted(
                {
                    event_id,
                    f"sidecar_ingested:{event_id}",
                    *event.get("source_refs", []),
                }
            ),
        )
    return None, "unknown", []


def _fact_kind(event: Mapping[str, Any]) -> str:
    if event["fact_domain"] == "market":
        return "market_fact"
    event_type = str(event.get("event_type") or "").lower()
    side = str(event.get("side") or "").upper()
    if event.get("account") and (event_type, side) in _OWNER_ACTION_PAIRS:
        return "owner_action"
    return "account_fact"


def _time_projection(
    value: str | None,
    basis: str,
    source_refs: Iterable[str],
) -> dict[str, Any]:
    return {
        "value": value,
        "basis": basis,
        "source_refs": sorted({str(item) for item in source_refs if str(item)}),
    }


def _event_projection_content_id(event: Mapping[str, Any]) -> str:
    return "sha256:" + _digest(event)


def _gap(
    code: str,
    *,
    event_id: str,
    source_refs: Iterable[str],
) -> dict[str, Any]:
    severity, owner, next_step = _GAP_DETAILS[code]
    return {
        "code": code,
        "severity": severity,
        "owner": owner,
        "next_step": next_step,
        "source_refs": sorted(
            {event_id, *(str(item) for item in source_refs if str(item))}
        ),
    }


def _project_event(
    event: Mapping[str, Any],
    evidence: Mapping[str, Any] | None,
    *,
    event_input_content_id: str,
    perspective: str,
    as_of: str,
    knowledge_cutoff: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    event_id = str(event["event_id"])
    refs = list(event["source_refs"])
    effective_at = str(event["occurred_at"])
    effective_dt = _as_datetime(effective_at)
    as_of_dt = _as_datetime(as_of)
    cutoff_dt = _as_datetime(knowledge_cutoff)
    system_value, system_refs = _valid_first_ingest(event, evidence)
    recorded_at, recorded_basis, recorded_refs = _recorded_projection(
        event,
        evidence,
        effective_at=effective_at,
    )
    base_ledger = {
        "event_id": event_id,
        "event_projection_content_id": event_input_content_id,
        "source_refs": refs,
    }
    if effective_dt > as_of_dt:
        return None, {
            **base_ledger,
            "status": "withheld",
            "reason": "effective_after_as_of",
        }

    kind = _fact_kind(event)
    if kind == "owner_action":
        user_known = _time_projection(
            effective_at, "owner_action_default", refs
        )
    elif kind == "account_fact":
        user_known = _time_projection(
            effective_at, "source_occurred_at", refs
        )
    else:
        user_known = _time_projection(None, "not_observed", [])

    withheld_evidence: list[dict[str, Any]] = []
    if (
        system_value is not None
        and _as_datetime(system_value) <= cutoff_dt
    ):
        system_observed = _time_projection(
            system_value, "ingest_observation", system_refs
        )
    else:
        system_observed = _time_projection(None, "not_observed", [])
        if system_value is not None:
            withheld_evidence.append(
                {
                    "field": "system_observed_at",
                    "status": "withheld_by_cutoff",
                    "evidence_content_id": "sha256:"
                    + _digest(
                        {
                            "event_id": event_id,
                            "value": system_value,
                            "basis": "ingest_observation",
                            "source_refs": system_refs,
                        }
                    ),
                    "source_refs": system_refs,
                }
            )

    gaps: list[dict[str, Any]] = []
    recorded_ready = False
    if recorded_at is None:
        recorded_time = _time_projection(None, "unknown", [])
        gaps.append(
            _gap(
                "RECORDED_TIME_NOT_PROVEN",
                event_id=event_id,
                source_refs=refs,
            )
        )
        recorded_reason = "recorded_time_not_proven"
    elif _as_datetime(recorded_at) > cutoff_dt:
        recorded_time = _time_projection(None, "unknown", [])
        recorded_evidence_refs = recorded_refs or refs
        withheld_evidence.append(
            {
                "field": "recorded_at",
                "status": "withheld_by_cutoff",
                "evidence_content_id": "sha256:"
                + _digest(
                    {
                        "event_id": event_id,
                        "value": recorded_at,
                        "basis": recorded_basis,
                        "source_refs": recorded_evidence_refs,
                    }
                ),
                "source_refs": recorded_evidence_refs,
            }
        )
        gaps.append(
            _gap(
                "RECORDED_TIME_WITHHELD_BY_CUTOFF",
                event_id=event_id,
                source_refs=recorded_evidence_refs,
            )
        )
        recorded_reason = "recorded_after_knowledge_cutoff"
    else:
        recorded_time = _time_projection(
            recorded_at, recorded_basis, recorded_refs
        )
        recorded_ready = True
        recorded_reason = None

    time_provenance = {
        "effective_at": _time_projection(
            effective_at, "source_occurred_at", refs
        ),
        "user_known_at": user_known,
        "system_observed_at": system_observed,
        "recorded_at": recorded_time,
    }
    selected_field = (
        "user_known_at" if perspective == "user" else "system_observed_at"
    )
    selected = time_provenance[selected_field]
    selected_value = selected["value"]
    if (
        recorded_ready
        and
        selected_value is not None
        and _as_datetime(selected_value) <= cutoff_dt
    ):
        status = "visible"
        reason = "visible_at_perspective_cutoff"
        visibility_refs = list(selected["source_refs"])
    else:
        status = "withheld"
        if recorded_reason is not None:
            reason = recorded_reason
        elif perspective == "user":
            reason = "user_knowledge_not_proven"
        elif any(
            item["field"] == "system_observed_at"
            for item in withheld_evidence
        ):
            reason = "system_observation_withheld_by_cutoff"
        else:
            reason = "system_observation_not_proven"
        visibility_refs = (
            sorted(
                {
                    ref
                    for item in withheld_evidence
                    for ref in item["source_refs"]
                }
            )
            if withheld_evidence
            else refs
        )
    projected = {
        "event_id": event_id,
        "fact_domain": event["fact_domain"],
        "fact_kind": kind,
        "owner_action_default_applied": (
            user_known["basis"] == "owner_action_default"
        ),
        "time_provenance": time_provenance,
        "visibility": {
            "status": status,
            "reason": reason,
            "selected_time_field": selected_field,
            "selected_time_value": selected_value,
            "source_refs": sorted(set(visibility_refs)),
        },
        "withheld_evidence": withheld_evidence,
        "gaps": gaps,
        "source_refs": refs,
    }
    return projected, {
        **base_ledger,
        "status": status,
        "reason": reason,
    }


def build_knowledge_provenance(
    event_inputs: Iterable[Mapping[str, Any]],
    *,
    perspective: str,
    as_of: str,
    knowledge_cutoff: str,
    observation_evidence: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build one closed perspective projection from immutable source facts."""

    if perspective not in PERSPECTIVES:
        raise KnowledgeProvenanceError(
            f"unsupported knowledge perspective: {perspective!r}"
        )
    canonical_as_of = _timestamp(as_of, field="as_of")
    canonical_cutoff = _timestamp(
        knowledge_cutoff, field="knowledge_cutoff"
    )
    if _as_datetime(canonical_as_of) > _as_datetime(canonical_cutoff):
        raise KnowledgeProvenanceError(
            "as_of cannot be later than knowledge_cutoff"
        )
    event_projections, originals = _dedupe_event_inputs(event_inputs)
    input_manifest = _event_input_manifest(event_projections, originals)
    input_manifest_index = {
        str(item["event_id"]): item for item in input_manifest
    }
    event_index = {
        str(item["event_id"]): item for item in event_projections
    }
    evidence_projections, evidence_index = _dedupe_evidence(
        observation_evidence,
        event_index=event_index,
    )

    events: list[dict[str, Any]] = []
    visibility_ledger: list[dict[str, Any]] = []
    for event in event_projections:
        projected, ledger = _project_event(
            event,
            evidence_index.get(str(event["event_id"])),
            event_input_content_id=str(
                input_manifest_index[str(event["event_id"])][
                    "event_input_content_id"
                ]
            ),
            perspective=perspective,
            as_of=canonical_as_of,
            knowledge_cutoff=canonical_cutoff,
        )
        if projected is not None:
            events.append(projected)
        visibility_ledger.append(ledger)
    events.sort(key=lambda item: item["event_id"])
    visibility_ledger.sort(key=lambda item: item["event_id"])
    visible_ids = sorted(
        item["event_id"]
        for item in visibility_ledger
        if item["status"] == "visible"
    )
    withheld_ids = sorted(
        item["event_id"]
        for item in visibility_ledger
        if item["status"] == "withheld"
    )
    artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "method_version": METHOD_VERSION,
        "content_id": "",
        "perspective": perspective,
        "as_of": canonical_as_of,
        "knowledge_cutoff": canonical_cutoff,
        "source_binding": {
            "event_input_count": len(event_projections),
            "event_projection_content_id": "sha256:"
            + _digest(event_projections),
            "full_event_input_content_id": "sha256:"
            + _digest(input_manifest),
            "event_input_manifest": input_manifest,
            "observation_evidence_count": len(evidence_projections),
            "observation_evidence_content_id": "sha256:"
            + _digest(evidence_projections),
        },
        "events": events,
        "visibility_ledger": visibility_ledger,
        "visible_event_ids": visible_ids,
        "withheld_event_ids": withheld_ids,
        "governance": deepcopy(_GOVERNANCE),
    }
    artifact["content_id"] = _content_id(artifact)
    return artifact


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
        "related_refs": sorted(
            {str(item) for item in related_refs if str(item)}
        ),
    }


def _valid_content_id(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value
    return (
        text.startswith("sha256:")
        and len(text) == 71
        and all(character in "0123456789abcdef" for character in text[7:])
    )


def _valid_refs(value: object, *, allow_empty: bool = True) -> bool:
    if not isinstance(value, list):
        return False
    if not all(isinstance(item, str) and item for item in value):
        return False
    return value == sorted(set(value)) and (allow_empty or bool(value))


def _valid_event_source_refs(event_id: str, value: object) -> bool:
    if not event_id or not _valid_refs(value, allow_empty=False):
        return False
    refs = list(value)
    source_refs = [
        item
        for item in refs
        if item.startswith("source:")
        and not item.startswith("source_record:")
    ]
    source_record_refs = [
        item for item in refs if item.startswith("source_record:")
    ]
    payload_refs = [
        item for item in refs if item.startswith("payload_sha256:")
    ]
    if (
        event_id not in refs
        or len(source_refs) != 1
        or len(source_record_refs) > 1
        or len(payload_refs) != 1
    ):
        return False
    source_id = source_refs[0][len("source:") :]
    payload_sha256 = payload_refs[0][len("payload_sha256:") :]
    if (
        not source_id
        or len(payload_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in payload_sha256
        )
        or (
            source_record_refs
            and not source_record_refs[0].startswith(
                f"source_record:{source_id}:"
            )
        )
    ):
        return False
    expected_count = 4 if source_record_refs else 3
    return len(refs) == expected_count


def _validate_time_projection(
    value: object,
    *,
    field: str,
    cutoff: datetime,
    findings: list[dict[str, Any]],
    event_id: str,
) -> None:
    if not isinstance(value, Mapping) or set(value) != _TIME_PROJECTION_FIELDS:
        findings.append(
            _finding(
                "MALFORMED_TIME_PROJECTION",
                f"{field} projection is not closed",
                related_refs=[event_id],
            )
        )
        return
    raw_value = value.get("value")
    basis = value.get("basis")
    refs = value.get("source_refs")
    bases = {
        "effective_at": _EFFECTIVE_BASES,
        "user_known_at": _USER_BASES,
        "system_observed_at": _SYSTEM_BASES,
        "recorded_at": _RECORDED_BASES,
    }[field]
    if (
        not isinstance(basis, str)
        or basis not in bases
        or not _valid_refs(refs)
    ):
        findings.append(
            _finding(
                "INVALID_TIME_PROJECTION_BASIS_OR_REFS",
                f"{field} basis or source refs are invalid",
                related_refs=[event_id],
            )
        )
    if raw_value is None:
        valid_null = (
            (
                field in {"user_known_at", "system_observed_at"}
                and isinstance(basis, str)
                and basis in {"not_observed", "unknown"}
            )
            or (
                field == "recorded_at"
                and isinstance(basis, str)
                and basis == "unknown"
            )
        )
        if not valid_null or refs:
            findings.append(
                _finding(
                    "INVALID_NULL_TIME_PROJECTION",
                    f"{field} cannot use this null projection",
                    related_refs=[event_id],
                )
            )
        return
    try:
        canonical = _timestamp(raw_value, field=f"{event_id}.{field}")
    except KnowledgeProvenanceError:
        canonical = None
    if (
        canonical != raw_value
        or (
            isinstance(basis, str)
            and basis in {"not_observed", "unknown"}
        )
        or not refs
        or (
            canonical is not None
            and _as_datetime(canonical) > cutoff
        )
    ):
        findings.append(
            _finding(
                "INVALID_TIME_PROJECTION_VALUE",
                f"{field} value is non-canonical, future, or unsupported",
                related_refs=[event_id],
            )
        )


def validate_knowledge_provenance(artifact: object) -> dict[str, Any]:
    """Validate closed shape, time semantics, and canonical identity."""

    findings: list[dict[str, Any]] = []
    if not isinstance(artifact, Mapping):
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "validation_status": "blocked",
            "findings": [
                _finding(
                    "MALFORMED_KNOWLEDGE_PROVENANCE",
                    "knowledge provenance must be a mapping",
                )
            ],
        }
    if set(artifact) != _ROOT_FIELDS:
        findings.append(
            _finding(
                "MALFORMED_KNOWLEDGE_PROVENANCE_SHAPE",
                "knowledge provenance root field set is not closed",
            )
        )
    if artifact.get("schema_version") != SCHEMA_VERSION:
        findings.append(
            _finding(
                "UNSUPPORTED_KNOWLEDGE_PROVENANCE_SCHEMA",
                "schema_version is unsupported",
            )
        )
    if artifact.get("method_version") != METHOD_VERSION:
        findings.append(
            _finding(
                "UNSUPPORTED_KNOWLEDGE_PROVENANCE_METHOD",
                "method_version is unsupported",
            )
        )
    if (
        not isinstance(artifact.get("perspective"), str)
        or artifact.get("perspective") not in PERSPECTIVES
    ):
        findings.append(
            _finding("INVALID_PERSPECTIVE", "perspective is unsupported")
        )
    try:
        _assert_strict_json(dict(artifact))
        expected_content_id = _content_id(artifact)
    except (
        KnowledgeProvenanceError,
        OverflowError,
        TypeError,
        UnicodeError,
        ValueError,
    ) as exc:
        expected_content_id = None
        findings.append(
            _finding("NON_CANONICAL_VALUE", str(exc))
        )
    if (
        not _valid_content_id(artifact.get("content_id"))
        or artifact.get("content_id") != expected_content_id
    ):
        findings.append(
            _finding(
                "KNOWLEDGE_PROVENANCE_CONTENT_ID_MISMATCH",
                "content_id does not bind the canonical artifact",
            )
        )
    try:
        as_of = _timestamp(artifact.get("as_of"), field="as_of")
        cutoff = _timestamp(
            artifact.get("knowledge_cutoff"),
            field="knowledge_cutoff",
        )
        if as_of != artifact.get("as_of") or cutoff != artifact.get(
            "knowledge_cutoff"
        ):
            raise KnowledgeProvenanceError("root times are not canonical UTC")
        if _as_datetime(as_of) > _as_datetime(cutoff):
            raise KnowledgeProvenanceError(
                "as_of cannot exceed knowledge_cutoff"
            )
        cutoff_dt = _as_datetime(cutoff)
        as_of_dt = _as_datetime(as_of)
    except KnowledgeProvenanceError as exc:
        findings.append(_finding("INVALID_ROOT_TIME", str(exc)))
        cutoff_dt = datetime.max.replace(tzinfo=timezone.utc)
        as_of_dt = cutoff_dt

    source_binding = artifact.get("source_binding")
    source_binding_malformed = (
        not isinstance(source_binding, Mapping)
        or set(source_binding) != _SOURCE_BINDING_FIELDS
        or not isinstance(source_binding.get("event_input_count"), int)
        or isinstance(source_binding.get("event_input_count"), bool)
        or int(source_binding.get("event_input_count") or 0) < 0
        or not isinstance(
            source_binding.get("observation_evidence_count"), int
        )
        or isinstance(
            source_binding.get("observation_evidence_count"), bool
        )
        or int(source_binding.get("observation_evidence_count") or 0) < 0
        or not _valid_content_id(
            source_binding.get("event_projection_content_id")
        )
        or not _valid_content_id(
            source_binding.get("full_event_input_content_id")
        )
        or not _valid_content_id(
            source_binding.get("observation_evidence_content_id")
        )
        or not isinstance(source_binding.get("event_input_manifest"), list)
    )
    if source_binding_malformed:
        findings.append(
            _finding(
                "MALFORMED_SOURCE_BINDING",
                "source binding is incomplete or malformed",
            )
        )

    manifest = (
        source_binding.get("event_input_manifest")
        if isinstance(source_binding, Mapping)
        and isinstance(source_binding.get("event_input_manifest"), list)
        else []
    )
    manifest_ids: list[str] = []
    manifest_index: dict[str, Mapping[str, Any]] = {}
    for item in manifest:
        item_valid = (
            isinstance(item, Mapping)
            and set(item) == _INPUT_MANIFEST_FIELDS
            and isinstance(item.get("event_id"), str)
            and bool(item.get("event_id"))
            and _valid_content_id(item.get("event_input_content_id"))
            and _valid_event_source_refs(
                str(item.get("event_id") or ""),
                item.get("source_refs"),
            )
        )
        event_id = (
            str(item.get("event_id") or "")
            if isinstance(item, Mapping)
            else ""
        )
        if item_valid:
            try:
                effective_at = _timestamp(
                    item.get("effective_at"),
                    field=f"{event_id}.manifest.effective_at",
                )
                item_valid = effective_at == item.get("effective_at")
            except KnowledgeProvenanceError:
                item_valid = False
        if not item_valid:
            findings.append(
                _finding(
                    "MALFORMED_EVENT_INPUT_MANIFEST_ENTRY",
                    "event input manifest entry is malformed",
                    related_refs=[event_id],
                )
            )
            continue
        manifest_ids.append(event_id)
        manifest_index[event_id] = item
    if manifest_ids != sorted(set(manifest_ids)):
        findings.append(
            _finding(
                "EVENT_INPUT_MANIFEST_ORDER_OR_IDENTITY_MISMATCH",
                "event input manifest must have unique sorted identities",
            )
        )
    if isinstance(source_binding, Mapping):
        event_input_count = source_binding.get("event_input_count")
        evidence_count = source_binding.get("observation_evidence_count")
        empty_content_id = "sha256:" + _digest([])
        try:
            manifest_content_id = "sha256:" + _digest(manifest)
        except KnowledgeProvenanceError:
            manifest_content_id = None
        if (
            source_binding.get("full_event_input_content_id")
            != manifest_content_id
        ):
            findings.append(
                _finding(
                    "FULL_EVENT_INPUT_BINDING_MISMATCH",
                    "full event input identity does not bind the manifest",
                )
            )
        if (
            isinstance(event_input_count, int)
            and not isinstance(event_input_count, bool)
            and isinstance(evidence_count, int)
            and not isinstance(evidence_count, bool)
            and evidence_count > event_input_count
        ):
            findings.append(
                _finding(
                    "OBSERVATION_EVIDENCE_COUNT_MISMATCH",
                    "observation evidence cannot exceed source events",
                )
            )
        if (
            event_input_count == 0
            and source_binding.get("event_projection_content_id")
            != empty_content_id
        ) or (
            isinstance(event_input_count, int)
            and not isinstance(event_input_count, bool)
            and event_input_count > 0
            and source_binding.get("event_projection_content_id")
            == empty_content_id
        ):
            findings.append(
                _finding(
                    "EVENT_PROJECTION_BINDING_CARDINALITY_MISMATCH",
                    "event projection identity conflicts with source count",
                )
            )
        if (
            evidence_count == 0
            and source_binding.get("observation_evidence_content_id")
            != empty_content_id
        ) or (
            isinstance(evidence_count, int)
            and not isinstance(evidence_count, bool)
            and evidence_count > 0
            and source_binding.get("observation_evidence_content_id")
            == empty_content_id
        ):
            findings.append(
                _finding(
                    "OBSERVATION_BINDING_CARDINALITY_MISMATCH",
                    "observation identity conflicts with evidence count",
                )
            )

    events = artifact.get("events")
    ledger = artifact.get("visibility_ledger")
    if not isinstance(events, list):
        findings.append(_finding("MALFORMED_EVENTS", "events must be a list"))
        events = []
    if not isinstance(ledger, list):
        findings.append(
            _finding(
                "MALFORMED_VISIBILITY_LEDGER",
                "visibility_ledger must be a list",
            )
        )
        ledger = []
    event_ids: list[str] = []
    event_visibility: dict[str, str] = {}
    event_reasons: dict[str, str] = {}
    event_refs: dict[str, list[str]] = {}
    for event in events:
        if not isinstance(event, Mapping) or set(event) != _EVENT_FIELDS:
            findings.append(
                _finding(
                    "MALFORMED_EVENT_PROJECTION",
                    "event projection is not closed",
                )
            )
            continue
        event_id = (
            event.get("event_id")
            if isinstance(event.get("event_id"), str)
            else ""
        )
        event_ids.append(event_id)
        refs = event.get("source_refs")
        if not _valid_event_source_refs(event_id, refs):
            findings.append(
                _finding(
                    "INVALID_EVENT_ID_OR_REFS",
                    "event identity or source refs are invalid",
                    related_refs=[event_id],
                )
            )
        else:
            event_refs[event_id] = list(refs)
        domain = event.get("fact_domain")
        kind = event.get("fact_kind")
        owner_applied = event.get("owner_action_default_applied")
        classification_valid = (
            not isinstance(domain, str)
            or domain not in {"account", "market"}
            or not isinstance(kind, str)
            or kind not in {"owner_action", "account_fact", "market_fact"}
            or not isinstance(owner_applied, bool)
            or (
                domain == "market"
                and (kind != "market_fact" or owner_applied)
            )
            or (
                domain == "account"
                and isinstance(kind, str)
                and kind not in {"owner_action", "account_fact"}
            )
            or (kind == "owner_action" and not owner_applied)
            or (kind != "owner_action" and owner_applied)
        )
        if classification_valid:
            findings.append(
                _finding(
                    "INVALID_FACT_CLASSIFICATION",
                    "fact domain/kind or owner default is invalid",
                    related_refs=[event_id],
                )
            )
        times = event.get("time_provenance")
        if not isinstance(times, Mapping) or set(times) != _TIME_FIELDS:
            findings.append(
                _finding(
                    "MALFORMED_TIME_PROVENANCE",
                    "time_provenance is not closed",
                    related_refs=[event_id],
                )
            )
            continue
        for field in sorted(_TIME_FIELDS):
            _validate_time_projection(
                times.get(field),
                field=field,
                cutoff=cutoff_dt,
                findings=findings,
                event_id=event_id,
            )
        projections_closed = all(
            isinstance(times.get(field), Mapping)
            and set(times.get(field)) == _TIME_PROJECTION_FIELDS
            for field in _TIME_FIELDS
        )
        if not projections_closed:
            continue
        effective_value = times["effective_at"].get("value")
        user_value = times["user_known_at"].get("value")
        system_value = times["system_observed_at"].get("value")
        recorded_value = times["recorded_at"].get("value")
        parsed_times: dict[str, datetime | None] = {}
        for field, raw_value in (
            ("effective_at", effective_value),
            ("user_known_at", user_value),
            ("system_observed_at", system_value),
            ("recorded_at", recorded_value),
        ):
            try:
                parsed_times[field] = (
                    _as_datetime(str(raw_value))
                    if raw_value is not None
                    else None
                )
            except (TypeError, ValueError):
                parsed_times[field] = None
        effective_dt = parsed_times["effective_at"]
        time_order_invalid = (
            effective_dt is None
            or effective_dt > as_of_dt
            or any(
                value is not None and value < effective_dt
                for field, value in parsed_times.items()
                if field != "effective_at"
            )
        )
        if time_order_invalid:
            findings.append(
                _finding(
                    "INVALID_EVENT_TIME_ORDER",
                    "event times violate effective/as-of/knowledge order",
                    related_refs=[event_id],
                )
            )
        effective_projection = times["effective_at"]
        if (
            effective_projection.get("basis") != "source_occurred_at"
            or effective_projection.get("value") is None
            or effective_projection.get("source_refs") != refs
        ):
            findings.append(
                _finding(
                    "EFFECTIVE_TIME_POLICY_MISMATCH",
                    "effective time must bind the source occurrence",
                    related_refs=[event_id],
                )
            )
        manifest_item = manifest_index.get(event_id)
        if (
            manifest_item is None
            or manifest_item.get("effective_at") != effective_value
            or manifest_item.get("source_refs") != refs
        ):
            findings.append(
                _finding(
                    "EVENT_MANIFEST_BINDING_MISMATCH",
                    "event projection does not match its input manifest",
                    related_refs=[event_id],
                )
            )

        user_projection = times["user_known_at"]
        user_basis = times["user_known_at"].get("basis")
        if kind == "owner_action":
            user_policy_valid = (
                owner_applied is True
                and user_basis == "owner_action_default"
                and user_value == effective_value
                and user_projection.get("source_refs") == refs
            )
        elif kind == "account_fact":
            user_policy_valid = (
                owner_applied is False
                and user_basis == "source_occurred_at"
                and user_value == effective_value
                and user_projection.get("source_refs") == refs
            )
        elif kind == "market_fact":
            user_policy_valid = (
                owner_applied is False
                and user_basis == "not_observed"
                and user_value is None
                and user_projection.get("source_refs") == []
            )
        else:
            user_policy_valid = False
        if not user_policy_valid:
            findings.append(
                _finding(
                    "OWNER_ACTION_POLICY_MISMATCH",
                    "user-known basis violates the account-only owner policy",
                    related_refs=[event_id],
                )
            )

        system_projection = times["system_observed_at"]
        if system_value is None:
            system_policy_valid = (
                system_projection.get("basis") == "not_observed"
                and system_projection.get("source_refs") == []
            )
        else:
            system_policy_valid = (
                system_projection.get("basis") == "ingest_observation"
                and _valid_refs(
                    system_projection.get("source_refs"),
                    allow_empty=False,
                )
                and event_id in system_projection.get("source_refs", [])
            )
        if not system_policy_valid:
            findings.append(
                _finding(
                    "SYSTEM_OBSERVATION_POLICY_MISMATCH",
                    "system observation does not bind first-ingest evidence",
                    related_refs=[event_id],
                )
            )

        recorded_projection = times["recorded_at"]
        if recorded_value is None:
            recorded_policy_valid = (
                recorded_projection.get("basis") == "unknown"
                and recorded_projection.get("source_refs") == []
            )
        else:
            recorded_policy_valid = (
                recorded_projection.get("basis")
                in {"recorded_later", "ingest_observation"}
                and _valid_refs(
                    recorded_projection.get("source_refs"),
                    allow_empty=False,
                )
                and event_id in recorded_projection.get("source_refs", [])
            )
        if not recorded_policy_valid:
            findings.append(
                _finding(
                    "RECORDED_TIME_POLICY_MISMATCH",
                    "recorded time basis or evidence binding is invalid",
                    related_refs=[event_id],
                )
            )

        withheld = event.get("withheld_evidence")
        withheld_by_field: dict[str, Mapping[str, Any]] = {}
        if not isinstance(withheld, list):
            findings.append(
                _finding(
                    "MALFORMED_WITHHELD_EVIDENCE",
                    "withheld_evidence must be a list",
                    related_refs=[event_id],
                )
            )
        else:
            for item in withheld:
                item_valid = (
                    isinstance(item, Mapping)
                    and set(item) == _WITHHELD_EVIDENCE_FIELDS
                    and isinstance(item.get("field"), str)
                    and item.get("field")
                    in {"system_observed_at", "recorded_at"}
                    and item.get("status") == "withheld_by_cutoff"
                    and _valid_content_id(item.get("evidence_content_id"))
                    and _valid_refs(
                        item.get("source_refs"), allow_empty=False
                    )
                    and event_id in item.get("source_refs", [])
                    and item.get("field") not in withheld_by_field
                )
                if not item_valid:
                    findings.append(
                        _finding(
                            "INVALID_WITHHELD_EVIDENCE",
                            "withheld evidence is malformed",
                            related_refs=[event_id],
                        )
                    )
                else:
                    withheld_by_field[str(item["field"])] = item
        if (
            system_value is not None
            and "system_observed_at" in withheld_by_field
        ) or (
            recorded_value is not None
            and "recorded_at" in withheld_by_field
        ):
            findings.append(
                _finding(
                    "WITHHELD_EVIDENCE_TIME_MISMATCH",
                    "withheld evidence conflicts with a visible time value",
                    related_refs=[event_id],
                )
            )

        gaps = event.get("gaps")
        gap_codes: list[str] = []
        if not isinstance(gaps, list):
            findings.append(
                _finding(
                    "MALFORMED_KNOWLEDGE_GAPS",
                    "knowledge gaps must be a list",
                    related_refs=[event_id],
                )
            )
            gaps = []
        for gap in gaps:
            gap_valid = (
                isinstance(gap, Mapping)
                and set(gap) == _GAP_FIELDS
                and isinstance(gap.get("code"), str)
                and gap.get("code") in _GAP_DETAILS
                and isinstance(gap.get("next_step"), str)
                and bool(gap.get("next_step"))
                and _valid_refs(gap.get("source_refs"), allow_empty=False)
                and event_id in gap.get("source_refs", [])
            )
            if gap_valid:
                severity, owner, next_step = _GAP_DETAILS[str(gap["code"])]
                gap_valid = (
                    gap.get("severity") == severity
                    and gap.get("owner") == owner
                    and gap.get("next_step") == next_step
                )
            if not gap_valid:
                findings.append(
                    _finding(
                        "INVALID_KNOWLEDGE_GAP",
                        "knowledge gap is malformed or open-ended",
                        related_refs=[event_id],
                    )
                )
            else:
                gap_codes.append(str(gap["code"]))
        if gap_codes != sorted(set(gap_codes)):
            findings.append(
                _finding(
                    "KNOWLEDGE_GAP_ORDER_OR_IDENTITY_MISMATCH",
                    "knowledge gaps must have unique sorted codes",
                    related_refs=[event_id],
                )
            )
        expected_gap_codes = (
            [
                "RECORDED_TIME_WITHHELD_BY_CUTOFF"
                if "recorded_at" in withheld_by_field
                else "RECORDED_TIME_NOT_PROVEN"
            ]
            if recorded_value is None
            else []
        )
        if gap_codes != expected_gap_codes:
            findings.append(
                _finding(
                    "RECORDED_GAP_DERIVATION_MISMATCH",
                    "recorded-time gaps do not match available evidence",
                    related_refs=[event_id],
                )
            )

        visibility = event.get("visibility")
        if (
            not isinstance(visibility, Mapping)
            or set(visibility) != _VISIBILITY_FIELDS
            or not isinstance(visibility.get("status"), str)
            or visibility.get("status") not in {"visible", "withheld"}
            or not isinstance(visibility.get("reason"), str)
            or visibility.get("reason") not in _VISIBILITY_REASONS
            or visibility.get("selected_time_field")
            != (
                "user_known_at"
                if artifact.get("perspective") == "user"
                else "system_observed_at"
            )
            or not _valid_refs(visibility.get("source_refs"))
        ):
            findings.append(
                _finding(
                    "MALFORMED_VISIBILITY",
                    "event visibility is malformed",
                    related_refs=[event_id],
                )
            )
        else:
            selected = times[visibility["selected_time_field"]]
            try:
                expected_visible = (
                    selected.get("value") is not None
                    and _as_datetime(str(selected["value"])) <= cutoff_dt
                    and recorded_value is not None
                    and _as_datetime(str(recorded_value)) <= cutoff_dt
                )
            except (TypeError, ValueError):
                expected_visible = False
            if expected_visible:
                expected_reason = "visible_at_perspective_cutoff"
                expected_visibility_refs = selected.get("source_refs")
            elif recorded_value is None:
                expected_reason = (
                    "recorded_after_knowledge_cutoff"
                    if "recorded_at" in withheld_by_field
                    else "recorded_time_not_proven"
                )
                expected_visibility_refs = (
                    sorted(
                        {
                            ref
                            for item in withheld_by_field.values()
                            for ref in item.get("source_refs", [])
                        }
                    )
                    if withheld_by_field
                    else refs
                )
            elif artifact.get("perspective") == "user":
                expected_reason = "user_knowledge_not_proven"
                expected_visibility_refs = (
                    sorted(
                        {
                            ref
                            for item in withheld_by_field.values()
                            for ref in item.get("source_refs", [])
                        }
                    )
                    if withheld_by_field
                    else refs
                )
            elif "system_observed_at" in withheld_by_field:
                expected_reason = "system_observation_withheld_by_cutoff"
                expected_visibility_refs = sorted(
                    {
                        ref
                        for item in withheld_by_field.values()
                        for ref in item.get("source_refs", [])
                    }
                )
            else:
                expected_reason = "system_observation_not_proven"
                expected_visibility_refs = refs
            if (
                visibility.get("selected_time_value")
                != selected.get("value")
                or (visibility.get("status") == "visible")
                != expected_visible
                or visibility.get("reason") != expected_reason
                or visibility.get("source_refs") != expected_visibility_refs
            ):
                findings.append(
                    _finding(
                        "VISIBILITY_DERIVATION_MISMATCH",
                        "visibility does not match selected perspective time",
                        related_refs=[event_id],
                    )
                )
            event_visibility[event_id] = str(
                visibility.get("status") or ""
            )
            event_reasons[event_id] = str(visibility.get("reason") or "")

    ledger_ids: list[str] = []
    ledger_visibility: dict[str, str] = {}
    ledger_reasons: dict[str, str] = {}
    for item in ledger:
        item_valid = (
            not isinstance(item, Mapping)
            or set(item) != _LEDGER_FIELDS
            or not isinstance(item.get("status"), str)
            or item.get("status") not in {"visible", "withheld"}
            or not isinstance(item.get("reason"), str)
            or item.get("reason") not in _LEDGER_REASONS
            or not _valid_content_id(
                item.get("event_projection_content_id")
            )
            or not isinstance(item.get("event_id"), str)
            or not item.get("event_id")
            or not _valid_event_source_refs(
                str(item.get("event_id") or ""),
                item.get("source_refs"),
            )
            or (
                item.get("status") == "visible"
                and item.get("reason") != "visible_at_perspective_cutoff"
            )
            or (
                item.get("status") == "withheld"
                and item.get("reason") == "visible_at_perspective_cutoff"
            )
        )
        if item_valid:
            findings.append(
                _finding(
                    "MALFORMED_VISIBILITY_LEDGER_ENTRY",
                    "visibility ledger entry is malformed",
                )
            )
            continue
        event_id = str(item["event_id"])
        ledger_ids.append(event_id)
        ledger_visibility[event_id] = str(item["status"])
        ledger_reasons[event_id] = str(item["reason"])
        manifest_item = manifest_index.get(event_id)
        if (
            manifest_item is None
            or item.get("event_projection_content_id")
            != manifest_item.get("event_input_content_id")
            or item.get("source_refs") != manifest_item.get("source_refs")
        ):
            findings.append(
                _finding(
                    "LEDGER_MANIFEST_BINDING_MISMATCH",
                    "visibility ledger does not bind its full event input",
                    related_refs=[event_id],
                )
            )
        if manifest_item is not None:
            try:
                effective_after_as_of = _as_datetime(
                    str(manifest_item["effective_at"])
                ) > as_of_dt
            except (KeyError, TypeError, ValueError):
                effective_after_as_of = False
            if (
                item.get("reason") == "effective_after_as_of"
            ) != effective_after_as_of:
                findings.append(
                    _finding(
                        "LEDGER_AS_OF_DERIVATION_MISMATCH",
                        "ledger as-of withholding does not match effective time",
                        related_refs=[event_id],
                    )
                )
    if event_ids != sorted(set(event_ids)):
        findings.append(
            _finding(
                "EVENT_ORDER_OR_IDENTITY_MISMATCH",
                "events must have unique sorted identities",
            )
        )
    if ledger_ids != sorted(set(ledger_ids)):
        findings.append(
            _finding(
                "LEDGER_ORDER_OR_IDENTITY_MISMATCH",
                "visibility ledger must have unique sorted identities",
            )
        )
    if isinstance(source_binding, Mapping):
        event_input_count = source_binding.get("event_input_count")
        if (
            isinstance(event_input_count, int)
            and not isinstance(event_input_count, bool)
            and (
                event_input_count != len(ledger_ids)
                or event_input_count != len(manifest_ids)
            )
        ):
            findings.append(
                _finding(
                    "SOURCE_BINDING_EVENT_COUNT_MISMATCH",
                    "source event count does not match manifest and ledger",
                )
            )
    if manifest_ids != ledger_ids:
        findings.append(
            _finding(
                "MANIFEST_LEDGER_MEMBERSHIP_MISMATCH",
                "manifest and visibility ledger identities must match",
            )
        )
    expected_event_ids: list[str] = []
    for event_id in manifest_ids:
        try:
            if _as_datetime(
                str(manifest_index[event_id]["effective_at"])
            ) <= as_of_dt:
                expected_event_ids.append(event_id)
        except (KeyError, TypeError, ValueError):
            continue
    if event_ids != expected_event_ids:
        findings.append(
            _finding(
                "EVENT_LEDGER_MEMBERSHIP_MISMATCH",
                "events must equal cutoff-eligible manifest identities",
            )
        )
    for event_id, status in event_visibility.items():
        if (
            ledger_visibility.get(event_id) != status
            or ledger_reasons.get(event_id) != event_reasons.get(event_id)
            or (
                event_id in event_refs
                and event_refs[event_id]
                != manifest_index.get(event_id, {}).get("source_refs")
            )
        ):
            findings.append(
                _finding(
                    "EVENT_LEDGER_VISIBILITY_MISMATCH",
                    "event and visibility ledger semantics disagree",
                    related_refs=[event_id],
                )
            )
    expected_visible = sorted(
        event_id
        for event_id, status in ledger_visibility.items()
        if status == "visible"
    )
    expected_withheld = sorted(
        event_id
        for event_id, status in ledger_visibility.items()
        if status == "withheld"
    )
    if (
        artifact.get("visible_event_ids") != expected_visible
        or artifact.get("withheld_event_ids") != expected_withheld
        or set(expected_visible).intersection(expected_withheld)
        or sorted(expected_visible + expected_withheld) != ledger_ids
    ):
        findings.append(
            _finding(
                "VISIBILITY_INDEX_MISMATCH",
                "visible/withheld indexes do not match the ledger",
            )
        )
    if artifact.get("governance") != _GOVERNANCE:
        findings.append(
            _finding(
                "INVALID_KNOWLEDGE_GOVERNANCE",
                "knowledge provenance governance is not closed",
            )
        )
    unique = {
        json.dumps(
            item,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ): item
        for item in findings
    }
    ordered = sorted(
        unique.values(),
        key=lambda item: (
            str(item.get("code") or ""),
            json.dumps(item.get("related_refs") or [], ensure_ascii=True),
        ),
    )
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "validation_status": "accepted" if not ordered else "blocked",
        "findings": ordered,
    }


def project_perspective_event_inputs(
    artifact: Mapping[str, Any],
    event_inputs: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return unchanged legacy events selected by the validated perspective."""

    validation = validate_knowledge_provenance(artifact)
    if validation["validation_status"] != "accepted":
        raise KnowledgeProvenanceError(
            "knowledge provenance validation blocked"
        )
    projections, originals = _dedupe_event_inputs(event_inputs)
    binding = artifact["source_binding"]
    input_manifest = _event_input_manifest(projections, originals)
    if (
        binding["event_input_count"] != len(projections)
        or binding["event_projection_content_id"]
        != "sha256:" + _digest(projections)
        or binding["full_event_input_content_id"]
        != "sha256:" + _digest(input_manifest)
        or binding["event_input_manifest"] != input_manifest
    ):
        raise KnowledgeProvenanceError(
            "event inputs do not match the knowledge source binding"
        )
    visible_ids = list(artifact["visible_event_ids"])
    if any(event_id not in originals for event_id in visible_ids):
        raise KnowledgeProvenanceError(
            "visible event identity is absent from source inputs"
        )
    return [deepcopy(originals[event_id]) for event_id in visible_ids]


def replay_validate_knowledge_provenance(
    artifact: object,
    *,
    event_inputs: Iterable[Mapping[str, Any]],
    observation_evidence: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Rebuild from frozen evidence and require byte-identical output."""

    validation = validate_knowledge_provenance(artifact)
    findings = list(validation["findings"])
    rebuilt: dict[str, Any] | None = None
    if isinstance(artifact, Mapping):
        try:
            rebuilt = build_knowledge_provenance(
                event_inputs,
                perspective=str(artifact.get("perspective") or ""),
                as_of=str(artifact.get("as_of") or ""),
                knowledge_cutoff=str(
                    artifact.get("knowledge_cutoff") or ""
                ),
                observation_evidence=observation_evidence,
            )
        except Exception as exc:
            findings.append(
                _finding(
                    "KNOWLEDGE_PROVENANCE_REBUILD_FAILED",
                    "knowledge provenance rebuild failed: "
                    + type(exc).__name__,
                )
            )
    if rebuilt is not None:
        try:
            matches = canonical_knowledge_provenance_bytes(
                rebuilt
            ) == canonical_knowledge_provenance_bytes(artifact)
        except Exception:
            matches = False
        if not matches:
            findings.append(
                _finding(
                    "KNOWLEDGE_PROVENANCE_SOURCE_REPLAY_MISMATCH",
                    "rebuilt knowledge provenance is not byte-identical",
                )
            )
    unique = {
        json.dumps(
            item,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ): item
        for item in findings
    }
    ordered = sorted(
        unique.values(), key=lambda item: str(item.get("code") or "")
    )
    verified = not ordered
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
        "findings": ordered,
    }


__all__ = [
    "METHOD_VERSION",
    "PERSPECTIVES",
    "REPLAY_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "VALIDATION_SCHEMA_VERSION",
    "KnowledgeProvenanceError",
    "build_knowledge_provenance",
    "canonical_knowledge_provenance_bytes",
    "project_perspective_event_inputs",
    "replay_validate_knowledge_provenance",
    "validate_knowledge_provenance",
]
