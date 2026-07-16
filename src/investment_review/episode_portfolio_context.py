"""Deterministic P2E-3 TradeEpisode portfolio-context artifacts.

This module consumes P2C episode artifacts and P2B snapshot tables without
writing either source database.  It deliberately degrades unverifiable
intraday boundaries to ``missing`` or ``ambiguous`` instead of guessing.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator, FormatChecker

from .artifact_io import (
    ArtifactIOError,
    atomic_write_bytes,
    canonical_json_bytes,
    load_json_object,
    pretty_json_bytes,
)
from .episodes import COLLECTION_SCHEMA_VERSION, validate_episode_collection
from .models import ModelValidationError
from .portfolio_context import (
    PORTFOLIO_METRIC_METHOD_REGISTRY,
    PORTFOLIO_METRIC_REGISTRY_VERSION,
    PortfolioSnapshot,
    calculate_portfolio_evidence_metrics,
    portfolio_metric_method_ref,
)


SCHEMA_VERSION = "p2e3.trade_episode_portfolio_context.v1"
VALIDATION_SCHEMA_VERSION = "p2e3.trade_episode_portfolio_context.validation.v1"
METRIC_REGISTRY_VERSION = PORTFOLIO_METRIC_REGISTRY_VERSION
_CONTENT_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DECIMAL_RE = re.compile(
    r"^(?:0|-?(?:[1-9][0-9]*(?:\.[0-9]*[1-9])?|0\.[0-9]*[1-9]))$"
)
_METRIC_KEY_RE = re.compile(r"^[a-z][a-z0-9_.-]*$")
_BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")
_MARKET_CLOSE = time(15, 0)
_CONTRACT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "contracts"
    / "P2E_3_TRADE_EPISODE_PORTFOLIO_CONTEXT_DRAFT.schema.json"
)
_ALLOWED_SOURCE_BLOCKERS = {
    "DECISION_LINK_AMBIGUOUS",
    "DECISION_LINK_INVALID",
}
_PARTIAL_METRIC_WARNING_CODES = {
    "MISSING_PRICE",
    "MISSING_FX",
    "ZERO_VALUATION",
    "PARTIAL_VALUATION_COVERAGE",
    "UNCLASSIFIED_INDUSTRY",
    "STALE_POSITION",
    "NAV_RECONCILIATION_GAP",
    "TARGET_POSITION_UNPRICED",
    "PORTFOLIO_CURSOR_SCOPE_LIMITED",
}


class EpisodePortfolioContextError(ValueError):
    """Raised when P2E-3 input or output violates the public contract."""


def _parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise EpisodePortfolioContextError(f"{field} must be a timezone-aware timestamp")
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EpisodePortfolioContextError(f"invalid {field}: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EpisodePortfolioContextError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    rendered = value.astimezone(timezone.utc).isoformat(timespec="seconds")
    return rendered.replace("+00:00", "Z")


def _business_date(value: datetime) -> date:
    return value.astimezone(_BUSINESS_TIMEZONE).date()


def _market_close_utc(value: date) -> datetime:
    return datetime.combine(value, _MARKET_CLOSE, tzinfo=_BUSINESS_TIMEZONE).astimezone(
        timezone.utc
    )


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise EpisodePortfolioContextError(f"{field} must be a Decimal string")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise EpisodePortfolioContextError(f"invalid Decimal in {field}") from exc
    if not parsed.is_finite():
        raise EpisodePortfolioContextError(f"{field} must be finite")
    return parsed


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _content_id(payload: Mapping[str, Any]) -> str:
    material = deepcopy(dict(payload))
    material.pop("content_id", None)
    return "sha256:" + hashlib.sha256(canonical_json_bytes(material)).hexdigest()


def _value_content_id(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _canonical_token(value: object) -> bytes:
    try:
        return canonical_json_bytes(value)
    except ArtifactIOError:
        return b""


def _stable_id(prefix: str, material: object) -> str:
    digest = hashlib.sha256(canonical_json_bytes(material)).hexdigest()
    return f"{prefix}:{digest[:32]}"


def _source_ref(
    *,
    source_type: str,
    source_id: str,
    effective_at: str | None = None,
    knowledge_at: str | None = None,
    revision: str | int | None = None,
    content_id: str | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source_type": source_type,
        "source_id": source_id,
        "effective_at": effective_at,
        "knowledge_at": knowledge_at,
        "revision": revision,
    }
    if content_id is not None:
        result["content_id"] = content_id
    if path is not None:
        result["path"] = path
    return result


def _warning(
    code: str,
    message: str,
    *,
    severity: str = "warning",
    source_refs: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "source_refs": [dict(item) for item in source_refs],
    }


def _sorted_warnings(values: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[bytes, dict[str, Any]] = {}
    for value in values:
        item = dict(value)
        unique[canonical_json_bytes(item)] = item
    return [unique[key] for key in sorted(unique)]


class _P2BSnapshotReader:
    """Strict read-only reader for the current P2B snapshot schema."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise EpisodePortfolioContextError(f"portfolio database not found: {self.path}")
        uri = self.path.resolve().as_uri() + "?mode=ro"
        self.connection = sqlite3.connect(uri, uri=True)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA query_only = ON")
        tables = {
            str(row[0])
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        required = {"portfolio_snapshots", "position_snapshots"}
        if not required.issubset(tables):
            self.close()
            raise EpisodePortfolioContextError(
                f"portfolio database lacks P2B tables: {sorted(required - tables)}"
            )
        columns = {
            str(row[1])
            for row in self.connection.execute("PRAGMA table_info(portfolio_snapshots)")
        }
        if not {"as_of_date", "knowledge_cutoff_at", "market_value"}.issubset(columns):
            self.close()
            raise EpisodePortfolioContextError("unsupported portfolio snapshot schema")
        self.rows = [
            dict(row)
            for row in self.connection.execute(
                """
                SELECT * FROM portfolio_snapshots
                ORDER BY account_id, as_of_date, knowledge_cutoff_at,
                         revision, snapshot_id
                """
            )
        ]
        self.by_id = {str(row["snapshot_id"]): row for row in self.rows}

    def close(self) -> None:
        if getattr(self, "connection", None) is not None:
            self.connection.close()
            self.connection = None

    def __enter__(self) -> "_P2BSnapshotReader":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def positions(self, snapshot_id: str) -> list[dict[str, Any]]:
        rows = [
            dict(row)
            for row in self.connection.execute(
                "SELECT * FROM position_snapshots WHERE snapshot_id = ? ORDER BY ts_code",
                (snapshot_id,),
            )
        ]
        parent = self.by_id.get(snapshot_id)
        if parent is not None:
            expected_engine = str(parent.get("engine_version") or "")
            expected_state = str(parent.get("source_state_hash") or "")
            for row in rows:
                if (
                    str(row.get("engine_version") or "") != expected_engine
                    or str(row.get("source_state_hash") or "") != expected_state
                ):
                    raise EpisodePortfolioContextError(
                        f"position snapshot lineage drift for {snapshot_id}"
                    )
        return rows

    def visible(
        self,
        row: Mapping[str, Any],
        *,
        anchor_at: datetime,
        knowledge_cutoff: datetime,
        side: str,
    ) -> bool:
        raw_known = row.get("knowledge_cutoff_at")
        if raw_known in (None, ""):
            return False
        try:
            known = _parse_timestamp(raw_known, "snapshot.knowledge_cutoff_at")
            as_of_date = date.fromisoformat(str(row.get("as_of_date")))
        except (EpisodePortfolioContextError, ValueError):
            return False
        if known > knowledge_cutoff or as_of_date > _business_date(anchor_at):
            return False
        return side != "pre" or known <= anchor_at

    @staticmethod
    def assert_catalog_match(
        row: Mapping[str, Any], catalog_ref: Mapping[str, Any]
    ) -> None:
        snapshot_id = str(row.get("snapshot_id") or "")
        scalar_fields = (
            "snapshot_id",
            "account_id",
            "as_of_date",
            "revision",
            "engine_version",
            "source_state_hash",
        )
        mismatches = [
            field
            for field in scalar_fields
            if str(row.get(field) or "") != str(catalog_ref.get(field) or "")
        ]
        try:
            row_known = _iso(
                _parse_timestamp(row.get("knowledge_cutoff_at"), "snapshot.knowledge_cutoff_at")
            )
            catalog_known = _iso(
                _parse_timestamp(
                    catalog_ref.get("knowledge_cutoff_at"),
                    "snapshot_catalog.knowledge_cutoff_at",
                )
            )
        except EpisodePortfolioContextError:
            mismatches.append("knowledge_cutoff_at")
        else:
            if row_known != catalog_known:
                mismatches.append("knowledge_cutoff_at")
        if mismatches:
            raise EpisodePortfolioContextError(
                f"snapshot catalog/database drift for {snapshot_id}: "
                + ", ".join(sorted(set(mismatches)))
            )
        state_hash = str(row.get("source_state_hash") or "")
        if _SHA256_RE.fullmatch(state_hash) is None:
            raise EpisodePortfolioContextError(
                f"snapshot {snapshot_id} has invalid source_state_hash"
            )

    def same_rank_is_ambiguous(
        self,
        *,
        selected: Mapping[str, Any],
        allowed_ids: set[str],
    ) -> bool:
        candidates = [
            row
            for row in self.rows
            if str(row.get("account_id")) == str(selected.get("account_id"))
            and str(row.get("snapshot_id")) in allowed_ids
            and str(row.get("as_of_date")) == str(selected.get("as_of_date"))
            and int(row.get("revision") or 0) == int(selected.get("revision") or 0)
            and _iso(
                _parse_timestamp(
                    row.get("knowledge_cutoff_at"), "snapshot.knowledge_cutoff_at"
                )
            )
            == _iso(
                _parse_timestamp(
                    selected.get("knowledge_cutoff_at"),
                    "snapshot.knowledge_cutoff_at",
                )
            )
        ]
        distinct_states = {str(row.get("source_state_hash") or "") for row in candidates}
        return len(candidates) > 1 and len(distinct_states) > 1


def _price_source_ref(
    position: Mapping[str, Any], *, price_lineage: Mapping[str, Any]
) -> dict[str, Any]:
    effective_at: str | None = None
    if position.get("price_date"):
        try:
            effective_at = _iso(_market_close_utc(date.fromisoformat(str(position["price_date"]))))
        except ValueError:
            effective_at = None
    knowledge_at: str | None = None
    if price_lineage.get("known_at"):
        try:
            knowledge_at = _iso(
                _parse_timestamp(price_lineage["known_at"], "position.price.known_at")
            )
        except EpisodePortfolioContextError:
            knowledge_at = None
    return _source_ref(
        source_type="price",
        source_id=str(
            price_lineage.get("source")
            or position.get("price_source")
            or position.get("ts_code")
            or "unknown"
        ),
        effective_at=effective_at,
        knowledge_at=knowledge_at,
        revision=None,
    )


def _snapshot_source_ref(
    row: Mapping[str, Any],
    catalog_ref: Mapping[str, Any],
    *,
    effective_at: datetime,
) -> dict[str, Any]:
    state_hash = str(row.get("source_state_hash") or "")
    return _source_ref(
        source_type="portfolio_snapshot",
        source_id=str(row.get("snapshot_id") or ""),
        effective_at=_iso(effective_at),
        knowledge_at=_iso(
            _parse_timestamp(row.get("knowledge_cutoff_at"), "snapshot.knowledge_cutoff_at")
        ),
        revision=int(row.get("revision") or 0),
        content_id=f"sha256:{state_hash}",
        path=str(catalog_ref.get("source_path") or "") or None,
    )


def _snapshot_model(
    reader: _P2BSnapshotReader,
    row: Mapping[str, Any],
    *,
    anchor_at: datetime,
    knowledge_cutoff: datetime,
    catalog_ref: Mapping[str, Any],
    snapshot_ref: Mapping[str, Any],
) -> tuple[PortfolioSnapshot | None, tuple[str, ...], list[dict[str, Any]]]:
    """Adapt one P2B row to the public P2E-2 snapshot model."""

    snapshot_id = str(row["snapshot_id"])
    known = _parse_timestamp(row["knowledge_cutoff_at"], "snapshot.knowledge_cutoff_at")
    observed = min(anchor_at, known)
    warnings: list[dict[str, Any]] = []
    if row.get("cash_balance") in (None, "") or row.get("cash_status") != "available":
        warnings.append(
            _warning(
                "CASH_UNAVAILABLE",
                "Snapshot cash is unavailable; NAV-based metrics cannot be constructed.",
                source_refs=[snapshot_ref],
            )
        )
        return None, (), warnings

    raw_positions = reader.positions(snapshot_id)
    catalog_instruments = {
        str(item).upper() for item in catalog_ref.get("instrument_ids", [])
    }
    database_instruments = {
        str(item.get("ts_code") or "").upper() for item in raw_positions
    }
    if catalog_instruments != database_instruments:
        raise EpisodePortfolioContextError(
            f"snapshot catalog/database instrument drift for {snapshot_id}"
        )
    if int(row.get("position_count") or 0) != len(raw_positions):
        warnings.append(
            _warning(
                "SNAPSHOT_RECONCILIATION_FAILED",
                "P2B position_count does not reconcile to position rows.",
                severity="error",
                source_refs=[snapshot_ref],
            )
        )
        return None, (), warnings
    supported_valuation_statuses = {"priced", "stale", "unpriced"}
    unknown_statuses = sorted(
        {
            str(item.get("valuation_status") or "")
            for item in raw_positions
            if str(item.get("valuation_status") or "")
            not in supported_valuation_statuses
        }
    )
    if unknown_statuses:
        warnings.append(
            _warning(
                "SNAPSHOT_RECONCILIATION_FAILED",
                "P2B position rows contain unsupported valuation_status values: "
                + ", ".join(unknown_statuses),
                severity="error",
                source_refs=[snapshot_ref],
            )
        )
        return None, (), warnings
    raw_unpriced = sum(
        str(item.get("valuation_status") or "") == "unpriced" for item in raw_positions
    )
    raw_priced = sum(
        str(item.get("valuation_status") or "") in {"priced", "stale"}
        for item in raw_positions
    )
    if (
        raw_unpriced != int(row.get("unpriced_position_count") or 0)
        or raw_priced != int(row.get("priced_position_count") or 0)
        or bool(row.get("valuation_complete"))
        != (raw_unpriced == 0 and raw_priced == len(raw_positions))
    ):
        warnings.append(
            _warning(
                "SNAPSHOT_RECONCILIATION_FAILED",
                "P2B unpriced_position_count does not reconcile to position rows.",
                severity="error",
                source_refs=[snapshot_ref],
            )
        )
        return None, (), warnings
    try:
        created_from = json.loads(str(row.get("created_from_json") or "{}"))
    except json.JSONDecodeError:
        created_from = {}
    if isinstance(created_from, Mapping) and created_from.get("source_document_sha256"):
        if created_from.get("source_document_sha256") != row.get("source_state_hash"):
            warnings.append(
                _warning(
                    "SNAPSHOT_RECONCILIATION_FAILED",
                    "P2B created_from lineage does not match source_state_hash.",
                    severity="error",
                    source_refs=[snapshot_ref],
                )
            )
            return None, (), warnings

    positions: list[dict[str, Any]] = []
    stale_keys: list[str] = []
    safe_position_values: list[Decimal] = []
    unsafe_valuation = False
    for position in raw_positions:
        symbol = str(position.get("ts_code") or "").upper()
        price = position.get("price")
        market_value = position.get("market_value")
        valuation_status = str(position.get("valuation_status") or "unpriced")
        price_date: date | None = None
        try:
            lineage = json.loads(str(position.get("lineage_json") or "{}"))
        except json.JSONDecodeError:
            lineage = {}
        if not isinstance(lineage, Mapping):
            lineage = {}
        price_lineage = (
            lineage.get("price") if isinstance(lineage.get("price"), Mapping) else {}
        )
        price_known_at: datetime | None = None
        if price_lineage.get("known_at"):
            try:
                price_known_at = _parse_timestamp(
                    price_lineage["known_at"], "position.price.known_at"
                )
            except EpisodePortfolioContextError:
                price_known_at = None
        if position.get("price_date"):
            try:
                price_date = date.fromisoformat(str(position["price_date"]))
            except ValueError:
                price_date = None
        price_effective_at = _market_close_utc(price_date) if price_date is not None else None
        price_lineage_matches = (
            price_date is not None
            and str(price_lineage.get("trade_date") or "") == price_date.isoformat()
            and str(price_lineage.get("source") or "")
            == str(position.get("price_source") or "")
        )
        if valuation_status != "unpriced" and (
            price in (None, "")
            or market_value in (None, "")
            or price_effective_at is None
            or price_effective_at > anchor_at
            or price_known_at is None
            or price_known_at > knowledge_cutoff
            or price_known_at > known
            or not price_lineage_matches
        ):
            warnings.append(
                _warning(
                    "PRICE_NOT_VISIBLE",
                    "A price lacking complete dual-time lineage at the anchor was withheld.",
                    source_refs=[
                        _price_source_ref(position, price_lineage=price_lineage)
                    ],
                )
            )
            price = None
            market_value = None
            valuation_status = "unpriced"
            unsafe_valuation = True
        elif valuation_status == "unpriced":
            price = None
            market_value = None
            unsafe_valuation = True
            warnings.append(
                _warning(
                    "UNPRICED",
                    "A position lacks a point-in-time-safe reviewed valuation.",
                    source_refs=[
                        _price_source_ref(position, price_lineage=price_lineage)
                    ],
                )
            )
        elif valuation_status == "stale":
            stale_keys.append(f"{symbol}|")
            warnings.append(
                _warning(
                    "PRICE_STALE",
                    "A reviewed position price is stale at this anchor.",
                    source_refs=[
                        _price_source_ref(position, price_lineage=price_lineage)
                    ],
                )
            )
        industry_lineage = (
            lineage.get("industry")
            if isinstance(lineage.get("industry"), Mapping)
            else {}
        )
        industry = None
        if industry_lineage.get("point_in_time") is True:
            candidate = str(position.get("industry_name") or "").strip() or None
            lineage_name = str(industry_lineage.get("name") or "").strip() or None
            row_source = str(position.get("industry_source") or "").strip() or None
            lineage_source = str(industry_lineage.get("source") or "").strip() or None
            updated_at = industry_lineage.get("updated_at")
            visible = False
            if (
                updated_at
                and candidate is not None
                and candidate == lineage_name
                and row_source is not None
                and row_source == lineage_source
            ):
                try:
                    visible = _parse_timestamp(
                        updated_at, "position.industry.updated_at"
                    ) <= min(anchor_at, knowledge_cutoff, known)
                except EpisodePortfolioContextError:
                    visible = False
            if visible:
                industry = candidate
        if industry is None:
            warnings.append(
                _warning(
                    "MISSING_CLASSIFICATION",
                    "No point-in-time industry classification is available.",
                    source_refs=[snapshot_ref],
                )
            )
        if market_value not in (None, ""):
            safe_position_values.append(_decimal(market_value, "position.market_value"))
        positions.append(
            {
                "symbol": symbol,
                "quantity": str(position.get("quantity") or "0"),
                "cost_basis": position.get("average_cost"),
                "price": price,
                "market_value": market_value,
                "currency": str(row.get("currency") or "CNY"),
                "industry": industry,
                "source_id": "p2b_portfolio_snapshot",
                "observed_at": _iso(observed),
                "known_at": _iso(known),
            }
        )
    if unsafe_valuation or not bool(row.get("valuation_complete")):
        warnings.append(
            _warning(
                "PARTIAL_NAV_UNAVAILABLE",
                "NAV-dependent metrics are unavailable because valuation coverage is incomplete.",
                source_refs=[snapshot_ref],
            )
        )
        return None, tuple(sorted(stale_keys)), warnings

    position_market_value = sum(safe_position_values, Decimal("0"))
    summary_market_value = _decimal(row.get("market_value"), "snapshot.market_value")
    if position_market_value != summary_market_value:
        warnings.append(
            _warning(
                "SNAPSHOT_RECONCILIATION_FAILED",
                "P2B market_value does not reconcile to position rows.",
                severity="error",
                source_refs=[snapshot_ref],
            )
        )
        return None, tuple(sorted(stale_keys)), warnings

    cash = _decimal(row["cash_balance"], "snapshot.cash_balance")
    nav = cash + summary_market_value
    warnings.append(
        _warning(
            "P2B_NAV_DERIVED",
            "NAV was derived exactly from reviewed P2B cash and complete market value.",
            severity="info",
            source_refs=[snapshot_ref],
        )
    )
    try:
        snapshot = PortfolioSnapshot.from_dict(
            {
                "snapshot_id": snapshot_id,
                "source_id": "p2b_portfolio_snapshot",
                "source_path": str(catalog_ref.get("source_path") or f"portfolio_snapshots/{snapshot_id}"),
                "source_record_id": str(row.get("source_state_hash") or snapshot_id),
                "account": str(row.get("account_id") or ""),
                "observed_at": _iso(observed),
                "known_at": _iso(known),
                "cash": _decimal_text(cash),
                "total_assets": _decimal_text(nav),
                "net_asset_value": _decimal_text(nav),
                "financing": "0",
                "base_currency": str(row.get("currency") or "CNY"),
                "positions": positions,
            },
            default_source_id="p2b_portfolio_snapshot",
            timezone="UTC",
        )
    except ModelValidationError as exc:
        warnings.append(
            _warning(
                "SNAPSHOT_INVALID",
                str(exc),
                severity="error",
                source_refs=[snapshot_ref],
            )
        )
        return None, tuple(stale_keys), warnings
    return snapshot, tuple(sorted(stale_keys)), warnings


def _metric_key(metric_name: str) -> str:
    if _METRIC_KEY_RE.fullmatch(metric_name):
        return metric_name
    if metric_name.startswith("industry_weight::"):
        suffix = metric_name.split("::", 1)[1]
        if suffix == "UNKNOWN":
            return "industry_weight.unknown"
        digest = hashlib.sha256(suffix.encode("utf-8")).hexdigest()[:12]
        return f"industry_weight.{digest}"
    candidate = re.sub(r"[^a-z0-9_.-]+", "-", metric_name.lower()).strip("-.")
    if candidate and _METRIC_KEY_RE.fullmatch(candidate):
        return candidate
    return "metric." + hashlib.sha256(metric_name.encode("utf-8")).hexdigest()[:12]


def _metric_payloads(
    snapshot: PortfolioSnapshot,
    *,
    target_symbol: str,
    stale_position_keys: Iterable[str],
    revision: int,
    snapshot_source_ref: Mapping[str, Any],
    force_partial: bool = False,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for metric in calculate_portfolio_evidence_metrics(
        snapshot,
        target_symbol=target_symbol,
        stale_position_keys=stale_position_keys,
    ):
        warning_codes = sorted({item.code for item in metric.warnings})
        if metric.status == "unavailable":
            availability = (
                "invalid" if "NON_POSITIVE_NAV" in warning_codes else "missing"
            )
        elif _PARTIAL_METRIC_WARNING_CODES.intersection(warning_codes):
            availability = "partial"
        else:
            availability = "available"
        if force_partial and availability == "available":
            availability = "partial"
            warning_codes = sorted(
                {*warning_codes, "PORTFOLIO_CURSOR_SCOPE_LIMITED"}
            )
        source_refs = [dict(snapshot_source_ref) for _ in metric.source_refs]
        result[_metric_key(metric.metric_name)] = {
            "availability": availability,
            "value": metric.value,
            "unit": metric.unit,
            "method": portfolio_metric_method_ref(metric.metric_name),
            "source_refs": source_refs,
            "warning_codes": warning_codes,
        }
    return {key: result[key] for key in sorted(result)}


def _event_source_ref(event: Mapping[str, Any]) -> dict[str, Any]:
    sources = event.get("source_refs") if isinstance(event.get("source_refs"), Mapping) else {}
    return _source_ref(
        source_type="trade_event",
        source_id=str(event.get("event_id") or sources.get("source_record_id") or "unknown"),
        effective_at=_iso(_parse_timestamp(event.get("effective_at"), "event.effective_at")),
        knowledge_at=_iso(_parse_timestamp(event.get("known_at"), "event.known_at")),
        revision=None,
    )


def _ambiguous_event_ids(events: Sequence[Mapping[str, Any]]) -> set[str]:
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for event in events:
        effective = _iso(_parse_timestamp(event.get("effective_at"), "event.effective_at"))
        groups.setdefault(effective, []).append(event)
    ambiguous: set[str] = set()
    for group in groups.values():
        if len(group) < 2:
            continue
        if any(
            isinstance(item.get("ordering_key"), list)
            and len(item["ordering_key"]) >= 2
            and item["ordering_key"][1] == 2
            for item in group
        ):
            ambiguous.update(str(item.get("event_id")) for item in group)
    return ambiguous


def _event_order(item: Mapping[str, Any]) -> tuple[datetime, int, str, str]:
    ordering = item.get("ordering_key")
    values = list(ordering) if isinstance(ordering, list) else []
    occurred = _parse_timestamp(
        values[0] if values else item.get("effective_at"),
        "event.ordering_key",
    )
    try:
        rank = int(values[1]) if len(values) > 1 else 99
    except (TypeError, ValueError):
        rank = 99
    return (
        occurred,
        rank,
        str(values[2]) if len(values) > 2 else "",
        str(values[3]) if len(values) > 3 else str(item.get("event_id") or ""),
    )


def _anchor_kind(episode: Mapping[str, Any], event_id: str) -> str:
    if event_id == str(episode.get("opening_event_ref") or ""):
        return "episode_open"
    if event_id == str(episode.get("closing_event_ref") or ""):
        return "episode_close"
    return "position_change"


def _decision_link_status(episode: Mapping[str, Any]) -> str:
    status = str((episode.get("decision_linkage") or {}).get("status") or "missing")
    if status not in {"linked", "unlinked", "ambiguous", "invalid", "missing"}:
        return "invalid"
    return status


def _canonical_ordering_key(event: Mapping[str, Any]) -> list[Any]:
    occurred_at, rank, source_sequence, stable_event_id = _event_order(event)
    return [_iso(occurred_at), rank, source_sequence, stable_event_id]


def _material_event_manifest_entry(
    episode: Mapping[str, Any], event: Mapping[str, Any]
) -> dict[str, Any]:
    event_id = str(event.get("event_id") or "")
    event_at = _iso(_parse_timestamp(event.get("effective_at"), "event.effective_at"))
    target_symbol = str((episode.get("scope") or {}).get("symbol") or "").upper()
    lineage = episode.get("lineage") if isinstance(episode.get("lineage"), Mapping) else {}
    episode_digest = str(lineage.get("canonical_content_digest") or "")
    return {
        "episode_id": str(episode.get("episode_id") or ""),
        "episode_content_id": f"sha256:{episode_digest}",
        "event_id": event_id,
        "event_content_id": _content_id(event),
        "anchor_kind": _anchor_kind(episode, event_id),
        "event_at": event_at,
        "known_at": _iso(
            _parse_timestamp(event.get("known_at"), "event.known_at")
        ),
        "ordering_key": _canonical_ordering_key(event),
        "target_symbol": target_symbol
        or str((episode.get("scope") or {}).get("instrument_id") or "UNKNOWN"),
        "decision_link_status": _decision_link_status(episode),
    }


def _context_sort_key(context: Mapping[str, Any]) -> tuple[Any, ...]:
    anchor = context.get("anchor") if isinstance(context.get("anchor"), Mapping) else {}
    return (
        str(context.get("episode_id") or ""),
        str(anchor.get("event_at") or ""),
        _canonical_token(anchor.get("ordering_key") or []),
        0 if anchor.get("side") == "pre" else 1,
        str(context.get("context_id") or ""),
    )


def _link_role(kind: str, side: str) -> str:
    suffix = {
        "episode_open": "open",
        "episode_close": "close",
        "position_change": "change",
    }[kind]
    return f"before_{suffix}" if side == "pre" else f"after_{suffix}"


def _find_link(
    episode: Mapping[str, Any], *, event_id: str, role: str
) -> Mapping[str, Any] | None:
    for link in episode.get("snapshot_links", []):
        if not isinstance(link, Mapping):
            continue
        if str(link.get("event_ref") or "") == event_id and link.get("link_role") == role:
            return link
    return None


def _select_snapshot_row(
    reader: _P2BSnapshotReader,
    *,
    episode: Mapping[str, Any],
    event: Mapping[str, Any],
    side: str,
    kind: str,
    knowledge_cutoff: datetime,
    catalog: Mapping[str, Mapping[str, Any]],
    account_events: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any] | None, str, list[dict[str, Any]], bool]:
    event_id = str(event["event_id"])
    event_at = _parse_timestamp(event.get("effective_at"), "event.effective_at")
    role = _link_role(kind, side)
    link = _find_link(episode, event_id=event_id, role=role)
    warnings: list[dict[str, Any]] = []
    required_method = "latest_at_or_before" if side == "pre" else "exact_event_cursor"
    if (
        link is None
        or link.get("link_method") != required_method
        or not link.get("snapshot_ref")
    ):
        warnings.append(
            _warning(
                "SNAPSHOT_MISSING",
                "P2C did not provide the required boundary link.",
                source_refs=[_event_source_ref(event)],
            )
        )
        return None, "missing", warnings, False

    snapshot_id = str(link["snapshot_ref"])
    catalog_ref = catalog.get(snapshot_id)
    preferred = reader.by_id.get(snapshot_id)
    if catalog_ref is None or preferred is None:
        warnings.append(
            _warning(
                "SNAPSHOT_MISSING",
                "The linked snapshot does not resolve in both catalog and database.",
                source_refs=[_event_source_ref(event)],
            )
        )
        return None, "missing", warnings, False
    reader.assert_catalog_match(preferred, catalog_ref)
    if not reader.visible(
        preferred,
        anchor_at=event_at,
        knowledge_cutoff=knowledge_cutoff,
        side=side,
    ):
        warnings.append(
            _warning(
                "SNAPSHOT_NOT_VISIBLE",
                "The linked snapshot is outside the dual-time boundary.",
                source_refs=[_event_source_ref(event)],
            )
        )
        return None, "missing", warnings, False
    if reader.same_rank_is_ambiguous(
        selected=preferred, allowed_ids=set(catalog)
    ):
        warnings.append(
            _warning(
                "AMBIGUOUS_SNAPSHOT_REVISION",
                "Multiple catalog snapshots share one explicit rank but differ in state.",
                source_refs=[_event_source_ref(event)],
            )
        )
        return None, "ambiguous", warnings, False

    included = {str(item) for item in catalog_ref.get("included_event_ids", [])}
    current_order = _event_order(event)
    known = _parse_timestamp(
        preferred.get("knowledge_cutoff_at"), "snapshot.knowledge_cutoff_at"
    )
    event_index = {
        str(item.get("event_id") or ""): item for item in account_events
    }
    later_ids = {
        str(item.get("event_id") or "")
        for item in account_events
        if _event_order(item) > current_order
    }
    future_known_ids = {
        event_identity
        for event_identity in included
        if event_identity in event_index
        and _parse_timestamp(
            event_index[event_identity].get("known_at"), "event.known_at"
        )
        > min(known, knowledge_cutoff)
    }
    unknown_included_ids = included.difference(event_index)
    if included.intersection(later_ids) or future_known_ids or unknown_included_ids or (
        side == "pre" and event_id in included
    ) or (
        side == "post" and event_id not in included
    ):
        warnings.append(
            _warning(
                "EVENT_CURSOR_AMBIGUOUS",
                "The linked snapshot does not prove the requested event cursor.",
                source_refs=[_event_source_ref(event)],
            )
        )
        return None, "ambiguous", warnings, False

    snapshot_day = date.fromisoformat(str(preferred.get("as_of_date")))
    event_day = _business_date(event_at)
    complete_account_cursor = (
        catalog_ref.get("cursor_scope") == "account"
        and catalog_ref.get("included_event_set_complete") is True
    )
    boundary_limited = snapshot_day == event_day and not complete_account_cursor
    if boundary_limited:
        warnings.append(
            _warning(
                "PORTFOLIO_CURSOR_SCOPE_LIMITED",
                "P2C proves a partition cursor, not a complete account-wide intraday cursor; metrics are partial.",
                source_refs=[_event_source_ref(event)],
            )
        )
    elif side == "pre" and snapshot_day < event_day:
        warnings.append(
            _warning(
                "SNAPSHOT_FALLBACK_USED",
                "The linked pre-event state is from an earlier business day.",
                source_refs=[_event_source_ref(event)],
            )
        )
    status = (
        "exact"
        if side == "post"
        and complete_account_cursor
        and snapshot_day == event_day
        else "replayed"
    )
    return preferred, status, warnings, boundary_limited


def _build_context(
    reader: _P2BSnapshotReader,
    *,
    episode: Mapping[str, Any],
    event: Mapping[str, Any],
    side: str,
    knowledge_cutoff: datetime,
    catalog: Mapping[str, Mapping[str, Any]],
    account_events: Sequence[Mapping[str, Any]],
    ambiguous: bool,
) -> dict[str, Any]:
    episode_id = str(episode["episode_id"])
    event_id = str(event["event_id"])
    event_at = _parse_timestamp(event.get("effective_at"), "event.effective_at")
    kind = _anchor_kind(episode, event_id)
    warnings: list[dict[str, Any]] = []
    row: Mapping[str, Any] | None = None
    force_partial = False
    snapshot_status = "ambiguous" if ambiguous else "missing"
    if ambiguous:
        warnings.append(
            _warning(
                "AMBIGUOUS_EVENT_ORDER",
                "Same-timestamp events lack a business sequence; pre/post state is ambiguous.",
                source_refs=[_event_source_ref(event)],
            )
        )
    else:
        row, snapshot_status, selection_warnings, force_partial = _select_snapshot_row(
            reader,
            episode=episode,
            event=event,
            side=side,
            kind=kind,
            knowledge_cutoff=knowledge_cutoff,
            catalog=catalog,
            account_events=account_events,
        )
        warnings.extend(selection_warnings)

    snapshot_id: str | None = None
    revision: int | None = None
    snapshot_sources: list[dict[str, Any]] = []
    metrics: dict[str, dict[str, Any]] = {}
    cursor_proof: dict[str, Any] = {
        "cursor_scope": "unknown",
        "included_event_set_complete": False,
        "boundary_limited": False,
    }
    base_currency: str | None = None
    snapshot_binding: dict[str, Any] | None = None
    target_symbol = str((episode.get("scope") or {}).get("symbol") or "").upper()
    if row is not None:
        snapshot_id = str(row["snapshot_id"])
        revision = int(row["revision"])
        known = _parse_timestamp(row["knowledge_cutoff_at"], "snapshot.knowledge_cutoff_at")
        observed = min(event_at, known)
        catalog_ref = catalog[snapshot_id]
        cursor_scope = str(catalog_ref.get("cursor_scope") or "partition")
        cursor_proof = {
            "cursor_scope": cursor_scope,
            "included_event_set_complete": (
                catalog_ref.get("included_event_set_complete") is True
            ),
            "boundary_limited": force_partial,
        }
        base_currency = str(row.get("currency") or "CNY").upper()
        snapshot_sources = [
            _snapshot_source_ref(
                row,
                catalog_ref,
                effective_at=observed,
            )
        ]
        snapshot, stale_keys, model_warnings = _snapshot_model(
            reader,
            row,
            anchor_at=event_at,
            knowledge_cutoff=knowledge_cutoff,
            catalog_ref=catalog_ref,
            snapshot_ref=snapshot_sources[0],
        )
        warnings.extend(model_warnings)
        if snapshot is None:
            snapshot_status = "invalid"
        else:
            metrics = _metric_payloads(
                snapshot,
                target_symbol=target_symbol,
                stale_position_keys=stale_keys,
                revision=revision,
                snapshot_source_ref=snapshot_sources[0],
                force_partial=force_partial,
            )

        snapshot_binding = {
            "snapshot_id": snapshot_id,
            "revision": revision,
            "state_content_id": snapshot_sources[0]["content_id"],
            "catalog_content_id": _value_content_id(catalog_ref),
            "included_event_ids_content_id": _value_content_id(
                sorted(str(item) for item in catalog_ref.get("included_event_ids", []))
            ),
            "same_business_day": (
                date.fromisoformat(str(row.get("as_of_date")))
                == _business_date(event_at)
            ),
            "cursor_scope": cursor_proof["cursor_scope"],
            "included_event_set_complete": cursor_proof[
                "included_event_set_complete"
            ],
            "metric_availability_ceiling": (
                "none"
                if snapshot_status == "invalid"
                else "partial"
                if force_partial
                else "available"
            ),
        }

    ordering_key = _canonical_ordering_key(event)
    anchor = {
        "kind": kind,
        "side": side,
        "event_id": event_id,
        "event_at": _iso(event_at),
        "as_of": _iso(event_at),
        "knowledge_cutoff": _iso(knowledge_cutoff),
        "ordering_key": ordering_key,
    }
    decision_status = _decision_link_status(episode)
    resolved_target_symbol = target_symbol or str(
        (episode.get("scope") or {}).get("instrument_id") or "UNKNOWN"
    )
    lineage = episode.get("lineage") if isinstance(episode.get("lineage"), Mapping) else {}
    source_binding = {
        "episode_content_id": "sha256:"
        + str(lineage.get("canonical_content_digest") or ""),
        "event_content_id": _content_id(event),
        "snapshot_binding": snapshot_binding,
    }
    context_id = _stable_id(
        "ctx",
        {
            "episode_id": episode_id,
            "anchor": anchor,
            "target_symbol": resolved_target_symbol,
            "decision_link_status": decision_status,
            "snapshot_status": snapshot_status,
            "snapshot_id": snapshot_id,
            "revision": revision,
            "source_binding": source_binding,
            "base_currency": base_currency,
            "metric_registry_version": METRIC_REGISTRY_VERSION,
        },
    )
    return {
        "context_id": context_id,
        "episode_id": episode_id,
        "decision_link_status": decision_status,
        "target_symbol": resolved_target_symbol,
        "source_binding": source_binding,
        "anchor": anchor,
        "portfolio_snapshot": {
            "status": snapshot_status,
            "snapshot_id": snapshot_id,
            "revision": revision,
            "base_currency": base_currency,
            "cursor_proof": cursor_proof,
            "source_refs": snapshot_sources,
        },
        "metrics": metrics,
        "warnings": _sorted_warnings(warnings),
    }


def _build_deltas(contexts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Mapping[str, Any]]] = {}
    for context in contexts:
        anchor = context.get("anchor") or {}
        key = (str(context.get("episode_id")), str(anchor.get("event_id")))
        grouped.setdefault(key, {})[str(anchor.get("side"))] = context
    deltas: list[dict[str, Any]] = []
    for (episode_id, event_id), pair in sorted(grouped.items()):
        before = pair.get("pre")
        after = pair.get("post")
        if before is None or after is None:
            continue
        before_metrics = before.get("metrics") if isinstance(before.get("metrics"), Mapping) else {}
        after_metrics = after.get("metrics") if isinstance(after.get("metrics"), Mapping) else {}
        for metric_key in sorted(set(before_metrics).union(after_metrics)):
            left = before_metrics.get(metric_key)
            right = after_metrics.get(metric_key)
            availability = "missing"
            value: str | None = None
            unit: str | None = None
            compatibility = "unknown"
            warning_codes: set[str] = set()
            if isinstance(left, Mapping) and isinstance(right, Mapping):
                warning_codes.update(str(item) for item in left.get("warning_codes", []))
                warning_codes.update(str(item) for item in right.get("warning_codes", []))
                methods_equal = left.get("method") == right.get("method")
                units_equal = left.get("unit") == right.get("unit")
                unit = (
                    str(left.get("unit"))
                    if units_equal and left.get("unit") is not None
                    else None
                )
                compatibility = "same" if methods_equal and units_equal else "incompatible"
                comparable = (
                    left.get("value") is not None
                    and right.get("value") is not None
                    and left.get("availability") == "available"
                    and right.get("availability") == "available"
                    and methods_equal
                    and units_equal
                )
                if comparable:
                    value = _decimal_text(
                        _decimal(right["value"], "delta.to")
                        - _decimal(left["value"], "delta.from")
                    )
                    availability = "available"
                elif compatibility == "incompatible":
                    availability = "not_comparable"
                    warning_codes.add("INCOMPATIBLE_METHOD_OR_UNIT")
                elif left.get("availability") == "invalid" or right.get("availability") == "invalid":
                    availability = "invalid"
                elif "partial" in {
                    left.get("availability"),
                    right.get("availability"),
                }:
                    warning_codes.add("PARTIAL_ENDPOINT")
            delta_id = _stable_id(
                "delta",
                {
                    "episode_id": episode_id,
                    "event_id": event_id,
                    "metric_key": metric_key,
                    "from": before["context_id"],
                    "to": after["context_id"],
                },
            )
            deltas.append(
                {
                    "delta_id": delta_id,
                    "episode_id": episode_id,
                    "metric_key": metric_key,
                    "from_context_id": before["context_id"],
                    "to_context_id": after["context_id"],
                    "availability": availability,
                    "value": value,
                    "unit": unit,
                    "method_compatibility": compatibility,
                    "warning_codes": sorted(warning_codes),
                }
            )
    return sorted(
        deltas,
        key=lambda item: (
            item["episode_id"],
            item["from_context_id"],
            item["to_context_id"],
            item["metric_key"],
            item["delta_id"],
        ),
    )


