from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_technical_market_pack.py"
EXAMPLE_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_technical_market_pack.example.yaml"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_technical_market_pack", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_example() -> dict:
    return yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))


def test_example_technical_pack_is_valid(capsys):
    validator = load_validator()
    assert validator.main([str(EXAMPLE_PATH)]) == 0
    assert "outcome: accepted_with_todos" in capsys.readouterr().out


def test_as_of_date_is_required():
    validator = load_validator()
    data = load_example()
    data["as_of_date"] = None
    errors = validator.validate_pack(data)
    assert any("as_of_date is required" in error for error in errors)


def test_required_market_fields_and_missing_reason():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data.pop("MA5")
    data["current_price"].pop("missing_reason")
    errors = validator.validate_pack(data)
    assert any("MA5 is required" in error for error in errors)
    assert any("current_price requires" in error for error in errors)


def test_support_resistance_rows_need_basis_and_source():
    validator = load_validator()
    data = load_example()
    data["support_levels"][0].pop("basis")
    data["resistance_levels"][0].pop("source_id_or_missing_reason")
    errors = validator.validate_pack(data)
    assert any("support_levels[0] missing" in error for error in errors)
    assert any("resistance_levels[0] missing" in error for error in errors)


def test_trading_action_language_is_forbidden():
    validator = load_validator()
    data = load_example()
    data["market_state_judgement"] = "建议买入"
    errors = validator.validate_pack(data)
    assert any("forbidden trading action" in error for error in errors)
