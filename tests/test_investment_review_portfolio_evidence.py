from __future__ import annotations

import json
from decimal import Decimal

import pytest

from src.investment_review.models import ModelValidationError
from src.investment_review.portfolio_context import (
    PORTFOLIO_METRIC_METHOD_REGISTRY,
    PORTFOLIO_METRIC_REGISTRY_VERSION,
    PortfolioContext,
    PortfolioSnapshot,
    calculate_portfolio_evidence_metrics,
    deterministic_portfolio_evidence_json,
    portfolio_metric_method_ref,
)


SOURCE_ID = "src_reviewed_portfolio_snapshot"


def snapshot(
    *,
    cash: str = "0",
    nav: str = "1000",
    positions: list[dict] | None = None,
    observed_at: str = "2026-07-15 09:59:00",
    known_at: str = "2026-07-15 09:59:30",
    timezone: str = "Asia/Shanghai",
) -> PortfolioSnapshot:
    return PortfolioSnapshot.from_dict(
        {
            "source_path": "tests/fixtures/reviewed-portfolio.json#snapshot=1",
            "observed_at": observed_at,
            "known_at": known_at,
            "cash": cash,
            "total_assets": nav,
            "net_asset_value": nav,
            "financing": "0",
            "base_currency": "CNY",
            "positions": positions or [],
        },
        default_source_id=SOURCE_ID,
        timezone=timezone,
    )


def metric_map(value: PortfolioSnapshot, **kwargs: object) -> dict[str, dict]:
    return {
        item.metric_name: item.to_dict()
        for item in calculate_portfolio_evidence_metrics(value, **kwargs)
    }


def warning_codes(metric: dict) -> set[str]:
    return {item["code"] for item in metric["warnings"]}


def test_standard_long_portfolio_has_nav_cash_and_concentration_evidence() -> None:
    metrics = metric_map(
        snapshot(
            cash="250",
            positions=[
                {"symbol": "BANK", "quantity": "50", "price": "10", "industry": "银行"},
                {"symbol": "TECH", "quantity": "25", "price": "10", "industry": "科技"},
            ],
        )
    )

    assert metrics["nav"]["value"] == "1000"
    assert metrics["cash_weight"]["value"] == "0.25"
    assert metrics["gross_market_value"]["value"] == "750"
    assert metrics["gross_exposure"]["value"] == "0.75"
    assert Decimal(metrics["max_position_weight"]["value"]) == Decimal("2") / Decimal("3")
    assert metrics["top3_concentration"]["value"] == "1"


def test_all_cash_portfolio_has_complete_zero_position_coverage() -> None:
    metrics = metric_map(snapshot(cash="1000"))

    assert metrics["position_count"]["value"] == "0"
    assert metrics["valued_position_count"]["value"] == "0"
    assert metrics["valuation_coverage"]["value"] == "1"
    assert metrics["gross_market_value"]["value"] == "0"
    assert metrics["max_position_weight"]["value"] == "0"
    assert metrics["missing_valuation_amount"]["value"] == "0"


@pytest.mark.parametrize("nav", ["0", "-100"])
def test_non_positive_nav_keeps_values_but_marks_weights_unavailable(nav: str) -> None:
    metrics = metric_map(
        snapshot(
            nav=nav,
            positions=[{"symbol": "A", "quantity": "10", "price": "10", "industry": "I1"}],
        )
    )

    assert metrics["gross_market_value"]["value"] == "100"
    for name in ("cash_weight", "gross_exposure", "top3_concentration", "hhi"):
        assert metrics[name]["status"] == "unavailable"
        assert metrics[name]["value"] is None
        assert "NON_POSITIVE_NAV" in warning_codes(metrics[name])


def test_long_and_short_exposures_are_distinct_and_signed_net_is_preserved() -> None:
    metrics = metric_map(
        snapshot(
            cash="600",
            positions=[
                {"symbol": "LONG", "quantity": "6", "price": "100", "industry": "I1"},
                {"symbol": "SHORT", "quantity": "-2", "price": "100", "industry": "I2"},
            ],
        )
    )

    assert metrics["long_exposure"]["value"] == "0.6"
    assert metrics["short_exposure"]["value"] == "0.2"
    assert metrics["gross_exposure"]["value"] == "0.8"
    assert metrics["net_exposure"]["value"] == "0.4"


def test_missing_price_is_excluded_without_becoming_zero() -> None:
    metrics = metric_map(
        snapshot(
            positions=[
                {"symbol": "MISSING", "quantity": "10", "industry": "I1"},
                {"symbol": "VALID", "quantity": "10", "price": "10", "industry": "I1"},
            ]
        )
    )

    assert metrics["gross_market_value"]["value"] == "100"
    assert metrics["valuation_coverage"]["value"] == "0.5"
    assert metrics["missing_valuation_amount"]["status"] == "unavailable"
    assert metrics["missing_valuation_amount"]["value"] is None
    assert {"MISSING_PRICE", "PARTIAL_VALUATION_COVERAGE"}.issubset(
        warning_codes(metrics["gross_market_value"])
    )


