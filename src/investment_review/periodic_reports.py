"""Lightweight portfolio and instrument periodic reports.

The implementation reads the formal portfolio database through an immutable,
query-only connection, reuses the canonical accounting and Trade Episode
projection, and stores derived reports only in the selected review sidecar.
Daily reports are the source facts for natural weekly and monthly summaries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence
from zoneinfo import ZoneInfo

from src.portfolio.accounting import build_position_states

from .episodes import build_episode_collection
from .periodic_narrative import (
    build_analysis_brief,
    build_reader_report,
    render_reader_report_markdown,
    validate_periodic_narrative,
)
from .periodic_context import PeriodicContextError, fetch_p1_decision_context


LEGACY_REPORT_SCHEMA_VERSION = "investment_review.periodic_report.v1"
REPORT_SCHEMA_VERSION = "investment_review.periodic_report.v2"
SUPPORTED_REPORT_SCHEMA_VERSIONS = {
    LEGACY_REPORT_SCHEMA_VERSION,
    REPORT_SCHEMA_VERSION,
}
REPORT_API_SCHEMA_VERSION = "investment_review.periodic_reports.api.v1"
PERIODIC_STORE_SCHEMA_VERSION = "1"
SHANGHAI = ZoneInfo("Asia/Shanghai")
ZERO = Decimal("0")

_SUBJECT_TYPES = {"portfolio", "instrument"}
_PERIOD_TYPES = {"daily", "weekly", "monthly"}
_PERIOD_DEPTHS = {
    "daily": "daily_delta_only",
    "weekly": "weekly_synthesis",
    "monthly": "monthly_synthesis",
}
_ACTIONS = {"buy", "sell", "hold", "add", "reduce", "exit"}
_POSITION_EVENT_TYPES = {"BUY", "SELL"}
_CASH_EVENT_TYPES = {"BUY", "SELL", "DIVIDEND", "CASH_FEE"}
_FEE_EXEMPT_RULES = {"online_primary_bond_subscription_fee_exempt_v1"}


class PeriodicReportError(ValueError):
    """Raised when a report input, payload, or sidecar state is invalid."""


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decimal(value: object, *, default: Decimal | None = None) -> Decimal | None:
    if value in (None, ""):
        return default
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PeriodicReportError(f"invalid decimal value: {value!r}") from exc
    if not result.is_finite():
        raise PeriodicReportError(f"non-finite decimal value: {value!r}")
    return result


def _decimal_text(value: Decimal | None, *, places: int | None = None) -> str | None:
    if value is None:
        return None
    if places is not None:
        value = value.quantize(Decimal(1).scaleb(-places))
    if value == ZERO:
        return "0"
    return format(value.normalize(), "f")


def _visible_text(value: object, *, fallback: str = "MISSING") -> str:
    return fallback if value is None or value == "" else str(value)


def _pct(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator in (None, ZERO):
        return None
    return numerator / denominator * Decimal("100")


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _aware_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PeriodicReportError(f"invalid timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PeriodicReportError(f"timestamp must include timezone: {value!r}")
    return parsed


def _parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise PeriodicReportError(f"invalid report date: {value!r}") from exc


def _event_time(row: Mapping[str, Any]) -> datetime:
    event_date = str(row.get("event_date") or "")
    event_time = str(row.get("event_time") or "00:00:00")
    try:
        local = datetime.fromisoformat(f"{event_date}T{event_time}")
    except ValueError as exc:
        raise PeriodicReportError(
            f"invalid ledger event timestamp: {event_date} {event_time}"
        ) from exc
    return local.replace(tzinfo=SHANGHAI).astimezone(timezone.utc)


def _report_cutoff(day: date) -> datetime:
    return datetime.combine(day, time(15, 0), tzinfo=SHANGHAI)


def _attach_reader_narrative(report: dict[str, Any]) -> None:
    analysis_brief = build_analysis_brief(report)
    reader_report = build_reader_report(
        report,
        analysis_brief=analysis_brief,
    )
    report["analysis_brief"] = analysis_brief
    report["reader_report"] = reader_report
    report["headline"] = reader_report["central_judgment"]


def upgrade_periodic_report_v2(
    report: Mapping[str, Any],
) -> dict[str, Any]:
    """Upgrade a valid V1 payload without changing its structured facts."""

    original = deepcopy(dict(report))
    validation = validate_periodic_report(original)
    if validation["status"] != "accepted":
        raise PeriodicReportError(
            "cannot upgrade invalid periodic report: "
            + ", ".join(validation["errors"])
        )
    if original.get("schema_version") == REPORT_SCHEMA_VERSION:
        return original
    legacy_report_id = str(original.get("report_id") or "")
    subject = (
        original.get("subject")
        if isinstance(original.get("subject"), Mapping)
        else {}
    )
    period = (
        original.get("period")
        if isinstance(original.get("period"), Mapping)
        else {}
    )
    identity = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "subject_type": subject.get("type"),
        "subject_id": subject.get("id"),
        "period_type": period.get("type"),
        "period_start": period.get("start"),
        "period_end": period.get("end"),
    }
    original["schema_version"] = REPORT_SCHEMA_VERSION
    original["report_id"] = (
        "periodic_" + _sha256_text(_canonical_json(identity))[:32]
    )
    original.pop("analysis_brief", None)
    original.pop("reader_report", None)
    original.pop("content_id", None)
    source = dict(
        original.get("source")
        if isinstance(original.get("source"), Mapping)
        else {}
    )
    source["upgraded_from"] = {
        "schema_version": LEGACY_REPORT_SCHEMA_VERSION,
        "report_id": legacy_report_id,
        "structured_facts_changed": False,
    }
    original["source"] = source
    _attach_reader_narrative(original)
    original["content_id"] = "sha256:" + _sha256_text(
        _canonical_json(original)
    )
    validation = validate_periodic_report(original)
    if validation["status"] != "accepted":
        raise PeriodicReportError(
            "upgraded periodic report validation failed: "
            + ", ".join(validation["errors"])
        )
    return original


@contextmanager
def _read_only_connection(path: str | Path) -> Iterator[sqlite3.Connection]:
    selected = Path(path).expanduser().resolve(strict=True)
    if not selected.is_file():
        raise PeriodicReportError(f"database does not exist: {selected}")
    connection = sqlite3.connect(
        selected.as_uri() + "?mode=ro&immutable=1",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    try:
        yield connection
    finally:
        connection.close()


def _ledger_rows(
    connection: sqlite3.Connection,
    *,
    account_id: str,
    through: date,
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            """
            SELECT l.*, b.broker AS import_broker,
                   b.source_name AS import_source_name,
                   b.source_sha256 AS import_source_sha256
            FROM ledger_entries AS l
            LEFT JOIN import_batches AS b
              ON b.batch_id = l.import_batch_id
            WHERE l.account_id = ? AND l.event_date <= ?
            ORDER BY l.event_date, COALESCE(l.event_time, ''), l.entry_id
            """,
            (account_id, through.isoformat()),
        )
    ]


def _note_fields(note: object) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in str(note or "").split(";"):
        key, separator, value = part.strip().partition("=")
        if separator and key.strip():
            fields[key.strip().lower()] = value.strip()
    return fields


def _fee_provenance(row: Mapping[str, Any]) -> dict[str, Any]:
    """Classify fee evidence without treating estimates as broker actuals."""

    note = str(row.get("note") or "")
    note_lower = note.lower()
    fields = _note_fields(note)
    fee_value = _decimal(row.get("fees"), default=ZERO) or ZERO
    fee_rule = fields.get("fee_rule")
    fee_source = fields.get("fee_source", "").lower()
    effective_fee_source = fee_source or "unknown"
    if fee_source == "formal_exemption" or fee_rule in _FEE_EXEMPT_RULES:
        status = "formal_exemption"
        effective_fee_source = "formal_exemption"
    elif (
        fee_source == "rule_derived"
        or fields.get("fee_backfilled_rule", "").lower() == "true"
        or (fee_rule is not None and fee_rule not in _FEE_EXEMPT_RULES)
    ):
        status = "rule_backfilled"
        effective_fee_source = "rule_derived"
    elif (
        fee_source == "broker_actual"
        or fields.get("fees_inferred_from_net_amount", "").lower() == "true"
        or "fee_backfilled_exact=" in note_lower
    ):
        status = "reported_actual"
        effective_fee_source = "broker_actual"
    elif any(
        marker in note_lower
        for marker in ("fee_pending", "fees_missing=true", "missing_source_column")
    ):
        status = "unknown"
    else:
        status = "unknown"
    return {
        "amount_cny": _decimal_text(fee_value, places=2),
        "status": status,
        "fee_rule": fee_rule,
        "fee_source": effective_fee_source,
        "is_known": status != "unknown",
        "note_ref": (
            f"fee_rule={fee_rule}" if fee_rule else "ledger note has no fee rule"
        ),
    }


def _cash_delta(rows: Sequence[Mapping[str, Any]]) -> tuple[Decimal, int]:
    change = ZERO
    unknown_fee_entries = 0
    for row in rows:
        event_type = str(row.get("event_type") or "").upper()
        gross = _decimal(row.get("gross_amount"), default=ZERO) or ZERO
        fees = _decimal(row.get("fees"), default=ZERO) or ZERO
        cash_amount = _decimal(row.get("cash_amount"), default=ZERO) or ZERO
        if event_type == "BUY":
            change -= gross + fees
        elif event_type == "SELL":
            change += gross - fees
        elif event_type == "DIVIDEND":
            change += cash_amount
        elif event_type == "CASH_FEE":
            change -= cash_amount
        if event_type in _POSITION_EVENT_TYPES and not _fee_provenance(row)["is_known"]:
            unknown_fee_entries += 1
    return change, unknown_fee_entries


def _cash_snapshot(
    connection: sqlite3.Connection,
    *,
    account_id: str,
    through: date,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT snapshot_id, as_of_date, amount, source, note, recorded_at
        FROM cash_balance_snapshots
        WHERE account_id = ? AND as_of_date <= ?
        ORDER BY as_of_date DESC, recorded_at DESC, snapshot_id DESC
        LIMIT 1
        """,
        (account_id, through.isoformat()),
    ).fetchone()
    if row is None:
        return None
    note = str(row["note"] or "")
    fee_pending = "fee_pending" in note or "fees_missing" in note
    if fee_pending:
        anchor = connection.execute(
            """
            SELECT snapshot_id, as_of_date, amount, source, note, recorded_at
            FROM cash_balance_snapshots
            WHERE account_id = ? AND as_of_date <= ?
              AND source <> 'statement_calculated'
            ORDER BY as_of_date DESC, recorded_at DESC, snapshot_id DESC
            LIMIT 1
            """,
            (account_id, through.isoformat()),
        ).fetchone()
        if anchor is not None:
            replay_rows = [
                dict(item)
                for item in connection.execute(
                    """
                    SELECT *
                    FROM ledger_entries
                    WHERE account_id = ?
                      AND event_date > ?
                      AND event_date <= ?
                      AND event_type IN ('BUY', 'SELL', 'DIVIDEND', 'CASH_FEE')
                    ORDER BY event_date,
                      CASE WHEN event_time = '' THEN '99:99:99' ELSE event_time END,
                      entry_id
                    """,
                    (
                        account_id,
                        anchor["as_of_date"],
                        through.isoformat(),
                    ),
                )
            ]
            change, unknown_fee_entries = _cash_delta(replay_rows)
            amount = (_decimal(anchor["amount"], default=ZERO) or ZERO) + change
            replay_complete = unknown_fee_entries == 0
            return {
                "amount_cny": _decimal_text(amount, places=2),
                "as_of_date": (
                    max(
                        (str(item.get("event_date") or "") for item in replay_rows),
                        default=str(anchor["as_of_date"]),
                    )
                ),
                "source": "derived_read_only_ledger_replay",
                "status": "fact" if replay_complete else "LOW_CONFIDENCE",
                "fee_pending": not replay_complete,
                "fee_provenance_status": (
                    "complete" if replay_complete else "contains_unknown"
                ),
                "consistency_status": "replayed_from_anchor",
                "cash_change_from_anchor_cny": _decimal_text(change, places=2),
                "anchor": {
                    "amount_cny": _decimal_text(
                        _decimal(anchor["amount"]), places=2
                    ),
                    "as_of_date": anchor["as_of_date"],
                    "source": anchor["source"],
                    "source_ref": (
                        "portfolio.sqlite3#cash_balance_snapshots:"
                        f"{anchor['snapshot_id']}"
                    ),
                },
                "superseded_snapshot": {
                    "amount_cny": _decimal_text(_decimal(row["amount"]), places=2),
                    "as_of_date": row["as_of_date"],
                    "note": note,
                    "source_ref": (
                        "portfolio.sqlite3#cash_balance_snapshots:"
                        f"{row['snapshot_id']}"
                    ),
                },
                "replayed_ledger_entries": len(replay_rows),
                "unknown_fee_entries": unknown_fee_entries,
                "recorded_at": max(
                    str(row["recorded_at"] or ""),
                    str(anchor["recorded_at"] or ""),
                ),
                "source_ref": (
                    "portfolio.sqlite3#cash_balance_snapshots:"
                    f"{anchor['snapshot_id']}+ledger_entries:"
                    f"through:{through.isoformat()}"
                ),
            }
    return {
        "amount_cny": _decimal_text(_decimal(row["amount"]), places=2),
        "as_of_date": row["as_of_date"],
        "source": row["source"],
        "status": "LOW_CONFIDENCE" if fee_pending else "fact",
        "fee_pending": fee_pending,
        "fee_provenance_status": "contains_unknown" if fee_pending else "complete",
        "consistency_status": "snapshot_direct",
        "note": note,
        "recorded_at": row["recorded_at"],
        "source_ref": f"portfolio.sqlite3#cash_balance_snapshots:{row['snapshot_id']}",
    }


