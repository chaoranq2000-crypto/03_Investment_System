from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any


ZERO = Decimal("0")
SUPPORTED_EVENT_TYPES = {
    "OPENING",
    "BUY",
    "SELL",
    "DIVIDEND",
    "CASH_FEE",
    "COST_REBASE",
}
SUPPORTED_ASSET_TYPES = {"equity", "etf", "unknown"}


@dataclass(frozen=True)
class Instrument:
    ts_code: str
    name: str
    asset_type: str = "unknown"

    @property
    def exchange(self) -> str:
        return self.ts_code.rsplit(".", 1)[-1] if "." in self.ts_code else ""


@dataclass(frozen=True)
class LedgerEntry:
    account_id: str
    event_date: date
    event_type: str
    ts_code: str
    quantity: Decimal = ZERO
    event_time: str = ""
    price: Decimal = ZERO
    gross_amount: Decimal = ZERO
    fees: Decimal = ZERO
    total_cost: Decimal = ZERO
    cash_amount: Decimal = ZERO
    external_id: str = ""
    dedupe_key: str = ""
    import_batch_id: str = ""
    source_row: int | None = None
    note: str = ""


@dataclass(frozen=True)
class ClosePrice:
    ts_code: str
    trade_date: date
    close: Decimal
    source: str
    pre_close: Decimal | None = None
    pct_chg: Decimal | None = None
    fetched_at: str = ""


@dataclass(frozen=True)
class DailyBarObservation:
    ts_code: str
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume_lots: Decimal
    amount_k_cny: Decimal
    source: str
    refresh_batch_id: str
    dedupe_key: str
    fetched_at: str = ""


@dataclass(frozen=True)
class AdjustmentFactorObservation:
    ts_code: str
    trade_date: date
    adj_factor: Decimal
    source: str
    refresh_batch_id: str
    dedupe_key: str
    fetched_at: str = ""


@dataclass(frozen=True)
class MinuteBarObservation:
    ts_code: str
    bar_time: datetime
    frequency_minutes: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume_shares: Decimal
    amount_cny: Decimal
    source: str
    refresh_batch_id: str
    dedupe_key: str
    fetched_at: str = ""


@dataclass(frozen=True)
class IndustryClassification:
    ts_code: str
    industry_name: str
    source: str
    classified_at: str = ""
    method: str = ""
    source_date: str = ""
    confidence: str = ""


@dataclass
class PositionState:
    ts_code: str
    quantity: Decimal = ZERO
    remaining_cost: Decimal = ZERO
    realized_trading_pnl: Decimal = ZERO
    cash_income: Decimal = ZERO
    cash_fees: Decimal = ZERO

    @property
    def average_cost(self) -> Decimal | None:
        if self.quantity == ZERO:
            return None
        return self.remaining_cost / self.quantity

    @property
    def realized_pnl(self) -> Decimal:
        return self.realized_trading_pnl + self.cash_income - self.cash_fees


@dataclass(frozen=True)
class ClosedPositionCycle:
    ts_code: str
    cycle_number: int
    opened_on: date
    closed_on: date
    opening_event_type: str
    acquired_quantity: Decimal
    sold_quantity: Decimal
    cost_basis: Decimal
    net_sale_proceeds: Decimal
    trading_pnl: Decimal
    cash_income: Decimal
    cash_fees: Decimal
    realized_pnl: Decimal
    close_price: Decimal
    buy_count: int
    sell_count: int

    @property
    def return_pct(self) -> Decimal | None:
        if self.cost_basis == ZERO:
            return None
        return self.realized_pnl / self.cost_basis * Decimal("100")

    @property
    def holding_days(self) -> int:
        return (self.closed_on - self.opened_on).days


@dataclass
class LedgerCycle:
    ts_code: str
    cycle_number: int
    opened_on: date
    opening_event_type: str
    entries: list[Any] = field(default_factory=list)
    closed_on: date | None = None

    @property
    def cycle_id(self) -> str:
        return f"{self.ts_code}:{self.cycle_number}"

    @property
    def is_closed(self) -> bool:
        return self.closed_on is not None


@dataclass(frozen=True)
class ImportIssue:
    row_number: int
    severity: str
    message: str
    raw_event: str = ""
    ts_code: str = ""


@dataclass
class StatementParseResult:
    source_name: str
    source_sha256: str
    instruments: dict[str, Instrument] = field(default_factory=dict)
    entries: list[LedgerEntry] = field(default_factory=list)
    issues: list[ImportIssue] = field(default_factory=list)
    skipped_rows: int = 0
    total_rows: int = 0

    @property
    def errors(self) -> list[ImportIssue]:
        return [item for item in self.issues if item.severity == "error"]


@dataclass
class OpeningParseResult:
    source_name: str
    source_sha256: str
    instruments: dict[str, Instrument] = field(default_factory=dict)
    entries: list[LedgerEntry] = field(default_factory=list)
    prices: list[ClosePrice] = field(default_factory=list)
    issues: list[ImportIssue] = field(default_factory=list)
    total_rows: int = 0

    @property
    def errors(self) -> list[ImportIssue]:
        return [item for item in self.issues if item.severity == "error"]


def decimal_to_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    if value == ZERO:
        return "0"
    return format(value.normalize(), "f")


def row_decimal(row: Any, key: str) -> Decimal:
    value = row[key]
    if value in (None, ""):
        return ZERO
    return Decimal(str(value))
