from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from .models import ClosedPositionCycle, PositionState, ZERO, row_decimal


class AccountingError(ValueError):
    """成交台账无法按移动加权平均成本法计算。"""


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
    """按输入顺序重放台账，并返回每只证券的剩余成本和已实现盈亏。"""

    states: dict[str, PositionState] = {}
    for row in rows:
        ts_code = str(_read(row, "ts_code")).strip()
        event_type = str(_read(row, "event_type")).strip().upper()
        event_date = str(_read(row, "event_date")).strip()
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
            continue

        if event_type == "BUY":
            if quantity <= ZERO or gross_amount <= ZERO or fees < ZERO:
                raise AccountingError(f"{event_date} {ts_code}: 买入数量/金额必须为正，费用不能为负")
            state.quantity += quantity
            state.remaining_cost += gross_amount + fees
            continue

        if event_type == "SELL":
            if quantity <= ZERO or gross_amount <= ZERO or fees < ZERO:
                raise AccountingError(f"{event_date} {ts_code}: 卖出数量/金额必须为正，费用不能为负")
            if quantity > state.quantity:
                raise AccountingError(
                    f"{event_date} {ts_code}: 卖出 {quantity} 超过当时持仓 {state.quantity}"
                )
            average_cost = state.remaining_cost / state.quantity
            released_cost = average_cost * quantity
            state.quantity -= quantity
            state.remaining_cost -= released_cost
            state.realized_trading_pnl += gross_amount - fees - released_cost
            if state.quantity == ZERO:
                state.remaining_cost = ZERO
            continue

        if event_type == "DIVIDEND":
            if cash_amount < ZERO:
                raise AccountingError(f"{event_date} {ts_code}: 现金红利不能为负")
            state.cash_income += cash_amount
            continue

        if event_type == "CASH_FEE":
            if cash_amount < ZERO:
                raise AccountingError(f"{event_date} {ts_code}: 现金税费不能为负")
            state.cash_fees += cash_amount
            continue

        raise AccountingError(f"{event_date} {ts_code}: 不支持的台账事件 {event_type!r}")

    return states


def build_closed_position_cycles(rows: Iterable[Any]) -> list[ClosedPositionCycle]:
    """重放台账，返回每次持仓数量从正数归零的完整清仓周期。"""

    states: dict[str, PositionState] = {}
    active_cycles: dict[str, _OpenCycle] = {}
    cycle_counts: dict[str, int] = {}
    closed_cycles: list[ClosedPositionCycle] = []

    for row in rows:
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

            if state.quantity == ZERO:
                cycle_number = cycle_counts.get(ts_code, 0) + 1
                cycle_counts[ts_code] = cycle_number
                active_cycles[ts_code] = _OpenCycle(
                    cycle_number=cycle_number,
                    opened_on=event_day,
                    opening_event_type=event_type,
                )
            cycle = active_cycles[ts_code]
            cycle.acquired_quantity += quantity
            cycle.buy_count += int(event_type == "BUY")
            state.quantity += quantity
            state.remaining_cost += acquisition_cost
            continue

        if event_type == "SELL":
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
            average_cost = state.remaining_cost / state.quantity
            released_cost = average_cost * quantity
            net_sale_proceeds = gross_amount - fees
            trading_pnl = net_sale_proceeds - released_cost
            state.quantity -= quantity
            state.remaining_cost -= released_cost
            state.realized_trading_pnl += trading_pnl
            cycle.sold_quantity += quantity
            cycle.cost_basis += released_cost
            cycle.net_sale_proceeds += net_sale_proceeds
            cycle.trading_pnl += trading_pnl
            cycle.close_price = row_decimal(row, "price")
            cycle.sell_count += 1
            if state.quantity == ZERO:
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
                        trading_pnl=cycle.trading_pnl,
                        cash_income=cycle.cash_income,
                        cash_fees=cycle.cash_fees,
                        realized_pnl=(
                            cycle.trading_pnl + cycle.cash_income - cycle.cash_fees
                        ),
                        close_price=cycle.close_price,
                        buy_count=cycle.buy_count,
                        sell_count=cycle.sell_count,
                    )
                )
                del active_cycles[ts_code]
            continue

        if event_type == "DIVIDEND":
            if cash_amount < ZERO:
                raise AccountingError(
                    f"{event_day.isoformat()} {ts_code}: 现金红利不能为负"
                )
            state.cash_income += cash_amount
            if ts_code in active_cycles:
                active_cycles[ts_code].cash_income += cash_amount
            continue

        if event_type == "CASH_FEE":
            if cash_amount < ZERO:
                raise AccountingError(
                    f"{event_day.isoformat()} {ts_code}: 现金税费不能为负"
                )
            state.cash_fees += cash_amount
            if ts_code in active_cycles:
                active_cycles[ts_code].cash_fees += cash_amount
            continue

        raise AccountingError(
            f"{event_day.isoformat()} {ts_code}: 不支持的台账事件 {event_type!r}"
        )

    closed_cycles.sort(
        key=lambda item: (item.closed_on, item.ts_code, item.cycle_number), reverse=True
    )
    return closed_cycles


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
