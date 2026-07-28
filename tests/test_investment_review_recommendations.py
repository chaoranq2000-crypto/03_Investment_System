from __future__ import annotations

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


def test_instrument_recommendation_is_direct_sized_and_not_an_order() -> None:
    recommendation = build_recommendation(
        subject_type="instrument",
        subject_id="000001.SZ",
        snapshot=_snapshot(),
        report_cutoff_at="2026-07-15T15:00:00+08:00",
    )

    assert recommendation["action"] == "reduce"
    assert recommendation["target_position"]["target_position_range_pct"] == [
        "8",
        "12",
    ]
    assert recommendation["confidence"] == "low"
    assert recommendation["major_downside_risks"]
    assert recommendation["invalidation_conditions"]
    assert recommendation["report_cutoff_at"] == (
        "2026-07-15T15:00:00+08:00"
    )
    assert recommendation["data_timestamp"] <= recommendation["report_cutoff_at"]
    assert recommendation["orders_executed"] is False
    assert recommendation["guaranteed_return"] is False
    assert "MISSING_FUNDAMENTAL_AND_VALUATION_CONTEXT" in (
        recommendation["important_missing_inputs"]
    )


def test_portfolio_recommendation_targets_cash_and_single_name_concentration() -> None:
    recommendation = build_recommendation(
        subject_type="portfolio",
        subject_id="default",
        snapshot=_snapshot(),
        report_cutoff_at="2026-07-15T15:00:00+08:00",
    )

    assert recommendation["action"] == "reduce"
    assert recommendation["target_position"]["target_cash_range_pct"] == [
        "5",
        "10",
    ]
    assert recommendation["target_position"][
        "single_instrument_cap_range_pct"
    ] == ["15", "20"]
    assert "15%–20%" in recommendation["target_position"]["target_position_note"]
    assert "5%–10%" in recommendation["target_position"]["target_position_note"]
    assert any(
        item["type"] == "opinion" for item in recommendation["rationale"]
    )
    assert recommendation["orders_executed"] is False


def test_missing_position_does_not_invent_a_precise_buy_size() -> None:
    snapshot = _snapshot()
    recommendation = build_recommendation(
        subject_type="instrument",
        subject_id="999999.SZ",
        snapshot=snapshot,
        report_cutoff_at="2026-07-15T15:00:00+08:00",
    )

    assert recommendation["action"] == "hold"
    assert recommendation["target_position"]["target_position_range_pct"] == [
        "0",
        "0",
    ]
    assert recommendation["confidence"] == "low"
