"""Deterministic, decision-optional operation review projection.

The projection is deliberately parallel to the frozen P2C/P2F artifacts.  It
uses P2C's validated quantity transitions as the authority for position
operations and only the explicit canonical event projection for standalone
cash events.  It never derives a thesis, motive, recommendation, or Decision.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, DecimalException, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence

from .episodes import COLLECTION_SCHEMA_VERSION, validate_episode_collection
from .models import canonical_json


SCHEMA_VERSION = "investment_review.operation_review.v1"
METHOD_VERSION = "quantity_transition_explicit_event_v1"
VALIDATION_SCHEMA_VERSION = "investment_review.operation_review.validation.v1"
REPLAY_SCHEMA_VERSION = "investment_review.operation_review.replay.v1"

_ROOT_FIELDS = {
    "schema_version",
    "method_version",
    "content_id",
    "source_binding",
    "summary",
    "episode_reviews",
    "standalone_operations",
    "governance",
}
_SOURCE_BINDING_FIELDS = {
    "episode_collection_schema_version",
    "episode_collection_content_id",
    "event_projection_content_id",
    "event_projection_count",
    "episode_collection_integrity_status",
    "episode_collection_validation_status",
    "episode_collection_blocker_codes",
}
_EPISODE_REVIEW_FIELDS = {
    "episode_id",
    "episode_status",
    "scope",
    "operation_review_status",
    "decision_context_status",
    "operations",
    "reason_codes",
}
_OPERATION_FIELDS = {
    "operation_id",
    "sequence_index",
    "episode_id",
    "event_id",
    "event_type",
    "effective_at",
    "side",
    "quantity_applicability",
    "qty_before",
    "qty_after",
    "signed_quantity",
    "operation_type",
    "classification_status",
    "method_version",
    "decision_context_status",
    "cash_amount",
    "cash_amount_status",
    "source_refs",
    "reason_codes",
}
_SOURCE_REF_FIELDS = {
    "source_id",
    "source_record_id",
    "payload_sha256",
    "source_keys",
}
_GOVERNANCE = {
    "facts_only": True,
    "decision_optional": True,
    "historical_decisions_inferred": False,
    "motive_inferred": False,
    "advice_generated": False,
    "model_called": False,
    "quantity_authority": "validated_p2c_event_transitions",
    "cash_authority": "explicit_event_inputs_only",
}
_POSITION_TYPES = {
    "position_open",
    "position_increase",
    "position_reduce",
    "position_close",
    "position_reversal",
    "position_anomaly",
    "special_quantity_adjustment",
}
_CASH_TYPES = {"cash_dividend", "cash_fee", "cash_event"}
_CLASSIFICATION_STATUSES = {"ready", "ambiguous", "blocked"}
_OPERATION_REVIEW_STATUSES = {"ready", "partial", "blocked"}
_DECISION_CONTEXT_STATUSES = {
    "complete",
    "partial",
    "not_recorded",
    "not_applicable",
    "blocked",
}
_SPECIAL_EVENT_TYPES = {
    "opening",
    "transfer",
    "corporate_action",
    "correction",
}
_NORMAL_POSITION_EVENT_TYPES = {"fill", "buy", "sell"}
_CASH_EVENT_TYPES = {"dividend", "cash_fee"}
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_EPISODE_ID = re.compile(r"^te_[0-9a-f]{32}$")
_MAX_DECIMAL_DIGITS = 1000
_MAX_DECIMAL_ADJUSTED_EXPONENT = 1000
_SCOPE_FIELDS = {
    "account_id",
    "instrument_id",
    "symbol",
    "market",
    "currency",
}
_ALLOWED_SOURCE_BLOCKERS = {
    "DECISION_LINK_AMBIGUOUS",
    "DECISION_LINK_INVALID",
    "FLAT_OUTFLOW_WITHOUT_OPEN_POSITION",
    "UNSPLIT_SIGN_REVERSAL",
}
_EPISODE_REASON_CODES = {
    "AMBIGUOUS_EPISODE_BOUNDARY",
    "AMBIGUOUS_OPERATION_FACT",
    "BLOCKED_OPERATION_FACT",
    "EPISODE_QUANTITY_HISTORY_INCOMPLETE",
    "NO_POSITION_OPERATION",
}
_POSITION_REASON_CODES = {
    "CONFLICTING_EVENT_INPUT",
    "EVENT_INPUT_TRANSITION_MISMATCH",
    "EVENT_INPUT_PROVENANCE_MISMATCH",
    "EVENT_TYPE_SIDE_MISMATCH",
    "INVALID_QUANTITY_TRANSITION",
    "MISSING_QUANTITY_TRANSITION",
    "NEGATIVE_POSITION_UNSUPPORTED",
    "QUANTITY_ARITHMETIC_MISMATCH",
    "SIDE_DELTA_MISMATCH",
    "SPECIAL_EVENT_REQUIRES_EXPLICIT_SEMANTICS",
    "UNCLASSIFIABLE_QUANTITY_TRANSITION",
    "UNSPLIT_SIGN_REVERSAL",
    "UNSUPPORTED_POSITION_EVENT_TYPE",
    "ZERO_DELTA_POSITION_EVENT",
}
_CASH_REASON_CODES = {
    "CASH_AMOUNT_NOT_RECORDED",
    "CONFLICTING_EVENT_INPUT",
    "INVALID_EXPLICIT_CASH_EVENT",
    "MISSING_EXPLICIT_CASH_EVENT_INPUT",
}


class OperationReviewError(ValueError):
    """Raised when the source projection cannot be interpreted safely."""


def _digest(value: object) -> str:
    return hashlib.sha256(_strict_canonical_bytes(value)).hexdigest()


def _assert_strict_json(value: object, *, path: str = "$") -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, str):
        if any("\ud800" <= character <= "\udfff" for character in value):
            raise OperationReviewError(
                f"lone surrogate is forbidden in canonical artifact at {path}"
            )
        return
    if isinstance(value, int) and not isinstance(value, bool):
        return
    if isinstance(value, float):
        raise OperationReviewError(
            f"binary float is forbidden in canonical artifact at {path}"
        )
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_strict_json(item, path=f"{path}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise OperationReviewError(
                    f"non-string object key at {path}"
                )
            _assert_strict_json(item, path=f"{path}.{key}")
        return
    raise OperationReviewError(
        f"non-JSON canonical value {type(value).__name__} at {path}"
    )


def _strict_canonical_bytes(value: object) -> bytes:
    _assert_strict_json(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _content_id(value: Mapping[str, Any]) -> str:
    material = deepcopy(dict(value))
    material["content_id"] = ""
    return "sha256:" + _digest(material)


def canonical_operation_review_bytes(artifact: Mapping[str, Any]) -> bytes:
    """Return canonical bytes for deterministic comparison and source replay."""

    if not isinstance(artifact, Mapping):
        raise OperationReviewError("operation review must be a mapping")
    return _strict_canonical_bytes(dict(artifact))


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, float):
        raise OperationReviewError(
            "binary float is forbidden for operation-review decimals"
        )
    text = str(value).strip()
    if not text:
        return None
    try:
        result = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise OperationReviewError(f"invalid decimal value: {value!r}") from exc
    if not result.is_finite():
        raise OperationReviewError(f"non-finite decimal value: {value!r}")
    if (
        len(result.as_tuple().digits) > _MAX_DECIMAL_DIGITS
        or abs(result.adjusted()) > _MAX_DECIMAL_ADJUSTED_EXPONENT
    ):
        raise OperationReviewError(
            f"decimal value exceeds canonical bounds: {value!r}"
        )
    return result


def _decimal_text(value: object) -> str | None:
    number = _decimal(value)
    if number is None:
        return None
    if number == 0:
        return "0"
    try:
        return format(number.normalize(), "f")
    except DecimalException as exc:
        raise OperationReviewError(
            f"decimal value cannot be canonicalized: {value!r}"
        ) from exc


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _timestamp_text(value: object) -> str | None:
    text = _text(value)
    if text is None:
        return None
    normalized = (
        text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    )
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise OperationReviewError(
            f"invalid operation timestamp: {text!r}"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OperationReviewError(
            f"operation timestamp must be timezone-aware: {text!r}"
        )
    try:
        return parsed.astimezone(timezone.utc).isoformat()
    except (OverflowError, ValueError) as exc:
        raise OperationReviewError(
            f"operation timestamp is outside canonical UTC range: {text!r}"
        ) from exc


def _safe_source_refs(
    value: Mapping[str, Any] | None,
    *,
    event_id: str,
) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    raw_keys = source.get("source_keys")
    keys: set[str] = {event_id}
    if isinstance(raw_keys, Sequence) and not isinstance(
        raw_keys, (str, bytes, bytearray)
    ):
        keys.update(
            text
            for item in raw_keys
            if (text := _text(item)) is not None
        )
    return {
        "source_id": _text(source.get("source_id")),
        "source_record_id": _text(source.get("source_record_id")),
        "payload_sha256": _text(source.get("payload_sha256")),
        "source_keys": sorted(keys),
    }


def _event_source_refs(event: Mapping[str, Any]) -> dict[str, Any]:
    raw_payload = event.get("raw_payload")
    raw_row = (
        raw_payload.get("source_row")
        if isinstance(raw_payload, Mapping)
        and isinstance(raw_payload.get("source_row"), Mapping)
        else {}
    )
    source_keys = {
        _text(event.get("event_id")),
        _text(event.get("source_record_id")),
        _text(raw_row.get("external_id")),
        _text(raw_row.get("dedupe_key")),
    }
    account_id = _text(raw_row.get("account_id"))
    external_id = _text(raw_row.get("external_id"))
    if account_id is not None and external_id is not None:
        source_keys.add(f"{account_id}::{external_id}")
    return _safe_source_refs(
        {
            "source_id": event.get("source_id"),
            "source_record_id": event.get("source_record_id"),
            "payload_sha256": event.get("payload_sha256"),
            "source_keys": sorted(item for item in source_keys if item),
        },
        event_id=str(event.get("event_id") or ""),
    )


def _event_projection(event: Mapping[str, Any]) -> dict[str, Any]:
    """Project only facts used by this classifier; omit arbitrary free text."""

    return {
        "event_id": _text(event.get("event_id")),
        "event_type": _text(event.get("event_type")) or "fill",
        "occurred_at": _timestamp_text(
            event.get("occurred_at") or event.get("effective_at")
        ),
        "side": _text(event.get("side")),
        "quantity": _decimal_text(event.get("quantity")),
        "cash_amount": _decimal_text(event.get("cash_amount")),
        "source_refs": _event_source_refs(event),
    }


def _relevant_event_ids(collection: Mapping[str, Any]) -> set[str]:
    event_ids = {
        str(event_ref.get("event_id") or "")
        for episode in collection.get("episodes", [])
        if isinstance(episode, Mapping)
        for event_ref in episode.get("event_refs", [])
        if isinstance(event_ref, Mapping) and event_ref.get("event_id")
    }
    event_ids.update(
        str(item.get("event_id") or "")
        for item in collection.get("consumption_ledger", [])
        if isinstance(item, Mapping)
        and item.get("outcome") == "non_position_changing"
        and item.get("event_id")
    )
    return event_ids


def _validate_source_collection(
    collection: Mapping[str, Any],
) -> dict[str, Any]:
    if collection.get("schema_version") != COLLECTION_SCHEMA_VERSION:
        raise OperationReviewError(
            "episode_collection schema_version is unsupported"
        )
    try:
        validation = validate_episode_collection(collection)
    except Exception as exc:
        raise OperationReviewError(
            "episode_collection validation could not complete"
        ) from exc
    blocker_codes = sorted(
        {
            str(item.get("code") or "")
            for item in validation.get("findings", [])
            if isinstance(item, Mapping)
            and item.get("severity") == "blocker"
            and item.get("code")
        }
    )
    unsupported = sorted(set(blocker_codes) - _ALLOWED_SOURCE_BLOCKERS)
    if unsupported:
        raise OperationReviewError(
            "episode_collection integrity or unsupported source blocker: "
            + ",".join(unsupported)
        )
    if (
        validation.get("validation_status") == "blocked"
        and not blocker_codes
    ):
        raise OperationReviewError(
            "episode_collection blocked without an explicit source finding"
        )
    return {
        "validation_status": str(
            validation.get("validation_status") or "blocked"
        ),
        "blocker_codes": blocker_codes,
    }


def _event_index(
    event_inputs: Iterable[Mapping[str, Any]],
    *,
    relevant_event_ids: set[str],
) -> tuple[
    dict[str, Mapping[str, Any]],
    set[str],
    list[dict[str, Any]],
]:
    projections: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    originals: dict[tuple[str, str], Mapping[str, Any]] = {}
    for raw in event_inputs:
        if not isinstance(raw, Mapping):
            continue
        event_id = str(raw.get("event_id") or "")
        if not event_id or event_id not in relevant_event_ids:
            continue
        projection = _event_projection(raw)
        projection_key = canonical_json(projection)
        projections[event_id][projection_key] = projection
        originals[(event_id, projection_key)] = raw

    index: dict[str, Mapping[str, Any]] = {}
    conflicts: set[str] = set()
    semantic_projections: list[dict[str, Any]] = []
    for event_id in sorted(projections):
        variants = projections[event_id]
        semantic_projections.extend(
            deepcopy(variants[key]) for key in sorted(variants)
        )
        if len(variants) == 1:
            only_key = next(iter(variants))
            index[event_id] = originals[(event_id, only_key)]
        else:
            conflicts.add(event_id)
    semantic_projections.sort(key=canonical_json)
    return index, conflicts, semantic_projections


def _operation_id(
    *,
    episode_id: str | None,
    event_id: str,
    operation_type: str,
) -> str:
    material = {
        "method_version": METHOD_VERSION,
        "episode_id": episode_id,
        "event_id": event_id,
        "operation_type": operation_type,
    }
    return "op_" + _digest(material)[:32]


def _position_role_from_facts(
    *,
    event_type: str,
    side: str,
    before: Decimal,
    after: Decimal,
) -> str:
    if before < 0 or after < 0:
        return (
            "position_reversal"
            if before * after < 0
            else "position_anomaly"
        )
    if before * after < 0:
        return "position_reversal"
    if (
        event_type in _SPECIAL_EVENT_TYPES
        or side in {"TRANSFER_IN", "TRANSFER_OUT"}
    ):
        return "special_quantity_adjustment"
    if event_type not in _NORMAL_POSITION_EVENT_TYPES:
        return "position_anomaly"
    if before == 0 and after > 0:
        return "position_open"
    if before > 0 and after > before:
        return "position_increase"
    if before > after > 0:
        return "position_reduce"
    if before > 0 and after == 0:
        return "position_close"
    return "position_anomaly"


def _position_operation(
    event_ref: Mapping[str, Any],
    *,
    episode_id: str,
    sequence_index: int,
    decision_context_status: str,
    event_input: Mapping[str, Any] | None,
    event_input_conflict: bool,
) -> dict[str, Any]:
    event_id = str(event_ref.get("event_id") or "")
    event_type = str(event_ref.get("event_type") or "fill").strip().lower()
    side = str(event_ref.get("side") or "").strip().upper()
    effective_at = _timestamp_text(event_ref.get("effective_at"))
    reasons: list[str] = []
    status = "ready"
    operation_type = "position_anomaly"

    try:
        before = _decimal(event_ref.get("quantity_before"))
        after = _decimal(event_ref.get("quantity_after"))
        signed = _decimal(event_ref.get("signed_quantity"))
    except OperationReviewError:
        before = after = signed = None
        status = "blocked"
        reasons.append("INVALID_QUANTITY_TRANSITION")

    if event_input_conflict:
        status = "blocked"
        reasons.append("CONFLICTING_EVENT_INPUT")
    elif event_input is not None:
        projected = _event_projection(event_input)
        raw_type = str(projected.get("event_type") or "fill").lower()
        raw_side = str(projected.get("side") or "").upper()
        raw_quantity = _decimal(projected.get("quantity"))
        if (
            raw_type != event_type
            or raw_side != side
            or (
                raw_quantity is not None
                and signed is not None
                and raw_quantity != abs(signed)
            )
        ):
            status = "blocked"
            reasons.append("EVENT_INPUT_TRANSITION_MISMATCH")
        if (
            projected.get("occurred_at") != effective_at
            or projected.get("source_refs")
            != _safe_source_refs(
                event_ref.get("source_refs")
                if isinstance(event_ref.get("source_refs"), Mapping)
                else None,
                event_id=event_id,
            )
        ):
            status = "blocked"
            reasons.append("EVENT_INPUT_PROVENANCE_MISMATCH")

    if before is None or after is None or signed is None:
        status = "blocked"
        reasons.append("MISSING_QUANTITY_TRANSITION")
    else:
        if before + signed != after:
            status = "blocked"
            reasons.append("QUANTITY_ARITHMETIC_MISMATCH")
        if signed == 0:
            status = "blocked"
            reasons.append("ZERO_DELTA_POSITION_EVENT")
        if (signed > 0 and side not in {"BUY", "TRANSFER_IN"}) or (
            signed < 0 and side not in {"SELL", "TRANSFER_OUT"}
        ):
            status = "blocked"
            reasons.append("SIDE_DELTA_MISMATCH")
        if (event_type == "buy" and side != "BUY") or (
            event_type == "sell" and side != "SELL"
        ):
            status = "blocked"
            reasons.append("EVENT_TYPE_SIDE_MISMATCH")
        if before < 0 or after < 0:
            status = "blocked"
            if before * after < 0:
                operation_type = "position_reversal"
                reasons.append("UNSPLIT_SIGN_REVERSAL")
            else:
                reasons.append("NEGATIVE_POSITION_UNSUPPORTED")
        elif before * after < 0:
            status = "blocked"
            operation_type = "position_reversal"
            reasons.append("UNSPLIT_SIGN_REVERSAL")
        elif (
            event_type in _SPECIAL_EVENT_TYPES
            or side in {"TRANSFER_IN", "TRANSFER_OUT"}
        ):
            if status != "blocked":
                status = "ambiguous"
            operation_type = "special_quantity_adjustment"
            reasons.append("SPECIAL_EVENT_REQUIRES_EXPLICIT_SEMANTICS")
        elif event_type not in _NORMAL_POSITION_EVENT_TYPES:
            status = "blocked"
            operation_type = "position_anomaly"
            reasons.append("UNSUPPORTED_POSITION_EVENT_TYPE")
        elif before == 0 and after > 0:
            operation_type = "position_open"
        elif before > 0 and after > before:
            operation_type = "position_increase"
        elif before > after > 0:
            operation_type = "position_reduce"
        elif before > 0 and after == 0:
            operation_type = "position_close"
        else:
            status = "blocked"
            operation_type = "position_anomaly"
            reasons.append("UNCLASSIFIABLE_QUANTITY_TRANSITION")

    if before is not None and after is not None:
        operation_type = _position_role_from_facts(
            event_type=event_type,
            side=side,
            before=before,
            after=after,
        )
    reasons = sorted(set(reasons))
    operation = {
        "operation_id": "",
        "sequence_index": sequence_index,
        "episode_id": episode_id,
        "event_id": event_id,
        "event_type": event_type,
        "effective_at": effective_at,
        "side": side,
        "quantity_applicability": "applicable",
        "qty_before": _decimal_text(before),
        "qty_after": _decimal_text(after),
        "signed_quantity": _decimal_text(signed),
        "operation_type": operation_type,
        "classification_status": status,
        "method_version": METHOD_VERSION,
        "decision_context_status": decision_context_status,
        "cash_amount": None,
        "cash_amount_status": "not_applicable",
        "source_refs": _safe_source_refs(
            event_ref.get("source_refs")
            if isinstance(event_ref.get("source_refs"), Mapping)
            else None,
            event_id=event_id,
        ),
        "reason_codes": reasons,
    }
    operation["operation_id"] = _operation_id(
        episode_id=episode_id,
        event_id=event_id,
        operation_type=operation_type,
    )
    return operation


def _cash_operation(
    event_id: str,
    *,
    event_input: Mapping[str, Any] | None,
    event_input_conflict: bool,
) -> dict[str, Any]:
    reasons: list[str] = []
    status = "ready"
    event_type = ""
    side = ""
    effective_at: str | None = None
    cash_amount: str | None = None
    source_refs = _safe_source_refs(None, event_id=event_id)

    if event_input_conflict:
        status = "blocked"
        reasons.append("CONFLICTING_EVENT_INPUT")
    elif event_input is None:
        status = "blocked"
        reasons.append("MISSING_EXPLICIT_CASH_EVENT_INPUT")
    else:
        projection = _event_projection(event_input)
        event_type = str(projection.get("event_type") or "").lower()
        side = str(projection.get("side") or "").upper()
        effective_at = _text(projection.get("occurred_at"))
        cash_amount = projection.get("cash_amount")
        source_refs = deepcopy(projection["source_refs"])
        quantity = _decimal(projection.get("quantity"))
        if (
            event_type not in _CASH_EVENT_TYPES
            or side != "OTHER"
            or quantity != 0
            or effective_at is None
        ):
            status = "blocked"
            reasons.append("INVALID_EXPLICIT_CASH_EVENT")
        if cash_amount is None:
            reasons.append("CASH_AMOUNT_NOT_RECORDED")

    operation_type = {
        "dividend": "cash_dividend",
        "cash_fee": "cash_fee",
    }.get(event_type, "cash_event")
    operation = {
        "operation_id": "",
        "sequence_index": -1,
        "episode_id": None,
        "event_id": event_id,
        "event_type": event_type,
        "effective_at": effective_at,
        "side": side,
        "quantity_applicability": "not_applicable",
        "qty_before": None,
        "qty_after": None,
        "signed_quantity": None,
        "operation_type": operation_type,
        "classification_status": status,
        "method_version": METHOD_VERSION,
        "decision_context_status": "not_applicable",
        "cash_amount": cash_amount,
        "cash_amount_status": (
            "available" if cash_amount is not None else "missing"
        ),
        "source_refs": source_refs,
        "reason_codes": sorted(set(reasons)),
    }
    operation["operation_id"] = _operation_id(
        episode_id=None,
        event_id=event_id,
        operation_type=operation_type,
    )
    return operation


def _decision_context_status(episode: Mapping[str, Any]) -> str:
    linkage = episode.get("decision_linkage")
    source_status = (
        str(linkage.get("status") or "")
        if isinstance(linkage, Mapping)
        else ""
    )
    return {
        "linked": "complete",
        "unlinked": "not_recorded",
        "ambiguous": "partial",
    }.get(source_status, "blocked")


def _episode_operation_status(
    episode: Mapping[str, Any],
    operations: Sequence[object],
) -> tuple[str, list[str]]:
    reasons: set[str] = set()
    valid_operations = [
        operation
        for operation in operations
        if isinstance(operation, Mapping)
    ]
    statuses = {
        str(operation.get("classification_status") or "blocked")
        for operation in valid_operations
    }
    if not valid_operations:
        return "blocked", ["NO_POSITION_OPERATION"]
    if "blocked" in statuses:
        status = "blocked"
        reasons.add("BLOCKED_OPERATION_FACT")
    elif "ambiguous" in statuses:
        status = "partial"
        reasons.add("AMBIGUOUS_OPERATION_FACT")
    else:
        status = "ready"
    episode_status = str(
        episode.get("status") or episode.get("episode_status") or ""
    )
    if episode_status == "ambiguous":
        status = "blocked"
        reasons.add("AMBIGUOUS_EPISODE_BOUNDARY")
    elif episode_status == "data_gap" and status == "ready":
        status = "partial"
        reasons.add("EPISODE_QUANTITY_HISTORY_INCOMPLETE")
    return status, sorted(reasons)


def _summary(
    episode_reviews: Sequence[Mapping[str, Any]],
    standalone_operations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    all_operations: list[Mapping[str, Any]] = []
    for episode in episode_reviews:
        if not isinstance(episode, Mapping):
            continue
        operations = episode.get("operations")
        if not isinstance(operations, list):
            continue
        all_operations.extend(
            operation
            for operation in operations
            if isinstance(operation, Mapping)
        )
    all_operations.extend(
        operation
        for operation in standalone_operations
        if isinstance(operation, Mapping)
    )
    operation_types = Counter(
        str(item.get("operation_type") or "") for item in all_operations
    )
    classifications = Counter(
        str(item.get("classification_status") or "")
        for item in all_operations
    )
    operation_statuses = Counter(
        str(item.get("operation_review_status") or "")
        for item in episode_reviews
        if isinstance(item, Mapping)
    )
    decision_statuses = Counter(
        str(item.get("decision_context_status") or "")
        for item in episode_reviews
        if isinstance(item, Mapping)
    )
    return {
        "episode_review_count": len(episode_reviews),
        "standalone_operation_count": len(standalone_operations),
        "operation_count": len(all_operations),
        "operation_type_counts": dict(sorted(operation_types.items())),
        "classification_status_counts": dict(
            sorted(classifications.items())
        ),
        "operation_review_status_counts": dict(
            sorted(operation_statuses.items())
        ),
        "decision_context_status_counts": dict(
            sorted(decision_statuses.items())
        ),
    }


def build_operation_review(
    episode_collection: Mapping[str, Any],
    *,
    event_inputs: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build a decision-optional operation review without mutating inputs."""

    if not isinstance(episode_collection, Mapping):
        raise OperationReviewError("episode_collection must be a mapping")
    source_validation = _validate_source_collection(episode_collection)
    collection_schema = str(
        episode_collection.get("schema_version") or ""
    )
    collection_digest = str(
        episode_collection.get("collection_digest") or ""
    )
    if (
        collection_schema != COLLECTION_SCHEMA_VERSION
        or not _HEX64.fullmatch(collection_digest)
    ):
        raise OperationReviewError(
            "episode_collection must expose its schema and digest"
        )

    relevant_event_ids = _relevant_event_ids(episode_collection)
    event_index, conflicts, event_projections = _event_index(
        event_inputs,
        relevant_event_ids=relevant_event_ids,
    )

    episode_reviews: list[dict[str, Any]] = []
    for episode in episode_collection.get("episodes", []):
        if not isinstance(episode, Mapping):
            raise OperationReviewError("episode entries must be mappings")
        episode_id = str(episode.get("episode_id") or "")
        if not episode_id:
            raise OperationReviewError("episode_id is required")
        decision_context_status = _decision_context_status(episode)
        operations = [
            _position_operation(
                event_ref,
                episode_id=episode_id,
                sequence_index=sequence_index,
                decision_context_status=decision_context_status,
                event_input=event_index.get(
                    str(event_ref.get("event_id") or "")
                ),
                event_input_conflict=str(
                    event_ref.get("event_id") or ""
                )
                in conflicts,
            )
            for sequence_index, event_ref in enumerate(
                episode.get("event_refs", [])
            )
            if isinstance(event_ref, Mapping)
        ]
        operation_status, reason_codes = _episode_operation_status(
            episode, operations
        )
        episode_reviews.append(
            {
                "episode_id": episode_id,
                "episode_status": str(episode.get("status") or ""),
                "scope": deepcopy(dict(episode.get("scope") or {})),
                "operation_review_status": operation_status,
                "decision_context_status": decision_context_status,
                "operations": operations,
                "reason_codes": reason_codes,
            }
        )
    episode_reviews.sort(key=lambda item: item["episode_id"])

    cash_event_ids = sorted(
        {
            str(item.get("event_id") or "")
            for item in episode_collection.get("consumption_ledger", [])
            if isinstance(item, Mapping)
            and item.get("outcome") == "non_position_changing"
            and item.get("event_id")
        }
    )
    standalone_operations = [
        _cash_operation(
            event_id,
            event_input=event_index.get(event_id),
            event_input_conflict=event_id in conflicts,
        )
        for event_id in cash_event_ids
    ]
    standalone_operations.sort(
        key=lambda item: (
            str(item.get("effective_at") or ""),
            str(item.get("event_id") or ""),
            str(item.get("operation_id") or ""),
        )
    )
    for sequence_index, operation in enumerate(standalone_operations):
        operation["sequence_index"] = sequence_index

    artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "method_version": METHOD_VERSION,
        "content_id": "",
        "source_binding": {
            "episode_collection_schema_version": collection_schema,
            "episode_collection_content_id": "sha256:"
            + collection_digest,
            "event_projection_content_id": "sha256:"
            + _digest(event_projections),
            "event_projection_count": len(event_projections),
            "episode_collection_integrity_status": "verified",
            "episode_collection_validation_status": (
                source_validation["validation_status"]
            ),
            "episode_collection_blocker_codes": (
                source_validation["blocker_codes"]
            ),
        },
        "summary": _summary(episode_reviews, standalone_operations),
        "episode_reviews": episode_reviews,
        "standalone_operations": standalone_operations,
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
        "details": {},
    }


