from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml

from src.research.r5_bundle13r_evidence_backflow import (
    build_execution_queue,
    evaluate_backflow_execution,
    load_yaml,
    merge_reviewed_backfill,
    validate_bundle12r_context,
    validate_contract,
    validate_observation,
    validate_reviewed_backfill,
)

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_CONTRACT = load_yaml(ROOT / "config" / "r5_bundle13r_backflow_execution_contract.yaml")
FIXTURE_CONTRACT = load_yaml(
    ROOT / "tests" / "fixtures" / "r5_bundle13r" / "r5_bundle13r_fixture_contract.yaml"
)
CONTRACT = FIXTURE_CONTRACT
CONTEXT = ROOT / "tests" / "fixtures" / "r5_bundle13r" / "bundle12r_context"
CANONICAL_CONTEXT = (
    ROOT
    / "reports"
    / "workflow_runs"
    / "wf_20260703_stock_first_002837_invic"
    / "bundle12r"
)
READY = load_yaml(ROOT / "tests" / "fixtures" / "r5_bundle13r" / "reviewed_backfill_ready.yaml")
PARTIAL = load_yaml(ROOT / "tests" / "fixtures" / "r5_bundle13r" / "reviewed_backfill_partial.yaml")
INVALID = load_yaml(ROOT / "tests" / "fixtures" / "r5_bundle13r" / "reviewed_backfill_invalid.yaml")


def codes(items):
    return {row.code for row in items}


def context_and_queue():
    artifacts, issues = validate_bundle12r_context(CONTEXT, CONTRACT, verify_artifact_hashes=False)
    assert issues == []
    queue = build_execution_queue(artifacts["backflow"], artifacts["questions"], artifacts["input"], CONTRACT)
    return artifacts, queue


def test_contract_keeps_dependency_order_and_promotions_closed():
    assert validate_contract(CONTRACT) == []
    assert CONTRACT["execution_order"] == [
        "BF12R-002",
        "BF12R-003",
        "RERUN_BUNDLE12R_OPERATING_GATE",
        "BF12R-001",
    ]
    assert CONTRACT["fixed_boundaries"]["sample_quality_allowed"] is False
    assert CONTRACT["fixed_boundaries"]["p2_allowed"] is False


def test_context_binds_to_exact_bundle12r_generation():
    artifacts, issues = validate_bundle12r_context(CONTEXT, CONTRACT, verify_artifact_hashes=False)
    assert issues == []
    assert artifacts["lock"]["generation_id"] == "op_evidence_gen_r5_bundle12r_e3567efdc999aa91"
    assert artifacts["result"]["decision"] == "needs_backflow"


def test_canonical_contract_binds_to_current_locked_bundle12r_generation():
    artifacts, issues = validate_bundle12r_context(
        CANONICAL_CONTEXT,
        CANONICAL_CONTRACT,
        verify_artifact_hashes=True,
    )
    assert issues == []
    assert artifacts["lock"]["generation_id"] == "op_evidence_gen_r5_bundle12r_fd5d23c5eb35ac27"
    queue = build_execution_queue(
        artifacts["backflow"],
        artifacts["questions"],
        artifacts["input"],
        CANONICAL_CONTRACT,
    )
    assert sum(row["target_kind"] == "driver" for row in queue["items"]) == 9
    assert sum(row["target_kind"] == "financial_total" for row in queue["items"]) == 2
    assert sum(row["target_kind"] == "independent_exposure" for row in queue["items"]) == 3
    assert sum(row["target_kind"] == "overlap" for row in queue["items"]) == 3


def test_canonical_contract_rejects_stale_invic_gap_fixture_binding():
    _, issues = validate_bundle12r_context(CONTEXT, CANONICAL_CONTRACT)
    found = codes(issues)
    assert "BUNDLE12R_GENERATION_ID_MISMATCH" in found
    assert "BUNDLE12R_PHYSICAL_HASH_MISMATCH" in found


def test_queue_reorders_backflow_by_dependency_not_yaml_order():
    _, queue = context_and_queue()
    action_ids = [row["action_id"] for row in queue["items"]]
    first_valuation = action_ids.index("BF12R-001")
    assert all(action in {"BF12R-002", "BF12R-003", "RERUN_BUNDLE12R_OPERATING_GATE"} for action in action_ids[:first_valuation])
    assert action_ids.index("RERUN_BUNDLE12R_OPERATING_GATE") < first_valuation
    assert sum(row["target_kind"] == "driver" for row in queue["items"]) == 8
    assert sum(row["target_kind"] == "financial_total" for row in queue["items"]) == 2
    assert sum(row["target_kind"] == "independent_exposure" for row in queue["items"]) == 2
    assert sum(row["target_kind"] == "overlap" for row in queue["items"]) == 1


