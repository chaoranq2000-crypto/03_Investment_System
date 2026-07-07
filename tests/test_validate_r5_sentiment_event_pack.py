from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_sentiment_event_pack.py"
EXAMPLE_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_sentiment_event_pack.example.yaml"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_sentiment_event_pack", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_example() -> dict:
    return yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))


def test_example_sentiment_event_pack_is_valid(capsys):
    validator = load_validator()
    assert validator.main([str(EXAMPLE_PATH)]) == 0
    assert "outcome: accepted_with_todos" in capsys.readouterr().out


def test_sentiment_layers_are_required_and_need_traceability():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data.pop("macro_sentiment")
    data["company_sentiment"][0].pop("missing_reason")
    errors = validator.validate_pack(data)
    assert any("macro_sentiment must be" in error for error in errors)
    assert any("company_sentiment[0] requires" in error for error in errors)


def test_catalyst_event_required_fields():
    validator = load_validator()
    data = load_example()
    data["catalyst_calendar"][0].pop("impact_path")
    data["catalyst_calendar"][0].pop("source_id_or_missing_reason")
    errors = validator.validate_pack(data)
    assert any("catalyst_calendar[0] missing" in error for error in errors)
    assert any("source_id_or_missing_reason" in error for error in errors)


def test_event_scenario_matrix_requires_base_upside_downside():
    validator = load_validator()
    data = load_example()
    data["event_scenario_matrix"].pop("upside")
    errors = validator.validate_pack(data)
    assert any("event_scenario_matrix missing" in error for error in errors)


def test_trading_action_language_is_forbidden():
    validator = load_validator()
    data = load_example()
    data["event_scenario_matrix"]["base"]["status"] = "交易动作"
    errors = validator.validate_pack(data)
    assert any("forbidden trading action" in error for error in errors)