def _valid_content_id(value: object) -> bool:
    text = str(value or "")
    return text.startswith("sha256:") and bool(
        _HEX64.fullmatch(text.removeprefix("sha256:"))
    )


def _validate_source_refs(
    source_refs: object,
    *,
    event_id: str,
    require_material: bool,
    findings: list[dict[str, Any]],
) -> None:
    if not isinstance(source_refs, Mapping) or set(source_refs) != (
        _SOURCE_REF_FIELDS
    ):
        findings.append(
            _finding(
                "MALFORMED_SOURCE_REFS",
                "source_refs must use the closed explicit-source shape",
                related_refs=[event_id],
            )
        )
        return
    keys = source_refs.get("source_keys")
    if (
        not isinstance(keys, list)
        or not all(isinstance(item, str) and item for item in keys)
        or (
            all(isinstance(item, str) for item in keys)
            and keys != sorted(set(keys))
        )
        or event_id not in keys
    ):
        findings.append(
            _finding(
                "INVALID_SOURCE_KEYS",
                "source keys must be unique, sorted, and include event_id",
                related_refs=[event_id],
            )
        )
    payload_hash = source_refs.get("payload_sha256")
    if payload_hash is not None and not _HEX64.fullmatch(str(payload_hash)):
        findings.append(
            _finding(
                "INVALID_SOURCE_PAYLOAD_HASH",
                "payload_sha256 must be null or lowercase SHA-256",
                related_refs=[event_id],
            )
        )
    if require_material and (
        not _text(source_refs.get("source_id"))
        or payload_hash is None
    ):
        findings.append(
            _finding(
                "MISSING_MATERIAL_SOURCE_LINEAGE",
                "ready or ambiguous facts require material source lineage",
                related_refs=[event_id],
            )
        )


