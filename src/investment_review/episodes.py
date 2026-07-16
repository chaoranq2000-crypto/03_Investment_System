"""Deterministic P2C trade-episode projection and read surface."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from .models import canonical_json


EPISODE_SCHEMA_VERSION = "portfolio.trade_episode.v1"
COLLECTION_SCHEMA_VERSION = "portfolio.trade_episode.collection.v1"
VALIDATION_SCHEMA_VERSION = "portfolio.trade_episode.validation.v1"
PROJECTION_VERSION = "p2c_v1"

_SEVERITY_ORDER = {"blocker": 0, "warning": 1, "info": 2}
_POSITION_SIDES = {"BUY": Decimal(1), "SELL": Decimal(-1), "TRANSFER_IN": Decimal(1), "TRANSFER_OUT": Decimal(-1)}
_NON_POSITION_TYPES = {"dividend", "cash_fee"}
_SPECIAL_QUANTITY_TYPES = {"opening", "transfer", "corporate_action", "correction"}


class EpisodeProjectionError(ValueError):
    """Raised when an episode artifact or projection input is invalid."""


def _sha256(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _decimal(value: object, *, field: str) -> Decimal:
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise EpisodeProjectionError(f"invalid {field}: {value!r}") from exc
    if not result.is_finite():
        raise EpisodeProjectionError(f"non-finite {field}: {value!r}")
    return result


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _aware_datetime(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise EpisodeProjectionError(f"{field} is required")
    text = value.strip().replace("Z", "+00:00")
    try:
        result = datetime.fromisoformat(text)
    except ValueError as exc:
        raise EpisodeProjectionError(f"invalid {field}: {value!r}") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise EpisodeProjectionError(f"{field} must include a timezone")
    return result


def _optional_aware_datetime(value: object, *, field: str) -> datetime | None:
    if value in (None, ""):
        return None
    return _aware_datetime(value, field=field)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _finding(
    severity: str,
    code: str,
    message: str,
    *,
    related_refs: Iterable[str] = (),
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if severity not in _SEVERITY_ORDER:
        raise EpisodeProjectionError(f"unsupported finding severity: {severity}")
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "related_refs": sorted({str(item) for item in related_refs if str(item)}),
        "details": dict(details or {}),
    }


def _sorted_findings(findings: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for finding in findings:
        normalized = dict(finding)
        normalized["related_refs"] = sorted(set(normalized.get("related_refs", [])))
        normalized["details"] = dict(normalized.get("details", {}))
        unique[canonical_json(normalized)] = normalized
    return sorted(
        unique.values(),
        key=lambda item: (
            _SEVERITY_ORDER.get(str(item.get("severity")), 99),
            str(item.get("code", "")),
            canonical_json(item.get("related_refs", [])),
            canonical_json(item.get("details", {})),
        ),
    )


def _validation_status(findings: Iterable[Mapping[str, Any]]) -> str:
    severities = {str(item.get("severity")) for item in findings}
    if "blocker" in severities:
        return "blocked"
    if "warning" in severities:
        return "accepted_with_warnings"
    return "accepted"


def _raw_payload(value: object) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        parsed = json.loads(value)
        if not isinstance(parsed, Mapping):
            raise EpisodeProjectionError("raw_payload_json must decode to an object")
        return dict(parsed)
    raise EpisodeProjectionError("raw_payload must be an object")


def _source_row(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    value = raw.get("source_row", raw)
    return value if isinstance(value, Mapping) else raw


def _source_sequence(raw: Mapping[str, Any], source_record_id: str | None, event_id: str) -> tuple[int, str]:
    row = _source_row(raw)
    for key in ("source_sequence", "source_row", "entry_id", "row_index"):
        value = row.get(key)
        if value not in (None, ""):
            try:
                return (0, f"{int(value):020d}")
            except (TypeError, ValueError):
                return (1, str(value))
    return (2, source_record_id or event_id)


def _source_keys(raw: Mapping[str, Any], source_record_id: str | None) -> tuple[str, ...]:
    row = _source_row(raw)
    values = [source_record_id, row.get("dedupe_key"), row.get("external_id")]
    account = row.get("account_id")
    external_id = row.get("external_id")
    if account not in (None, "") and external_id not in (None, ""):
        values.append(f"{account}::{external_id}")
    return tuple(sorted({str(value) for value in values if value not in (None, "")}))


def _source_known_at(raw: Mapping[str, Any], fallback: datetime) -> datetime | None:
    row = _source_row(raw)
    value = row.get("created_at") or raw.get("source_known_at")
    try:
        return _optional_aware_datetime(value, field="source_known_at") or fallback
    except EpisodeProjectionError:
        return None


@dataclass(frozen=True)
class ProjectionEvent:
    event_id: str
    source_id: str
    source_record_id: str | None
    payload_sha256: str
    event_type: str
    occurred_at: datetime
    known_at: datetime
    account: str
    market: str | None
    symbol: str
    side: str
    quantity: Decimal
    currency: str
    raw_payload: Mapping[str, Any]
    decision_refs: tuple[Mapping[str, Any], ...]
    source_sequence: tuple[int, str]
    source_keys: tuple[str, ...]
    source_known_at: datetime | None
    known_at_fallback: bool

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ProjectionEvent":
        event_id = str(payload.get("event_id") or "").strip()
        source_id = str(payload.get("source_id") or "").strip()
        account = str(payload.get("account") or "").strip()
        symbol = str(payload.get("symbol") or "").strip().upper()
        side = str(payload.get("side") or "").strip().upper()
        if not event_id:
            raise EpisodeProjectionError("event_id is required")
        if not source_id:
            raise EpisodeProjectionError("source_id is required")
        if not account:
            raise EpisodeProjectionError("account is required for episode partitioning")
        if not symbol:
            raise EpisodeProjectionError("symbol is required")
        if side not in _POSITION_SIDES and side != "OTHER":
            raise EpisodeProjectionError(f"unsupported side: {side!r}")
        occurred_at = _aware_datetime(payload.get("occurred_at"), field="occurred_at")
        known_at = _aware_datetime(payload.get("known_at"), field="known_at")
        if known_at < occurred_at:
            raise EpisodeProjectionError("known_at cannot be earlier than occurred_at")
        raw = _raw_payload(payload.get("raw_payload", payload.get("raw_payload_json")))
        source_record_id = (
            str(payload.get("source_record_id")).strip()
            if payload.get("source_record_id") not in (None, "")
            else None
        )
        quantity = _decimal(payload.get("quantity"), field="quantity")
        if quantity < 0:
            raise EpisodeProjectionError("quantity must be non-negative; use side for direction")
        decisions = payload.get("decision_refs", [])
        if not isinstance(decisions, Sequence) or isinstance(decisions, (str, bytes)):
            raise EpisodeProjectionError("decision_refs must be a list")
        return cls(
            event_id=event_id,
            source_id=source_id,
            source_record_id=source_record_id,
            payload_sha256=str(payload.get("payload_sha256") or "").strip(),
            event_type=str(payload.get("event_type") or "fill").strip().lower(),
            occurred_at=occurred_at,
            known_at=known_at,
            account=account,
            market=(str(payload.get("market")).strip().upper() if payload.get("market") else None),
            symbol=symbol,
            side=side,
            quantity=quantity,
            currency=str(payload.get("currency") or "CNY").strip().upper(),
            raw_payload=raw,
            decision_refs=tuple(dict(item) for item in decisions if isinstance(item, Mapping)),
            source_sequence=_source_sequence(raw, source_record_id, event_id),
            source_keys=_source_keys(raw, source_record_id),
            source_known_at=_source_known_at(raw, known_at),
            known_at_fallback=bool(raw.get("known_at_fallback")),
        )

    @property
    def partition_key(self) -> tuple[str, str, str, str]:
        return (self.account, self.market or "", self.symbol, self.currency)

    @property
    def instrument_id(self) -> str:
        if self.market and not self.symbol.endswith(f".{self.market}"):
            return f"{self.market}.{self.symbol}"
        return self.symbol

    @property
    def ordering_key(self) -> tuple[datetime, int, str, str]:
        return (self.occurred_at, self.source_sequence[0], self.source_sequence[1], self.event_id)

    @property
    def signed_quantity(self) -> Decimal | None:
        multiplier = _POSITION_SIDES.get(self.side)
        return self.quantity * multiplier if multiplier is not None else None

    def digest_payload(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source_id": self.source_id,
            "source_record_id": self.source_record_id,
            "payload_sha256": self.payload_sha256,
            "event_type": self.event_type,
            "occurred_at": _iso(self.occurred_at),
            "known_at": _iso(self.known_at),
            "account": self.account,
            "market": self.market,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": _decimal_text(self.quantity),
            "currency": self.currency,
            "source_keys": list(self.source_keys),
        }


def _normalize_snapshots(
    snapshots: Iterable[Mapping[str, Any]], events: Sequence[ProjectionEvent]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_to_event: dict[str, set[str]] = defaultdict(set)
    for event in events:
        for source_key in event.source_keys:
            source_to_event[source_key].add(event.event_id)
    normalized: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for raw_snapshot in snapshots:
        try:
            snapshot_id = str(raw_snapshot.get("snapshot_id") or "").strip()
            account_id = str(raw_snapshot.get("account_id") or "").strip()
            if not snapshot_id or not account_id:
                raise EpisodeProjectionError("snapshot_id and account_id are required")
            as_of_date = date.fromisoformat(str(raw_snapshot.get("as_of_date")))
            cutoff = _optional_aware_datetime(
                raw_snapshot.get("knowledge_cutoff_at"), field="snapshot.knowledge_cutoff_at"
            )
            explicit_ids = {str(value) for value in raw_snapshot.get("included_event_ids", [])}
            for source_key in raw_snapshot.get("included_source_keys", []):
                explicit_ids.update(source_to_event.get(str(source_key), set()))
            cursor_scope = str(raw_snapshot.get("cursor_scope") or "partition")
            if cursor_scope not in {"account", "partition"}:
                raise EpisodeProjectionError(
                    "snapshot cursor_scope must be account or partition"
                )
            included_event_set_complete = (
                raw_snapshot.get("included_event_set_complete") is True
            )
            if cursor_scope != "account" and included_event_set_complete:
                raise EpisodeProjectionError(
                    "included_event_set_complete requires account cursor_scope"
                )
            normalized.append(
                {
                    "snapshot_id": snapshot_id,
                    "account_id": account_id,
                    "as_of_date": as_of_date.isoformat(),
                    "knowledge_cutoff_at": _iso(cutoff) if cutoff else None,
                    "revision": int(raw_snapshot.get("revision") or 1),
                    "engine_version": str(raw_snapshot.get("engine_version") or ""),
                    "source_state_hash": str(raw_snapshot.get("source_state_hash") or ""),
                    "source_path": str(raw_snapshot.get("source_path") or ""),
                    "instrument_ids": sorted({str(value).upper() for value in raw_snapshot.get("instrument_ids", [])}),
                    "included_event_ids": sorted(explicit_ids),
                    "cursor_scope": cursor_scope,
                    "included_event_set_complete": included_event_set_complete,
                }
            )
        except Exception as exc:
            findings.append(
                _finding(
                    "blocker",
                    "INVALID_SNAPSHOT_REFERENCE",
                    str(exc),
                    related_refs=[str(raw_snapshot.get("snapshot_id") or "unknown_snapshot")],
                )
            )
    normalized.sort(
        key=lambda item: (
            item["account_id"],
            item["as_of_date"],
            item["knowledge_cutoff_at"] or "",
            item["revision"],
            item["snapshot_id"],
        )
    )
    return normalized, findings


def load_p2b_snapshot_references(
    database: str | Path, *, account: str | None = None
) -> list[dict[str, Any]]:
    """Read only the P2B snapshot reference contract; never mutate the portfolio DB."""

    path = Path(database)
    if not path.exists():
        raise FileNotFoundError(path)
    uri = f"{path.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        required = {"portfolio_snapshots", "position_snapshots"}
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if not required.issubset(tables):
            raise EpisodeProjectionError(
                f"portfolio database lacks P2B snapshot tables: {sorted(required - tables)}"
            )
        params: list[Any] = []
        where = ""
        if account:
            where = "WHERE account_id = ?"
            params.append(account)
        rows = connection.execute(
            f"""
            SELECT snapshot_id, account_id, as_of_date, knowledge_cutoff_at,
                   revision, engine_version, source_state_hash
            FROM portfolio_snapshots {where}
            ORDER BY account_id, as_of_date, revision, snapshot_id
            """,
            params,
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            instruments: set[str] = set()
            source_keys: set[str] = set()
            for position in connection.execute(
                "SELECT ts_code, lineage_json FROM position_snapshots WHERE snapshot_id = ? ORDER BY ts_code",
                (row["snapshot_id"],),
            ):
                instruments.add(str(position["ts_code"]).upper())
                lineage = json.loads(position["lineage_json"])
                for transaction in lineage.get("transactions", []):
                    if transaction.get("dedupe_key"):
                        source_keys.add(str(transaction["dedupe_key"]))
            result.append(
                {
                    "snapshot_id": row["snapshot_id"],
                    "account_id": row["account_id"],
                    "as_of_date": row["as_of_date"],
                    "knowledge_cutoff_at": row["knowledge_cutoff_at"] or None,
                    "revision": row["revision"],
                    "engine_version": row["engine_version"],
                    "source_state_hash": row["source_state_hash"],
                    "source_path": str(path.resolve()),
                    "instrument_ids": sorted(instruments),
                    "included_source_keys": sorted(source_keys),
                }
            )
        return result
    finally:
        connection.close()


def _snapshot_link(
    *,
    role: str,
    event: ProjectionEvent | None,
    snapshot: Mapping[str, Any] | None,
    method: str,
    reason: str | None = None,
    distance_seconds: int | None = None,
) -> dict[str, Any]:
    return {
        "link_role": role,
        "snapshot_ref": snapshot.get("snapshot_id") if snapshot else None,
        "link_method": method,
        "snapshot_as_of": snapshot.get("as_of_date") if snapshot else None,
        "snapshot_knowledge_cutoff_at": snapshot.get("knowledge_cutoff_at") if snapshot else None,
        "event_ref": event.event_id if event else None,
        "event_time": _iso(event.occurred_at) if event else None,
        "temporal_distance_seconds": distance_seconds,
        "validation_status": "linked" if snapshot else "missing",
        "reason": reason,
    }


def _link_snapshots(
    episode: Mapping[str, Any],
    event_map: Mapping[str, ProjectionEvent],
    snapshots: Sequence[Mapping[str, Any]],
    cutoff: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    account = episode["scope"]["account_id"]
    partition_events = [event_map[item["event_id"]] for item in episode["event_refs"]]
    all_partition_events = sorted(
        [event for event in event_map.values() if event.partition_key == partition_events[0].partition_key],
        key=lambda event: event.ordering_key,
    )
    links: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    timezone = ZoneInfo("Asia/Shanghai")

    for index, event in enumerate(partition_events):
        if index == 0:
            before_role = "before_open"
            after_role = "after_open"
        elif episode.get("closing_event_ref") == event.event_id:
            before_role = "before_close"
            after_role = "after_close"
        else:
            before_role = "before_change"
            after_role = "after_change"
        event_date = event.occurred_at.astimezone(timezone).date()
        safe_before: list[tuple[datetime, Mapping[str, Any]]] = []
        for snapshot in snapshots:
            if snapshot["account_id"] != account:
                continue
            snapshot_cutoff = _optional_aware_datetime(
                snapshot.get("knowledge_cutoff_at"), field="snapshot.knowledge_cutoff_at"
            )
            if (
                snapshot_cutoff is not None
                and snapshot_cutoff <= event.occurred_at
                and date.fromisoformat(snapshot["as_of_date"]) <= event_date
            ):
                safe_before.append((snapshot_cutoff, snapshot))
        if safe_before:
            snapshot_cutoff, selected = max(
                safe_before,
                key=lambda item: (
                    item[0],
                    item[1]["as_of_date"],
                    item[1]["revision"],
                    item[1]["snapshot_id"],
                ),
            )
            distance = max(0, int((event.occurred_at - snapshot_cutoff).total_seconds()))
            links.append(
                _snapshot_link(
                    role=before_role,
                    event=event,
                    snapshot=selected,
                    method="latest_at_or_before",
                    distance_seconds=distance,
                )
            )
            if distance:
                findings.append(
                    _finding(
                        "warning",
                        "SNAPSHOT_FALLBACK_USED",
                        "state-before linkage used the latest point-in-time-safe snapshot",
                        related_refs=[event.event_id, selected["snapshot_id"]],
                        details={"temporal_distance_seconds": distance},
                    )
                )
        else:
            links.append(
                _snapshot_link(
                    role=before_role,
                    event=event,
                    snapshot=None,
                    method="missing",
                    reason="no_point_in_time_safe_snapshot_before_event",
                )
            )
            findings.append(
                _finding(
                    "warning",
                    "SNAPSHOT_LINK_MISSING",
                    "no point-in-time-safe state-before snapshot was available",
                    related_refs=[event.event_id],
                    details={"link_role": before_role},
                )
            )

        later_event_ids = {
            candidate.event_id
            for candidate in all_partition_events
            if candidate.ordering_key > event.ordering_key
        }
        exact_after: list[tuple[datetime, Mapping[str, Any]]] = []
        for snapshot in snapshots:
            if snapshot["account_id"] != account:
                continue
            snapshot_cutoff = _optional_aware_datetime(
                snapshot.get("knowledge_cutoff_at"), field="snapshot.knowledge_cutoff_at"
            )
            included = set(snapshot.get("included_event_ids", []))
            if (
                snapshot_cutoff is not None
                and snapshot_cutoff <= cutoff
                and date.fromisoformat(snapshot["as_of_date"]) == event_date
                and event.event_id in included
                and not included.intersection(later_event_ids)
                and event.source_known_at is not None
                and snapshot_cutoff >= event.source_known_at
            ):
                exact_after.append((snapshot_cutoff, snapshot))
        if exact_after:
            _, selected = min(exact_after, key=lambda item: (item[0], item[1]["revision"], item[1]["snapshot_id"]))
            links.append(
                _snapshot_link(
                    role=after_role,
                    event=event,
                    snapshot=selected,
                    method="exact_event_cursor",
                )
            )
        else:
            links.append(
                _snapshot_link(
                    role=after_role,
                    event=event,
                    snapshot=None,
                    method="missing",
                    reason="no_snapshot_proves_event_inclusion_without_later_events",
                )
            )
            findings.append(
                _finding(
                    "warning",
                    "SNAPSHOT_LINK_MISSING",
                    "no snapshot proved the state immediately after this event",
                    related_refs=[event.event_id],
                    details={"link_role": after_role},
                )
            )

    if episode["status"] in {"open", "data_gap"}:
        cutoff_date = cutoff.astimezone(timezone).date()
        candidates: list[tuple[datetime, Mapping[str, Any]]] = []
        for snapshot in snapshots:
            snapshot_cutoff = _optional_aware_datetime(
                snapshot.get("knowledge_cutoff_at"), field="snapshot.knowledge_cutoff_at"
            )
            if (
                snapshot["account_id"] == account
                and snapshot_cutoff is not None
                and snapshot_cutoff <= cutoff
                and date.fromisoformat(snapshot["as_of_date"]) <= cutoff_date
            ):
                candidates.append((snapshot_cutoff, snapshot))
        if candidates:
            snapshot_cutoff, selected = max(
                candidates,
                key=lambda item: (item[0], item[1]["as_of_date"], item[1]["revision"], item[1]["snapshot_id"]),
            )
            distance = int((cutoff - snapshot_cutoff).total_seconds())
            links.append(
                _snapshot_link(
                    role="at_cutoff",
                    event=None,
                    snapshot=selected,
                    method="latest_at_or_before",
                    distance_seconds=distance,
                )
            )
            if distance:
                findings.append(
                    _finding(
                        "warning",
                        "SNAPSHOT_FALLBACK_USED",
                        "open-episode cutoff used the latest point-in-time-safe snapshot",
                        related_refs=[episode["episode_id"], selected["snapshot_id"]],
                        details={"temporal_distance_seconds": distance},
                    )
                )
        else:
            links.append(
                _snapshot_link(
                    role="at_cutoff",
                    event=None,
                    snapshot=None,
                    method="missing",
                    reason="no_point_in_time_safe_snapshot_at_cutoff",
                )
            )
            findings.append(
                _finding(
                    "warning",
                    "SNAPSHOT_LINK_MISSING",
                    "no point-in-time-safe snapshot was available at the episode cutoff",
                    related_refs=[episode["episode_id"]],
                    details={"link_role": "at_cutoff"},
                )
            )
    return links, findings


def _decision_linkage(events: Sequence[ProjectionEvent]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    refs: dict[str, dict[str, Any]] = {}
    findings: list[dict[str, Any]] = []
    event_by_id = {event.event_id: event for event in events}
    for event in events:
        for raw_ref in event.decision_refs:
            ref = dict(raw_ref)
            decision_id = str(ref.get("decision_id") or "").strip()
            if not decision_id:
                continue
            ref.setdefault("event_id", event.event_id)
            ref.setdefault("link_source", "decision_event_links")
            refs[decision_id] = ref
    if not refs:
        findings.append(
            _finding(
                "info",
                "DECISION_LINK_UNAVAILABLE",
                "no explicit Decision reference was supplied; no inference was made",
            )
        )
        return {"status": "unlinked", "decision_refs": [], "reason": "no_explicit_upstream_reference"}, findings

    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for decision_id, ref in sorted(refs.items()):
        event = event_by_id.get(str(ref.get("event_id") or ""))
        try:
            if ref.get("link_source") != "decision_event_links":
                raise EpisodeProjectionError("Decision reference is not from the explicit link registry")
            if event is None:
                raise EpisodeProjectionError("linked execution event is not in the episode")
            if str(ref.get("symbol") or "").strip().upper() != event.symbol:
                raise EpisodeProjectionError("Decision symbol does not match the linked event")
            decision_market = str(ref.get("market") or "").strip().upper()
            if decision_market and event.market and decision_market != event.market:
                raise EpisodeProjectionError("Decision market does not match the linked event")
            known_at = _aware_datetime(ref.get("known_at"), field="decision.known_at")
            if known_at > event.occurred_at:
                raise EpisodeProjectionError("Decision was not known by the linked execution time")
            valid.append(ref)
        except EpisodeProjectionError as exc:
            invalid.append(ref)
            findings.append(
                _finding(
                    "blocker",
                    "DECISION_LINK_INVALID",
                    str(exc),
                    related_refs=[decision_id, str(ref.get("event_id") or "")],
                )
            )
    if invalid:
        return {"status": "invalid", "decision_refs": sorted(refs), "reason": "explicit_reference_failed_validation"}, findings
    if len(valid) > 1:
        findings.append(
            _finding(
                "blocker",
                "DECISION_LINK_AMBIGUOUS",
                "multiple explicit Decision references require manual resolution",
                related_refs=sorted(refs),
            )
        )
        return {"status": "ambiguous", "decision_refs": sorted(refs), "reason": "multiple_explicit_references"}, findings
    return {"status": "linked", "decision_refs": sorted(refs), "reason": "explicit_registry_link"}, findings


def _episode_digest_payload(episode: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(episode))
    payload.pop("validation", None)
    lineage = dict(payload.get("lineage", {}))
    lineage.pop("canonical_content_digest", None)
    payload["lineage"] = lineage
    return payload


def _make_episode(
    draft: Mapping[str, Any],
    *,
    cutoff: datetime,
    event_map: Mapping[str, ProjectionEvent],
    snapshots: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    events = [event_map[event_id] for event_id in draft["event_ids"]]
    opening = events[0]
    episode_id = "te_" + _sha256(
        {
            "schema_version": EPISODE_SCHEMA_VERSION,
            "account": opening.account,
            "instrument": opening.instrument_id,
            "currency": opening.currency,
            "opening_event_id": opening.event_id,
        }
    )[:32]
    status = str(draft["status"])
    closed_at = _iso(events[-1].occurred_at) if draft.get("closed") else None
    event_refs = []
    for item in draft["transitions"]:
        event = event_map[item["event_id"]]
        event_refs.append(
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "effective_at": _iso(event.occurred_at),
                "known_at": _iso(event.known_at),
                "side": event.side,
                "signed_quantity": _decimal_text(item["signed_quantity"]),
                "quantity_before": _decimal_text(item["quantity_before"]),
                "quantity_after": _decimal_text(item["quantity_after"]),
                "source_refs": {
                    "source_id": event.source_id,
                    "source_record_id": event.source_record_id,
                    "payload_sha256": event.payload_sha256,
                    "source_keys": list(event.source_keys),
                },
                "ordering_key": [
                    _iso(event.occurred_at),
                    event.source_sequence[0],
                    event.source_sequence[1],
                    event.event_id,
                ],
            }
        )
    decision_linkage, decision_findings = _decision_linkage(events)
    episode: dict[str, Any] = {
        "schema_version": EPISODE_SCHEMA_VERSION,
        "episode_id": episode_id,
        "projection_version": PROJECTION_VERSION,
        "scope": {
            "account_id": opening.account,
            "instrument_id": opening.instrument_id,
            "symbol": opening.symbol,
            "market": opening.market,
            "currency": opening.currency,
        },
        "status": status,
        "origin": draft["origin"],
        "direction": "long" if draft["first_quantity"] > 0 else "short",
        "opened_at": _iso(opening.occurred_at),
        "closed_at": closed_at,
        "cutoff_at": _iso(cutoff),
        "opening_event_ref": opening.event_id,
        "closing_event_ref": events[-1].event_id if draft.get("closed") else None,
        "starting_quantity": "0",
        "ending_quantity": _decimal_text(draft["ending_quantity"]),
        "maximum_absolute_quantity": _decimal_text(draft["maximum_absolute_quantity"]),
        "material_transition_count": len(events),
        "event_refs": event_refs,
        "snapshot_links": [],
        "decision_linkage": decision_linkage,
        "lineage": {
            "normalized_event_digest": _sha256([event.digest_payload() for event in events]),
            "snapshot_set_digest": _sha256([]),
            "input_digest": _sha256([event.digest_payload() for event in events]),
            "canonical_content_digest": "",
            "builder_version": PROJECTION_VERSION,
        },
    }
    links, snapshot_findings = _link_snapshots(episode, event_map, snapshots, cutoff)
    episode["snapshot_links"] = links
    episode["lineage"]["snapshot_set_digest"] = _sha256(links)
    episode["lineage"]["canonical_content_digest"] = _sha256(_episode_digest_payload(episode))
    findings = list(draft.get("findings", [])) + decision_findings + snapshot_findings
    validation = validate_episode(episode, snapshot_catalog=snapshots)
    findings.extend(validation["findings"])
    findings = _sorted_findings(findings)
    episode["validation"] = {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "validation_status": _validation_status(findings),
        "findings": findings,
    }
    return episode


def _new_draft(event: ProjectionEvent, delta: Decimal) -> dict[str, Any]:
    is_gap = event.event_type in _SPECIAL_QUANTITY_TYPES or event.side == "TRANSFER_IN"
    ambiguous = event.side in {"SELL", "TRANSFER_OUT"}
    findings: list[dict[str, Any]] = []
    if is_gap:
        findings.append(
            _finding(
                "warning",
                "OPENING_BALANCE_INCOMPLETE_HISTORY",
                "the first observed non-zero state is typed as an opening balance, transfer, correction, or corporate action",
                related_refs=[event.event_id],
            )
        )
    if ambiguous:
        findings.append(
            _finding(
                "blocker",
                "FLAT_OUTFLOW_WITHOUT_OPEN_POSITION",
                "a sell or transfer-out from flat cannot be classified without guessing prior state",
                related_refs=[event.event_id],
            )
        )
    if event.known_at_fallback:
        findings.append(
            _finding(
                "warning",
                "KNOWN_AT_FALLBACK",
                "upstream known_at fell back to occurred_at and is not independent historical knowledge evidence",
                related_refs=[event.event_id],
            )
        )
    return {
        "event_ids": [event.event_id],
        "transitions": [
            {
                "event_id": event.event_id,
                "signed_quantity": delta,
                "quantity_before": Decimal(0),
                "quantity_after": delta,
            }
        ],
        "origin": "ambiguous_flat_outflow" if ambiguous else "opening_balance_or_incomplete_history" if is_gap else "explicit_trade",
        "status": "ambiguous" if ambiguous else "data_gap" if is_gap else "open",
        "first_quantity": delta,
        "ending_quantity": delta,
        "maximum_absolute_quantity": abs(delta),
        "closed": False,
        "findings": findings,
    }


def build_episode_collection(
    event_inputs: Iterable[Mapping[str, Any]],
    *,
    cutoff_at: str,
    snapshot_references: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build the canonical P2C projection without writing either source database."""

    cutoff = _aware_datetime(cutoff_at, field="cutoff_at")
    raw_events = [dict(item) for item in event_inputs]
    raw_events.sort(key=canonical_json)
    collection_findings: list[dict[str, Any]] = []
    ledger: dict[str, dict[str, Any]] = {}

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in raw_events:
        key = str(item.get("event_id") or f"invalid_{_sha256(item)[:24]}")
        buckets[key].append(item)

    events: list[ProjectionEvent] = []
    occurrence_counts: dict[str, int] = {}
    for event_key, occurrences in sorted(buckets.items()):
        occurrence_counts[event_key] = len(occurrences)
        fingerprints = {canonical_json(item) for item in occurrences}
        if len(fingerprints) > 1:
            ledger[event_key] = {
                "event_id": event_key,
                "outcome": "rejected_conflict",
                "reason": "same event_id appeared with different content",
                "input_occurrences": len(occurrences),
                "episode_id": None,
            }
            collection_findings.append(
                _finding(
                    "blocker",
                    "CONFLICTING_DUPLICATE_EVENT",
                    "the same event_id appeared with different content",
                    related_refs=[event_key],
                )
            )
            continue
        try:
            event = ProjectionEvent.from_mapping(occurrences[0])
        except Exception as exc:
            ledger[event_key] = {
                "event_id": event_key,
                "outcome": "rejected_invalid",
                "reason": str(exc),
                "input_occurrences": len(occurrences),
                "episode_id": None,
            }
            collection_findings.append(
                _finding("blocker", "INVALID_EVENT", str(exc), related_refs=[event_key])
            )
            continue
        if len(occurrences) > 1:
            collection_findings.append(
                _finding(
                    "info",
                    "EXACT_DUPLICATE_EVENT",
                    "exact duplicate inputs were deduplicated under the stable event identity",
                    related_refs=[event.event_id],
                    details={"input_occurrences": len(occurrences)},
                )
            )
        if event.occurred_at > cutoff:
            ledger[event.event_id] = {
                "event_id": event.event_id,
                "outcome": "excluded_after_cutoff",
                "reason": "occurred_at is later than the projection cutoff",
                "input_occurrences": len(occurrences),
                "episode_id": None,
            }
            continue
        if event.known_at > cutoff:
            ledger[event.event_id] = {
                "event_id": event.event_id,
                "outcome": "excluded_not_known_at_cutoff",
                "reason": "known_at is later than the projection cutoff",
                "input_occurrences": len(occurrences),
                "episode_id": None,
            }
            collection_findings.append(
                _finding(
                    "info",
                    "EVENT_NOT_KNOWN_AT_CUTOFF",
                    "event was preserved but excluded by the no-lookahead cutoff",
                    related_refs=[event.event_id],
                )
            )
            continue
        events.append(event)
        ledger[event.event_id] = {
            "event_id": event.event_id,
            "outcome": "pending",
            "reason": None,
            "input_occurrences": len(occurrences),
            "episode_id": None,
        }

    events.sort(key=lambda item: (item.partition_key, item.ordering_key))
    snapshots, snapshot_findings = _normalize_snapshots(snapshot_references, events)
    collection_findings.extend(snapshot_findings)
    event_map = {event.event_id: event for event in events}
    drafts: list[dict[str, Any]] = []

    by_partition: dict[tuple[str, str, str, str], list[ProjectionEvent]] = defaultdict(list)
    for event in events:
        by_partition[event.partition_key].append(event)

    for partition_events in by_partition.values():
        partition_events.sort(key=lambda item: item.ordering_key)
        active: dict[str, Any] | None = None
        current_quantity = Decimal(0)
        partition_blocked = False
        for event in partition_events:
            if event.event_type in _NON_POSITION_TYPES and event.side == "OTHER":
                ledger[event.event_id]["outcome"] = "non_position_changing"
                ledger[event.event_id]["reason"] = f"typed {event.event_type} event"
                continue
            delta = event.signed_quantity
            if delta is None:
                if event.quantity == 0:
                    ledger[event.event_id]["outcome"] = "non_position_changing"
                    ledger[event.event_id]["reason"] = "zero-quantity OTHER event"
                    continue
                ledger[event.event_id]["outcome"] = "rejected_ambiguous"
                ledger[event.event_id]["reason"] = "non-zero OTHER event has no deterministic direction"
                collection_findings.append(
                    _finding(
                        "blocker",
                        "AMBIGUOUS_QUANTITY_EFFECT",
                        "non-zero OTHER event has no deterministic signed quantity",
                        related_refs=[event.event_id],
                    )
                )
                continue
            if event.quantity <= 0:
                ledger[event.event_id]["outcome"] = "rejected_invalid"
                ledger[event.event_id]["reason"] = "position-changing event quantity must be positive"
                collection_findings.append(
                    _finding(
                        "blocker",
                        "NON_POSITIVE_POSITION_QUANTITY",
                        "position-changing event quantity must be positive",
                        related_refs=[event.event_id],
                    )
                )
                continue
            if partition_blocked:
                ledger[event.event_id]["outcome"] = "blocked_after_ambiguous_boundary"
                ledger[event.event_id]["reason"] = "earlier sign reversal left the lifecycle boundary unresolved"
                continue
            before = current_quantity
            after = before + delta
            if before == 0:
                active = _new_draft(event, delta)
                current_quantity = after
                if active["status"] == "ambiguous":
                    drafts.append(active)
                    active = None
                    partition_blocked = True
                continue
            if active is None:
                ledger[event.event_id]["outcome"] = "blocked_without_active_episode"
                ledger[event.event_id]["reason"] = "non-zero position had no active auditable episode"
                continue
            active["event_ids"].append(event.event_id)
            active["transitions"].append(
                {
                    "event_id": event.event_id,
                    "signed_quantity": delta,
                    "quantity_before": before,
                    "quantity_after": after,
                }
            )
            active["ending_quantity"] = after
            active["maximum_absolute_quantity"] = max(active["maximum_absolute_quantity"], abs(after))
            if event.known_at_fallback:
                active["findings"].append(
                    _finding(
                        "warning",
                        "KNOWN_AT_FALLBACK",
                        "upstream known_at fell back to occurred_at and is not independent historical knowledge evidence",
                        related_refs=[event.event_id],
                    )
                )
            if event.event_type in _SPECIAL_QUANTITY_TYPES:
                active["findings"].append(
                    _finding(
                        "warning",
                        "TYPED_QUANTITY_ADJUSTMENT",
                        "a transfer, correction, corporate action, or opening adjustment affected episode quantity",
                        related_refs=[event.event_id],
                        details={"event_type": event.event_type},
                    )
                )
            if after == 0:
                active["closed"] = True
                active["status"] = "data_gap" if active["status"] == "data_gap" else "closed"
                drafts.append(active)
                active = None
            elif before * after < 0:
                active["status"] = "ambiguous"
                active["findings"].append(
                    _finding(
                        "blocker",
                        "UNSPLIT_SIGN_REVERSAL",
                        "one normalized event crossed through flat and cannot belong to two episodes",
                        related_refs=[event.event_id],
                    )
                )
                drafts.append(active)
                active = None
                partition_blocked = True
            current_quantity = after
        if active is not None:
            active["status"] = "data_gap" if active["status"] == "data_gap" else "open"
            drafts.append(active)

    episodes = [
        _make_episode(draft, cutoff=cutoff, event_map=event_map, snapshots=snapshots)
        for draft in drafts
    ]
    episodes.sort(key=lambda item: (item["scope"]["account_id"], item["scope"]["instrument_id"], item["opened_at"], item["episode_id"]))
    for episode in episodes:
        for event_ref in episode["event_refs"]:
            item = ledger[event_ref["event_id"]]
            item["outcome"] = "consumed"
            item["episode_id"] = episode["episode_id"]
    for item in ledger.values():
        if item["outcome"] == "pending":
            item["outcome"] = "unassigned"
            item["reason"] = "accepted event was not classified"
            collection_findings.append(
                _finding(
                    "blocker",
                    "ACCEPTED_EVENT_UNASSIGNED",
                    "accepted event was not consumed or explicitly classified",
                    related_refs=[item["event_id"]],
                )
            )

    consumption_ledger = sorted(ledger.values(), key=lambda item: item["event_id"])
    input_digest = _sha256([event.digest_payload() for event in events])
    collection: dict[str, Any] = {
        "schema_version": COLLECTION_SCHEMA_VERSION,
        "projection_version": PROJECTION_VERSION,
        "cutoff_at": _iso(cutoff),
        "input_digest": input_digest,
        "collection_digest": "",
        "episodes": episodes,
        "consumption_ledger": consumption_ledger,
        "snapshot_catalog": snapshots,
    }
    validation = validate_episode_collection(collection, extra_findings=collection_findings)
    collection["validation"] = validation
    digest_payload = deepcopy(collection)
    digest_payload.pop("validation", None)
    digest_payload["collection_digest"] = ""
    collection["collection_digest"] = _sha256(digest_payload)
    return collection


