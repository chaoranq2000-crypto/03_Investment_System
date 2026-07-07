from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py"
EXAMPLE_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_stock_research_pack", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_example() -> dict:
    with EXAMPLE_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_example_pack_is_valid():
    validator = load_validator()
    assert validator.validate_pack(load_example()) == []


def test_pack_status_enum_is_validated():
    validator = load_validator()
    data = load_example()
    data["pack_status"] = "sample_quality_ready"
    assert any("pack_status must be one of" in error for error in validator.validate_pack(data))


def test_missing_top_level_key_is_reported():
    validator = load_validator()
    data = load_example()
    data.pop("forecast_model_pack")
    assert any("forecast_model_pack" in error for error in validator.validate_pack(data))


def test_business_metric_null_requires_missing_reason():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    revenue = data["business_breakdown_pack"]["business_lines"][0]["revenue"]
    revenue.pop("missing_reason")
    revenue["value"] = None
    assert any("business_lines[0].revenue" in error for error in validator.validate_pack(data))


def test_business_metric_value_requires_evidence_or_metric_id():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    revenue = data["business_breakdown_pack"]["business_lines"][0]["revenue"]
    revenue.pop("missing_reason")
    revenue["value"] = 123
    revenue["evidence_id"] = None
    revenue["metric_id"] = None
    assert any("non-null value requires evidence_id or metric_id" in error for error in validator.validate_pack(data))


def test_sample_quality_requires_no_advice_gate_and_market_snapshot():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["pack_status"] = "sample_quality_candidate"
    data["quality_status"]["allowed_report_level"] = "sample_quality_ready"
    data["quality_status"]["no_advice_gate_passed"] = False
    errors = validator.validate_pack(data)
    assert any("no_advice_gate_passed" in error for error in errors)
    assert any("market_snapshot.current_price" in error for error in errors)


def test_sample_quality_candidate_requires_forecast_and_business_ready():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["pack_status"] = "sample_quality_candidate"
    data["quality_status"]["allowed_report_level"] = "research_draft"
    errors = validator.validate_pack(data)
    assert any("forecast_model_pack.status" in error for error in errors)
    assert any("business_breakdown_pack.status" in error for error in errors)


def test_forbidden_direct_trading_phrase_is_reported():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["report_composition_pack"]["thesis_statement"] = "建议买入"
    assert any("forbidden direct trading phrase" in error for error in validator.validate_pack(data))


def test_cli_accepts_pack_argument(capsys):
    validator = load_validator()
    assert validator.main(["--pack", str(EXAMPLE_PATH)]) == 0
    captured = capsys.readouterr()
    assert "outcome: accepted_with_todos" in captured.out