def _validate_operation(
    operation: object,
    *,
    expected_episode_id: str | None,
    expected_sequence_index: int,
    expected_decision_context_status: str,
    findings: list[dict[str, Any]],
) -> None:
    if not isinstance(operation, Mapping):
        findings.append(
            _finding(
                "MALFORMED_OPERATION",
                "operation entries must be mappings",
            )
        )
        return
    event_id = str(operation.get("event_id") or "")
    if set(operation) != _OPERATION_FIELDS:
        findings.append(
            _finding(
                "MALFORMED_OPERATION_SHAPE",
                "operation uses an unexpected field set",
                related_refs=[event_id],
            )
        )
    if operation.get("episode_id") != expected_episode_id:
        findings.append(
            _finding(
                "OPERATION_EPISODE_MISMATCH",
                "operation episode_id does not match its container",
                related_refs=[event_id],
            )
        )
    if (
        operation.get("sequence_index") != expected_sequence_index
        or isinstance(operation.get("sequence_index"), bool)
    ):
        findings.append(
            _finding(
                "OPERATION_SEQUENCE_MISMATCH",
                "operation sequence_index is not canonical",
                related_refs=[event_id],
            )
        )
    if (
        operation.get("decision_context_status")
        != expected_decision_context_status
        or operation.get("decision_context_status")
        not in _DECISION_CONTEXT_STATUSES
    ):
        findings.append(
            _finding(
                "OPERATION_DECISION_CONTEXT_MISMATCH",
                "operation decision context does not match its container",
                related_refs=[event_id],
            )
        )
    operation_type = str(operation.get("operation_type") or "")
    classification = str(
        operation.get("classification_status") or ""
    )
    if operation_type not in _POSITION_TYPES | _CASH_TYPES:
        findings.append(
            _finding(
                "INVALID_OPERATION_TYPE",
                "operation_type is unsupported",
                related_refs=[event_id],
            )
        )
    if classification not in _CLASSIFICATION_STATUSES:
        findings.append(
            _finding(
                "INVALID_CLASSIFICATION_STATUS",
                "classification_status is unsupported",
                related_refs=[event_id],
            )
        )
    if operation.get("method_version") != METHOD_VERSION:
        findings.append(
            _finding(
                "UNSUPPORTED_OPERATION_METHOD",
                "operation method_version is unsupported",
                related_refs=[event_id],
            )
        )
    expected_id = _operation_id(
        episode_id=expected_episode_id,
        event_id=event_id,
        operation_type=operation_type,
    )
    if operation.get("operation_id") != expected_id:
        findings.append(
            _finding(
                "OPERATION_ID_MISMATCH",
                "operation_id does not match semantic identity",
                related_refs=[event_id],
            )
        )
    _validate_source_refs(
        operation.get("source_refs"),
        event_id=event_id,
        require_material=classification in {"ready", "ambiguous"},
        findings=findings,
    )
    reasons = operation.get("reason_codes")
    valid_reasons = (
        isinstance(reasons, list)
        and all(isinstance(item, str) and item for item in reasons)
        and reasons == sorted(set(reasons))
    )
    if not valid_reasons:
        findings.append(
            _finding(
                "INVALID_OPERATION_REASON_CODES",
                "reason_codes must be unique and sorted",
                related_refs=[event_id],
            )
        )
    elif classification != "ready" and not reasons:
        findings.append(
            _finding(
                "MISSING_OPERATION_REASON_CODE",
                "non-ready operation requires an explicit reason code",
                related_refs=[event_id],
            )
        )
    allowed_operation_reasons = (
        _CASH_REASON_CODES
        if expected_episode_id is None
        else _POSITION_REASON_CODES
    )
    if valid_reasons and bool(
        set(reasons) - allowed_operation_reasons
    ):
        findings.append(
            _finding(
                "UNKNOWN_OPERATION_REASON_CODE",
                "operation reason_codes are not from the closed classifier",
                related_refs=[event_id],
            )
        )
    effective_at = operation.get("effective_at")
    try:
        canonical_effective_at = _timestamp_text(effective_at)
    except OperationReviewError:
        canonical_effective_at = object()
    if (
        not event_id
        or (
            (
                not _text(operation.get("event_type"))
                or canonical_effective_at is None
            )
            and classification != "blocked"
        )
        or (
            effective_at is not None
            and canonical_effective_at != effective_at
        )
    ):
        findings.append(
            _finding(
                "MISSING_OPERATION_IDENTITY_FACT",
                "event_id, event_type, and effective_at are required facts",
                related_refs=[event_id],
            )
        )

    if expected_episode_id is None:
        event_type = str(operation.get("event_type") or "").lower()
        side = str(operation.get("side") or "").upper()
        expected_cash_type = {
            "dividend": "cash_dividend",
            "cash_fee": "cash_fee",
        }.get(event_type)
        if (
            operation_type not in _CASH_TYPES
            or operation.get("quantity_applicability") != "not_applicable"
            or any(
                operation.get(field) is not None
                for field in (
                    "qty_before",
                    "qty_after",
                    "signed_quantity",
                )
            )
            or operation.get("cash_amount_status")
            not in {"available", "missing"}
        ):
            findings.append(
                _finding(
                    "INVALID_CASH_OPERATION_FACTS",
                    "standalone cash facts violate quantity/cash semantics",
                    related_refs=[event_id],
                )
            )
        if operation_type != (expected_cash_type or "cash_event"):
            findings.append(
                _finding(
                    "CASH_EVENT_TYPE_MISMATCH",
                    "cash operation_type does not match explicit event_type",
                    related_refs=[event_id],
                )
            )
        if classification == "ready" and (
            expected_cash_type is None
            or side != "OTHER"
            or operation_type != expected_cash_type
        ):
            findings.append(
                _finding(
                    "INVALID_READY_CASH_EVENT",
                    "ready cash operation requires dividend/cash_fee and OTHER",
                    related_refs=[event_id],
                )
            )
        cash_amount = operation.get("cash_amount")
        try:
            canonical_cash_amount = _decimal_text(cash_amount)
        except OperationReviewError:
            canonical_cash_amount = object()
        if (
            operation.get("cash_amount_status") == "available"
            and canonical_cash_amount != cash_amount
        ) or (
            operation.get("cash_amount_status") == "missing"
            and cash_amount is not None
        ):
            findings.append(
                _finding(
                    "INVALID_CASH_AMOUNT",
                    "cash_amount status and canonical value disagree",
                    related_refs=[event_id],
                )
            )
        if classification == "ready":
            expected_cash_reasons = (
                ["CASH_AMOUNT_NOT_RECORDED"]
                if cash_amount is None
                else []
            )
            if operation.get("reason_codes") != expected_cash_reasons:
                findings.append(
                    _finding(
                        "READY_CASH_REASON_MISMATCH",
                        "ready cash reasons must match amount availability",
                        related_refs=[event_id],
                    )
                )
        return

    if (
        operation_type not in _POSITION_TYPES
        or operation.get("quantity_applicability") != "applicable"
        or operation.get("cash_amount") is not None
        or operation.get("cash_amount_status") != "not_applicable"
    ):
        findings.append(
            _finding(
                "INVALID_POSITION_OPERATION_FACTS",
                "position facts violate quantity/cash applicability",
                related_refs=[event_id],
            )
        )
        return
    try:
        before = _decimal(operation.get("qty_before"))
        after = _decimal(operation.get("qty_after"))
        signed = _decimal(operation.get("signed_quantity"))
    except OperationReviewError:
        before = after = signed = None
    if (
        before is None
        or after is None
        or signed is None
        or _decimal_text(before) != operation.get("qty_before")
        or _decimal_text(after) != operation.get("qty_after")
        or _decimal_text(signed) != operation.get("signed_quantity")
    ):
        findings.append(
            _finding(
                "INVALID_POSITION_QUANTITY",
                "position quantities must be present canonical decimals",
                related_refs=[event_id],
            )
        )
        return
    event_type = str(operation.get("event_type") or "").lower()
    side = str(operation.get("side") or "").upper()
    derived_operation_type = _position_role_from_facts(
        event_type=event_type,
        side=side,
        before=before,
        after=after,
    )
    if operation_type != derived_operation_type:
        findings.append(
            _finding(
                "POSITION_OPERATION_ROLE_MISMATCH",
                "operation_type is not derived from quantity and event facts",
                related_refs=[event_id],
            )
        )
    if classification == "ready":
        expected_type = (
            "position_open"
            if before == 0 and after > 0
            else "position_increase"
            if before > 0 and after > before
            else "position_reduce"
            if before > after > 0
            else "position_close"
            if before > 0 and after == 0
            else ""
        )
        if before + signed != after or operation_type != expected_type:
            findings.append(
                _finding(
                    "READY_OPERATION_TRANSITION_MISMATCH",
                    "ready operation does not match its quantity transition",
                    related_refs=[event_id],
                )
            )
        if (
            event_type not in _NORMAL_POSITION_EVENT_TYPES
            or (signed > 0 and side != "BUY")
            or (signed < 0 and side != "SELL")
            or (event_type == "buy" and side != "BUY")
            or (event_type == "sell" and side != "SELL")
        ):
            findings.append(
                _finding(
                    "READY_OPERATION_EVENT_FACT_MISMATCH",
                    "ready operation conflicts with explicit type/side/delta",
                    related_refs=[event_id],
                )
            )
        if operation.get("reason_codes") != []:
            findings.append(
                _finding(
                    "READY_POSITION_HAS_REASON_CODE",
                    "ready position operation cannot carry limitation codes",
                    related_refs=[event_id],
                )
            )
        if operation_type in {
            "position_reversal",
            "position_anomaly",
            "special_quantity_adjustment",
        }:
            findings.append(
                _finding(
                    "INVALID_READY_OPERATION_TYPE",
                    "ambiguous or anomalous operation cannot be ready",
                    related_refs=[event_id],
                )
            )
    elif classification == "ambiguous" and (
        operation_type != "special_quantity_adjustment"
        or (
            str(operation.get("event_type") or "").lower()
            not in _SPECIAL_EVENT_TYPES
            and str(operation.get("side") or "").upper()
            not in {"TRANSFER_IN", "TRANSFER_OUT"}
        )
        or operation.get("reason_codes")
        != ["SPECIAL_EVENT_REQUIRES_EXPLICIT_SEMANTICS"]
    ):
        findings.append(
            _finding(
                "AMBIGUOUS_OPERATION_SEMANTICS_MISMATCH",
                "ambiguous operation must be an explicit special adjustment",
                related_refs=[event_id],
            )
        )


