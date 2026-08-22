"""Deterministic, facts-only ledger snapshot reconstruction.

This module is the additive P4 projection for the investment-review
reviewability overlay.  It never opens SQLite.  Callers must supply canonical
events that were read from the fully reconciled review sidecar and a source
binding produced by the read-only runner preflight.

The projection deliberately keeps position quantity, cost, cash, price, NAV,
weight and industry independent.  Missing cash or valuation evidence therefore
cannot hide a position that the ledger can prove.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence


LEDGER_SNAPSHOT_RECONSTRUCTION_SCHEMA_VERSION = (
    "investment_review.ledger_snapshot_reconstruction.v1"
)
LEDGER_SNAPSHOT_RECONSTRUCTION_METHOD_VERSION = (
    "deterministic_ledger_replay_v1"
)
LEDGER_SNAPSHOT_BASELINE_SCHEMA_VERSION = (
    "investment_review.ledger_snapshot_baseline.v1"
)
LEDGER_SNAPSHOT_RECONSTRUCTION_VALIDATION_SCHEMA_VERSION = (
    "investment_review.ledger_snapshot_reconstruction.validation.v1"
)
LEDGER_SNAPSHOT_RECONSTRUCTION_REPLAY_SCHEMA_VERSION = (
    "investment_review.ledger_snapshot_reconstruction.replay.v1"
)

__all__ = [
    "LEDGER_SNAPSHOT_RECONSTRUCTION_SCHEMA_VERSION",
    "LEDGER_SNAPSHOT_RECONSTRUCTION_METHOD_VERSION",
    "LEDGER_SNAPSHOT_BASELINE_SCHEMA_VERSION",
    "LEDGER_SNAPSHOT_RECONSTRUCTION_VALIDATION_SCHEMA_VERSION",
    "LEDGER_SNAPSHOT_RECONSTRUCTION_REPLAY_SCHEMA_VERSION",
    "LedgerSnapshotReconstructionError",
    "build_ledger_snapshot_reconstruction",
    "canonical_ledger_snapshot_reconstruction_bytes",
    "validate_ledger_snapshot_reconstruction",
    "replay_validate_ledger_snapshot_reconstruction",
]


class LedgerSnapshotReconstructionError(ValueError):
    """Raised when source inputs cannot be projected without guessing."""


_SHA256_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
_SOURCE_BINDING_INPUT_FIELDS = {
    "portfolio_source_sha256",
    "sync_source_sha256",
    "mapping_sha256",
    "source_cutoff_id",
    "sidecar_projection_sha256",
    "knowledge_provenance_content_id",
    "cash_baseline_proof_content_id",
}
_SOURCE_BINDING_FIELDS = {
    "proof",
    "event_input_count",
    "event_input_content_id",
    "scope_event_count",
    "scope_event_content_id",
    "episode_event_ids",
}
_ROOT_FIELDS = {
    "schema_version",
    "method_version",
    "content_id",
    "episode_id",
    "perspective",
    "as_of",
    "knowledge_cutoff",
    "scope",
    "source_binding",
    "baseline",
    "event_cursor",
    "anchors",
    "gaps",
    "governance",
}
_SCOPE_FIELDS = {"account_id", "symbol", "instrument_id", "currency"}
_BASELINE_FIELDS = {"schema_version", "position", "cash"}
_POSITION_BASELINE_FIELDS = {
    "status",
    "quantity",
    "cost_basis",
    "effective_at",
    "known_at",
    "method",
    "source_refs",
}
_CASH_BASELINE_FIELDS = {
    "status",
    "value",
    "currency",
    "effective_at",
    "known_at",
    "recorded_at",
    "fee_pending",
    "method",
    "source_refs",
}
_CURSOR_FIELDS = {
    "cursor_scope",
    "account_event_set_complete",
    "partition_event_set_complete",
    "input_event_ids",
    "account_event_ids",
    "scope_event_ids",
    "included_account_event_ids",
    "included_event_ids",
    "excluded_after_as_of_ids",
    "excluded_future_known_ids",
    "episode_boundary_mode",
    "episode_boundary_event_id",
    "episode_boundary_ordering_key",
    "visible_account_event_ids",
    "visible_event_ids",
    "excluded_by_episode_cursor_ids",
    "same_time_groups",
    "source_refs",
}
_SAME_TIME_GROUP_FIELDS = {
    "effective_at",
    "event_ids",
    "ordering_status",
    "basis",
}
_ANCHOR_FIELDS = {
    "anchor_id",
    "anchor_type",
    "event_id",
    "effective_at",
    "ordering_status",
    "same_time_event_ids",
    "position",
    "snapshot_cash_valuation",
    "source_refs",
    "gaps",
}
_POSITION_FIELDS = {
    "symbol",
    "quantity",
    "cost_basis",
    "quantity_status",
    "cost_basis_status",
}
_SNAPSHOT_AXIS_FIELDS = {"status", "fields", "source_refs", "summary"}
_SNAPSHOT_FIELD_NAMES = (
    "position_quantity",
    "cost_basis",
    "cash",
    "price",
    "nav",
    "weight",
    "industry",
)
_SNAPSHOT_FIELD_FIELDS = {"status", "value", "unit", "source_refs"}
_GAP_FIELDS = {
    "axis",
    "code",
    "severity",
    "blocks_axis",
    "owner",
    "next_step",
    "source_refs",
}
_GOVERNANCE = {
    "facts_only": True,
    "source_database_write_allowed": False,
    "snapshot_table_write_allowed": False,
    "network_allowed": False,
    "model_allowed": False,
    "motive_inference_allowed": False,
    "advice_allowed": False,
}
_POSITION_SIDES = {
    "BUY": Decimal("1"),
    "SELL": Decimal("-1"),
    "TRANSFER_IN": Decimal("1"),
    "TRANSFER_OUT": Decimal("-1"),
}
_SUPPORTED_EVENT_TYPES = {"buy", "sell", "opening", "dividend", "cash_fee"}
_POSITION_EVENT_SIDES = {
    "buy": {"BUY"},
    "sell": {"SELL"},
    "opening": {"BUY", "TRANSFER_IN"},
}


def _freeze(value: object, *, field: str = "value") -> Any:
    if isinstance(value, float):
        raise LedgerSnapshotReconstructionError(
            f"{field} must not contain a binary float"
        )
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise LedgerSnapshotReconstructionError(
                f"{field} contains an invalid Unicode surrogate"
            ) from exc
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise LedgerSnapshotReconstructionError(
                    f"{field} object keys must be strings"
                )
            result[key] = _freeze(item, field=f"{field}.{key}")
        return result
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return [
            _freeze(item, field=f"{field}[{index}]")
            for index, item in enumerate(value)
        ]
    raise LedgerSnapshotReconstructionError(
        f"{field} contains unsupported value {type(value).__name__}"
    )


def _canonical_bytes(value: object) -> bytes:
    frozen = _freeze(value)
    try:
        return json.dumps(
            frozen,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise LedgerSnapshotReconstructionError(
            "value is not strict canonical JSON"
        ) from exc


def _content_id(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _timestamp(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LedgerSnapshotReconstructionError(f"{field} is required")
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise LedgerSnapshotReconstructionError(
            f"{field} must be an ISO 8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LedgerSnapshotReconstructionError(
            f"{field} must include a timezone"
        )
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat(
        timespec="seconds"
    )


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _decimal(value: object, *, field: str) -> Decimal | None:
    if value in (None, ""):
        return None
    if isinstance(value, (bool, float)):
        raise LedgerSnapshotReconstructionError(
            f"{field} must not be a binary float or boolean"
        )
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise LedgerSnapshotReconstructionError(
            f"{field} is not a decimal"
        ) from exc
    if not result.is_finite():
        raise LedgerSnapshotReconstructionError(
            f"{field} must be finite"
        )
    return result


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _raw_payload(value: object) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value, parse_float=Decimal)
        except json.JSONDecodeError as exc:
            raise LedgerSnapshotReconstructionError(
                "raw_payload_json is invalid"
            ) from exc
        if not isinstance(parsed, Mapping):
            raise LedgerSnapshotReconstructionError(
                "raw_payload_json must decode to an object"
            )
        return dict(_freeze(parsed, field="raw_payload"))
    if isinstance(value, Mapping):
        return dict(_freeze(value, field="raw_payload"))
    raise LedgerSnapshotReconstructionError(
        "raw_payload must be an object"
    )


def _source_refs(event: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            f"event:{event['event_id']}",
            f"source:{event['source_id']}",
            f"payload:sha256:{event['payload_sha256']}",
        }
    )


def _event(value: Mapping[str, Any]) -> dict[str, Any]:
    event_id = str(value.get("event_id") or "").strip()
    source_id = str(value.get("source_id") or "").strip()
    account = str(value.get("account") or "").strip()
    symbol = str(value.get("symbol") or "").strip().upper()
    side = str(value.get("side") or "").strip().upper()
    event_type = str(value.get("event_type") or "").strip().lower()
    currency = str(value.get("currency") or "").strip().upper()
    if (
        not event_id
        or not source_id
        or not account
        or not symbol
        or not currency
    ):
        raise LedgerSnapshotReconstructionError(
            "event_id/source_id/account/symbol/currency are required"
        )
    payload_sha = str(value.get("payload_sha256") or "").strip()
    if not re.fullmatch(r"[0-9a-f]{64}", payload_sha):
        raise LedgerSnapshotReconstructionError(
            f"event {event_id} has invalid payload_sha256"
        )
    occurred = _timestamp(value.get("occurred_at"), field="occurred_at")
    known = _timestamp(value.get("known_at"), field="known_at")
    if _dt(known) < _dt(occurred):
        raise LedgerSnapshotReconstructionError(
            f"event {event_id} known_at precedes occurred_at"
        )
    raw = _raw_payload(
        value.get("raw_payload", value.get("raw_payload_json"))
    )
    quantity = _decimal(value.get("quantity"), field=f"{event_id}.quantity")
    price = _decimal(value.get("price"), field=f"{event_id}.price")
    gross = _decimal(
        value.get("gross_amount"), field=f"{event_id}.gross_amount"
    )
    cash = _decimal(
        value.get("cash_amount"), field=f"{event_id}.cash_amount"
    )
    fees = _decimal(value.get("fees"), field=f"{event_id}.fees")
    normalized = {
        "event_id": event_id,
        "source_id": source_id,
        "source_record_id": (
            str(value.get("source_record_id")).strip()
            if value.get("source_record_id") not in (None, "")
            else None
        ),
        "payload_sha256": payload_sha,
        "event_type": event_type,
        "occurred_at": occurred,
        "known_at": known,
        "account": account,
        "symbol": symbol,
        "side": side,
        "quantity": _decimal_text(quantity) if quantity is not None else None,
        "price": _decimal_text(price) if price is not None else None,
        "gross_amount": _decimal_text(gross) if gross is not None else None,
        "cash_amount": _decimal_text(cash) if cash is not None else None,
        "fees": _decimal_text(fees) if fees is not None else None,
        "currency": currency,
        "raw_payload": raw,
        "full_input": _freeze(dict(value), field=f"event[{event_id}]"),
    }
    normalized["source_refs"] = _source_refs(normalized)
    return normalized


def _dedupe_events(
    event_inputs: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for raw in event_inputs:
        if not isinstance(raw, Mapping):
            raise LedgerSnapshotReconstructionError(
                "event inputs must contain objects"
            )
        item = _event(raw)
        buckets.setdefault(item["event_id"], []).append(item)
    result: list[dict[str, Any]] = []
    for event_id, occurrences in sorted(buckets.items()):
        fingerprints = {
            _content_id(item["full_input"]) for item in occurrences
        }
        if len(fingerprints) != 1:
            raise LedgerSnapshotReconstructionError(
                f"conflicting duplicate event_id: {event_id}"
            )
        result.append(occurrences[0])
    return result


def _episode_scope(
    episode: Mapping[str, Any],
) -> tuple[str, str, str, str, str, list[str]]:
    episode_id = str(episode.get("episode_id") or "").strip()
    scope = episode.get("scope")
    if not episode_id or not isinstance(scope, Mapping):
        raise LedgerSnapshotReconstructionError(
            "episode_id and episode.scope are required"
        )
    account = str(
        scope.get("account_id", scope.get("account")) or ""
    ).strip()
    symbol = str(
        scope.get("symbol", scope.get("instrument_id")) or ""
    ).strip().upper()
    instrument = str(scope.get("instrument_id") or symbol).strip().upper()
    currency = str(scope.get("currency") or "").strip().upper()
    if not account or not symbol or not currency:
        raise LedgerSnapshotReconstructionError(
            "episode scope requires account_id, symbol and currency"
        )
    raw_refs = episode.get("event_refs", [])
    if not isinstance(raw_refs, Sequence) or isinstance(
        raw_refs, (str, bytes, bytearray)
    ):
        raise LedgerSnapshotReconstructionError(
            "episode.event_refs must be a list"
        )
    event_ids: list[str] = []
    for item in raw_refs:
        event_id = (
            str(item.get("event_id") or "").strip()
            if isinstance(item, Mapping)
            else str(item).strip()
        )
        if not event_id:
            raise LedgerSnapshotReconstructionError(
                "episode event ref is missing event_id"
            )
        event_ids.append(event_id)
    if len(event_ids) != len(set(event_ids)):
        raise LedgerSnapshotReconstructionError(
            "episode event refs must be unique"
        )
    if not event_ids:
        raise LedgerSnapshotReconstructionError(
            "episode requires at least one event ref"
        )
    return episode_id, account, symbol, instrument, currency, event_ids


def _normalize_source_binding(
    value: Mapping[str, Any],
) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise LedgerSnapshotReconstructionError(
            "source_binding must be an object"
        )
    missing = _SOURCE_BINDING_INPUT_FIELDS - set(value)
    extra = set(value) - _SOURCE_BINDING_INPUT_FIELDS
    if missing or extra:
        raise LedgerSnapshotReconstructionError(
            "source_binding has an unexpected shape"
        )
    result = {key: str(value.get(key) or "").strip() for key in sorted(value)}
    if any(not item for item in result.values()):
        raise LedgerSnapshotReconstructionError(
            "source_binding values must be non-empty"
        )
    for key in (
        "portfolio_source_sha256",
        "sync_source_sha256",
        "mapping_sha256",
        "sidecar_projection_sha256",
        "knowledge_provenance_content_id",
        "cash_baseline_proof_content_id",
    ):
        if not _SHA256_RE.fullmatch(result[key]):
            raise LedgerSnapshotReconstructionError(
                f"source_binding.{key} must be a SHA-256 identifier"
            )
    return result


def _missing_baseline() -> dict[str, Any]:
    return {
        "schema_version": LEDGER_SNAPSHOT_BASELINE_SCHEMA_VERSION,
        "position": {
            "status": "missing",
            "quantity": None,
            "cost_basis": None,
            "effective_at": None,
            "known_at": None,
            "method": "missing",
            "source_refs": [],
        },
        "cash": {
            "status": "missing",
            "value": None,
            "currency": "CNY",
            "effective_at": None,
            "known_at": None,
            "recorded_at": None,
            "fee_pending": False,
            "method": "missing",
            "source_refs": [],
        },
    }


def _normalize_baseline(
    value: Mapping[str, Any] | None,
    *,
    currency: str,
    as_of: str,
    knowledge_cutoff: str,
) -> dict[str, Any]:
    if value is None:
        result = _missing_baseline()
        result["cash"]["currency"] = currency
        return result
    result = deepcopy(dict(value))
    if set(result) != _BASELINE_FIELDS:
        raise LedgerSnapshotReconstructionError(
            "baseline_proof has an unexpected shape"
        )
    if (
        result.get("schema_version")
        != LEDGER_SNAPSHOT_BASELINE_SCHEMA_VERSION
    ):
        raise LedgerSnapshotReconstructionError(
            "baseline_proof schema_version is unsupported"
        )
    position = result.get("position")
    cash = result.get("cash")
    if (
        not isinstance(position, Mapping)
        or set(position) != _POSITION_BASELINE_FIELDS
        or not isinstance(cash, Mapping)
        or set(cash) != _CASH_BASELINE_FIELDS
    ):
        raise LedgerSnapshotReconstructionError(
            "baseline position/cash shape is invalid"
        )
    position = deepcopy(dict(position))
    cash = deepcopy(dict(cash))
    if not isinstance(cash.get("currency"), str) or not cash[
        "currency"
    ].strip():
        raise LedgerSnapshotReconstructionError(
            "baseline cash currency is required"
        )
    if position["status"] not in {"available", "missing"}:
        raise LedgerSnapshotReconstructionError(
            "baseline position status is invalid"
        )
    if cash["status"] not in {"available", "partial", "missing"}:
        raise LedgerSnapshotReconstructionError(
            "baseline cash status is invalid"
        )
    for part in (position, cash):
        refs = part.get("source_refs")
        if not isinstance(refs, list) or any(
            not isinstance(item, str) or not item for item in refs
        ):
            raise LedgerSnapshotReconstructionError(
                "baseline source_refs are invalid"
            )
        part["source_refs"] = sorted(set(refs))
    if position["status"] == "available":
        if (
            not isinstance(position.get("method"), str)
            or not position["method"].strip()
            or position["method"] == "missing"
        ):
            raise LedgerSnapshotReconstructionError(
                "available position baseline needs an explicit method"
            )
        quantity = _decimal(
            position.get("quantity"), field="baseline.position.quantity"
        )
        cost = _decimal(
            position.get("cost_basis"),
            field="baseline.position.cost_basis",
        )
        if quantity is None or cost is None or not position["source_refs"]:
            raise LedgerSnapshotReconstructionError(
                "available position baseline needs values and source_refs"
            )
        if quantity < 0 or cost < 0:
            raise LedgerSnapshotReconstructionError(
                "position baseline quantity/cost cannot be negative"
            )
        if quantity == 0 and cost != 0:
            raise LedgerSnapshotReconstructionError(
                "zero position baseline requires zero cost"
            )
        position["quantity"] = _decimal_text(quantity)
        position["cost_basis"] = _decimal_text(cost)
        for field in ("effective_at", "known_at"):
            position[field] = _timestamp(
                position.get(field), field=f"baseline.position.{field}"
            )
            if _dt(position[field]) > _dt(knowledge_cutoff):
                raise LedgerSnapshotReconstructionError(
                    f"baseline.position.{field} exceeds knowledge_cutoff"
                )
        if _dt(position["effective_at"]) > _dt(as_of):
            raise LedgerSnapshotReconstructionError(
                "baseline.position.effective_at exceeds as_of"
            )
        if _dt(position["known_at"]) < _dt(position["effective_at"]):
            raise LedgerSnapshotReconstructionError(
                "baseline.position.known_at precedes effective_at"
            )
    else:
        position["quantity"] = None
        position["cost_basis"] = None
        position["effective_at"] = None
        position["known_at"] = None
        position["method"] = "missing"
        position["source_refs"] = []
    if cash["status"] in {"available", "partial"}:
        if (
            not isinstance(cash.get("method"), str)
            or not cash["method"].strip()
            or cash["method"] == "missing"
        ):
            raise LedgerSnapshotReconstructionError(
                "cash baseline needs an explicit method"
            )
        amount = _decimal(cash.get("value"), field="baseline.cash.value")
        if amount is None or not cash["source_refs"]:
            raise LedgerSnapshotReconstructionError(
                "cash baseline needs value and source_refs"
            )
        cash["value"] = _decimal_text(amount)
        for field in ("effective_at", "known_at", "recorded_at"):
            cash[field] = _timestamp(
                cash.get(field), field=f"baseline.cash.{field}"
            )
            if _dt(cash[field]) > _dt(knowledge_cutoff):
                raise LedgerSnapshotReconstructionError(
                    f"baseline.cash.{field} exceeds knowledge_cutoff"
                )
        if _dt(cash["effective_at"]) > _dt(as_of):
            raise LedgerSnapshotReconstructionError(
                "baseline.cash.effective_at exceeds as_of"
            )
        if _dt(cash["known_at"]) < _dt(cash["effective_at"]):
            raise LedgerSnapshotReconstructionError(
                "baseline.cash.known_at precedes effective_at"
            )
        if _dt(cash["recorded_at"]) < _dt(cash["effective_at"]):
            raise LedgerSnapshotReconstructionError(
                "baseline.cash.recorded_at precedes effective_at"
            )
        if not isinstance(cash.get("fee_pending"), bool):
            raise LedgerSnapshotReconstructionError(
                "baseline.cash.fee_pending must be boolean"
            )
        if cash["fee_pending"]:
            cash["status"] = "partial"
    else:
        cash["value"] = None
        cash["effective_at"] = None
        cash["known_at"] = None
        cash["recorded_at"] = None
        cash["fee_pending"] = False
        cash["method"] = "missing"
        cash["source_refs"] = []
    cash["currency"] = str(cash.get("currency") or currency).upper()
    if cash["currency"] != currency:
        raise LedgerSnapshotReconstructionError(
            "cash baseline currency mismatch requires explicit FX evidence"
        )
    return {
        "schema_version": LEDGER_SNAPSHOT_BASELINE_SCHEMA_VERSION,
        "position": position,
        "cash": cash,
    }


def _source_row(event: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = event.get("raw_payload")
    if not isinstance(raw, Mapping):
        return {}
    row = raw.get("source_row", raw)
    return row if isinstance(row, Mapping) else {}


def _fee_is_complete(event: Mapping[str, Any]) -> bool:
    fees = _decimal(event.get("fees"), field="fees")
    if fees is None or fees <= 0:
        return False
    row = _source_row(event)
    note = str(row.get("note") or "").lower()
    return "fees_missing=true" not in note and "fee_pending" not in note


def _sequence_value(
    value: object,
    *,
    field: str,
) -> tuple[int, str]:
    if isinstance(value, bool):
        raise LedgerSnapshotReconstructionError(
            f"{field} must not be boolean"
        )
    try:
        return (0, f"{int(str(value)):020d}")
    except (TypeError, ValueError):
        text = str(value).strip()
        if not text:
            raise LedgerSnapshotReconstructionError(
                f"{field} is empty"
            )
        return (1, text)


def _business_sequence(
    event: Mapping[str, Any],
) -> tuple[int, str] | None:
    raw = event.get("raw_payload")
    row = _source_row(event)

    # P2C may use source_sequence/source_row/entry_id/row_index as stable
    # classification tie-breakers.  They are not explicit business sequence
    # evidence and must not make P4 event anchors look ordered.
    alias_values: list[tuple[int, str]] = []
    for key in ("business_sequence", "execution_sequence"):
        if isinstance(raw, Mapping) and raw.get(key) not in (None, ""):
            alias_values.append(
                _sequence_value(raw[key], field=key)
            )
        if row.get(key) not in (None, ""):
            alias_values.append(
                _sequence_value(row[key], field=key)
            )
    if alias_values:
        if len(set(alias_values)) != 1:
            raise LedgerSnapshotReconstructionError(
                "conflicting business sequence evidence"
            )
        return alias_values[0]
    return None


def _p2c_ordering_key(
    event: Mapping[str, Any],
) -> tuple[datetime, int, str, str]:
    event_id = str(event.get("event_id") or "")
    row = _source_row(event)
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
        _dt(str(event["occurred_at"])),
        sequence_rank,
        sequence_value,
        event_id,
    )


def _episode_boundary(
    episode: Mapping[str, Any],
    *,
    event_map: Mapping[str, Mapping[str, Any]],
    as_of: str,
) -> tuple[
    str,
    str | None,
    tuple[datetime, int, str, str] | None,
    list[Any] | None,
]:
    status = str(episode.get("status") or "")
    if status not in {"open", "closed"}:
        return "request_as_of", None, None, None
    if status == "open":
        if episode.get("closed_at") not in (None, ""):
            raise LedgerSnapshotReconstructionError(
                "open episode has an unexpected closed_at"
            )
        return "request_as_of", None, None, None
    closed_at = _timestamp(
        episode.get("closed_at"), field="episode.closed_at"
    )
    if closed_at != as_of:
        raise LedgerSnapshotReconstructionError(
            "closed episode reconstruction as_of must equal closed_at"
        )
    closing_event_id = str(
        episode.get("closing_event_ref") or ""
    ).strip()
    closing_event = event_map.get(closing_event_id)
    if not closing_event_id or not isinstance(closing_event, Mapping):
        raise LedgerSnapshotReconstructionError(
            "closed episode closing event is missing"
        )
    actual_key = _p2c_ordering_key(closing_event)
    closing_refs = [
        item
        for item in episode.get("event_refs", [])
        if (
            isinstance(item, Mapping)
            and str(item.get("event_id") or "") == closing_event_id
        )
    ]
    if len(closing_refs) != 1:
        raise LedgerSnapshotReconstructionError(
            "closed episode needs one closing event ref"
        )
    raw_key = closing_refs[0].get("ordering_key")
    if (
        not isinstance(raw_key, list)
        or len(raw_key) != 4
        or isinstance(raw_key[1], bool)
    ):
        raise LedgerSnapshotReconstructionError(
            "closed episode lacks a canonical P2C ordering cursor"
        )
    try:
        expected_key = (
            _dt(
                _timestamp(
                    raw_key[0],
                    field="episode.closing.ordering_key[0]",
                )
            ),
            int(raw_key[1]),
            str(raw_key[2]),
            str(raw_key[3]),
        )
    except (TypeError, ValueError) as exc:
        raise LedgerSnapshotReconstructionError(
            "closed episode P2C ordering cursor is invalid"
        ) from exc
    if (
        expected_key != actual_key
        or expected_key[1] not in {0, 1, 2}
        or not expected_key[2]
        or expected_key[3] != closing_event_id
        or _timestamp(
            closing_refs[0].get("effective_at"),
            field="episode.closing.effective_at",
        )
        != closed_at
    ):
        raise LedgerSnapshotReconstructionError(
            "closed episode cursor disagrees with source event"
        )
    serialized_key: list[Any] = [
        closed_at,
        expected_key[1],
        expected_key[2],
        expected_key[3],
    ]
    return (
        "closed_episode_cursor",
        closing_event_id,
        expected_key,
        serialized_key,
    )


def _ordered_group(
    group: Sequence[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    sequences = [_business_sequence(item) for item in group]
    explicit = (
        len(group) == 1
        or (
            all(value is not None for value in sequences)
            and len(set(sequences)) == len(sequences)
        )
    )
    if explicit and len(group) > 1:
        ordered = sorted(
            group,
            key=lambda item: (
                _business_sequence(item),
                item["event_id"],
            ),
        )
    else:
        # Stable identity is a byte-ordering device only.  Callers must not
        # use this order to derive business-state transitions.
        ordered = sorted(group, key=lambda item: item["event_id"])
    return ("proven" if explicit else "ambiguous"), ordered


def _field(
    status: str,
    value: str | None,
    unit: str | None,
    refs: Iterable[str] = (),
) -> dict[str, Any]:
    return {
        "status": status,
        "value": value,
        "unit": unit,
        "source_refs": sorted(set(refs)),
    }


def _gap(
    code: str,
    *,
    severity: str = "warning",
    blocks_axis: bool = False,
    refs: Iterable[str] = (),
    owner: str = "data_owner",
    next_step: str,
) -> dict[str, Any]:
    return {
        "axis": "snapshot_cash_valuation",
        "code": code,
        "severity": severity,
        "blocks_axis": blocks_axis,
        "owner": owner,
        "next_step": next_step,
        "source_refs": sorted(set(refs)),
    }


def _axis(
    *,
    quantity: Decimal | None,
    quantity_status: str,
    cost: Decimal | None,
    cost_status: str,
    cash: Decimal | None,
    cash_status: str,
    currency: str,
    position_refs: Iterable[str],
    cash_refs: Iterable[str],
    blocked: bool,
) -> dict[str, Any]:
    fields = {
        "position_quantity": _field(
            quantity_status,
            (
                _decimal_text(quantity)
                if quantity is not None
                and quantity_status in {"available", "partial"}
                else None
            ),
            "shares",
            position_refs if quantity_status in {"available", "partial"} else (),
        ),
        "cost_basis": _field(
            (
                "not_applicable"
                if quantity == 0 and quantity_status == "available"
                else cost_status
            ),
            (
                None
                if quantity == 0 and quantity_status == "available"
                else (
                    _decimal_text(cost)
                    if cost is not None
                    and cost_status in {"available", "partial"}
                    else None
                )
            ),
            currency,
            (
                ()
                if quantity == 0 and quantity_status == "available"
                else position_refs
                if cost_status in {"available", "partial"}
                else ()
            ),
        ),
        "cash": _field(
            cash_status,
            (
                _decimal_text(cash)
                if cash is not None
                and cash_status in {"available", "partial"}
                else None
            ),
            currency,
            cash_refs if cash_status in {"available", "partial"} else (),
        ),
        "price": _field("missing", None, f"{currency}/share"),
        "nav": _field("missing", None, currency),
        "weight": _field("missing", None, "ratio"),
        "industry": _field("missing", None, None),
    }
    statuses = [item["status"] for item in fields.values()]
    if blocked:
        status = "blocked"
    elif all(item in {"missing", "not_applicable"} for item in statuses):
        status = "missing"
    elif all(item in {"available", "not_applicable"} for item in statuses):
        status = "available"
    else:
        status = "partial"
    refs = sorted(
        {
            ref
            for item in fields.values()
            for ref in item["source_refs"]
        }
    )
    return {
        "status": status,
        "fields": fields,
        "source_refs": refs,
        "summary": (
            "持仓数量与成本、现金及估值组件分别报告；缺失组件未补零。"
        ),
    }


def _anchor(
    *,
    episode_id: str,
    anchor_type: str,
    event_id: str | None,
    effective_at: str,
    ordering_status: str,
    same_time_event_ids: Sequence[str],
    symbol: str,
    quantity: Decimal | None,
    quantity_status: str,
    cost: Decimal | None,
    cost_status: str,
    cash: Decimal | None,
    cash_status: str,
    currency: str,
    position_refs: Iterable[str],
    cash_refs: Iterable[str],
    gaps: Sequence[Mapping[str, Any]],
    blocked: bool,
) -> dict[str, Any]:
    axis = _axis(
        quantity=quantity,
        quantity_status=quantity_status,
        cost=cost,
        cost_status=cost_status,
        cash=cash,
        cash_status=cash_status,
        currency=currency,
        position_refs=position_refs,
        cash_refs=cash_refs,
        blocked=blocked,
    )
    material = {
        "episode_id": episode_id,
        "anchor_type": anchor_type,
        "event_id": event_id,
        "effective_at": effective_at,
    }
    return {
        "anchor_id": "ledger_anchor_" + _content_id(material)[7:39],
        "anchor_type": anchor_type,
        "event_id": event_id,
        "effective_at": effective_at,
        "ordering_status": ordering_status,
        "same_time_event_ids": list(same_time_event_ids),
        "position": {
            "symbol": symbol,
            "quantity": (
                _decimal_text(quantity)
                if quantity is not None
                and quantity_status in {"available", "partial"}
                else None
            ),
            "cost_basis": (
                _decimal_text(cost)
                if cost is not None
                and cost_status in {"available", "partial"}
                else None
            ),
            "quantity_status": quantity_status,
            "cost_basis_status": cost_status,
        },
        "snapshot_cash_valuation": axis,
        "source_refs": axis["source_refs"],
        "gaps": [deepcopy(dict(item)) for item in gaps],
    }


def build_ledger_snapshot_reconstruction(
    event_inputs: Iterable[Mapping[str, Any]],
    *,
    episode: Mapping[str, Any],
    perspective: str,
    as_of: str,
    knowledge_cutoff: str,
    source_binding: Mapping[str, Any],
    baseline_proof: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one immutable episode-scoped pre/post/cutoff projection."""

    if perspective not in {"user", "system"}:
        raise LedgerSnapshotReconstructionError(
            "perspective must be user or system"
        )
    canonical_as_of = _timestamp(as_of, field="as_of")
    canonical_cutoff = _timestamp(
        knowledge_cutoff, field="knowledge_cutoff"
    )
    if _dt(canonical_as_of) > _dt(canonical_cutoff):
        raise LedgerSnapshotReconstructionError(
            "as_of cannot exceed knowledge_cutoff"
        )
    (
        episode_id,
        account,
        symbol,
        instrument,
        currency,
        episode_event_ids,
    ) = _episode_scope(episode)
    proof = _normalize_source_binding(source_binding)
    events = _dedupe_events(event_inputs)
    event_map = {item["event_id"]: item for item in events}
    missing_episode_ids = sorted(set(episode_event_ids) - set(event_map))
    if missing_episode_ids:
        raise LedgerSnapshotReconstructionError(
            "episode event ids are missing from canonical inputs: "
            + ",".join(missing_episode_ids)
        )
    account_events = [
        item for item in events if item["account"] == account
    ]
    account_events.sort(
        key=lambda item: (item["occurred_at"], item["event_id"])
    )
    scope_events = [
        item
        for item in account_events
        if item["symbol"] == symbol
    ]
    scope_events.sort(
        key=lambda item: (item["occurred_at"], item["event_id"])
    )
    (
        episode_boundary_mode,
        episode_boundary_event_id,
        episode_boundary_key,
        episode_boundary_ordering_key,
    ) = _episode_boundary(
        episode,
        event_map=event_map,
        as_of=canonical_as_of,
    )
    visible_account_events = [
        item
        for item in account_events
        if (
            _dt(item["occurred_at"]) <= _dt(canonical_as_of)
            and _dt(item["known_at"]) <= _dt(canonical_cutoff)
        )
    ]
    visible_scope_events = [
        item
        for item in scope_events
        if (
            _dt(item["occurred_at"]) <= _dt(canonical_as_of)
            and _dt(item["known_at"]) <= _dt(canonical_cutoff)
        )
    ]
    included_account_events = [
        item
        for item in visible_account_events
        if (
            episode_boundary_key is None
            or _p2c_ordering_key(item) <= episode_boundary_key
        )
    ]
    included = [
        item
        for item in visible_scope_events
        if (
            episode_boundary_key is None
            or _p2c_ordering_key(item) <= episode_boundary_key
        )
    ]
    excluded = [
        item["event_id"]
        for item in scope_events
        if _dt(item["occurred_at"]) > _dt(canonical_as_of)
    ]
    excluded_future_known = [
        item["event_id"]
        for item in account_events
        if (
            _dt(item["occurred_at"]) <= _dt(canonical_as_of)
            and _dt(item["known_at"]) > _dt(canonical_cutoff)
        )
    ]
    included_account_ids = {
        item["event_id"] for item in included_account_events
    }
    excluded_by_episode_cursor = [
        item["event_id"]
        for item in visible_account_events
        if item["event_id"] not in included_account_ids
    ]
    included_ids = {item["event_id"] for item in included}
    if not set(episode_event_ids).issubset(included_ids):
        raise LedgerSnapshotReconstructionError(
            "episode contains an event after as_of"
        )
    for item in visible_account_events:
        allowed_sides = _POSITION_EVENT_SIDES.get(item["event_type"])
        if allowed_sides is not None and item["side"] not in allowed_sides:
            raise LedgerSnapshotReconstructionError(
                f"event {item['event_id']} event_type/side semantics conflict"
            )
        gross = _decimal(
            item["gross_amount"],
            field=f"{item['event_id']}.gross_amount",
        )
        fees = _decimal(
            item["fees"], field=f"{item['event_id']}.fees"
        )
        if item["event_type"] in {"buy", "sell"} and (
            gross is not None and gross <= 0
        ):
            raise LedgerSnapshotReconstructionError(
                f"event {item['event_id']} gross_amount must be positive"
            )
        if fees is not None and fees < 0:
            raise LedgerSnapshotReconstructionError(
                f"event {item['event_id']} fees cannot be negative"
            )
    mismatched_scope_currencies = sorted(
        item["event_id"]
        for item in visible_scope_events
        if item["currency"] != currency
    )
    if mismatched_scope_currencies:
        raise LedgerSnapshotReconstructionError(
            "event currency mismatch requires explicit FX evidence: "
            + ",".join(mismatched_scope_currencies)
        )
    baseline = _normalize_baseline(
        baseline_proof,
        currency=currency,
        as_of=canonical_as_of,
        knowledge_cutoff=canonical_cutoff,
    )
    if baseline["cash"]["status"] in {"available", "partial"}:
        cash_effective_at = _dt(baseline["cash"]["effective_at"])
        mismatched_cash_currencies = sorted(
            item["event_id"]
            for item in included_account_events
            if (
                _dt(item["occurred_at"]) > cash_effective_at
                and item["currency"] != currency
            )
        )
        if mismatched_cash_currencies:
            raise LedgerSnapshotReconstructionError(
                "account cash event currency mismatch requires explicit FX "
                "evidence: "
                + ",".join(mismatched_cash_currencies)
            )
    first_episode_at = min(
        _dt(event_map[event_id]["occurred_at"])
        for event_id in episode_event_ids
    )
    for baseline_name in ("position", "cash"):
        baseline_part = baseline[baseline_name]
        if baseline_part["status"] in {"available", "partial"} and (
            _dt(baseline_part["effective_at"]) >= first_episode_at
        ):
            raise LedgerSnapshotReconstructionError(
                f"baseline.{baseline_name}.effective_at must precede "
                "the first episode event"
            )

    quantity: Decimal | None = None
    cost: Decimal | None = None
    quantity_status = "partial"
    cost_status = "missing"
    position_refs: set[str] = set()
    if baseline["position"]["status"] == "available":
        quantity = _decimal(
            baseline["position"]["quantity"], field="baseline.quantity"
        )
        cost = _decimal(
            baseline["position"]["cost_basis"], field="baseline.cost_basis"
        )
        quantity_status = "available"
        cost_status = "available"
        position_refs.update(baseline["position"]["source_refs"])
    else:
        # Keep a ledger delta internally.  It becomes an absolute,
        # episode-scoped quantity only after an earlier complete round trip
        # proves a flat boundary.
        quantity = Decimal("0")
        cost = Decimal("0")

    cash = (
        _decimal(baseline["cash"]["value"], field="baseline.cash.value")
        if baseline["cash"]["status"] in {"available", "partial"}
        else None
    )
    cash_status = baseline["cash"]["status"]
    cash_refs: set[str] = set(baseline["cash"]["source_refs"])
    cash_partial_reasons: set[str] = set()
    if cash_status == "partial":
        cash_partial_reasons.add(
            "fee_unknown"
            if baseline["cash"]["fee_pending"]
            else "baseline_partial"
        )
    position_baseline_time = (
        _dt(baseline["position"]["effective_at"])
        if baseline["position"]["status"] == "available"
        else None
    )
    cash_baseline_time = (
        _dt(baseline["cash"]["effective_at"])
        if baseline["cash"]["status"] in {"available", "partial"}
        else None
    )
    blocked = False
    cost_complete = cost_status == "available"
    cost_fee_unknown = False
    prior_open_seen = quantity is not None and quantity > 0
    prior_flat_refs: set[str] = set()

    # Cash is account-scoped, not instrument-scoped.  Reconstruct it from every
    # cutoff-visible account event after the explicit baseline.  A proven
    # business sequence yields per-event anchors; an unsequenced same-time
    # batch yields only a commutative checkpoint total, never an ID-derived
    # event pre/post balance.
    cash_by_time: dict[str, dict[str, Any]] = {}
    cash_event_states: dict[str, dict[str, Any]] = {}
    account_group_meta: dict[
        str, tuple[str, list[dict[str, Any]]]
    ] = {}
    account_evidence_by_time: dict[str, list[dict[str, Any]]] = {}
    for item in visible_account_events:
        account_evidence_by_time.setdefault(
            item["occurred_at"], []
        ).append(item)
    for occurred_at, evidence_group in sorted(
        account_evidence_by_time.items()
    ):
        account_group_meta[occurred_at] = _ordered_group(
            evidence_group
        )
    account_by_time: dict[str, list[dict[str, Any]]] = {}
    for item in included_account_events:
        account_by_time.setdefault(item["occurred_at"], []).append(item)

    def apply_cash_event(cash_event: Mapping[str, Any]) -> None:
        nonlocal cash, cash_status
        event_type = cash_event["event_type"]
        gross = _decimal(
            cash_event["gross_amount"],
            field=f"{cash_event['event_id']}.gross_amount",
        )
        fees = _decimal(
            cash_event["fees"],
            field=f"{cash_event['event_id']}.fees",
        )
        cash_amount = _decimal(
            cash_event["cash_amount"],
            field=f"{cash_event['event_id']}.cash_amount",
        )
        if event_type == "buy" and gross is not None:
            cash -= gross + (fees or Decimal("0"))
            if not _fee_is_complete(cash_event):
                cash_status = "partial"
                cash_partial_reasons.add("fee_unknown")
        elif event_type == "sell" and gross is not None:
            cash += gross - (fees or Decimal("0"))
            if not _fee_is_complete(cash_event):
                cash_status = "partial"
                cash_partial_reasons.add("fee_unknown")
        elif event_type == "dividend" and cash_amount is not None:
            cash += cash_amount
        elif event_type == "cash_fee" and cash_amount is not None:
            cash -= cash_amount
        elif event_type == "opening":
            # Opening inventory has no proven cash movement.
            pass
        else:
            # Preserve the provisional value but make the limitation explicit;
            # never convert an unknown delta to zero.
            cash_status = "partial"
            cash_partial_reasons.add("unknown_event_effect")

    for occurred_at, cash_group in sorted(account_by_time.items()):
        (
            cash_ordering_status,
            ordered_evidence_group,
        ) = account_group_meta[occurred_at]
        replay_ids = {item["event_id"] for item in cash_group}
        ordered_cash_group = [
            item
            for item in ordered_evidence_group
            if item["event_id"] in replay_ids
        ]
        excluded_boundary_ids = {
            item["event_id"]
            for item in ordered_evidence_group
            if item["event_id"] not in replay_ids
        }
        if cash_ordering_status == "proven" and excluded_boundary_ids:
            seen_excluded = False
            for evidence_event in ordered_evidence_group:
                if evidence_event["event_id"] in excluded_boundary_ids:
                    seen_excluded = True
                elif seen_excluded:
                    raise LedgerSnapshotReconstructionError(
                        "P2C episode cursor conflicts with explicit "
                        "same-time business sequence"
                    )
        before_cash = cash
        before_status = cash_status
        before_refs = set(cash_refs)
        applies = (
            cash is not None
            and (
                cash_baseline_time is None
                or _dt(occurred_at) > cash_baseline_time
            )
        )
        if applies and cash_ordering_status == "proven":
            for cash_event in ordered_cash_group:
                event_before_cash = cash
                event_before_status = cash_status
                event_before_refs = set(cash_refs)
                event_refs = set(cash_event["source_refs"])
                apply_cash_event(cash_event)
                cash_refs.update(event_refs)
                cash_event_states[cash_event["event_id"]] = {
                    "ordering_status": "proven",
                    "pre_value": event_before_cash,
                    "pre_status": event_before_status,
                    "pre_refs": event_before_refs,
                    "post_value": cash,
                    "post_status": cash_status,
                    "post_refs": set(cash_refs),
                }
        elif applies:
            for cash_event in ordered_cash_group:
                apply_cash_event(cash_event)
                cash_refs.update(cash_event["source_refs"])
            ambiguous_refs = set(cash_refs) | before_refs
            for cash_event in ordered_cash_group:
                cash_event_states[cash_event["event_id"]] = {
                    "ordering_status": "ambiguous",
                    "pre_value": None,
                    "pre_status": "partial",
                    "pre_refs": ambiguous_refs,
                    "post_value": None,
                    "post_status": "partial",
                    "post_refs": ambiguous_refs,
                }
        if not applies:
            for cash_event in ordered_cash_group:
                cash_event_states[cash_event["event_id"]] = {
                    "ordering_status": cash_ordering_status,
                    "pre_value": cash,
                    "pre_status": cash_status,
                    "pre_refs": set(cash_refs),
                    "post_value": cash,
                    "post_status": cash_status,
                    "post_refs": set(cash_refs),
                }
        if (
            applies
            and excluded_boundary_ids
            and cash_ordering_status == "ambiguous"
        ):
            cash_status = "partial"
            cash_partial_reasons.add("boundary_ambiguity")
            boundary_refs = {
                ref
                for item in ordered_evidence_group
                for ref in item["source_refs"]
            }
            cash_refs.update(boundary_refs)
            for cash_event in ordered_cash_group:
                state = cash_event_states[cash_event["event_id"]]
                state["pre_refs"].update(boundary_refs)
                state["post_refs"].update(boundary_refs)
        cash_by_time[occurred_at] = {
            "ordering_status": cash_ordering_status,
            "event_ids": [
                item["event_id"] for item in ordered_evidence_group
            ],
            "pre_value": before_cash,
            "pre_status": before_status,
            "pre_refs": before_refs,
            "post_value": cash,
            "post_status": cash_status,
            "post_refs": set(cash_refs),
        }

    by_time: dict[str, list[dict[str, Any]]] = {}
    for item in included:
        by_time.setdefault(item["occurred_at"], []).append(item)
    visible_scope_by_time: dict[str, list[dict[str, Any]]] = {}
    for item in visible_scope_events:
        visible_scope_by_time.setdefault(item["occurred_at"], []).append(item)
    group_meta: dict[
        str,
        tuple[
            str,
            list[dict[str, Any]],
            list[dict[str, Any]],
        ],
    ] = {}
    same_time_groups: list[dict[str, Any]] = []
    for occurred_at, evidence_group in sorted(
        visible_scope_by_time.items()
    ):
        status, ordered_evidence = _ordered_group(evidence_group)
        replay_ids = {
            item["event_id"] for item in by_time.get(occurred_at, [])
        }
        ordered_replay = [
            item
            for item in ordered_evidence
            if item["event_id"] in replay_ids
        ]
        excluded_boundary_ids = {
            item["event_id"]
            for item in ordered_evidence
            if item["event_id"] not in replay_ids
        }
        if status == "proven" and excluded_boundary_ids:
            seen_excluded = False
            for evidence_event in ordered_evidence:
                if evidence_event["event_id"] in excluded_boundary_ids:
                    seen_excluded = True
                elif seen_excluded:
                    raise LedgerSnapshotReconstructionError(
                        "P2C episode cursor conflicts with explicit "
                        "same-time business sequence"
                    )
        for item in ordered_replay:
            group_meta[item["event_id"]] = (
                status,
                ordered_replay,
                ordered_evidence,
            )

    # Cursor-level same-time evidence is account-scoped because cash is
    # account-scoped.  This also exposes cross-symbol ambiguity rather than
    # silently attributing a whole batch to the selected symbol event.
    for occurred_at, (status, ordered) in sorted(
        account_group_meta.items()
    ):
        if len(ordered) > 1:
            same_time_groups.append(
                {
                    "effective_at": occurred_at,
                    "event_ids": [
                        item["event_id"] for item in ordered
                    ],
                    "ordering_status": status,
                    "basis": (
                        "explicit_business_sequence"
                        if status == "proven"
                        else "same_time_without_business_sequence"
                    ),
                }
            )

    anchors: list[dict[str, Any]] = []
    root_gaps: list[dict[str, Any]] = []
    position_event_states: dict[str, dict[str, Any]] = {}

    def position_state() -> dict[str, Any]:
        return {
            "quantity": quantity,
            "cost": cost,
            "quantity_status": quantity_status,
            "cost_status": cost_status,
            "refs": set(position_refs),
        }

    def apply_position_event(
        item: Mapping[str, Any],
        *,
        group_gaps: list[dict[str, Any]],
        before_episode: bool,
    ) -> None:
        nonlocal quantity, cost, quantity_status, cost_status
        nonlocal cost_complete, cost_fee_unknown, blocked, prior_open_seen
        event_refs = set(item["source_refs"])
        apply_position = (
            position_baseline_time is None
            or _dt(item["occurred_at"]) > position_baseline_time
        )
        if not apply_position:
            return
        position_refs.update(event_refs)
        event_type = item["event_type"]
        side = item["side"]
        event_quantity = _decimal(
            item["quantity"], field=f"{item['event_id']}.quantity"
        )
        gross = _decimal(
            item["gross_amount"],
            field=f"{item['event_id']}.gross_amount",
        )
        fees = _decimal(
            item["fees"], field=f"{item['event_id']}.fees"
        )
        cash_amount = _decimal(
            item["cash_amount"],
            field=f"{item['event_id']}.cash_amount",
        )
        if event_type not in _SUPPORTED_EVENT_TYPES:
            blocked = True
            gap = _gap(
                "UNSUPPORTED_LEDGER_EVENT_EFFECT",
                severity="blocker",
                blocks_axis=True,
                refs=event_refs,
                next_step="复核公司行动、修正或转入转出的显式数量与成本效果。",
            )
            group_gaps.append(gap)
            root_gaps.append(gap)
            quantity = None
            cost = None
            quantity_status = "partial"
            cost_status = "missing"
            return
        if event_type in {"buy", "sell", "opening"}:
            if (
                event_quantity is None
                or event_quantity <= 0
                or side not in _POSITION_SIDES
            ):
                blocked = True
                gap = _gap(
                    "INVALID_POSITION_EVENT",
                    severity="blocker",
                    blocks_axis=True,
                    refs=event_refs,
                    next_step="复核数量、方向和事件类型。",
                )
                group_gaps.append(gap)
                root_gaps.append(gap)
                quantity = None
                cost = None
                quantity_status = "partial"
                cost_status = "missing"
                return
            quantity_before_event = quantity
            if quantity is not None:
                next_quantity = (
                    quantity + event_quantity * _POSITION_SIDES[side]
                )
                if next_quantity < 0:
                    blocked = True
                    gap = _gap(
                        "NEGATIVE_POSITION_QUANTITY",
                        severity="blocker",
                        blocks_axis=True,
                        refs=event_refs,
                        next_step="补充缺失期初或更正冲突流水；不得解释为负仓。",
                    )
                    group_gaps.append(gap)
                    root_gaps.append(gap)
                    quantity = None
                    cost = None
                    quantity_status = "partial"
                    cost_status = "missing"
                    return
                quantity = next_quantity
            if event_type == "opening":
                opening_cost = _decimal(
                    _source_row(item).get("total_cost"),
                    field=f"{item['event_id']}.total_cost",
                )
                if opening_cost is None:
                    cost = None
                    cost_status = "missing"
                    cost_complete = False
                else:
                    cost = opening_cost
                    cost_status = "available"
                    cost_complete = True
                quantity_status = "available"
            elif gross is None or gross <= 0 or cost is None:
                cost = None
                cost_status = "missing"
                cost_complete = False
            elif event_type == "buy":
                cost += gross + (fees or Decimal("0"))
                if not _fee_is_complete(item):
                    cost_complete = False
                    cost_fee_unknown = True
                cost_status = "available" if cost_complete else "partial"
            else:
                if (
                    quantity_before_event is None
                    or quantity_before_event <= 0
                    or quantity is None
                ):
                    cost = None
                    cost_status = "missing"
                    cost_complete = False
                elif quantity == 0:
                    cost = Decimal("0")
                else:
                    cost = cost * quantity / quantity_before_event
                if cost is not None:
                    cost_status = (
                        "available" if cost_complete else "partial"
                    )
            if quantity is not None and quantity > 0:
                prior_open_seen = True
            if quantity == 0 and prior_open_seen:
                cost = Decimal("0")
                cost_status = "available"
                cost_complete = True
                prior_flat_refs.update(position_refs)
                if before_episode:
                    quantity_status = "available"
        elif event_type in {"dividend", "cash_fee"}:
            if cost is not None and quantity not in (None, Decimal("0")):
                if cash_amount is None:
                    cost = None
                    cost_status = "missing"
                    cost_complete = False
                elif event_type == "dividend":
                    cost -= cash_amount
                else:
                    cost += cash_amount

    processed_groups: set[str] = set()
    for event in included:
        occurred = event["occurred_at"]
        if occurred in processed_groups:
            continue
        processed_groups.add(occurred)
        (
            position_ordering_status,
            group,
            evidence_group,
        ) = group_meta[event["event_id"]]
        group_ids = [item["event_id"] for item in group]
        evidence_group_ids = [
            item["event_id"] for item in evidence_group
        ]
        group_is_episode = any(
            event_id in set(episode_event_ids) for event_id in group_ids
        )
        account_status, account_group = account_group_meta.get(
            occurred, ("proven", group)
        )
        account_ids = [item["event_id"] for item in account_group]
        group_gaps: list[dict[str, Any]] = []
        if (
            group_is_episode
            and (
                position_ordering_status == "ambiguous"
                or account_status == "ambiguous"
            )
        ):
            group_gap = _gap(
                "SAME_TIME_BUSINESS_ORDER_AMBIGUOUS",
                refs=[
                    ref
                    for item in account_group
                    for ref in item["source_refs"]
                ],
                next_step=(
                    "提供同一生效时点内的显式业务序列；稳定 ID "
                    "仅用于确定性字节排序。"
                ),
            )
            group_gaps.append(group_gap)
            root_gaps.append(group_gap)

        before_episode = _dt(occurred) < first_episode_at
        if position_ordering_status == "proven":
            for item in group:
                before = position_state()
                apply_position_event(
                    item,
                    group_gaps=group_gaps,
                    before_episode=before_episode,
                )
                position_event_states[item["event_id"]] = {
                    "pre": before,
                    "post": position_state(),
                    "ordering_status": "proven",
                }
        else:
            group_pre = position_state()
            applies = (
                position_baseline_time is None
                or _dt(occurred) > position_baseline_time
            )
            if applies:
                for item in group:
                    position_refs.update(item["source_refs"])
                unsupported = [
                    item
                    for item in group
                    if item["event_type"] not in _SUPPORTED_EVENT_TYPES
                ]
                invalid = [
                    item
                    for item in group
                    if item["event_type"] in {"buy", "sell", "opening"}
                    and (
                        _decimal(
                            item["quantity"],
                            field=f"{item['event_id']}.quantity",
                        )
                        in (None, Decimal("0"))
                        or _decimal(
                            item["quantity"],
                            field=f"{item['event_id']}.quantity",
                        )
                        < 0
                        or item["side"] not in _POSITION_SIDES
                    )
                ]
                if unsupported or invalid:
                    blocked = True
                    bad = unsupported or invalid
                    gap = _gap(
                        (
                            "UNSUPPORTED_LEDGER_EVENT_EFFECT"
                            if unsupported
                            else "INVALID_POSITION_EVENT"
                        ),
                        severity="blocker",
                        blocks_axis=True,
                        refs=[
                            ref
                            for item in bad
                            for ref in item["source_refs"]
                        ],
                        next_step="复核同刻流水的数量、方向和业务效果。",
                    )
                    group_gaps.append(gap)
                    root_gaps.append(gap)
                    quantity = None
                    cost = None
                    quantity_status = "partial"
                    cost_status = "missing"
                else:
                    position_items = [
                        item
                        for item in group
                        if item["event_type"]
                        in {"buy", "sell", "opening"}
                    ]
                    delta = sum(
                        (
                            _decimal(
                                item["quantity"],
                                field=f"{item['event_id']}.quantity",
                            )
                            * _POSITION_SIDES[item["side"]]
                            for item in position_items
                        ),
                        Decimal("0"),
                    )
                    next_quantity = (
                        quantity + delta if quantity is not None else None
                    )
                    if next_quantity is not None and next_quantity < 0:
                        if quantity_status == "available":
                            blocked = True
                            gap = _gap(
                                "NEGATIVE_POSITION_QUANTITY",
                                severity="blocker",
                                blocks_axis=True,
                                refs=[
                                    ref
                                    for item in position_items
                                    for ref in item["source_refs"]
                                ],
                                next_step=(
                                    "补充缺失期初或更正冲突流水；组级净额仍为负，"
                                    "不存在非负业务排序。"
                                ),
                            )
                            group_gaps.append(gap)
                            root_gaps.append(gap)
                        quantity = None
                        cost = None
                        quantity_status = "partial"
                        cost_status = "missing"
                    else:
                        quantity_before_group = quantity
                        quantity = next_quantity
                        has_sell = any(
                            item["event_type"] == "sell"
                            for item in position_items
                        )
                        has_other_cost_effect = any(
                            item["event_type"] in {
                                "buy",
                                "opening",
                                "dividend",
                                "cash_fee",
                            }
                            for item in group
                        )
                        if has_sell and has_other_cost_effect:
                            cost = None
                            cost_status = "partial"
                            cost_complete = False
                        elif any(
                            item["event_type"] == "opening"
                            for item in position_items
                        ):
                            cost = None
                            cost_status = "partial"
                            cost_complete = False
                        elif has_sell:
                            if (
                                cost is None
                                or quantity_before_group is None
                                or quantity_before_group <= 0
                                or quantity is None
                            ):
                                cost = None
                                cost_status = "missing"
                                cost_complete = False
                            elif quantity == 0:
                                cost = Decimal("0")
                            else:
                                cost = (
                                    cost
                                    * quantity
                                    / quantity_before_group
                                )
                                cost_status = (
                                    "available"
                                    if cost_complete
                                    else "partial"
                                )
                        else:
                            for item in group:
                                event_type = item["event_type"]
                                if event_type == "buy":
                                    gross = _decimal(
                                        item["gross_amount"],
                                        field=(
                                            f"{item['event_id']}.gross_amount"
                                        ),
                                    )
                                    fees = _decimal(
                                        item["fees"],
                                        field=f"{item['event_id']}.fees",
                                    )
                                    if (
                                        gross is None
                                        or gross <= 0
                                        or cost is None
                                    ):
                                        cost = None
                                        cost_status = "missing"
                                        cost_complete = False
                                    else:
                                        cost += gross + (
                                            fees or Decimal("0")
                                        )
                                        if not _fee_is_complete(item):
                                            cost_complete = False
                                            cost_fee_unknown = True
                                elif event_type in {
                                    "dividend",
                                    "cash_fee",
                                } and cost is not None and quantity not in (
                                    None,
                                    Decimal("0"),
                                ):
                                    cash_amount = _decimal(
                                        item["cash_amount"],
                                        field=(
                                            f"{item['event_id']}.cash_amount"
                                        ),
                                    )
                                    if cash_amount is None:
                                        cost = None
                                        cost_status = "missing"
                                        cost_complete = False
                                    elif event_type == "dividend":
                                        cost -= cash_amount
                                    else:
                                        cost += cash_amount
                            if cost is not None:
                                cost_status = (
                                    "available"
                                    if cost_complete
                                    else "partial"
                                )
                        if quantity is not None and quantity > 0:
                            prior_open_seen = True
                        if quantity == 0 and prior_open_seen:
                            cost = Decimal("0")
                            cost_status = "available"
                            cost_complete = True
                            prior_flat_refs.update(position_refs)
                            if before_episode:
                                quantity_status = "available"
            group_post = position_state()
            ambiguous_refs = (
                set(group_pre["refs"])
                | set(group_post["refs"])
                | {
                    ref
                    for item in group
                    for ref in item["source_refs"]
                }
            )
            for item in group:
                position_event_states[item["event_id"]] = {
                    "pre": {
                        "quantity": None,
                        "cost": None,
                        "quantity_status": "partial",
                        "cost_status": "partial",
                        "refs": ambiguous_refs,
                    },
                    "post": {
                        "quantity": None,
                        "cost": None,
                        "quantity_status": "partial",
                        "cost_status": "partial",
                        "refs": ambiguous_refs,
                    },
                    "ordering_status": "ambiguous",
                }

        if not group_is_episode:
            continue
        for item in group:
            if item["event_id"] not in set(episode_event_ids):
                continue
            position_projection = position_event_states[item["event_id"]]
            cash_projection = cash_event_states.get(
                item["event_id"],
                {
                    "ordering_status": "proven",
                    "pre_value": cash,
                    "pre_status": cash_status,
                    "pre_refs": set(cash_refs),
                    "post_value": cash,
                    "post_status": cash_status,
                    "post_refs": set(cash_refs),
                },
            )
            anchor_ordering_status = (
                "ambiguous"
                if (
                    position_projection["ordering_status"] == "ambiguous"
                    or cash_projection["ordering_status"] == "ambiguous"
                )
                else "proven"
            )
            same_time_ids = sorted(
                set(evidence_group_ids) | set(account_ids)
            )
            for anchor_type, position_key, cash_prefix in (
                ("event_pre", "pre", "pre"),
                ("event_post", "post", "post"),
            ):
                state = position_projection[position_key]
                anchors.append(
                    _anchor(
                        episode_id=episode_id,
                        anchor_type=anchor_type,
                        event_id=item["event_id"],
                        effective_at=occurred,
                        ordering_status=anchor_ordering_status,
                        same_time_event_ids=same_time_ids,
                        symbol=symbol,
                        quantity=state["quantity"],
                        quantity_status=state["quantity_status"],
                        cost=state["cost"],
                        cost_status=state["cost_status"],
                        cash=cash_projection[f"{cash_prefix}_value"],
                        cash_status=cash_projection[
                            f"{cash_prefix}_status"
                        ],
                        currency=currency,
                        position_refs=(
                            set(state["refs"]) | set(item["source_refs"])
                        ),
                        cash_refs=cash_projection[f"{cash_prefix}_refs"],
                        gaps=group_gaps,
                        blocked=blocked,
                    )
                )

    if quantity_status != "available":
        gap = _gap(
            "OPENING_BASELINE_NOT_PROVEN",
            refs=position_refs,
            next_step=(
                "提供显式复核期初，或在完整 partition 流水中证明先前归零边界。"
            ),
        )
        root_gaps.append(gap)
    if cash is None:
        root_gaps.append(
            _gap(
                "CASH_BASELINE_MISSING",
                next_step="提供 cutoff-safe 的现金余额锚点。",
            )
        )
    elif cash_status == "partial":
        if "fee_unknown" in cash_partial_reasons:
            root_gaps.append(
                _gap(
                    "CASH_BALANCE_PARTIAL_FEE_UNKNOWN",
                    refs=cash_refs,
                    next_step=(
                        "补齐费用投影或提供已核对的现金余额；当前现金值仅为暂定。"
                    ),
                )
            )
        if "baseline_partial" in cash_partial_reasons:
            root_gaps.append(
                _gap(
                    "CASH_BASELINE_PARTIAL",
                    refs=cash_refs,
                    next_step="提供完整、cutoff-safe 的现金基准证明。",
                )
            )
        if "unknown_event_effect" in cash_partial_reasons:
            root_gaps.append(
                _gap(
                    "CASH_LEDGER_EFFECT_PARTIAL",
                    refs=cash_refs,
                    next_step="复核无法确定现金效果的账户流水。",
                )
            )
        if "boundary_ambiguity" in cash_partial_reasons:
            root_gaps.append(
                _gap(
                    "EPISODE_BOUNDARY_SAME_TIME_AMBIGUOUS",
                    refs=cash_refs,
                    next_step=(
                        "提供同一生效时点内的显式业务序列，以证明复核期边界"
                        "两侧的账户现金归属。"
                    ),
                )
            )
    if cost_status == "partial" and cost_fee_unknown:
        root_gaps.append(
            _gap(
                "COST_BASIS_PARTIAL_FEE_UNKNOWN",
                refs=position_refs,
                next_step="使用 append-only fee projection/correction 补齐费用。",
            )
        )
    root_gaps.extend(
        [
            _gap(
                "SNAPSHOT_PRICE_MISSING",
                next_step="在 P6 冻结 cutoff-safe 市场价格。",
            ),
            _gap(
                "SNAPSHOT_NAV_WEIGHT_MISSING",
                next_step="仅在现金和全部持仓定价完整后计算 NAV/权重。",
            ),
            _gap(
                "POINT_IN_TIME_INDUSTRY_MISSING",
                next_step="提供时点行业分类；当前分类不得倒填。",
            ),
        ]
    )
    unique_gaps = {
        _canonical_bytes(item).decode("utf-8"): item for item in root_gaps
    }
    root_gaps = sorted(
        unique_gaps.values(),
        key=lambda item: (item["code"], _canonical_bytes(item)),
    )
    anchors.append(
        _anchor(
            episode_id=episode_id,
            anchor_type="checkpoint",
            event_id=None,
            effective_at=canonical_as_of,
            ordering_status="not_applicable",
            same_time_event_ids=[],
            symbol=symbol,
            quantity=quantity,
            quantity_status=quantity_status,
            cost=cost,
            cost_status=cost_status,
            cash=cash,
            cash_status=cash_status,
            currency=currency,
            position_refs=position_refs,
            cash_refs=cash_refs,
            gaps=root_gaps,
            blocked=blocked,
        )
    )
    anchors.sort(
        key=lambda item: (
            item["effective_at"],
            {"event_pre": 0, "event_post": 1, "checkpoint": 2}[
                item["anchor_type"]
            ],
            item["event_id"] or "",
        )
    )
    event_input_projection = [
        item["full_input"] for item in sorted(events, key=lambda x: x["event_id"])
    ]
    scope_projection = [
        item["full_input"]
        for item in sorted(scope_events, key=lambda x: x["event_id"])
    ]
    source_refs = sorted(
        {
            f"source_binding:{value}"
            for value in proof.values()
        }
    )
    artifact: dict[str, Any] = {
        "schema_version": LEDGER_SNAPSHOT_RECONSTRUCTION_SCHEMA_VERSION,
        "method_version": LEDGER_SNAPSHOT_RECONSTRUCTION_METHOD_VERSION,
        "content_id": "",
        "episode_id": episode_id,
        "perspective": perspective,
        "as_of": canonical_as_of,
        "knowledge_cutoff": canonical_cutoff,
        "scope": {
            "account_id": account,
            "symbol": symbol,
            "instrument_id": instrument,
            "currency": currency,
        },
        "source_binding": {
            "proof": proof,
            "event_input_count": len(events),
            "event_input_content_id": _content_id(
                event_input_projection
            ),
            "scope_event_count": len(scope_events),
            "scope_event_content_id": _content_id(scope_projection),
            "episode_event_ids": list(episode_event_ids),
        },
        "baseline": {
            **baseline,
            "derived_prior_flat": {
                "status": (
                    "available" if prior_flat_refs else "missing"
                ),
                "method": (
                    "prior_flat_event"
                    if prior_flat_refs
                    else "not_proven"
                ),
                "source_refs": sorted(prior_flat_refs),
                "account_opening_baseline_proven": (
                    baseline["position"]["status"] == "available"
                ),
            },
        },
        "event_cursor": {
            "cursor_scope": "partition",
            "account_event_set_complete": False,
            "partition_event_set_complete": True,
            "input_event_ids": sorted(event_map),
            "account_event_ids": [
                item["event_id"] for item in account_events
            ],
            "scope_event_ids": [item["event_id"] for item in scope_events],
            "included_account_event_ids": [
                item["event_id"] for item in included_account_events
            ],
            "included_event_ids": [item["event_id"] for item in included],
            "excluded_after_as_of_ids": sorted(excluded),
            "excluded_future_known_ids": sorted(excluded_future_known),
            "episode_boundary_mode": episode_boundary_mode,
            "episode_boundary_event_id": episode_boundary_event_id,
            "episode_boundary_ordering_key": (
                episode_boundary_ordering_key
            ),
            "visible_account_event_ids": [
                item["event_id"] for item in visible_account_events
            ],
            "visible_event_ids": [
                item["event_id"] for item in visible_scope_events
            ],
            "excluded_by_episode_cursor_ids": sorted(
                excluded_by_episode_cursor
            ),
            "same_time_groups": same_time_groups,
            "source_refs": source_refs,
        },
        "anchors": anchors,
        "gaps": root_gaps,
        "governance": deepcopy(_GOVERNANCE),
    }
    artifact["content_id"] = _content_id(artifact)
    validation = validate_ledger_snapshot_reconstruction(artifact)
    if validation["validation_status"] != "accepted":
        raise LedgerSnapshotReconstructionError(
            "built reconstruction failed closed validation: "
            + ",".join(item["code"] for item in validation["findings"])
        )
    return artifact


