from __future__ import annotations

from src.maintenance.night_shift.backflow import build_fallback_backlog


def test_external_research_gates_leave_preapproved_fallback_work() -> None:
    backlog = build_fallback_backlog()
    assert backlog["no_ready_research_task_causes_exit"] is False
    assert backlog["fallback_task_count"] == 5
    assert {item["task_id"] for item in backlog["tasks"]} == {
        "ns02_t50_golden_case_inventory",
        "ns02_t51_semantic_quality_negative_fixtures",
        "ns02_t52_driver_contract_gap_matrix",
        "ns02_t53_bundle18_readiness_precheck",
        "ns02_t54_next_mission_seed",
    }