def _validate_episode_operation_chain(
    episode: Mapping[str, Any],
    operations: Sequence[object],
    *,
    findings: list[dict[str, Any]],
) -> None:
    episode_id = str(episode.get("episode_id") or "")
    position_operations = [
        operation
        for operation in operations
        if isinstance(operation, Mapping)
    ]
    if not position_operations:
        return
    transitions: list[tuple[Decimal, Decimal, datetime, str]] = []
    for operation in position_operations:
        event_id = str(operation.get("event_id") or "")
        try:
            before = _decimal(operation.get("qty_before"))
            after = _decimal(operation.get("qty_after"))
            effective_text = _timestamp_text(operation.get("effective_at"))
            effective = datetime.fromisoformat(str(effective_text))
        except (OperationReviewError, ValueError):
            return
        if before is None or after is None or effective_text is None:
            return
        transitions.append((before, after, effective, event_id))
    if transitions[0][0] != 0:
        findings.append(
            _finding(
                "EPISODE_CHAIN_START_MISMATCH",
                "episode operation chain must start from zero quantity",
                related_refs=[episode_id, transitions[0][3]],
            )
        )
    for previous, current in zip(transitions, transitions[1:]):
        if previous[1] != current[0]:
            findings.append(
                _finding(
                    "EPISODE_QUANTITY_CHAIN_MISMATCH",
                    "adjacent operation quantities are not continuous",
                    related_refs=[
                        episode_id,
                        previous[3],
                        current[3],
                    ],
                )
            )
        if previous[2] > current[2]:
            findings.append(
                _finding(
                    "EPISODE_TIME_ORDER_MISMATCH",
                    "episode operations are not in effective-time order",
                    related_refs=[
                        episode_id,
                        previous[3],
                        current[3],
                    ],
                )
            )
    final_quantity = transitions[-1][1]
    episode_status = str(episode.get("episode_status") or "")
    if (
        episode_status == "closed"
        and final_quantity != 0
    ) or (
        episode_status == "open"
        and final_quantity <= 0
    ):
        findings.append(
            _finding(
                "EPISODE_TERMINAL_QUANTITY_MISMATCH",
                "episode status conflicts with terminal quantity",
                related_refs=[episode_id, transitions[-1][3]],
            )
        )


