from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_forecast_model_pack.py"
EXAMPLE_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_forecast_model_pack.example.yaml"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_forecast_model_pack", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_example() -> dict:
    return yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))


def test_example_forecast_model_pack_is_accepted_with_todos(capsys):
    validator = load_validator()

    assert validator.main(["--input", str(EXAMPLE_PATH)]) == 0
    assert "outcome: accepted_with_todos" in capsys.readouterr().out


def test_required_years_and_scenarios_are_present():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["forecast_years"] = ["2026E"]
    data["scenarios"].pop("bear_case")

    errors = validator.validate_forecast_model_pack(data)

    assert any("2027E" in error and "2028E" in error for error in errors)
    assert any("scenario missing: bear_case" in error for error in errors)


def test_non_null_forecast_row_requires_assumption_and_source():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    row = data["scenarios"]["base_case"]["forecast_table"]["2026E"]["revenue"]
    row["value"] = 100.0
    row["missing_reason"] = None

    errors = validator.validate_forecast_model_pack(data)

    assert any("assumption_id is required" in error for error in errors)
    assert any("requires evidence_id or metric_id" in error for error in errors)


def test_ready_status_requires_complete_base_case_and_sensitivity():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["status"] = "ready"
    data["sensitivity_tests"] = []

    errors = validator.validate_forecast_model_pack(data)

    assert any("status ready requires at least one sensitivity test" in error for error in errors)
    assert any("status ready requires base_case 2026E.revenue" in error for error in errors)
    assert any("status ready cannot contain TODO_MODEL_INPUT" in error for error in errors)


def test_consensus_comparison_requires_date_and_source_when_present():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["consensus_comparison"] = {"status": "present"}

    errors = validator.validate_forecast_model_pack(data)

    assert any("consensus_comparison.as_of_date" in error for error in errors)
    assert any("consensus_comparison requires source" in error for error in errors)