def _price_row(
    connection: sqlite3.Connection,
    *,
    ts_code: str,
    through: date,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT observation_id, trade_date, close, pre_close, pct_chg,
               source, fetched_at
        FROM close_prices
        WHERE ts_code = ? AND trade_date <= ?
        ORDER BY trade_date DESC, fetched_at DESC, observation_id DESC
        LIMIT 1
        """,
        (ts_code, through.isoformat()),
    ).fetchone()
    return dict(row) if row is not None else None


def _prior_closes(
    connection: sqlite3.Connection,
    *,
    ts_code: str,
    before: date,
    limit: int = 6,
) -> list[dict[str, Any]]:
    return [
        {
            "trade_date": row["trade_date"],
            "close": row["close"],
            "pre_close": row["pre_close"],
            "pct_chg": row["pct_chg"],
            "source": row["source"],
            "fetched_at": row["fetched_at"],
            "source_ref": (
                "portfolio.sqlite3#close_prices:"
                f"{ts_code}:{row['trade_date']}:{row['observation_id']}"
            ),
        }
        for row in connection.execute(
            """
            SELECT observation_id, trade_date, close, pre_close, pct_chg,
                   source, fetched_at
            FROM close_prices
            WHERE ts_code = ? AND trade_date < ?
            ORDER BY trade_date DESC, fetched_at DESC, observation_id DESC
            LIMIT ?
            """,
            (ts_code, before.isoformat(), limit),
        )
    ]


def _portfolio_snapshot(
    connection: sqlite3.Connection,
    *,
    account_id: str,
    as_of: date,
) -> dict[str, Any]:
    ledger = _ledger_rows(connection, account_id=account_id, through=as_of)
    states = build_position_states(ledger)
    positions: list[dict[str, Any]] = []
    observed_times = [
        str(row.get("created_at") or "") for row in ledger if row.get("created_at")
    ]
    for ts_code, state in sorted(states.items()):
        if state.quantity <= ZERO:
            continue
        instrument = connection.execute(
            """
            SELECT name, asset_type, industry_name, industry_source
            FROM instruments WHERE ts_code = ?
            """,
            (ts_code,),
        ).fetchone()
        price = _price_row(connection, ts_code=ts_code, through=as_of)
        close = _decimal(price["close"]) if price is not None else None
        market_value = close * state.quantity if close is not None else None
        unrealized = (
            market_value - state.remaining_cost if market_value is not None else None
        )
        if price is not None and price.get("fetched_at"):
            observed_times.append(str(price["fetched_at"]))
        positions.append(
            {
                "ts_code": ts_code,
                "name": instrument["name"] if instrument is not None else ts_code,
                "asset_type": (
                    instrument["asset_type"] if instrument is not None else "unknown"
                ),
                "industry_name": (
                    instrument["industry_name"]
                    if instrument is not None and instrument["industry_name"]
                    else "MISSING"
                ),
                "quantity": _decimal_text(state.quantity),
                "average_cost_cny": _decimal_text(state.average_cost, places=4),
                "remaining_cost_cny": _decimal_text(
                    state.remaining_cost, places=2
                ),
                "close_cny": _decimal_text(close, places=4),
                "price_date": price["trade_date"] if price is not None else None,
                "price_source": price["source"] if price is not None else None,
                "market_value_cny": _decimal_text(market_value, places=2),
                "unrealized_pnl_cny": _decimal_text(unrealized, places=2),
                "unrealized_return_pct": _decimal_text(
                    _pct(unrealized, state.remaining_cost), places=2
                ),
                "realized_pnl_to_date_cny": _decimal_text(
                    state.realized_pnl, places=2
                ),
                "source_refs": [
                    f"portfolio.sqlite3#ledger_entries:{ts_code}:through:{as_of.isoformat()}",
                    (
                        "portfolio.sqlite3#close_prices:"
                        f"{ts_code}:{price['trade_date']}"
                        if price is not None
                        else "TODO_PRICE"
                    ),
                ],
            }
        )

    priced = [
        _decimal(item["market_value_cny"])
        for item in positions
        if item["market_value_cny"] is not None
    ]
    missing_prices = [
        item["ts_code"] for item in positions if item["market_value_cny"] is None
    ]
    market_value = sum((value or ZERO for value in priced), ZERO)
    cash = _cash_snapshot(connection, account_id=account_id, through=as_of)
    cash_value = _decimal(cash["amount_cny"]) if cash is not None else None
    if cash is not None and cash.get("recorded_at"):
        observed_times.append(str(cash["recorded_at"]))
    total_assets = (
        market_value + cash_value
        if not missing_prices and cash_value is not None
        else None
    )
    for position in positions:
        position["portfolio_weight_pct"] = _decimal_text(
            _pct(_decimal(position["market_value_cny"]), total_assets),
            places=2,
        )
    positions.sort(
        key=lambda item: _decimal(item["market_value_cny"], default=ZERO) or ZERO,
        reverse=True,
    )
    realized = sum((state.realized_pnl for state in states.values()), ZERO)
    cash_weight = _pct(cash_value, total_assets)
    top_weight = (
        _decimal(positions[0]["portfolio_weight_pct"], default=ZERO)
        if positions
        else ZERO
    )
    top3_weight = sum(
        (
            _decimal(item["portfolio_weight_pct"], default=ZERO) or ZERO
            for item in positions[:3]
        ),
        ZERO,
    )
    return {
        "as_of_date": as_of.isoformat(),
        "account_id": account_id,
        "positions": positions,
        "position_count": len(positions),
        "market_value_cny": _decimal_text(
            market_value if not missing_prices else None, places=2
        ),
        "cash": cash,
        "cash_weight_pct": _decimal_text(cash_weight, places=2),
        "total_assets_cny": _decimal_text(total_assets, places=2),
        "realized_pnl_to_date_cny": _decimal_text(realized, places=2),
        "missing_prices": missing_prices,
        "top_position_weight_pct": _decimal_text(top_weight, places=2),
        "top3_weight_pct": _decimal_text(top3_weight, places=2),
        "source_observed_through": max(observed_times, default=None),
    }


def _previous_market_date(
    connection: sqlite3.Connection,
    *,
    report_date: date,
) -> date | None:
    row = connection.execute(
        "SELECT MAX(trade_date) FROM close_prices WHERE trade_date < ?",
        (report_date.isoformat(),),
    ).fetchone()
    return date.fromisoformat(row[0]) if row is not None and row[0] else None


def _local_decision_context(
    connection: sqlite3.Connection,
    *,
    ts_code: str,
    name: str,
    industry_name: str,
    report_date: date,
) -> dict[str, Any]:
    """Build a deterministic fallback from facts already in the formal DB."""

    rows = [
        dict(row)
        for row in connection.execute(
            """
            WITH ranked AS (
                SELECT trade_date, close, pre_close, pct_chg, source, fetched_at,
                       observation_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY trade_date
                           ORDER BY fetched_at DESC, observation_id DESC
                       ) AS rank_in_day
                FROM close_prices
                WHERE ts_code = ? AND trade_date <= ?
            )
            SELECT trade_date, close, pre_close, pct_chg, source, fetched_at,
                   observation_id
            FROM ranked
            WHERE rank_in_day = 1
            ORDER BY trade_date DESC
            LIMIT 25
            """,
            (ts_code, report_date.isoformat()),
        )
    ]
    rows.reverse()
    latest = rows[-1] if rows else None
    closes = [_decimal(row.get("close")) for row in rows]
    latest_close = closes[-1] if closes else None

    def session_return(sessions: int) -> str | None:
        if len(closes) <= sessions or latest_close is None:
            return None
        return _decimal_text(
            _pct(
                latest_close - (closes[-sessions - 1] or ZERO),
                closes[-sessions - 1],
            ),
            places=2,
        )

    technical_metrics = {
        "trade_date": latest.get("trade_date") if latest else None,
        "close_cny": _decimal_text(latest_close, places=4),
        "return_3_session_pct": session_return(3),
        "return_5_session_pct": session_return(5),
        "return_20_session_pct": session_return(20),
        "volume_vs_prior_5d_avg": None,
        "day_open_cny": None,
        "day_high_cny": None,
        "day_low_cny": None,
    }
    return_3 = technical_metrics["return_3_session_pct"] or "MISSING"
    return_5 = technical_metrics["return_5_session_pct"] or "MISSING"
    return_20 = technical_metrics["return_20_session_pct"] or "MISSING"
    technical_summary = (
        "截至报告日，正式行情中的 3/5/20 个交易日涨跌幅分别为 "
        f"{return_3}%/{return_5}%/{return_20}%；"
        "成交量与日内高低价不在该轻量回退数据中。"
        if latest
        else "正式组合库没有报告日及之前的可用收盘价，无法形成趋势判断。"
    )
    day_change = _decimal_text(
        _decimal(latest.get("pct_chg")) if latest else None,
        places=2,
    )
    visible_day_change = day_change or "MISSING"
    fetched_at = max(
        (str(row.get("fetched_at") or "") for row in rows),
        default=_report_cutoff(report_date).astimezone(timezone.utc).isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z"),
    )
    price_ref = (
        "portfolio.sqlite3#close_prices:"
        f"{ts_code}:{latest['trade_date']}:{latest['observation_id']}"
        if latest
        else "TODO_PRICE"
    )
    return {
        "schema_version": "investment_review.periodic_context.v1",
        "subject": {
            "ts_code": ts_code,
            "name": name,
            "industry_name": industry_name or "MISSING",
        },
        "as_of": report_date.isoformat(),
        "fetched_at": fetched_at,
        "provider": "formal_portfolio_read_only_fallback",
        "fundamental_and_valuation": {
            "status": "missing",
            "scope": "latest_public_snapshot_before_report_cutoff",
            "summary": (
                "正式组合库不保存财务与估值快照；本日报未用常识或未来披露"
                "补造基本面结论，需在标的研究证据可用后补充。"
            ),
            "metrics": {},
            "valuation": {},
            "observations": [],
            "source_refs": [],
        },
        "market_and_sector": {
            "status": "partial" if latest else "missing",
            "scope": "report_day_delta",
            "summary": (
                f"标的当日涨跌幅 {visible_day_change}%；正式组合库未保存同日基准和"
                "板块指数，因此不做大盘/板块归因。"
                if latest
                else "缺少标的、基准和板块的报告日行情，无法归因。"
            ),
            "stock_change_pct": day_change,
            "benchmarks": [],
            "sector": None,
            "observations": (
                [
                    {
                        "type": "fact",
                        "text": f"标的当日涨跌幅 {visible_day_change}%。",
                        "timing": "end_of_day_retrospective",
                        "source_ref": price_ref,
                    }
                ]
                if latest
                else []
            ),
            "source_refs": [price_ref] if latest else [],
        },
        "technical_and_trend": {
            "status": "available" if latest else "missing",
            "scope": "report_cutoff_technical_delta",
            "summary": technical_summary,
            "metrics": technical_metrics,
            "observations": [],
            "source_refs": [price_ref] if latest else [],
        },
        "intraday_bars": [],
        "timing_policy": (
            "local fallback contains report-cutoff or earlier facts only; "
            "no intraday observation is inferred"
        ),
    }


def _aggregate_portfolio_daily_context(
    contexts: Mapping[str, Mapping[str, Any]],
    *,
    report_date: date,
) -> dict[str, Any]:
    """Summarize per-instrument contexts without pretending full research coverage."""

    ordered = [
        (code, contexts[code])
        for code in sorted(contexts)
        if isinstance(contexts.get(code), Mapping)
    ]
    names = {
        code: str(context.get("subject", {}).get("name") or code)
        for code, context in ordered
    }

    def layer_status(layer_name: str) -> tuple[str, int]:
        statuses = [
            str(context.get(layer_name, {}).get("status") or "missing")
            for _, context in ordered
        ]
        available = sum(status in {"available", "partial"} for status in statuses)
        if available == len(statuses) and statuses:
            return "available", available
        if available:
            return "partial", available
        return "missing", 0

    fundamental_status, fundamental_covered = layer_status(
        "fundamental_and_valuation"
    )
    market_status, market_covered = layer_status("market_and_sector")
    technical_status, technical_covered = layer_status("technical_and_trend")
    changes = [
        _decimal(context.get("market_and_sector", {}).get("stock_change_pct"))
        for _, context in ordered
    ]
    positive = sum(value is not None and value > ZERO for value in changes)
    negative = sum(value is not None and value < ZERO for value in changes)
    flat = sum(value == ZERO for value in changes if value is not None)
    trend20 = [
        _decimal(
            context.get("technical_and_trend", {})
            .get("metrics", {})
            .get("return_20_session_pct")
        )
        for _, context in ordered
    ]
    trend_positive = sum(value is not None and value > ZERO for value in trend20)
    trend_negative = sum(value is not None and value < ZERO for value in trend20)

    def combined_refs(layer_name: str) -> list[str]:
        return sorted(
            {
                str(ref)
                for _, context in ordered
                for ref in context.get(layer_name, {}).get("source_refs", [])
                if ref
            }
        )

    fetched_at = max(
        (str(context.get("fetched_at") or "") for _, context in ordered),
        default=_report_cutoff(report_date).astimezone(timezone.utc).isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z"),
    )
    covered_names = [names[code] for code, _ in ordered]
    return {
        "schema_version": "investment_review.periodic_context.v1",
        "subject": {
            "type": "portfolio",
            "ts_code": "",
            "name": "组合账户",
            "covered_instruments": covered_names,
        },
        "as_of": report_date.isoformat(),
        "fetched_at": fetched_at,
        "provider": "portfolio_context_aggregation",
        "fundamental_and_valuation": {
            "status": fundamental_status,
            "scope": "daily_held_and_traded_instruments",
            "summary": (
                f"本日报覆盖 {len(ordered)} 个持有或当日交易标的，其中 "
                f"{fundamental_covered} 个取得可核对的基本面/估值上下文；"
                "详细事实保留在对应标的日报，组合层不冒充完整个股研究。"
            ),
            "observations": [],
            "source_refs": combined_refs("fundamental_and_valuation"),
        },
        "market_and_sector": {
            "status": market_status,
            "scope": "daily_held_and_traded_instruments",
            "summary": (
                f"报告日可核对 {market_covered}/{len(ordered)} 个标的的市场上下文；"
                f"其中上涨 {positive}、下跌 {negative}、持平 {flat}。"
                "缺少基准或板块时不做强行归因。"
            ),
            "observations": [],
            "source_refs": combined_refs("market_and_sector"),
        },
        "technical_and_trend": {
            "status": technical_status,
            "scope": "daily_held_and_traded_instruments",
            "summary": (
                f"报告日可核对 {technical_covered}/{len(ordered)} 个标的的趋势；"
                f"20 个交易日趋势为正 {trend_positive}、为负 {trend_negative}，"
                "其余数据不足。"
            ),
            "observations": [],
            "source_refs": combined_refs("technical_and_trend"),
        },
        "instrument_contexts": {code: dict(context) for code, context in ordered},
        "intraday_bars": [],
        "timing_policy": (
            "each operation may consume only its own instrument context available "
            "no later than the operation; end-of-day aggregates are retrospective"
        ),
    }


def _event_id(row: Mapping[str, Any]) -> str:
    material = f"portfolio-ledger:{row.get('account_id')}:{row.get('entry_id')}"
    return "evt_periodic_" + _sha256_text(material)[:32]


def _source_record_id(row: Mapping[str, Any]) -> str:
    external_id = str(row.get("external_id") or "").strip()
    if external_id:
        return f"{row.get('account_id')}::{external_id}"
    return f"ledger_entries:{row.get('entry_id')}"


def _projection_event(row: Mapping[str, Any]) -> dict[str, Any]:
    occurred_at = _event_time(row)
    event_type = str(row.get("event_type") or "").upper()
    side = event_type if event_type in _POSITION_EVENT_TYPES else "OTHER"
    raw_source = {
        key: row.get(key)
        for key in (
            "entry_id",
            "account_id",
            "external_id",
            "dedupe_key",
            "source_row",
            "created_at",
            "note",
        )
    }
    payload_hash = _sha256_text(_canonical_json(dict(row)))
    return {
        "event_id": _event_id(row),
        "source_id": "formal_portfolio_sqlite",
        "source_record_id": _source_record_id(row),
        "payload_sha256": payload_hash,
        "event_type": event_type.lower(),
        "occurred_at": _iso_utc(occurred_at),
        # The operation fact becomes available at execution time.  The later
        # source import timestamp remains visible in raw_payload.source_row.
        "known_at": _iso_utc(occurred_at),
        "account": str(row.get("account_id") or ""),
        "market": (
            str(row.get("ts_code") or "").rsplit(".", 1)[1]
            if "." in str(row.get("ts_code") or "")
            else None
        ),
        "symbol": str(row.get("ts_code") or ""),
        "side": side,
        "quantity": str(row.get("quantity") or "0"),
        "currency": "CNY",
        "raw_payload": {"source_row": raw_source},
        "decision_refs": [],
    }


def _episode_transition_index(
    ledger: Sequence[Mapping[str, Any]],
    *,
    cutoff_at: datetime,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    collection = build_episode_collection(
        [_projection_event(row) for row in ledger],
        cutoff_at=cutoff_at.isoformat(),
    )
    index: dict[str, dict[str, Any]] = {}
    for episode in collection.get("episodes", []):
        for event_ref in episode.get("event_refs", []):
            index[str(event_ref.get("event_id") or "")] = {
                "episode_id": episode.get("episode_id"),
                "episode_status": episode.get("status"),
                "quantity_before": event_ref.get("quantity_before"),
                "quantity_after": event_ref.get("quantity_after"),
                "signed_quantity": event_ref.get("signed_quantity"),
            }
    return index, collection


def _decision_links(
    review_db: str | Path | None,
    operations: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    result = {_event_id(row): [] for row in operations}
    if review_db is None or not Path(review_db).is_file() or not operations:
        return result
    record_ids = {_source_record_id(row): _event_id(row) for row in operations}
    placeholders = ",".join("?" for _ in record_ids)
    try:
        with _read_only_connection(review_db) as connection:
            table = connection.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type='table' AND name='decision_event_links'
                """
            ).fetchone()
            if table is None:
                return result
            rows = connection.execute(
                f"""
                SELECT te.source_record_id, d.decision_id, d.occurred_at,
                       d.known_at, d.status, d.thesis, d.direct_reason,
                       d.trigger_text, d.invalidation_text, d.risk_notes,
                       l.relation
                FROM trade_events AS te
                JOIN decision_event_links AS l ON l.event_id = te.event_id
                JOIN decisions AS d ON d.decision_id = l.decision_id
                WHERE te.source_record_id IN ({placeholders})
                ORDER BY d.known_at, d.decision_id
                """,
                tuple(record_ids),
            )
            for row in rows:
                result[record_ids[str(row["source_record_id"])]].append(dict(row))
    except sqlite3.Error as exc:
        raise PeriodicReportError("review sidecar decision lookup failed") from exc
    return result


def _operation_role(operation: Mapping[str, Any]) -> str:
    side = str(operation.get("side") or "")
    before = _decimal(operation.get("quantity_before"), default=ZERO) or ZERO
    after = _decimal(operation.get("quantity_after"), default=ZERO) or ZERO
    if side == "BUY":
        return "open" if before == ZERO else "add"
    if side == "SELL":
        return "exit" if after == ZERO else "reduce"
    return "cash_or_non_position"


def _intraday_context_at(
    operation: Mapping[str, Any],
    intraday_bars: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any] | None:
    if not intraday_bars:
        return None
    cutoff = _aware_timestamp(str(operation.get("occurred_at") or ""))
    completed: list[tuple[datetime, Mapping[str, Any]]] = []
    for bar in intraday_bars:
        value = str(bar.get("bar_end_at") or "")
        if not value:
            continue
        bar_time = _aware_timestamp(value)
        if bar_time <= cutoff:
            completed.append((bar_time, bar))
    if not completed:
        return None
    _, selected = max(completed, key=lambda item: item[0])
    return dict(selected)