def build_episode_portfolio_context(
    episode_collection: Mapping[str, Any],
    *,
    portfolio_db: str | Path,
    as_of: str,
    knowledge_cutoff: str,
    episode_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build the canonical P2E-3 fact artifact without source writes."""

    if not isinstance(episode_collection, Mapping):
        raise EpisodePortfolioContextError("episode_collection must be an object")
    as_of_time = _parse_timestamp(as_of, "as_of")
    knowledge_time = _parse_timestamp(knowledge_cutoff, "knowledge_cutoff")
    if episode_collection.get("schema_version") != COLLECTION_SCHEMA_VERSION:
        raise EpisodePortfolioContextError("unsupported TradeEpisode collection schema")
    episode_validation = validate_episode_collection(episode_collection)
    source_warnings: list[dict[str, Any]] = []
    source_blockers = {
        str(item.get("code") or "")
        for item in episode_validation.get("findings", [])
        if isinstance(item, Mapping) and item.get("severity") == "blocker"
    }
    unexpected_blockers = source_blockers - _ALLOWED_SOURCE_BLOCKERS
    if unexpected_blockers:
        raise EpisodePortfolioContextError(
            "source TradeEpisode collection is blocked: "
            + ", ".join(sorted(unexpected_blockers))
        )
    if source_blockers:
        source_warnings.append(
            _warning(
                "SOURCE_EPISODE_BLOCKED",
                "Only decision-linkage blockers were preserved: "
                + ", ".join(sorted(source_blockers)),
            )
        )
    collection_digest = str(episode_collection.get("collection_digest") or "")
    if _SHA256_RE.fullmatch(collection_digest) is None:
        raise EpisodePortfolioContextError(
            "source TradeEpisode collection requires a valid collection_digest"
        )
    requested_ids = (
        {str(item) for item in episode_ids} if episode_ids is not None else None
    )
    raw_episodes = [
        item
        for item in episode_collection.get("episodes", [])
        if isinstance(item, Mapping)
        and (requested_ids is None or str(item.get("episode_id")) in requested_ids)
    ]
    raw_episodes.sort(
        key=lambda item: (
            str((item.get("scope") or {}).get("account_id") or ""),
            str((item.get("scope") or {}).get("instrument_id") or ""),
            str(item.get("opened_at") or ""),
            str(item.get("episode_id") or ""),
        )
    )
    catalog_rows = [
        item
        for item in episode_collection.get("snapshot_catalog", [])
        if isinstance(item, Mapping) and item.get("snapshot_id")
    ]
    catalog_ids = [str(item.get("snapshot_id")) for item in catalog_rows]
    if len(catalog_ids) != len(set(catalog_ids)):
        raise EpisodePortfolioContextError(
            "source TradeEpisode collection has duplicate snapshot IDs"
        )
    catalog = {str(item.get("snapshot_id")): item for item in catalog_rows}
    account_events: dict[str, list[dict[str, Any]]] = {}
    seen_account_events: set[tuple[str, str]] = set()
    for source_episode in episode_collection.get("episodes", []):
        if not isinstance(source_episode, Mapping):
            continue
        account = str((source_episode.get("scope") or {}).get("account_id") or "")
        for item in source_episode.get("event_refs", []):
            if not isinstance(item, Mapping):
                continue
            identity = (account, str(item.get("event_id") or ""))
            if identity in seen_account_events:
                continue
            seen_account_events.add(identity)
            account_events.setdefault(account, []).append(dict(item))
    for rows in account_events.values():
        rows.sort(key=_event_order)
    visible_account_events = {
        account: [
            item
            for item in rows
            if _parse_timestamp(item.get("effective_at"), "event.effective_at")
            <= as_of_time
            and _parse_timestamp(item.get("known_at"), "event.known_at")
            <= knowledge_time
        ]
        for account, rows in account_events.items()
    }
    ambiguous_by_account = {
        account: _ambiguous_event_ids(rows)
        for account, rows in visible_account_events.items()
    }
    contexts: list[dict[str, Any]] = []
    material_events: list[dict[str, Any]] = []
    excluded_event_count = 0
    with _P2BSnapshotReader(portfolio_db) as reader:
        for episode in raw_episodes:
            source_events = [
                item
                for item in episode.get("event_refs", [])
                if isinstance(item, Mapping)
            ]
            events = []
            for item in source_events:
                effective_at = _parse_timestamp(
                    item.get("effective_at"), "event.effective_at"
                )
                known_at = _parse_timestamp(item.get("known_at"), "event.known_at")
                if effective_at <= as_of_time and known_at <= knowledge_time:
                    events.append(item)
                else:
                    excluded_event_count += 1
            events.sort(key=_event_order)
            account = str((episode.get("scope") or {}).get("account_id") or "")
            ambiguous_ids = ambiguous_by_account.get(account, set())
            for event in events:
                event_id = str(event.get("event_id"))
                material_events.append(
                    _material_event_manifest_entry(episode, event)
                )
                for side in ("pre", "post"):
                    contexts.append(
                        _build_context(
                            reader,
                            episode=episode,
                            event=event,
                            side=side,
                            knowledge_cutoff=knowledge_time,
                            catalog=catalog,
                            account_events=account_events.get(account, ()),
                            ambiguous=event_id in ambiguous_ids,
                        )
                    )
    contexts.sort(key=_context_sort_key)
    material_events.sort(
        key=lambda item: (
            item["episode_id"],
            item["event_at"],
            canonical_json_bytes(item["ordering_key"]),
            item["event_id"],
        )
    )
    deltas = _build_deltas(contexts)
    if excluded_event_count:
        source_warnings.append(
            _warning(
                "EVENTS_EXCLUDED_BY_CUTOFF",
                f"{excluded_event_count} event reference(s) were outside as_of or knowledge_cutoff.",
            )
        )
    artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "content_id": "",
        "episode_artifact_ref": {
            "content_id": f"sha256:{collection_digest}",
            "schema_version": str(episode_collection.get("schema_version")),
        },
        "source_binding": {
            "schema_version": "p2e3.source_binding.v1",
            "episode_collection_content_id": f"sha256:{collection_digest}",
            "episode_collection_cutoff": _iso(
                _parse_timestamp(
                    episode_collection.get("cutoff_at"),
                    "episode_collection.cutoff_at",
                )
            ),
            "selection": {
                "mode": "explicit" if requested_ids is not None else "all_visible",
                "requested_episode_ids": sorted(requested_ids or set()),
                "resolved_episode_ids": sorted(
                    str(item.get("episode_id") or "") for item in raw_episodes
                ),
            },
            "material_events": material_events,
            "material_event_set_content_id": _value_content_id(material_events),
        },
        "as_of": _iso(as_of_time),
        "knowledge_cutoff": _iso(knowledge_time),
        "metric_registry_version": METRIC_REGISTRY_VERSION,
        "contexts": contexts,
        "deltas": deltas,
        "warnings": _sorted_warnings(source_warnings),
    }
    artifact["content_id"] = _content_id(artifact)
    validation = validate_episode_portfolio_context(artifact)
    if validation["validation_status"] == "blocked":
        raise EpisodePortfolioContextError(
            "built artifact failed validation: "
            + "; ".join(str(item.get("message")) for item in validation["findings"])
        )
    return artifact


def _finding(severity: str, code: str, message: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message}


@lru_cache(maxsize=1)
def _contract_validator() -> Draft202012Validator:
    try:
        schema = json.loads(_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EpisodePortfolioContextError(
            f"cannot load P2E-3 contract schema: {exc}"
        ) from exc
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _schema_path(error: Any) -> str:
    parts = [str(item) for item in error.absolute_path]
    return "$" + "".join(
        f"[{part}]" if part.isdigit() else f".{part}" for part in parts
    )


def _validate_decimal_value(
    value: object, *, field: str, findings: list[dict[str, str]]
) -> None:
    if value is None:
        return
    if not isinstance(value, str) or _DECIMAL_RE.fullmatch(value) is None:
        findings.append(
            _finding("blocker", "INVALID_DECIMAL", f"{field} must be a canonical Decimal string")
        )


def _validate_source_refs(
    values: object,
    *,
    field: str,
    findings: list[dict[str, str]],
    effective_limit: datetime | None = None,
    knowledge_limit: datetime | None = None,
) -> None:
    if not isinstance(values, list):
        return
    for index, source in enumerate(values):
        if not isinstance(source, Mapping):
            continue
        try:
            if source.get("effective_at"):
                effective_at = _parse_timestamp(
                    source["effective_at"], f"{field}[{index}].effective_at"
                )
                if source["effective_at"] != _iso(effective_at):
                    findings.append(
                        _finding(
                            "blocker",
                            "NON_CANONICAL_TIME",
                            f"{field}[{index}].effective_at must use canonical UTC seconds",
                        )
                    )
                if effective_limit is not None and effective_at > effective_limit:
                    findings.append(
                        _finding(
                            "blocker",
                            "FUTURE_SOURCE_EFFECTIVE_TIME",
                            f"{field}[{index}] effective time exceeds the anchor",
                        )
                    )
            if source.get("knowledge_at"):
                known_at = _parse_timestamp(
                    source["knowledge_at"], f"{field}[{index}].knowledge_at"
                )
                if source["knowledge_at"] != _iso(known_at):
                    findings.append(
                        _finding(
                            "blocker",
                            "NON_CANONICAL_TIME",
                            f"{field}[{index}].knowledge_at must use canonical UTC seconds",
                        )
                    )
                if knowledge_limit is not None and known_at > knowledge_limit:
                    findings.append(
                        _finding(
                            "blocker",
                            "FUTURE_SOURCE_KNOWLEDGE_TIME",
                            f"{field}[{index}] knowledge time exceeds the cutoff",
                        )
                    )
        except EpisodePortfolioContextError as exc:
            findings.append(_finding("blocker", "INVALID_SOURCE_TIME", str(exc)))


def _validate_canonical_timestamp(
    value: object, *, field: str, findings: list[dict[str, str]]
) -> datetime | None:
    try:
        parsed = _parse_timestamp(value, field)
    except EpisodePortfolioContextError as exc:
        findings.append(_finding("blocker", "INVALID_CANONICAL_TIME", str(exc)))
        return None
    if value != _iso(parsed):
        findings.append(
            _finding(
                "blocker",
                "NON_CANONICAL_TIME",
                f"{field} must use canonical UTC seconds",
            )
        )
    return parsed


def _is_sorted_unique(values: Sequence[object]) -> bool:
    canonical = [_canonical_token(value) for value in values]
    return canonical == sorted(set(canonical))


def validate_episode_portfolio_context(
    artifact: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the structural, semantic, temporal and digest contract."""

    findings: list[dict[str, str]] = []
    if not isinstance(artifact, Mapping):
        findings.append(_finding("blocker", "INVALID_ROOT", "artifact root must be an object"))
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "validation_mode": "offline_structural",
            "validation_status": "blocked",
            "findings": findings,
        }
    try:
        schema_errors = sorted(
            _contract_validator().iter_errors(artifact),
            key=lambda item: (_schema_path(item), item.message),
        )
        findings.extend(
            _finding(
                "blocker",
                "SCHEMA_VIOLATION",
                f"{_schema_path(error)}: {error.message}",
            )
            for error in schema_errors
        )
    except Exception as exc:
        findings.append(_finding("blocker", "SCHEMA_VALIDATOR_ERROR", str(exc)))
    try:
        canonical_json_bytes(artifact)
    except ArtifactIOError as exc:
        findings.append(_finding("blocker", "NON_CANONICAL_JSON", str(exc)))
    if artifact.get("schema_version") != SCHEMA_VERSION:
        findings.append(_finding("blocker", "UNSUPPORTED_SCHEMA", "unsupported schema_version"))
    if artifact.get("metric_registry_version") != METRIC_REGISTRY_VERSION:
        findings.append(
            _finding(
                "blocker",
                "UNSUPPORTED_METRIC_REGISTRY",
                "metric_registry_version does not match the public P2E-2 registry",
            )
        )
    episode_ref = (
        artifact.get("episode_artifact_ref")
        if isinstance(artifact.get("episode_artifact_ref"), Mapping)
        else {}
    )
    if episode_ref.get("schema_version") != COLLECTION_SCHEMA_VERSION:
        findings.append(
            _finding(
                "blocker",
                "UNSUPPORTED_EPISODE_ARTIFACT_REF",
                "episode_artifact_ref must identify a P2C collection",
            )
        )
    source_binding = (
        artifact.get("source_binding")
        if isinstance(artifact.get("source_binding"), Mapping)
        else {}
    )
    if (
        episode_ref.get("content_id")
        != source_binding.get("episode_collection_content_id")
    ):
        findings.append(
            _finding(
                "blocker",
                "SOURCE_BINDING_DIGEST_MISMATCH",
                "episode artifact ref and source binding identify different collections",
            )
        )
    material_events = source_binding.get("material_events")
    if not isinstance(material_events, list):
        material_events = []
    try:
        expected_material_digest = _value_content_id(material_events)
    except ArtifactIOError:
        expected_material_digest = None
    if source_binding.get("material_event_set_content_id") != expected_material_digest:
        findings.append(
            _finding(
                "blocker",
                "SOURCE_BINDING_DIGEST_MISMATCH",
                "material event set digest does not match its canonical rows",
            )
        )
    expected_material_order = sorted(
        (item for item in material_events if isinstance(item, Mapping)),
        key=lambda item: (
            str(item.get("episode_id") or ""),
            str(item.get("event_at") or ""),
            _canonical_token(item.get("ordering_key") or []),
            str(item.get("event_id") or ""),
        ),
    )
    if material_events != expected_material_order:
        findings.append(
            _finding(
                "blocker",
                "NON_CANONICAL_MATERIAL_EVENT_ORDER",
                "source binding material events are not in canonical order",
            )
        )
    material_index: dict[tuple[str, str], Mapping[str, Any]] = {}
    for index, item in enumerate(material_events):
        if not isinstance(item, Mapping):
            continue
        key = (
            str(item.get("episode_id") or ""),
            str(item.get("event_id") or ""),
        )
        if key in material_index:
            findings.append(
                _finding(
                    "blocker",
                    "DUPLICATE_MATERIAL_EVENT_IDENTITY",
                    f"source_binding.material_events[{index}] duplicates {key}",
                )
            )
        material_index[key] = item
        event_time = _validate_canonical_timestamp(
            item.get("event_at"),
            field=f"source_binding.material_events[{index}].event_at",
            findings=findings,
        )
        known_time = _validate_canonical_timestamp(
            item.get("known_at"),
            field=f"source_binding.material_events[{index}].known_at",
            findings=findings,
        )
        ordering = item.get("ordering_key")
        if isinstance(ordering, list) and len(ordering) == 4:
            _validate_canonical_timestamp(
                ordering[0],
                field=f"source_binding.material_events[{index}].ordering_key[0]",
                findings=findings,
            )
            if ordering[0] != item.get("event_at") or ordering[3] != item.get(
                "event_id"
            ):
                findings.append(
                    _finding(
                        "blocker",
                        "MATERIAL_EVENT_ORDERING_MISMATCH",
                        f"source_binding.material_events[{index}] ordering key is not bound to the event",
                    )
                )
    selection = (
        source_binding.get("selection")
        if isinstance(source_binding.get("selection"), Mapping)
        else {}
    )
    requested_selection = selection.get("requested_episode_ids")
    resolved_selection = selection.get("resolved_episode_ids")
    if isinstance(requested_selection, list) and requested_selection != sorted(
        requested_selection
    ):
        findings.append(
            _finding("blocker", "NON_CANONICAL_SELECTION", "requested episode IDs must be sorted")
        )
    if isinstance(resolved_selection, list) and resolved_selection != sorted(
        resolved_selection
    ):
        findings.append(
            _finding("blocker", "NON_CANONICAL_SELECTION", "resolved episode IDs must be sorted")
        )
    if selection.get("mode") == "all_visible" and requested_selection:
        findings.append(
            _finding("blocker", "INVALID_SELECTION", "all_visible selection cannot request explicit episode IDs")
        )
    if (
        selection.get("mode") == "explicit"
        and isinstance(requested_selection, list)
        and isinstance(resolved_selection, list)
        and not set(resolved_selection).issubset(requested_selection)
    ):
        findings.append(
            _finding("blocker", "INVALID_SELECTION", "resolved episode IDs must be a subset of requested IDs")
        )
    content_id = artifact.get("content_id")
    if not isinstance(content_id, str) or _CONTENT_ID_RE.fullmatch(content_id) is None:
        findings.append(_finding("blocker", "INVALID_CONTENT_ID", "invalid content_id"))
    else:
        try:
            expected = _content_id(artifact)
            if content_id != expected:
                findings.append(_finding("blocker", "CONTENT_ID_MISMATCH", "content_id does not match canonical content"))
        except (ArtifactIOError, TypeError, ValueError) as exc:
            findings.append(_finding("blocker", "CONTENT_ID_ERROR", str(exc)))
    try:
        top_as_of = _parse_timestamp(artifact.get("as_of"), "as_of")
        top_cutoff = _parse_timestamp(artifact.get("knowledge_cutoff"), "knowledge_cutoff")
        if artifact.get("as_of") != _iso(top_as_of) or artifact.get(
            "knowledge_cutoff"
        ) != _iso(top_cutoff):
            findings.append(
                _finding(
                    "blocker",
                    "NON_CANONICAL_TIME",
                    "top-level temporal boundaries must use canonical UTC seconds",
                )
            )
    except EpisodePortfolioContextError as exc:
        findings.append(_finding("blocker", "INVALID_TEMPORAL_BOUNDARY", str(exc)))
        top_as_of = top_cutoff = datetime.min.replace(tzinfo=timezone.utc)
    _validate_canonical_timestamp(
        source_binding.get("episode_collection_cutoff"),
        field="source_binding.episode_collection_cutoff",
        findings=findings,
    )
    for index, item in enumerate(material_events):
        if not isinstance(item, Mapping):
            continue
        event_time = _validate_canonical_timestamp(
            item.get("event_at"),
            field=f"source_binding.material_events[{index}].event_at",
            findings=[],
        )
        known_time = _validate_canonical_timestamp(
            item.get("known_at"),
            field=f"source_binding.material_events[{index}].known_at",
            findings=[],
        )
        if (
            event_time is not None
            and known_time is not None
            and (event_time > top_as_of or known_time > top_cutoff)
        ):
            findings.append(
                _finding(
                    "blocker",
                    "FUTURE_MATERIAL_EVENT",
                    f"source_binding.material_events[{index}] exceeds the artifact boundary",
                )
            )
    top_warnings = artifact.get("warnings")
    if isinstance(top_warnings, list):
        for index, warning in enumerate(top_warnings):
            if isinstance(warning, Mapping):
                if warning.get("severity") == "error":
                    findings.append(
                        _finding(
                            "blocker",
                            "TOP_LEVEL_ERROR_WARNING",
                            f"warnings[{index}] cannot downgrade a source error to an accepted artifact",
                        )
                    )
                _validate_source_refs(
                    warning.get("source_refs"),
                    field=f"warnings[{index}].source_refs",
                    findings=findings,
                    effective_limit=top_as_of,
                    knowledge_limit=top_cutoff,
                )
        if not _is_sorted_unique(top_warnings):
            findings.append(
                _finding("blocker", "NON_CANONICAL_WARNINGS", "top warnings must be sorted and unique")
            )
    contexts = artifact.get("contexts")
    if not isinstance(contexts, list):
        findings.append(_finding("blocker", "INVALID_CONTEXTS", "contexts must be an array"))
        contexts = []
    valid_context_rows = [item for item in contexts if isinstance(item, Mapping)]
    if len(valid_context_rows) == len(contexts) and contexts != sorted(
        valid_context_rows, key=_context_sort_key
    ):
        findings.append(
            _finding(
                "blocker",
                "NON_CANONICAL_CONTEXT_ORDER",
                "contexts are not in canonical episode/event/side order",
            )
        )
    seen_contexts: set[str] = set()
    context_index: dict[str, Mapping[str, Any]] = {}
    registered_method_ids = {
        spec["method_id"] for spec in PORTFOLIO_METRIC_METHOD_REGISTRY.values()
    }
    for index, context in enumerate(contexts):
        if not isinstance(context, Mapping):
            findings.append(_finding("blocker", "INVALID_CONTEXT", f"contexts[{index}] must be an object"))
            continue
        context_id = str(context.get("context_id") or "")
        if not context_id or context_id in seen_contexts:
            findings.append(_finding("blocker", "INVALID_CONTEXT_ID", "context IDs must be non-empty and unique"))
        seen_contexts.add(context_id)
        if context_id:
            context_index[context_id] = context
        anchor = context.get("anchor") if isinstance(context.get("anchor"), Mapping) else {}
        snapshot = (
            context.get("portfolio_snapshot")
            if isinstance(context.get("portfolio_snapshot"), Mapping)
            else {}
        )
        context_binding = (
            context.get("source_binding")
            if isinstance(context.get("source_binding"), Mapping)
            else {}
        )
        try:
            expected_context_id = _stable_id(
                "ctx",
                {
                    "episode_id": str(context.get("episode_id") or ""),
                    "anchor": anchor,
                    "target_symbol": str(context.get("target_symbol") or ""),
                    "decision_link_status": str(
                        context.get("decision_link_status") or ""
                    ),
                    "snapshot_status": snapshot.get("status"),
                    "snapshot_id": snapshot.get("snapshot_id"),
                    "revision": snapshot.get("revision"),
                    "source_binding": context_binding,
                    "base_currency": snapshot.get("base_currency"),
                    "metric_registry_version": artifact.get(
                        "metric_registry_version"
                    ),
                },
            )
        except ArtifactIOError:
            expected_context_id = ""
        if context_id != expected_context_id:
            findings.append(
                _finding(
                    "blocker",
                    "CONTEXT_ID_MISMATCH",
                    f"contexts[{index}] context_id does not match its canonical identity",
                )
            )
        try:
            event_at = _parse_timestamp(anchor.get("event_at"), "anchor.event_at")
            anchor_as_of = _parse_timestamp(anchor.get("as_of"), "anchor.as_of")
            anchor_cutoff = _parse_timestamp(anchor.get("knowledge_cutoff"), "anchor.knowledge_cutoff")
            if anchor_as_of > top_as_of or anchor_cutoff > top_cutoff:
                findings.append(_finding("blocker", "FUTURE_ANCHOR", "anchor exceeds artifact cutoff"))
            if event_at != anchor_as_of:
                findings.append(
                    _finding(
                        "blocker",
                        "ANCHOR_EVENT_TIME_MISMATCH",
                        "anchor.event_at and anchor.as_of must denote the same instant",
                    )
                )
            if (
                anchor.get("event_at") != _iso(event_at)
                or anchor.get("as_of") != _iso(anchor_as_of)
                or anchor.get("knowledge_cutoff") != _iso(anchor_cutoff)
            ):
                findings.append(
                    _finding(
                        "blocker",
                        "NON_CANONICAL_TIME",
                        f"contexts[{index}] anchor times must use canonical UTC seconds",
                    )
                )
            if anchor.get("knowledge_cutoff") != artifact.get(
                "knowledge_cutoff"
            ):
                findings.append(
                    _finding(
                        "blocker",
                        "ANCHOR_KNOWLEDGE_CUTOFF_MISMATCH",
                        f"contexts[{index}] must use the artifact knowledge cutoff",
                    )
                )
            ordering_key = anchor.get("ordering_key")
            if not (
                isinstance(ordering_key, list)
                and len(ordering_key) == 4
                and ordering_key[0] == anchor.get("event_at")
                and ordering_key[3] == anchor.get("event_id")
            ):
                findings.append(
                    _finding(
                        "blocker",
                        "ANCHOR_ORDERING_KEY_MISMATCH",
                        f"contexts[{index}] ordering key is not bound to its event",
                    )
                )
        except EpisodePortfolioContextError as exc:
            findings.append(_finding("blocker", "INVALID_ANCHOR_TIME", str(exc)))
            anchor_as_of = anchor_cutoff = datetime.min.replace(tzinfo=timezone.utc)
        material_key = (
            str(context.get("episode_id") or ""),
            str(anchor.get("event_id") or ""),
        )
        material = material_index.get(material_key)
        if material is None:
            findings.append(
                _finding(
                    "blocker",
                    "MATERIAL_EVENT_COVERAGE_MISMATCH",
                    f"contexts[{index}] does not resolve in the material-event source binding",
                )
            )
        else:
            expected_material_values = {
                "episode_content_id": material.get("episode_content_id"),
                "event_content_id": material.get("event_content_id"),
            }
            if any(
                context_binding.get(field) != value
                for field, value in expected_material_values.items()
            ) or any(
                actual != expected
                for actual, expected in (
                    (anchor.get("kind"), material.get("anchor_kind")),
                    (anchor.get("event_at"), material.get("event_at")),
                    (anchor.get("ordering_key"), material.get("ordering_key")),
                    (context.get("target_symbol"), material.get("target_symbol")),
                    (
                        context.get("decision_link_status"),
                        material.get("decision_link_status"),
                    ),
                )
            ):
                findings.append(
                    _finding(
                        "blocker",
                        "CONTEXT_EVENT_BINDING_MISMATCH",
                        f"contexts[{index}] does not match its material-event source binding",
                    )
                )
        _validate_source_refs(
            snapshot.get("source_refs"),
            field=f"contexts[{index}].portfolio_snapshot.source_refs",
            findings=findings,
            effective_limit=anchor_as_of,
            knowledge_limit=anchor_cutoff,
        )
        snapshot_sources = snapshot.get("source_refs")
        if isinstance(snapshot_sources, list) and not _is_sorted_unique(
            snapshot_sources
        ):
            findings.append(
                _finding(
                    "blocker",
                    "NON_CANONICAL_SOURCE_REFS",
                    f"contexts[{index}] snapshot source refs must be sorted and unique",
                )
            )
        snapshot_binding = context_binding.get("snapshot_binding")
        cursor_proof = (
            snapshot.get("cursor_proof")
            if isinstance(snapshot.get("cursor_proof"), Mapping)
            else {}
        )
        snapshot_status = snapshot.get("status")
        if snapshot.get("snapshot_id") is None:
            if snapshot_binding is not None or cursor_proof != {
                "cursor_scope": "unknown",
                "included_event_set_complete": False,
                "boundary_limited": False,
            }:
                findings.append(
                    _finding(
                        "blocker",
                        "SNAPSHOT_BINDING_MISMATCH",
                        f"contexts[{index}] unusable unselected snapshot must not claim a source binding",
                    )
                )
        elif not isinstance(snapshot_binding, Mapping):
            findings.append(
                _finding(
                    "blocker",
                    "SNAPSHOT_BINDING_MISMATCH",
                    f"contexts[{index}] selected snapshot requires a source binding",
                )
            )
        else:
            source_ref = (
                snapshot_sources[0]
                if isinstance(snapshot_sources, list)
                and len(snapshot_sources) == 1
                and isinstance(snapshot_sources[0], Mapping)
                else {}
            )
            if (
                snapshot_binding.get("snapshot_id")
                != snapshot.get("snapshot_id")
                or snapshot_binding.get("revision") != snapshot.get("revision")
                or snapshot_binding.get("state_content_id")
                != source_ref.get("content_id")
                or source_ref.get("source_type") != "portfolio_snapshot"
                or source_ref.get("source_id") != snapshot.get("snapshot_id")
                or source_ref.get("revision") != snapshot.get("revision")
                or source_ref.get("effective_at") is None
                or source_ref.get("knowledge_at") is None
                or snapshot_binding.get("cursor_scope")
                != cursor_proof.get("cursor_scope")
                or snapshot_binding.get("included_event_set_complete")
                != cursor_proof.get("included_event_set_complete")
            ):
                findings.append(
                    _finding(
                        "blocker",
                        "SNAPSHOT_BINDING_MISMATCH",
                        f"contexts[{index}] snapshot identity, revision, state or cursor proof drifted",
                    )
                )
            ceiling = snapshot_binding.get("metric_availability_ceiling")
            if snapshot_status == "exact" and not (
                anchor.get("side") == "post"
                and cursor_proof.get("cursor_scope") == "account"
                and cursor_proof.get("included_event_set_complete") is True
                and cursor_proof.get("boundary_limited") is False
                and snapshot_binding.get("same_business_day") is True
                and ceiling == "available"
            ):
                findings.append(
                    _finding(
                        "blocker",
                        "CURSOR_PROOF_MISMATCH",
                        f"contexts[{index}] exact status lacks a complete account cursor proof",
                    )
                )
            if cursor_proof.get("boundary_limited") is True and not (
                (snapshot_status == "replayed" and ceiling == "partial")
                or (snapshot_status == "invalid" and ceiling == "none")
            ):
                findings.append(
                    _finding(
                        "blocker",
                        "AVAILABILITY_CEILING_VIOLATION",
                        f"contexts[{index}] boundary-limited cursor must remain replayed/partial",
                    )
                )
            if snapshot_status == "invalid" and ceiling != "none":
                findings.append(
                    _finding(
                        "blocker",
                        "AVAILABILITY_CEILING_VIOLATION",
                        f"contexts[{index}] invalid snapshot must have a none metric ceiling",
                    )
                )
        metrics = context.get("metrics") if isinstance(context.get("metrics"), Mapping) else {}
        if snapshot.get("status") in {"missing", "ambiguous", "invalid"} and metrics:
            findings.append(
                _finding(
                    "blocker",
                    "METRICS_FOR_UNUSABLE_SNAPSHOT",
                    f"contexts[{index}] cannot publish metrics for an unusable snapshot",
                )
            )
        if snapshot.get("status") in {"exact", "replayed"}:
            expected_core_metrics = set(PORTFOLIO_METRIC_METHOD_REGISTRY).difference(
                {"industry_weight::*"}
            )
            missing_core_metrics = expected_core_metrics.difference(metrics)
            if not metrics:
                findings.append(
                    _finding(
                        "blocker",
                        "MISSING_METRICS_FOR_USABLE_SNAPSHOT",
                        f"contexts[{index}] requires metrics for a usable snapshot",
                    )
                )
            if missing_core_metrics:
                findings.append(
                    _finding(
                        "blocker",
                        "MISSING_REGISTERED_METRICS",
                        f"contexts[{index}] is missing registered metrics: "
                        + ", ".join(sorted(missing_core_metrics)),
                    )
                )
        for metric_key, metric in metrics.items():
            if not isinstance(metric_key, str) or _METRIC_KEY_RE.fullmatch(metric_key) is None:
                findings.append(_finding("blocker", "INVALID_METRIC_KEY", f"invalid metric key: {metric_key!r}"))
                continue
            if not isinstance(metric, Mapping):
                findings.append(_finding("blocker", "INVALID_METRIC", f"metric {metric_key} must be an object"))
                continue
            _validate_decimal_value(metric.get("value"), field=f"metrics.{metric_key}.value", findings=findings)
            availability = metric.get("availability")
            if availability not in {"available", "partial", "missing", "not_applicable", "invalid"}:
                findings.append(_finding("blocker", "INVALID_AVAILABILITY", f"invalid availability for {metric_key}"))
            if availability in {"missing", "not_applicable", "invalid"} and metric.get("value") is not None:
                findings.append(_finding("blocker", "VALUE_FOR_UNAVAILABLE_METRIC", f"unavailable metric {metric_key} must be null"))
            if availability in {"available", "partial"} and metric.get("value") is None:
                findings.append(
                    _finding(
                        "blocker",
                        "MISSING_AVAILABLE_METRIC_VALUE",
                        f"metric {metric_key} requires a value when {availability}",
                    )
                )
            method = metric.get("method") if isinstance(metric.get("method"), Mapping) else {}
            method_id = str(method.get("method_id") or "")
            method_version = str(method.get("method_version") or "")
            expected_spec = PORTFOLIO_METRIC_METHOD_REGISTRY.get(
                "industry_weight::*"
                if metric_key.startswith("industry_weight.")
                else metric_key
            )
            expected_method_id = (
                expected_spec.get("method_id") if expected_spec is not None else None
            )
            if (
                expected_method_id is None
                or method_id not in registered_method_ids
                or method_id != expected_method_id
                or method_version != METRIC_REGISTRY_VERSION
            ):
                findings.append(
                    _finding(
                        "blocker",
                        "UNREGISTERED_METRIC_METHOD",
                        f"metric {metric_key} does not match the public P2E-2 registry",
                    )
                )
            if expected_spec is not None:
                unit_kind = expected_spec.get("unit_kind")
                expected_unit = (
                    snapshot.get("base_currency")
                    if unit_kind == "base_currency"
                    else unit_kind
                )
                if metric.get("unit") != expected_unit:
                    findings.append(
                        _finding(
                            "blocker",
                            "METRIC_UNIT_MISMATCH",
                            f"metric {metric_key} unit does not match its P2E-2 registry metadata",
                        )
                    )
                raw_value = metric.get("value")
                if isinstance(raw_value, str) and _DECIMAL_RE.fullmatch(raw_value):
                    numeric_value = Decimal(raw_value)
                    value_domain = expected_spec.get("value_domain")
                    invalid_domain = (
                        value_domain == "nonnegative" and numeric_value < 0
                    ) or (
                        value_domain == "zero_if_numeric" and numeric_value != 0
                    ) or (
                        value_domain == "nonnegative_integer"
                        and (
                            numeric_value < 0
                            or numeric_value != numeric_value.to_integral_value()
                        )
                    ) or (
                        value_domain == "unit_interval"
                        and not (Decimal("0") <= numeric_value <= Decimal("1"))
                    )
                    if invalid_domain:
                        findings.append(
                            _finding(
                                "blocker",
                                "METRIC_VALUE_DOMAIN_MISMATCH",
                                f"metric {metric_key} violates its P2E-2 registry value domain",
                            )
                        )
            if snapshot_status in {"exact", "replayed"} and availability == "not_applicable":
                findings.append(
                    _finding(
                        "blocker",
                        "INVALID_METRIC_AVAILABILITY",
                        f"metric {metric_key} cannot be not_applicable for a usable v1 snapshot",
                    )
                )
            sources = metric.get("source_refs")
            if availability in {"available", "partial"} and (not isinstance(sources, list) or not sources):
                findings.append(_finding("blocker", "MISSING_METRIC_PROVENANCE", f"metric {metric_key} requires source refs"))
            _validate_source_refs(
                sources,
                field=f"contexts[{index}].metrics.{metric_key}.source_refs",
                findings=findings,
                effective_limit=anchor_as_of,
                knowledge_limit=anchor_cutoff,
            )
            if (
                isinstance(snapshot_sources, list)
                and sources != snapshot_sources
            ):
                findings.append(
                    _finding(
                        "blocker",
                        "SOURCE_REF_BINDING_MISMATCH",
                        f"metric {metric_key} is not bound to its context snapshot",
                    )
                )
            if isinstance(sources, list) and not _is_sorted_unique(sources):
                findings.append(
                    _finding(
                        "blocker",
                        "NON_CANONICAL_SOURCE_REFS",
                        f"metric {metric_key} source refs must be sorted and unique",
                    )
                )
            warning_codes = metric.get("warning_codes")
            if isinstance(warning_codes, list) and warning_codes != sorted(
                set(warning_codes)
            ):
                findings.append(
                    _finding(
                        "blocker",
                        "NON_CANONICAL_WARNING_CODES",
                        f"metric {metric_key} warning codes must be sorted and unique",
                    )
                )
            warning_code_set = (
                {str(item) for item in warning_codes}
                if isinstance(warning_codes, list)
                else set()
            )
            if availability == "partial" and not warning_code_set.intersection(
                _PARTIAL_METRIC_WARNING_CODES
            ):
                findings.append(
                    _finding(
                        "blocker",
                        "METRIC_AVAILABILITY_WARNING_MISMATCH",
                        f"partial metric {metric_key} lacks a recognized degradation code",
                    )
                )
            if availability == "available" and warning_code_set.intersection(
                _PARTIAL_METRIC_WARNING_CODES
            ):
                findings.append(
                    _finding(
                        "blocker",
                        "METRIC_AVAILABILITY_WARNING_MISMATCH",
                        f"available metric {metric_key} carries a degradation code",
                    )
                )
            if availability == "invalid" and "NON_POSITIVE_NAV" not in warning_code_set:
                findings.append(
                    _finding(
                        "blocker",
                        "METRIC_AVAILABILITY_WARNING_MISMATCH",
                        f"invalid metric {metric_key} lacks NON_POSITIVE_NAV",
                    )
                )
            if (
                isinstance(snapshot_binding, Mapping)
                and snapshot_binding.get("metric_availability_ceiling") == "partial"
                and availability == "available"
            ):
                findings.append(
                    _finding(
                        "blocker",
                        "AVAILABILITY_CEILING_VIOLATION",
                        f"metric {metric_key} exceeds its source-bound partial ceiling",
                    )
                )
        context_warnings = context.get("warnings")
        if isinstance(context_warnings, list):
            for warning_index, warning in enumerate(context_warnings):
                if isinstance(warning, Mapping):
                    warning_allows_excluded_source = warning.get("code") in {
                        "PRICE_NOT_VISIBLE"
                    }
                    _validate_source_refs(
                        warning.get("source_refs"),
                        field=f"contexts[{index}].warnings[{warning_index}].source_refs",
                        findings=findings,
                        effective_limit=(
                            None if warning_allows_excluded_source else anchor_as_of
                        ),
                        knowledge_limit=(
                            None if warning_allows_excluded_source else anchor_cutoff
                        ),
                    )
            if not _is_sorted_unique(context_warnings):
                findings.append(
                    _finding(
                        "blocker",
                        "NON_CANONICAL_WARNINGS",
                        f"contexts[{index}] warnings must be sorted and unique",
                    )
                )
            context_warning_codes = {
                str(item.get("code") or "")
                for item in context_warnings
                if isinstance(item, Mapping)
            }
            if snapshot_status in {"exact", "replayed"} and any(
                isinstance(item, Mapping) and item.get("severity") == "error"
                for item in context_warnings
            ):
                findings.append(
                    _finding(
                        "blocker",
                        "SNAPSHOT_STATUS_WARNING_MISMATCH",
                        f"contexts[{index}] usable snapshot cannot carry an error warning",
                    )
                )
            required_status_codes = {
                "missing": {"SNAPSHOT_MISSING", "SNAPSHOT_NOT_VISIBLE"},
                "ambiguous": {
                    "AMBIGUOUS_EVENT_ORDER",
                    "AMBIGUOUS_SNAPSHOT_REVISION",
                    "EVENT_CURSOR_AMBIGUOUS",
                },
                "invalid": {
                    "CASH_UNAVAILABLE",
                    "SNAPSHOT_RECONCILIATION_FAILED",
                    "SNAPSHOT_INVALID",
                    "PARTIAL_NAV_UNAVAILABLE",
                },
            }
            expected_codes = required_status_codes.get(str(snapshot_status))
            if expected_codes is not None and not context_warning_codes.intersection(
                expected_codes
            ):
                findings.append(
                    _finding(
                        "blocker",
                        "SNAPSHOT_STATUS_WARNING_MISMATCH",
                        f"contexts[{index}] snapshot status lacks a causal warning",
                    )
                )
            if (
                isinstance(snapshot_binding, Mapping)
                and snapshot_binding.get("metric_availability_ceiling") == "partial"
                and "PORTFOLIO_CURSOR_SCOPE_LIMITED" not in context_warning_codes
            ):
                findings.append(
                    _finding(
                        "blocker",
                        "AVAILABILITY_CEILING_VIOLATION",
                        f"contexts[{index}] partial ceiling lacks its cursor warning",
                    )
                )
    deltas = artifact.get("deltas")
    if not isinstance(deltas, list):
        findings.append(_finding("blocker", "INVALID_DELTAS", "deltas must be an array"))
        deltas = []
    context_pairs: dict[
        tuple[str, str], dict[str, Mapping[str, Any]]
    ] = {}
    for context in contexts:
        if not isinstance(context, Mapping):
            continue
        anchor = context.get("anchor")
        if not isinstance(anchor, Mapping):
            continue
        pair_key = (
            str(context.get("episode_id") or ""),
            str(anchor.get("event_id") or ""),
        )
        side = str(anchor.get("side") or "")
        pair = context_pairs.setdefault(pair_key, {})
        if side in pair:
            findings.append(
                _finding(
                    "blocker",
                    "DUPLICATE_CONTEXT_ANCHOR",
                    f"multiple {side!r} contexts exist for episode/event {pair_key}",
                )
            )
        pair[side] = context
    if set(context_pairs) != set(material_index):
        missing_pairs = sorted(set(material_index) - set(context_pairs))
        extra_pairs = sorted(set(context_pairs) - set(material_index))
        findings.append(
            _finding(
                "blocker",
                "MATERIAL_EVENT_COVERAGE_MISMATCH",
                "context pairs must exactly cover source-bound material events "
                f"(missing={len(missing_pairs)}, extra={len(extra_pairs)})",
            )
        )
    expected_delta_keys: Counter[tuple[str, str, str, str]] = Counter()
    for pair in context_pairs.values():
        if set(pair) != {"pre", "post"}:
            findings.append(
                _finding(
                    "blocker",
                    "INCOMPLETE_CONTEXT_ANCHOR_PAIR",
                    "each material episode/event anchor requires exactly one pre and one post context",
                )
            )
        before = pair.get("pre")
        after = pair.get("post")
        if before is None or after is None:
            continue
        before_anchor = (
            before.get("anchor")
            if isinstance(before.get("anchor"), Mapping)
            else {}
        )
        after_anchor = (
            after.get("anchor")
            if isinstance(after.get("anchor"), Mapping)
            else {}
        )
        shared_anchor_fields = (
            "kind",
            "event_id",
            "event_at",
            "as_of",
            "knowledge_cutoff",
            "ordering_key",
        )
        if any(
            before_anchor.get(field) != after_anchor.get(field)
            for field in shared_anchor_fields
        ) or any(
            before.get(field) != after.get(field)
            for field in ("target_symbol", "decision_link_status")
        ):
            findings.append(
                _finding(
                    "blocker",
                    "CONTEXT_ANCHOR_PAIR_MISMATCH",
                    "pre/post contexts must share event identity, temporal boundary, target and decision status",
                )
            )
        before_metrics = (
            before.get("metrics")
            if isinstance(before.get("metrics"), Mapping)
            else {}
        )
        after_metrics = (
            after.get("metrics")
            if isinstance(after.get("metrics"), Mapping)
            else {}
        )
        for metric_key in set(before_metrics).union(after_metrics):
            expected_delta_keys[
                (
                    str(before.get("episode_id") or ""),
                    str(metric_key),
                    str(before.get("context_id") or ""),
                    str(after.get("context_id") or ""),
                )
            ] += 1
    seen_deltas: set[str] = set()
    actual_delta_keys: Counter[tuple[str, str, str, str]] = Counter()
    for index, delta in enumerate(deltas):
        if not isinstance(delta, Mapping):
            findings.append(_finding("blocker", "INVALID_DELTA", f"deltas[{index}] must be an object"))
            continue
        _validate_decimal_value(delta.get("value"), field=f"deltas[{index}].value", findings=findings)
        delta_warning_codes = delta.get("warning_codes")
        if isinstance(delta_warning_codes, list) and delta_warning_codes != sorted(
            set(delta_warning_codes)
        ):
            findings.append(
                _finding(
                    "blocker",
                    "NON_CANONICAL_WARNING_CODES",
                    f"deltas[{index}] warning codes must be sorted and unique",
                )
            )
        delta_id = str(delta.get("delta_id") or "")
        if not delta_id or delta_id in seen_deltas:
            findings.append(
                _finding(
                    "blocker",
                    "INVALID_DELTA_ID",
                    "delta IDs must be non-empty and unique",
                )
            )
        seen_deltas.add(delta_id)
        actual_delta_keys[
            (
                str(delta.get("episode_id") or ""),
                str(delta.get("metric_key") or ""),
                str(delta.get("from_context_id") or ""),
                str(delta.get("to_context_id") or ""),
            )
        ] += 1
        availability = delta.get("availability")
        if availability != "available" and delta.get("value") is not None:
            findings.append(
                _finding(
                    "blocker",
                    "VALUE_FOR_UNAVAILABLE_DELTA",
                    "only an available delta may publish a numeric value",
                )
            )
        if delta.get("method_compatibility") == "incompatible" and delta.get("value") is not None:
            findings.append(_finding("blocker", "INCOMPATIBLE_DELTA_VALUE", "incompatible methods cannot publish a numeric delta"))
        before = context_index.get(str(delta.get("from_context_id") or ""))
        after = context_index.get(str(delta.get("to_context_id") or ""))
        if before is None or after is None:
            findings.append(
                _finding(
                    "blocker",
                    "DANGLING_DELTA_CONTEXT",
                    f"deltas[{index}] references a missing context",
                )
            )
            continue
        if (
            before.get("episode_id") != delta.get("episode_id")
            or after.get("episode_id") != delta.get("episode_id")
        ):
            findings.append(
                _finding(
                    "blocker",
                    "DELTA_EPISODE_MISMATCH",
                    f"deltas[{index}] crosses episode boundaries",
                )
            )
        metric_key = str(delta.get("metric_key") or "")
        before_anchor = (
            before.get("anchor")
            if isinstance(before.get("anchor"), Mapping)
            else {}
        )
        expected_delta_id = _stable_id(
            "delta",
            {
                "episode_id": str(delta.get("episode_id") or ""),
                "event_id": str(before_anchor.get("event_id") or ""),
                "metric_key": metric_key,
                "from": str(delta.get("from_context_id") or ""),
                "to": str(delta.get("to_context_id") or ""),
            },
        )
        if delta_id != expected_delta_id:
            findings.append(
                _finding(
                    "blocker",
                    "DELTA_ID_MISMATCH",
                    f"deltas[{index}] delta_id does not match its canonical identity",
                )
            )
        left = (
            before.get("metrics", {}).get(metric_key)
            if isinstance(before.get("metrics"), Mapping)
            else None
        )
        right = (
            after.get("metrics", {}).get(metric_key)
            if isinstance(after.get("metrics"), Mapping)
            else None
        )
        if isinstance(left, Mapping) and isinstance(right, Mapping):
            same_method = left.get("method") == right.get("method")
            same_unit = left.get("unit") == right.get("unit")
            expected_compatibility = "same" if same_method and same_unit else "incompatible"
            if delta.get("method_compatibility") != expected_compatibility:
                findings.append(
                    _finding(
                        "blocker",
                        "DELTA_METHOD_COMPATIBILITY_MISMATCH",
                        f"deltas[{index}] compatibility does not match endpoint methods",
                    )
                )
            expected_unit = left.get("unit") if same_unit else None
            if delta.get("unit") != expected_unit:
                findings.append(
                    _finding(
                        "blocker",
                        "DELTA_UNIT_MISMATCH",
                        f"deltas[{index}] unit does not match endpoint units",
                    )
                )
            endpoints_available = (
                left.get("availability") == "available"
                and right.get("availability") == "available"
                and left.get("value") is not None
                and right.get("value") is not None
                and same_method
                and same_unit
            )
            if availability == "available":
                if not endpoints_available:
                    findings.append(
                        _finding(
                            "blocker",
                            "DELTA_ENDPOINT_NOT_AVAILABLE",
                            f"deltas[{index}] cannot upgrade partial or missing endpoints",
                        )
                    )
                elif delta.get("value") is not None:
                    expected_value = _decimal_text(
                        _decimal(right["value"], "delta.to")
                        - _decimal(left["value"], "delta.from")
                    )
                    if delta.get("value") != expected_value:
                        findings.append(
                            _finding(
                                "blocker",
                                "DELTA_VALUE_MISMATCH",
                                f"deltas[{index}] does not equal the exact endpoint difference",
                            )
                        )
            elif endpoints_available:
                findings.append(
                    _finding(
                        "blocker",
                        "MISSING_COMPATIBLE_DELTA",
                        f"deltas[{index}] omitted an exact compatible endpoint difference",
                    )
                )
        elif availability == "available":
            findings.append(
                _finding(
                    "blocker",
                    "MISSING_DELTA_METRIC",
                    f"deltas[{index}] lacks one or both endpoint metrics",
                )
            )
    if actual_delta_keys != expected_delta_keys:
        missing_count = sum((expected_delta_keys - actual_delta_keys).values())
        extra_count = sum((actual_delta_keys - expected_delta_keys).values())
        findings.append(
            _finding(
                "blocker",
                "DELTA_COVERAGE_MISMATCH",
                "delta coverage must contain exactly one row for every pre/post "
                f"metric union (missing={missing_count}, extra={extra_count})",
            )
        )
    try:
        expected_deltas = _build_deltas(valid_context_rows)
        if deltas != expected_deltas:
            findings.append(
                _finding(
                    "blocker",
                    "DELTA_DERIVATION_MISMATCH",
                    "deltas must exactly match the deterministic endpoint state machine",
                )
            )
    except (ArtifactIOError, EpisodePortfolioContextError, KeyError, TypeError, ValueError) as exc:
        findings.append(
            _finding(
                "blocker",
                "DELTA_DERIVATION_ERROR",
                f"cannot derive canonical deltas: {exc}",
            )
        )
    nested_warnings = list(artifact.get("warnings", [])) if isinstance(artifact.get("warnings"), list) else []
    has_metric_or_delta_warnings = False
    for context in contexts:
        if isinstance(context, Mapping) and isinstance(context.get("warnings"), list):
            nested_warnings.extend(context["warnings"])
        if isinstance(context, Mapping) and isinstance(context.get("metrics"), Mapping):
            has_metric_or_delta_warnings = has_metric_or_delta_warnings or any(
                isinstance(metric, Mapping) and bool(metric.get("warning_codes"))
                for metric in context["metrics"].values()
            )
    has_metric_or_delta_warnings = has_metric_or_delta_warnings or any(
        isinstance(delta, Mapping) and bool(delta.get("warning_codes"))
        for delta in deltas
    )
    findings = sorted(
        findings,
        key=lambda item: (item["severity"], item["code"], item["message"]),
    )
    severities = {item["severity"] for item in findings}
    if "blocker" in severities:
        status = "blocked"
    elif nested_warnings or has_metric_or_delta_warnings or "warning" in severities:
        status = "accepted_with_warnings"
    else:
        status = "accepted"
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "validation_mode": "offline_structural",
        "validation_status": status,
        "findings": findings,
    }


