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


def test_example_valuation_pack_is_valid(capsys):
    validator = load_validator()
    assert validator.main([str(EXAMPLE_PATH)]) == 0
    assert "outcome: accepted_with_todos" in capsys.readouterr().out


def test_market_snapshot_fields_are_required():
    validator = load_validator()
    data = load_example()
    data["market_snapshot"].pop("share_count")
    errors = validator.validate_valuation_pack(data)
    assert any("market_snapshot.share_count is required" in error for error in errors)


def test_null_market_value_requires_missing_reason():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["market_snapshot"].pop("missing_reason")
    errors = validator.validate_valuation_pack(data)
    assert any("market_snapshot.current_price requires missing_reason" in error for error in errors)


def test_multiples_and_peer_context_are_required():
    validator = load_validator()
    data = load_example()
    data["multiples"].pop("PE_TTM")
    data["peer_context"].pop("missing_reason")
    errors = validator.validate_valuation_pack(data)
    assert any("multiples.PE_TTM is required" in error for error in errors)
    assert any("peer_context requires peer_set" in error for error in errors)


def test_sample_quality_requires_market_and_peer_context():
    validator = load_validator()
    data = load_example()
    data["sample_quality_allowed"] = True
    errors = validator.validate_valuation_pack(data)
    assert any("complete market_snapshot" in error for error in errors)
    assert any("peer context" in error for error in errors)


def test_valuation_scenario_requires_method_assumptions_and_sources():
    validator = load_validator()
    data = load_example()
    data["valuation_scenarios"][0].pop("source_ids_or_missing_reason")
    errors = validator.validate_valuation_pack(data)
    assert any("source_ids_or_missing_reason" in error for error in errors)
