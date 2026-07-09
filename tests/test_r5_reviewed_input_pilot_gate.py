from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/r5_reviewed_input_pilot_gate.py"


def load_gate():
    spec = importlib.util.spec_from_file_location("r5_reviewed_input_pilot_gate", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def rules():
    return {
        "required_for_reviewed_input_pilot": [
            "reviewed_market_inputs_available",
            "reviewed_peer_inputs_available",
            "reviewed_forecast_assumptions_available",
            "reviewed_valuation_inputs_available",
        ],
        "critical_todo_tokens": ["TODO_MARKET_DATA", "TODO_PEER_DATA", "TODO_MODEL_INPUT", "MISSING_DISCLOSURE"],
        "next_candidate_tasks": ["a", "b", "c", "d"],
        "max_next_candidate_tasks": 3,
    }


def inputs(**dry_run_overrides):
    dry_run = {
        "reviewed_market_inputs_available": False,
        "reviewed_peer_inputs_available": False,
        "reviewed_forecast_assumptions_available": False,
        "reviewed_valuation_inputs_available": False,
        "remaining_todos": ["TODO_MARKET_DATA"],
    }
    dry_run.update(dry_run_overrides)
    return {
        "strict_smoke_result": {"status": "pass", "failed": 0},
        "reviewed_input_dry_run_result": dry_run,
        "quality_scorecard_v2": {"allowed_report_level": "source_gapped_research_draft", "sample_quality_blockers": ["todo"]},
        "pack_promotion_gate_result": {"promotion_level": "source_gapped_research_draft", "blockers": []},
        "no_advice_gate_passed": True,
    }


def test_missing_reviewed_inputs_keep_pilot_closed():
    gate = load_gate()
    result = gate.evaluate_gate(inputs(), rules())

    assert result["reviewed_input_pilot_allowed"] is False
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False
    assert any(blocker["id"] == "reviewed_input_requirements" for blocker in result["blockers"])


def test_all_reviewed_inputs_allow_reviewed_input_pilot_only():
    gate = load_gate()
    result = gate.evaluate_gate(
        inputs(
            reviewed_market_inputs_available=True,
            reviewed_peer_inputs_available=True,
            reviewed_forecast_assumptions_available=True,
            reviewed_valuation_inputs_available=True,
            remaining_todos=["MISSING_DISCLOSURE"],
        ),
        rules(),
    )

    assert result["reviewed_input_pilot_allowed"] is True
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False


def test_sample_quality_requires_promotion_and_no_critical_todos():
    gate = load_gate()
    data = inputs(
        reviewed_market_inputs_available=True,
        reviewed_peer_inputs_available=True,
        reviewed_forecast_assumptions_available=True,
        reviewed_valuation_inputs_available=True,
        remaining_todos=[],
    )
    data["pack_promotion_gate_result"] = {"promotion_level": "sample_quality_candidate", "blockers": []}
    data["quality_scorecard_v2"] = {"allowed_report_level": "sample_quality_candidate", "sample_quality_blockers": []}

    result = gate.evaluate_gate(data, rules())

    assert result["sample_quality_report_allowed"] is True
    assert result["p2_allowed"] is False
