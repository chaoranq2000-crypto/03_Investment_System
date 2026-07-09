from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".agents/skills/quality-review/scripts/validate_r5_quality_scorecard.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_quality_scorecard", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def scorecard():
    return {
        "artifact_type": "R5_quality_scorecard_v2",
        "allowed_report_level": "source_gapped_research_draft",
        "reviewed_input_flags": {
            "reviewed_market_inputs_available": False,
            "reviewed_peer_inputs_available": False,
            "reviewed_forecast_assumptions_available": False,
            "reviewed_valuation_inputs_available": False,
        },
        "sections": [
            {
                "section_id": "forecast",
                "readiness": "source_gapped",
                "evidence_ids": [],
                "issues": ["TODO_MODEL_INPUT"],
                "limitations": ["reviewed assumptions absent"],
                "fix_owner_skill": "stock-deep-dive",
            },
            {
                "section_id": "valuation",
                "readiness": "source_gapped",
                "evidence_ids": [],
                "issues": ["TODO_MARKET_DATA", "TODO_PEER_DATA"],
                "limitations": ["reviewed market and peer inputs absent"],
                "fix_owner_skill": "stock-deep-dive",
            },
        ],
        "sample_quality_blockers": ["reviewed inputs absent"],
        "next_actions": ["register reviewed inputs"],
    }


def test_source_gapped_scorecard_is_valid():
    validator = load_validator()
    data = scorecard()
    issues = validator.validate_scorecard(data)

    assert validator.derive_decision(data, issues) == "source_gapped_research_draft"


def test_forecast_ready_requires_reviewed_assumptions():
    validator = load_validator()
    data = scorecard()
    data["sections"][0]["readiness"] = "ready"

    issues = validator.validate_scorecard(data)

    assert any(issue["issue_id"] == "R5SC-FCST-001" for issue in issues)
    assert validator.derive_decision(data, issues) == "blocked"


def test_valuation_ready_requires_reviewed_market_peer_and_valuation_inputs():
    validator = load_validator()
    data = scorecard()
    data["sections"][1]["readiness"] = "ready"

    issues = validator.validate_scorecard(data)

    assert any(issue["issue_id"] == "R5SC-VAL-001" for issue in issues)


def test_ready_forecast_and_valuation_pass_when_flags_are_reviewed():
    validator = load_validator()
    data = scorecard()
    data["reviewed_input_flags"] = {
        "reviewed_market_inputs_available": True,
        "reviewed_peer_inputs_available": True,
        "reviewed_forecast_assumptions_available": True,
        "reviewed_valuation_inputs_available": True,
    }
    data["sections"][0]["readiness"] = "ready"
    data["sections"][1]["readiness"] = "ready"

    issues = validator.validate_scorecard(data)

    assert not [issue for issue in issues if issue["severity"] == "high"]
