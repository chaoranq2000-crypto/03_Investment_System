from scripts.start_r5_bundle8r_forward_requalification import start_requalification


def test_forward_requalification_preserves_bundle9_and_bundle10_history() -> None:
    original = {
        "workflow_id": "wf_fixture",
        "status": "accepted_with_todos",
        "bundle8_close": {"decision": "accepted_with_todos", "value": 8},
        "bundle9_close": {"decision": "accepted_with_todos", "value": 9},
        "bundle10_close": {"decision": "accepted_with_todos", "value": 10},
    }
    updated = start_requalification(original, baseline_commit="abc", activated_at="2026-07-13")
    assert updated["bundle9_close"] == original["bundle9_close"]
    assert updated["bundle10_close"] == original["bundle10_close"]
    assert updated["status"] == "needs_fix"
    assert updated["bundle8r_requalification"]["mode"] == "forward_requalification_not_rollback"
    assert updated["bundle8r_requalification"]["canonical_sample_quality_allowed"] is False
    assert updated["bundle8r_requalification"]["downstream_plan"]["bundle9"].endswith("bundle9r")
