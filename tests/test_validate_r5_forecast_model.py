from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_forecast_model.py"
EXAMPLE_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_forecast_model.example.yaml"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_forecast_model", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_example() -> dict:
    return yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))


def test_example_forecast_model_is_valid(capsys):
    validator = load_validator()
    assert validator.main([str(EXAMPLE_PATH)]) == 0
    assert "outcome: accepted_with_todos" in capsys.readouterr().out


def test_forecast_years_must_cover_2026_to_2028():
    validator = load_validator()
    data = load_example()
    data["forecast_years"] = ["2026E"]
    errors = validator.validate_forecast_model(data)
    assert any("2027E" in error and "2028E" in error for error in errors)


def test_base_case_requires_four_metrics_each_year():
    validator = load_validator()
    data = load_example()
    del data["scenarios"]["base_case"]["forecast_table"]["2026E"]["eps"]
    errors = validator.validate_forecast_model(data)
    assert any("2026E.eps is required" in error for error in errors)


def test_each_forecast_value_requires_assumption_or_missing_reason():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    metric = data["scenarios"]["base_case"]["forecast_table"]["2026E"]["revenue"]
    metric.pop("missing_reason")
    errors = validator.validate_forecast_model(data)
    assert any("requires assumption_id or missing_reason" in error for error in errors)


def test_sample_quality_cannot_use_missing_forecast_values():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["status"] = "ready"
    data["sample_quality_allowed"] = True
    errors = validator.validate_forecast_model(data)
    assert any("reviewed non-missing forecast value" in error for error in errors)


def test_scenarios_and_sensitivity_fields_are_required():
    validator = load_validator()
    data = load_example()
    data["scenarios"].pop("bear_case")
    data["sensitivity_table"][0].pop("impact_metric")
    errors = validator.validate_forecast_model(data)
    assert any("scenario missing: bear_case" in error for error in errors)
    assert any("sensitivity_table[0] missing" in error for error in errors)