def validate_operation_review(
    artifact: object,
) -> dict[str, Any]:
    """Validate the closed operation-review artifact shape and integrity."""

    findings: list[dict[str, Any]] = []
    if not isinstance(artifact, Mapping):
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "validation_status": "blocked",
            "findings": [
                _finding(
                    "MALFORMED_OPERATION_REVIEW",
                    "operation review must be a mapping",
                )
            ],
        }
    if set(artifact) != _ROOT_FIELDS:
        findings.append(
            _finding(
                "MALFORMED_OPERATION_REVIEW_SHAPE",
                "operation review uses an unexpected root field set",
            )
        )
    if artifact.get("schema_version") != SCHEMA_VERSION:
        findings.append(
            _finding(
                "UNSUPPORTED_OPERATION_REVIEW_SCHEMA",
                "operation review schema_version is unsupported",
            )
        )
    if artifact.get("method_version") != METHOD_VERSION:
        findings.append(
            _finding(
                "UNSUPPORTED_OPERATION_REVIEW_METHOD",
                "operation review method_version is unsupported",
            )
        )
    try:
        _assert_strict_json(dict(artifact))
        expected_content_id = _content_id(artifact)
    except OperationReviewError as exc:
        expected_content_id = None
        findings.append(
            _finding(
                "NON_CANONICAL_OPERATION_REVIEW_VALUE",
                str(exc),
            )
        )
    if (
        not _valid_content_id(artifact.get("content_id"))
        or artifact.get("content_id") != expected_content_id
    ):
        findings.append(
            _finding(
                "OPERATION_REVIEW_CONTENT_ID_MISMATCH",
                "content_id does not bind the canonical artifact",
            )
        )

    source_binding = artifact.get("source_binding")
    source_count = (
        source_binding.get("event_projection_count")
        if isinstance(source_binding, Mapping)
        else None
    )
    source_blockers = (
        source_binding.get("episode_collection_blocker_codes")
        if isinstance(source_binding, Mapping)
        else None
    )
    source_validation_status = (
        source_binding.get("episode_collection_validation_status")
        if isinstance(source_binding, Mapping)
        else None
    )
    if (
        not isinstance(source_binding, Mapping)
        or set(source_binding) != _SOURCE_BINDING_FIELDS
        or source_binding.get("episode_collection_schema_version")
        != COLLECTION_SCHEMA_VERSION
        or source_binding.get("episode_collection_integrity_status")
        != "verified"
        or not _valid_content_id(
            source_binding.get("episode_collection_content_id")
            if isinstance(source_binding, Mapping)
            else None
        )
        or not _valid_content_id(
            source_binding.get("event_projection_content_id")
            if isinstance(source_binding, Mapping)
            else None
        )
        or not isinstance(source_count, int)
        or isinstance(source_count, bool)
        or (isinstance(source_count, int) and source_count < 0)
        or source_validation_status
        not in {"accepted", "accepted_with_warnings", "blocked"}
        or not isinstance(source_blockers, list)
        or (
            isinstance(source_blockers, list)
            and (
                not all(
                    isinstance(item, str) and item
                    for item in source_blockers
                )
                or source_blockers != sorted(set(source_blockers))
                or bool(set(source_blockers) - _ALLOWED_SOURCE_BLOCKERS)
                or (
                    source_validation_status == "blocked"
                    and not source_blockers
                )
                or (
                    source_validation_status != "blocked"
                    and bool(source_blockers)
                )
            )
        )
    ):
        findings.append(
            _finding(
                "MALFORMED_OPERATION_SOURCE_BINDING",
                "source_binding is incomplete or malformed",
            )
        )

    episode_reviews = artifact.get("episode_reviews")
    standalone = artifact.get("standalone_operations")
    if not isinstance(episode_reviews, list):
        findings.append(
            _finding(
                "MALFORMED_EPISODE_REVIEWS",
                "episode_reviews must be a list",
            )
        )
        episode_reviews = []
    if not isinstance(standalone, list):
        findings.append(
            _finding(
                "MALFORMED_STANDALONE_OPERATIONS",
                "standalone_operations must be a list",
            )
        )
        standalone = []

    episode_ids: list[str] = []
    operation_ids: list[str] = []
    for episode in episode_reviews:
        if not isinstance(episode, Mapping):
            findings.append(
                _finding(
                    "MALFORMED_EPISODE_REVIEW",
                    "episode review entries must be mappings",
                )
            )
            continue
        episode_id = str(episode.get("episode_id") or "")
        episode_ids.append(episode_id)
        if not _EPISODE_ID.fullmatch(episode_id):
            findings.append(
                _finding(
                    "INVALID_EPISODE_IDENTITY",
                    "episode_id must retain the canonical P2C identity",
                    related_refs=[episode_id],
                )
            )
        if set(episode) != _EPISODE_REVIEW_FIELDS:
            findings.append(
                _finding(
                    "MALFORMED_EPISODE_REVIEW_SHAPE",
                    "episode review uses an unexpected field set",
                    related_refs=[episode_id],
                )
            )
        scope = episode.get("scope")
        if (
            not isinstance(scope, Mapping)
            or set(scope) != _SCOPE_FIELDS
            or any(
                not isinstance(scope.get(field), str)
                or not str(scope.get(field) or "").strip()
                for field in (
                    "account_id",
                    "instrument_id",
                    "symbol",
                    "currency",
                )
            )
            or (
                isinstance(scope, Mapping)
                and scope.get("market") is not None
                and (
                    not isinstance(scope.get("market"), str)
                    or not str(scope.get("market") or "").strip()
                )
            )
        ):
            findings.append(
                _finding(
                    "MALFORMED_EPISODE_SCOPE",
                    "episode scope must use the closed P2C identity shape",
                    related_refs=[episode_id],
                )
            )
        if episode.get("episode_status") not in {
            "open",
            "closed",
            "data_gap",
            "ambiguous",
        }:
            findings.append(
                _finding(
                    "INVALID_EPISODE_STATUS",
                    "episode_status is unsupported",
                    related_refs=[episode_id],
                )
            )
        if (
            episode.get("operation_review_status")
            not in _OPERATION_REVIEW_STATUSES
        ):
            findings.append(
                _finding(
                    "INVALID_OPERATION_REVIEW_STATUS",
                    "operation_review_status is unsupported",
                    related_refs=[episode_id],
                )
            )
        if (
            episode.get("decision_context_status")
            not in _DECISION_CONTEXT_STATUSES
        ):
            findings.append(
                _finding(
                    "INVALID_DECISION_CONTEXT_STATUS",
                    "decision_context_status is unsupported",
                    related_refs=[episode_id],
                )
            )
        reasons = episode.get("reason_codes")
        if (
            not isinstance(reasons, list)
            or not all(isinstance(item, str) and item for item in reasons)
            or (
                all(isinstance(item, str) for item in reasons)
                and reasons != sorted(set(reasons))
            )
        ):
            findings.append(
                _finding(
                    "INVALID_EPISODE_REASON_CODES",
                    "episode reason_codes must be unique and sorted",
                    related_refs=[episode_id],
                )
            )
        elif bool(set(reasons) - _EPISODE_REASON_CODES):
            findings.append(
                _finding(
                    "UNKNOWN_EPISODE_REASON_CODE",
                    "episode reason_codes are not from the closed classifier",
                    related_refs=[episode_id],
                )
            )
        operations = episode.get("operations")
        if not isinstance(operations, list):
            findings.append(
                _finding(
                    "MALFORMED_EPISODE_OPERATIONS",
                    "episode operations must be a list",
                    related_refs=[episode_id],
                )
            )
            continue
        for sequence_index, operation in enumerate(operations):
            _validate_operation(
                operation,
                expected_episode_id=episode_id,
                expected_sequence_index=sequence_index,
                expected_decision_context_status=str(
                    episode.get("decision_context_status") or ""
                ),
                findings=findings,
            )
            if isinstance(operation, Mapping):
                operation_ids.append(str(operation.get("operation_id") or ""))
        _validate_episode_operation_chain(
            episode,
            operations,
            findings=findings,
        )
        expected_status, expected_reasons = _episode_operation_status(
            episode, operations
        )
        if (
            episode.get("operation_review_status") != expected_status
            or episode.get("reason_codes") != expected_reasons
        ):
            findings.append(
                _finding(
                    "EPISODE_OPERATION_STATUS_MISMATCH",
                    "episode operation status does not match operation facts",
                    related_refs=[episode_id],
                )
            )
    for sequence_index, operation in enumerate(standalone):
        _validate_operation(
            operation,
            expected_episode_id=None,
            expected_sequence_index=sequence_index,
            expected_decision_context_status="not_applicable",
            findings=findings,
        )
        if isinstance(operation, Mapping):
            operation_ids.append(str(operation.get("operation_id") or ""))
    standalone_order = [
        (
            str(operation.get("effective_at") or ""),
            str(operation.get("event_id") or ""),
            str(operation.get("operation_id") or ""),
        )
        for operation in standalone
        if isinstance(operation, Mapping)
    ]
    if standalone_order != sorted(standalone_order):
        findings.append(
            _finding(
                "STANDALONE_OPERATION_ORDER_MISMATCH",
                "standalone cash operations are not in canonical order",
            )
        )

    if episode_ids != sorted(set(episode_ids)):
        findings.append(
            _finding(
                "EPISODE_REVIEW_ORDER_OR_IDENTITY_MISMATCH",
                "episode reviews must have unique sorted identities",
            )
        )
    if len(operation_ids) != len(set(operation_ids)):
        findings.append(
            _finding(
                "DUPLICATE_OPERATION_IDENTITY",
                "operation identities must be unique",
            )
        )
    if artifact.get("summary") != _summary(episode_reviews, standalone):
        findings.append(
            _finding(
                "OPERATION_REVIEW_SUMMARY_MISMATCH",
                "summary does not match contained operations",
            )
        )
    if artifact.get("governance") != _GOVERNANCE:
        findings.append(
            _finding(
                "INVALID_OPERATION_REVIEW_GOVERNANCE",
                "facts-only and no-inference governance is not closed",
            )
        )
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "validation_status": "accepted" if not findings else "blocked",
        "findings": sorted(
            findings,
            key=lambda item: (
                str(item.get("code") or ""),
                canonical_json(item.get("related_refs") or []),
            ),
        ),
    }