def replay_validate_episode_portfolio_context(
    artifact: Mapping[str, Any],
    *,
    episode_collection: Mapping[str, Any],
    portfolio_db: str | Path,
) -> dict[str, Any]:
    """Verify a P2E-3 artifact by rebuilding it from the identified read-only sources."""

    structural = validate_episode_portfolio_context(artifact)
    findings = list(structural["findings"])
    rebuilt_content_id: str | None = None
    if structural["validation_status"] != "blocked":
        source_binding = (
            artifact.get("source_binding")
            if isinstance(artifact.get("source_binding"), Mapping)
            else {}
        )
        expected_source_id = "sha256:" + str(
            episode_collection.get("collection_digest") or ""
        )
        if source_binding.get("episode_collection_content_id") != expected_source_id:
            findings.append(
                _finding(
                    "blocker",
                    "SOURCE_COLLECTION_REF_MISMATCH",
                    "supplied P2C collection does not match the artifact source binding",
                )
            )
        else:
            selection = (
                source_binding.get("selection")
                if isinstance(source_binding.get("selection"), Mapping)
                else {}
            )
            requested = selection.get("requested_episode_ids")
            episode_ids = (
                list(requested)
                if selection.get("mode") == "explicit"
                and isinstance(requested, list)
                else None
            )
            try:
                rebuilt = build_episode_portfolio_context(
                    episode_collection,
                    portfolio_db=portfolio_db,
                    as_of=str(artifact.get("as_of") or ""),
                    knowledge_cutoff=str(
                        artifact.get("knowledge_cutoff") or ""
                    ),
                    episode_ids=episode_ids,
                )
                rebuilt_content_id = str(rebuilt.get("content_id") or "")
                if canonical_json_bytes(rebuilt) != canonical_json_bytes(artifact):
                    findings.append(
                        _finding(
                            "blocker",
                            "SOURCE_REPLAY_MISMATCH",
                            "artifact bytes do not match a deterministic rebuild from the supplied sources",
                        )
                    )
            except Exception as exc:
                findings.append(
                    _finding(
                        "blocker",
                        "SOURCE_REPLAY_ERROR",
                        f"source-aware rebuild failed: {exc}",
                    )
                )
    findings = sorted(
        findings,
        key=lambda item: (item["severity"], item["code"], item["message"]),
    )
    status = (
        "blocked"
        if any(item.get("severity") == "blocker" for item in findings)
        else structural["validation_status"]
    )
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "validation_mode": "source_replay",
        "validation_status": status,
        "source_verification": {
            "status": "verified" if status != "blocked" else "mismatch",
            "rebuilt_content_id": rebuilt_content_id,
        },
        "findings": findings,
    }