def infer_motive_hypothesis(
    operation: Mapping[str, Any],
    *,
    earlier_operations: Sequence[Mapping[str, Any]],
    prior_closes: Sequence[Mapping[str, Any]],
    position_weight_before_pct: str | None,
    intraday_bars: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Infer one motive using only inputs available by this operation."""

    occurred_at = str(operation.get("occurred_at") or "")
    role = _operation_role(operation)
    side = str(operation.get("side") or "")
    price = _decimal(operation.get("price_cny"))
    quantity = _decimal(operation.get("quantity"), default=ZERO) or ZERO
    quantity_before = (
        _decimal(operation.get("quantity_before"), default=ZERO) or ZERO
    )
    quantity_after = (
        _decimal(operation.get("quantity_after"), default=ZERO) or ZERO
    )
    position_change_pct = _pct(quantity, quantity_before)
    previous_close = (
        _decimal(prior_closes[0].get("close")) if prior_closes else None
    )
    prior_return = None
    if len(prior_closes) >= 3:
        latest = _decimal(prior_closes[0].get("close"))
        oldest = _decimal(prior_closes[min(2, len(prior_closes) - 1)].get("close"))
        prior_return = _pct(
            latest - oldest if latest is not None and oldest is not None else None,
            oldest,
        )
    trade_vs_prior = _pct(
        price - previous_close
        if price is not None and previous_close is not None
        else None,
        previous_close,
    )
    earlier_same_instrument = [
        item
        for item in earlier_operations
        if item.get("ts_code") == operation.get("ts_code")
        and str(item.get("occurred_at") or "") <= occurred_at
    ]
    earlier_buys = sum(
        (
            _decimal(item.get("quantity"), default=ZERO) or ZERO
            for item in earlier_same_instrument
            if item.get("side") == "BUY"
        ),
        ZERO,
    )
    earlier_buy_operations = [
        item for item in earlier_same_instrument if item.get("side") == "BUY"
    ]
    latest_completed_bar = _intraday_context_at(operation, intraday_bars)
    bar_high = (
        _decimal(latest_completed_bar.get("high_cny"))
        if latest_completed_bar
        else None
    )
    trade_vs_bar_high = _pct(
        price - bar_high if price is not None and bar_high is not None else None,
        bar_high,
    )

    observations = [
        {
            "type": "fact",
            "text": (
                f"{role} {operation.get('quantity')} 股，成交价 "
                f"{operation.get('price_cny')} 元"
            ),
            "source_ref": operation.get("source_ref"),
            "observed_at": occurred_at,
        }
    ]
    if position_change_pct is not None:
        observations.append(
            {
                "type": "fact",
                "text": (
                    f"本笔数量相当于操作前持仓的 "
                    f"{_decimal_text(position_change_pct, places=2)}%"
                ),
                "source_ref": operation.get("source_ref"),
                "observed_at": occurred_at,
            }
        )
    if previous_close is not None:
        observations.append(
            {
                "type": "fact",
                "text": (
                    f"操作前最近收盘价 {prior_closes[0].get('close')} 元，"
                    f"成交价相对其变动 {_decimal_text(trade_vs_prior, places=2)}%"
                ),
                "source_ref": prior_closes[0].get("source_ref"),
                "observed_at": (
                    f"{prior_closes[0].get('trade_date')}T15:00:00+08:00"
                ),
            }
        )
    if earlier_same_instrument:
        observations.append(
            {
                "type": "fact",
                "text": f"本次操作前同日已有 {len(earlier_same_instrument)} 笔该标的操作",
                "source_ref": ",".join(
                    str(item.get("source_ref") or "")
                    for item in earlier_same_instrument
                ),
                "observed_at": occurred_at,
            }
        )
    if latest_completed_bar is not None:
        observations.append(
            {
                "type": "fact",
                "text": (
                    f"操作前最近一根已完成 5 分钟 K 线截至 "
                    f"{latest_completed_bar.get('bar_end_at')}："
                    f"高 {latest_completed_bar.get('high_cny')} 元、"
                    f"收 {latest_completed_bar.get('close_cny')} 元；"
                    f"成交价相对该高点 "
                    f"{_decimal_text(trade_vs_bar_high, places=2)}%"
                ),
                "source_ref": latest_completed_bar.get("source_ref"),
                "observed_at": _iso_utc(
                    _aware_timestamp(
                        str(latest_completed_bar.get("bar_end_at") or "")
                    )
                ),
            }
        )
    if position_weight_before_pct is not None:
        observations.append(
            {
                "type": "estimate",
                "text": f"按上一收盘估算，操作前组合权重约 {position_weight_before_pct}%",
                "source_ref": "portfolio.sqlite3#ledger_entries+close_prices",
                "observed_at": occurred_at,
            }
        )

    trend_up = prior_return is not None and prior_return > Decimal("1")
    if side == "BUY":
        if earlier_buy_operations:
            previous_buy = earlier_buy_operations[-1]
            previous_buy_quantity = (
                _decimal(previous_buy.get("quantity"), default=ZERO) or ZERO
            )
            previous_buy_price = _decimal(previous_buy.get("price_cny"))
            size_multiple = (
                quantity / previous_buy_quantity
                if previous_buy_quantity > ZERO
                else None
            )
            price_step = _pct(
                price - previous_buy_price
                if price is not None and previous_buy_price is not None
                else None,
                previous_buy_price,
            )
            size_multiple_text = _visible_text(
                _decimal_text(size_multiple, places=2)
            )
            price_step_text = _visible_text(
                _decimal_text(price_step, places=2)
            )
            if (
                size_multiple is not None
                and size_multiple > Decimal("1")
                and price_step is not None
                and price_step > ZERO
            ):
                motive = (
                    "系统推断：在前一笔买入后，本笔加仓规模约为前笔的 "
                    f"{size_multiple_text} 倍，成交价又提高 "
                    f"{price_step_text}%；"
                    "更像是在看到盘中强势后放大试仓。规模随价格上升而扩大，"
                    "执行上带有追高风险，但这不是用户已记录动机。"
                )
            elif size_multiple is not None and size_multiple <= Decimal("1"):
                motive = (
                    "系统推断：本笔延续同日买入，但规模缩小为前笔的 "
                    f"{size_multiple_text} 倍、成交价变化 "
                    f"{price_step_text}%；"
                    "更像控制加仓节奏或继续拆单，不能据此声称用户在放大判断。"
                )
            else:
                motive = (
                    "系统推断：本笔延续同日买入，规模约为前笔的 "
                    f"{size_multiple_text} 倍、成交价变化 "
                    f"{price_step_text}%；"
                    "更像分批补仓或执行既定数量，而非顺价追高。"
                )
            alternative = (
                "也可能只是预先拆分的固定买入计划；缺少 Decision 和目标仓位，"
                "不能把盘面解释当成用户事实。"
            )
        elif trend_up or (trade_vs_prior is not None and trade_vs_prior > ZERO):
            bar_phrase = (
                "，且成交接近操作前最近已完成 5 分钟 K 线高点"
                if bar_high is not None
                and price is not None
                and abs(trade_vs_bar_high or ZERO) <= Decimal("0.5")
                else ""
            )
            trend_phrase = (
                f"操作前近三次收盘累计上涨约 "
                f"{_decimal_text(prior_return, places=2)}%"
                if prior_return is not None
                else (
                    f"成交价较操作前最近收盘高 "
                    f"{_decimal_text(trade_vs_prior, places=2)}%"
                )
            )
            motive = (
                f"系统推断：{trend_phrase}，"
                f"本笔仅增加操作前持仓的 "
                f"{_visible_text(_decimal_text(position_change_pct, places=2))}%"
                f"{bar_phrase}；"
                "更像小幅顺势试仓，而不是一次性改变长期仓位。"
            )
            alternative = (
                "也可能是长期仓位补回或被动再平衡；没有 Decision，"
                "不能确认其依据是短线趋势。"
            )
        else:
            motive = (
                "系统推断：本笔在操作前趋势不强时增加仓位，更像回撤补仓或"
                "恢复目标仓位；现有数据不能证明其目的。"
            )
            alternative = "也可能是长期配置或现金再平衡，而非基于短线价格判断。"
    elif side == "SELL":
        if (
            earlier_buys == quantity
            and quantity > ZERO
            and quantity_after
            == (
                _decimal(earlier_buy_operations[0].get("quantity_before"))
                if earlier_buy_operations
                else None
            )
        ):
            motive = (
                f"系统推断：本笔卖出数量恰好等于此前同日买入的 "
                f"{_decimal_text(earlier_buys)} 股，并把持仓恢复到 "
                f"{_decimal_text(quantity_after)} 股；结构上最像撤回全部日内新增、"
                "完成一次做 T，或在加仓未形成足够优势时回到原仓位。"
            )
            alternative = (
                "也可能是预设的同量拆单卖出或现金调度；数量闭环只提高结构解释力，"
                "仍不能证明用户真实意图。"
            )
        elif earlier_buys >= quantity and quantity > ZERO:
            motive = (
                "系统推断：本笔卖出可由此前同日买入数量覆盖，"
                "更像撤回部分新增仓位、控制盘中风险或做 T。"
            )
            alternative = "也可能是预设拆单卖出或现金调度，不能据此认定实际交易意图。"
        elif trade_vs_prior is not None and trade_vs_prior > ZERO:
            motive = "系统推断：本笔更像在上涨中降低仓位风险或兑现一部分利润。"
            alternative = "也可能是组合再平衡或现金需要，与价格判断无关。"
        else:
            motive = "系统推断：本笔更像降低持仓风险或执行止损/退出计划。"
            alternative = "也可能是组合再平衡；缺少 Decision，不能确认止损理由。"
    else:
        motive = "系统推断：当前操作不改变持仓，更像现金或费用类账务事件。"
        alternative = "缺少原始说明时不能进一步归因。"

    confidence = (
        "medium"
        if previous_close is not None
        and (
            len(prior_closes) >= 3
            or earlier_same_instrument
            or latest_completed_bar is not None
        )
        else "low"
    )
    missing = [
        "MISSING_DECISION",
        "MISSING_STRATEGY_OR_TARGET_POSITION",
    ]
    if latest_completed_bar is None:
        missing.append("MISSING_INTRADAY_MARKET_CONTEXT")
    return {
        "label": "system_inference",
        "operation_id": operation.get("operation_id"),
        "input_cutoff_at": occurred_at,
        "most_likely_motive": motive,
        "supporting_observations": observations,
        "alternative_explanations": [alternative],
        "confidence": confidence,
        "important_missing_information": missing,
        "uses_later_information": False,
    }


def _operation_evaluation(
    operation: Mapping[str, Any],
    *,
    closing_price: Decimal | None,
) -> dict[str, Any]:
    side = str(operation.get("side") or "")
    price = _decimal(operation.get("price_cny"))
    quantity = _decimal(operation.get("quantity"), default=ZERO) or ZERO
    mark_to_close = None
    if closing_price is not None and price is not None:
        mark_to_close = (
            (closing_price - price) * quantity
            if side == "BUY"
            else (price - closing_price) * quantity
            if side == "SELL"
            else ZERO
        )
    fee_status = str(operation.get("fee_status") or "unknown")
    if mark_to_close is None:
        judgment = "unknown"
        narrative = "缺少当日收盘价，无法进行事后执行评价。"
    elif mark_to_close > ZERO:
        judgment = "reasonable"
        narrative = "按当日收盘价回看，成交方向获得了正的毛价差。"
    elif mark_to_close == ZERO:
        judgment = "mixed"
        narrative = "按当日收盘价回看，毛价差接近零。"
    else:
        judgment = "needs_improvement"
        narrative = "按当日收盘价回看，成交方向产生了负的毛价差。"
    if fee_status == "unknown":
        narrative += " 费用来源仍未知，不能把毛价差当作真实净收益。"
    elif fee_status == "rule_backfilled":
        narrative += " 费用为规则计算或回填值，可用于净结果计算，但不冒充券商实收。"
    elif fee_status == "formal_exemption":
        narrative += " 该笔为正式规则确认的费用豁免。"
    elif fee_status == "reported_actual":
        narrative += " 该笔采用账本记录的实收费用。"
    return {
        "type": "retrospective_outcome",
        "judgment": judgment,
        "gross_mark_to_close_cny": _decimal_text(mark_to_close, places=2),
        "fee_status": fee_status,
        "narrative": narrative,
    }


def _daily_operations(
    connection: sqlite3.Connection,
    *,
    ledger: Sequence[Mapping[str, Any]],
    report_date: date,
    end_snapshot: Mapping[str, Any],
    review_db: str | Path | None,
    point_in_time_context: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    day_rows = [
        row
        for row in ledger
        if row.get("event_date") == report_date.isoformat()
        and row.get("event_type") in _POSITION_EVENT_TYPES
    ]
    transition_index, collection = _episode_transition_index(
        ledger,
        cutoff_at=_report_cutoff(report_date),
    )
    decisions = _decision_links(review_db, day_rows)
    positions = {
        item["ts_code"]: item for item in end_snapshot.get("positions", [])
    }
    day_codes = sorted(
        {
            str(row.get("ts_code") or "")
            for row in day_rows
            if row.get("ts_code")
        }
    )
    instrument_names: dict[str, str] = {}
    if day_codes:
        placeholders = ",".join("?" for _ in day_codes)
        instrument_names = {
            str(item["ts_code"]): str(item["name"] or item["ts_code"])
            for item in connection.execute(
                f"SELECT ts_code, name FROM instruments "
                f"WHERE ts_code IN ({placeholders})",
                tuple(day_codes),
            )
        }
    context_subject = (
        str(point_in_time_context.get("subject", {}).get("ts_code") or "")
        if isinstance(point_in_time_context, Mapping)
        and isinstance(point_in_time_context.get("subject"), Mapping)
        else ""
    )
    instrument_contexts = (
        point_in_time_context.get("instrument_contexts", {})
        if isinstance(point_in_time_context, Mapping)
        and isinstance(point_in_time_context.get("instrument_contexts"), Mapping)
        else {}
    )
    earlier: list[dict[str, Any]] = []
    result: list[dict[str, Any]] = []
    prior_cache: dict[str, list[dict[str, Any]]] = {}
    for row in day_rows:
        event_id = _event_id(row)
        transition = transition_index.get(event_id, {})
        fee = _fee_provenance(row)
        occurred_at = _iso_utc(_event_time(row))
        code = str(row.get("ts_code") or "")
        operation_context = (
            instrument_contexts.get(code)
            if isinstance(instrument_contexts.get(code), Mapping)
            else (
                point_in_time_context
                if context_subject == code
                and isinstance(point_in_time_context, Mapping)
                else {}
            )
        )
        intraday_bars = (
            list(operation_context.get("intraday_bars", []))
            if isinstance(operation_context, Mapping)
            else []
        )
        operation = {
            "operation_id": "operation_" + _sha256_text(event_id)[:24],
            "event_id": event_id,
            "episode_id": transition.get("episode_id"),
            "episode_status": transition.get("episode_status"),
            "occurred_at": occurred_at,
            "source_imported_at": row.get("created_at"),
            "event_type": str(row.get("event_type") or "").lower(),
            "side": str(row.get("event_type") or "").upper(),
            "ts_code": code,
            "name": positions.get(code, {}).get(
                "name", instrument_names.get(code, code)
            ),
            "quantity": str(row.get("quantity") or "0"),
            "price_cny": _decimal_text(_decimal(row.get("price")), places=4),
            "gross_amount_cny": _decimal_text(
                _decimal(row.get("gross_amount")), places=2
            ),
            "fee_cny": fee["amount_cny"],
            "fee_status": fee["status"],
            "fee_rule": fee["fee_rule"],
            "fee_is_known": fee["is_known"],
            "quantity_before": transition.get("quantity_before"),
            "quantity_after": transition.get("quantity_after"),
            "operation_role": None,
            "decision_status": (
                "recorded" if decisions.get(event_id) else "not_recorded"
            ),
            "recorded_decisions": decisions.get(event_id, []),
            "source_ref": f"portfolio.sqlite3#ledger_entries:{row.get('entry_id')}",
        }
        operation["operation_role"] = _operation_role(operation)
        if code not in prior_cache:
            prior_cache[code] = _prior_closes(
                connection,
                ts_code=code,
                before=report_date,
            )
        position = positions.get(code, {})
        current_weight = _decimal(position.get("portfolio_weight_pct"))
        current_quantity = _decimal(position.get("quantity"))
        estimated_weight_before = None
        if (
            current_weight is not None
            and current_quantity not in (None, ZERO)
        ):
            quantity_before = _decimal(operation.get("quantity_before"))
            if quantity_before is not None:
                estimated_weight_before = (
                    current_weight * quantity_before / current_quantity
                )
        if decisions.get(event_id):
            operation["motive"] = {
                "label": "recorded_decision",
                "operation_id": operation["operation_id"],
                "input_cutoff_at": occurred_at,
                "records": decisions[event_id],
                "uses_later_information": False,
            }
        else:
            operation["motive"] = infer_motive_hypothesis(
                operation,
                earlier_operations=earlier,
                prior_closes=prior_cache[code],
                position_weight_before_pct=_decimal_text(
                    estimated_weight_before, places=2
                ),
                intraday_bars=intraday_bars or None,
            )
        closing_row = _price_row(
            connection,
            ts_code=code,
            through=report_date,
        )
        closing_price = (
            _decimal(closing_row.get("close")) if closing_row is not None else None
        )
        operation["retrospective_evaluation"] = _operation_evaluation(
            operation,
            closing_price=closing_price,
        )
        result.append(operation)
        earlier.append(operation)
    return result, collection


def _daily_episode_summaries(
    operations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for operation in operations:
        grouped.setdefault(str(operation.get("ts_code") or ""), []).append(operation)
    summaries: list[dict[str, Any]] = []
    for code, items in sorted(grouped.items()):
        ordered = sorted(items, key=lambda item: str(item.get("occurred_at") or ""))
        buys = [item for item in ordered if item.get("side") == "BUY"]
        sells = [item for item in ordered if item.get("side") == "SELL"]
        bought_quantity = sum(
            (_decimal(item.get("quantity"), default=ZERO) or ZERO for item in buys),
            ZERO,
        )
        sold_quantity = sum(
            (_decimal(item.get("quantity"), default=ZERO) or ZERO for item in sells),
            ZERO,
        )
        buy_gross = sum(
            (
                _decimal(item.get("gross_amount_cny"), default=ZERO) or ZERO
                for item in buys
            ),
            ZERO,
        )
        sell_gross = sum(
            (
                _decimal(item.get("gross_amount_cny"), default=ZERO) or ZERO
                for item in sells
            ),
            ZERO,
        )
        fees_known = all(bool(item.get("fee_is_known")) for item in ordered)
        fee_total = sum(
            (
                _decimal(item.get("fee_cny"), default=ZERO) or ZERO
                for item in ordered
            ),
            ZERO,
        )
        opening_quantity = _decimal(ordered[0].get("quantity_before"), default=ZERO)
        closing_quantity = _decimal(ordered[-1].get("quantity_after"), default=ZERO)
        quantity_path = [
            opening_quantity or ZERO,
            *[
                _decimal(item.get("quantity_after"), default=ZERO) or ZERO
                for item in ordered
            ],
        ]
        peak_quantity = max(quantity_path, default=ZERO)
        peak_increase_pct = _pct(
            peak_quantity - (opening_quantity or ZERO),
            opening_quantity,
        )
        closed_round_trip = (
            bought_quantity == sold_quantity
            and bought_quantity > ZERO
            and opening_quantity == closing_quantity
        )
        gross_round_trip = (
            sell_gross - buy_gross if closed_round_trip else None
        )
        net_round_trip = (
            gross_round_trip - fee_total
            if gross_round_trip is not None and fees_known
            else None
        )
        if closed_round_trip and len(buys) > 1:
            first_quantity = _decimal(buys[0].get("quantity"), default=ZERO) or ZERO
            largest_later = max(
                (
                    _decimal(item.get("quantity"), default=ZERO) or ZERO
                    for item in buys[1:]
                ),
                default=ZERO,
            )
            scale_up = (
                largest_later > first_quantity
                and _decimal(buys[-1].get("price_cny"), default=ZERO)
                > _decimal(buys[0].get("price_cny"), default=ZERO)
            )
            if net_round_trip is not None and net_round_trip < ZERO and scale_up:
                assessment = (
                    "先小额试仓本身控制了初始风险，但随后在更高价格放大加仓，"
                    "最终又全部撤回；毛价差没有覆盖费用。需要改进的是"
                    "“价格越高、加仓越大”的执行节奏，而不是把亏损简单归因于手续费。"
                )
            elif net_round_trip is not None and net_round_trip < ZERO:
                assessment = "日内仓位已回到起点，但闭环净结果为负，操作收益未覆盖费用。"
            else:
                assessment = "日内新增仓位已全部撤回；应结合净结果判断做 T 是否有效。"
        elif closed_round_trip:
            assessment = "日内新增仓位已全部撤回，形成可核对的仓位闭环。"
        else:
            assessment = "当日操作改变了期末仓位，应与目标仓位和风险预算共同复盘。"
        summaries.append(
            {
                "type": "retrospective_execution_summary",
                "ts_code": code,
                "name": ordered[0].get("name") or code,
                "opening_quantity": _decimal_text(opening_quantity),
                "peak_quantity": _decimal_text(peak_quantity),
                "closing_quantity": _decimal_text(closing_quantity),
                "peak_increase_pct": _decimal_text(peak_increase_pct, places=2),
                "bought_quantity": _decimal_text(bought_quantity),
                "sold_quantity": _decimal_text(sold_quantity),
                "round_trip_closed": closed_round_trip,
                "gross_round_trip_pnl_cny": _decimal_text(
                    gross_round_trip, places=2
                ),
                "fee_total_cny": (
                    _decimal_text(fee_total, places=2) if fees_known else None
                ),
                "fee_statuses": sorted(
                    {str(item.get("fee_status") or "unknown") for item in ordered}
                ),
                "net_round_trip_pnl_cny": _decimal_text(
                    net_round_trip, places=2
                ),
                "assessment": assessment,
                "source_refs": [str(item.get("source_ref") or "") for item in ordered],
            }
        )
    return summaries


def _missing_context_layer(name: str) -> dict[str, Any]:
    return {
        "status": "missing",
        "scope": "daily_operation_delta",
        "summary": f"本期未取得可核对的{name}增量上下文。",
        "observations": [],
        "source_refs": [],
    }


def _decision_context(
    *,
    subject_type: str,
    subject_id: str,
    snapshot: Mapping[str, Any],
    positions: Sequence[Mapping[str, Any]],
    operations: Sequence[Mapping[str, Any]],
    episode_summaries: Sequence[Mapping[str, Any]],
    point_in_time_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    source = point_in_time_context if isinstance(point_in_time_context, Mapping) else {}
    fundamental = dict(
        source.get("fundamental_and_valuation")
        if isinstance(source.get("fundamental_and_valuation"), Mapping)
        else _missing_context_layer("基本面与估值")
    )
    market = dict(
        source.get("market_and_sector")
        if isinstance(source.get("market_and_sector"), Mapping)
        else _missing_context_layer("大盘与板块")
    )
    technical = dict(
        source.get("technical_and_trend")
        if isinstance(source.get("technical_and_trend"), Mapping)
        else _missing_context_layer("技术与趋势")
    )
    if (
        subject_type == "portfolio"
        and source
        and str(source.get("subject", {}).get("ts_code") or "")
    ):
        operated_name = str(source.get("subject", {}).get("name") or subject_id)
        for layer in (fundamental, market, technical):
            layer["scope"] = "daily_operated_instrument_delta"
            layer["portfolio_scope_note"] = (
                f"日报只展开当日操作相关标的 {operated_name}，"
                "不冒充全组合基本面覆盖。"
            )
    elif subject_type == "portfolio" and source:
        for layer in (fundamental, market, technical):
            layer["portfolio_scope_note"] = (
                "组合层汇总持有或当日交易标的；具体事实与缺口见对应标的日报。"
            )

    cash_weight_text = _visible_text(snapshot.get("cash_weight_pct"))
    top_weight_text = _visible_text(snapshot.get("top_position_weight_pct"))
    top3_weight_text = _visible_text(snapshot.get("top3_weight_pct"))
    position_observations = [
        {
            "type": "fact",
            "text": (
                f"报告截止现金权重 {cash_weight_text}%，"
                f"最大单一标的权重 {top_weight_text}%，"
                f"前三大合计 {top3_weight_text}%。"
            ),
            "source_ref": "portfolio.sqlite3#ledger_entries+cash_balance_snapshots+close_prices",
        }
    ]
    for summary in episode_summaries:
        position_observations.append(
            {
                "type": "retrospective_outcome",
                "text": (
                    f"{summary.get('name')}（{summary.get('ts_code')}）"
                    f"持仓 {summary.get('opening_quantity')} → "
                    f"{summary.get('peak_quantity')} → "
                    f"{summary.get('closing_quantity')}；"
                    f"{summary.get('assessment')}"
                ),
                "source_ref": ",".join(summary.get("source_refs", [])),
            }
        )
    selected_position = next(
        (
            item
            for item in positions
            if item.get("ts_code") == subject_id
        ),
        None,
    )
    selected_weight_text = (
        _visible_text(selected_position.get("portfolio_weight_pct"))
        if isinstance(selected_position, Mapping)
        else "0"
    )
    position_summary = (
        f"标的期末组合权重 {selected_weight_text}%；"
        f"当日 {len(operations)} 笔操作已按仓位路径和净闭环复盘。"
        if subject_type == "instrument"
        else (
            f"组合现金权重 {cash_weight_text}%，"
            f"最大单一标的 {top_weight_text}%；"
            "日报只展开当日操作带来的仓位与执行变化。"
        )
    )
    return {
        "framework": "four_layer_periodic_review_v1",
        "report_depth": "daily_delta_only",
        "fundamental_and_valuation": fundamental,
        "market_and_sector": market,
        "technical_and_trend": technical,
        "position_and_execution": {
            "status": "available",
            "scope": "daily_operation_delta",
            "summary": position_summary,
            "observations": position_observations,
            "episode_summaries": list(episode_summaries),
            "source_refs": sorted(
                {
                    ref
                    for item in position_observations
                    for ref in [str(item.get("source_ref") or "")]
                    if ref
                }
            ),
        },
        "timing_policy": (
            "动机仅使用操作时点已可见信息；收盘、板块相对表现和净闭环"
            "只进入事后复盘与报告截止建议。"
        ),
    }


def build_recommendation(
    *,
    subject_type: str,
    subject_id: str,
    snapshot: Mapping[str, Any],
    report_cutoff_at: str,
    decision_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    positions = list(snapshot.get("positions", []))
    total_assets = _decimal(snapshot.get("total_assets_cny"))
    cash_weight = _decimal(snapshot.get("cash_weight_pct"))
    top_weight = _decimal(snapshot.get("top_position_weight_pct"))
    context = decision_context if isinstance(decision_context, Mapping) else {}
    fundamental = (
        context.get("fundamental_and_valuation")
        if isinstance(context.get("fundamental_and_valuation"), Mapping)
        else {}
    )
    market = (
        context.get("market_and_sector")
        if isinstance(context.get("market_and_sector"), Mapping)
        else {}
    )
    technical = (
        context.get("technical_and_trend")
        if isinstance(context.get("technical_and_trend"), Mapping)
        else {}
    )
    execution = (
        context.get("position_and_execution")
        if isinstance(context.get("position_and_execution"), Mapping)
        else {}
    )
    snapshot_cash = (
        snapshot.get("cash")
        if isinstance(snapshot.get("cash"), Mapping)
        else {}
    )
    latest_price_date = max(
        (
            str(item.get("price_date") or "")
            for item in positions
            if item.get("price_date")
        ),
        default=None,
    )
    missing_inputs = ["MISSING_EXPLICIT_USER_RISK_BUDGET"]
    if fundamental.get("status") not in {"available", "partial"}:
        missing_inputs.append("MISSING_FUNDAMENTAL_AND_VALUATION_CONTEXT")
    if market.get("status") not in {"available", "partial"}:
        missing_inputs.append("MISSING_MARKET_AND_SECTOR_CONTEXT")
    if technical.get("status") != "available":
        missing_inputs.append("MISSING_TECHNICAL_AND_TREND_CONTEXT")
    if snapshot_cash.get("fee_pending"):
        missing_inputs.append("UNKNOWN_TRADE_FEE_PROVENANCE")
    if subject_type == "portfolio":
        concentrated = top_weight is not None and top_weight > Decimal("20")
        cash_thin = cash_weight is not None and cash_weight < Decimal("5")
        action = "reduce" if concentrated or cash_thin else "hold"
        target = {
            "target_cash_range_pct": ["5", "10"],
            "single_instrument_cap_range_pct": ["15", "20"],
            "target_position_note": (
                "把超过 20% 的单一标的降至 15%–20%，并将现金提高至 5%–10%。"
            ),
        }
        rationale = [
            {
                "type": "fact",
                "text": f"当前现金权重约 {snapshot.get('cash_weight_pct')}%。",
                "source_ref": "portfolio.sqlite3#cash_balance_snapshots+close_prices",
            },
            {
                "type": "fact",
                "text": (
                    "最大单一标的权重约 "
                    f"{snapshot.get('top_position_weight_pct')}%，"
                    f"前三大合计约 {snapshot.get('top3_weight_pct')}%。"
                ),
                "source_ref": "portfolio.sqlite3#ledger_entries+close_prices",
            },
            {
                "type": "opinion",
                "text": "在缺少完整风险预算时，先降低集中度比继续放大方向暴露更稳妥。",
                "source_ref": "periodic_report:risk_guardrail",
            },
        ]
        if market.get("summary"):
            rationale.append(
                {
                    "type": "inference",
                    "text": (
                        f"当日操作环境增量：{market.get('summary')}"
                        " 这不替代全组合逐标的研究。"
                    ),
                    "source_ref": ",".join(market.get("source_refs", [])),
                }
            )
        invalidation = [
            "用户已有可验证且不同的风险预算或资金安排",
            "正式账本现金或持仓在报告截止后发生变化",
            "新增全组合基本面证据支持当前集中度且风险预算允许",
        ]
        risks = [
            "减仓后标的继续上涨会产生机会成本",
            "日报只展开当日操作标的，未完成全组合逐标的基本面覆盖",
            "指数或板块同涨不代表组合内每只股票的风险同步下降",
        ]
        if snapshot_cash.get("fee_pending"):
            risks.append("部分交易费用来源未知，现金比例仍有小幅误差风险")
        missing_inputs.append("MISSING_FULL_PORTFOLIO_FUNDAMENTAL_COVERAGE")
        confidence = "medium" if total_assets is not None else "low"
    else:
        selected = next(
            (item for item in positions if item.get("ts_code") == subject_id),
            None,
        )
        weight = _decimal(selected.get("portfolio_weight_pct")) if selected else ZERO
        if selected is None:
            action = "hold"
            target_range = ["0", "0"]
            target_note = "当前无持仓；数据不足时不新增仓位。"
        elif weight is not None and weight > Decimal("20"):
            action = "reduce"
            target_range = ["12", "18"]
            target_note = "把单标的权重降至 12%–18%。"
        elif weight is not None and weight > Decimal("12"):
            action = "reduce"
            target_range = ["8", "12"]
            target_note = "把单标的权重降至 8%–12%。"
        elif weight is not None and weight >= Decimal("5"):
            action = "hold"
            target_range = ["5", "12"]
            target_note = "维持 5%–12%，不在证据不足时继续加仓。"
        else:
            action = "hold"
            target_range = ["0", "5"]
            target_note = "维持观察仓或空仓，不主动扩大到 5% 以上。"
        target = {
            "target_position_range_pct": target_range,
            "target_position_note": target_note,
        }
        rationale = [
            {
                "type": "fact",
                "text": (
                    f"报告截止时组合权重约 "
                    f"{selected.get('portfolio_weight_pct') if selected else '0'}%。"
                ),
                "source_ref": (
                    selected.get("source_refs", [None])[0]
                    if selected
                    else "portfolio.sqlite3#ledger_entries"
                ),
            },
            {
                "type": "fact",
                "text": (
                    f"收盘价 {selected.get('close_cny') if selected else 'MISSING'} 元，"
                    f"账面成本 {selected.get('average_cost_cny') if selected else 'MISSING'} 元。"
                ),
                "source_ref": "portfolio.sqlite3#ledger_entries+close_prices",
            },
            {
                "type": "inference",
                "text": (
                    str(fundamental.get("summary"))
                    if fundamental.get("summary")
                    else "基本面与估值增量不足，不能仅因短期价格反弹扩大集中仓位。"
                ),
                "source_ref": ",".join(fundamental.get("source_refs", []))
                or "periodic_report:risk_guardrail",
            },
            {
                "type": "inference",
                "text": (
                    str(market.get("summary"))
                    if market.get("summary")
                    else "大盘与板块信息不足，不能把共同涨跌直接解释为个股动机。"
                ),
                "source_ref": ",".join(market.get("source_refs", []))
                or "periodic_report:market_context_boundary",
            },
            {
                "type": "inference",
                "text": (
                    str(technical.get("summary"))
                    if technical.get("summary")
                    else "技术与趋势信息不足，不据此放大仓位。"
                ),
                "source_ref": ",".join(technical.get("source_refs", []))
                or "periodic_report:trend_boundary",
            },
            {
                "type": "opinion",
                "text": (
                    str(execution.get("summary"))
                    if execution.get("summary")
                    else "在缺少明确风险预算时，不应继续扩大单一标的集中度。"
                ),
                "source_ref": "periodic_report:position_and_execution",
            },
        ]
        invalidation = [
            "用户提供可验证的目标仓位与止损/加仓计划",
            "新的基本面或估值证据改变风险收益判断",
            "正式账本持仓在报告截止后已发生变化",
        ]
        risks = [
            "减仓后价格继续上涨会产生机会成本",
            (
                "最新可得财务快照仍显示经营风险，短期趋势转强不等于基本面反转"
                if fundamental.get("observations")
                else "轻量日报不能替代公司长期价值深度研究"
            ),
            "大盘或板块共同上涨不能证明个股会持续跑赢",
            "技术趋势是概率性上下文，不能保证后续收益",
        ]
        if snapshot_cash.get("fee_pending"):
            risks.append("部分交易费用来源未知，会影响执行净结果")
        confidence = (
            "medium"
            if all(
                layer.get("status") in {"available", "partial"}
                for layer in (fundamental, market, technical)
            )
            and total_assets is not None
            else "low"
        )
    return {
        "type": "analyst_view",
        "action": action,
        "target_position": target,
        "time_horizon": "下一交易周或下一次实质性信息更新前",
        "confidence": confidence,
        "rationale": rationale,
        "major_downside_risks": risks,
        "invalidation_conditions": invalidation,
        "data_timestamp": (
            f"{latest_price_date}T15:00:00+08:00"
            if latest_price_date
            else report_cutoff_at
        ),
        "report_cutoff_at": report_cutoff_at,
        "important_missing_inputs": sorted(set(missing_inputs)),
        "orders_executed": False,
        "guaranteed_return": False,
    }


def _report_headline(
    *,
    subject_type: str,
    subject_id: str,
    subject_name: str | None = None,
    snapshot: Mapping[str, Any],
    performance: Mapping[str, Any],
    recommendation: Mapping[str, Any],
) -> str:
    if subject_type == "portfolio":
        change_basis = (
            "总资产"
            if performance.get("asset_change_pct") is not None
            else "不含现金的持仓市值"
        )
        change_pct = (
            performance.get("asset_change_pct")
            if performance.get("asset_change_pct") is not None
            else performance.get("invested_market_value_change_pct")
        )
        change_pct = change_pct if change_pct is not None else "MISSING"
        cash_weight = snapshot.get("cash_weight_pct")
        cash_weight = cash_weight if cash_weight is not None else "MISSING"
        return (
            f"组合当日{change_basis}变动 {change_pct}%，"
            f"现金权重 {cash_weight}%；"
            f"建议 {recommendation.get('action')}，优先降低集中度并保留现金缓冲。"
        )
    selected = next(
        (item for item in snapshot.get("positions", []) if item.get("ts_code") == subject_id),
        None,
    )
    display_name = (
        selected.get("name")
        if selected
        else (str(subject_name).strip() if str(subject_name or "").strip() else subject_id)
    )
    selected_weight = (
        selected.get("portfolio_weight_pct") if selected else "0"
    )
    selected_weight = (
        selected_weight if selected_weight is not None else "MISSING"
    )
    price_change_pct = performance.get("price_change_pct")
    performance_text = (
        f"收盘价变动 {price_change_pct}%"
        if price_change_pct is not None
        else "收盘价变动 MISSING"
    )
    return (
        f"{display_name}（{subject_id}）期末权重 "
        f"{selected_weight}%，"
        f"{performance_text}；"
        f"当日操作已按四层上下文与无 Decision 的 system_inference 复盘；"
        f"建议 {recommendation.get('action')}。"
    )


def _selected_market_value(
    positions: Sequence[Mapping[str, Any]],
) -> Decimal | None:
    if not positions:
        return ZERO
    values = [_decimal(item.get("market_value_cny")) for item in positions]
    if any(value is None for value in values):
        return None
    return sum((value or ZERO for value in values), ZERO)


def _selected_quantity(
    positions: Sequence[Mapping[str, Any]],
) -> Decimal:
    return sum(
        (
            _decimal(item.get("quantity"), default=ZERO) or ZERO
            for item in positions
        ),
        ZERO,
    )


def _instrument_performance(
    *,
    subject_id: str,
    previous_date: date | None,
    report_date: date,
    opening_positions: Sequence[Mapping[str, Any]],
    closing_positions: Sequence[Mapping[str, Any]],
    opening_price: Mapping[str, Any] | None,
    closing_price: Mapping[str, Any] | None,
) -> dict[str, Any]:
    start_close = (
        _decimal(opening_price.get("close"))
        if isinstance(opening_price, Mapping)
        else None
    )
    end_close = (
        _decimal(closing_price.get("close"))
        if isinstance(closing_price, Mapping)
        else None
    )
    price_change = (
        end_close - start_close
        if start_close is not None and end_close is not None
        else None
    )
    opening_market_value = _selected_market_value(opening_positions)
    closing_market_value = _selected_market_value(closing_positions)
    market_value_change = (
        closing_market_value - opening_market_value
        if opening_market_value is not None and closing_market_value is not None
        else None
    )
    opening_quantity = _selected_quantity(opening_positions)
    closing_quantity = _selected_quantity(closing_positions)
    if price_change is not None:
        performance_basis = "instrument_close_price"
        period_change = price_change
        period_change_pct = _pct(price_change, start_close)
    elif market_value_change is not None:
        performance_basis = "instrument_position_market_value"
        period_change = market_value_change
        period_change_pct = _pct(market_value_change, opening_market_value)
    else:
        performance_basis = "MISSING"
        period_change = None
        period_change_pct = None
    price_refs = []
    for price in (opening_price, closing_price):
        if isinstance(price, Mapping) and price.get("trade_date"):
            price_refs.append(
                "portfolio.sqlite3#close_prices:"
                f"{subject_id}:{price['trade_date']}"
            )
    return {
        "type": "fact",
        "comparison_date": previous_date.isoformat() if previous_date else None,
        "start_total_assets_cny": None,
        "end_total_assets_cny": None,
        "asset_change_cny": None,
        "asset_change_pct": None,
        "start_close_cny": _decimal_text(start_close, places=4),
        "end_close_cny": _decimal_text(end_close, places=4),
        "start_price_date": (
            opening_price.get("trade_date")
            if isinstance(opening_price, Mapping)
            else None
        ),
        "end_price_date": (
            closing_price.get("trade_date")
            if isinstance(closing_price, Mapping)
            else None
        ),
        "price_change_cny": _decimal_text(price_change, places=4),
        "price_change_pct": _decimal_text(
            _pct(price_change, start_close),
            places=2,
        ),
        "start_quantity": _decimal_text(opening_quantity),
        "end_quantity": _decimal_text(closing_quantity),
        "quantity_change": _decimal_text(closing_quantity - opening_quantity),
        "start_invested_market_value_cny": _decimal_text(
            opening_market_value,
            places=2,
        ),
        "end_invested_market_value_cny": _decimal_text(
            closing_market_value,
            places=2,
        ),
        "invested_market_value_change_cny": _decimal_text(
            market_value_change,
            places=2,
        ),
        "invested_market_value_change_pct": _decimal_text(
            _pct(market_value_change, opening_market_value),
            places=2,
        ),
        "performance_basis": performance_basis,
        "period_change_cny": _decimal_text(period_change, places=4),
        "period_change_pct": _decimal_text(period_change_pct, places=2),
        "cash_change_cny": None,
        "valuation_complete": (
            end_close is not None
            and (previous_date is None or start_close is not None)
            and closing_market_value is not None
        ),
        "calculation_method": (
            "标的收益以报告日与上一交易日收盘价变化计算，避免买卖数量变化"
            "冒充投资收益；持仓市值与数量变化另列，用于解释加减仓或退出。"
            "缺价时保持 MISSING，不以组合总资产变化替代标的表现。"
        ),
        "source_refs": sorted(
            {
                *price_refs,
                (
                    "portfolio.sqlite3#ledger_entries:"
                    f"{subject_id}:through:{report_date.isoformat()}"
                ),
            }
        ),
    }


def build_daily_report(
    *,
    portfolio_db: str | Path,
    review_db: str | Path | None,
    report_date: str | date,
    subject_type: str,
    subject_id: str | None = None,
    account_id: str = "default",
    point_in_time_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one deterministic P1 daily report from immutable source data."""

    day = _parse_date(report_date)
    if subject_type not in _SUBJECT_TYPES:
        raise PeriodicReportError("subject_type must be portfolio or instrument")
    if subject_type == "instrument" and not str(subject_id or "").strip():
        raise PeriodicReportError("instrument report requires subject_id")
    selected_subject = account_id if subject_type == "portfolio" else str(subject_id)
    source = Path(portfolio_db).expanduser().resolve(strict=True)
    source_sha = sha256_file(source)
    market_cutoff = _report_cutoff(day)

    opening_instrument_price: dict[str, Any] | None = None
    closing_instrument_price: dict[str, Any] | None = None
    with _read_only_connection(source) as connection:
        previous_date = _previous_market_date(connection, report_date=day)
        end_snapshot = _portfolio_snapshot(
            connection,
            account_id=account_id,
            as_of=day,
        )
        start_snapshot = (
            _portfolio_snapshot(
                connection,
                account_id=account_id,
                as_of=previous_date,
            )
            if previous_date is not None
            else None
        )
        ledger = _ledger_rows(connection, account_id=account_id, through=day)
        operations, episode_collection = _daily_operations(
            connection,
            ledger=ledger,
            report_date=day,
            end_snapshot=end_snapshot,
            review_db=review_db,
            point_in_time_context=point_in_time_context,
        )
        if subject_type == "instrument":
            closing_instrument_price = _price_row(
                connection,
                ts_code=selected_subject,
                through=day,
            )
            opening_instrument_price = (
                _price_row(
                    connection,
                    ts_code=selected_subject,
                    through=previous_date,
                )
                if previous_date is not None
                else None
            )

    if subject_type == "instrument":
        operations = [
            item for item in operations if item.get("ts_code") == selected_subject
        ]
        selected_positions = [
            item
            for item in end_snapshot["positions"]
            if item.get("ts_code") == selected_subject
        ]
        selected_opening_positions = [
            item
            for item in (
                start_snapshot.get("positions", [])
                if start_snapshot is not None
                else []
            )
            if item.get("ts_code") == selected_subject
        ]
    else:
        selected_positions = end_snapshot["positions"]
        selected_opening_positions = (
            start_snapshot.get("positions", [])
            if start_snapshot is not None
            else []
        )
    episode_summaries = _daily_episode_summaries(operations)

    source_observed_through = max(
        filter(
            None,
            [
                end_snapshot.get("source_observed_through"),
                start_snapshot.get("source_observed_through")
                if start_snapshot is not None
                else None,
            ],
        ),
        default=None,
    )
    generated_at = max(
        filter(
            None,
            [
                source_observed_through,
                (
                    point_in_time_context.get("fetched_at")
                    if isinstance(point_in_time_context, Mapping)
                    else None
                ),
            ],
        ),
        default=None,
    )
    report_cutoff_at = market_cutoff.astimezone(SHANGHAI).isoformat(
        timespec="seconds"
    )

    start_assets = (
        _decimal(start_snapshot.get("total_assets_cny"))
        if start_snapshot is not None
        else None
    )
    end_assets = _decimal(end_snapshot.get("total_assets_cny"))
    asset_change = (
        end_assets - start_assets
        if end_assets is not None and start_assets is not None
        else None
    )
    start_market_value = (
        _decimal(start_snapshot.get("market_value_cny"))
        if start_snapshot is not None
        else None
    )
    end_market_value = _decimal(end_snapshot.get("market_value_cny"))
    market_value_change = (
        end_market_value - start_market_value
        if end_market_value is not None and start_market_value is not None
        else None
    )
    start_cash_payload = (
        start_snapshot.get("cash")
        if start_snapshot is not None
        and isinstance(start_snapshot.get("cash"), Mapping)
        else {}
    )
    end_cash_payload = (
        end_snapshot.get("cash")
        if isinstance(end_snapshot.get("cash"), Mapping)
        else {}
    )
    start_cash = _decimal(start_cash_payload.get("amount_cny"))
    end_cash = _decimal(end_cash_payload.get("amount_cny"))
    performance = {
        "type": "fact",
        "comparison_date": (
            previous_date.isoformat() if previous_date is not None else None
        ),
        "start_total_assets_cny": _decimal_text(start_assets, places=2),
        "end_total_assets_cny": _decimal_text(end_assets, places=2),
        "asset_change_cny": _decimal_text(asset_change, places=2),
        "asset_change_pct": _decimal_text(
            _pct(asset_change, start_assets), places=2
        ),
        "start_invested_market_value_cny": _decimal_text(
            start_market_value,
            places=2,
        ),
        "end_invested_market_value_cny": _decimal_text(
            end_market_value,
            places=2,
        ),
        "invested_market_value_change_cny": _decimal_text(
            market_value_change,
            places=2,
        ),
        "invested_market_value_change_pct": _decimal_text(
            _pct(market_value_change, start_market_value),
            places=2,
        ),
        "performance_basis": (
            "total_assets"
            if asset_change is not None
            else (
                "invested_market_value_ex_cash"
                if market_value_change is not None
                else "MISSING"
            )
        ),
        "period_change_cny": _decimal_text(
            asset_change if asset_change is not None else market_value_change,
            places=2,
        ),
        "period_change_pct": _decimal_text(
            (
                _pct(asset_change, start_assets)
                if asset_change is not None
                else _pct(market_value_change, start_market_value)
            ),
            places=2,
        ),
        "cash_change_cny": _decimal_text(
            end_cash - start_cash
            if end_cash is not None and start_cash is not None
            else None,
            places=2,
        ),
        "valuation_complete": not end_snapshot.get("missing_prices"),
        "calculation_method": (
            "期末总资产减上一交易日总资产；当日无外部资金流证据时作为资产变动。"
            "若历史现金快照仍带 fee_pending，则从最近可靠现金锚点按当前账本费用"
            "只读重放，并保留被替代快照。现金不可得时总资产保持 MISSING，"
            "另报不含现金的持仓市值变化作为可核对的次级口径。"
        ),
        "source_refs": [
            "portfolio.sqlite3#ledger_entries",
            "portfolio.sqlite3#close_prices",
            "portfolio.sqlite3#cash_balance_snapshots",
        ],
    }
    if subject_type == "instrument":
        performance = _instrument_performance(
            subject_id=selected_subject,
            previous_date=previous_date,
            report_date=day,
            opening_positions=selected_opening_positions,
            closing_positions=selected_positions,
            opening_price=opening_instrument_price,
            closing_price=closing_instrument_price,
        )
    decision_context = _decision_context(
        subject_type=subject_type,
        subject_id=selected_subject,
        snapshot=end_snapshot,
        positions=selected_positions,
        operations=operations,
        episode_summaries=episode_summaries,
        point_in_time_context=point_in_time_context,
    )
    recommendation = build_recommendation(
        subject_type=subject_type,
        subject_id=selected_subject,
        snapshot=end_snapshot,
        report_cutoff_at=report_cutoff_at,
        decision_context=decision_context,
    )
    judgments = (
        [
            {
                "type": "inference",
                "status": (
                    "needs_improvement"
                    if _decimal(item.get("net_round_trip_pnl_cny")) is not None
                    and (_decimal(item.get("net_round_trip_pnl_cny")) or ZERO)
                    < ZERO
                    else "mixed"
                ),
                "text": item.get("assessment"),
                "source_refs": item.get("source_refs", []),
            }
            for item in episode_summaries
        ]
        or [
            {
                "type": "inference",
                "status": "no_trade",
                "text": "当日无持仓变动，不构造虚假的操作评价。",
                "source_refs": [],
            }
        ]
    )
    risks = {
        "type": "fact_and_inference",
        "cash_weight_pct": end_snapshot.get("cash_weight_pct"),
        "top_position_weight_pct": end_snapshot.get(
            "top_position_weight_pct"
        ),
        "top3_weight_pct": end_snapshot.get("top3_weight_pct"),
        "concentration_status": (
            "HIGH"
            if (_decimal(end_snapshot.get("top_position_weight_pct")) or ZERO)
            > Decimal("20")
            else "MODERATE"
        ),
        "missing_prices": end_snapshot.get("missing_prices", []),
        "cash_status": end_cash_payload.get("status", "MISSING"),
    }
    identity = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "subject_type": subject_type,
        "subject_id": selected_subject,
        "period_type": "daily",
        "period_start": day.isoformat(),
        "period_end": day.isoformat(),
    }
    report_id = "periodic_" + _sha256_text(_canonical_json(identity))[:32]
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_id": report_id,
        "status": "ready",
        "subject": {
            "type": subject_type,
            "id": selected_subject,
            "name": (
                "组合账户"
                if subject_type == "portfolio"
                else (
                    selected_positions[0]["name"]
                    if selected_positions
                    else (
                        point_in_time_context.get("subject", {}).get("name")
                        if isinstance(point_in_time_context, Mapping)
                        and isinstance(
                            point_in_time_context.get("subject"), Mapping
                        )
                        else selected_subject
                    )
                )
            ),
        },
        "period": {
            "type": "daily",
            "start": day.isoformat(),
            "end": day.isoformat(),
            "report_cutoff_at": report_cutoff_at,
        },
        "generated_at": generated_at,
        "headline": "",
        "sections": {
            "performance_and_positions": {
                "performance": performance,
                "opening_cash": (
                    start_snapshot.get("cash")
                    if start_snapshot is not None
                    else None
                ),
                "cash": end_snapshot.get("cash"),
                "opening_positions": selected_opening_positions,
                "positions": selected_positions,
                "risk_change": risks,
            },
            "decision_context": decision_context,
            "operations_and_motives": {
                "operation_count": len(operations),
                "operations": operations,
                "episode_summaries": episode_summaries,
            },
            "review_judgments": judgments,
            "recommendation": recommendation,
            "risks_invalidation_and_missing": {
                "major_risks": recommendation["major_downside_risks"],
                "invalidation_conditions": recommendation[
                    "invalidation_conditions"
                ],
                "missing_inputs": recommendation["important_missing_inputs"],
                "data_limitations": sorted(
                    {
                        *(
                            ["UNKNOWN_TRADE_FEE_PROVENANCE"]
                            if any(
                                item.get("fee_status") == "unknown"
                                for item in operations
                            )
                            else []
                        ),
                        *(
                            ["MISSING_DECISION"]
                            if any(
                                item.get("decision_status") == "not_recorded"
                                for item in operations
                            )
                            else []
                        ),
                        *(
                            ["EPISODE_PROJECTION_HAS_FINDINGS"]
                            if episode_collection.get("validation", {}).get(
                                "validation_status"
                            )
                            == "blocked"
                            else []
                        ),
                    }
                ),
            },
        },
        "source": {
            "source_path": "portfolio.sqlite3 (formal, immutable/query-only)",
            "source_sha256": source_sha,
            "source_observed_through": source_observed_through,
            "context_fetched_at": (
                point_in_time_context.get("fetched_at")
                if isinstance(point_in_time_context, Mapping)
                else None
            ),
            "review_sidecar": (
                "investment_review.sqlite3 (derived report state)"
                if review_db is not None
                else None
            ),
            "source_refs": [
                "portfolio.sqlite3#ledger_entries",
                "portfolio.sqlite3#close_prices",
                "portfolio.sqlite3#cash_balance_snapshots",
                "investment_review.sqlite3#decisions",
                *(
                    ["baostock#bounded_periodic_context"]
                    if point_in_time_context
                    else []
                ),
            ],
        },
        "safety": {
            "orders_executed": False,
            "broker_accessed": False,
            "guaranteed_return_claims": False,
            "recommendation_is_not_an_order": True,
        },
    }
    report["headline"] = _report_headline(
        subject_type=subject_type,
        subject_id=selected_subject,
        subject_name=report["subject"]["name"],
        snapshot=end_snapshot,
        performance=performance,
        recommendation=recommendation,
    )
    _attach_reader_narrative(report)
    report["content_id"] = "sha256:" + _sha256_text(_canonical_json(report))
    validation = validate_periodic_report(report)
    if validation["status"] != "accepted":
        raise PeriodicReportError(
            "periodic report validation failed: "
            + ", ".join(validation["errors"])
        )
    return report


