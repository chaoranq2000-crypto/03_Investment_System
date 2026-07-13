import importlib.util
from pathlib import Path


def load_script():
    path = Path("scripts/start_r5_bundle9r_forecast_valuation_rebuild.py")
    spec = importlib.util.spec_from_file_location("bundle9r_start", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_forward_state_preserves_history_and_closes_sample_gate():
    module = load_script()
    state = {
        "status": "accepted_with_todos",
        "completed_stages": ["R5_bundle9_close", "R5_bundle10_final_close", "R5_bundle8r_7_quality_close"],
        "evidence_snapshot": {"input_evidence_generation_id": "evidence_gen_r5_bundle8r_b82ba6f33b5044e6"},
        "bundle9_close": {"decision": "accepted_with_todos"},
        "bundle10_close": {"decision": "accepted_with_todos"},
        "bundle8r_close": {"decision": "accepted_with_todos"},
        "bundle8r_requalification": {"bundle9r_rebuilt": False, "bundle10r_rebuilt": False},
        "quality_backflow": {"canonical_sample_quality_allowed": False},
    }
    lock = {"generation_id": "evidence_gen_r5_bundle8r_b82ba6f33b5044e6", "missing_input_count": 0, "downstream_consumers": ["R5_BUNDLE_9R_FORECAST_VALUATION_REBUILD"]}
    updated = module.build_state(state, lock)
    assert updated["bundle9_close"] == state["bundle9_close"]
    assert updated["bundle10_close"] == state["bundle10_close"]
    assert updated["completed_stages"] == state["completed_stages"]
    assert updated["bundle9r_rebuild"]["status"] == "in_progress"
    assert updated["bundle9r_rebuild"]["sample_quality_allowed"] is False
    assert updated["quality_backflow"]["canonical_sample_quality_allowed"] is False
