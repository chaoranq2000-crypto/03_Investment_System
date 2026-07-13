from scripts.start_r5_bundle10r_reader_rebuild import transition_state
from tests.r5_bundle10r_test_fixtures import binding, model_lock


def test_forward_state_preserves_historical_bundle10():
    state = {
        "status": "accepted_with_todos",
        "current_stage": "R5_bundle9r_closed",
        "bundle10_close": {"status": "historical_closed"},
        "completed_stages": ["bundle10_historical", "R5_bundle9r_closed"],
    }
    out = transition_state(state, binding(), model_lock())
    assert out["bundle10_close"] == state["bundle10_close"]
    assert out["completed_stages"] == state["completed_stages"]
    assert out["bundle10r_rebuild"]["status"] == "in_progress"
    assert "bundle10_close" in out["bundle10r_rebuild"]["historical_bundle10_keys_preserved"]
    assert out["sample_quality_allowed"] is False
    assert out["p2_allowed"] is False
