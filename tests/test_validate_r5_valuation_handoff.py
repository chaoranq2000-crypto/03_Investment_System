from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/validate_r5_valuation_handoff.py"
EXAMPLE_PATH = REPO_ROOT / ".agents/skills/company-valuation/assets/r5_valuation_handoff.example.yaml"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_valuation_handoff", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_example() -> dict:
    return yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))


def test_example_handoff_validates():
    validator = load_validator()
    issues = validator.validate_handoff(load_example())
    assert issues == []
    assert validator.main([str(EXAMPLE_PATH)]) == 0


def test_missing_market_snapshot_value_blocks_gate():
    validator = load_validator()
    data = load_example()
    data["market_snapshot"].pop("current_price")
    issues = validator.validate_handoff(data)
    assert any(issue["path"] == "market_snapshot.current_price" for issue in issues)
    assert validator.decision_for(issues) == "blocked"


def test_missing_peer_context_blocks_gate():
    validator = load_validator()
    data = load_example()
    data["peer_context"]["peers"] = []
    issues = validator.validate_handoff(data)
    assert any(issue["path"] == "peer_context" for issue in issues)


def test_target_price_advice_language_is_rejected():
    validator = load_validator()
    data = load_example()
    data["scenario_values"][0]["interpretation_boundary"] = "price target is 12 and should guide action"
    issues = validator.validate_handoff(data)
    assert any(issue["path"] == "no_advice_scan" for issue in issues)


def test_scenario_value_requires_support_metadata():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    target = data["scenario_values"][0]["target_price_scenario"]
    target.pop("source_evidence_id")
    target.pop("assumption_id")
    issues = validator.validate_handoff(data)
    assert any("requires evidence_id" in issue["message"] for issue in issues)


def test_raw_numeric_value_is_rejected():
    validator = load_validator()
    data = load_example()
    data["sensitivity"][0]["impact_value"] = 1.5
    issues = validator.validate_handoff(data)
    assert any("raw numeric" in issue["message"] for issue in issues)
