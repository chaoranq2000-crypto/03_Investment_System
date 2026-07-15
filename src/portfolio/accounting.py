from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from .models import ClosedPositionCycle, LedgerCycle, PositionState, ZERO, row_decimal


class AccountingError(ValueError):
    """成交台账无法按日终周期和券商摊薄成本口径计算。"""


def _read(row: Any, key: str, default: Any = "") -> Any:
    if isinstance(row, Mapping):
        return row.get(key, default)
    try:
        return row[key]
    except (IndexError, KeyError):
        return default


def _event_date(row: Any) -> date:
    value = _read(row, "event_date")
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip())


def _rows_and_day_ends(rows: Iterable[Any]) -> tuple[list[Any], dict[tuple[str, date], int]]:
    """保留台账顺序，并标记每只证券每个交易日的最后一条事件。"""

    ordered = list(rows)
    last_index: dict[tuple[str, date], int] = {}
    for index, row in enumerate(ordered):
        key = (str(_read(row, "ts_code")).strip(), _event_date(row))
        last_index[key] = index
    return ordered, last_index


@dataclass
class _OpenCycle:
    cycle_number: int
    opened_on: date
    opening_event_type: str
    acquired_quantity: Decimal = ZERO
    sold_quantity: Decimal = ZERO
    cost_basis: Decimal = ZERO
    net_sale_proceeds: Decimal = ZERO
    trading_pnl: Decimal = ZERO
    cash_income: Decimal = ZERO
    cash_fees: Decimal = ZERO
    close_price: Decimal = ZERO
    buy_count: int = 0
    sell_count: int = 0


def build_position_states(rows: Iterable[Any]) -> dict[str, PositionState]:
    """按日终周期重放台账，并返回券商摊薄成本和已确认清仓盈亏。"""

    ordered_rows, last_index = _rows_and_day_ends(rows)
    states: dict[str, PositionState] = {}
    active_cycles: set[str] = set()
    for index, row in enumerate(ordered_rows):
        ts_code = str(_read(row, "ts_code")).strip()
        event_type = str(_read(row, "event_type")).strip().upper()
        event_day = _event_date(row)
        event_date = event_day.isoformat()
        state = states.setdefault(ts_code, PositionState(ts_code=ts_code))

        quantity = row_decimal(row, "quantity")
        gross_amount = row_decimal(row, "gross_amount")
        fees = row_decimal(row, "fees")
        total_cost = row_decimal(row, "total_cost")
        cash_amount = row_decimal(row, "cash_amount")

        if event_type == "OPENING":
            if quantity <= ZERO or total_cost < ZERO:
                raise AccountingError(f"{event_date} {ts_code}: 期初数量必须为正且成本不能为负")
            state.quantity += quantity
            state.remaining_cost += total_cost
            active_cycles.add(ts_code)
        elif event_type == "BUY":
            if quantity <= ZERO or gross_amount <= ZERO or fees < ZERO:
                raise AccountingError(f"{event_date} {ts_code}: 买入数量/金额必须为正，费用不能为负")
            state.quantity += quantity
            state.remaining_cost += gross_amount + fees
            active_cycles.add(ts_code)
        elif event_type == "SELL":
            if quantity <= ZERO or gross_amount <= ZERO or fees < ZERO:
                raise AccountingError(f"{event_date} {ts_code}: 卖出数量/金额必须为正，费用不能为负")
            if quantity > state.quantity:
                raise AccountingError(
                    f"{event_date} {ts_code}: 卖出 {quantity} 超过当时持仓 {state.quantity}"
                )
            state.quantity -= quantity
            state.remaining_cost -= gross_amount - fees
        elif event_type == "DIVIDEND":
            if cash_amount < ZERO:
                raise AccountingError(f"{event_date} {ts_code}: 现金红利不能为负")
            if ts_code in active_cycles:
                state.remaining_cost -= cash_amount
            else:
                state.cash_income += cash_amount
        elif event_type == "CASH_FEE":
            if cash_amount < ZERO:
                raise AccountingError(f"{event_date} {ts_code}: 现金税费不能为负")
            if ts_code in active_cycles:
                state.remaining_cost += cash_amount
            else:
                state.cash_fees += cash_amount
        elif event_type == "COST_REBASE":
            if ts_code not in active_cycles or state.quantity <= ZERO:
                raise AccountingError(f"{event_date} {ts_code}: 成本锚定前没有开放持仓")
            if quantity != state.quantity:
                raise AccountingError(
                    f"{event_date} {ts_code}: 成本锚定数量 {quantity} 与当时持仓 {state.quantity} 不一致"
                )
            if not total_cost.is_finite():
                raise AccountingError(f"{event_date} {ts_code}: 成本锚定值必须是有限数值")
            state.remaining_cost = total_cost
        else:
            raise AccountingError(f"{event_date} {ts_code}: 不支持的台账事件 {event_type!r}")

        day_key = (ts_code, event_day)
        if (
            last_index[day_key] == index
            and state.quantity == ZERO
            and ts_code in active_cycles
        ):
            # 日内临时归零不拆周期；只有日终仍为零才确认整个周期盈亏。
            state.realized_trading_pnl -= state.remaining_cost
            state.remaining_cost = ZERO
            active_cycles.remove(ts_code)

    return states


