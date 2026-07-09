from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_valuation_pack.py"
EXAMPLE_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_valuation_pack.example.yaml"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_valuation_pack", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_example() -> dict:
    return yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))


def test_example_valuation_pack_is_accepted_with_todos(capsys):
    validator = load_validator()

    assert validator.main(["--input", str(EXAMPLE_PATH)]) == 0
    assert "outcome: accepted_with_todos" in capsys.readouterr().out


def test_market_snapshot_fields_are_required():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["market_snapshot"].pop("share_count")

    errors = validator.validate_valuation_pack(data)

    assert any("market_snapshot.share_count is required" in error for error in errors)


def test_null_market_value_requires_missing_reason():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["market_snapshot"]["current_price"].pop("missing_reason")

    errors = validator.validate_valuation_pack(data)

    assert any("market_snapshot.current_price requires missing_reason" in error for error in errors)


def test_non_null_market_value_requires_source_support():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["market_snapshot"]["current_price"]["value"] = 10.0
    data["market_snapshot"]["current_price"]["missing_reason"] = None

    errors = validator.validate_valuation_pack(data)

    assert any("market_snapshot.current_price requires evidence_id or metric_id" in error for error in errors)


def test_ready_status_requires_market_peer_and_method_outputs():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["status"] = "ready"

    errors = validator.validate_valuation_pack(data)

    assert any("status ready requires dated market_snapshot.as_of_date" in error for error in errors)
    assert any("status ready requires at least one peer" in error for error in errors)
    assert any("status ready requires at least one valuation method" in error for error in errors)


def test_forecast_dependent_ready_method_requires_forecast_support():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    method = data["valuation_methods"][1]
    method["status"] = "ready"
    method["supported_output"] = {"value": 100.0, "unit": "CNY"}

    errors = validator.validate_valuation_pack(data)

    assert any("forecast-dependent ready method requires forecast" in error for error in errors)


def test_forbidden_direct_trading_phrase_is_rejected():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["limitations"].append("目标价 instruction")

    errors = validator.validate_valuation_pack(data)

    assert any("forbidden valuation advice phrase" in error for error in errors)