def save_episode_portfolio_context(
    path: str | Path, artifact: Mapping[str, Any]
) -> Path:
    validation = validate_episode_portfolio_context(artifact)
    if validation["validation_status"] == "blocked":
        raise EpisodePortfolioContextError("refusing to save an invalid P2E-3 artifact")
    try:
        return atomic_write_bytes(path, pretty_json_bytes(artifact))
    except ArtifactIOError as exc:
        raise EpisodePortfolioContextError(str(exc)) from exc


def load_episode_portfolio_context(path: str | Path) -> dict[str, Any]:
    try:
        return load_json_object(path)
    except ArtifactIOError as exc:
        raise EpisodePortfolioContextError(str(exc)) from exc


def query_episode_portfolio_context(
    artifact: Mapping[str, Any],
    *,
    episode_id: str | None = None,
    context_id: str | None = None,
    content_id: str | None = None,
) -> list[dict[str, Any]]:
    if artifact.get("schema_version") != SCHEMA_VERSION:
        raise EpisodePortfolioContextError("unsupported P2E-3 artifact schema")
    if content_id is not None and artifact.get("content_id") != content_id:
        return []
    result = []
    for context in artifact.get("contexts", []):
        if not isinstance(context, Mapping):
            continue
        if episode_id and context.get("episode_id") != episode_id:
            continue
        if context_id and context.get("context_id") != context_id:
            continue
        result.append(deepcopy(dict(context)))
    return result