def test_ready_reviewed_backfill_is_valid_and_ready_for_bundle12r_rerun():
    _, queue = context_and_queue()
    issues = validate_reviewed_backfill(READY, queue, CONTRACT)
    assert issues == []
    result = evaluate_backflow_execution(queue=queue, reviewed_backfill=READY, validation_issues=issues)
    assert result["decision"] == "ready_for_bundle12r_rerun"
    assert result["unresolved_t1_t2_item_count"] == 0
    assert result["valuation_backflow_allowed"] is False


def test_partial_reviewed_backfill_stays_in_progress_without_inventing_values():
    _, queue = context_and_queue()
    issues = validate_reviewed_backfill(PARTIAL, queue, CONTRACT)
    assert issues == []
    result = evaluate_backflow_execution(queue=queue, reviewed_backfill=PARTIAL, validation_issues=issues)
    assert result["decision"] == "backflow_execution_in_progress"
    assert result["unresolved_t1_t2_item_count"] > 0
    assert result["sample_quality_allowed"] is False
    assert result["p2_allowed"] is False


def test_missing_evidence_and_locators_block_confirmed_promotion():
    _, queue = context_and_queue()
    issues = validate_reviewed_backfill(INVALID, queue, CONTRACT)
    assert "OBSERVATION_EVIDENCE_IDS_MISSING" in codes(issues)
    assert "OBSERVATION_LOCATORS_MISSING" in codes(issues)
    result = evaluate_backflow_execution(queue=queue, reviewed_backfill=INVALID, validation_issues=issues)
    assert result["decision"] == "blocked_invalid_reviewed_backfill"


def test_bounded_estimate_requires_ordered_bounds_method_and_replacement_trigger():
    row = {
        "status": "bounded_estimate",
        "lower_bound": 5,
        "upper_bound": 3,
        "unit": "ratio",
        "period": "2025A",
        "confidence": 0.7,
        "source_tier": "B",
        "evidence_ids": ["E1"],
        "locators": ["p.1"],
        "financial_mapping": "revenue",
    }
    found = codes(validate_observation(row, CONTRACT, scope="fixture", require_financial_mapping=True))
    assert "BOUNDED_ESTIMATE_BOUNDS_INVALID" in found
    assert "BOUNDED_ESTIMATE_METHODOLOGY_MISSING" in found
    assert "BOUNDED_ESTIMATE_OVERLAP_TREATMENT_MISSING" in found
    assert "REPLACEMENT_TRIGGER_MISSING" in found


def test_missing_status_cannot_carry_numeric_value():
    row = {
        "status": "missing",
        "value": 123,
        "unit": "CNY_mn",
        "period": "2025A",
        "confidence": 0,
        "source_tier": "D",
        "evidence_ids": [],
        "locators": [],
        "report_limitation": "No disclosure.",
        "replacement_trigger": {
            "metric_or_event": "future filing",
            "due_or_review_date": "2026-12-31",
            "source_plan": "issuer filing",
        },
    }
    assert "NONQUALIFIED_OBSERVATION_PROMOTES_NUMERIC_VALUE" in codes(
        validate_observation(row, CONTRACT, scope="fixture")
    )


def test_merge_updates_drivers_financial_totals_exposure_and_overlap():
    artifacts, _ = context_and_queue()
    promoted = merge_reviewed_backfill(artifacts["input"], READY, generation_id="fixture_generation")
    segments = {row["segment_id"]: row for row in promoted["segments"]}
    broad_drivers = {row["driver_id"]: row for row in segments["broad_data_center_thermal"]["drivers"]}
    assert broad_drivers["project_count"]["status"] == "confirmed"
    assert promoted["financial_totals"]["revenue"]["value"] == 1000
    assert segments["liquid_cooling_related"]["independent_exposure"]["value"] == 200
    assert promoted["overlaps"][0]["relation"] == "contains"
    assert promoted["bundle13r_backfill_lineage"]["backfill_generation_id"] == "fixture_generation"


def test_valuation_only_opens_after_downstream_bundle12r_operating_ready():
    _, queue = context_and_queue()
    issues = validate_reviewed_backfill(READY, queue, CONTRACT)
    downstream = {"decision": "operating_evidence_ready"}
    result = evaluate_backflow_execution(
        queue=queue,
        reviewed_backfill=READY,
        validation_issues=issues,
        downstream_bundle12r_result=downstream,
    )
    assert result["decision"] == "operating_evidence_requalified"
    assert result["valuation_backflow_allowed"] is True
    assert result["required_next_skill"] == "company-valuation"


def test_unknown_overlap_does_not_resolve_t2():
    _, queue = context_and_queue()
    payload = deepcopy(READY)
    payload["overlaps"][0]["relation"] = "unknown"
    issues = validate_reviewed_backfill(payload, queue, CONTRACT)
    assert "OVERLAP_RELATION_INVALID" in codes(issues)