def test_unpriced_position_count_and_ratio_come_from_the_missing_valuation_set() -> None:
    metrics = metric_map(
        snapshot(
            positions=[
                {"symbol": "UNPRICED", "quantity": "10", "industry": "I1"},
                {"symbol": "VALUED", "quantity": "10", "price": "10", "industry": "I1"},
            ]
        )
    )

    assert metrics["unpriced_position_count"]["value"] == "1"
    assert metrics["unpriced_position_count"]["status"] == "derived"
    assert metrics["unpriced_position_ratio"]["value"] == "0.5"
    assert metrics["unpriced_position_ratio"]["status"] == "derived"
    assert metrics["unpriced_position_count"]["source_refs"][0]["position_keys"] == [
        "UNPRICED|"
    ]


def test_stale_metrics_distinguish_missing_metadata_from_reviewed_zero() -> None:
    value = snapshot(
        positions=[
            {"symbol": "A", "quantity": "10", "price": "10"},
            {"symbol": "B", "quantity": "10", "price": "10"},
        ]
    )

    unknown = metric_map(value)
    assert unknown["stale_position_count"]["value"] is None
    assert unknown["stale_position_count"]["status"] == "unavailable"
    assert unknown["stale_position_ratio"]["value"] is None
    assert "STALE_POSITION_METADATA_UNAVAILABLE" in warning_codes(
        unknown["stale_position_count"]
    )

    reviewed_zero = metric_map(value, stale_position_keys=[])
    assert reviewed_zero["stale_position_count"]["value"] == "0"
    assert reviewed_zero["stale_position_ratio"]["value"] == "0"

    reviewed_stale = metric_map(value, stale_position_keys=["B|"])
    assert reviewed_stale["stale_position_count"]["value"] == "1"
    assert reviewed_stale["stale_position_ratio"]["value"] == "0.5"
    assert "STALE_POSITION" in warning_codes(reviewed_stale["stale_position_count"])


def test_target_metrics_distinguish_absent_valued_and_unpriced_positions() -> None:
    value = snapshot(
        positions=[
            {"symbol": "TARGET", "quantity": "2", "price": "25", "industry": "I1"},
            {"symbol": "OTHER", "quantity": "10", "price": "10", "industry": "I2"},
        ]
    )

    valued = metric_map(value, target_symbol="target")
    assert valued["target_position_value"]["value"] == "50"
    assert valued["target_position_weight"]["value"] == "0.05"
    assert valued["target_position_weight"]["unit"] == "ratio_to_nav"

    absent = metric_map(value, target_symbol="ABSENT")
    assert absent["target_position_value"]["value"] == "0"
    assert absent["target_position_weight"]["value"] == "0"

    unpriced = metric_map(
        snapshot(positions=[{"symbol": "TARGET", "quantity": "2", "industry": "I1"}]),
        target_symbol="TARGET",
    )
    assert unpriced["target_position_value"]["value"] is None
    assert unpriced["target_position_value"]["status"] == "unavailable"
    assert unpriced["target_position_weight"]["value"] is None
    assert "TARGET_POSITION_UNPRICED" in warning_codes(
        unpriced["target_position_value"]
    )


def test_missing_fx_is_visible_and_not_counted_as_a_base_currency_valuation() -> None:
    metrics = metric_map(
        snapshot(
            positions=[
                {
                    "symbol": "0700.HK",
                    "market": "HK",
                    "quantity": "1",
                    "price": "500",
                    "currency": "HKD",
                    "industry": "互联网",
                }
            ]
        )
    )

    assert metrics["valued_position_count"]["value"] == "0"
    assert metrics["valuation_coverage"]["value"] == "0"
    assert "MISSING_FX" in warning_codes(metrics["missing_valuation_amount"])


def test_missing_industry_has_an_explicit_unknown_weight_and_warning() -> None:
    metrics = metric_map(
        snapshot(positions=[{"symbol": "A", "quantity": "10", "price": "10"}])
    )

    assert metrics["industry_weight::UNKNOWN"]["value"] == "1"
    assert metrics["unclassified_industry_weight"]["value"] == "1"
    assert "UNCLASSIFIED_INDUSTRY" in warning_codes(
        metrics["unclassified_industry_weight"]
    )


def test_duplicate_position_keys_are_explicitly_rejected() -> None:
    with pytest.raises(ModelValidationError, match="Duplicate position key"):
        snapshot(
            positions=[
                {"symbol": "A", "quantity": "1", "price": "1"},
                {"symbol": "A", "quantity": "2", "price": "1"},
            ]
        )