def _compound_percent(values: Iterable[object]) -> str | None:
    factor = Decimal("1")
    observed = False
    for value in values:
        selected = _decimal(value)
        if selected is None:
            continue
        factor *= Decimal("1") + selected / Decimal("100")
        observed = True
    return (
        _decimal_text((factor - Decimal("1")) * Decimal("100"), places=2)
        if observed
        else None
    )


def _position_changes(
    opening: Sequence[Mapping[str, Any]],
    closing: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    before = {str(item.get("ts_code") or ""): item for item in opening}
    after = {str(item.get("ts_code") or ""): item for item in closing}
    result: list[dict[str, Any]] = []
    for code in sorted(set(before) | set(after)):
        start = before.get(code, {})
        end = after.get(code, {})
        start_quantity = _decimal(start.get("quantity"), default=ZERO) or ZERO
        end_quantity = _decimal(end.get("quantity"), default=ZERO) or ZERO
        change = end_quantity - start_quantity
        if change == ZERO and start and end:
            status = "held"
        elif start_quantity == ZERO and end_quantity > ZERO:
            status = "opened"
        elif start_quantity > ZERO and end_quantity == ZERO:
            status = "exited"
        elif change > ZERO:
            status = "added"
        else:
            status = "reduced"
        result.append(
            {
                "ts_code": code,
                "name": str(end.get("name") or start.get("name") or code),
                "opening_quantity": _decimal_text(start_quantity),
                "closing_quantity": _decimal_text(end_quantity),
                "quantity_change": _decimal_text(change),
                "opening_weight_pct": start.get("portfolio_weight_pct"),
                "closing_weight_pct": end.get("portfolio_weight_pct"),
                "status": status,
                "source_refs": sorted(
                    {
                        str(ref)
                        for item in (start, end)
                        for ref in item.get("source_refs", [])
                        if ref
                    }
                ),
            }
        )
    return result


def _aggregate_context_layer(
    reports: Sequence[Mapping[str, Any]],
    *,
    layer_name: str,
    period_type: str,
) -> dict[str, Any]:
    entries: list[tuple[str, Mapping[str, Any]]] = []
    for report in reports:
        layer = report.get("sections", {}).get("decision_context", {}).get(
            layer_name
        )
        if isinstance(layer, Mapping):
            entries.append((str(report["period"]["end"]), layer))
    if not entries:
        return _missing_context_layer(
            {
                "fundamental_and_valuation": "基本面与估值",
                "market_and_sector": "大盘与板块",
                "technical_and_trend": "技术与趋势",
            }[layer_name]
        )
    latest = deepcopy(entries[-1][1])
    statuses = [str(layer.get("status") or "missing") for _, layer in entries]
    covered = sum(status in {"available", "partial"} for status in statuses)
    latest["status"] = (
        "available"
        if covered == len(entries)
        else ("partial" if covered else "missing")
    )
    latest["scope"] = f"natural_{period_type}_synthesis"
    latest["covered_trade_dates"] = [day for day, _ in entries]
    latest["source_refs"] = sorted(
        {
            str(ref)
            for _, layer in entries
            for ref in layer.get("source_refs", [])
            if ref
        }
    )
    period_label = "周" if period_type == "weekly" else "月"
    if layer_name == "fundamental_and_valuation":
        distinct_summaries = list(
            dict.fromkeys(
                str(layer.get("summary") or "")
                for _, layer in entries
                if layer.get("summary")
            )
        )
        latest["summary"] = (
            f"本{period_label}覆盖 {len(entries)} 个交易日，"
            f"{covered} 日具备可核对的基本面/估值上下文；"
            f"期末判断：{distinct_summaries[-1] if distinct_summaries else '数据缺失'}"
        )
        latest["context_change_count"] = max(len(distinct_summaries) - 1, 0)
    elif layer_name == "market_and_sector":
        stock_return = _compound_percent(
            layer.get("stock_change_pct") for _, layer in entries
        )
        latest["period_stock_return_pct"] = stock_return
        latest["summary"] = (
            f"本{period_label}覆盖 {len(entries)} 个交易日；"
            + (
                f"标的区间复合涨跌幅 {stock_return}%。"
                if stock_return is not None
                else "组合层或行情缺口使区间标的收益无法统一计算。"
            )
            + " 大盘与板块仅用于事后归因，不反推操作动机。"
        )
    else:
        first_metrics = entries[0][1].get("metrics", {})
        last_metrics = entries[-1][1].get("metrics", {})
        first_close = (
            _decimal(first_metrics.get("close_cny"))
            if isinstance(first_metrics, Mapping)
            else None
        )
        last_close = (
            _decimal(last_metrics.get("close_cny"))
            if isinstance(last_metrics, Mapping)
            else None
        )
        period_return = (
            _pct(last_close - first_close, first_close)
            if first_close is not None and last_close is not None
            else None
        )
        latest["period_return_pct"] = _decimal_text(period_return, places=2)
        visible_period_return = latest["period_return_pct"] or "MISSING"
        latest["summary"] = (
            f"本{period_label}趋势以期初/期末和日级序列综合："
            f"区间收盘变动 {visible_period_return}%；"
            f"期末状态：{entries[-1][1].get('summary')}"
        )
    return latest


def build_aggregate_report(
    *,
    daily_reports: Sequence[Mapping[str, Any]],
    period_type: str,
    period_start: str | date,
    period_end: str | date,
) -> dict[str, Any]:
    """Build one natural weekly/monthly synthesis from validated daily facts."""

    if period_type not in {"weekly", "monthly"}:
        raise PeriodicReportError("aggregate period_type must be weekly or monthly")
    start = _parse_date(period_start)
    end = _parse_date(period_end)
    if start > end:
        raise PeriodicReportError("period_start must not be after period_end")
    selected = [
        deepcopy(dict(report))
        for report in daily_reports
        if report.get("period", {}).get("type") == "daily"
        and start.isoformat()
        <= str(report.get("period", {}).get("end") or "")
        <= end.isoformat()
    ]
    selected.sort(key=lambda report: str(report["period"]["end"]))
    if not selected:
        raise PeriodicReportError("aggregate report requires daily source reports")
    subject_keys = {
        (
            str(report.get("subject", {}).get("type") or ""),
            str(report.get("subject", {}).get("id") or ""),
        )
        for report in selected
    }
    if len(subject_keys) != 1:
        raise PeriodicReportError("daily source reports must share one subject")
    if any(validate_periodic_report(report)["status"] != "accepted" for report in selected):
        raise PeriodicReportError("aggregate source contains an invalid daily report")
    subject_type, subject_id = next(iter(subject_keys))
    first = selected[0]
    last = selected[-1]
    first_performance = first["sections"]["performance_and_positions"][
        "performance"
    ]
    last_performance = last["sections"]["performance_and_positions"][
        "performance"
    ]
    start_assets = _decimal(first_performance.get("start_total_assets_cny"))
    end_assets = _decimal(last_performance.get("end_total_assets_cny"))
    asset_change = (
        end_assets - start_assets
        if start_assets is not None and end_assets is not None
        else None
    )
    start_market_value = _decimal(
        first_performance.get("start_invested_market_value_cny")
    )
    end_market_value = _decimal(
        last_performance.get("end_invested_market_value_cny")
    )
    market_value_change = (
        end_market_value - start_market_value
        if start_market_value is not None and end_market_value is not None
        else None
    )
    start_close = _decimal(first_performance.get("start_close_cny"))
    end_close = _decimal(last_performance.get("end_close_cny"))
    close_change = (
        end_close - start_close
        if start_close is not None and end_close is not None
        else None
    )
    if subject_type == "instrument":
        asset_change = None
        start_assets = None
        end_assets = None
        primary_change = (
            close_change if close_change is not None else market_value_change
        )
        primary_start = (
            start_close if close_change is not None else start_market_value
        )
        performance_basis = (
            "instrument_close_price"
            if close_change is not None
            else (
                "instrument_position_market_value"
                if market_value_change is not None
                else "MISSING"
            )
        )
    else:
        start_close = None
        end_close = None
        close_change = None
        primary_change = (
            asset_change if asset_change is not None else market_value_change
        )
        primary_start = (
            start_assets if asset_change is not None else start_market_value
        )
        performance_basis = (
            "total_assets"
            if asset_change is not None
            else (
                "invested_market_value_ex_cash"
                if market_value_change is not None
                else "MISSING"
            )
        )
    opening_section = first["sections"]["performance_and_positions"]
    closing_section = last["sections"]["performance_and_positions"]
    opening_positions = list(
        opening_section.get("opening_positions")
        or opening_section.get("positions")
        or []
    )
    closing_positions = list(closing_section.get("positions") or [])
    changes = _position_changes(opening_positions, closing_positions)
    operations_by_id: dict[str, dict[str, Any]] = {}
    for report in selected:
        for operation in report["sections"]["operations_and_motives"].get(
            "operations", []
        ):
            operations_by_id[str(operation.get("operation_id") or "")] = deepcopy(
                dict(operation)
            )
    operations = sorted(
        operations_by_id.values(),
        key=lambda operation: str(operation.get("occurred_at") or ""),
    )
    episode_summaries = _daily_episode_summaries(operations)
    daily_changes = [
        {
            "trade_date": report["period"]["end"],
            "asset_change_cny": report["sections"]["performance_and_positions"][
                "performance"
            ].get("asset_change_cny"),
            "asset_change_pct": report["sections"]["performance_and_positions"][
                "performance"
            ].get("asset_change_pct"),
            "period_change_cny": report["sections"][
                "performance_and_positions"
            ]["performance"].get("period_change_cny"),
            "period_change_pct": report["sections"][
                "performance_and_positions"
            ]["performance"].get("period_change_pct"),
            "performance_basis": report["sections"][
                "performance_and_positions"
            ]["performance"].get("performance_basis"),
            "operation_count": report["sections"]["operations_and_motives"].get(
                "operation_count", 0
            ),
            "source_report_id": report["report_id"],
        }
        for report in selected
    ]
    quantified = [
        item
        for item in daily_changes
        if _decimal(item.get("period_change_cny")) is not None
    ]
    best_day = (
        max(quantified, key=lambda item: _decimal(item["period_change_cny"]) or ZERO)
        if quantified
        else None
    )
    worst_day = (
        min(quantified, key=lambda item: _decimal(item["period_change_cny"]) or ZERO)
        if quantified
        else None
    )
    period_label = "周" if period_type == "weekly" else "月"
    position_summary = (
        f"本{period_label}共有 {len(operations)} 笔操作；"
        f"期末持仓 {len(closing_positions)} 个，"
        f"新增/加仓 {sum(item['status'] in {'opened', 'added'} for item in changes)} 个，"
        f"减仓/退出 {sum(item['status'] in {'reduced', 'exited'} for item in changes)} 个。"
    )
    decision_context = {
        "framework": "four_layer_periodic_review_v1",
        "report_depth": _PERIOD_DEPTHS[period_type],
        "fundamental_and_valuation": _aggregate_context_layer(
            selected,
            layer_name="fundamental_and_valuation",
            period_type=period_type,
        ),
        "market_and_sector": _aggregate_context_layer(
            selected,
            layer_name="market_and_sector",
            period_type=period_type,
        ),
        "technical_and_trend": _aggregate_context_layer(
            selected,
            layer_name="technical_and_trend",
            period_type=period_type,
        ),
        "position_and_execution": {
            "status": "available",
            "scope": f"natural_{period_type}_synthesis",
            "summary": position_summary,
            "observations": [
                {
                    "type": "fact",
                    "text": (
                        f"{item['name']}（{item['ts_code']}）"
                        f"{item['opening_quantity']} → {item['closing_quantity']} 股，"
                        f"状态 {item['status']}。"
                    ),
                    "source_ref": ",".join(item["source_refs"]),
                }
                for item in changes
                if item["status"] != "held"
            ],
            "position_changes": changes,
            "episode_summaries": episode_summaries,
            "source_refs": sorted(
                {
                    ref
                    for item in changes
                    for ref in item.get("source_refs", [])
                }
            ),
        },
        "timing_policy": (
            "操作动机沿用各日报在操作时点冻结的 system_inference；"
            "本周期表现、归因和建议只使用期末 cutoff 之前的信息。"
        ),
    }
    report_cutoff_at = _report_cutoff(end).isoformat(timespec="seconds")
    recommendation = deepcopy(last["sections"]["recommendation"])
    recommendation["time_horizon"] = (
        "next_natural_week" if period_type == "weekly" else "next_natural_month"
    )
    recommendation["data_timestamp"] = report_cutoff_at
    recommendation["report_cutoff_at"] = report_cutoff_at
    change_unit = "元/股" if performance_basis == "instrument_close_price" else "元"
    change_description = (
        "收盘价"
        if performance_basis == "instrument_close_price"
        else "资产或持仓市值"
    )
    recommendation["rationale"] = [
        {
            "type": "fact",
            "text": (
                f"本{period_label}独立汇总 {len(selected)} 个交易日，"
                f"按 {performance_basis} 口径的{change_description}变动 "
                f"{_decimal_text(primary_change, places=4)} {change_unit}，"
                f"共 {len(operations)} 笔操作。"
            ),
        },
        *list(recommendation.get("rationale", [])),
    ]
    performance = {
        "type": "fact",
        "comparison_date": first_performance.get("comparison_date"),
        "start_total_assets_cny": _decimal_text(start_assets, places=2),
        "end_total_assets_cny": _decimal_text(end_assets, places=2),
        "asset_change_cny": _decimal_text(asset_change, places=2),
        "asset_change_pct": _decimal_text(_pct(asset_change, start_assets), places=2),
        "start_close_cny": _decimal_text(start_close, places=4),
        "end_close_cny": _decimal_text(end_close, places=4),
        "start_price_date": first_performance.get("start_price_date"),
        "end_price_date": last_performance.get("end_price_date"),
        "price_change_cny": _decimal_text(close_change, places=4),
        "price_change_pct": _decimal_text(
            _pct(close_change, start_close),
            places=2,
        ),
        "start_invested_market_value_cny": _decimal_text(
            start_market_value,
            places=2,
        ),
        "end_invested_market_value_cny": _decimal_text(
            end_market_value,
            places=2,
        ),
        "invested_market_value_change_cny": _decimal_text(
            market_value_change,
            places=2,
        ),
        "invested_market_value_change_pct": _decimal_text(
            _pct(market_value_change, start_market_value),
            places=2,
        ),
        "performance_basis": performance_basis,
        "period_change_cny": _decimal_text(primary_change, places=2),
        "period_change_pct": _decimal_text(
            _pct(primary_change, primary_start),
            places=2,
        ),
        "cash_change_cny": _decimal_text(
            (
                (_decimal(closing_section.get("cash", {}).get("amount_cny")) or ZERO)
                - (
                    _decimal(
                        opening_section.get("opening_cash", {}).get("amount_cny")
                    )
                    or ZERO
                )
            )
            if closing_section.get("cash")
            and opening_section.get("opening_cash")
            else None,
            places=2,
        ),
        "valuation_complete": all(
            bool(
                report["sections"]["performance_and_positions"]["performance"].get(
                    "valuation_complete"
                )
            )
            for report in selected
        ),
        "covered_trading_days": [report["period"]["end"] for report in selected],
        "calculation_method": (
            (
                "使用首个日级报告的期初收盘价与最后一个日级报告的期末"
                "收盘价计算标的周期表现，持仓市值变化单独呈现，避免期间"
                "买卖数量变化冒充收益；"
                if performance_basis == "instrument_close_price"
                else (
                    "期初无可比收盘价或无持仓，周期收益率保持 MISSING；"
                    "仅呈现标的持仓市值变化，并明确该变化包含买卖数量影响，"
                    "不能当作投资收益；"
                    if subject_type == "instrument"
                    else (
                        "使用首个日级报告的期初资产与最后一个日级报告的期末"
                        "资产对账；现金快照缺失时保持总资产为 MISSING，并使用"
                        "不含现金的持仓市值作为明确标注的次级变化口径；"
                    )
                )
            )
            + "操作序列按 operation_id 去重，日级事实不重新解释。"
        ),
        "source_refs": [f"periodic_report:{report['report_id']}" for report in selected],
    }
    risks = deepcopy(closing_section.get("risk_change", {}))
    risks["period_start"] = start.isoformat()
    risks["period_end"] = end.isoformat()
    risks["position_changes"] = changes
    judgments = (
        [
            {
                "type": "inference",
                "status": (
                    "needs_improvement"
                    if (_decimal(item.get("net_round_trip_pnl_cny")) or ZERO) < ZERO
                    else "mixed"
                ),
                "text": item.get("assessment"),
                "source_refs": item.get("source_refs", []),
            }
            for item in episode_summaries
        ]
        or [
            {
                "type": "inference",
                "status": "no_trade",
                "text": f"本{period_label}没有操作，不构造虚假动机或执行评价。",
                "source_refs": [],
            }
        ]
    )
    daily_limits = sorted(
        {
            str(item)
            for report in selected
            for item in report["sections"]["risks_invalidation_and_missing"].get(
                "data_limitations", []
            )
        }
    )
    identity = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "period_type": period_type,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
    }
    report_id = "periodic_" + _sha256_text(_canonical_json(identity))[:32]
    generated_at = max(
        (str(report.get("generated_at") or "") for report in selected),
        default=None,
    )
    headline_performance_label = {
        "total_assets": "总资产",
        "invested_market_value_ex_cash": "持仓市值（不含现金）",
        "instrument_close_price": "收盘价",
        "instrument_position_market_value": "标的持仓市值",
    }.get(performance_basis, "表现")
    headline_change_pct = (
        performance["period_change_pct"]
        if performance["period_change_pct"] is not None
        else "MISSING"
    )
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_id": report_id,
        "status": "ready",
        "subject": deepcopy(last["subject"]),
        "period": {
            "type": period_type,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "report_cutoff_at": report_cutoff_at,
            "covered_trading_dates": [report["period"]["end"] for report in selected],
        },
        "generated_at": generated_at,
        "headline": (
            f"{last['subject']['name']}本{period_label}"
            f"{headline_performance_label}"
            f"变动 {headline_change_pct}%，共 {len(operations)} 笔操作；"
            f"下一周期建议 {recommendation.get('action')}。"
        ),
        "sections": {
            "performance_and_positions": {
                "performance": performance,
                "opening_cash": opening_section.get("opening_cash"),
                "cash": closing_section.get("cash"),
                "opening_positions": opening_positions,
                "positions": closing_positions,
                "risk_change": risks,
                "period_attribution": {
                    "daily_changes": daily_changes,
                    "best_day": best_day,
                    "worst_day": worst_day,
                    "operation_count": len(operations),
                },
            },
            "decision_context": decision_context,
            "operations_and_motives": {
                "operation_count": len(operations),
                "operations": operations,
                "episode_summaries": episode_summaries,
            },
            "review_judgments": judgments,
            "recommendation": recommendation,
            "risks_invalidation_and_missing": {
                "major_risks": recommendation.get("major_downside_risks", []),
                "invalidation_conditions": recommendation.get(
                    "invalidation_conditions", []
                ),
                "missing_inputs": recommendation.get("important_missing_inputs", []),
                "data_limitations": daily_limits,
            },
        },
        "source": {
            "source_path": "derived from validated daily periodic reports",
            "source_sha256": last.get("source", {}).get("source_sha256"),
            "source_observed_through": max(
                (
                    str(report.get("source", {}).get("source_observed_through") or "")
                    for report in selected
                ),
                default=None,
            ),
            "context_fetched_at": max(
                (
                    str(report.get("source", {}).get("context_fetched_at") or "")
                    for report in selected
                ),
                default=None,
            ),
            "review_sidecar": "investment_review.sqlite3 (derived report state)",
            "daily_report_ids": [report["report_id"] for report in selected],
            "source_refs": [
                f"investment_review.sqlite3#periodic_reports:{report['report_id']}"
                for report in selected
            ],
        },
        "safety": {
            "orders_executed": False,
            "broker_accessed": False,
            "guaranteed_return_claims": False,
            "recommendation_is_not_an_order": True,
        },
    }
    _attach_reader_narrative(report)
    report["content_id"] = "sha256:" + _sha256_text(_canonical_json(report))
    validation = validate_periodic_report(report)
    if validation["status"] != "accepted":
        raise PeriodicReportError(
            "aggregate periodic report validation failed: "
            + ", ".join(validation["errors"])
        )
    return report


