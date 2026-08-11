from __future__ import annotations

import json

from src.investment_review.periodic_reports import build_recommendation


def _snapshot() -> dict[str, object]:
    return {
        "total_assets_cny": "100000",
        "cash_weight_pct": "1",
        "top_position_weight_pct": "30",
        "top3_weight_pct": "70",
        "cash": {"fee_pending": True},
        "positions": [
            {
                "ts_code": "000001.SZ",
                "portfolio_weight_pct": "13",
                "close_cny": "11",
                "average_cost_cny": "15",
                "price_date": "2026-07-15",
                "source_refs": [
                    "portfolio.sqlite3#ledger_entries:000001.SZ"
                ],
            },
            {
                "ts_code": "000002.SZ",
                "portfolio_weight_pct": "30",
                "close_cny": "20",
                "average_cost_cny": "18",
                "price_date": "2026-07-15",
                "source_refs": [
                    "portfolio.sqlite3#ledger_entries:000002.SZ"
                ],
            },
        ],
    }


def _assert_observation_only(recommendation: dict[str, object]) -> None:
    assert recommendation["mode"] == "observation_only"
    assert recommendation["decision_basis"] is None
    assert recommendation["user_risk_budget"] is None
    assert recommendation["action"] is None
    assert recommendation["target_position"] is None
    assert recommendation["orders_executed"] is False
    assert recommendation["guaranteed_return"] is False
    serialized = json.dumps(recommendation, ensure_ascii=False).lower()
    for action in ("buy", "sell", "hold", "add", "reduce", "exit"):
        assert f'"{action}"' not in serialized


def test_instrument_without_explicit_user_policy_is_observation_only() -> None:
    recommendation = build_recommendation(
        subject_type="instrument",
        subject_id="000001.SZ",
        snapshot=_snapshot(),
        report_cutoff_at="2026-07-15T15:00:00+08:00",
    )

    _assert_observation_only(recommendation)
    assert recommendation["major_downside_risks"]
    assert recommendation["invalidation_conditions"]
    assert recommendation["report_cutoff_at"] == (
        "2026-07-15T15:00:00+08:00"
    )
    assert recommendation["data_timestamp"] <= recommendation["report_cutoff_at"]
    assert "MISSING_EXPLICIT_USER_REVIEW_MODE" in (
        recommendation["important_missing_inputs"]
    )
    assert "MISSING_EXPLICIT_USER_RISK_POLICY" in (
        recommendation["important_missing_inputs"]
    )
    assert "MISSING_FUNDAMENTAL_AND_VALUATION_CONTEXT" in (
        recommendation["important_missing_inputs"]
    )


def test_portfolio_without_explicit_user_policy_is_observation_only() -> None:
    recommendation = build_recommendation(
        subject_type="portfolio",
        subject_id="default",
        snapshot=_snapshot(),
        report_cutoff_at="2026-07-15T15:00:00+08:00",
    )

    _assert_observation_only(recommendation)
    assert any(
        item["type"] == "fact" for item in recommendation["rationale"]
    )


def test_explicit_instrument_policy_uses_only_user_supplied_range() -> None:
    recommendation = build_recommendation(
        subject_type="instrument",
        subject_id="000001.SZ",
        snapshot=_snapshot(),
        report_cutoff_at="2026-07-15T15:00:00+08:00",
        review_mode="advice",
        risk_policy={
            "time_horizon": "未来十二个月",
            "risk_budget": "最大可承受本金损失 10%",
            "target_position_range_pct": ["7", "9"],
        },
    )

    assert recommendation["mode"] == "advice"
    assert recommendation["decision_basis"] == "user_policy_trigger"
    assert recommendation["user_risk_budget"] == "最大可承受本金损失 10%"
    assert recommendation["action"] == "reduce"
    assert recommendation["target_position"]["target_position_range_pct"] == [
        "7",
        "9",
    ]
    assert recommendation["confidence"] == "low"
    assert recommendation["time_horizon"] == "未来十二个月"


def test_explicit_portfolio_policy_uses_only_user_supplied_ranges() -> None:
    recommendation = build_recommendation(
        subject_type="portfolio",
        subject_id="default",
        snapshot=_snapshot(),
        report_cutoff_at="2026-07-15T15:00:00+08:00",
        review_mode="advice",
        risk_policy={
            "time_horizon": "未来六个月",
            "risk_budget": "组合最大可承受损失 8%",
            "target_cash_range_pct": ["2", "4"],
            "single_instrument_cap_range_pct": ["25", "28"],
        },
    )

    assert recommendation["mode"] == "advice"
    assert recommendation["decision_basis"] == "user_policy_trigger"
    assert recommendation["user_risk_budget"] == "组合最大可承受损失 8%"
    assert recommendation["action"] == "reduce"
    assert recommendation["target_position"]["target_cash_range_pct"] == [
        "2",
        "4",
    ]
    assert recommendation["target_position"][
        "single_instrument_cap_range_pct"
    ] == ["25", "28"]


def test_advice_mode_without_horizon_and_risk_budget_stays_observation_only() -> None:
    recommendation = build_recommendation(
        subject_type="instrument",
        subject_id="000001.SZ",
        snapshot=_snapshot(),
        report_cutoff_at="2026-07-15T15:00:00+08:00",
        review_mode="advice",
        risk_policy={"target_position_range_pct": ["7", "9"]},
    )

    _assert_observation_only(recommendation)
    assert "MISSING_EXPLICIT_USER_TIME_HORIZON" in (
        recommendation["important_missing_inputs"]
    )
    assert "MISSING_EXPLICIT_USER_RISK_BUDGET" in (
        recommendation["important_missing_inputs"]
    )