def test_top_n_and_hhi_use_stable_gross_value_ordering() -> None:
    rows = [
        {"symbol": f"P{value}", "quantity": "1", "price": str(value), "industry": "I"}
        for value in (1, 2, 3, 4, 5, 6)
    ]
    metrics = metric_map(snapshot(positions=rows))

    assert Decimal(metrics["top3_concentration"]["value"]) == Decimal("15") / Decimal("21")
    assert Decimal(metrics["top5_concentration"]["value"]) == Decimal("20") / Decimal("21")
    assert Decimal(metrics["hhi"]["value"]) == sum(
        (Decimal(value) / Decimal("21")) ** 2 for value in (1, 2, 3, 4, 5, 6)
    )


def test_naive_times_are_explicitly_normalized_with_the_supplied_timezone() -> None:
    metrics = calculate_portfolio_evidence_metrics(snapshot())

    assert {item.as_of for item in metrics} == {"2026-07-15T01:59:00Z"}
    assert {item.available_at for item in metrics} == {"2026-07-15T01:59:30Z"}


def test_input_order_does_not_change_the_deterministic_json() -> None:
    rows = [
        {"symbol": "B", "quantity": "10", "price": "10", "industry": "I2"},
        {"symbol": "A", "quantity": "10", "price": "10", "industry": "I1"},
    ]

    assert deterministic_portfolio_evidence_json(snapshot(positions=rows)) == (
        deterministic_portfolio_evidence_json(snapshot(positions=list(reversed(rows))))
    )


def test_target_and_stale_inputs_remain_deterministic_when_orders_change() -> None:
    rows = [
        {"symbol": "B", "quantity": "10", "price": "10", "industry": "I2"},
        {"symbol": "A", "quantity": "10", "price": "10", "industry": "I1"},
    ]

    assert deterministic_portfolio_evidence_json(
        snapshot(positions=rows),
        target_symbol="A",
        stale_position_keys=["B|", "A|"],
    ) == deterministic_portfolio_evidence_json(
        snapshot(positions=list(reversed(rows))),
        target_symbol="a",
        stale_position_keys=["A|", "B|"],
    )


def test_public_metric_registry_exposes_versioned_methods_and_keeps_formula_text() -> None:
    method = portfolio_metric_method_ref("cash_weight")
    assert method == {
        "method_id": "cash_weight",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
    }
    assert portfolio_metric_method_ref("industry_weight::银行")["method_id"] == (
        "industry_weight"
    )
    assert PORTFOLIO_METRIC_METHOD_REGISTRY["target_position_weight"][
        "calculation_method"
    ] == "target_position_value / nav"

    metric = metric_map(snapshot(cash="1000"))["cash_weight"]
    assert metric["method"] == method
    assert metric["calculation_method"] == "cash_value / nav"

    with pytest.raises(ModelValidationError, match="Missing metric method registration"):
        portfolio_metric_method_ref("not_registered")


def test_large_amounts_and_decimal_precision_are_not_converted_to_float() -> None:
    amount = "999999999999999999999999.123456789"
    metrics = metric_map(
        snapshot(
            nav="1000000000000000000000000.123456789",
            positions=[
                {
                    "symbol": "BIG",
                    "quantity": "1",
                    "market_value": amount,
                    "industry": "I1",
                }
            ],
        )
    )

    assert metrics["gross_market_value"]["value"] == amount
    assert "e+" not in metrics["gross_market_value"]["value"].lower()


def test_every_metric_keeps_status_time_and_source_references() -> None:
    metrics = [item.to_dict() for item in calculate_portfolio_evidence_metrics(snapshot())]

    assert metrics
    for metric in metrics:
        assert metric["status"] in {"observed", "derived", "unavailable"}
        assert metric["as_of"]
        assert metric["available_at"]
        assert metric["calculation_method"]
        assert len(metric["source_refs"]) == 1
        source = metric["source_refs"][0]
        assert source["source_id"] == SOURCE_ID
        assert source["source_path"].endswith("#snapshot=1")
        assert len(source["evidence_id"]) > 24


def test_portfolio_context_embeds_metric_evidence_without_advice_or_scoring() -> None:
    before = snapshot(cash="900", positions=[{"symbol": "A", "quantity": "10", "price": "10"}])
    payload = PortfolioContext(
        reference_type="trade_episode",
        reference_id="episode-1",
        reference_symbol="A",
        reference_occurred_at="2026-07-15T02:00:00Z",
        before_snapshot=before,
    ).to_dict()

    evidence = payload["portfolio_facts_available_at_reference"]["metric_evidence"]
    assert {item["metric_name"] for item in evidence}.issuperset(
        {"nav", "cash_weight", "top3_concentration", "valuation_coverage"}
    )
    serialized = json.dumps(evidence, ensure_ascii=False).lower()
    assert "buy" not in serialized
    assert "sell" not in serialized
    assert "score" not in serialized
    assert "psychology" not in serialized