def canonical_ledger_snapshot_reconstruction_bytes(
    artifact: Mapping[str, Any],
) -> bytes:
    validation = validate_ledger_snapshot_reconstruction(artifact)
    if validation["validation_status"] != "accepted":
        raise LedgerSnapshotReconstructionError(
            "ledger snapshot reconstruction validation blocked"
        )
    return _canonical_bytes(artifact)


def _finding(code: str, message: str) -> dict[str, Any]:
    return {
        "severity": "blocker",
        "code": code,
        "message": message,
        "related_refs": [],
    }


def _gap_is_canonical(value: object) -> bool:
    if not isinstance(value, Mapping) or set(value) != _GAP_FIELDS:
        return False
    refs = value.get("source_refs")
    return bool(
        value.get("axis") == "snapshot_cash_valuation"
        and isinstance(value.get("code"), str)
        and value["code"].strip()
        and value.get("severity") in {"info", "warning", "blocker"}
        and isinstance(value.get("blocks_axis"), bool)
        and isinstance(value.get("owner"), str)
        and value["owner"].strip()
        and isinstance(value.get("next_step"), str)
        and value["next_step"].strip()
        and isinstance(refs, list)
        and refs == sorted(set(refs))
        and (
            value["blocks_axis"] is False
            or (
                value["severity"] == "blocker"
                and bool(refs)
            )
        )
    )


