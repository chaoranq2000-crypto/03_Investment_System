from copy import deepcopy

import yaml

from src.research.r5_bundle9r_contracts import validate_model_pack


def contract():
    return yaml.safe_load(open("config/r5_bundle9r_model_contract.yaml", encoding="utf-8"))


def number(value, claim_type="estimate"):
    return {"value": value, "claim_type": claim_type, "assumption_id": "a"}


def year(revenue):
    segments = {
        "room_cooling": {"disclosure_basis": "issuer_reported_broad_line", "revenue": number(revenue * 0.6), "gross_margin": number(25), "gross_profit": number(revenue * 0.15)},
        "cabinet_cooling": {"disclosure_basis": "issuer_reported_broad_line", "revenue": number(revenue * 0.3), "gross_margin": number(20), "gross_profit": number(revenue * 0.06)},
        "other_businesses": {"disclosure_basis": "issuer_reported_residual", "revenue": number(revenue * 0.1), "gross_margin": number(10), "gross_profit": number(revenue * 0.01)},
    }
    bridge = {
        "revenue": number(revenue), "gross_profit": number(revenue * 0.22), "tax_surcharge": number(revenue * 0.005),
        "selling_expense": number(revenue * 0.04), "administrative_expense": number(revenue * 0.04), "rd_expense": number(revenue * 0.07),
        "financial_expense": number(revenue * 0.005),
        "investment_income": number(0), "fair_value_change": number(0), "other_income": number(0),
        "asset_impairment_loss": number(0), "credit_impairment_loss": number(0), "asset_disposal_gain": number(0),
        "operating_profit": number(revenue * 0.06), "non_operating_net": number(0),
        "pretax_profit": number(revenue * 0.06), "income_tax": number(revenue * 0.006), "minority_interest": number(0),
        "nonrecurring_items": number(0), "attributable_net_profit": number(revenue * 0.054),
        "shares_outstanding": number(100), "eps": number(revenue * 0.00054),
        "operating_cash_flow": number(revenue * 0.05), "capex": number(revenue * 0.03), "free_cash_flow": number(revenue * 0.02),
    }
    return {"segments": segments, "bridge": bridge}


def valid_model():
    scenarios = {}
    for name, factor in (("bear", 0.8), ("base", 1.0), ("bull", 1.2)):
        scenarios[name] = {"periods": {period: year(1000 * factor * (1 + idx * 0.1)) for idx, period in enumerate(("2026E", "2027E", "2028E"))}}
    return {
        "artifact_type": "R5_bundle9r_model_pack",
        "input_evidence_generation_id": "g1",
        "periods": ["2026E", "2027E", "2028E"],
        "scenarios": scenarios,
        "consensus_comparison": {"claim_type": "analyst_view", "minimum_institution_count": 3, "rows": []},
        "valuation": {
            "market_snapshot": {"close_price": number(10, "metric"), "shares_outstanding": number(100, "metric"), "market_cap": number(1000, "metric")},
            "peer_set": {"quality": "LOW_CONFIDENCE_PEER_SET", "ranking_allowed": False},
            "methods": {"reverse_valuation": {"eligible": True}, "scenario_valuation": {"eligible": True}},
            "scenario_equity_values": {"bear": number(800, "inference"), "base": number(1000, "inference"), "bull": number(1200, "inference")},
        },
    }


def test_valid_model_passes():
    assert validate_model_pack(valid_model(), contract(), expected_generation_id="g1") == []


def test_unexplained_plug_is_critical():
    model = valid_model()
    model["scenarios"]["base"]["periods"]["2026E"]["bridge"]["other_operating_drag"] = number(1)
    assert "prohibited_plug_field" in [x.code for x in validate_model_pack(model, contract(), expected_generation_id="g1")]


def test_segment_double_count_or_mismatch_is_blocked():
    model = valid_model()
    model["scenarios"]["base"]["periods"]["2026E"]["segments"]["room_cooling"]["revenue"] = number(999)
    assert "segment_revenue_does_not_reconcile" in [x.code for x in validate_model_pack(model, contract(), expected_generation_id="g1")]


def test_missing_required_segment_is_blocked():
    model = valid_model()
    del model["scenarios"]["base"]["periods"]["2026E"]["segments"]["room_cooling"]
    assert "required_segments_missing" in [x.code for x in validate_model_pack(model, contract(), expected_generation_id="g1")]


def test_liquid_cooling_fact_and_double_count_are_blocked():
    model = valid_model()
    model["scenarios"]["base"]["periods"]["2026E"]["segments"]["liquid_cooling"] = {
        "disclosure_basis": "issuer_reported_broad_line",
        "revenue": number(10, "fact"),
        "gross_margin": number(20),
        "gross_profit": number(2),
    }
    codes = [x.code for x in validate_model_pack(model, contract(), expected_generation_id="g1")]
    assert "liquid_cooling_boundary_violation" in codes
    assert "liquid_cooling_double_count_risk" in codes


def test_operating_profit_arithmetic_mismatch_is_blocked():
    model = valid_model()
    model["scenarios"]["base"]["periods"]["2026E"]["bridge"]["operating_profit"] = number(1)
    assert "operating_profit_bridge_error" in [x.code for x in validate_model_pack(model, contract(), expected_generation_id="g1")]


def test_scenario_monotonicity_failure_is_blocked():
    model = valid_model()
    model["scenarios"]["bear"]["periods"]["2026E"]["bridge"]["attributable_net_profit"] = number(999)
    assert "scenario_monotonicity_failure" in [x.code for x in validate_model_pack(model, contract(), expected_generation_id="g1")]


def test_market_cap_denominator_mismatch_is_blocked():
    model = valid_model()
    model["valuation"]["market_snapshot"]["market_cap"] = number(2000, "metric")
    assert "market_cap_share_price_mismatch" in [x.code for x in validate_model_pack(model, contract(), expected_generation_id="g1")]


def test_required_valuation_method_missing_is_blocked():
    model = valid_model()
    del model["valuation"]["methods"]["reverse_valuation"]
    assert "required_valuation_method_missing" in [x.code for x in validate_model_pack(model, contract(), expected_generation_id="g1")]


def test_consensus_fact_label_is_blocked():
    model = valid_model()
    model["consensus_comparison"]["claim_type"] = "fact"
    assert "consensus_claim_boundary_violation" in [x.code for x in validate_model_pack(model, contract(), expected_generation_id="g1")]


def test_consensus_institution_count_below_contract_is_blocked():
    model = valid_model()
    model["consensus_comparison"]["minimum_institution_count"] = 2
    assert "consensus_institution_count_too_low" in [x.code for x in validate_model_pack(model, contract(), expected_generation_id="g1")]


def test_low_confidence_peer_ranking_is_blocked():
    model = valid_model()
    model["valuation"]["peer_set"]["ranking_allowed"] = True
    assert "low_confidence_peer_ranking_enabled" in [x.code for x in validate_model_pack(model, contract(), expected_generation_id="g1")]


def test_direct_advice_language_is_blocked():
    model = valid_model()
    model["notes"] = "建议买入"
    assert "prohibited_action_language" in [x.code for x in validate_model_pack(model, contract(), expected_generation_id="g1")]
