"""Lightweight portfolio and instrument periodic reports.

The P1 implementation intentionally supports daily reports only.  It reads the
formal portfolio database through an immutable, query-only connection, reuses
the canonical accounting and Trade Episode projection, and stores derived
reports only in the selected review sidecar.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence
from zoneinfo import ZoneInfo

from src.portfolio.accounting import build_position_states

from .episodes import build_episode_collection


REPORT_SCHEMA_VERSION = "investment_review.periodic_report.v1"
REPORT_API_SCHEMA_VERSION = "investment_review.periodic_reports.api.v1"
PERIODIC_STORE_SCHEMA_VERSION = "1"
SHANGHAI = ZoneInfo("Asia/Shanghai")
ZERO = Decimal("0")

_SUBJECT_TYPES = {"portfolio", "instrument"}
_PERIOD_TYPES = {"daily"}
_ACTIONS = {"buy", "sell", "hold", "add", "reduce", "exit"}
_POSITION_EVENT_TYPES = {"BUY", "SELL"}


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
    return {
        "amount_cny": _decimal_text(_decimal(row["amount"]), places=2),
        "as_of_date": row["as_of_date"],
        "source": row["source"],
        "status": "LOW_CONFIDENCE" if fee_pending else "fact",
        "fee_pending": fee_pending,
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


def infer_motive_hypothesis(
    operation: Mapping[str, Any],
    *,
    earlier_operations: Sequence[Mapping[str, Any]],
    prior_closes: Sequence[Mapping[str, Any]],
    position_weight_before_pct: str | None,
) -> dict[str, Any]:
    """Infer one motive using only inputs available by this operation."""

    occurred_at = str(operation.get("occurred_at") or "")
    role = _operation_role(operation)
    side = str(operation.get("side") or "")
    price = _decimal(operation.get("price_cny"))
    quantity = _decimal(operation.get("quantity"), default=ZERO) or ZERO
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
        if earlier_same_instrument:
            motive = "在已有同日买入后继续分批加仓，最可能是在确认盘中强度后扩大试仓。"
            alternative = "也可能只是拆单执行既定买入数量，并不代表新的判断。"
        elif trend_up or (trade_vs_prior is not None and trade_vs_prior > ZERO):
            motive = "最可能是顺势加仓或建立日内试仓，尝试延续操作前已可见的上涨。"
            alternative = "也可能是长期仓位补回或被动再平衡，现有数据无法证明追涨动机。"
        else:
            motive = "最可能是在回撤中补仓，尝试降低持仓成本或恢复目标仓位。"
            alternative = "也可能是长期配置或现金再平衡，而非基于短线价格判断。"
    elif side == "SELL":
        if earlier_buys >= quantity and quantity > ZERO:
            motive = "最可能是撤回当日新增仓位、控制盘中风险，或完成一次短线做 T。"
            alternative = "也可能是预设拆单卖出或现金调度，不能据此认定实际交易意图。"
        elif trade_vs_prior is not None and trade_vs_prior > ZERO:
            motive = "最可能是在上涨中降低仓位风险或兑现一部分利润。"
            alternative = "也可能是组合再平衡或现金需要，与价格判断无关。"
        else:
            motive = "最可能是降低持仓风险或执行止损/退出计划。"
            alternative = "也可能是组合再平衡；缺少 Decision，不能确认止损理由。"
    else:
        motive = "当前操作不改变持仓，最可能是现金或费用类账务事件。"
        alternative = "缺少原始说明时不能进一步归因。"

    confidence = (
        "medium"
        if previous_close is not None
        and (len(prior_closes) >= 3 or earlier_same_instrument)
        else "low"
    )
    return {
        "label": "system_inference",
        "operation_id": operation.get("operation_id"),
        "input_cutoff_at": occurred_at,
        "most_likely_motive": motive,
        "supporting_observations": observations,
        "alternative_explanations": [alternative],
        "confidence": confidence,
        "important_missing_information": [
            "MISSING_DECISION",
            "MISSING_INTRADAY_MARKET_CONTEXT",
            "MISSING_STRATEGY_OR_TARGET_POSITION",
        ],
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
    if fee_status != "actual":
        narrative += " 手续费缺失，不能把毛价差当作真实净收益。"
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
    earlier: list[dict[str, Any]] = []
    result: list[dict[str, Any]] = []
    prior_cache: dict[str, list[dict[str, Any]]] = {}
    for row in day_rows:
        event_id = _event_id(row)
        transition = transition_index.get(event_id, {})
        note = str(row.get("note") or "")
        fee_value = _decimal(row.get("fees"), default=ZERO) or ZERO
        fee_missing = (
            "fee_pending" in note
            or "fees_missing" in note
            or (fee_value == ZERO and row.get("event_type") in _POSITION_EVENT_TYPES)
        )
        occurred_at = _iso_utc(_event_time(row))
        operation = {
            "operation_id": "operation_" + _sha256_text(event_id)[:24],
            "event_id": event_id,
            "episode_id": transition.get("episode_id"),
            "episode_status": transition.get("episode_status"),
            "occurred_at": occurred_at,
            "source_imported_at": row.get("created_at"),
            "event_type": str(row.get("event_type") or "").lower(),
            "side": str(row.get("event_type") or "").upper(),
            "ts_code": row.get("ts_code"),
            "name": positions.get(str(row.get("ts_code")), {}).get(
                "name", row.get("ts_code")
            ),
            "quantity": str(row.get("quantity") or "0"),
            "price_cny": _decimal_text(_decimal(row.get("price")), places=4),
            "gross_amount_cny": _decimal_text(
                _decimal(row.get("gross_amount")), places=2
            ),
            "fee_cny": None if fee_missing else _decimal_text(fee_value, places=2),
            "fee_status": "MISSING" if fee_missing else "actual",
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
        code = str(row.get("ts_code") or "")
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


def build_recommendation(
    *,
    subject_type: str,
    subject_id: str,
    snapshot: Mapping[str, Any],
    report_cutoff_at: str,
) -> dict[str, Any]:
    positions = list(snapshot.get("positions", []))
    total_assets = _decimal(snapshot.get("total_assets_cny"))
    cash_weight = _decimal(snapshot.get("cash_weight_pct"))
    top_weight = _decimal(snapshot.get("top_position_weight_pct"))
    latest_price_date = max(
        (
            str(item.get("price_date") or "")
            for item in positions
            if item.get("price_date")
        ),
        default=None,
    )
    missing_inputs = [
        "MISSING_FUNDAMENTAL_AND_VALUATION_CONTEXT",
        "MISSING_EXPLICIT_USER_RISK_BUDGET",
    ]
    if snapshot.get("cash", {}).get("fee_pending"):
        missing_inputs.append("MISSING_TRADE_FEES")
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
        invalidation = [
            "用户已有可验证且不同的风险预算或资金安排",
            "正式账本现金或持仓在报告截止后发生变化",
            "缺失手续费补齐后显著改变当日现金与执行评价",
        ]
        risks = [
            "减仓后标的继续上涨会产生机会成本",
            "当前建议未纳入公司基本面与估值",
            "现金数据含 fee_pending，精确比例可能小幅变化",
        ]
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
                    selected.get("source_refs", [None])[0] if selected else "portfolio.sqlite3#ledger_entries"
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
                "type": "opinion",
                "text": "缺少基本面、估值和明确风险预算时，不应仅因短期价格反弹扩大集中仓位。",
                "source_ref": "periodic_report:risk_guardrail",
            },
        ]
        invalidation = [
            "用户提供可验证的目标仓位与止损/加仓计划",
            "新的基本面或估值证据改变风险收益判断",
            "正式账本持仓在报告截止后已发生变化",
        ]
        risks = [
            "减仓后价格继续上涨会产生机会成本",
            "仅靠账本与日线无法判断公司长期价值",
            "手续费和盘中市场背景缺失会影响执行评价",
        ]
        confidence = "low"
        missing_inputs.append("MISSING_INTRADAY_MARKET_CONTEXT")
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
    snapshot: Mapping[str, Any],
    performance: Mapping[str, Any],
    recommendation: Mapping[str, Any],
) -> str:
    if subject_type == "portfolio":
        return (
            f"组合当日资产变动 {performance.get('asset_change_pct')}%，"
            f"现金权重 {snapshot.get('cash_weight_pct')}%；"
            f"建议 {recommendation.get('action')}，优先降低集中度并保留现金缓冲。"
        )
    selected = next(
        (item for item in snapshot.get("positions", []) if item.get("ts_code") == subject_id),
        None,
    )
    return (
        f"{subject_id} 期末权重 "
        f"{selected.get('portfolio_weight_pct') if selected else '0'}%，"
        f"当日操作已按无 Decision 的 system_inference 复盘；"
        f"建议 {recommendation.get('action')}。"
    )


def build_daily_report(
    *,
    portfolio_db: str | Path,
    review_db: str | Path | None,
    report_date: str | date,
    subject_type: str,
    subject_id: str | None = None,
    account_id: str = "default",
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
    else:
        selected_positions = end_snapshot["positions"]

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
    effective_cutoff = market_cutoff
    if source_observed_through:
        observed_at = _aware_timestamp(str(source_observed_through))
        if observed_at > effective_cutoff:
            effective_cutoff = observed_at
    report_cutoff_at = effective_cutoff.astimezone(SHANGHAI).isoformat(
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
    start_cash = (
        _decimal(start_snapshot.get("cash", {}).get("amount_cny"))
        if start_snapshot is not None and start_snapshot.get("cash")
        else None
    )
    end_cash = (
        _decimal(end_snapshot.get("cash", {}).get("amount_cny"))
        if end_snapshot.get("cash")
        else None
    )
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
        "cash_change_cny": _decimal_text(
            end_cash - start_cash
            if end_cash is not None and start_cash is not None
            else None,
            places=2,
        ),
        "valuation_complete": not end_snapshot.get("missing_prices"),
        "calculation_method": (
            "期末总资产减上一交易日总资产；当日无外部资金流证据时作为资产变动，"
            "手续费待补会降低精度。"
        ),
        "source_refs": [
            "portfolio.sqlite3#ledger_entries",
            "portfolio.sqlite3#close_prices",
            "portfolio.sqlite3#cash_balance_snapshots",
        ],
    }
    recommendation = build_recommendation(
        subject_type=subject_type,
        subject_id=selected_subject,
        snapshot=end_snapshot,
        report_cutoff_at=report_cutoff_at,
    )
    judgments = [
        {
            "type": "inference",
            "status": "needs_improvement"
            if any(
                item["retrospective_evaluation"]["judgment"]
                == "needs_improvement"
                for item in operations
            )
            else "mixed"
            if operations
            else "no_trade",
            "text": (
                "当日执行评价仅使用成交、收盘价和已知费用；"
                "毛价差不能替代真实净收益。"
            ),
            "source_refs": [
                item["source_ref"] for item in operations
            ],
        }
    ]
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
        "cash_status": end_snapshot.get("cash", {}).get("status", "MISSING"),
    }
    identity = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "subject_type": subject_type,
        "subject_id": selected_subject,
        "period_type": "daily",
        "period_start": day.isoformat(),
        "period_end": day.isoformat(),
        "source_sha256": source_sha,
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
                    else selected_subject
                )
            ),
        },
        "period": {
            "type": "daily",
            "start": day.isoformat(),
            "end": day.isoformat(),
            "report_cutoff_at": report_cutoff_at,
        },
        "generated_at": source_observed_through,
        "headline": "",
        "sections": {
            "performance_and_positions": {
                "performance": performance,
                "cash": end_snapshot.get("cash"),
                "positions": selected_positions,
                "risk_change": risks,
            },
            "operations_and_motives": {
                "operation_count": len(operations),
                "operations": operations,
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
                            ["MISSING_TRADE_FEES"]
                            if end_snapshot.get("cash", {}).get("fee_pending")
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
        snapshot=end_snapshot,
        performance=performance,
        recommendation=recommendation,
    )
    report["content_id"] = "sha256:" + _sha256_text(_canonical_json(report))
    validation = validate_periodic_report(report)
    if validation["status"] != "accepted":
        raise PeriodicReportError(
            "periodic report validation failed: "
            + ", ".join(validation["errors"])
        )
    return report


def validate_periodic_report(report: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        errors.append("unsupported_schema_version")
    subject = report.get("subject")
    if not isinstance(subject, Mapping) or subject.get("type") not in _SUBJECT_TYPES:
        errors.append("invalid_subject")
    period = report.get("period")
    if not isinstance(period, Mapping) or period.get("type") not in _PERIOD_TYPES:
        errors.append("invalid_period")
    sections = report.get("sections")
    if not isinstance(sections, Mapping):
        errors.append("missing_sections")
        sections = {}
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
    return {
        "status": "accepted" if not errors else "blocked",
        "errors": sorted(set(errors)),
    }


def render_periodic_report_markdown(report: Mapping[str, Any]) -> str:
    subject = report["subject"]
    period = report["period"]
    sections = report["sections"]
    performance = sections["performance_and_positions"]["performance"]
    cash = sections["performance_and_positions"].get("cash") or {}
    risk = sections["performance_and_positions"]["risk_change"]
    recommendation = sections["recommendation"]
    operations = sections["operations_and_motives"]["operations"]
    lines = [
        f"# {subject['name']} {period['end']} 日报",
        "",
        f"> {report['headline']}",
        "",
        "## 1. 本期结论摘要",
        "",
        f"- 报告对象：`{subject['type']}` / `{subject['id']}`",
        f"- 报告截止：`{period['report_cutoff_at']}`",
        f"- 直接建议：`{recommendation['action']}`；{recommendation['target_position'].get('target_position_note')}",
        f"- 建议置信度：`{recommendation['confidence']}`；本报告不会执行订单。",
        "",
        "## 2. 收益、持仓、现金和风险变化",
        "",
        f"- 总资产：{performance.get('start_total_assets_cny')} → {performance.get('end_total_assets_cny')} 元，变动 {performance.get('asset_change_cny')} 元（{performance.get('asset_change_pct')}%）。",
        f"- 现金：{cash.get('amount_cny', 'MISSING')} 元，组合权重 {risk.get('cash_weight_pct')}%，状态 `{cash.get('status', 'MISSING')}`。",
        f"- 集中度：最大单一标的 {risk.get('top_position_weight_pct')}%，前三大合计 {risk.get('top3_weight_pct')}%，状态 `{risk.get('concentration_status')}`。",
        f"- 计算说明：{performance.get('calculation_method')}",
        "",
        "## 3. 操作与交易动机复盘",
        "",
    ]
    if not operations:
        lines.append("- 当日无持仓变动操作；报告仍保留表现、风险与建议。")
    for operation in operations:
        motive = operation["motive"]
        evaluation = operation["retrospective_evaluation"]
        lines.extend(
            [
                f"### {operation['occurred_at']} · {operation['side']} {operation['ts_code']}",
                "",
                f"- 操作事实：{operation['quantity']} 股 × {operation['price_cny']} 元；持仓 {operation.get('quantity_before')} → {operation.get('quantity_after')}；手续费 `{operation['fee_status']}`。",
                f"- 动机标签：`{motive['label']}`；置信度 `{motive.get('confidence', 'recorded')}`。",
                f"- 最可能动机：{motive.get('most_likely_motive', '见已记录 Decision。')}",
                f"- 替代解释：{'；'.join(motive.get('alternative_explanations', [])) or '无。'}",
                f"- 事后评价：{evaluation['narrative']} 毛价差 {evaluation.get('gross_mark_to_close_cny')} 元。",
                "",
            ]
        )
    lines.extend(
        [
            "## 4. 哪些判断或执行合理，哪些需要改进",
            "",
            *[
                f"- `{item['status']}`：{item['text']}"
                for item in sections["review_judgments"]
            ],
            "",
            "## 5. 个性化交易建议与建议仓位",
            "",
            f"- 动作：`{recommendation['action']}`",
            f"- 仓位：`{json.dumps(recommendation['target_position'], ensure_ascii=False)}`",
            f"- 期限：{recommendation['time_horizon']}",
            *[
                f"- 依据（{item['type']}）：{item['text']}"
                for item in recommendation["rationale"]
            ],
            "",
            "## 6. 主要依据、风险、失效条件和数据缺失",
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
            f"- 数据观察至：`{report['source']['source_observed_through']}`",
            f"- 来源：{', '.join(report['source']['source_refs'])}",
            "- 动机推断只使用各操作时点以前的信息；当日收盘结果只进入事后评价。",
            "- 建议只使用报告 cutoff 及以前的账本与市场信息。",
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
                str(report["source"]["source_sha256"]),
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
                """,
                (report["report_id"], identity_key),
            ).fetchone()
            if existing is not None:
                if existing["report_id"] != report["report_id"]:
                    raise PeriodicReportError(
                        "periodic report identity conflicts with different content"
                    )
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
                    SET report_cutoff_at = ?, generated_at = ?, status = ?,
                        payload_json = ?, payload_sha256 = ?, created_at = ?
                    WHERE report_id = ?
                    """,
                    (
                        report["period"]["report_cutoff_at"],
                        report.get("generated_at"),
                        report.get("status", "ready"),
                        payload,
                        payload_sha,
                        now,
                        report["report_id"],
                    ),
                )
                connection.commit()
                return {
                    "status": "updated",
                    "report_id": existing["report_id"],
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
                "status": report.get("status"),
                "subject": report["subject"],
                "period": report["period"],
                "generated_at": report.get("generated_at"),
                "headline": report.get("headline"),
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

    def count(self) -> int:
        with self._connect() as connection:
            if not self._table_exists(connection):
                return 0
            return int(
                connection.execute("SELECT COUNT(*) FROM periodic_reports").fetchone()[
                    0
                ]
            )


def _write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


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
    store = PeriodicReportStore(sidecar)
    store.initialize()
    reports = [
        build_daily_report(
            portfolio_db=source,
            review_db=sidecar,
            report_date=report_date,
            subject_type="portfolio",
        ),
        build_daily_report(
            portfolio_db=source,
            review_db=sidecar,
            report_date=report_date,
            subject_type="instrument",
            subject_id=instrument,
        ),
    ]
    receipts = [store.save(report) for report in reports]
    day = _parse_date(report_date).isoformat()
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
            "可同时检验时间边界、动机推断、手续费缺失和直接仓位建议。"
        ),
        "reports": [
            {
                "report_id": report["report_id"],
                "subject": report["subject"],
                "validation": validate_periodic_report(report),
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
    raise PeriodicReportError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