def validate_ledger_snapshot_reconstruction(
    artifact: object,
) -> dict[str, Any]:
    """Validate closed shape, hashes, state independence and safety."""

    findings: list[dict[str, Any]] = []
    if not isinstance(artifact, Mapping):
        findings.append(
            _finding("ARTIFACT_NOT_OBJECT", "artifact must be an object")
        )
        return {
            "schema_version": (
                LEDGER_SNAPSHOT_RECONSTRUCTION_VALIDATION_SCHEMA_VERSION
            ),
            "validation_status": "blocked",
            "findings": findings,
        }
    try:
        _canonical_bytes(artifact)
    except Exception as exc:
        findings.append(
            _finding("NON_CANONICAL_JSON", type(exc).__name__)
        )
    if set(artifact) != _ROOT_FIELDS:
        findings.append(
            _finding("INVALID_ROOT_SHAPE", "root object is not closed")
        )
    if artifact.get("schema_version") != (
        LEDGER_SNAPSHOT_RECONSTRUCTION_SCHEMA_VERSION
    ):
        findings.append(
            _finding("INVALID_SCHEMA_VERSION", "schema version is unsupported")
        )
    if artifact.get("method_version") != (
        LEDGER_SNAPSHOT_RECONSTRUCTION_METHOD_VERSION
    ):
        findings.append(
            _finding("INVALID_METHOD_VERSION", "method version is unsupported")
        )
    for field in ("as_of", "knowledge_cutoff"):
        try:
            canonical = _timestamp(artifact.get(field), field=field)
            if artifact.get(field) != canonical:
                raise LedgerSnapshotReconstructionError(
                    f"{field} is not canonical UTC seconds"
                )
        except Exception:
            findings.append(
                _finding("INVALID_TIME", f"{field} is invalid")
            )
    try:
        if _dt(str(artifact.get("as_of"))) > _dt(
            str(artifact.get("knowledge_cutoff"))
        ):
            raise LedgerSnapshotReconstructionError(
                "as_of exceeds knowledge_cutoff"
            )
    except Exception:
        findings.append(
            _finding(
                "INVALID_TIME_ORDER",
                "as_of must not exceed knowledge_cutoff",
            )
        )
    if artifact.get("perspective") not in {"user", "system"}:
        findings.append(
            _finding("INVALID_PERSPECTIVE", "perspective is invalid")
        )
    scope = artifact.get("scope")
    if not isinstance(scope, Mapping) or set(scope) != _SCOPE_FIELDS:
        findings.append(
            _finding("INVALID_SCOPE", "scope shape is invalid")
        )
    elif (
        any(
            not isinstance(scope.get(field), str)
            or not scope[field].strip()
            for field in _SCOPE_FIELDS
        )
        or scope["symbol"] != scope["symbol"].upper()
        or scope["instrument_id"] != scope["instrument_id"].upper()
        or not re.fullmatch(r"[A-Z]{3}", scope["currency"])
    ):
        findings.append(
            _finding("INVALID_SCOPE", "scope semantics are invalid")
        )
    if (
        not isinstance(artifact.get("episode_id"), str)
        or not artifact["episode_id"].strip()
    ):
        findings.append(
            _finding("INVALID_EPISODE_ID", "episode_id is required")
        )
    binding = artifact.get("source_binding")
    if (
        not isinstance(binding, Mapping)
        or set(binding) != _SOURCE_BINDING_FIELDS
        or not isinstance(binding.get("proof"), Mapping)
    ):
        findings.append(
            _finding("INVALID_SOURCE_BINDING", "source binding is invalid")
        )
    else:
        try:
            if _normalize_source_binding(binding["proof"]) != binding["proof"]:
                raise LedgerSnapshotReconstructionError(
                    "source proof is not canonical"
                )
            for field in (
                "event_input_content_id",
                "scope_event_content_id",
            ):
                if not _SHA256_RE.fullmatch(str(binding.get(field) or "")):
                    raise LedgerSnapshotReconstructionError(
                        f"{field} is invalid"
                    )
            if (
                not isinstance(binding.get("event_input_count"), int)
                or isinstance(binding.get("event_input_count"), bool)
                or binding["event_input_count"] < 0
                or not isinstance(binding.get("scope_event_count"), int)
                or isinstance(binding.get("scope_event_count"), bool)
                or binding["scope_event_count"] < 0
            ):
                raise LedgerSnapshotReconstructionError(
                    "source binding counts are invalid"
                )
            episode_event_ids = binding.get("episode_event_ids")
            if (
                not isinstance(episode_event_ids, list)
                or not episode_event_ids
                or any(
                    not isinstance(item, str) or not item
                    for item in episode_event_ids
                )
                or len(episode_event_ids) != len(set(episode_event_ids))
            ):
                raise LedgerSnapshotReconstructionError(
                    "episode_event_ids is invalid"
                )
        except Exception:
            findings.append(
                _finding(
                    "INVALID_SOURCE_BINDING",
                    "source binding semantics are invalid",
                )
            )
    baseline = artifact.get("baseline")
    if not isinstance(baseline, Mapping):
        findings.append(
            _finding("INVALID_BASELINE", "baseline is invalid")
        )
    else:
        derived = baseline.get("derived_prior_flat")
        core = {key: value for key, value in baseline.items() if key != "derived_prior_flat"}
        try:
            normalized_baseline = _normalize_baseline(
                core,
                currency=str(
                    scope.get("currency") if isinstance(scope, Mapping) else "CNY"
                ),
                as_of=str(artifact.get("as_of") or ""),
                knowledge_cutoff=str(artifact.get("knowledge_cutoff") or ""),
            )
            if normalized_baseline != core:
                raise LedgerSnapshotReconstructionError(
                    "baseline is not canonical"
                )
            if (
                not isinstance(derived, Mapping)
                or set(derived)
                != {
                    "status",
                    "method",
                    "source_refs",
                    "account_opening_baseline_proven",
                }
                or derived.get("status") not in {"available", "missing"}
                or not isinstance(
                    derived.get("account_opening_baseline_proven"), bool
                )
            ):
                raise LedgerSnapshotReconstructionError(
                    "derived prior-flat proof is invalid"
                )
            if (
                (
                    derived["status"] == "available"
                    and (
                        derived["method"] != "prior_flat_event"
                        or not derived["source_refs"]
                    )
                )
                or (
                    derived["status"] == "missing"
                    and (
                        derived["method"] != "not_proven"
                        or derived["source_refs"]
                    )
                )
                or derived["source_refs"]
                != sorted(set(derived["source_refs"]))
                or derived["account_opening_baseline_proven"]
                != (core["position"]["status"] == "available")
            ):
                raise LedgerSnapshotReconstructionError(
                    "derived prior-flat semantics are inconsistent"
                )
        except Exception:
            findings.append(
                _finding("INVALID_BASELINE", "baseline semantics are invalid")
            )
    same_time_cursor_by_event: dict[
        str, tuple[str, set[str], str]
    ] = {}
    cursor = artifact.get("event_cursor")
    if not isinstance(cursor, Mapping) or set(cursor) != _CURSOR_FIELDS:
        findings.append(
            _finding("INVALID_EVENT_CURSOR", "event cursor is invalid")
        )
    elif (
        cursor.get("cursor_scope") != "partition"
        or cursor.get("account_event_set_complete") is not False
        or cursor.get("partition_event_set_complete") is not True
    ):
        findings.append(
            _finding(
                "CURSOR_SCOPE_OVERCLAIM",
                "partition cursor must not claim account completeness",
            )
        )
    else:
        cursor_lists: dict[str, list[str]] = {}
        for field in (
            "input_event_ids",
            "account_event_ids",
            "scope_event_ids",
            "visible_account_event_ids",
            "visible_event_ids",
            "included_account_event_ids",
            "included_event_ids",
            "excluded_after_as_of_ids",
            "excluded_future_known_ids",
            "excluded_by_episode_cursor_ids",
            "source_refs",
        ):
            value = cursor.get(field)
            if (
                not isinstance(value, list)
                or any(not isinstance(item, str) or not item for item in value)
                or len(value) != len(set(value))
            ):
                findings.append(
                    _finding(
                        "INVALID_EVENT_CURSOR",
                        f"event cursor {field} is invalid",
                    )
                )
                cursor_lists[field] = []
            else:
                cursor_lists[field] = value
        if cursor_lists.get("input_event_ids") != sorted(
            cursor_lists.get("input_event_ids", [])
        ):
            findings.append(
                _finding(
                    "INVALID_EVENT_CURSOR",
                    "input event IDs are not canonical",
                )
            )
        input_ids = set(cursor_lists.get("input_event_ids", []))
        account_ids = set(cursor_lists.get("account_event_ids", []))
        scope_ids = set(cursor_lists.get("scope_event_ids", []))
        visible_account_ids = set(
            cursor_lists.get("visible_account_event_ids", [])
        )
        visible_ids = set(
            cursor_lists.get("visible_event_ids", [])
        )
        included_account_ids = set(
            cursor_lists.get("included_account_event_ids", [])
        )
        included_ids = set(cursor_lists.get("included_event_ids", []))
        after_ids = set(cursor_lists.get("excluded_after_as_of_ids", []))
        future_known_ids = set(
            cursor_lists.get("excluded_future_known_ids", [])
        )
        cursor_excluded_ids = set(
            cursor_lists.get("excluded_by_episode_cursor_ids", [])
        )
        episode_ids = (
            set(binding.get("episode_event_ids", []))
            if isinstance(binding, Mapping)
            else set()
        )
        if not (
            account_ids <= input_ids
            and scope_ids <= account_ids
            and visible_account_ids <= account_ids
            and visible_ids <= scope_ids
            and visible_ids <= visible_account_ids
            and included_account_ids <= visible_account_ids
            and included_ids <= visible_ids
            and included_ids <= included_account_ids
            and episode_ids <= included_ids
            and after_ids <= scope_ids
            and future_known_ids <= account_ids
            and cursor_excluded_ids <= visible_account_ids
            and cursor_excluded_ids.isdisjoint(included_account_ids)
            and visible_account_ids
            == included_account_ids | cursor_excluded_ids
            and included_ids.isdisjoint(after_ids)
            and included_account_ids.isdisjoint(future_known_ids)
            and visible_ids.isdisjoint(after_ids)
            and visible_account_ids.isdisjoint(future_known_ids)
        ):
            findings.append(
                _finding(
                    "EVENT_CURSOR_SET_MISMATCH",
                    "event cursor set relationships are inconsistent",
                )
            )
        boundary_mode = cursor.get("episode_boundary_mode")
        boundary_event_id = cursor.get("episode_boundary_event_id")
        boundary_key = cursor.get("episode_boundary_ordering_key")
        if boundary_mode == "request_as_of":
            if (
                boundary_event_id is not None
                or boundary_key is not None
                or cursor_excluded_ids
                or visible_account_ids != included_account_ids
                or visible_ids != included_ids
            ):
                findings.append(
                    _finding(
                        "INVALID_EPISODE_BOUNDARY_CURSOR",
                        "request-as-of cursor has a closed-episode boundary",
                    )
                )
        elif boundary_mode == "closed_episode_cursor":
            try:
                if (
                    not isinstance(boundary_event_id, str)
                    or not boundary_event_id
                    or boundary_event_id not in episode_ids
                    or boundary_event_id not in included_ids
                    or not isinstance(boundary_key, list)
                    or len(boundary_key) != 4
                    or boundary_key[0] != artifact.get("as_of")
                    or isinstance(boundary_key[1], bool)
                    or not isinstance(boundary_key[1], int)
                    or boundary_key[1] not in {0, 1, 2}
                    or not isinstance(boundary_key[2], str)
                    or not boundary_key[2]
                    or boundary_key[3] != boundary_event_id
                ):
                    raise LedgerSnapshotReconstructionError(
                        "closed episode cursor is invalid"
                    )
            except Exception:
                findings.append(
                    _finding(
                        "INVALID_EPISODE_BOUNDARY_CURSOR",
                        "closed-episode boundary cursor is invalid",
                    )
                )
        else:
            findings.append(
                _finding(
                    "INVALID_EPISODE_BOUNDARY_CURSOR",
                    "episode boundary cursor mode is invalid",
                )
            )
        if isinstance(binding, Mapping):
            if (
                binding.get("event_input_count") != len(input_ids)
                or binding.get("scope_event_count") != len(scope_ids)
            ):
                findings.append(
                    _finding(
                        "SOURCE_BINDING_COUNT_MISMATCH",
                        "source binding counts disagree with cursor",
                    )
                )
            proof = binding.get("proof")
            if isinstance(proof, Mapping):
                expected_source_refs = sorted(
                    {
                        f"source_binding:{value}"
                        for value in proof.values()
                    }
                )
                if cursor_lists.get("source_refs") != expected_source_refs:
                    findings.append(
                        _finding(
                            "CURSOR_SOURCE_BINDING_MISMATCH",
                            "cursor refs do not equal source proof",
                        )
                    )
        same_time = cursor.get("same_time_groups")
        if not isinstance(same_time, list):
            findings.append(
                _finding(
                    "INVALID_SAME_TIME_GROUP",
                    "same_time_groups must be a list",
                )
            )
        else:
            seen_times: set[str] = set()
            for group in same_time:
                try:
                    if (
                        not isinstance(group, Mapping)
                        or set(group) != _SAME_TIME_GROUP_FIELDS
                    ):
                        raise LedgerSnapshotReconstructionError(
                            "same-time group shape is invalid"
                        )
                    effective_at = _timestamp(
                        group.get("effective_at"),
                        field="same_time_group.effective_at",
                    )
                    event_ids = group.get("event_ids")
                    ordering_status = group.get("ordering_status")
                    expected_basis = (
                        "explicit_business_sequence"
                        if ordering_status == "proven"
                        else "same_time_without_business_sequence"
                    )
                    if (
                        effective_at != group.get("effective_at")
                        or effective_at in seen_times
                        or _dt(effective_at)
                        > _dt(str(artifact.get("as_of")))
                        or not isinstance(event_ids, list)
                        or len(event_ids) < 2
                        or len(event_ids) != len(set(event_ids))
                        or any(
                            not isinstance(item, str) or not item
                            for item in event_ids
                        )
                        or not set(event_ids) <= visible_account_ids
                        or ordering_status not in {"proven", "ambiguous"}
                        or group.get("basis") != expected_basis
                        or (
                            ordering_status == "ambiguous"
                            and event_ids != sorted(event_ids)
                        )
                    ):
                        raise LedgerSnapshotReconstructionError(
                            "same-time group semantics are invalid"
                        )
                    seen_times.add(effective_at)
                    for event_id in event_ids:
                        if event_id in same_time_cursor_by_event:
                            raise LedgerSnapshotReconstructionError(
                                "event appears in multiple same-time groups"
                            )
                        same_time_cursor_by_event[event_id] = (
                            effective_at,
                            set(event_ids),
                            str(ordering_status),
                        )
                except Exception:
                    findings.append(
                        _finding(
                            "INVALID_SAME_TIME_GROUP",
                            "same-time group semantics are invalid",
                        )
                    )
    anchors = artifact.get("anchors")
    if not isinstance(anchors, list) or not anchors:
        findings.append(
            _finding("INVALID_ANCHORS", "anchors must be a non-empty list")
        )
    else:
        checkpoint_count = 0
        event_anchor_counts: dict[tuple[str, str], int] = {}
        event_anchor_times: list[datetime] = []
        event_anchor_metadata: dict[
            str, tuple[str, str, tuple[str, ...]]
        ] = {}
        anchor_gap_payloads: list[tuple[str, str]] = []
        for anchor in anchors:
            if not isinstance(anchor, Mapping) or set(anchor) != _ANCHOR_FIELDS:
                findings.append(
                    _finding("INVALID_ANCHOR_SHAPE", "anchor shape is invalid")
                )
                continue
            anchor_type = anchor.get("anchor_type")
            event_id = anchor.get("event_id")
            if anchor_type == "checkpoint":
                checkpoint_count += 1
                if (
                    event_id is not None
                    or anchor.get("effective_at") != artifact.get("as_of")
                    or anchor.get("ordering_status") != "not_applicable"
                    or anchor.get("same_time_event_ids") != []
                ):
                    findings.append(
                        _finding(
                            "INVALID_CHECKPOINT_ANCHOR",
                            "checkpoint anchor identity/time is invalid",
                        )
                    )
            elif anchor_type in {"event_pre", "event_post"}:
                if (
                    not isinstance(event_id, str)
                    or not event_id
                    or anchor.get("ordering_status")
                    not in {"proven", "ambiguous"}
                ):
                    findings.append(
                        _finding(
                            "INVALID_EVENT_ANCHOR",
                            "event anchor identity/order is invalid",
                        )
                    )
                else:
                    event_anchor_counts[(event_id, anchor_type)] = (
                        event_anchor_counts.get((event_id, anchor_type), 0) + 1
                    )
                    same_time_ids = anchor.get("same_time_event_ids")
                    metadata = (
                        str(anchor.get("effective_at") or ""),
                        str(anchor.get("ordering_status") or ""),
                        (
                            tuple(same_time_ids)
                            if isinstance(same_time_ids, list)
                            else ()
                        ),
                    )
                    previous_metadata = event_anchor_metadata.get(event_id)
                    if (
                        previous_metadata is not None
                        and previous_metadata != metadata
                    ):
                        findings.append(
                            _finding(
                                "EVENT_ANCHOR_METADATA_MISMATCH",
                                "event pre/post metadata disagree",
                            )
                        )
                    event_anchor_metadata[event_id] = metadata
                    if (
                        not isinstance(same_time_ids, list)
                        or same_time_ids != sorted(set(same_time_ids))
                        or event_id not in same_time_ids
                    ):
                        findings.append(
                            _finding(
                                "INVALID_EVENT_SAME_TIME_SET",
                                "event anchor same-time set is invalid",
                            )
                        )
                    cursor_group = same_time_cursor_by_event.get(event_id)
                    if cursor_group is None:
                        if same_time_ids != [event_id]:
                            findings.append(
                                _finding(
                                    "EVENT_CURSOR_ANCHOR_MISMATCH",
                                    "single event anchor overclaims peers",
                                )
                            )
                    elif (
                        metadata[0] != cursor_group[0]
                        or set(same_time_ids or []) != cursor_group[1]
                        or metadata[1] != cursor_group[2]
                    ):
                        findings.append(
                            _finding(
                                "EVENT_CURSOR_ANCHOR_MISMATCH",
                                "anchor ordering disagrees with cursor group",
                            )
                        )
                try:
                    canonical_anchor_time = _timestamp(
                        anchor.get("effective_at"),
                        field="anchor.effective_at",
                    )
                    anchor_time = _dt(canonical_anchor_time)
                    if (
                        canonical_anchor_time != anchor.get("effective_at")
                        or anchor_time
                        > _dt(str(artifact.get("as_of")))
                    ):
                        raise LedgerSnapshotReconstructionError(
                            "event anchor exceeds reconstruction as_of"
                        )
                    event_anchor_times.append(anchor_time)
                except Exception:
                    findings.append(
                        _finding(
                            "INVALID_EVENT_ANCHOR_TIME",
                            "event anchor time is invalid",
                        )
                    )
            else:
                findings.append(
                    _finding(
                        "INVALID_ANCHOR_TYPE",
                        "anchor_type is unsupported",
                    )
                )
            anchor_gaps = anchor.get("gaps")
            if (
                not isinstance(anchor_gaps, list)
                or any(not _gap_is_canonical(item) for item in anchor_gaps)
            ):
                findings.append(
                    _finding(
                        "INVALID_ANCHOR_GAPS",
                        "anchor gaps are invalid",
                    )
                )
            else:
                anchor_gap_payloads.extend(
                    (
                        str(anchor_type),
                        _canonical_bytes(item).decode("utf-8"),
                    )
                    for item in anchor_gaps
                )
            try:
                expected_anchor_id = "ledger_anchor_" + _content_id(
                    {
                        "episode_id": artifact.get("episode_id"),
                        "anchor_type": anchor_type,
                        "event_id": event_id,
                        "effective_at": anchor.get("effective_at"),
                    }
                )[7:39]
                if anchor.get("anchor_id") != expected_anchor_id:
                    raise LedgerSnapshotReconstructionError(
                        "anchor_id mismatch"
                    )
            except Exception:
                findings.append(
                    _finding(
                        "INVALID_ANCHOR_ID",
                        "anchor_id does not match anchor identity",
                    )
                )
            position = anchor.get("position")
            if (
                not isinstance(position, Mapping)
                or set(position) != _POSITION_FIELDS
                or (
                    isinstance(scope, Mapping)
                    and position.get("symbol") != scope.get("symbol")
                )
                or position.get("quantity_status")
                not in {"available", "partial", "missing"}
                or position.get("cost_basis_status")
                not in {"available", "partial", "missing"}
            ):
                findings.append(
                    _finding(
                        "INVALID_POSITION_PROJECTION",
                        "anchor position projection is invalid",
                    )
                )
                position = None
            axis = anchor.get("snapshot_cash_valuation")
            if (
                not isinstance(axis, Mapping)
                or set(axis) != _SNAPSHOT_AXIS_FIELDS
                or not isinstance(axis.get("fields"), Mapping)
                or set(axis["fields"]) != set(_SNAPSHOT_FIELD_NAMES)
            ):
                findings.append(
                    _finding(
                        "INVALID_SNAPSHOT_AXIS",
                        "snapshot field axis is invalid",
                    )
                )
                continue
            field_statuses: list[str] = []
            for name in _SNAPSHOT_FIELD_NAMES:
                field = axis["fields"][name]
                if (
                    not isinstance(field, Mapping)
                    or set(field) != _SNAPSHOT_FIELD_FIELDS
                    or field.get("status")
                    not in {
                        "available",
                        "partial",
                        "missing",
                        "not_applicable",
                    }
                ):
                    findings.append(
                        _finding(
                            "INVALID_SNAPSHOT_FIELD",
                            f"snapshot field {name} is invalid",
                        )
                    )
                    continue
                field_statuses.append(str(field["status"]))
                refs = field.get("source_refs")
                if not isinstance(refs, list) or refs != sorted(set(refs)):
                    findings.append(
                        _finding(
                            "INVALID_FIELD_PROVENANCE",
                            f"snapshot field {name} refs are not canonical",
                        )
                    )
                if (
                    field["status"] in {"available", "partial"}
                    and (not isinstance(refs, list) or not refs)
                ):
                    findings.append(
                        _finding(
                            "MISSING_FIELD_PROVENANCE",
                            f"snapshot field {name} lacks source refs",
                        )
                    )
                if (
                    field["status"] in {"missing", "not_applicable"}
                    and field.get("value") is not None
                ):
                    findings.append(
                        _finding(
                            "MISSING_FIELD_HAS_VALUE",
                            f"snapshot field {name} fabricated a value",
                        )
                    )
                if (
                    field["status"] == "available"
                    and field.get("value") is None
                ):
                    findings.append(
                        _finding(
                            "AVAILABLE_FIELD_MISSING_VALUE",
                            f"snapshot field {name} lacks a value",
                        )
                    )
                if (
                    name != "industry"
                    and field.get("value") is not None
                ):
                    try:
                        value = field["value"]
                        decimal_value = _decimal(
                            value, field=f"snapshot.fields.{name}.value"
                        )
                        if (
                            not isinstance(value, str)
                            or decimal_value is None
                            or value != _decimal_text(decimal_value)
                        ):
                            raise LedgerSnapshotReconstructionError(
                                "numeric field value is not canonical"
                            )
                    except Exception:
                        findings.append(
                            _finding(
                                "INVALID_FIELD_VALUE",
                                f"snapshot field {name} value is invalid",
                            )
                        )
            if isinstance(position, Mapping):
                quantity_field = axis["fields"]["position_quantity"]
                expected_cost_status = position["cost_basis_status"]
                expected_cost_value = position["cost_basis"]
                if (
                    position["quantity_status"] == "available"
                    and position["quantity"] == "0"
                ):
                    expected_cost_status = "not_applicable"
                    expected_cost_value = None
                if (
                    quantity_field.get("status")
                    != position.get("quantity_status")
                    or quantity_field.get("value")
                    != position.get("quantity")
                    or quantity_field.get("unit") != "shares"
                    or axis["fields"]["cost_basis"].get("status")
                    != expected_cost_status
                    or axis["fields"]["cost_basis"].get("value")
                    != expected_cost_value
                    or axis["fields"]["cost_basis"].get("unit")
                    != (
                        scope.get("currency")
                        if isinstance(scope, Mapping)
                        else None
                    )
                ):
                    findings.append(
                        _finding(
                            "POSITION_AXIS_MISMATCH",
                            "position object and field axis disagree",
                        )
                    )
                for name, value, status in (
                    (
                        "quantity",
                        position.get("quantity"),
                        position.get("quantity_status"),
                    ),
                    (
                        "cost_basis",
                        position.get("cost_basis"),
                        position.get("cost_basis_status"),
                    ),
                ):
                    try:
                        decimal_value = _decimal(
                            value, field=f"anchor.position.{name}"
                        )
                        if status == "available" and decimal_value is None:
                            raise LedgerSnapshotReconstructionError(
                                f"{name} available without value"
                            )
                        if status == "missing" and decimal_value is not None:
                            raise LedgerSnapshotReconstructionError(
                                f"{name} missing with value"
                            )
                        if name == "quantity" and (
                            decimal_value is not None and decimal_value < 0
                        ):
                            raise LedgerSnapshotReconstructionError(
                                "negative position quantity"
                            )
                    except Exception:
                        findings.append(
                            _finding(
                                "INVALID_POSITION_VALUE",
                                f"anchor position {name} is invalid",
                            )
                        )
            expected_units = {
                "cash": (
                    scope.get("currency")
                    if isinstance(scope, Mapping)
                    else None
                ),
                "price": (
                    f"{scope.get('currency')}/share"
                    if isinstance(scope, Mapping)
                    else None
                ),
                "nav": (
                    scope.get("currency")
                    if isinstance(scope, Mapping)
                    else None
                ),
                "weight": "ratio",
                "industry": None,
            }
            for name in ("price", "nav", "weight", "industry"):
                field = axis["fields"][name]
                if field != {
                    "status": "missing",
                    "value": None,
                    "unit": expected_units[name],
                    "source_refs": [],
                }:
                    findings.append(
                        _finding(
                            "FABRICATED_P4_VALUATION_FIELD",
                            f"P4 field {name} must remain missing",
                        )
                    )
            cash_field = axis["fields"]["cash"]
            if cash_field.get("unit") != expected_units["cash"]:
                findings.append(
                    _finding(
                        "INVALID_CASH_UNIT",
                        "cash currency does not match episode scope",
                    )
                )
            expected_axis_refs = sorted(
                {
                    ref
                    for field in axis["fields"].values()
                    for ref in field.get("source_refs", [])
                }
            )
            if (
                axis.get("source_refs") != expected_axis_refs
                or anchor.get("source_refs") != expected_axis_refs
            ):
                findings.append(
                    _finding(
                        "INVALID_AXIS_PROVENANCE",
                        "axis/anchor refs do not match field provenance",
                    )
                )
            if axis.get("summary") != (
                "持仓数量与成本、现金及估值组件分别报告；缺失组件未补零。"
            ):
                findings.append(
                    _finding(
                        "INVALID_AXIS_SUMMARY",
                        "snapshot axis summary is not canonical",
                    )
                )
            expected = (
                "missing"
                if field_statuses
                and all(
                    item in {"missing", "not_applicable"}
                    for item in field_statuses
                )
                else "available"
                if field_statuses
                and all(
                    item in {"available", "not_applicable"}
                    for item in field_statuses
                )
                and any(item == "available" for item in field_statuses)
                else "partial"
            )
            if axis.get("status") != "blocked" and axis.get("status") != expected:
                findings.append(
                    _finding(
                        "INVALID_SNAPSHOT_AGGREGATE",
                        "snapshot aggregate does not match field states",
                    )
                )
        if checkpoint_count != 1:
            findings.append(
                _finding(
                    "INVALID_CHECKPOINT_COUNT",
                    "exactly one checkpoint anchor is required",
                )
            )
        if isinstance(binding, Mapping):
            episode_ids = binding.get("episode_event_ids")
            if isinstance(episode_ids, list):
                expected_anchor_keys = {
                    (event_id, anchor_type)
                    for event_id in episode_ids
                    for anchor_type in ("event_pre", "event_post")
                }
                if (
                    set(event_anchor_counts) != expected_anchor_keys
                    or any(count != 1 for count in event_anchor_counts.values())
                ):
                    findings.append(
                        _finding(
                            "INVALID_EVENT_ANCHOR_SET",
                            "event anchors do not close over episode events",
                        )
                    )
        if event_anchor_times and isinstance(baseline, Mapping):
            first_anchor_time = min(event_anchor_times)
            for baseline_name in ("position", "cash"):
                part = baseline.get(baseline_name)
                if (
                    isinstance(part, Mapping)
                    and part.get("status") in {"available", "partial"}
                ):
                    try:
                        if _dt(str(part.get("effective_at"))) >= first_anchor_time:
                            raise LedgerSnapshotReconstructionError(
                                "baseline does not precede event anchors"
                            )
                    except Exception:
                        findings.append(
                            _finding(
                                "BASELINE_EVENT_TIME_INVERSION",
                                "baseline must precede event anchors",
                            )
                        )
    gaps = artifact.get("gaps")
    if not isinstance(gaps, list):
        findings.append(_finding("INVALID_GAPS", "gaps must be a list"))
    else:
        root_gap_payloads: set[str] = set()
        for gap in gaps:
            if not _gap_is_canonical(gap):
                findings.append(
                    _finding(
                        "INVALID_GAP_SEMANTICS",
                        "gap owner/severity/next_step/provenance is invalid",
                    )
                )
                continue
            root_gap_payloads.add(
                _canonical_bytes(gap).decode("utf-8")
            )
        expected_gap_order = sorted(
            gaps,
            key=lambda item: (
                str(item.get("code") if isinstance(item, Mapping) else ""),
                (
                    _canonical_bytes(item)
                    if isinstance(item, Mapping)
                    else b""
                ),
            ),
        )
        if gaps != expected_gap_order:
            findings.append(
                _finding(
                    "NON_CANONICAL_GAP_ORDER",
                    "root gaps are not canonically ordered",
                )
            )
        for anchor_type, payload in anchor_gap_payloads:
            if payload not in root_gap_payloads:
                findings.append(
                    _finding(
                        "ANCHOR_GAP_NOT_ROOTED",
                        "anchor gap is absent from root gaps",
                    )
                )
            if anchor_type == "checkpoint" and (
                {
                    item_payload
                    for item_type, item_payload in anchor_gap_payloads
                    if item_type == "checkpoint"
                }
                != root_gap_payloads
            ):
                findings.append(
                    _finding(
                        "CHECKPOINT_GAPS_MISMATCH",
                        "checkpoint gaps do not equal root gaps",
                    )
                )
                break
    if artifact.get("governance") != _GOVERNANCE:
        findings.append(
            _finding("INVALID_GOVERNANCE", "governance is not closed")
        )
    try:
        material = deepcopy(dict(artifact))
        claimed = material["content_id"]
        material["content_id"] = ""
        if not _SHA256_RE.fullmatch(str(claimed or "")):
            raise LedgerSnapshotReconstructionError("invalid content_id")
        if claimed != _content_id(material):
            raise LedgerSnapshotReconstructionError("content_id mismatch")
    except Exception:
        findings.append(
            _finding("CONTENT_ID_MISMATCH", "content_id does not match")
        )
    unique = {
        json.dumps(item, sort_keys=True, separators=(",", ":")): item
        for item in findings
    }
    ordered = sorted(unique.values(), key=lambda item: item["code"])
    return {
        "schema_version": (
            LEDGER_SNAPSHOT_RECONSTRUCTION_VALIDATION_SCHEMA_VERSION
        ),
        "validation_status": "accepted" if not ordered else "blocked",
        "findings": ordered,
    }


