from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

HEALTHY = "healthy"
DEGRADED = "degraded"
CIRCUIT_OPEN = "circuit_open"
QUARANTINED = "quarantined"
UNKNOWN = "unknown"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_utc(value: datetime | None = None) -> str:
    current = value or utc_now()
    return current.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def schema_fingerprint(fields: Iterable[str]) -> str:
    normalized = sorted({str(field).strip() for field in fields if str(field).strip()})
    payload = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def empty_health_ledger() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "updated_at": isoformat_utc(),
        "sources": {},
        "events": [],
    }


def load_health_ledger(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return empty_health_ledger()
    ledger_path = Path(path)
    if not ledger_path.exists():
        return empty_health_ledger()
    payload = yaml.safe_load(ledger_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("source health ledger must be a mapping")
    payload.setdefault("schema_version", 1)
    payload.setdefault("sources", {})
    payload.setdefault("events", [])
    payload.setdefault("updated_at", isoformat_utc())
    return payload


def save_health_ledger(path: str | Path, ledger: Mapping[str, Any]) -> None:
    ledger_path = Path(path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    payload = deepcopy(dict(ledger))
    payload["updated_at"] = isoformat_utc()
    temporary_path = ledger_path.with_suffix(f"{ledger_path.suffix}.tmp")
    temporary_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    temporary_path.replace(ledger_path)


def source_state(
    ledger: Mapping[str, Any],
    source_name: str,
    *,
    now: datetime | None = None,
) -> str:
    current = now or utc_now()
    entry = dict(ledger.get("sources", {}).get(source_name, {}))
    state = str(entry.get("state", UNKNOWN))
    if state == CIRCUIT_OPEN:
        open_until = parse_utc(entry.get("circuit_open_until"))
        if open_until is not None and current >= open_until:
            return DEGRADED
    return state


def should_attempt(
    ledger: Mapping[str, Any],
    source_name: str,
    *,
    now: datetime | None = None,
) -> bool:
    return source_state(ledger, source_name, now=now) not in {CIRCUIT_OPEN, QUARANTINED}


def classify_failure(
    *,
    http_status: int | None = None,
    error_class: str | None = None,
) -> str:
    normalized_error = (error_class or "").strip().lower()
    if normalized_error in {"schema_drift", "field_drift", "schema_mismatch"}:
        return "schema_drift"
    if http_status in {401, 403}:
        return "permission_denied"
    if http_status in {408, 425, 429} or (http_status is not None and http_status >= 500):
        return "transient"
    if normalized_error in {"timeout", "network", "connection", "temporary"}:
        return "transient"
    if http_status in {400, 404, 410, 422}:
        return "permanent"
    return "transient"


def _source_entry(ledger: dict[str, Any], source_name: str) -> dict[str, Any]:
    sources = ledger.setdefault("sources", {})
    entry = sources.setdefault(
        source_name,
        {
            "state": UNKNOWN,
            "consecutive_failures": 0,
            "last_success_at": None,
            "last_failure_at": None,
            "circuit_open_until": None,
            "last_error_class": None,
            "last_http_status": None,
            "last_schema_fingerprint": None,
            "last_capability": None,
        },
    )
    return entry


def _append_event(ledger: dict[str, Any], event: Mapping[str, Any]) -> None:
    events = ledger.setdefault("events", [])
    events.append(dict(event))
    if len(events) > 1000:
        del events[:-1000]


def record_success(
    ledger: Mapping[str, Any],
    *,
    source_name: str,
    capability: str,
    fields: Iterable[str] = (),
    http_status: int | None = 200,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    current = observed_at or utc_now()
    updated = deepcopy(dict(ledger))
    entry = _source_entry(updated, source_name)
    field_tuple = tuple(fields)
    fingerprint = schema_fingerprint(field_tuple) if field_tuple else None
    entry.update(
        {
            "state": HEALTHY,
            "consecutive_failures": 0,
            "last_success_at": isoformat_utc(current),
            "circuit_open_until": None,
            "last_error_class": None,
            "last_http_status": http_status,
            "last_schema_fingerprint": fingerprint,
            "last_capability": capability,
        }
    )
    _append_event(
        updated,
        {
            "observed_at": isoformat_utc(current),
            "source_name": source_name,
            "capability": capability,
            "result": "success",
            "http_status": http_status,
            "schema_fingerprint": fingerprint,
        },
    )
    updated["updated_at"] = isoformat_utc(current)
    return updated


def record_failure(
    ledger: Mapping[str, Any],
    *,
    source_name: str,
    capability: str,
    http_status: int | None = None,
    error_class: str | None = None,
    message: str | None = None,
    observed_at: datetime | None = None,
    transient_failure_threshold: int = 3,
) -> dict[str, Any]:
    current = observed_at or utc_now()
    updated = deepcopy(dict(ledger))
    entry = _source_entry(updated, source_name)
    failure_kind = classify_failure(http_status=http_status, error_class=error_class)
    failure_count = int(entry.get("consecutive_failures") or 0) + 1
    state = DEGRADED
    circuit_open_until: datetime | None = None

    if failure_kind == "permission_denied":
        state = CIRCUIT_OPEN
        circuit_open_until = current + timedelta(hours=24)
    elif failure_kind == "schema_drift":
        state = DEGRADED
    elif failure_kind == "transient" and failure_count >= transient_failure_threshold:
        state = CIRCUIT_OPEN
        circuit_open_until = current + timedelta(minutes=30)
    elif failure_kind == "permanent":
        state = QUARANTINED

    entry.update(
        {
            "state": state,
            "consecutive_failures": failure_count,
            "last_failure_at": isoformat_utc(current),
            "circuit_open_until": isoformat_utc(circuit_open_until)
            if circuit_open_until
            else None,
            "last_error_class": failure_kind,
            "last_http_status": http_status,
            "last_capability": capability,
        }
    )
    _append_event(
        updated,
        {
            "observed_at": isoformat_utc(current),
            "source_name": source_name,
            "capability": capability,
            "result": "failure",
            "failure_kind": failure_kind,
            "http_status": http_status,
            "message": message,
            "state_after": state,
        },
    )
    updated["updated_at"] = isoformat_utc(current)
    return updated
