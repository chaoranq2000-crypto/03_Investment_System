from src.research.r5_bundle13r_workflow_state import apply_bundle13r_result_to_state


def test_ready_result_routes_to_bundle12r_rerun_and_keeps_promotions_closed():
    updated = apply_bundle13r_result_to_state(
        {"workflow_id": "wf_20260703_stock_first_002837_invic"},
        {
            "decision": "ready_for_bundle12r_rerun",
            "source_bundle12r_generation_id": "op_evidence_gen_r5_bundle12r_fd5d23c5eb35ac27",
            "resolved_t1_t2_item_count": 17,
            "unresolved_t1_t2_item_count": 0,
            "valuation_backflow_allowed": False,
        },
        generation_id="backflow_gen_fixture",
        as_of="2026-07-15",
    )
    assert updated["required_next_skill"] == "research-orchestrator"
    assert updated["current_stage"] == "R5_bundle13r_rerun_bundle12r_operating_gate"
    assert updated["sample_quality_allowed"] is False
    assert updated["p2_allowed"] is False


def test_requalified_result_routes_to_company_valuation():
    updated = apply_bundle13r_result_to_state(
        {},
        {
            "decision": "operating_evidence_requalified",
            "source_bundle12r_generation_id": "op_evidence_gen_r5_bundle12r_fd5d23c5eb35ac27",
            "resolved_t1_t2_item_count": 17,
            "unresolved_t1_t2_item_count": 0,
            "valuation_backflow_allowed": True,
        },
        generation_id="backflow_gen_fixture",
        as_of="2026-07-15",
    )
    assert updated["required_next_skill"] == "company-valuation"
    assert updated["bundle13r_backflow_execution"]["valuation_backflow_allowed"] is True
