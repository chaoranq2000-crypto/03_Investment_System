from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/r5_next_pilot_gate.py"


def load_gate():
    spec = importlib.util.spec_from_file_location("r5_next_pilot_gate", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def readiness():
    return {
        "decision": "R5_CONTRACTS_EXECUTABLE_WITH_TODOS_ONLY",
        "blockers": [],
        "non_blockers": [{"id": "forecast_todo"}],
        "input_summary": {"source_gap_report_exists": True, "no_advice_passed": True},
    }


def rules():
    return {"candidate_tasks": ["a", "b", "c", "d"], "max_next_candidate_tasks": 3}


def registries(market_status="pending", forecast_status="pending"):
    return {
        "market_peer_input_registry": {"review_status": market_status},
        "forecast_assumption_registry": {"review_status": forecast_status},
        "evidence_request_review_ledger": {
            "review_status": "pending",
            "summary": {"pending_count": 10},
            "items": [{"review_decision": "pending", "evidence_id": None}],
        },
    }


def test_pending_registries_keep_pilot_false():
    gate = load_gate()
    result = gate.evaluate_gate(readiness(), rules(), registries())

    assert result["source_gapped_real_sample_pilot_allowed"] is False
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False
    assert any(item["id"] == "market_peer_registry_pending" for item in result["registry_blockers"])


def test_reviewed_degraded_registries_may_allow_source_gapped_pilot_only():
    gate = load_gate()
    result = gate.evaluate_gate(
        readiness(),
        rules(),
        registries("explicitly_degraded_but_reviewed", "explicitly_degraded_but_reviewed"),
    )

    assert result["source_gapped_real_sample_pilot_allowed"] is True
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False


def test_accepted_null_evidence_keeps_pilot_false():
    gate = load_gate()
    data = registries("explicitly_degraded_but_reviewed", "explicitly_degraded_but_reviewed")
    data["evidence_request_review_ledger"]["items"] = [{"review_decision": "accepted", "evidence_id": None}]

    result = gate.evaluate_gate(readiness(), rules(), data)

    assert result["source_gapped_real_sample_pilot_allowed"] is False
