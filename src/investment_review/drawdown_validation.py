"""Deterministic, causal drawdown-overlay simulations for P10.

The engine consumes an abstract daily return stream.  It deliberately does not
read the formal portfolio database or pretend to reconstruct individual fills.
Signals are formed after day ``t`` closes and may only change exposure on a
later tradable observation.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import asdict, dataclass
from datetime import date
from math import prod
from typing import Iterable, Mapping


_EPSILON = 1e-12


@dataclass(frozen=True)
class DailyBaseline:
    """One full-risk-sleeve observation before simulated transaction costs.

    ``turnover`` is the underlying portfolio turnover as a fraction of NAV at
    100% exposure.  Overlay exposure changes are added separately.  Set
    ``reference_return`` when upside participation should use an external
    benchmark instead of the baseline gross return.
    """

    trade_date: date
    gross_return: float
    turnover: float = 0.0
    reference_return: float | None = None
    tradable: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.trade_date, date):
            raise TypeError("trade_date must be datetime.date")
        if self.gross_return <= -1.0:
            raise ValueError("gross_return must be greater than -1")
        if self.turnover < 0.0:
            raise ValueError("turnover must be non-negative")
        if self.reference_return is not None and self.reference_return <= -1.0:
            raise ValueError("reference_return must be greater than -1")


@dataclass(frozen=True)
class DrawdownRule:
    """Pre-registered drawdown bands and their maximum equity exposures."""

    name: str
    thresholds: tuple[float, ...]
    exposures: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("rule name is required")
        if len(self.exposures) != len(self.thresholds) + 1:
            raise ValueError("exposures must contain one more value than thresholds")
        if tuple(sorted(self.thresholds)) != self.thresholds:
            raise ValueError("thresholds must be ascending")
        if any(value <= 0.0 or value >= 1.0 for value in self.thresholds):
            raise ValueError("thresholds must be strictly between zero and one")
        if any(value < 0.0 or value > 1.0 for value in self.exposures):
            raise ValueError("exposures must be between zero and one")
        if any(left < right for left, right in zip(self.exposures, self.exposures[1:])):
            raise ValueError("exposures must be non-increasing")

    def state_for_drawdown(self, drawdown: float) -> int:
        """Return the band index; an exact boundary enters the defensive band."""

        if drawdown < -_EPSILON:
            raise ValueError("drawdown must be non-negative")
        # NAV arithmetic can represent an exact 20% loss as
        # 0.19999999999999996.  The tiny tolerance keeps contractual boundary
        # semantics without moving observations that are materially below it.
        return bisect_right(self.thresholds, max(0.0, drawdown) + _EPSILON)


BASELINE_RULE = DrawdownRule("baseline", (), (1.0,))
DEFENSE_30_RULE = DrawdownRule(
    "defense_30",
    (0.20, 0.25, 0.30),
    (1.00, 0.75, 0.50, 0.25),
)
ELASTIC_35_RULE = DrawdownRule(
    "elastic_35",
    (0.25, 0.30, 0.35),
    (1.00, 0.75, 0.50, 0.25),
)
PRE_REGISTERED_RULES = (BASELINE_RULE, DEFENSE_30_RULE, ELASTIC_35_RULE)


@dataclass(frozen=True)
class OverlayConfig:
    """Execution and hysteresis assumptions used by all compared rules."""

    initial_nav: float = 1.0
    execution_delay_days: int = 1
    fee_rate: float = 0.0
    slippage_bps: float = 0.0
    cooldown_days: int = 10
    no_new_low_days: int = 5
    recovery_points: float = 0.03
    periods_per_year: int = 252

    def __post_init__(self) -> None:
        if self.initial_nav <= 0.0:
            raise ValueError("initial_nav must be positive")
        if self.execution_delay_days < 1:
            raise ValueError("execution_delay_days must be at least one")
        if self.fee_rate < 0.0 or self.slippage_bps < 0.0:
            raise ValueError("fee_rate and slippage_bps must be non-negative")
        if self.cooldown_days < 0 or self.no_new_low_days < 0:
            raise ValueError("cooldown and confirmation windows must be non-negative")
        if self.recovery_points < 0.0:
            raise ValueError("recovery_points must be non-negative")
        if self.periods_per_year <= 0:
            raise ValueError("periods_per_year must be positive")

    @property
    def transaction_cost_rate(self) -> float:
        return self.fee_rate + self.slippage_bps / 10_000.0


@dataclass(frozen=True)
class StrategyDay:
    trade_date: date
    gross_return: float
    reference_return: float
    tradable: bool
    applied_state: int
    signal_state: int
    applied_exposure: float
    signal_exposure: float
    overlay_turnover: float
    underlying_turnover: float
    transaction_cost: float
    transaction_cost_fraction: float
    net_return: float
    nav: float
    peak_nav: float
    drawdown: float
    signal_event: str | None


@dataclass(frozen=True)
class StrategyMetrics:
    initial_nav: float
    final_nav: float
    net_total_return: float
    net_cagr: float
    max_drawdown: float
    calmar: float | None
    longest_underwater_days: int
    longest_completed_recovery_days: int | None
    current_underwater_days: int
    recovery_count: int
    unrecovered: bool
    upside_participation: float | None
    total_turnover: float
    overlay_turnover: float
    underlying_turnover: float
    total_transaction_cost: float
    transaction_cost_fraction_initial: float
    trigger_count: int
    de_risk_trigger_count: int
    re_risk_trigger_count: int
    state_share: dict[str, float]
    average_exposure: float
    worst_daily_return: float
    worst_day: date


@dataclass(frozen=True)
class StrategyResult:
    rule: DrawdownRule
    config: OverlayConfig
    daily: tuple[StrategyDay, ...]
    metrics: StrategyMetrics

    def to_dict(self) -> dict[str, object]:
        """Return a stable, JSON-ready representation for later report writers."""

        payload = asdict(self)
        for row in payload["daily"]:
            row["trade_date"] = row["trade_date"].isoformat()
        payload["metrics"]["worst_day"] = payload["metrics"]["worst_day"].isoformat()
        return payload


@dataclass(frozen=True)
class BacktestComparison:
    results: tuple[StrategyResult, ...]

    def by_name(self, name: str) -> StrategyResult:
        for result in self.results:
            if result.rule.name == name:
                return result
        raise KeyError(name)


@dataclass
class _PolicyState:
    signal_state: int = 0
    last_downgrade_index: int | None = None
    deepest_drawdown: float = 0.0
    last_new_low_index: int | None = None


@dataclass(frozen=True)
class _PendingOrder:
    due_trading_ordinal: int
    signal_index: int
    target_state: int


def _coerce_day(value: DailyBaseline | Mapping[str, object]) -> DailyBaseline:
    if isinstance(value, DailyBaseline):
        return value
    payload = dict(value)
    raw_date = payload.get("trade_date")
    if isinstance(raw_date, str):
        payload["trade_date"] = date.fromisoformat(raw_date)
    return DailyBaseline(**payload)  # type: ignore[arg-type]


def _normalize_days(
    observations: Iterable[DailyBaseline | Mapping[str, object]],
) -> tuple[DailyBaseline, ...]:
    days = tuple(_coerce_day(value) for value in observations)
    if not days:
        raise ValueError("at least one daily observation is required")
    for previous, current in zip(days, days[1:]):
        if current.trade_date <= previous.trade_date:
            raise ValueError("trade_date values must be strictly increasing")
    return days


def _next_signal_state(
    *,
    rule: DrawdownRule,
    runtime: _PolicyState,
    drawdown: float,
    index: int,
    config: OverlayConfig,
) -> tuple[int, str | None]:
    raw_state = rule.state_for_drawdown(drawdown)
    current = runtime.signal_state
    if raw_state > current:
        runtime.signal_state = raw_state
        runtime.last_downgrade_index = index
        runtime.deepest_drawdown = drawdown
        runtime.last_new_low_index = index
        return raw_state, "de_risk"

    if current == 0:
        return current, None

    if drawdown > runtime.deepest_drawdown + _EPSILON:
        runtime.deepest_drawdown = drawdown
        runtime.last_new_low_index = index

    downgrade_index = runtime.last_downgrade_index
    low_index = runtime.last_new_low_index
    cooldown_ok = downgrade_index is not None and index - downgrade_index >= config.cooldown_days
    no_new_low_ok = low_index is not None and index - low_index >= config.no_new_low_days
    recovery_ok = runtime.deepest_drawdown - drawdown + _EPSILON >= config.recovery_points
    band_allows_upgrade = raw_state < current
    if cooldown_ok and no_new_low_ok and recovery_ok and band_allows_upgrade:
        runtime.signal_state = current - 1
        return runtime.signal_state, "re_risk"
    return current, None


def _upside_participation(rows: tuple[StrategyDay, ...]) -> float | None:
    upside = tuple(row for row in rows if row.reference_return > 0.0)
    if not upside:
        return None
    reference_gain = prod(1.0 + row.reference_return for row in upside) - 1.0
    if abs(reference_gain) <= _EPSILON:
        return None
    strategy_gain = prod(1.0 + row.net_return for row in upside) - 1.0
    return strategy_gain / reference_gain


def _state_share(rule: DrawdownRule, rows: tuple[StrategyDay, ...]) -> dict[str, float]:
    counts = [0] * len(rule.exposures)
    for row in rows:
        counts[row.applied_state] += 1
    total = len(rows)
    return {
        f"{round(exposure * 100):d}%": counts[index] / total
        for index, exposure in enumerate(rule.exposures)
    }


def _build_metrics(
    rule: DrawdownRule,
    config: OverlayConfig,
    rows: tuple[StrategyDay, ...],
) -> StrategyMetrics:
    final_nav = rows[-1].nav
    net_return = final_nav / config.initial_nav - 1.0
    years = len(rows) / config.periods_per_year
    cagr = (final_nav / config.initial_nav) ** (1.0 / years) - 1.0
    maximum_drawdown = max(row.drawdown for row in rows)
    calmar = None if maximum_drawdown <= _EPSILON else cagr / maximum_drawdown

    underwater = 0
    longest_underwater = 0
    completed: list[int] = []
    for row in rows:
        if row.drawdown > _EPSILON:
            underwater += 1
            longest_underwater = max(longest_underwater, underwater)
        elif underwater:
            completed.append(underwater)
            underwater = 0

    overlay_turnover = sum(row.overlay_turnover for row in rows)
    underlying_turnover = sum(row.underlying_turnover for row in rows)
    total_cost = sum(row.transaction_cost for row in rows)
    de_risk = sum(row.signal_event == "de_risk" for row in rows)
    re_risk = sum(row.signal_event == "re_risk" for row in rows)
    worst = min(rows, key=lambda row: (row.net_return, row.trade_date))

    return StrategyMetrics(
        initial_nav=config.initial_nav,
        final_nav=final_nav,
        net_total_return=net_return,
        net_cagr=cagr,
        max_drawdown=maximum_drawdown,
        calmar=calmar,
        longest_underwater_days=longest_underwater,
        longest_completed_recovery_days=max(completed) if completed else None,
        current_underwater_days=underwater,
        recovery_count=len(completed),
        unrecovered=underwater > 0,
        upside_participation=_upside_participation(rows),
        total_turnover=overlay_turnover + underlying_turnover,
        overlay_turnover=overlay_turnover,
        underlying_turnover=underlying_turnover,
        total_transaction_cost=total_cost,
        transaction_cost_fraction_initial=total_cost / config.initial_nav,
        trigger_count=de_risk + re_risk,
        de_risk_trigger_count=de_risk,
        re_risk_trigger_count=re_risk,
        state_share=_state_share(rule, rows),
        average_exposure=sum(row.applied_exposure for row in rows) / len(rows),
        worst_daily_return=worst.net_return,
        worst_day=worst.trade_date,
    )


def run_strategy(
    observations: Iterable[DailyBaseline | Mapping[str, object]],
    rule: DrawdownRule,
    config: OverlayConfig | None = None,
) -> StrategyResult:
    """Run one causal overlay rule on a full-risk daily baseline."""

    days = _normalize_days(observations)
    settings = config or OverlayConfig()
    runtime = _PolicyState()
    pending: list[_PendingOrder] = []
    applied_state = 0
    trading_ordinal = -1
    nav = settings.initial_nav
    peak = nav
    rows: list[StrategyDay] = []

    for index, day in enumerate(days):
        if day.tradable:
            trading_ordinal += 1
            due = [order for order in pending if order.due_trading_ordinal <= trading_ordinal]
            if due:
                applied_state = max(due, key=lambda order: order.signal_index).target_state
                pending = [
                    order for order in pending if order.due_trading_ordinal > trading_ordinal
                ]

        previous_exposure = rows[-1].applied_exposure if rows else rule.exposures[0]
        exposure = rule.exposures[applied_state]
        overlay_turnover = abs(exposure - previous_exposure)
        underlying_turnover = day.turnover * exposure
        total_turnover = overlay_turnover + underlying_turnover
        cost_fraction = total_turnover * settings.transaction_cost_rate
        if cost_fraction >= 1.0:
            raise ValueError("transaction costs would exhaust NAV")

        previous_nav = nav
        transaction_cost = previous_nav * cost_fraction
        nav = previous_nav * (1.0 - cost_fraction) * (1.0 + exposure * day.gross_return)
        net_return = nav / previous_nav - 1.0
        peak = max(peak, nav)
        drawdown = max(0.0, 1.0 - nav / peak)

        old_signal_state = runtime.signal_state
        signal_state, signal_event = _next_signal_state(
            rule=rule,
            runtime=runtime,
            drawdown=drawdown,
            index=index,
            config=settings,
        )
        if signal_state != old_signal_state:
            pending.append(
                _PendingOrder(
                    due_trading_ordinal=trading_ordinal + settings.execution_delay_days,
                    signal_index=index,
                    target_state=signal_state,
                )
            )

        rows.append(
            StrategyDay(
                trade_date=day.trade_date,
                gross_return=day.gross_return,
                reference_return=(
                    day.gross_return if day.reference_return is None else day.reference_return
                ),
                tradable=day.tradable,
                applied_state=applied_state,
                signal_state=signal_state,
                applied_exposure=exposure,
                signal_exposure=rule.exposures[signal_state],
                overlay_turnover=overlay_turnover,
                underlying_turnover=underlying_turnover,
                transaction_cost=transaction_cost,
                transaction_cost_fraction=cost_fraction,
                net_return=net_return,
                nav=nav,
                peak_nav=peak,
                drawdown=drawdown,
                signal_event=signal_event,
            )
        )

    frozen_rows = tuple(rows)
    return StrategyResult(
        rule=rule,
        config=settings,
        daily=frozen_rows,
        metrics=_build_metrics(rule, settings, frozen_rows),
    )


def run_pre_registered_strategies(
    observations: Iterable[DailyBaseline | Mapping[str, object]],
    config: OverlayConfig | None = None,
) -> BacktestComparison:
    """Run baseline, ``defense_30`` and ``elastic_35`` on identical data."""

    days = _normalize_days(observations)
    settings = config or OverlayConfig()
    return BacktestComparison(
        tuple(run_strategy(days, rule, settings) for rule in PRE_REGISTERED_RULES)
    )
