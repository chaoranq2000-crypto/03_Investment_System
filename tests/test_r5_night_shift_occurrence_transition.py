from __future__ import annotations

from pathlib import Path

from src.maintenance.night_shift.night03 import authoritative_queue
from src.maintenance.night_shift.night03_execution import (
    build_resolution_receipt,
    initial_occurrence_state,
    transition_occurrence,
)


def test_occurrence_transitions_preserve_candidate_decision_attempt_and_receipt_chain() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    task = next(
        item
        for item in authoritative_queue(repo_root)["tasks"]
        if item["work_type"] == "analysis_required"
    )
    state = initial_occurrence_state(task)
    state = transition_occurrence(
        state,
        "candidate_ready",
        event_id="candidate",
        candidate_artifact_sha256="a" * 64,
    )
    decision = {
        "occurrence_id": task["id"],
        "decision": "approved",
        "decision_digest_sha256": "b" * 64,
    }
    state = transition_occurrence(
        state, "approved", event_id="approved", validated_decision=decision
    )
    state = transition_occurrence(state, "running", event_id="running")
    receipt = build_resolution_receipt(
        occurrence_id=task["id"],
        decision_digest_sha256="b" * 64,
        implementation_tree_sha="c" * 40,
        commands=[{"command": "pytest", "exit_code": 0}],
        outputs=[],
        terminal_status="passed",
        lineage_match=True,
        resolution_claim_allowed=True,
    )
    state = transition_occurrence(
        state, "passed", event_id="passed", execution_receipt=receipt
    )
    state = transition_occurrence(
        state,
        "resolved",
        event_id="resolved",
        validated_decision=decision,
        execution_receipt=receipt,
    )
    assert state["status"] == "resolved"
    assert state["attempts"] == 1
    assert state["candidate_artifact_sha256"] == "a" * 64
    assert state["decision_digest_sha256"] == "b" * 64
    assert state["resolution_receipt_sha256"] == receipt["stable_receipt_sha256"]
    assert transition_occurrence(
        state,
        "resolved",
        event_id="resolved",
        validated_decision=decision,
        execution_receipt=receipt,
    ) == state
