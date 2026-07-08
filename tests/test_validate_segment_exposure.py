from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/segment-company-mapping/scripts/validate_segment_exposure.py"
EXAMPLE_PATH = REPO_ROOT / ".agents/skills/segment-company-mapping/assets/segment_exposure.example.yaml"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_segment_exposure", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_example() -> dict:
    with EXAMPLE_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_example_segment_exposure_is_valid():
    validator = load_validator()
    data = load_example()
    errors = validator.validate_segment_exposure(data)
    assert errors == []
    assert validator.derive_outcome(data, errors) == "accepted_with_todos"


def test_narrative_exposure_score_is_capped():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["exposures"][2]["exposure_score"] = 2
    errors = validator.validate_segment_exposure(data)
    assert any("narrative_only exposure cannot score above 1" in error for error in errors)


def test_missing_revenue_pct_requires_explicit_token():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["exposures"][0]["revenue_pct"] = None
    errors = validator.validate_segment_exposure(data)
    assert any("revenue_pct" in error for error in errors)


def test_technology_score_above_two_requires_business_support():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["exposures"][1]["exposure_score"] = 3
    errors = validator.validate_segment_exposure(data)
    assert any("technology_reserve exposure above 2" in error for error in errors)


def test_exposure_type_enum_matches_r5_contract():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["exposures"][0]["exposure_type"] = "product"
    errors = validator.validate_segment_exposure(data)
    assert any("exposure_type is invalid" in error for error in errors)


def test_score_must_be_integer_zero_to_five():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["exposures"][0]["exposure_score"] = 2.5
    errors = validator.validate_segment_exposure(data)
    assert any("integer between 0 and 5" in error for error in errors)


def test_score_above_zero_requires_support():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    row = data["exposures"][0]
    row["evidence_ids"] = []
    row["claim_ids"] = []
    row["metric_ids"] = []
    row["missing_reason"] = ""
    errors = validator.validate_segment_exposure(data)
    assert any("requires evidence_ids" in error for error in errors)


def test_company_total_revenue_cannot_be_used_as_segment_revenue():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["exposures"][0]["revenue_basis"] = "company_total_revenue"
    errors = validator.validate_segment_exposure(data)
    assert any("company total revenue" in error for error in errors)


def test_product_line_clue_does_not_update_revenue_exposure():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["exposures"][0]["backflow_decision"] = "update_revenue_exposure"
    errors = validator.validate_segment_exposure(data)
    assert any("backflow_decision is invalid" in error for error in errors)


def test_cli_validates_example(capsys):
    validator = load_validator()
    assert validator.main([str(EXAMPLE_PATH)]) == 0
    captured = capsys.readouterr()
    assert "outcome: accepted_with_todos" in captured.out
