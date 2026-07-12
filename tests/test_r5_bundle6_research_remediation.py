from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def load(name):
    return yaml.safe_load((RUN / name).read_text(encoding="utf-8"))


def test_coverage_keeps_methods_and_liquid_cooling_boundary_visible():
    coverage = load("R5_bundle6_coverage_inventory.yaml")
    assert any(x["dimension"] == "industry_and_competition" and x["review_status"].startswith("accepted") for x in coverage["dimensions"])
    assert any(x["dimension"] == "historical_market_series" and not x["mandatory"] for x in coverage["dimensions"])
    assert "unverified" in coverage["liquid_cooling_boundary"]
    assert not coverage["sample_quality_report_allowed"] and not coverage["p2_allowed"]


def test_forecast_bridge_reconciles_eps_and_has_explicit_scenarios():
    bridge = load("R5_bundle6_forecast_bridge.yaml")
    assert set(bridge["scenarios"]) == {"base_case", "bull_case", "bear_case"}
    assert max(abs(r["reconciliation_difference"]) for r in bridge["base_case_bridge"]) < 1e-6
    assert len(bridge["sensitivity_variables"]) == 2
    assert "不直接年化" in bridge["latest_quarter_treatment"]["model_choice"]


def test_valuation_has_date_denominator_and_inactive_methods_without_values():
    value = load("R5_bundle6_valuation_reasoning_pack.yaml")
    assert value["as_of_date"] == "2026-07-10"
    assert "TTM" in value["dated_snapshot"]["denominator_control"]
    inactive = [x for x in value["method_eligibility"] if x["status"] == "inactive"]
    assert {x["method"] for x in inactive} == {"dcf", "sotp"}
    assert value["target_price"] is None and value["rating"] is None
