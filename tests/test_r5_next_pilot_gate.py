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


def test_contracts_with_todos_do_not_allow_pilot_or_p2():
    gate = load_gate()
    result = gate.evaluate_gate(
        {"decision": "R5_CONTRACTS_EXECUTABLE_WITH_TODOS_ONLY", "blockers": [], "non_blockers": [{"id": "forecast_todo"}]},
        {"candidate_tasks": ["a", "b", "c", "d"], "max_next_candidate_tasks": 3},
    )

    assert result["source_gapped_real_sample_pilot_allowed"] is False
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False
    assert len(result["next_candidate_tasks"]) == 3


def test_ready_state_allows_only_source_gapped_pilot():
    gate = load_gate()
    result = gate.evaluate_gate(
        {"decision": "R5_READY_FOR_SOURCE_GAPPED_REAL_SAMPLE_PILOT", "blockers": [], "non_blockers": []},
        {"candidate_tasks": [], "max_next_candidate_tasks": 3},
    )

    assert result["source_gapped_real_sample_pilot_allowed"] is True
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False
