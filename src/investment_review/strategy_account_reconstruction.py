"""Read-only account-history reconstruction for P10 strategy validation.

The formal portfolio database is opened with SQLite URI read-only and immutable
flags and ``PRAGMA query_only``.  The output intentionally consists of labelled
reconstruction scenarios, not assertions that any inferred cash history is a
complete accounting fact.
"""

from __future__ import annotations

import sqlite3
from bisect import bisect_right
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence


ZERO = Decimal("0")


class AccountReconstructionError(ValueError):
    """Raised when inputs or source rows cannot be reconstructed safely."""


def _decimal(value: object, *, field: str) -> Decimal:
    try:
        result = Decimal(str(value if value not in (None, "") else "0"))
    except (InvalidOperation, ValueError) as exc:
        raise AccountReconstructionError(f"invalid decimal in {field}: {value!r}") from exc
    if not result.is_finite():
        raise AccountReconstructionError(f"non-finite decimal in {field}: {value!r}")
    return result


def _coerce_date(value: date | str, *, field: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise AccountReconstructionError(f"invalid ISO date in {field}: {value!r}") from exc


def sqlite_read_only_uri(database_path: str | Path) -> str:
    """Return the exact URI used for a protected formal SQLite source."""

    selected = Path(database_path).expanduser().resolve(strict=True)
    if not selected.is_file():
        raise AccountReconstructionError(f"database is not a file: {selected}")
    return selected.as_uri() + "?mode=ro&immutable=1"


@contextmanager
def open_formal_portfolio_read_only(
    database_path: str | Path,
) -> Iterator[sqlite3.Connection]:
    """Open the formal portfolio database without any writable code path."""

    connection = sqlite3.connect(sqlite_read_only_uri(database_path), uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    try:
        yield connection
    finally:
        connection.close()


def ledger_cash_delta(
    event_type: str,
    *,
    gross_amount: object = ZERO,
    fees: object = ZERO,
    cash_amount: object = ZERO,
) -> Decimal:
    """Return the contractual end-of-day cash effect of one ledger row."""

    event = str(event_type).upper()
    gross = _decimal(gross_amount, field="gross_amount")
    fee = _decimal(fees, field="fees")
    cash = _decimal(cash_amount, field="cash_amount")
    if event == "BUY":
        return -(gross + fee)
    if event == "SELL":
        return gross - fee
    if event == "DIVIDEND":
        return cash
    if event == "CASH_FEE":
        return -cash
    if event == "OPENING":
        return ZERO
    raise AccountReconstructionError(f"unsupported ledger event_type: {event_type!r}")


@dataclass(frozen=True)
class CashAnchor:
    as_of_date: date
    amount: Decimal
    source_ref: str = "caller_supplied_cash_anchor"
    timing: str = "end_of_day"

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of_date", _coerce_date(self.as_of_date, field="anchor"))
        object.__setattr__(self, "amount", _decimal(self.amount, field="anchor.amount"))
        if self.timing != "end_of_day":
            raise AccountReconstructionError("only an end_of_day cash anchor is supported")


@dataclass(frozen=True)
class ReconstructionGap:
    code: str
    detail: str
    ts_code: str | None = None
    source_ref: str | None = None


@dataclass(frozen=True)
class PriceMark:
    ts_code: str
    instrument_name: str
    quantity: Decimal
    unit_price: Decimal | None
    market_value: Decimal | None
    method: str
    price_date: date | None
    source: str | None
    source_ref: str | None
    is_market_price: bool
    carried_forward_days: int | None


@dataclass(frozen=True)
class ReconstructionDay:
    trade_date: date
    cash: Decimal
    market_value: Decimal | None
    known_market_value: Decimal
    nav: Decimal | None
    daily_return: Decimal | None
    equity_exposure: Decimal | None
    gross_trade_amount: Decimal
    transaction_cash_delta: Decimal
    ledger_fees_used_in_cash: Decimal
    actual_fees: Decimal | None
    estimated_or_unverified_fees: Decimal
    fee_evidence_status: str
    trade_count: int
    event_count: int
    price_marks: tuple[PriceMark, ...]
    gaps: tuple[ReconstructionGap, ...]
    source_refs: tuple[str, ...]


@dataclass(frozen=True)
class ScenarioDiagnostics:
    minimum_cash: Decimal
    negative_cash_dates: tuple[date, ...]
    nonpositive_nav_dates: tuple[date, ...]
    incomplete_valuation_dates: tuple[date, ...]


@dataclass(frozen=True)
class ReconstructionScenario:
    name: str
    epistemic_status: str
    assumptions: tuple[str, ...]
    cash_shift: Decimal
    daily: tuple[ReconstructionDay, ...]
    diagnostics: ScenarioDiagnostics


@dataclass(frozen=True)
class CashSnapshotCheck:
    snapshot_id: str
    as_of_date: date
    recorded_amount: Decimal
    reconstructed_cash: Decimal
    difference: Decimal
    source: str
    note: str
    recorded_at: str
    is_selected_anchor: bool


@dataclass(frozen=True)
class HoldingQuantity:
    ts_code: str
    instrument_name: str
    quantity: Decimal


@dataclass(frozen=True)
class NegativeHoldingEvent:
    entry_id: int
    event_date: date
    ts_code: str
    quantity_after: Decimal


@dataclass(frozen=True)
class RebaseQuantityCheck:
    rebase_id: str
    as_of_date: date
    ts_code: str
    ledger_quantity: Decimal
    target_quantity: Decimal
    difference: Decimal
    status: str
    source_path: str


@dataclass(frozen=True)
class ReconstructionAudit:
    source_access: str
    inferred_cash_before_first_ledger_event: Decimal
    cash_snapshot_checks: tuple[CashSnapshotCheck, ...]
    holdings_before_output_start: tuple[HoldingQuantity, ...]
    holdings_at_output_start: tuple[HoldingQuantity, ...]
    final_holdings: tuple[HoldingQuantity, ...]
    negative_holding_events: tuple[NegativeHoldingEvent, ...]
    rebase_quantity_checks: tuple[RebaseQuantityCheck, ...]
    source_row_counts: Mapping[str, int]


@dataclass(frozen=True)
class AccountReconstruction:
    account_id: str
    cash_anchor: CashAnchor
    scenarios: tuple[ReconstructionScenario, ...]
    audit: ReconstructionAudit

    def by_name(self, name: str) -> ReconstructionScenario:
        for scenario in self.scenarios:
            if scenario.name == name:
                return scenario
        raise KeyError(name)

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready representation."""

        return _json_ready(asdict(self))


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _load_rows(
    connection: sqlite3.Connection,
    *,
    account_id: str,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, str],
]:
    tables = _tables(connection)
    missing = {"ledger_entries", "close_prices"} - tables
    if missing:
        raise AccountReconstructionError(
            "formal database lacks required tables: " + ", ".join(sorted(missing))
        )
    ledger = [
        dict(row)
        for row in connection.execute(
            """
            SELECT entry_id, account_id, event_date, event_time, event_type,
                   ts_code, quantity, price, gross_amount, fees, cash_amount,
                   note, import_batch_id
            FROM ledger_entries
            WHERE account_id = ?
            ORDER BY event_date,
                     CASE WHEN event_time = '' THEN '99:99:99' ELSE event_time END,
                     entry_id
            """,
            (account_id,),
        )
    ]
    if not ledger:
        raise AccountReconstructionError(f"no ledger rows for account_id={account_id!r}")
    codes = sorted({str(row["ts_code"]) for row in ledger if row.get("ts_code")})
    placeholders = ",".join("?" for _ in codes)
    prices = (
        [
            dict(row)
            for row in connection.execute(
                f"""
            SELECT observation_id, ts_code, trade_date, close, source, fetched_at
            FROM close_prices
            WHERE ts_code IN ({placeholders})
            ORDER BY ts_code, trade_date, fetched_at, observation_id
            """,
                codes,
            )
        ]
        if codes
        else []
    )
    snapshots = []
    if "cash_balance_snapshots" in tables:
        snapshots = [
            dict(row)
            for row in connection.execute(
                """
                SELECT snapshot_id, as_of_date, amount, source, note, recorded_at
                FROM cash_balance_snapshots
                WHERE account_id = ?
                ORDER BY as_of_date, recorded_at, snapshot_id
                """,
                (account_id,),
            )
        ]
    rebases = []
    if "position_cost_rebases" in tables:
        rebases = [
            dict(row)
            for row in connection.execute(
                """
                SELECT rebase_id, as_of_date, ts_code, target_quantity,
                       status, source_path, recorded_at
                FROM position_cost_rebases
                WHERE account_id = ?
                ORDER BY as_of_date, ts_code, recorded_at, rebase_id
                """,
                (account_id,),
            )
        ]
    names = {code: code for code in codes}
    if "instruments" in tables and codes:
        names.update(
            {
                str(row["ts_code"]): str(row["name"] or row["ts_code"])
                for row in connection.execute(
                    f"SELECT ts_code, name FROM instruments WHERE ts_code IN ({placeholders})",
                    codes,
                )
            }
        )
    return ledger, prices, snapshots, rebases, names


def _fee_evidence(row: Mapping[str, Any]) -> str:
    event_type = str(row.get("event_type") or "").upper()
    if event_type == "CASH_FEE":
        return "recorded_actual"
    if event_type not in {"BUY", "SELL"}:
        return "not_applicable"
    note = str(row.get("note") or "").lower()
    fields: dict[str, str] = {}
    for part in note.split(";"):
        key, separator, value = part.strip().partition("=")
        if separator and key.strip():
            fields[key.strip()] = value.strip()
    fee_source = fields.get("fee_source", "")
    fee_rule = fields.get("fee_rule", "")
    if fee_source == "formal_exemption" or "exempt" in fee_rule:
        return "formal_exemption"
    if fee_source == "rule_derived" or "fee_backfilled_rule=true" in note:
        return "rule_backfilled"
    if fee_rule:
        return "rule_backfilled"
    if (
        fee_source == "broker_actual"
        or "fees_inferred_from_net_amount=true" in note
        or "fee_backfilled_exact=" in note
    ):
        return "recorded_actual"
    if any(marker in note for marker in ("fee_pending", "fees_missing=true")):
        return "unknown"
    return "unknown"


def _position_delta(row: Mapping[str, Any]) -> Decimal:
    event_type = str(row["event_type"]).upper()
    quantity = _decimal(row.get("quantity"), field="quantity")
    if quantity < ZERO:
        raise AccountReconstructionError(
            f"negative quantity at ledger entry {row.get('entry_id')}: {quantity}"
        )
    if event_type in {"OPENING", "BUY"}:
        return quantity
    if event_type == "SELL":
        return -quantity
    return ZERO


def _price_index(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[list[date], list[dict[str, Any]]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in rows:
        row = dict(raw)
        row["parsed_date"] = _coerce_date(row["trade_date"], field="price.trade_date")
        close = _decimal(row["close"], field="close")
        if close <= ZERO:
            continue
        row["parsed_close"] = close
        grouped[str(row["ts_code"])].append(row)
    result: dict[str, tuple[list[date], list[dict[str, Any]]]] = {}
    for code, values in grouped.items():
        result[code] = ([row["parsed_date"] for row in values], values)
    return result


def _latest_price(
    index: Mapping[str, tuple[list[date], list[dict[str, Any]]]],
    ts_code: str,
    through: date,
) -> dict[str, Any] | None:
    values = index.get(ts_code)
    if values is None:
        return None
    dates, rows = values
    position = bisect_right(dates, through) - 1
    return None if position < 0 else rows[position]


def _holding_tuple(
    holdings: Mapping[str, Decimal],
    names: Mapping[str, str],
) -> tuple[HoldingQuantity, ...]:
    return tuple(
        HoldingQuantity(code, names.get(code, code), quantity)
        for code, quantity in sorted(holdings.items())
        if quantity != ZERO
    )


def _scenario_diagnostics(rows: Sequence[ReconstructionDay]) -> ScenarioDiagnostics:
    cash_values = [row.cash for row in rows]
    return ScenarioDiagnostics(
        minimum_cash=min(cash_values),
        negative_cash_dates=tuple(row.trade_date for row in rows if row.cash < ZERO),
        nonpositive_nav_dates=tuple(
            row.trade_date for row in rows if row.nav is not None and row.nav <= ZERO
        ),
        incomplete_valuation_dates=tuple(
            row.trade_date for row in rows if row.market_value is None
        ),
    )


def _with_returns(
    rows: Sequence[ReconstructionDay],
    *,
    cash_shift: Decimal,
) -> tuple[ReconstructionDay, ...]:
    result: list[ReconstructionDay] = []
    previous_nav: Decimal | None = None
    for source in rows:
        cash = source.cash + cash_shift
        nav = cash + source.market_value if source.market_value is not None else None
        daily_return = None
        if nav is not None and previous_nav is not None and previous_nav > ZERO:
            daily_return = nav / previous_nav - Decimal("1")
        exposure = None if nav in (None, ZERO) else source.known_market_value / nav
        result.append(
            replace(
                source,
                cash=cash,
                nav=nav,
                daily_return=daily_return,
                equity_exposure=exposure,
            )
        )
        previous_nav = nav
    return tuple(result)


def reconstruct_account_history(
    database_path: str | Path,
    *,
    account_id: str,
    cash_anchor: CashAnchor,
    constant_cash_shift: Decimal | str | int | float,
    trusted_window_start: date | str,
    trusted_window_end: date | str | None = None,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    allow_subscription_cost_proxy: bool = True,
) -> AccountReconstruction:
    """Reconstruct three explicitly labelled, non-factual analysis scenarios.

    ``constant_cash_shift`` and ``trusted_window_start`` are mandatory so a
    caller cannot silently accept a guessed correction or trust boundary.
    Prices are always the latest close whose ``trade_date`` is not later than
    the reconstructed day.  A positive historical BUY fill may temporarily
    proxy an unpriced holding, but that mark remains a visible non-market gap.
    """

    shift = _decimal(constant_cash_shift, field="constant_cash_shift")
    trusted_start = _coerce_date(trusted_window_start, field="trusted_window_start")
    trusted_end = (
        _coerce_date(trusted_window_end, field="trusted_window_end")
        if trusted_window_end is not None
        else None
    )
    if trusted_end is not None and trusted_end < trusted_start:
        raise AccountReconstructionError("trusted_window_end precedes trusted_window_start")

    with open_formal_portfolio_read_only(database_path) as connection:
        if int(connection.execute("PRAGMA query_only").fetchone()[0]) != 1:
            raise AccountReconstructionError("formal database connection is not query_only")
        ledger, prices, snapshots, rebases, names = _load_rows(
            connection,
            account_id=account_id,
        )

    for row in ledger:
        row["parsed_date"] = _coerce_date(row["event_date"], field="ledger.event_date")
    for row in snapshots:
        row["parsed_date"] = _coerce_date(row["as_of_date"], field="snapshot.as_of_date")
    for row in rebases:
        row["parsed_date"] = _coerce_date(row["as_of_date"], field="rebase.as_of_date")

    first_ledger_date = min(row["parsed_date"] for row in ledger)
    last_ledger_date = max(row["parsed_date"] for row in ledger)
    price_dates = [_coerce_date(row["trade_date"], field="price.trade_date") for row in prices]
    snapshot_dates = [row["parsed_date"] for row in snapshots]
    rebase_dates = [row["parsed_date"] for row in rebases]
    output_start = (
        _coerce_date(start_date, field="start_date")
        if start_date is not None
        else first_ledger_date
    )
    default_end_candidates = [last_ledger_date, cash_anchor.as_of_date]
    default_end_candidates.extend(price_dates)
    default_end_candidates.extend(snapshot_dates)
    output_end = (
        _coerce_date(end_date, field="end_date")
        if end_date is not None
        else max(default_end_candidates)
    )
    if output_end < output_start:
        raise AccountReconstructionError("end_date precedes start_date")
    if trusted_start < output_start or trusted_start > output_end:
        raise AccountReconstructionError("trusted_window_start is outside the output range")
    if trusted_end is not None and trusted_end > output_end:
        raise AccountReconstructionError("trusted_window_end is outside the output range")

    events_by_date: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for row in ledger:
        events_by_date[row["parsed_date"]].append(row)
    cash_through_anchor = sum(
        (
            ledger_cash_delta(
                str(row["event_type"]),
                gross_amount=row.get("gross_amount"),
                fees=row.get("fees"),
                cash_amount=row.get("cash_amount"),
            )
            for row in ledger
            if row["parsed_date"] <= cash_anchor.as_of_date
        ),
        ZERO,
    )
    inferred_cash_before_first = cash_anchor.amount - cash_through_anchor

    calendar = {
        row["parsed_date"] for row in ledger if output_start <= row["parsed_date"] <= output_end
    }
    calendar.update(day for day in price_dates if output_start <= day <= output_end)
    calendar.update(day for day in snapshot_dates if output_start <= day <= output_end)
    calendar.update(day for day in rebase_dates if output_start <= day <= output_end)
    calendar.add(output_start)
    calendar.add(output_end)
    calendar.add(trusted_start)
    if trusted_end is not None:
        calendar.add(trusted_end)
    if output_start <= cash_anchor.as_of_date <= output_end:
        calendar.add(cash_anchor.as_of_date)
    days = sorted(calendar)

    price_lookup = _price_index(prices)
    holdings: dict[str, Decimal] = defaultdict(lambda: ZERO)
    last_buy_fill: dict[str, tuple[Decimal, date, int]] = {}
    cumulative_cash_delta = ZERO
    negative_holdings: list[NegativeHoldingEvent] = []
    raw_rows: list[ReconstructionDay] = []
    holdings_before_start: dict[str, Decimal] = {}
    holdings_at_start: dict[str, Decimal] = {}
    quantity_after_date: dict[date, dict[str, Decimal]] = {}

    pre_output_events = [row for row in ledger if row["parsed_date"] < output_start]
    for row in pre_output_events:
        cumulative_cash_delta += ledger_cash_delta(
            str(row["event_type"]),
            gross_amount=row.get("gross_amount"),
            fees=row.get("fees"),
            cash_amount=row.get("cash_amount"),
        )
        code = str(row["ts_code"])
        holdings[code] += _position_delta(row)
        if str(row["event_type"]).upper() == "BUY":
            quantity = _decimal(row.get("quantity"), field="quantity")
            fill = _decimal(row.get("price"), field="price")
            if fill <= ZERO and quantity > ZERO:
                fill = _decimal(row.get("gross_amount"), field="gross_amount") / quantity
            if fill > ZERO:
                last_buy_fill[code] = (fill, row["parsed_date"], int(row["entry_id"]))
    holdings_before_start = dict(holdings)

    for day in days:
        day_events = events_by_date.get(day, [])
        gross_trade_amount = ZERO
        day_cash_delta = ZERO
        ledger_fees = ZERO
        actual_fee_sum = ZERO
        estimated_fee_sum = ZERO
        actual_fee_complete = True
        trade_count = 0
        source_refs: list[str] = []
        day_gaps: list[ReconstructionGap] = []
        for row in day_events:
            event_type = str(row["event_type"]).upper()
            delta = ledger_cash_delta(
                event_type,
                gross_amount=row.get("gross_amount"),
                fees=row.get("fees"),
                cash_amount=row.get("cash_amount"),
            )
            day_cash_delta += delta
            cumulative_cash_delta += delta
            code = str(row["ts_code"])
            holdings[code] += _position_delta(row)
            if holdings[code] < ZERO:
                negative_holdings.append(
                    NegativeHoldingEvent(int(row["entry_id"]), day, code, holdings[code])
                )
            source_refs.append(f"portfolio.sqlite3#ledger_entries:{row['entry_id']}")
            if event_type in {"BUY", "SELL"}:
                trade_count += 1
                gross_trade_amount += _decimal(row.get("gross_amount"), field="gross_amount")
                fee = _decimal(row.get("fees"), field="fees")
                ledger_fees += fee
                evidence = _fee_evidence(row)
                if evidence in {"recorded_actual", "formal_exemption"}:
                    actual_fee_sum += fee
                else:
                    actual_fee_complete = False
                    estimated_fee_sum += fee
                    day_gaps.append(
                        ReconstructionGap(
                            "fee_not_directly_observed",
                            f"ledger fee evidence is {evidence}",
                            code,
                            f"portfolio.sqlite3#ledger_entries:{row['entry_id']}",
                        )
                    )
                if event_type == "BUY":
                    quantity = _decimal(row.get("quantity"), field="quantity")
                    fill = _decimal(row.get("price"), field="price")
                    if fill <= ZERO and quantity > ZERO:
                        fill = _decimal(row.get("gross_amount"), field="gross_amount") / quantity
                    if fill > ZERO:
                        last_buy_fill[code] = (fill, day, int(row["entry_id"]))
            elif event_type == "CASH_FEE":
                fee = _decimal(row.get("cash_amount"), field="cash_amount")
                ledger_fees += fee
                actual_fee_sum += fee

        if day == output_start:
            holdings_at_start = dict(holdings)
        price_marks: list[PriceMark] = []
        known_market_value = ZERO
        valuation_complete = True
        for code, quantity in sorted(holdings.items()):
            if quantity <= ZERO:
                continue
            price = _latest_price(price_lookup, code, day)
            if price is not None:
                price_day = price["parsed_date"]
                unit_price = price["parsed_close"]
                market_value = quantity * unit_price
                known_market_value += market_value
                price_marks.append(
                    PriceMark(
                        code,
                        names.get(code, code),
                        quantity,
                        unit_price,
                        market_value,
                        "market_close",
                        price_day,
                        str(price.get("source") or ""),
                        f"portfolio.sqlite3#close_prices:{price['observation_id']}",
                        True,
                        (day - price_day).days,
                    )
                )
                continue
            fill = last_buy_fill.get(code)
            if allow_subscription_cost_proxy and fill is not None:
                unit_price, fill_date, entry_id = fill
                market_value = quantity * unit_price
                known_market_value += market_value
                source_ref = f"portfolio.sqlite3#ledger_entries:{entry_id}"
                price_marks.append(
                    PriceMark(
                        code,
                        names.get(code, code),
                        quantity,
                        unit_price,
                        market_value,
                        "subscription_cost_proxy_non_market",
                        fill_date,
                        "ledger_buy_fill",
                        source_ref,
                        False,
                        None,
                    )
                )
                day_gaps.append(
                    ReconstructionGap(
                        "market_price_missing_cost_proxy_used",
                        "no close at or before the day; historical BUY fill is a non-market proxy",
                        code,
                        source_ref,
                    )
                )
            else:
                valuation_complete = False
                price_marks.append(
                    PriceMark(
                        code,
                        names.get(code, code),
                        quantity,
                        None,
                        None,
                        "unpriced",
                        None,
                        None,
                        None,
                        False,
                        None,
                    )
                )
                day_gaps.append(
                    ReconstructionGap(
                        "market_price_missing",
                        "no close at or before the day and no eligible BUY fill proxy",
                        code,
                    )
                )
        cash = inferred_cash_before_first + cumulative_cash_delta
        market_value = known_market_value if valuation_complete else None
        raw_rows.append(
            ReconstructionDay(
                trade_date=day,
                cash=cash,
                market_value=market_value,
                known_market_value=known_market_value,
                nav=None,
                daily_return=None,
                equity_exposure=None,
                gross_trade_amount=gross_trade_amount,
                transaction_cash_delta=day_cash_delta,
                ledger_fees_used_in_cash=ledger_fees,
                actual_fees=actual_fee_sum if actual_fee_complete else None,
                estimated_or_unverified_fees=estimated_fee_sum,
                fee_evidence_status=("complete" if actual_fee_complete else "contains_non_actual"),
                trade_count=trade_count,
                event_count=len(day_events),
                price_marks=tuple(price_marks),
                gaps=tuple(day_gaps),
                source_refs=tuple(source_refs),
            )
        )
        quantity_after_date[day] = dict(holdings)

    anchored_rows = _with_returns(raw_rows, cash_shift=ZERO)
    shifted_rows = _with_returns(raw_rows, cash_shift=shift)
    trusted_source_rows = [
        row
        for row in anchored_rows
        if row.trade_date >= trusted_start
        and (trusted_end is None or row.trade_date <= trusted_end)
    ]
    trusted_rows = _with_returns(trusted_source_rows, cash_shift=ZERO)
    scenarios = (
        ReconstructionScenario(
            "anchored_raw",
            "reconstruction_scenario_not_fact",
            (
                "cash anchor is correct at end of anchor date",
                "ledger contains every cash-changing event after initial funding",
                "latest available close at or before each date is a valid valuation mark",
            ),
            ZERO,
            anchored_rows,
            _scenario_diagnostics(anchored_rows),
        ),
        ReconstructionScenario(
            "constant_cash_shift",
            "sensitivity_scenario_not_fact",
            (
                "caller-specified constant cash correction applies unchanged to every date",
                "the shift is a sensitivity input and is not evidence of an actual transfer",
            ),
            shift,
            shifted_rows,
            _scenario_diagnostics(shifted_rows),
        ),
        ReconstructionScenario(
            "trusted_window",
            "restricted_window_scenario_not_fact",
            (
                f"dates before {trusted_start.isoformat()} are excluded from return statistics",
                "holdings and cash at the trusted boundary still depend on earlier ledger replay",
            ),
            ZERO,
            trusted_rows,
            _scenario_diagnostics(trusted_rows),
        ),
    )

    raw_by_date = {row.trade_date: row for row in anchored_rows}
    snapshot_checks = tuple(
        CashSnapshotCheck(
            snapshot_id=str(row["snapshot_id"]),
            as_of_date=row["parsed_date"],
            recorded_amount=_decimal(row["amount"], field="snapshot.amount"),
            reconstructed_cash=raw_by_date[row["parsed_date"]].cash,
            difference=(
                raw_by_date[row["parsed_date"]].cash
                - _decimal(row["amount"], field="snapshot.amount")
            ),
            source=str(row.get("source") or ""),
            note=str(row.get("note") or ""),
            recorded_at=str(row.get("recorded_at") or ""),
            is_selected_anchor=(
                row["parsed_date"] == cash_anchor.as_of_date
                and _decimal(row["amount"], field="snapshot.amount") == cash_anchor.amount
            ),
        )
        for row in snapshots
        if row["parsed_date"] in raw_by_date
    )

    def quantity_as_of(target: date, code: str) -> Decimal:
        quantity = ZERO
        for row in ledger:
            if row["parsed_date"] > target:
                break
            if str(row["ts_code"]) == code:
                quantity += _position_delta(row)
        return quantity

    rebase_checks = tuple(
        RebaseQuantityCheck(
            rebase_id=str(row["rebase_id"]),
            as_of_date=row["parsed_date"],
            ts_code=str(row["ts_code"]),
            ledger_quantity=quantity_as_of(row["parsed_date"], str(row["ts_code"])),
            target_quantity=_decimal(row["target_quantity"], field="target_quantity"),
            difference=(
                quantity_as_of(row["parsed_date"], str(row["ts_code"]))
                - _decimal(row["target_quantity"], field="target_quantity")
            ),
            status=str(row.get("status") or ""),
            source_path=str(row.get("source_path") or ""),
        )
        for row in rebases
    )
    final_quantities = quantity_after_date[days[-1]]
    audit = ReconstructionAudit(
        source_access="sqlite_uri_mode_ro_immutable_1_and_pragma_query_only_on",
        inferred_cash_before_first_ledger_event=inferred_cash_before_first,
        cash_snapshot_checks=snapshot_checks,
        holdings_before_output_start=_holding_tuple(holdings_before_start, names),
        holdings_at_output_start=_holding_tuple(holdings_at_start, names),
        final_holdings=_holding_tuple(final_quantities, names),
        negative_holding_events=tuple(negative_holdings),
        rebase_quantity_checks=rebase_checks,
        source_row_counts={
            "ledger_entries": len(ledger),
            "close_prices": len(prices),
            "cash_balance_snapshots": len(snapshots),
            "position_cost_rebases": len(rebases),
        },
    )
    return AccountReconstruction(account_id, cash_anchor, scenarios, audit)


__all__ = [
    "AccountReconstruction",
    "AccountReconstructionError",
    "CashAnchor",
    "CashSnapshotCheck",
    "HoldingQuantity",
    "NegativeHoldingEvent",
    "PriceMark",
    "RebaseQuantityCheck",
    "ReconstructionAudit",
    "ReconstructionDay",
    "ReconstructionGap",
    "ReconstructionScenario",
    "ScenarioDiagnostics",
    "ledger_cash_delta",
    "open_formal_portfolio_read_only",
    "reconstruct_account_history",
    "sqlite_read_only_uri",
]