def build_closed_position_cycles(rows: Iterable[Any]) -> list[ClosedPositionCycle]:
    """重放台账，返回每次持仓在日终真正归零的完整清仓周期。"""

    ordered_rows, last_index = _rows_and_day_ends(rows)
    states: dict[str, PositionState] = {}
    active_cycles: dict[str, _OpenCycle] = {}
    cycle_counts: dict[str, int] = {}
    closed_cycles: list[ClosedPositionCycle] = []

    for index, row in enumerate(ordered_rows):
        ts_code = str(_read(row, "ts_code")).strip()
        event_type = str(_read(row, "event_type")).strip().upper()
        event_day = _event_date(row)
        state = states.setdefault(ts_code, PositionState(ts_code=ts_code))

        quantity = row_decimal(row, "quantity")
        gross_amount = row_decimal(row, "gross_amount")
        fees = row_decimal(row, "fees")
        total_cost = row_decimal(row, "total_cost")
        cash_amount = row_decimal(row, "cash_amount")

        if event_type in {"OPENING", "BUY"}:
            if event_type == "OPENING":
                if quantity <= ZERO or total_cost < ZERO:
                    raise AccountingError(
                        f"{event_day.isoformat()} {ts_code}: 期初数量必须为正且成本不能为负"
                    )
                acquisition_cost = total_cost
            else:
                if quantity <= ZERO or gross_amount <= ZERO or fees < ZERO:
                    raise AccountingError(
                        f"{event_day.isoformat()} {ts_code}: 买入数量/金额必须为正，费用不能为负"
                    )
                acquisition_cost = gross_amount + fees

            if ts_code not in active_cycles:
                cycle_number = cycle_counts.get(ts_code, 0) + 1
                cycle_counts[ts_code] = cycle_number
                active_cycles[ts_code] = _OpenCycle(
                    cycle_number=cycle_number,
                    opened_on=event_day,
                    opening_event_type=event_type,
                )
            cycle = active_cycles[ts_code]
            cycle.acquired_quantity += quantity
            cycle.cost_basis += acquisition_cost
            cycle.buy_count += int(event_type == "BUY")
            state.quantity += quantity
            state.remaining_cost += acquisition_cost
        elif event_type == "SELL":
            if quantity <= ZERO or gross_amount <= ZERO or fees < ZERO:
                raise AccountingError(
                    f"{event_day.isoformat()} {ts_code}: 卖出数量/金额必须为正，费用不能为负"
                )
            if quantity > state.quantity:
                raise AccountingError(
                    f"{event_day.isoformat()} {ts_code}: 卖出 {quantity} 超过当时持仓 {state.quantity}"
                )
            cycle = active_cycles.get(ts_code)
            if cycle is None:
                raise AccountingError(
                    f"{event_day.isoformat()} {ts_code}: 卖出前没有可追溯的持仓周期"
                )
            net_sale_proceeds = gross_amount - fees
            state.quantity -= quantity
            state.remaining_cost -= net_sale_proceeds
            cycle.sold_quantity += quantity
            cycle.net_sale_proceeds += net_sale_proceeds
            cycle.close_price = row_decimal(row, "price")
            cycle.sell_count += 1
        elif event_type == "DIVIDEND":
            if cash_amount < ZERO:
                raise AccountingError(
                    f"{event_day.isoformat()} {ts_code}: 现金红利不能为负"
                )
            state.cash_income += cash_amount
            if ts_code in active_cycles:
                active_cycles[ts_code].cash_income += cash_amount
                state.remaining_cost -= cash_amount
                state.cash_income -= cash_amount
        elif event_type == "CASH_FEE":
            if cash_amount < ZERO:
                raise AccountingError(
                    f"{event_day.isoformat()} {ts_code}: 现金税费不能为负"
                )
            state.cash_fees += cash_amount
            if ts_code in active_cycles:
                active_cycles[ts_code].cash_fees += cash_amount
                state.remaining_cost += cash_amount
                state.cash_fees -= cash_amount
        elif event_type == "COST_REBASE":
            cycle = active_cycles.get(ts_code)
            if cycle is None or state.quantity <= ZERO:
                raise AccountingError(
                    f"{event_day.isoformat()} {ts_code}: 成本锚定前没有开放持仓"
                )
            if quantity != state.quantity:
                raise AccountingError(
                    f"{event_day.isoformat()} {ts_code}: 成本锚定数量 {quantity} "
                    f"与当时持仓 {state.quantity} 不一致"
                )
            if not total_cost.is_finite():
                raise AccountingError(
                    f"{event_day.isoformat()} {ts_code}: 成本锚定值必须是有限数值"
                )
            cycle.cost_basis += total_cost - state.remaining_cost
            state.remaining_cost = total_cost
        else:
            raise AccountingError(
                f"{event_day.isoformat()} {ts_code}: 不支持的台账事件 {event_type!r}"
            )

        day_key = (ts_code, event_day)
        if (
            last_index[day_key] == index
            and state.quantity == ZERO
            and ts_code in active_cycles
        ):
            cycle = active_cycles.pop(ts_code)
            trading_pnl = cycle.net_sale_proceeds - cycle.cost_basis
            realized_pnl = trading_pnl + cycle.cash_income - cycle.cash_fees
            state.realized_trading_pnl += realized_pnl
            state.remaining_cost = ZERO
            closed_cycles.append(
                ClosedPositionCycle(
                    ts_code=ts_code,
                    cycle_number=cycle.cycle_number,
                    opened_on=cycle.opened_on,
                    closed_on=event_day,
                    opening_event_type=cycle.opening_event_type,
                    acquired_quantity=cycle.acquired_quantity,
                    sold_quantity=cycle.sold_quantity,
                    cost_basis=cycle.cost_basis,
                    net_sale_proceeds=cycle.net_sale_proceeds,
                    trading_pnl=trading_pnl,
                    cash_income=cycle.cash_income,
                    cash_fees=cycle.cash_fees,
                    realized_pnl=realized_pnl,
                    close_price=cycle.close_price,
                    buy_count=cycle.buy_count,
                    sell_count=cycle.sell_count,
                )
            )

    closed_cycles.sort(
        key=lambda item: (item.closed_on, item.ts_code, item.cycle_number), reverse=True
    )
    return closed_cycles


