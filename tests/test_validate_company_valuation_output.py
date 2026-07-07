from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/company-valuation/scripts/validate_valuation_output.py"
EXAMPLE_PATH = REPO_ROOT / ".agents/skills/company-valuation/assets/valuation_output.example.yaml"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_valuation_output", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_example() -> dict:
    return yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))


def test_example_valuation_output_validates(capsys):
    validator = load_validator()
    assert validator.main([str(EXAMPLE_PATH)]) == 0
    assert "outcome: accepted_with_todos" in capsys.readouterr().out


def test_required_top_level_fields_exist():
    validator = load_validator()
    data = load_example()
    data.pop("source_gap")
    errors = validator.validate_output(data)
    assert any("source_gap" in error for error in errors)


def test_input_status_enum_and_market_snapshot_completion_rule():
    validator = load_validator()
    data = load_example()
    data["input_status"] = "complete"
    errors = validator.validate_output(data)
    assert any("cannot be complete" in error for error in errors)
    data["input_status"] = "done"
    errors = validator.validate_output(data)
    assert any("input_status is invalid" in error for error in errors)


def test_scenario_outputs_require_base_bull_bear():
    validator = load_validator()
    data = load_example()
    data["scenario_outputs"].pop("base")
    errors = validator.validate_output(data)
    assert any("scenario_outputs missing" in error for error in errors)
    assert any("scenario_outputs.base is required" in error for error in errors)


def test_each_value_requires_assumption_or_missing_reason():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["scenario_outputs"]["base"]["implied_market_cap"].pop("missing_reason")
    errors = validator.validate_output(data)
    assert any("requires missing_reason" in error for error in errors)


def test_no_advice_language_is_blocked():
    validator = load_validator()
    data = load_example()
    data["no_advice_disclaimer"] = "买入评级"
    errors = validator.validate_output(data)
    assert any("no_advice_disclaimer" in error for error in errors)
    assert any("forbidden advice language" in error for error in errors)