def validate_episode(
    episode: Mapping[str, Any], *, snapshot_catalog: Iterable[Mapping[str, Any]] = ()
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    episode_id = str(episode.get("episode_id") or "")
    if episode.get("schema_version") != EPISODE_SCHEMA_VERSION:
        findings.append(_finding("blocker", "UNSUPPORTED_EPISODE_SCHEMA", "unsupported TradeEpisode schema version", related_refs=[episode_id]))
    if not episode_id:
        findings.append(_finding("blocker", "MISSING_EPISODE_ID", "episode_id is required"))
    scope = episode.get("scope") if isinstance(episode.get("scope"), Mapping) else {}
    if not scope.get("account_id") or not scope.get("instrument_id"):
        findings.append(_finding("blocker", "MISSING_PARTITION_IDENTITY", "account and instrument identity are required", related_refs=[episode_id]))
    try:
        opened_at = _aware_datetime(episode.get("opened_at"), field="opened_at")
        closed_at = _optional_aware_datetime(episode.get("closed_at"), field="closed_at")
        cutoff = _aware_datetime(episode.get("cutoff_at"), field="cutoff_at")
        if closed_at and closed_at < opened_at:
            findings.append(_finding("blocker", "INVALID_EPISODE_BOUNDARY", "closed_at cannot be before opened_at", related_refs=[episode_id]))
    except EpisodeProjectionError as exc:
        findings.append(_finding("blocker", "INVALID_EPISODE_TIMESTAMP", str(exc), related_refs=[episode_id]))
        opened_at = closed_at = cutoff = None

    event_refs = episode.get("event_refs") if isinstance(episode.get("event_refs"), list) else []
    event_ids = [str(item.get("event_id") or "") for item in event_refs if isinstance(item, Mapping)]
    if not event_refs:
        findings.append(_finding("blocker", "MISSING_EVENT_LINEAGE", "episode requires at least one event reference", related_refs=[episode_id]))
    if len(event_ids) != len(set(event_ids)):
        findings.append(_finding("blocker", "DUPLICATE_EVENT_CONSUMPTION", "an event appears more than once in one episode", related_refs=event_ids))
    previous_after: Decimal | None = None
    previous_key: str | None = None
    for item in event_refs:
        if not isinstance(item, Mapping):
            findings.append(_finding("blocker", "MALFORMED_EVENT_REFERENCE", "event reference must be an object", related_refs=[episode_id]))
            continue
        event_id = str(item.get("event_id") or "")
        try:
            _aware_datetime(item.get("effective_at"), field="event.effective_at")
            _aware_datetime(item.get("known_at"), field="event.known_at")
            before = _decimal(item.get("quantity_before"), field="quantity_before")
            after = _decimal(item.get("quantity_after"), field="quantity_after")
            signed = _decimal(item.get("signed_quantity"), field="signed_quantity")
            if after - before != signed:
                findings.append(_finding("blocker", "QUANTITY_PATH_MISMATCH", "quantity_after - quantity_before must equal signed_quantity", related_refs=[event_id]))
            if previous_after is not None and before != previous_after:
                findings.append(_finding("blocker", "QUANTITY_PATH_GAP", "adjacent quantity transitions do not connect", related_refs=[event_id]))
            previous_after = after
            ordering_key = canonical_json(item.get("ordering_key", []))
            if previous_key is not None and ordering_key < previous_key:
                findings.append(_finding("blocker", "NON_CANONICAL_EVENT_ORDER", "event references are not canonically ordered", related_refs=[event_id]))
            previous_key = ordering_key
            source_refs = item.get("source_refs") if isinstance(item.get("source_refs"), Mapping) else {}
            if not source_refs.get("source_id") or not source_refs.get("payload_sha256"):
                findings.append(_finding("blocker", "MISSING_SOURCE_LINEAGE", "event source lineage is incomplete", related_refs=[event_id]))
        except EpisodeProjectionError as exc:
            findings.append(_finding("blocker", "INVALID_EVENT_REFERENCE", str(exc), related_refs=[event_id]))
    status = str(episode.get("status") or "")
    ending = _decimal(episode.get("ending_quantity", "0"), field="ending_quantity")
    if status == "closed" and (episode.get("closed_at") in (None, "") or ending != 0):
        findings.append(_finding("blocker", "INVALID_CLOSED_STATUS", "closed episodes require closed_at and zero ending quantity", related_refs=[episode_id]))
    if status == "open" and (episode.get("closed_at") not in (None, "") or ending == 0):
        findings.append(_finding("blocker", "INVALID_OPEN_STATUS", "open episodes require no closed_at and non-zero ending quantity", related_refs=[episode_id]))
    if status not in {"open", "closed", "data_gap", "ambiguous"}:
        findings.append(_finding("blocker", "INVALID_EPISODE_STATUS", "unsupported episode status", related_refs=[episode_id]))
    if cutoff and event_refs:
        try:
            last_time = max(_aware_datetime(item.get("effective_at"), field="event.effective_at") for item in event_refs)
            if cutoff < last_time:
                findings.append(_finding("blocker", "CUTOFF_BEFORE_LAST_EVENT", "cutoff cannot precede the last consumed event", related_refs=[episode_id]))
        except EpisodeProjectionError:
            pass
    lineage = episode.get("lineage") if isinstance(episode.get("lineage"), Mapping) else {}
    for field in ("normalized_event_digest", "input_digest", "builder_version", "canonical_content_digest"):
        if not lineage.get(field):
            findings.append(_finding("blocker", "MISSING_EPISODE_LINEAGE", f"lineage.{field} is required", related_refs=[episode_id]))
    if lineage.get("canonical_content_digest"):
        expected_digest = _sha256(_episode_digest_payload(episode))
        if lineage.get("canonical_content_digest") != expected_digest:
            findings.append(_finding("blocker", "EPISODE_DIGEST_MISMATCH", "canonical episode content digest does not match", related_refs=[episode_id]))

    snapshot_index = {str(item.get("snapshot_id")): item for item in snapshot_catalog}
    events_by_id = {str(item.get("event_id")): item for item in event_refs}
    for link in episode.get("snapshot_links", []):
        snapshot_ref = link.get("snapshot_ref")
        if not snapshot_ref:
            continue
        snapshot = snapshot_index.get(str(snapshot_ref))
        if snapshot is None:
            findings.append(_finding("blocker", "SNAPSHOT_REFERENCE_NOT_FOUND", "snapshot reference does not resolve", related_refs=[str(snapshot_ref)]))
            continue
        if snapshot.get("account_id") != scope.get("account_id"):
            findings.append(_finding("blocker", "SNAPSHOT_ACCOUNT_MISMATCH", "snapshot account does not match episode", related_refs=[episode_id, str(snapshot_ref)]))
        event = events_by_id.get(str(link.get("event_ref") or ""))
        snapshot_cutoff = _optional_aware_datetime(snapshot.get("knowledge_cutoff_at"), field="snapshot.knowledge_cutoff_at")
        if event and snapshot_cutoff:
            event_time = _aware_datetime(event.get("effective_at"), field="event.effective_at")
            role = str(link.get("link_role") or "")
            if role.startswith("before") and snapshot_cutoff > event_time:
                findings.append(_finding("blocker", "FUTURE_SNAPSHOT_LINK", "state-before snapshot is later than the event", related_refs=[str(snapshot_ref), str(event.get("event_id"))]))
            if role.startswith("after"):
                if link.get("link_method") != "exact_event_cursor" or str(event.get("event_id")) not in snapshot.get("included_event_ids", []):
                    findings.append(_finding("blocker", "UNPROVEN_AFTER_SNAPSHOT", "state-after link must prove inclusion of the event", related_refs=[str(snapshot_ref), str(event.get("event_id"))]))
        instruments = {str(value).upper() for value in snapshot.get("instrument_ids", [])}
        if str(link.get("link_role", "")).startswith("after") and instruments:
            if str(scope.get("instrument_id", "")).upper() not in instruments and str(scope.get("symbol", "")).upper() not in instruments:
                findings.append(_finding("blocker", "SNAPSHOT_INSTRUMENT_MISMATCH", "state-after snapshot does not contain the episode instrument", related_refs=[episode_id, str(snapshot_ref)]))
    decision = episode.get("decision_linkage") if isinstance(episode.get("decision_linkage"), Mapping) else {}
    if decision.get("status") == "linked" and not decision.get("decision_refs"):
        findings.append(_finding("blocker", "MISSING_EXPLICIT_DECISION_REF", "linked status requires an explicit Decision reference", related_refs=[episode_id]))
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "episode_id": episode_id,
        "validation_status": _validation_status(findings),
        "findings": _sorted_findings(findings),
    }


