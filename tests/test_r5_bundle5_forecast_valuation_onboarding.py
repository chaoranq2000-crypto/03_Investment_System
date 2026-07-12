from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/build_r5_bundle5_forecast_valuation_onboarding.py"
SKILL_SCRIPTS = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BUILDER = load_module("r5_bundle5_forecast_valuation_builder_test", SCRIPT_PATH)
FORECAST_VALIDATOR = load_module(
    "r5_bundle5_forecast_pack_validator_test",
    SKILL_SCRIPTS / "validate_r5_forecast_model_pack.py",
)
VALUATION_VALIDATOR = load_module(
    "r5_bundle5_valuation_pack_validator_test",
    SKILL_SCRIPTS / "validate_r5_valuation_pack.py",
)


def test_model_values_are_reproducible_from_disclosed_base_inputs() -> None:
    values = BUILDER.model_values()
    assert values["revenue_growth"]["2026E"] == 26.0291
    assert values["gross_margin"]["2026E"] == 24.2935
    assert values["opex"]["2026E"] == 18.5321
    assert values["revenue"]["2026E"] == 7_647_141_176.21
    assert values["net_profit"]["2026E"] == 94_115_513.02
    assert values["eps"]["2026E"] == 0.073854
    assert values["eps"]["2028E"] == 0.455462


def test_forecast_records_cover_core_drivers_and_are_estimates() -> None:
    records = BUILDER.build_forecast_records("2026-07-12T01:45:00+08:00")
    assert {row["driver"] for row in records} == {"revenue_growth", "gross_margin", "opex", "net_profit", "eps"}
    assert len({row["input_id"] for row in records}) == 5
    forbidden = {
        "TODO_MARKET_DATA",
        "TODO_PEER_DATA",
        "TODO_MODEL_INPUT",
        "TODO_SOURCE_REQUIRED",
        "MISSING_DISCLOSURE",
        "LOW_CONFIDENCE_CLUE_ONLY",
    }
    text = yaml.safe_dump(records, allow_unicode=True)
    assert not any(token in text for token in forbidden)
    for row in records:
        assert row["periods"] == ["2026E", "2027E", "2028E"]
        assert row["scenario"] == "base"
        assert row["claim_type"] == "estimate"
        assert row["management_guidance_used"] is False
        assert row["review_status"] == "accepted"
        assert row["reviewer"] == "codex"
        assert row["evidence_ids"]
        assert row["formula_by_period"]
        assert row["sensitivity_range_by_period"]
        assert row["sample_quality_allowed"] is False


def test_forecast_candidate_validates_as_ready_without_hidden_model_todos() -> None:
    records = BUILDER.build_forecast_records("2026-07-12T01:45:00+08:00")
    pack = BUILDER.build_forecast_pack(records)
    assert FORECAST_VALIDATOR.validate_forecast_model_pack(pack) == []
    assert FORECAST_VALIDATOR.derive_outcome([], pack) == "accepted"
    assert pack["status"] == "ready"
    assert set(pack["scenarios"]) == {"base_case", "bull_case", "bear_case"}
    assert pack["sample_quality_allowed"] is False
    assert pack["p2_allowed"] is False


def test_net_debt_bridge_reconciles_from_q1_balance_sheet() -> None:
    bridge = BUILDER.net_debt_bridge()
    assert bridge["gross_debt"] == 1_615_274_513.10
    assert bridge["net_debt_proxy"] == 698_135_329.67
    assert bridge["claim_type"] == "inference"
    assert bridge["confidence"] == "low"
    assert bridge["evidence_id"] == BUILDER.Q1_EVIDENCE_ID


def test_valuation_input_fails_closed_on_method_eligibility() -> None:
    records = BUILDER.build_forecast_records("2026-07-12T01:45:00+08:00")
    record = BUILDER.build_valuation_record("2026-07-12T01:45:00+08:00", records)
    assert record["requested_methods"] == ["relative_pe"]
    assert record["method_eligibility"]["relative_pe"]["status"] == "eligible_low_confidence_context_only"
    assert record["method_eligibility"]["dcf"]["status"] == "excluded"
    assert record["method_eligibility"]["sotp"]["status"] == "excluded"
    assert record["scenario_output_boundary"] == "relative multiple context and forward-PE sensitivity only; no price output"
    assert record["cross_multiple_context"]["label"] == "mixed_multiple_signal_not_assessable"
    assert record["no_advice_boundary"] is True
    assert record["sample_quality_allowed"] is False


def test_valuation_candidate_validates_with_explicit_method_gaps() -> None:
    records = BUILDER.build_forecast_records("2026-07-12T01:45:00+08:00")
    pack = BUILDER.build_valuation_pack(records)
    assert VALUATION_VALIDATOR.validate_valuation_pack(pack) == []
    assert VALUATION_VALIDATOR.derive_outcome([], pack) == "accepted"
    methods = {row["method_id"]: row for row in pack["valuation_methods"]}
    assert methods["relative_pe"]["status"] == "ready"
    assert methods["relative_pe"]["confidence"] == "low"
    assert methods["relative_pe"]["supported_output"]["label"] == "mixed_multiple_signal_not_assessable"
    assert methods["dcf"]["status"] == "skipped"
    assert methods["sotp"]["status"] == "skipped"
    assert pack["sample_quality_allowed"] is False
    assert pack["p2_allowed"] is False