def build_ledger_cycles(rows: Iterable[Any]) -> list[LedgerCycle]:
    """按证券和轮次归集原始台账行，供操作复盘与当前周期定位使用。"""

    ordered_rows, last_index = _rows_and_day_ends(rows)
    # 先执行完整会计校验，避免周期视图掩盖超卖或非法金额等台账错误。
    build_position_states(ordered_rows)
    quantities: dict[str, Decimal] = {}
    cycle_counts: dict[str, int] = {}
    active: dict[str, LedgerCycle] = {}
    cycles: list[LedgerCycle] = []

    for index, row in enumerate(ordered_rows):
        ts_code = str(_read(row, "ts_code")).strip()
        event_type = str(_read(row, "event_type")).strip().upper()
        event_day = _event_date(row)
        quantity = row_decimal(row, "quantity")
        current_quantity = quantities.get(ts_code, ZERO)

        if event_type in {"OPENING", "BUY"}:
            if ts_code not in active:
                cycle_number = cycle_counts.get(ts_code, 0) + 1
                cycle_counts[ts_code] = cycle_number
                cycle = LedgerCycle(
                    ts_code=ts_code,
                    cycle_number=cycle_number,
                    opened_on=event_day,
                    opening_event_type=event_type,
                )
                active[ts_code] = cycle
                cycles.append(cycle)
            active[ts_code].entries.append(row)
            quantities[ts_code] = current_quantity + quantity
        elif event_type == "SELL":
            cycle = active.get(ts_code)
            if cycle is None:
                raise AccountingError(
                    f"{event_day.isoformat()} {ts_code}: 卖出前没有可追溯的持仓周期"
                )
            cycle.entries.append(row)
            next_quantity = current_quantity - quantity
            quantities[ts_code] = next_quantity
        elif event_type in {"DIVIDEND", "CASH_FEE", "COST_REBASE"}:
            if ts_code in active:
                active[ts_code].entries.append(row)

        day_key = (ts_code, event_day)
        if (
            last_index[day_key] == index
            and quantities.get(ts_code, ZERO) == ZERO
            and ts_code in active
        ):
            active[ts_code].closed_on = event_day
            del active[ts_code]

    return cycles


def portfolio_totals(position_rows: Iterable[Mapping[str, Any]]) -> dict[str, Decimal]:
    totals = {
        "remaining_cost": ZERO,
        "market_value": ZERO,
        "unrealized_pnl": ZERO,
        "realized_pnl": ZERO,
        "total_pnl": ZERO,
    }
    for row in position_rows:
        for key in totals:
            value = row.get(key)
            if value is not None:
                totals[key] += Decimal(str(value))
    return totals