def validate_episode_collection(
    collection: Mapping[str, Any], *, extra_findings: Iterable[Mapping[str, Any]] = ()
) -> dict[str, Any]:
    findings = list(extra_findings)
    if collection.get("schema_version") != COLLECTION_SCHEMA_VERSION:
        findings.append(_finding("blocker", "UNSUPPORTED_COLLECTION_SCHEMA", "unsupported episode collection schema"))
    if collection.get("collection_digest"):
        digest_payload = deepcopy(dict(collection))
        digest_payload.pop("validation", None)
        digest_payload["collection_digest"] = ""
        if collection.get("collection_digest") != _sha256(digest_payload):
            findings.append(
                _finding(
                    "blocker",
                    "COLLECTION_DIGEST_MISMATCH",
                    "canonical collection digest does not match the artifact content",
                )
            )
    snapshot_catalog = collection.get("snapshot_catalog", [])
    snapshot_ids = [
        str(item.get("snapshot_id") or "")
        for item in snapshot_catalog
        if isinstance(item, Mapping)
    ]
    duplicate_snapshot_ids = sorted(
        snapshot_id
        for snapshot_id, count in Counter(snapshot_ids).items()
        if snapshot_id and count > 1
    )
    if duplicate_snapshot_ids:
        findings.append(
            _finding(
                "blocker",
                "DUPLICATE_SNAPSHOT_IDENTITY",
                "snapshot_catalog contains duplicate snapshot IDs",
                related_refs=duplicate_snapshot_ids,
            )
        )
    episodes = collection.get("episodes", [])
    episode_ids = [
        str(item.get("episode_id") or "")
        for item in episodes
        if isinstance(item, Mapping)
    ]
    duplicate_episode_ids = sorted(
        episode_id
        for episode_id, count in Counter(episode_ids).items()
        if episode_id and count > 1
    )
    if duplicate_episode_ids:
        findings.append(
            _finding(
                "blocker",
                "DUPLICATE_EPISODE_IDENTITY",
                "episodes contains duplicate episode IDs",
                related_refs=duplicate_episode_ids,
            )
        )
    consumed: dict[str, list[str]] = defaultdict(list)
    for episode in episodes:
        result = validate_episode(episode, snapshot_catalog=snapshot_catalog)
        findings.extend(result["findings"])
        existing_validation = episode.get("validation", {})
        if isinstance(existing_validation, Mapping):
            findings.extend(existing_validation.get("findings", []))
        for event_ref in episode.get("event_refs", []):
            consumed[str(event_ref.get("event_id"))].append(str(episode.get("episode_id")))
    for event_id, episode_ids in consumed.items():
        if len(episode_ids) > 1:
            findings.append(
                _finding(
                    "blocker",
                    "DUPLICATE_EVENT_CONSUMPTION",
                    "one event was assigned to multiple episodes",
                    related_refs=[event_id, *episode_ids],
                )
            )
    ledger = collection.get("consumption_ledger", [])
    ledger_by_id = {str(item.get("event_id")): item for item in ledger}
    for event_id, episode_ids in consumed.items():
        item = ledger_by_id.get(event_id)
        if item is None or item.get("outcome") != "consumed" or item.get("episode_id") != episode_ids[0]:
            findings.append(_finding("blocker", "CONSUMPTION_LEDGER_MISMATCH", "episode assignment does not match the consumption ledger", related_refs=[event_id]))
    unassigned = sum(item.get("outcome") == "unassigned" for item in ledger)
    duplicate_consumption = sum(len(values) > 1 for values in consumed.values())
    findings = _sorted_findings(findings)
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "validation_status": _validation_status(findings),
        "findings": findings,
        "coverage": {
            "input_event_identities": len(ledger),
            "consumed_once": sum(item.get("outcome") == "consumed" for item in ledger),
            "classified_non_position": sum(item.get("outcome") == "non_position_changing" for item in ledger),
            "rejected_or_blocked": sum(
                str(item.get("outcome", "")).startswith(("rejected", "blocked")) for item in ledger
            ),
            "excluded_by_cutoff": sum(str(item.get("outcome", "")).startswith("excluded") for item in ledger),
            "unassigned": unassigned,
            "duplicate_consumption": duplicate_consumption,
        },
        "temporal_checks": {
            "future_snapshot_links": sum(item.get("code") == "FUTURE_SNAPSHOT_LINK" for item in findings),
            "invalid_cutoffs": sum(item.get("code") == "CUTOFF_BEFORE_LAST_EVENT" for item in findings),
            "naive_timestamps": sum(item.get("code") == "INVALID_EVENT" and "timezone" in item.get("message", "") for item in findings),
        },
    }


