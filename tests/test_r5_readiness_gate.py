from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/r5_readiness_gate.py"


def load_gate():
    spec = importlib.util.spec_from_file_location("r5_readiness_gate", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def base_inputs() -> dict:
    return {
        "smoke_result": {"status": "pass", "results": []},
        "inventory_status": {"accepted": True, "inventory_status": "validated_complete"},
        "no_advice_passed": True,
        "source_gapped_pack": {
            "quality_status": {"source_gap_visible": True},
            "source_gap_register": [{"gap_id": "gap"}],
            "forecast_model_pack": {"status": "ready"},
            "valuation_pack": {"status": "ready"},
        },
        "evidence_plan": {"artifact_type": "R5_stock_evidence_snapshot_plan"},
        "valuation_handoff_example": {"artifact_type": "R5_valuation_handoff"},
    }


def test_smoke_failure_blocks_readiness():
    gate = load_gate()
    inputs = base_inputs()
    inputs["smoke_result"] = {"status": "fail", "results": [{"name": "inventory", "exit_code": 1}]}

    result = gate.decide_readiness(inputs)

    assert result["decision"] == "R5_BLOCKED"
    assert result["can_enter_source_gapped_real_sample_pilot"] is False


def test_no_advice_failure_blocks_readiness():
    gate = load_gate()
    inputs = base_inputs()
    inputs["no_advice_passed"] = False

    result = gate.decide_readiness(inputs)

    assert result["decision"] == "R5_BLOCKED"
    assert any(item["id"] == "no_advice_gate" for item in result["blockers"])


def test_todos_without_blockers_keep_contracts_only():
    gate = load_gate()
    inputs = base_inputs()
    inputs["source_gapped_pack"] = copy.deepcopy(inputs["source_gapped_pack"])
    inputs["source_gapped_pack"]["forecast_model_pack"]["status"] = "TODO"

    result = gate.decide_readiness(inputs)

    assert result["decision"] == "R5_CONTRACTS_EXECUTABLE_WITH_TODOS_ONLY"
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False


def test_all_green_allows_source_gapped_pilot_only():
    gate = load_gate()

    result = gate.decide_readiness(base_inputs())

    assert result["decision"] == "R5_READY_FOR_SOURCE_GAPPED_REAL_SAMPLE_PILOT"
    assert result["can_enter_source_gapped_real_sample_pilot"] is True
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False
