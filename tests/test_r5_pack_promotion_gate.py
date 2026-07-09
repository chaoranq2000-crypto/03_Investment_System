from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/r5_pack_promotion_gate.py"


def load_gate():
    spec = importlib.util.spec_from_file_location("r5_pack_promotion_gate", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pack():
    return {
        "quality_status": {"high_issue_count": 0, "source_gap_visible": True},
        "evidence_snapshot_pack": {"evidence_ids": ["ev_1"]},
        "source_gap_register": [{"missing_reason": "TODO_MARKET_DATA"}, {"missing_reason": "MISSING_DISCLOSURE"}],
        "valuation_pack": {"market_snapshot": {"missing_reason": "TODO_MARKET_DATA"}},
    }


def rules():
    return {
        "blocking_todo_tokens": ["TODO_MARKET_DATA", "TODO_PEER_DATA", "TODO_MODEL_INPUT", "MISSING_DISCLOSURE"],
        "required_for_reviewed_input_research_draft": [
            "reviewed_market_inputs_available",
            "reviewed_peer_inputs_available",
            "reviewed_forecast_assumptions_available",
            "reviewed_valuation_inputs_available",
        ],
        "required_for_sample_quality_candidate": [
            "reviewed_market_inputs_available",
            "reviewed_peer_inputs_available",
            "reviewed_forecast_assumptions_available",
            "reviewed_valuation_inputs_available",
            "reviewed_business_disclosure_available",
        ],
    }


def dry_run(**overrides):
    data = {
        "reviewed_market_inputs_available": False,
        "reviewed_peer_inputs_available": False,
        "reviewed_forecast_assumptions_available": False,
        "reviewed_valuation_inputs_available": False,
        "reviewed_business_disclosure_available": False,
        "remaining_todos": ["TODO_MARKET_DATA"],
    }
    data.update(overrides)
    return data


def test_source_gapped_pack_stays_source_gapped():
    gate = load_gate()
    result = gate.evaluate_promotion(pack(), dry_run(), rules())

    assert result["promotion_level"] == "source_gapped_research_draft"
    assert result["sample_quality_candidate_allowed"] is False


def test_reviewed_inputs_without_business_split_allow_draft_plus_only():
    gate = load_gate()
    result = gate.evaluate_promotion(
        pack(),
        dry_run(
            reviewed_market_inputs_available=True,
            reviewed_peer_inputs_available=True,
            reviewed_forecast_assumptions_available=True,
            reviewed_valuation_inputs_available=True,
            remaining_todos=["MISSING_DISCLOSURE"],
        ),
        rules(),
    )

    assert result["promotion_level"] == "reviewed_input_research_draft"


def test_sample_quality_requires_no_remaining_todos_and_all_reviewed_inputs():
    gate = load_gate()
    result = gate.evaluate_promotion(
        pack(),
        dry_run(
            reviewed_market_inputs_available=True,
            reviewed_peer_inputs_available=True,
            reviewed_forecast_assumptions_available=True,
            reviewed_valuation_inputs_available=True,
            reviewed_business_disclosure_available=True,
            remaining_todos=[],
        ),
        rules(),
    )

    assert result["promotion_level"] == "sample_quality_candidate"


def test_hidden_todo_blocks_promotion():
    gate = load_gate()
    bad_pack = pack()
    bad_pack["source_gap_register"] = []

    result = gate.evaluate_promotion(bad_pack, dry_run(), rules())

    assert result["promotion_level"] == "blocked"
    assert any(item["id"] == "hidden_todo_check" for item in result["blockers"])