def query_episode_collection(
    collection: Mapping[str, Any],
    *,
    episode_id: str | None = None,
    account: str | None = None,
    instrument: str | None = None,
    status: str | None = None,
    interval_start: str | None = None,
    interval_end: str | None = None,
) -> list[dict[str, Any]]:
    if collection.get("schema_version") != COLLECTION_SCHEMA_VERSION:
        raise EpisodeProjectionError("unsupported episode collection schema")
    start = _optional_aware_datetime(interval_start, field="interval_start")
    end = _optional_aware_datetime(interval_end, field="interval_end")
    if start and end and start > end:
        raise EpisodeProjectionError("interval_start cannot be later than interval_end")
    if status and status not in {"open", "closed", "data_gap", "ambiguous"}:
        raise EpisodeProjectionError(f"unsupported status filter: {status}")
    result: list[dict[str, Any]] = []
    for episode in collection.get("episodes", []):
        scope = episode.get("scope", {})
        if episode_id and episode.get("episode_id") != episode_id:
            continue
        if account and scope.get("account_id") != account:
            continue
        if instrument and instrument.upper() not in {str(scope.get("instrument_id", "")).upper(), str(scope.get("symbol", "")).upper()}:
            continue
        if status and episode.get("status") != status:
            continue
        opened = _aware_datetime(episode.get("opened_at"), field="opened_at")
        ended = _aware_datetime(episode.get("closed_at") or episode.get("cutoff_at"), field="episode_end")
        if start and ended < start:
            continue
        if end and opened > end:
            continue
        result.append(deepcopy(dict(episode)))
    result.sort(key=lambda item: (item["scope"]["account_id"], item["scope"]["instrument_id"], item["opened_at"], item["episode_id"]))
    return result


def save_episode_collection(path: str | Path, collection: Mapping[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(collection, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def load_episode_collection(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise EpisodeProjectionError("episode artifact must contain a JSON object")
    return payload
