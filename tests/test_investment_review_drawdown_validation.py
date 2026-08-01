from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.investment_review.drawdown_validation import (
    DEFENSE_30_RULE,
    ELASTIC_35_RULE,
    DailyBaseline,
    OverlayConfig,
    run_pre_registered_strategies,
    run_strategy,
)


def _days(
    returns: list[float],
    *,
    turnover: float = 0.0,
    start: date = date(2025, 1, 2),
) -> list[DailyBaseline]:
    return [
        DailyBaseline(start + timedelta(days=index), value, turnover=turnover)
        for index, value in enumerate(returns)
    ]


def test_exact_thresholds_enter_defensive_band() -> None:
    assert DEFENSE_30_RULE.state_for_drawdown(0.20 - 1e-9) == 0
    assert DEFENSE_30_RULE.state_for_drawdown(0.20) == 1
    assert DEFENSE_30_RULE.state_for_drawdown(0.25) == 2
    assert DEFENSE_30_RULE.state_for_drawdown(0.30) == 3

    assert ELASTIC_35_RULE.state_for_drawdown(0.25 - 1e-9) == 0
    assert ELASTIC_35_RULE.state_for_drawdown(0.25) == 1
    assert ELASTIC_35_RULE.state_for_drawdown(0.30) == 2
    assert ELASTIC_35_RULE.state_for_drawdown(0.35) == 3


def test_close_signal_cannot_change_same_day_exposure() -> None:
    result = run_strategy(_days([-0.20, 0.04]), DEFENSE_30_RULE)

    assert result.daily[0].signal_state == 1
    assert result.daily[0].applied_exposure == 1.0
    assert result.daily[1].applied_exposure == 0.75


def test_future_changes_do_not_change_any_historical_prefix_row() -> None:
    prefix = _days([-0.21, 0.01, -0.02, 0.03])
    first = run_strategy(prefix, DEFENSE_30_RULE)
    full = run_strategy(prefix + _days([0.80, -0.70], start=date(2025, 2, 1)), DEFENSE_30_RULE)

    assert full.daily[: len(prefix)] == first.daily


def test_execution_delay_counts_only_tradable_observations() -> None:
    rows = _days([-0.21, 0.00, 0.00, 0.00])
    rows[1] = DailyBaseline(rows[1].trade_date, 0.00, tradable=False)
    result = run_strategy(
        rows,
        DEFENSE_30_RULE,
        OverlayConfig(execution_delay_days=2),
    )

    assert [row.applied_exposure for row in result.daily] == [1.0, 1.0, 1.0, 0.75]
    with pytest.raises(ValueError, match="at least one"):
        OverlayConfig(execution_delay_days=0)


def test_recovery_waits_and_moves_only_one_state_per_close() -> None:
    returns = [-0.31] + [0.0] * 10 + [0.20, 0.20, 0.10]
    result = run_strategy(_days(returns), DEFENSE_30_RULE)

    assert result.daily[0].signal_state == 3
    assert all(row.signal_state == 3 for row in result.daily[1:11])
    assert [row.signal_state for row in result.daily[11:]] == [2, 1, 0]
    changes = [
        right.signal_state - left.signal_state
        for left, right in zip(result.daily, result.daily[1:])
    ]
    assert all(change >= -1 for change in changes)
    assert result.metrics.de_risk_trigger_count == 1
    assert result.metrics.re_risk_trigger_count == 3


def test_fees_and_slippage_lower_nav_and_are_reported() -> None:
    observations = _days([-0.21, 0.04, 0.03, 0.02], turnover=0.20)
    free = run_strategy(observations, DEFENSE_30_RULE, OverlayConfig())
    costly = run_strategy(
        observations,
        DEFENSE_30_RULE,
        OverlayConfig(fee_rate=0.001, slippage_bps=20.0),
    )

    assert costly.metrics.final_nav < free.metrics.final_nav
    assert costly.metrics.total_transaction_cost > 0.0
    assert costly.metrics.total_turnover > costly.metrics.overlay_turnover


def test_all_registered_rules_return_required_metrics_and_state_shares() -> None:
    comparison = run_pre_registered_strategies(_days([0.02, -0.30, 0.05, 0.05]))

    assert [result.rule.name for result in comparison.results] == [
        "baseline",
        "defense_30",
        "elastic_35",
    ]
    for result in comparison.results:
        metrics = result.metrics
        assert metrics.final_nav > 0.0
        assert metrics.net_cagr == pytest.approx(
            (metrics.final_nav / metrics.initial_nav) ** (252 / len(result.daily)) - 1
        )
        assert 0.0 <= metrics.max_drawdown < 1.0
        assert metrics.longest_underwater_days >= metrics.current_underwater_days
        assert sum(metrics.state_share.values()) == pytest.approx(1.0)
        assert metrics.worst_day in {row.trade_date for row in result.daily}


def test_results_are_deterministic_and_json_ready() -> None:
    observations = [
        {"trade_date": "2025-01-02", "gross_return": -0.21, "turnover": 0.1},
        {"trade_date": "2025-01-03", "gross_return": 0.02, "turnover": 0.1},
    ]
    config = OverlayConfig(fee_rate=0.0003, slippage_bps=10.0)

    first = run_pre_registered_strategies(observations, config)
    second = run_pre_registered_strategies(observations, config)

    assert first == second
    assert first.by_name("defense_30").to_dict()["daily"][0]["trade_date"] == "2025-01-02"