def replay_validate_operation_review(
    artifact: object,
    *,
    episode_collection: Mapping[str, Any],
    event_inputs: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Rebuild from frozen facts and require byte-identical canonical output."""

    findings = list(validate_operation_review(artifact)["findings"])
    try:
        rebuilt = build_operation_review(
            episode_collection,
            event_inputs=event_inputs,
        )
    except Exception as exc:  # fail closed at the source-replay boundary
        findings.append(
            _finding(
                "OPERATION_REVIEW_REBUILD_FAILED",
                f"operation review rebuild failed: {type(exc).__name__}",
            )
        )
        rebuilt = None
    if rebuilt is not None:
        try:
            matches = (
                canonical_operation_review_bytes(rebuilt)
                == canonical_operation_review_bytes(artifact)
            )
        except Exception:
            matches = False
        if not matches:
            findings.append(
                _finding(
                    "OPERATION_REVIEW_SOURCE_REPLAY_MISMATCH",
                    "rebuilt operation review is not byte-identical",
                )
            )
    findings = sorted(
        {
            canonical_json(item): item
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


def query_operation_review(
    artifact: Mapping[str, Any],
    *,
    episode_id: str | None = None,
    operation_type: str | None = None,
    classification_status: str | None = None,
) -> list[dict[str, Any]]:
    """Query operation facts without changing the canonical artifact."""

    validation = validate_operation_review(artifact)
    if validation["validation_status"] != "accepted":
        raise OperationReviewError(
            "operation review validation blocked: "
            + ",".join(
                str(item.get("code") or "")
                for item in validation["findings"]
            )
        )
    operations = [
        deepcopy(dict(operation))
        for episode in artifact.get("episode_reviews", [])
        if isinstance(episode, Mapping)
        for operation in episode.get("operations", [])
        if isinstance(operation, Mapping)
    ] + [
        deepcopy(dict(operation))
        for operation in artifact.get("standalone_operations", [])
        if isinstance(operation, Mapping)
    ]
    result = [
        operation
        for operation in operations
        if (
            episode_id is None
            or operation.get("episode_id") == episode_id
        )
        and (
            operation_type is None
            or operation.get("operation_type") == operation_type
        )
        and (
            classification_status is None
            or operation.get("classification_status")
            == classification_status
        )
    ]
    return result
