from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml

from src.research.r5_bundle12r_operating_evidence import (
    evaluate_bundle12r,
    load_yaml,
    observation_qualified,
    validate_contract,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = load_yaml(ROOT / "config" / "r5_bundle12r_operating_evidence_contract.yaml")
READY = load_yaml(ROOT / "tests" / "fixtures" / "r5_bundle12r" / "ready_manufacturing.yaml")
GAP = load_yaml(ROOT / "tests" / "fixtures" / "r5_bundle12r" / "invic_gap_template.yaml")


def issue_codes(result: dict[str, object]) -> set[str]:
    return {str(row["code"]) for row in result["issues"]}


def test_contract_has_eight_archetypes_and_no_critical_issues() -> None:
    assert len(CONTRACT["archetypes"]) == 8
    assert validate_contract(CONTRACT) == []


def test_ready_fixture_passes_operating_gate_and_enables_all_valuation_methods() -> None:
    result = evaluate_bundle12r(READY, CONTRACT)
    assert result["decision"] == "operating_evidence_ready"
    assert result["blocker_count"] == 0
    assert result["coverage"]["revenue_coverage"]["coverage_ratio"] == 1.0
    assert result["coverage"]["gross_profit_coverage"]["coverage_ratio"] == 1.0
    assert result["coverage"]["essential_driver_coverage_ratio"] == 1.0
    eligibility = result["valuation_eligibility"]
    assert eligibility["peer_method"]["eligible"] is True
    assert eligibility["dcf_method"]["eligible"] is True
    assert eligibility["sotp_method"]["eligible"] is True


def test_gap_template_fails_without_inventing_operating_depth() -> None:
    result = evaluate_bundle12r(GAP, CONTRACT)
    codes = issue_codes(result)
    assert result["decision"] == "needs_backflow"
    assert "ESSENTIAL_DRIVER_NOT_QUALIFIED" in codes
    assert "OPERATING_OVERLAP_UNRESOLVED" in codes
    assert "REVENUE_COVERAGE_DENOMINATOR_MISSING" in codes
    assert result["sample_quality_allowed"] is False
    assert result["p2_allowed"] is False


def test_unknown_overlap_is_non_compensating_blocker() -> None:
    payload = deepcopy(READY)
    payload["overlaps"][0]["relation"] = "unknown"
    result = evaluate_bundle12r(payload, CONTRACT)
    assert result["decision"] == "needs_backflow"
    assert "OPERATING_OVERLAP_UNRESOLVED" in issue_codes(result)
    assert result["coverage"]["operating_gate_passed"] is False
    assert result["valuation_eligibility"]["peer_method"]["eligible"] is True
    assert result["valuation_eligibility"]["dcf_method"]["eligible"] is False
    assert result["valuation_eligibility"]["sotp_method"]["eligible"] is False


def test_overcoverage_detects_double_counting() -> None:
    payload = deepcopy(READY)
    payload["segments"][1]["revenue"]["value"] = 500
    payload["overlaps"][0]["relation"] = "disjoint"
    result = evaluate_bundle12r(payload, CONTRACT)
    assert "FINANCIAL_OVER_COVERAGE_DETECTED" in issue_codes(result)
    assert result["coverage"]["operating_gate_passed"] is False
    assert result["valuation_eligibility"]["dcf_method"]["eligible"] is False
    assert result["valuation_eligibility"]["sotp_method"]["eligible"] is False


def test_segment_financial_period_must_match_total_period() -> None:
    payload = deepcopy(READY)
    payload["segments"][0]["revenue"]["period"] = "2024A"
    result = evaluate_bundle12r(payload, CONTRACT)
    assert result["decision"] == "needs_backflow"
    assert "FINANCIAL_PERIOD_MISMATCH" in issue_codes(result)
    assert result["coverage"]["operating_gate_passed"] is False
    assert result["valuation_eligibility"]["dcf_method"]["eligible"] is False


def test_segment_financial_unit_must_match_total_unit() -> None:
    payload = deepcopy(READY)
    payload["segments"][0]["revenue"]["unit"] = "USD_mn"
    result = evaluate_bundle12r(payload, CONTRACT)
    assert result["decision"] == "needs_backflow"
    assert "FINANCIAL_UNIT_MISMATCH" in issue_codes(result)
    assert result["coverage"]["operating_gate_passed"] is False
    assert result["valuation_eligibility"]["sotp_method"]["eligible"] is False


def test_contains_relation_requires_numeric_adjustment() -> None:
    payload = deepcopy(READY)
    payload["overlaps"][0] = {
        "left_segment_id": "high_end_material",
        "right_segment_id": "battery_material",
        "relation": "contains",
        "allocation_method": "direct_deduction",
    }
    result = evaluate_bundle12r(payload, CONTRACT)
    assert "FINANCIAL_OVERLAP_ADJUSTMENT_MISSING" in issue_codes(result)


def test_every_business_pair_requires_exactly_one_overlap_declaration() -> None:
    missing = deepcopy(READY)
    missing["overlaps"] = missing["overlaps"][:-1]
    missing_result = evaluate_bundle12r(missing, CONTRACT)
    assert "OPERATING_OVERLAP_PAIR_MISSING" in issue_codes(missing_result)
    assert missing_result["valuation_eligibility"]["dcf_method"]["eligible"] is False
    assert missing_result["valuation_eligibility"]["sotp_method"]["eligible"] is False

    duplicate = deepcopy(READY)
    duplicate["overlaps"].append(deepcopy(duplicate["overlaps"][0]))
    duplicate_result = evaluate_bundle12r(duplicate, CONTRACT)
    assert "OPERATING_OVERLAP_PAIR_DUPLICATE" in issue_codes(duplicate_result)
    assert duplicate_result["coverage"]["operating_gate_passed"] is False


def test_input_high_issue_also_blocks_dcf_and_sotp() -> None:
    payload = deepcopy(READY)
    payload["segments"].append(deepcopy(payload["segments"][0]))
    result = evaluate_bundle12r(payload, CONTRACT)
    assert "SEGMENT_ID_DUPLICATE" in issue_codes(result)
    assert result["coverage"]["operating_gate_passed"] is False
    assert result["valuation_eligibility"]["peer_method"]["eligible"] is False
    assert result["valuation_eligibility"]["dcf_method"]["eligible"] is False
    assert result["valuation_eligibility"]["sotp_method"]["eligible"] is False


def test_invalid_input_identity_blocks_all_valuation_methods() -> None:
    payload = deepcopy(READY)
    payload["artifact_type"] = "invalid"
    payload["issuer"] = {"stock_code": "", "company_name": ""}
    result = evaluate_bundle12r(payload, CONTRACT)
    assert "INPUT_ARTIFACT_TYPE_INVALID" in issue_codes(result)
    assert "INPUT_ISSUER_IDENTITY_MISSING" in issue_codes(result)
    assert result["coverage"]["input_gate_passed"] is False
    eligibility = result["valuation_eligibility"]
    assert eligibility["peer_method"]["eligible"] is False
    assert eligibility["dcf_method"]["eligible"] is False
    assert eligibility["sotp_method"]["eligible"] is False


def test_bounded_estimate_needs_ordered_bounds() -> None:
    observation = {
        "status": "bounded_estimate",
        "lower_bound": 2,
        "upper_bound": 1,
        "unit": "ratio",
        "period": "2025A",
        "confidence": 0.8,
        "source_tier": "B",
        "evidence_ids": ["E1"],
    }
    qualified, reason = observation_qualified(observation, CONTRACT)
    assert qualified is False
    assert "ordered" in reason


def test_observations_reject_blank_ids_and_non_finite_numbers() -> None:
    blank_evidence = deepcopy(READY["segments"][0]["revenue"])
    blank_evidence["evidence_ids"] = ["  "]
    qualified, reason = observation_qualified(blank_evidence, CONTRACT)
    assert qualified is False
    assert "evidence_ids" in reason

    for value in ("nan", "inf", "-inf"):
        non_finite = deepcopy(READY["segments"][0]["revenue"])
        non_finite["value"] = value
        qualified, reason = observation_qualified(non_finite, CONTRACT)
        assert qualified is False
        assert "numeric value" in reason

    non_finite_confidence = deepcopy(READY["segments"][0]["revenue"])
    non_finite_confidence["confidence"] = "nan"
    qualified, reason = observation_qualified(non_finite_confidence, CONTRACT)
    assert qualified is False
    assert "confidence" in reason


def test_peer_method_requires_three_definition_compatible_peers() -> None:
    payload = deepcopy(READY)
    payload["valuation_inputs"]["peers"][2]["metric_definition_match"] = False
    result = evaluate_bundle12r(payload, CONTRACT)
    assert result["valuation_eligibility"]["peer_method"]["eligible"] is False
    assert "PEER_METHOD_NOT_ELIGIBLE" in issue_codes(result)


def test_peer_method_requires_three_unique_non_empty_peer_ids() -> None:
    duplicate = deepcopy(READY)
    for peer in duplicate["valuation_inputs"]["peers"]:
        peer["peer_id"] = "P1"
    duplicate_result = evaluate_bundle12r(duplicate, CONTRACT)
    assert duplicate_result["valuation_eligibility"]["peer_method"]["eligible"] is False
    assert duplicate_result["valuation_eligibility"]["peer_method"]["qualified_peer_count"] == 1

    blank = deepcopy(READY)
    for peer in blank["valuation_inputs"]["peers"]:
        peer["peer_id"] = ""
    blank_result = evaluate_bundle12r(blank, CONTRACT)
    assert blank_result["valuation_eligibility"]["peer_method"]["eligible"] is False
    assert blank_result["valuation_eligibility"]["peer_method"]["qualified_peer_count"] == 0


def test_peer_match_flags_require_literal_booleans() -> None:
    payload = deepcopy(READY)
    for peer in payload["valuation_inputs"]["peers"]:
        peer["business_definition_match"] = "false"
        peer["period_match"] = 1
        peer["metric_definition_match"] = "true"
    result = evaluate_bundle12r(payload, CONTRACT)
    assert result["valuation_eligibility"]["peer_method"]["eligible"] is False
    assert result["valuation_eligibility"]["peer_method"]["qualified_peer_count"] == 0


def test_dcf_requires_three_year_cashflow_and_capex_history() -> None:
    payload = deepcopy(READY)
    payload["financial_totals"]["capex_history"] = payload["financial_totals"]["capex_history"][:2]
    result = evaluate_bundle12r(payload, CONTRACT)
    assert result["valuation_eligibility"]["dcf_method"]["eligible"] is False
    assert "DCF_METHOD_NOT_ELIGIBLE" in issue_codes(result)


def test_dcf_requires_aligned_periods_and_compatible_cashflow_units() -> None:
    disjoint = deepcopy(READY)
    for index, row in enumerate(disjoint["financial_totals"]["capex_history"]):
        row["period"] = f"202{index}A"
    disjoint_result = evaluate_bundle12r(disjoint, CONTRACT)
    assert disjoint_result["valuation_eligibility"]["dcf_method"]["eligible"] is False
    assert disjoint_result["valuation_eligibility"]["dcf_method"]["paired_cashflow_period_count"] == 0

    capex_unit = deepcopy(READY)
    for row in capex_unit["financial_totals"]["capex_history"]:
        row["unit"] = "USD_mn"
    capex_unit_result = evaluate_bundle12r(capex_unit, CONTRACT)
    assert capex_unit_result["valuation_eligibility"]["dcf_method"]["eligible"] is False
    assert capex_unit_result["valuation_eligibility"]["dcf_method"]["paired_cashflow_period_count"] == 0

    working_capital_unit = deepcopy(READY)
    working_capital_unit["financial_totals"]["working_capital_bridge"]["unit"] = "USD_mn"
    working_capital_result = evaluate_bundle12r(working_capital_unit, CONTRACT)
    assert working_capital_result["valuation_eligibility"]["dcf_method"]["eligible"] is False
    assert working_capital_result["valuation_eligibility"]["dcf_method"]["working_capital_bridge_qualified"] is False


def test_dcf_ratio_inputs_require_valid_units_ranges_and_discount_spread() -> None:
    bad_unit = deepcopy(READY)
    bad_unit["valuation_inputs"]["dcf"]["wacc"]["unit"] = "CNY_mn"
    bad_unit_result = evaluate_bundle12r(bad_unit, CONTRACT)
    assert bad_unit_result["valuation_eligibility"]["dcf_method"]["eligible"] is False
    assert bad_unit_result["valuation_eligibility"]["dcf_method"]["wacc_qualified"] is False

    bad_spread = deepcopy(READY)
    bad_spread["valuation_inputs"]["dcf"]["terminal_growth"]["lower_bound"] = 0.20
    bad_spread["valuation_inputs"]["dcf"]["terminal_growth"]["upper_bound"] = 0.25
    bad_spread_result = evaluate_bundle12r(bad_spread, CONTRACT)
    assert bad_spread_result["valuation_eligibility"]["dcf_method"]["eligible"] is False
    assert bad_spread_result["valuation_eligibility"]["dcf_method"]["discount_spread_qualified"] is False

    bad_tax = deepcopy(READY)
    bad_tax["valuation_inputs"]["dcf"]["tax_rate"]["value"] = 2.0
    bad_tax_result = evaluate_bundle12r(bad_tax, CONTRACT)
    assert bad_tax_result["valuation_eligibility"]["dcf_method"]["eligible"] is False
    assert bad_tax_result["valuation_eligibility"]["dcf_method"]["tax_rate_qualified"] is False


def test_sotp_requires_independent_financials_for_every_material_segment() -> None:
    payload = deepcopy(READY)
    payload["segments"][0]["independent_exposure"]["quantitative_metric_ids"] = []
    result = evaluate_bundle12r(payload, CONTRACT)
    assert result["valuation_eligibility"]["sotp_method"]["eligible"] is False
    assert result["valuation_eligibility"]["dcf_method"]["eligible"] is False
    assert result["valuation_eligibility"]["dcf_method"]["operating_gate_qualified"] is False
    assert "INDEPENDENT_EXPOSURE_NOT_QUALIFIED" in issue_codes(result)


def test_sotp_overlap_resolved_requires_literal_true() -> None:
    payload = deepcopy(READY)
    for component in payload["valuation_inputs"]["sotp"]["components"]:
        component["overlap_resolved"] = "false"
    result = evaluate_bundle12r(payload, CONTRACT)
    assert result["valuation_eligibility"]["sotp_method"]["eligible"] is False
    assert set(result["valuation_eligibility"]["sotp_method"]["component_failures"]) == {
        "high_end_material",
        "battery_material",
    }


def test_independent_exposure_and_peer_evidence_reject_blank_ids() -> None:
    exposure = deepcopy(READY)
    exposure["segments"][0]["independent_exposure"]["quantitative_metric_ids"] = [" "]
    exposure_result = evaluate_bundle12r(exposure, CONTRACT)
    assert exposure_result["decision"] == "needs_backflow"
    assert "INDEPENDENT_EXPOSURE_NOT_QUALIFIED" in issue_codes(exposure_result)

    peer = deepcopy(READY)
    for item in peer["valuation_inputs"]["peers"]:
        item["operating_metric_evidence_ids"] = [""]
    peer_result = evaluate_bundle12r(peer, CONTRACT)
    assert peer_result["valuation_eligibility"]["peer_method"]["eligible"] is False
    assert peer_result["valuation_eligibility"]["peer_method"]["qualified_peer_count"] == 0


def test_research_questions_are_generated_for_each_missing_essential_driver() -> None:
    result = evaluate_bundle12r(GAP, CONTRACT)
    questions = result["research_question_plan"]["questions"]
    driver_ids = {row["driver_id"] for row in questions}
    assert {"project_count", "unit_value", "acceptance_rate", "gross_margin"}.issubset(driver_ids)


def test_backflow_routes_operating_gaps_to_evidence_and_stock_deep_dive() -> None:
    result = evaluate_bundle12r(GAP, CONTRACT)
    actions = result["backflow_plan"]["actions"]
    skills = {row["required_next_skill"] for row in actions}
    assert "evidence-ingest" in skills
    assert "stock-deep-dive" in skills
    assert "company-valuation" in skills


def test_yaml_fixture_round_trip_is_mapping() -> None:
    dumped = yaml.safe_dump(READY, allow_unicode=True, sort_keys=False)
    assert isinstance(yaml.safe_load(dumped), dict)