def replay_validate_ledger_snapshot_reconstruction(
    artifact: object,
    *,
    event_inputs: Iterable[Mapping[str, Any]],
    episode: Mapping[str, Any],
    baseline_proof: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Rebuild from exact canonical inputs and require byte identity."""

    validation = validate_ledger_snapshot_reconstruction(artifact)
    findings = list(validation["findings"])
    if isinstance(artifact, Mapping):
        try:
            rebuilt = build_ledger_snapshot_reconstruction(
                event_inputs,
                episode=episode,
                perspective=str(artifact.get("perspective") or ""),
                as_of=str(artifact.get("as_of") or ""),
                knowledge_cutoff=str(
                    artifact.get("knowledge_cutoff") or ""
                ),
                source_binding=artifact["source_binding"]["proof"],
                baseline_proof=baseline_proof,
            )
            if _canonical_bytes(rebuilt) != _canonical_bytes(artifact):
                findings.append(
                    _finding(
                        "SOURCE_REPLAY_MISMATCH",
                        "rebuilt artifact is not byte-identical",
                    )
                )
        except Exception as exc:
            findings.append(
                _finding(
                    "SOURCE_REPLAY_FAILED",
                    f"source replay failed: {type(exc).__name__}",
                )
            )
    unique = {
        json.dumps(item, sort_keys=True, separators=(",", ":")): item
        for item in findings
    }
    ordered = sorted(unique.values(), key=lambda item: item["code"])
    verified = not ordered
    return {
        "schema_version": (
            LEDGER_SNAPSHOT_RECONSTRUCTION_REPLAY_SCHEMA_VERSION
        ),
        "validation_status": "accepted" if verified else "blocked",
        "source_verification": {
            "status": "verified" if verified else "failed",
            "content_id": (
                artifact.get("content_id")
                if isinstance(artifact, Mapping)
                else None
            ),
        },
        "findings": ordered,
    }