def validate_periodic_report(report: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    schema_version = report.get("schema_version")
    if schema_version not in SUPPORTED_REPORT_SCHEMA_VERSIONS:
        errors.append("unsupported_schema_version")
    subject = report.get("subject")
    if not isinstance(subject, Mapping) or subject.get("type") not in _SUBJECT_TYPES:
        errors.append("invalid_subject")
    elif not str(subject.get("name") or "").strip():
        errors.append("missing_subject_name")
    period = report.get("period")
    if not isinstance(period, Mapping) or period.get("type") not in _PERIOD_TYPES:
        errors.append("invalid_period")
    sections = report.get("sections")
    if not isinstance(sections, Mapping):
        errors.append("missing_sections")
        sections = {}
    decision_context = sections.get("decision_context")
    if not isinstance(decision_context, Mapping):
        errors.append("missing_decision_context")
    else:
        period_type = (
            str(period.get("type") or "")
            if isinstance(period, Mapping)
            else ""
        )
        expected_depth = _PERIOD_DEPTHS.get(period_type)
        if (
            expected_depth is not None
            and decision_context.get("report_depth") != expected_depth
        ):
            errors.append(f"invalid_{period_type}_context_depth")
        for layer_name in (
            "fundamental_and_valuation",
            "market_and_sector",
            "technical_and_trend",
            "position_and_execution",
        ):
            layer = decision_context.get(layer_name)
            if not isinstance(layer, Mapping):
                errors.append(f"missing_context_layer_{layer_name}")
            elif not str(layer.get("summary") or "").strip():
                errors.append(f"missing_context_summary_{layer_name}")
    recommendation = sections.get("recommendation")
    if not isinstance(recommendation, Mapping):
        errors.append("missing_recommendation")
    else:
        if recommendation.get("action") not in _ACTIONS:
            errors.append("invalid_recommendation_action")
        if not recommendation.get("target_position"):
            errors.append("missing_target_position")
        if not recommendation.get("major_downside_risks"):
            errors.append("missing_recommendation_risks")
        if not recommendation.get("invalidation_conditions"):
            errors.append("missing_invalidation_conditions")
        if recommendation.get("orders_executed") is not False:
            errors.append("orders_executed_not_false")
        if recommendation.get("guaranteed_return") is not False:
            errors.append("guaranteed_return_not_false")
        if str(recommendation.get("data_timestamp") or "") > str(
            period.get("report_cutoff_at") if isinstance(period, Mapping) else ""
        ):
            errors.append("recommendation_uses_post_cutoff_data")
    operations_section = sections.get("operations_and_motives")
    operations = (
        operations_section.get("operations", [])
        if isinstance(operations_section, Mapping)
        else []
    )
    for operation in operations:
        if not isinstance(operation, Mapping):
            errors.append("invalid_operation")
            continue
        if not str(operation.get("name") or "").strip():
            errors.append("missing_operation_name")
        if operation.get("fee_status") not in {
            "reported_actual",
            "rule_backfilled",
            "formal_exemption",
            "unknown",
        }:
            errors.append("invalid_fee_provenance")
        if (
            operation.get("fee_status") == "rule_backfilled"
            and not operation.get("fee_rule")
        ):
            errors.append("rule_backfilled_fee_missing_rule")
        motive = operation.get("motive")
        if not isinstance(motive, Mapping):
            errors.append("missing_motive")
            continue
        if operation.get("decision_status") == "not_recorded":
            if motive.get("label") != "system_inference":
                errors.append("missing_system_inference_label")
            if not motive.get("alternative_explanations"):
                errors.append("missing_alternative_explanation")
            if motive.get("confidence") not in {"high", "medium", "low"}:
                errors.append("invalid_motive_confidence")
        if motive.get("uses_later_information") is not False:
            errors.append("motive_uses_later_information")
        if str(motive.get("input_cutoff_at") or "") > str(
            operation.get("occurred_at") or ""
        ):
            errors.append("motive_cutoff_after_operation")
        for observation in motive.get("supporting_observations", []):
            if not isinstance(observation, Mapping):
                errors.append("invalid_motive_observation")
                continue
            observed_at = str(observation.get("observed_at") or "")
            if observed_at:
                try:
                    observation_time = _aware_timestamp(observed_at)
                    operation_time = _aware_timestamp(
                        str(operation.get("occurred_at") or "")
                    )
                except PeriodicReportError:
                    errors.append("invalid_motive_observation_time")
                else:
                    if observation_time > operation_time:
                        errors.append("motive_observation_after_operation")
    safety = report.get("safety")
    if not isinstance(safety, Mapping):
        errors.append("missing_safety")
    else:
        for field in (
            "orders_executed",
            "broker_accessed",
            "guaranteed_return_claims",
        ):
            if safety.get(field) is not False:
                errors.append(f"{field}_not_false")
    if schema_version == REPORT_SCHEMA_VERSION:
        errors.extend(validate_periodic_narrative(report))
    return {
        "status": "accepted" if not errors else "blocked",
        "errors": sorted(set(errors)),
    }


def render_periodic_report_markdown(report: Mapping[str, Any]) -> str:
    if report.get("schema_version") == REPORT_SCHEMA_VERSION:
        return render_reader_report_markdown(report)

    subject = report["subject"]
    period = report["period"]
    sections = report["sections"]
    performance_section = sections["performance_and_positions"]
    performance = performance_section["performance"]
    cash = performance_section.get("cash") or {}
    risk = performance_section["risk_change"]
    context = sections["decision_context"]
    recommendation = sections["recommendation"]
    operations = sections["operations_and_motives"]["operations"]
    episode_summaries = sections["operations_and_motives"].get(
        "episode_summaries", []
    )
    period_title = {
        "daily": "日报",
        "weekly": "周报",
        "monthly": "月报",
    }.get(str(period.get("type") or ""), "周期报告")
    context_title = {
        "daily": "日报增量",
        "weekly": "自然周汇总",
        "monthly": "自然月汇总",
    }.get(str(period.get("type") or ""), "周期汇总")
    subject_label = (
        subject["name"]
        if subject["type"] == "portfolio"
        else f"{subject['name']}（{subject['id']}）"
    )
    fee_labels = {
        "reported_actual": "账本实收",
        "rule_backfilled": "规则计算/回填",
        "formal_exemption": "正式豁免",
        "unknown": "来源未知",
    }

    def visible(value: object, fallback: str = "MISSING") -> object:
        return fallback if value is None or value == "" else value

    if subject["type"] == "instrument":
        opening_quantity = _selected_quantity(
            performance_section.get("opening_positions") or []
        )
        closing_quantity = _selected_quantity(
            performance_section.get("positions") or []
        )
        instrument_change_unit = (
            "元/股"
            if performance.get("performance_basis") == "instrument_close_price"
            else "元"
        )
        instrument_change_pct = (
            performance.get("period_change_pct")
            if performance.get("period_change_pct") is not None
            else "MISSING"
        )
        price_line = (
            f"- 标的收盘价：{visible(performance.get('start_close_cny'))} → "
            f"{visible(performance.get('end_close_cny'))} 元/股，变动 "
            f"{visible(performance.get('price_change_cny'))} 元/股"
            f"（{visible(performance.get('price_change_pct'))}%）。"
            if performance.get("performance_basis") == "instrument_close_price"
            else (
                "- 标的收盘价：期初可比价格 MISSING；不计算收益率，"
                "以下持仓市值变化包含买卖数量影响。"
            )
        )
        performance_lines = [
            price_line,
            (
                f"- 持仓数量：{_decimal_text(opening_quantity)} → "
                f"{_decimal_text(closing_quantity)} 股；持仓市值 "
                f"{visible(performance.get('start_invested_market_value_cny'))} → "
                f"{visible(performance.get('end_invested_market_value_cny'))} 元。"
            ),
            (
                f"- 可核对变化口径："
                f"`{performance.get('performance_basis', 'MISSING')}`；"
                f"{visible(performance.get('period_change_cny'))} "
                f"{instrument_change_unit}"
                f"（{instrument_change_pct}%）。"
            ),
            (
                f"- 组合上下文：现金 {visible(cash.get('amount_cny'))} 元，"
                f"现金权重 {visible(risk.get('cash_weight_pct'))}%，"
                f"最大单一标的 "
                f"{visible(risk.get('top_position_weight_pct'))}%。"
            ),
            (
                f"- 现金一致性：`{cash.get('consistency_status', 'unknown')}`；"
                f"费用来源完整性 "
                f"`{cash.get('fee_provenance_status', 'unknown')}`。"
            ),
            f"- 计算说明：{performance.get('calculation_method')}",
        ]
    else:
        performance_lines = [
            (
                f"- 总资产：{visible(performance.get('start_total_assets_cny'))} → "
                f"{visible(performance.get('end_total_assets_cny'))} 元，变动 "
                f"{visible(performance.get('asset_change_cny'))} 元"
                f"（{visible(performance.get('asset_change_pct'))}%）。"
            ),
            (
                f"- 可核对变化口径："
                f"`{performance.get('performance_basis', 'MISSING')}`；"
                f"{visible(performance.get('period_change_cny'))} 元"
                f"（{visible(performance.get('period_change_pct'))}%）。"
            ),
            (
                f"- 现金：{visible(cash.get('amount_cny'))} 元，组合权重 "
                f"{visible(risk.get('cash_weight_pct'))}%，状态 "
                f"`{cash.get('status', 'MISSING')}`。"
            ),
            (
                f"- 现金一致性：`{cash.get('consistency_status', 'unknown')}`；"
                f"费用来源完整性 "
                f"`{cash.get('fee_provenance_status', 'unknown')}`。"
            ),
            (
                f"- 集中度：最大单一标的 "
                f"{visible(risk.get('top_position_weight_pct'))}%，前三大合计 "
                f"{visible(risk.get('top3_weight_pct'))}%，状态 "
                f"`{risk.get('concentration_status')}`。"
            ),
            f"- 计算说明：{performance.get('calculation_method')}",
        ]
    lines = [
        f"# {subject_label} {period['end']} {period_title}",
        "",
        f"> {report['headline']}",
        "",
        "## 1. 本期结论摘要",
        "",
        f"- 报告对象：{subject_label}；类型 `{subject['type']}`",
        f"- 报告截止：`{period['report_cutoff_at']}`",
        (
            f"- 直接建议：`{recommendation['action']}`；"
            f"{recommendation['target_position'].get('target_position_note')}"
        ),
        f"- 建议置信度：`{recommendation['confidence']}`；本报告不会执行订单。",
        "",
        "## 2. 收益、持仓、现金和风险变化",
        "",
        *performance_lines,
        "",
        f"## 3. 四层决策上下文（{context_title}）",
        "",
    ]
    attribution = sections["performance_and_positions"].get("period_attribution")
    if isinstance(attribution, Mapping):
        best = attribution.get("best_day") or {}
        worst = attribution.get("worst_day") or {}
        attribution_unit = (
            "元/股"
            if performance.get("performance_basis") == "instrument_close_price"
            else "元"
        )
        lines[-2:-2] = [
            (
                f"- 周期归因：覆盖 "
                f"{len(attribution.get('daily_changes', []))} 个交易日、"
                f"{attribution.get('operation_count', 0)} 笔操作；"
                f"最佳日 {visible(best.get('trade_date'))} "
                f"{visible(best.get('period_change_cny'))} {attribution_unit}，"
                f"最弱日 {visible(worst.get('trade_date'))} "
                f"{visible(worst.get('period_change_cny'))} "
                f"{attribution_unit}。"
            ),
            "",
        ]
    layer_labels = (
        ("fundamental_and_valuation", "基本面与估值"),
        ("market_and_sector", "大盘与板块"),
        ("technical_and_trend", "技术与趋势"),
        ("position_and_execution", "仓位与执行"),
    )
    for key, label in layer_labels:
        layer = context[key]
        lines.extend(
            [
                f"### 3.{len([line for line in lines if line.startswith('### 3.')]) + 1} {label}",
                "",
                f"- 状态：`{visible(layer.get('status'))}`；"
                f"{visible(layer.get('summary'))}",
            ]
        )
        if layer.get("portfolio_scope_note"):
            lines.append(f"- 范围说明：{layer.get('portfolio_scope_note')}")
        for observation in layer.get("observations", [])[:4]:
            lines.append(
                f"- {observation.get('type', 'unknown')}：{observation.get('text')}"
            )
        lines.append("")
    lines.extend(
        [
            "## 4. 操作与交易动机复盘",
            "",
        ]
    )
    if not operations:
        lines.append("- 本期无持仓变动操作；报告仍保留表现、风险与建议。")
    for summary in episode_summaries:
        fee_basis = "、".join(
            fee_labels.get(str(item), str(item))
            for item in summary.get("fee_statuses", [])
        )
        lines.extend(
            [
                f"### {summary.get('name')}（{summary.get('ts_code')}）本期执行摘要",
                "",
                (
                    f"- 仓位路径：{visible(summary.get('opening_quantity'))} → "
                    f"{visible(summary.get('peak_quantity'))} → "
                    f"{visible(summary.get('closing_quantity'))} 股；峰值较期初 "
                    f"{visible(summary.get('peak_increase_pct'))}%。"
                ),
            ]
        )
        if summary.get("round_trip_closed"):
            lines.append(
                f"- 闭环结果：毛价差 "
                f"{visible(summary.get('gross_round_trip_pnl_cny'))} 元；"
                f"费用 {visible(summary.get('fee_total_cny'))} 元（{fee_basis}）；"
                f"净结果 {visible(summary.get('net_round_trip_pnl_cny'))} 元。"
            )
        else:
            lines.append(
                f"- 当日非闭环：买入 {visible(summary.get('bought_quantity'))} 股、"
                f"卖出 {visible(summary.get('sold_quantity'))} 股；"
                f"已知费用 {visible(summary.get('fee_total_cny'))} 元"
                f"（{fee_basis}），"
                "不计算虚假的日内净收益。"
            )
        lines.extend([f"- 执行判断：{summary.get('assessment')}", ""])
    if subject["type"] == "portfolio" and operations:
        lines.extend(["### 组合逐笔动机简表", ""])
        for operation in operations:
            local_time = _aware_timestamp(operation["occurred_at"]).astimezone(
                SHANGHAI
            )
            motive = operation["motive"]
            lines.append(
                f"- {local_time.strftime('%H:%M:%S')} "
                f"{operation['side']} "
                f"{operation.get('name') or operation['ts_code']}"
                f"（{operation['ts_code']}）{operation['quantity']} 股："
                f"{motive.get('most_likely_motive', '见已记录 Decision。')}"
            )
        lines.extend(
            [
                "",
                "- 逐笔费用、替代解释和时点证据保留在同名 JSON/API 详情中；"
                "组合报告只呈现当前周期必要增量，避免重复铺陈。",
                "",
            ]
        )
    else:
        for operation in operations:
            motive = operation["motive"]
            evaluation = operation["retrospective_evaluation"]
            operation_label = (
                f"{operation.get('name') or operation['ts_code']}"
                f"（{operation['ts_code']}）"
            )
            fee_label = fee_labels.get(
                str(operation.get("fee_status") or ""), "来源未知"
            )
            fee_rule = (
                f"，规则 `{operation.get('fee_rule')}`"
                if operation.get("fee_rule")
                else ""
            )
            local_time = _aware_timestamp(operation["occurred_at"]).astimezone(
                SHANGHAI
            )
            lines.extend(
                [
                    (
                        f"### {local_time.isoformat(timespec='seconds')} "
                        f"· {operation['side']} {operation_label}"
                    ),
                    "",
                    (
                        f"- 操作事实：{operation['quantity']} 股 × "
                        f"{operation['price_cny']} 元；持仓 "
                        f"{visible(operation.get('quantity_before'))} → "
                        f"{visible(operation.get('quantity_after'))}。"
                    ),
                    (
                        f"- 费用：{visible(operation.get('fee_cny'))} 元；"
                        f"来源 `{fee_label}`{fee_rule}。"
                    ),
                    (
                        f"- 动机标签：`{motive['label']}`；置信度 "
                        f"`{motive.get('confidence', 'recorded')}`。"
                    ),
                    (
                        f"- 最可能动机："
                        f"{motive.get('most_likely_motive', '见已记录 Decision。')}"
                    ),
                    (
                        f"- 替代解释："
                        f"{'；'.join(motive.get('alternative_explanations', [])) or '无。'}"
                    ),
                    (
                        f"- 事后评价：{evaluation['narrative']} 毛价差 "
                        f"{visible(evaluation.get('gross_mark_to_close_cny'))} 元。"
                    ),
                    "",
                ]
            )
    lines.extend(
        [
            "## 5. 哪些判断或执行合理，哪些需要改进",
            "",
            *[
                f"- `{item['status']}`：{visible(item.get('text'))}"
                for item in sections["review_judgments"]
            ],
            "",
            (
                f"## 6. {subject_label}个性化交易建议与建议仓位"
                if subject["type"] == "instrument"
                else "## 6. 个性化交易建议与建议仓位"
            ),
            "",
            f"- 动作：`{recommendation['action']}`",
            f"- 仓位：`{json.dumps(recommendation['target_position'], ensure_ascii=False)}`",
            f"- 期限：{recommendation['time_horizon']}",
            *[
                f"- 依据（{item['type']}）：{item['text']}"
                for item in recommendation["rationale"]
            ],
            "",
            "## 7. 主要依据、风险、失效条件和数据缺失",
            "",
            *[
                f"- 主要风险：{item}"
                for item in recommendation["major_downside_risks"]
            ],
            *[
                f"- 失效条件：{item}"
                for item in recommendation["invalidation_conditions"]
            ],
            f"- 缺失输入：{', '.join(recommendation['important_missing_inputs'])}",
            "",
            "<details>",
            "<summary>最小来源与时间说明</summary>",
            "",
            f"- 正式数据库 SHA-256：`{report['source']['source_sha256']}`",
            f"- 数据观察至："
            f"`{visible(report['source']['source_observed_through'])}`",
            f"- 来源：{', '.join(report['source']['source_refs'])}",
            "- 动机推断只使用各操作时点以前的信息；当日收盘结果只进入事后评价。",
            "- 建议只使用报告 cutoff 及以前的账本与市场信息。",
            "- 规则回填费用会明确标注，不冒充券商实收；正式豁免与来源未知分开显示。",
            "",
            "</details>",
            "",
        ]
    )
    return "\n".join(lines)


class PeriodicReportStore:
    """Small additive report table inside the selected review sidecar."""

    def __init__(self, path: str | Path, *, read_only: bool = False) -> None:
        self.path = Path(path).expanduser().resolve(strict=False)
        self.read_only = bool(read_only)

    @contextmanager
    def _connect(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        if write:
            if self.read_only:
                raise PeriodicReportError("periodic report store is read-only")
            connection = sqlite3.connect(self.path)
        else:
            if not self.path.is_file():
                raise PeriodicReportError("periodic report sidecar does not exist")
            suffix = "?mode=ro&immutable=1" if self.read_only else "?mode=ro"
            connection = sqlite3.connect(self.path.as_uri() + suffix, uri=True)
        connection.row_factory = sqlite3.Row
        if not write:
            connection.execute("PRAGMA query_only = ON")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        if not self.path.is_file():
            raise PeriodicReportError(
                "review sidecar must exist before periodic report initialization"
            )
        with self._connect(write=True) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS periodic_reports (
                    report_id TEXT PRIMARY KEY,
                    identity_key TEXT NOT NULL UNIQUE,
                    schema_version TEXT NOT NULL,
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    period_type TEXT NOT NULL,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    report_cutoff_at TEXT NOT NULL,
                    generated_at TEXT,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_periodic_reports_lookup
                ON periodic_reports(
                    subject_type, subject_id, period_type, period_end DESC,
                    generated_at DESC
                );
                CREATE TABLE IF NOT EXISTS periodic_report_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            connection.execute(
                """
                INSERT INTO periodic_report_meta(key, value)
                VALUES ('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (PERIODIC_STORE_SCHEMA_VERSION,),
            )
            connection.commit()

    @staticmethod
    def _identity_key(report: Mapping[str, Any]) -> str:
        return "|".join(
            [
                str(report["subject"]["type"]),
                str(report["subject"]["id"]),
                str(report["period"]["type"]),
                str(report["period"]["start"]),
                str(report["period"]["end"]),
            ]
        )

    def save(self, report: Mapping[str, Any]) -> dict[str, Any]:
        validation = validate_periodic_report(report)
        if validation["status"] != "accepted":
            raise PeriodicReportError(
                "cannot store invalid periodic report: "
                + ", ".join(validation["errors"])
            )
        payload = _canonical_json(dict(report))
        payload_sha = _sha256_text(payload)
        identity_key = self._identity_key(report)
        with self._connect(write=True) as connection:
            existing = connection.execute(
                """
                SELECT report_id, payload_sha256 FROM periodic_reports
                WHERE report_id = ? OR identity_key = ?
                   OR (
                     subject_type = ? AND subject_id = ? AND period_type = ?
                     AND period_start = ? AND period_end = ?
                   )
                ORDER BY CASE WHEN report_id = ? THEN 0 ELSE 1 END
                LIMIT 1
                """,
                (
                    report["report_id"],
                    identity_key,
                    report["subject"]["type"],
                    report["subject"]["id"],
                    report["period"]["type"],
                    report["period"]["start"],
                    report["period"]["end"],
                    report["report_id"],
                ),
            ).fetchone()
            if existing is not None:
                if existing["payload_sha256"] == payload_sha:
                    return {
                        "status": "skipped",
                        "report_id": existing["report_id"],
                        "payload_sha256": payload_sha,
                    }
                now = datetime.now(timezone.utc).isoformat(
                    timespec="seconds"
                ).replace("+00:00", "Z")
                connection.execute(
                    """
                    UPDATE periodic_reports
                    SET report_id = ?, identity_key = ?, schema_version = ?,
                        report_cutoff_at = ?, generated_at = ?, status = ?,
                        payload_json = ?, payload_sha256 = ?, created_at = ?
                    WHERE report_id = ?
                    """,
                    (
                        report["report_id"],
                        identity_key,
                        report["schema_version"],
                        report["period"]["report_cutoff_at"],
                        report.get("generated_at"),
                        report.get("status", "ready"),
                        payload,
                        payload_sha,
                        now,
                        existing["report_id"],
                    ),
                )
                connection.commit()
                return {
                    "status": "updated",
                    "report_id": report["report_id"],
                    "payload_sha256": payload_sha,
                }
            now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
                "+00:00", "Z"
            )
            connection.execute(
                """
                INSERT INTO periodic_reports(
                    report_id, identity_key, schema_version, subject_type,
                    subject_id, period_type, period_start, period_end,
                    report_cutoff_at, generated_at, status, payload_json,
                    payload_sha256, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report["report_id"],
                    identity_key,
                    report["schema_version"],
                    report["subject"]["type"],
                    report["subject"]["id"],
                    report["period"]["type"],
                    report["period"]["start"],
                    report["period"]["end"],
                    report["period"]["report_cutoff_at"],
                    report.get("generated_at"),
                    report.get("status", "ready"),
                    payload,
                    payload_sha,
                    now,
                ),
            )
            connection.commit()
        return {
            "status": "inserted",
            "report_id": report["report_id"],
            "payload_sha256": payload_sha,
        }

    def _table_exists(self, connection: sqlite3.Connection) -> bool:
        return (
            connection.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type='table' AND name='periodic_reports'
                """
            ).fetchone()
            is not None
        )

    def list(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        period_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if not self._table_exists(connection):
                return []
            clauses: list[str] = []
            parameters: list[object] = []
            for column, value in (
                ("subject_type", subject_type),
                ("subject_id", subject_id),
                ("period_type", period_type),
            ):
                if value is not None:
                    clauses.append(f"{column} = ?")
                    parameters.append(value)
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            parameters.append(limit)
            rows = connection.execute(
                f"""
                SELECT payload_json FROM periodic_reports
                {where}
                ORDER BY period_end DESC, generated_at DESC, report_id
                LIMIT ?
                """,
                tuple(parameters),
            )
            reports = [json.loads(row["payload_json"]) for row in rows]
        return [
            {
                "report_id": report["report_id"],
                "schema_version": report.get("schema_version"),
                "status": report.get("status"),
                "subject": report["subject"],
                "period": report["period"],
                "generated_at": report.get("generated_at"),
                "headline": report.get("headline"),
                "reader_report": (
                    {
                        "schema_version": report["reader_report"].get(
                            "schema_version"
                        ),
                        "central_judgment": report["reader_report"].get(
                            "central_judgment"
                        ),
                        "action_plan": report["reader_report"].get(
                            "action_plan"
                        ),
                    }
                    if isinstance(report.get("reader_report"), Mapping)
                    else None
                ),
                "recommendation": report["sections"].get("recommendation"),
                "risk_change": report["sections"]
                .get("performance_and_positions", {})
                .get("risk_change"),
                "operation_count": report["sections"]
                .get("operations_and_motives", {})
                .get("operation_count", 0),
            }
            for report in reports
        ]

    def get(self, report_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            if not self._table_exists(connection):
                raise PeriodicReportError("periodic report table is not initialized")
            row = connection.execute(
                "SELECT payload_json, payload_sha256 FROM periodic_reports WHERE report_id = ?",
                (report_id,),
            ).fetchone()
        if row is None:
            raise PeriodicReportError("periodic report not found")
        payload = str(row["payload_json"])
        if _sha256_text(payload) != row["payload_sha256"]:
            raise PeriodicReportError("periodic report payload hash mismatch")
        report = json.loads(payload)
        validation = validate_periodic_report(report)
        if validation["status"] != "accepted":
            raise PeriodicReportError("stored periodic report failed validation")
        return report

    def get_by_identity(
        self,
        *,
        subject_type: str,
        subject_id: str,
        period_type: str,
        period_start: str,
        period_end: str,
    ) -> dict[str, Any] | None:
        identity_key = "|".join(
            [
                subject_type,
                subject_id,
                period_type,
                period_start,
                period_end,
            ]
        )
        with self._connect() as connection:
            if not self._table_exists(connection):
                return None
            row = connection.execute(
                """
                SELECT payload_json, payload_sha256
                FROM periodic_reports
                WHERE identity_key = ?
                """,
                (identity_key,),
            ).fetchone()
        if row is None:
            return None
        payload = str(row["payload_json"])
        if _sha256_text(payload) != row["payload_sha256"]:
            raise PeriodicReportError("periodic report payload hash mismatch")
        report = json.loads(payload)
        validation = validate_periodic_report(report)
        if validation["status"] != "accepted":
            raise PeriodicReportError("stored periodic report failed validation")
        return report

    def count(self) -> int:
        with self._connect() as connection:
            if not self._table_exists(connection):
                return 0
            return int(
                connection.execute("SELECT COUNT(*) FROM periodic_reports").fetchone()[
                    0
                ]
            )

    def set_meta(self, key: str, value: Mapping[str, Any] | str) -> None:
        if not str(key).strip():
            raise PeriodicReportError("periodic report meta key must not be blank")
        payload = (
            _canonical_json(dict(value))
            if isinstance(value, Mapping)
            else str(value)
        )
        with self._connect(write=True) as connection:
            connection.execute(
                """
                INSERT INTO periodic_report_meta(key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(key), payload),
            )
            connection.commit()

    def get_meta(self, key: str) -> str | None:
        with self._connect() as connection:
            if not self._table_exists(connection):
                return None
            meta_exists = connection.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type='table' AND name='periodic_report_meta'
                """
            ).fetchone()
            if meta_exists is None:
                return None
            row = connection.execute(
                "SELECT value FROM periodic_report_meta WHERE key = ?",
                (str(key),),
            ).fetchone()
        return str(row["value"]) if row is not None else None

    def get_json_meta(self, key: str) -> dict[str, Any] | None:
        payload = self.get_meta(key)
        if payload is None:
            return None
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise PeriodicReportError("periodic report meta JSON is invalid") from exc
        if not isinstance(value, Mapping):
            raise PeriodicReportError("periodic report meta JSON must be an object")
        return dict(value)


def _write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


PeriodicContextResolver = Callable[..., Mapping[str, Any]]


def _trading_dates(
    connection: sqlite3.Connection,
    *,
    start_date: date,
    end_date: date,
) -> list[date]:
    if start_date > end_date:
        raise PeriodicReportError("start_date must not be after end_date")
    return [
        date.fromisoformat(str(row[0]))
        for row in connection.execute(
            """
            SELECT DISTINCT trade_date
            FROM close_prices
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date
            """,
            (start_date.isoformat(), end_date.isoformat()),
        )
    ]


def build_daily_report_set(
    *,
    portfolio_db: str | Path,
    review_db: str | Path | None,
    report_date: str | date,
    account_id: str = "default",
    context_resolver: PeriodicContextResolver | None = None,
) -> dict[str, Any]:
    """Build the portfolio and every held-or-traded instrument daily report."""

    source = Path(portfolio_db).expanduser().resolve(strict=True)
    day = _parse_date(report_date)
    contexts: dict[str, dict[str, Any]] = {}
    context_errors: list[dict[str, str]] = []
    with _read_only_connection(source) as connection:
        snapshot = _portfolio_snapshot(
            connection,
            account_id=account_id,
            as_of=day,
        )
        traded_codes = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT DISTINCT ts_code
                FROM ledger_entries
                WHERE account_id = ? AND event_date = ?
                  AND event_type IN ('BUY', 'SELL')
                """,
                (account_id, day.isoformat()),
            )
            if row[0]
        }
        held_codes = {
            str(item.get("ts_code"))
            for item in snapshot.get("positions", [])
            if item.get("ts_code")
        }
        codes = sorted(held_codes | traded_codes)
        metadata = {
            str(row["ts_code"]): {
                "name": str(row["name"] or row["ts_code"]),
                "industry_name": str(row["industry_name"] or "MISSING"),
            }
            for row in connection.execute(
                (
                    "SELECT ts_code, name, industry_name FROM instruments "
                    f"WHERE ts_code IN ({','.join('?' for _ in codes)})"
                )
                if codes
                else "SELECT ts_code, name, industry_name FROM instruments WHERE 0",
                tuple(codes),
            )
        }
        for code in codes:
            item = metadata.get(
                code,
                {"name": code, "industry_name": "MISSING"},
            )
            local = _local_decision_context(
                connection,
                ts_code=code,
                name=item["name"],
                industry_name=item["industry_name"],
                report_date=day,
            )
            if context_resolver is None:
                contexts[code] = local
                continue
            try:
                resolved = context_resolver(
                    ts_code=code,
                    name=item["name"],
                    industry_name=item["industry_name"],
                    report_date=day,
                )
                if not isinstance(resolved, Mapping):
                    raise PeriodicContextError(
                        "periodic context resolver returned a non-mapping"
                    )
                contexts[code] = dict(resolved)
            except (ImportError, OSError, PeriodicContextError, RuntimeError) as exc:
                local["context_fallback"] = {
                    "status": "used",
                    "error_type": type(exc).__name__,
                    "reason": str(exc),
                }
                contexts[code] = local
                context_errors.append(
                    {
                        "ts_code": code,
                        "error_type": type(exc).__name__,
                        "reason": str(exc),
                    }
                )

    portfolio_context = _aggregate_portfolio_daily_context(
        contexts,
        report_date=day,
    )
    reports = [
        build_daily_report(
            portfolio_db=source,
            review_db=review_db,
            report_date=day,
            subject_type="portfolio",
            account_id=account_id,
            point_in_time_context=portfolio_context,
        )
    ]
    reports.extend(
        build_daily_report(
            portfolio_db=source,
            review_db=review_db,
            report_date=day,
            subject_type="instrument",
            subject_id=code,
            account_id=account_id,
            point_in_time_context=contexts[code],
        )
        for code in codes
    )
    return {
        "report_date": day.isoformat(),
        "reports": reports,
        "held_instruments": sorted(held_codes),
        "traded_instruments": sorted(traded_codes),
        "context_errors": context_errors,
    }


def generate_daily_range(
    *,
    portfolio_db: str | Path,
    review_db: str | Path,
    start_date: str | date,
    end_date: str | date,
    output_dir: str | Path | None = None,
    account_id: str = "default",
    context_resolver: PeriodicContextResolver | None = None,
    preserve_existing: bool = False,
) -> dict[str, Any]:
    """Generate and store complete daily report sets for real trading dates."""

    source = Path(portfolio_db).expanduser().resolve(strict=True)
    sidecar = Path(review_db).expanduser().resolve(strict=True)
    repository = Path.cwd().resolve()
    output = (
        Path(output_dir).expanduser().resolve(strict=False)
        if output_dir is not None
        else None
    )
    if source == sidecar:
        raise PeriodicReportError("formal source and review sidecar must differ")
    if not sidecar.is_relative_to(repository):
        raise PeriodicReportError("review sidecar must remain in the execution worktree")
    if output is not None and not output.is_relative_to(repository):
        raise PeriodicReportError("daily artifacts must remain in the execution worktree")

    selected_start = _parse_date(start_date)
    selected_end = _parse_date(end_date)
    source_before = sha256_file(source)
    with _read_only_connection(source) as connection:
        trading_days = _trading_dates(
            connection,
            start_date=selected_start,
            end_date=selected_end,
        )
    if not trading_days:
        raise PeriodicReportError("no formal trading dates exist in the selected range")

    store = PeriodicReportStore(sidecar)
    store.initialize()
    receipts: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    report_ids: list[str] = []
    context_errors: list[dict[str, str]] = []
    for day in trading_days:
        daily = build_daily_report_set(
            portfolio_db=source,
            review_db=sidecar,
            report_date=day,
            account_id=account_id,
            context_resolver=context_resolver,
        )
        context_errors.extend(daily["context_errors"])
        stored_reports: list[dict[str, Any]] = []
        for candidate in daily["reports"]:
            existing = store.get_by_identity(
                subject_type=str(candidate["subject"]["type"]),
                subject_id=str(candidate["subject"]["id"]),
                period_type="daily",
                period_start=day.isoformat(),
                period_end=day.isoformat(),
            )
            if preserve_existing and existing is not None:
                report = existing
                receipt = {
                    "status": "preserved",
                    "report_id": report["report_id"],
                    "payload_sha256": _sha256_text(_canonical_json(report)),
                }
            else:
                report = candidate
                receipt = store.save(report)
            receipts.append(receipt)
            stored_reports.append(report)
            report_ids.append(str(report["report_id"]))
            if output is not None:
                subject = report["subject"]
                stem = (
                    f"portfolio_daily_{day.isoformat()}"
                    if subject["type"] == "portfolio"
                    else (
                        f"instrument_daily_{subject['id']}_"
                        f"{day.isoformat()}"
                    )
                )
                _write_report(
                    output / day.isoformat() / f"{stem}.json",
                    json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                )
                _write_report(
                    output / day.isoformat() / f"{stem}.md",
                    render_periodic_report_markdown(report),
                )
        portfolio_report = next(
            item
            for item in stored_reports
            if item["subject"]["type"] == "portfolio"
        )
        coverage.append(
            {
                "trade_date": day.isoformat(),
                "portfolio_reports": 1,
                "instrument_reports": sum(
                    item["subject"]["type"] == "instrument"
                    for item in stored_reports
                ),
                "held_instruments": daily["held_instruments"],
                "traded_instruments": daily["traded_instruments"],
                "operation_count": portfolio_report["sections"][
                    "operations_and_motives"
                ]["operation_count"],
                "no_trade_day": (
                    portfolio_report["sections"]["operations_and_motives"][
                        "operation_count"
                    ]
                    == 0
                ),
            }
        )

    source_after = sha256_file(source)
    if source_after != source_before:
        raise PeriodicReportError(
            "formal portfolio database changed during daily range generation"
        )
    result = {
        "schema_version": "investment_review.daily_range.validation.v1",
        "status": "pass",
        "period": {
            "start": trading_days[0].isoformat(),
            "end": trading_days[-1].isoformat(),
            "trading_day_count": len(trading_days),
        },
        "coverage": coverage,
        "report_count": len(report_ids),
        "report_ids": report_ids,
        "store_receipts": receipts,
        "idempotency_identity": (
            "subject_type+subject_id+period_type+period_start+period_end"
        ),
        "context_errors": context_errors,
        "formal_portfolio_db": {
            "mode": "ro+immutable+query_only",
            "sha256_before": source_before,
            "sha256_after": source_after,
            "unchanged": True,
        },
        "orders_executed": False,
        "broker_accessed": False,
        "guaranteed_return_claims": False,
    }
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        _write_report(
            output / "daily_range_validation.json",
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        )
    return result


def _natural_period_key(day: date, period_type: str) -> tuple[int, int]:
    if period_type == "weekly":
        iso = day.isocalendar()
        return int(iso.year), int(iso.week)
    if period_type == "monthly":
        return day.year, day.month
    raise PeriodicReportError("natural period_type must be weekly or monthly")


def _natural_calendar_bounds(day: date, period_type: str) -> tuple[date, date]:
    if period_type == "weekly":
        start = day.fromordinal(day.toordinal() - day.weekday())
        return start, start.fromordinal(start.toordinal() + 6)
    if period_type == "monthly":
        start = day.replace(day=1)
        if start.month == 12:
            next_month = start.replace(year=start.year + 1, month=1)
        else:
            next_month = start.replace(month=start.month + 1)
        return start, next_month.fromordinal(next_month.toordinal() - 1)
    raise PeriodicReportError("natural period_type must be weekly or monthly")


def generate_periodic_summaries(
    *,
    review_db: str | Path,
    period_type: str,
    start_date: str | date,
    end_date: str | date,
    output_dir: str | Path | None = None,
    subject_type: str | None = None,
    subject_id: str | None = None,
) -> dict[str, Any]:
    """Aggregate stored daily facts into natural weekly or monthly reports."""

    if period_type not in {"weekly", "monthly"}:
        raise PeriodicReportError("period_type must be weekly or monthly")
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start > end:
        raise PeriodicReportError("start_date must not be after end_date")
    sidecar = Path(review_db).expanduser().resolve(strict=True)
    repository = Path.cwd().resolve()
    output = (
        Path(output_dir).expanduser().resolve(strict=False)
        if output_dir is not None
        else None
    )
    if not sidecar.is_relative_to(repository):
        raise PeriodicReportError("review sidecar must remain in the execution worktree")
    if output is not None and not output.is_relative_to(repository):
        raise PeriodicReportError("periodic artifacts must remain in the worktree")
    if subject_type is not None and subject_type not in _SUBJECT_TYPES:
        raise PeriodicReportError("subject_type must be portfolio or instrument")
    if subject_id is not None and not str(subject_id).strip():
        raise PeriodicReportError("subject_id must not be blank")

    store = PeriodicReportStore(sidecar)
    summaries = store.list(period_type="daily", limit=10000)
    source_reports = [
        store.get(str(item["report_id"]))
        for item in summaries
        if start.isoformat()
        <= str(item.get("period", {}).get("end") or "")
        <= end.isoformat()
        and (
            subject_type is None
            or item.get("subject", {}).get("type") == subject_type
        )
        and (
            subject_id is None
            or item.get("subject", {}).get("id") == subject_id
        )
    ]
    groups: dict[
        tuple[str, str, tuple[int, int]],
        list[dict[str, Any]],
    ] = {}
    for report in source_reports:
        report_day = _parse_date(str(report["period"]["end"]))
        key = (
            str(report["subject"]["type"]),
            str(report["subject"]["id"]),
            _natural_period_key(report_day, period_type),
        )
        groups.setdefault(key, []).append(report)
    if not groups:
        raise PeriodicReportError("no stored daily reports match the selected period")

    receipts: list[dict[str, Any]] = []
    generated: list[dict[str, Any]] = []
    for _, daily in sorted(groups.items()):
        daily.sort(key=lambda report: str(report["period"]["end"]))
        actual_start = _parse_date(str(daily[0]["period"]["end"]))
        actual_end = _parse_date(str(daily[-1]["period"]["end"]))
        calendar_start, calendar_end = _natural_calendar_bounds(
            actual_end,
            period_type,
        )
        report = build_aggregate_report(
            daily_reports=daily,
            period_type=period_type,
            period_start=actual_start,
            period_end=actual_end,
        )
        report["period"]["calendar_start"] = calendar_start.isoformat()
        report["period"]["calendar_end"] = calendar_end.isoformat()
        report["period"]["completeness"] = (
            "complete_selected_window"
            if start <= calendar_start and end >= calendar_end
            else "partial_selected_window"
        )
        report["content_id"] = "sha256:" + _sha256_text(
            _canonical_json(
                {
                    key: value
                    for key, value in report.items()
                    if key != "content_id"
                }
            )
        )
        validation = validate_periodic_report(report)
        if validation["status"] != "accepted":
            raise PeriodicReportError(
                "periodic summary validation failed: "
                + ", ".join(validation["errors"])
            )
        receipts.append(store.save(report))
        generated.append(report)
        if output is not None:
            subject = report["subject"]
            stem = (
                f"portfolio_{period_type}_{actual_start}_{actual_end}"
                if subject["type"] == "portfolio"
                else (
                    f"instrument_{period_type}_{subject['id']}_"
                    f"{actual_start}_{actual_end}"
                )
            )
            _write_report(
                output / f"{stem}.json",
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            )
            _write_report(
                output / f"{stem}.md",
                render_periodic_report_markdown(report),
            )
    result = {
        "schema_version": "investment_review.periodic_summary.validation.v1",
        "status": "pass",
        "period_type": period_type,
        "selected_window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "report_count": len(generated),
        "reports": [
            {
                "report_id": report["report_id"],
                "subject": report["subject"],
                "period": report["period"],
                "operation_count": report["sections"][
                    "operations_and_motives"
                ]["operation_count"],
                "daily_source_count": len(
                    report.get("source", {}).get("daily_report_ids", [])
                ),
                "validation": validate_periodic_report(report),
            }
            for report in generated
        ],
        "store_receipts": receipts,
        "orders_executed": False,
        "broker_accessed": False,
        "guaranteed_return_claims": False,
    }
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        _write_report(
            output / f"{period_type}_validation.json",
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        )
    return result


def export_final_sample_matrix(
    *,
    portfolio_db: str | Path,
    review_db: str | Path,
    output_dir: str | Path,
    instrument: str,
    daily_date: str | date,
    weekly_start: str | date,
    weekly_end: str | date,
    monthly_start: str | date,
    monthly_end: str | date,
) -> dict[str, Any]:
    """Export the six reader-facing report types and a compact final manifest."""

    source = Path(portfolio_db).expanduser().resolve(strict=True)
    sidecar = Path(review_db).expanduser().resolve(strict=True)
    output = Path(output_dir).expanduser().resolve(strict=False)
    repository = Path.cwd().resolve()
    if source == sidecar:
        raise PeriodicReportError("formal source and review sidecar must differ")
    if not sidecar.is_relative_to(repository):
        raise PeriodicReportError("review sidecar must remain in the worktree")
    if not output.is_relative_to(repository):
        raise PeriodicReportError("final artifacts must remain in the worktree")
    source_before = sha256_file(source)
    store = PeriodicReportStore(sidecar)
    selectors = [
        ("portfolio", "default", "daily", daily_date, daily_date),
        ("instrument", instrument, "daily", daily_date, daily_date),
        ("portfolio", "default", "weekly", weekly_start, weekly_end),
        ("instrument", instrument, "weekly", weekly_start, weekly_end),
        ("portfolio", "default", "monthly", monthly_start, monthly_end),
        ("instrument", instrument, "monthly", monthly_start, monthly_end),
    ]
    reports: list[dict[str, Any]] = []
    for subject_type, subject_id, period_type, start_value, end_value in selectors:
        start = _parse_date(start_value).isoformat()
        end = _parse_date(end_value).isoformat()
        report = store.get_by_identity(
            subject_type=subject_type,
            subject_id=subject_id,
            period_type=period_type,
            period_start=start,
            period_end=end,
        )
        if report is None:
            raise PeriodicReportError(
                "final sample is missing: "
                f"{subject_type}/{subject_id}/{period_type}/{start}/{end}"
            )
        validation = validate_periodic_report(report)
        if validation["status"] != "accepted":
            raise PeriodicReportError(
                f"final sample failed validation: {report['report_id']}"
            )
        reports.append(report)

    output.mkdir(parents=True, exist_ok=True)
    matrix: list[dict[str, Any]] = []
    for report in reports:
        subject = report["subject"]
        period = report["period"]
        subject_stem = (
            "portfolio"
            if subject["type"] == "portfolio"
            else f"instrument_{subject['id']}"
        )
        stem = (
            f"{subject_stem}_{period['type']}_"
            f"{period['start']}_{period['end']}"
        )
        json_path = output / f"{stem}.json"
        markdown_path = output / f"{stem}.md"
        _write_report(
            json_path,
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        )
        markdown = render_periodic_report_markdown(report)
        _write_report(markdown_path, markdown)
        reader_report = (
            report.get("reader_report")
            if isinstance(report.get("reader_report"), Mapping)
            else {}
        )
        analysis_brief = (
            report.get("analysis_brief")
            if isinstance(report.get("analysis_brief"), Mapping)
            else {}
        )
        matrix.append(
            {
                "report_id": report["report_id"],
                "schema_version": report.get("schema_version"),
                "subject": report["subject"],
                "period": report["period"],
                "analysis_brief_schema_version": analysis_brief.get(
                    "schema_version"
                ),
                "reader_report_schema_version": reader_report.get(
                    "schema_version"
                ),
                "central_judgment": reader_report.get("central_judgment"),
                "narrative_section_titles": [
                    item.get("title")
                    for item in reader_report.get("narrative_sections", [])
                    if isinstance(item, Mapping)
                ],
                "cross_period_synthesis": [
                    item.get("text")
                    for item in analysis_brief.get("material_findings", [])
                    if isinstance(item, Mapping)
                    and item.get("kind") == "cross_period_synthesis"
                ],
                "main_text_line_count": len(
                    markdown.split("<details>", 1)[0].splitlines()
                ),
                "collapsed_fact_appendix": "<details>" in markdown,
                "operation_count": report["sections"][
                    "operations_and_motives"
                ]["operation_count"],
                "performance_basis": report["sections"][
                    "performance_and_positions"
                ]["performance"].get("performance_basis"),
                "period_change_cny": report["sections"][
                    "performance_and_positions"
                ]["performance"].get("period_change_cny"),
                "validation": validate_periodic_report(report),
                "upgraded_from": report.get("source", {}).get(
                    "upgraded_from"
                ),
                "json_path": str(json_path),
                "markdown_path": str(markdown_path),
            }
        )
    source_after = sha256_file(source)
    if source_after != source_before:
        raise PeriodicReportError(
            "formal portfolio database changed during final export"
        )
    automation_status = store.get_json_meta("periodic_automation_status")
    validation_summary = {
        "schema_version": "investment_review.periodic_v2.final_validation.v1",
        "status": "candidate",
        "p1_sample_acceptance": {
            "grant": "accept_p1_sample_and_continue",
            "recorded": True,
        },
        "p5_sample_acceptance": {
            "grant": "accept_reader_report_samples_and_continue",
            "recorded": True,
        },
        "sample_matrix": matrix,
        "reader_report_behavior": {
            "all_samples_v2": all(
                item["schema_version"] == REPORT_SCHEMA_VERSION
                for item in matrix
            ),
            "one_central_judgment_per_report": all(
                bool(item["central_judgment"]) for item in matrix
            ),
            "collapsed_fact_appendix": all(
                item["collapsed_fact_appendix"] for item in matrix
            ),
            "weekly_monthly_cross_period_synthesis": all(
                bool(item["cross_period_synthesis"])
                for item in matrix
                if item["period"]["type"] in {"weekly", "monthly"}
            ),
            "runtime_model_provider_used": False,
        },
        "periodic_report_store_count": store.count(),
        "automation": automation_status
        or {
            "enabled": False,
            "state": "not_run",
            "os_scheduler_installed": False,
        },
        "formal_portfolio_db": {
            "mode": "ro+immutable+query_only",
            "sha256_before": source_before,
            "sha256_after": source_after,
            "unchanged": True,
        },
        "known_data_limitations": [
            (
                "2026-07-14 以前没有可靠现金快照；相关周/月报告保留总资产 "
                "MISSING，并明确改用不含现金的持仓市值变化口径。"
            ),
            (
                "批量历史日报默认使用正式库本地行情回退；基本面、基准或板块"
                "缺失时明确显示，不用未来信息补造。"
            ),
            "没有显式用户风险预算，精确仓位建议保持为区间。",
        ],
        "orders_executed": False,
        "broker_accessed": False,
        "guaranteed_return_claims": False,
        "production_released": False,
        "os_scheduler_or_service_installed": False,
    }
    validation_path = output / "validation_summary.json"
    _write_report(
        validation_path,
        json.dumps(validation_summary, ensure_ascii=False, indent=2) + "\n",
    )
    readout_lines = [
        "# 周期投资复盘读者版 V2 本地候选",
        "",
        "- P1 用户授权：`accept_p1_sample_and_continue`（已记录）",
        "- P5 用户授权：`accept_reader_report_samples_and_continue`（已记录）",
        f"- 六类真实报告：{len(matrix)} / 6",
        f"- 派生报告库当前报告数：{store.count()}",
        f"- 正式组合库 SHA-256：`{source_before}`（前后不变）",
        "- 默认主文：中心判断、综合分析、操作复盘与行动；完整事实默认折叠",
        "- 运行时模型/provider：未接入；V1 历史报告保持兼容",
        "- 订单执行：`false`；券商访问：`false`；保证收益：`false`",
        "- 生产发布：`false`；OS scheduler/service：未安装",
        "",
        "## 六类样本",
        "",
    ]
    for item in matrix:
        readout_lines.append(
            f"- {item['subject']['name']} · {item['period']['type']} · "
            f"{item['period']['start']} 至 {item['period']['end']} · "
            f"`{item['report_id']}`"
        )
    readout_lines.extend(
        [
            "",
            "## 已知限制",
            "",
            *[
                f"- {item}"
                for item in validation_summary["known_data_limitations"]
            ],
            "",
        ]
    )
    readout_path = output / "FINAL_READOUT.md"
    _write_report(readout_path, "\n".join(readout_lines))
    return {
        "status": "candidate",
        "report_count": len(matrix),
        "report_ids": [item["report_id"] for item in matrix],
        "validation_path": str(validation_path),
        "readout_path": str(readout_path),
        "formal_db_unchanged": True,
        "source_sha256": source_before,
    }


def generate_p1_daily_slice(
    *,
    portfolio_db: str | Path,
    review_db: str | Path,
    report_date: str | date,
    instrument: str,
    output_dir: str | Path,
) -> dict[str, Any]:
    source = Path(portfolio_db).resolve(strict=True)
    sidecar = Path(review_db).resolve(strict=True)
    output = Path(output_dir).resolve(strict=False)
    repository = Path.cwd().resolve()
    if source == sidecar:
        raise PeriodicReportError("formal source and review sidecar must differ")
    if not sidecar.is_relative_to(repository):
        raise PeriodicReportError("review sidecar must remain in the execution worktree")
    if not output.is_relative_to(repository):
        raise PeriodicReportError("P1 artifacts must remain in the execution worktree")

    source_before = sha256_file(source)
    selected_day = _parse_date(report_date)
    with _read_only_connection(source) as connection:
        metadata = connection.execute(
            """
            SELECT ts_code, name, industry_name
            FROM instruments
            WHERE ts_code = ?
            """,
            (instrument,),
        ).fetchone()
    if metadata is None:
        raise PeriodicReportError(f"instrument metadata not found: {instrument}")
    try:
        point_in_time_context = fetch_p1_decision_context(
            ts_code=instrument,
            name=str(metadata["name"] or instrument),
            industry_name=str(metadata["industry_name"] or "MISSING"),
            report_date=selected_day,
        )
    except PeriodicContextError as exc:
        raise PeriodicReportError(
            f"P1 four-layer context fetch failed: {exc}"
        ) from exc
    store = PeriodicReportStore(sidecar)
    store.initialize()
    reports = [
        build_daily_report(
            portfolio_db=source,
            review_db=sidecar,
            report_date=report_date,
            subject_type="portfolio",
            point_in_time_context=point_in_time_context,
        ),
        build_daily_report(
            portfolio_db=source,
            review_db=sidecar,
            report_date=report_date,
            subject_type="instrument",
            subject_id=instrument,
            point_in_time_context=point_in_time_context,
        ),
    ]
    receipts = [store.save(report) for report in reports]
    day = selected_day.isoformat()
    output.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for report in reports:
        stem = (
            f"portfolio_daily_{day}"
            if report["subject"]["type"] == "portfolio"
            else f"instrument_daily_{instrument}_{day}"
        )
        json_path = output / f"{stem}.json"
        md_path = output / f"{stem}.md"
        _write_report(
            json_path,
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        )
        _write_report(md_path, render_periodic_report_markdown(report))
        paths.extend([str(json_path), str(md_path)])
    source_after = sha256_file(source)
    if source_after != source_before:
        raise PeriodicReportError("formal portfolio database changed during P1 generation")
    validation = {
        "schema_version": "investment_review.p1_daily_slice.validation.v1",
        "status": "pass",
        "selected_report_date": day,
        "selected_instrument": instrument,
        "selection_reason": (
            "最近数据充分且包含无 Decision 的日内加仓后减回原仓位操作，"
            "可同时检验四层上下文、时间边界、非机械动机推断、"
            "费用来源分类、现金一致性和直接仓位建议。"
        ),
        "context": {
            "provider": point_in_time_context.get("provider"),
            "fetched_at": point_in_time_context.get("fetched_at"),
            "subject": point_in_time_context.get("subject"),
            "intraday_bar_count": len(
                point_in_time_context.get("intraday_bars", [])
            ),
            "layer_statuses": {
                key: point_in_time_context.get(key, {}).get("status")
                for key in (
                    "fundamental_and_valuation",
                    "market_and_sector",
                    "technical_and_trend",
                )
            },
        },
        "reports": [
            {
                "report_id": report["report_id"],
                "subject": report["subject"],
                "validation": validate_periodic_report(report),
                "operation_names_present": all(
                    bool(item.get("name"))
                    for item in report["sections"]["operations_and_motives"][
                        "operations"
                    ]
                ),
                "fee_statuses": sorted(
                    {
                        item.get("fee_status")
                        for item in report["sections"][
                            "operations_and_motives"
                        ]["operations"]
                    }
                ),
                "cash_consistency_status": report["sections"][
                    "performance_and_positions"
                ]["cash"].get("consistency_status"),
            }
            for report in reports
        ],
        "store_receipts": receipts,
        "formal_portfolio_db": {
            "mode": "ro+immutable+query_only",
            "sha256_before": source_before,
            "sha256_after": source_after,
            "unchanged": source_before == source_after,
        },
        "orders_executed": False,
        "broker_accessed": False,
        "guaranteed_return_claims": False,
    }
    validation_path = output / "validation_summary.json"
    _write_report(
        validation_path,
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
    )
    paths.append(str(validation_path))
    return {
        "status": "pass",
        "reports": [report["report_id"] for report in reports],
        "paths": paths,
        "formal_db_unchanged": True,
        "source_sha256": source_before,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser(
        "generate-p1-daily",
        help="Generate the real P1 portfolio and no-Decision instrument daily slice",
    )
    generate.add_argument("--portfolio-db", required=True)
    generate.add_argument("--review-db", required=True)
    generate.add_argument("--date", required=True)
    generate.add_argument("--instrument", required=True)
    generate.add_argument("--output-dir", required=True)
    daily_range = subparsers.add_parser(
        "generate-daily-range",
        help="Generate portfolio and held-or-traded instrument reports for a date range",
    )
    daily_range.add_argument("--portfolio-db", required=True)
    daily_range.add_argument("--review-db", required=True)
    daily_range.add_argument("--start-date", required=True)
    daily_range.add_argument("--end-date", required=True)
    daily_range.add_argument("--output-dir", required=True)
    daily_range.add_argument("--account", default="default")
    daily_range.add_argument(
        "--context-source",
        choices=("local", "baostock"),
        default="local",
        help="Use deterministic formal-DB context or bounded BaoStock enrichment",
    )
    daily_range.add_argument(
        "--preserve-existing",
        action="store_true",
        help="Keep an already stored semantic report instead of refreshing it",
    )
    summaries = subparsers.add_parser(
        "generate-summaries",
        help="Aggregate stored daily reports into natural weekly or monthly reports",
    )
    summaries.add_argument("--review-db", required=True)
    summaries.add_argument(
        "--period-type",
        choices=("weekly", "monthly"),
        required=True,
    )
    summaries.add_argument("--start-date", required=True)
    summaries.add_argument("--end-date", required=True)
    summaries.add_argument("--output-dir", required=True)
    summaries.add_argument(
        "--subject-type",
        choices=("portfolio", "instrument"),
    )
    summaries.add_argument("--subject-id")
    final_export = subparsers.add_parser(
        "export-final",
        help="Export the six real portfolio/instrument daily/weekly/monthly samples",
    )
    final_export.add_argument("--portfolio-db", required=True)
    final_export.add_argument("--review-db", required=True)
    final_export.add_argument("--output-dir", required=True)
    final_export.add_argument("--instrument", required=True)
    final_export.add_argument("--daily-date", required=True)
    final_export.add_argument("--weekly-start", required=True)
    final_export.add_argument("--weekly-end", required=True)
    final_export.add_argument("--monthly-start", required=True)
    final_export.add_argument("--monthly-end", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "generate-p1-daily":
        result = generate_p1_daily_slice(
            portfolio_db=args.portfolio_db,
            review_db=args.review_db,
            report_date=args.date,
            instrument=args.instrument,
            output_dir=args.output_dir,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "generate-daily-range":
        result = generate_daily_range(
            portfolio_db=args.portfolio_db,
            review_db=args.review_db,
            start_date=args.start_date,
            end_date=args.end_date,
            output_dir=args.output_dir,
            account_id=args.account,
            context_resolver=(
                fetch_p1_decision_context
                if args.context_source == "baostock"
                else None
            ),
            preserve_existing=args.preserve_existing,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "generate-summaries":
        result = generate_periodic_summaries(
            review_db=args.review_db,
            period_type=args.period_type,
            start_date=args.start_date,
            end_date=args.end_date,
            output_dir=args.output_dir,
            subject_type=args.subject_type,
            subject_id=args.subject_id,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "export-final":
        result = export_final_sample_matrix(
            portfolio_db=args.portfolio_db,
            review_db=args.review_db,
            output_dir=args.output_dir,
            instrument=args.instrument,
            daily_date=args.daily_date,
            weekly_start=args.weekly_start,
            weekly_end=args.weekly_end,
            monthly_start=args.monthly_start,
            monthly_end=args.monthly_end,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    raise PeriodicReportError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
