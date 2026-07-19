from __future__ import annotations

from pathlib import Path

from src.maintenance.night_shift.night03 import authoritative_queue
from src.maintenance.night_shift.night03_execution import (
    build_resolution_receipt,
    initial_occurrence_state,
    replay_decisions,
)


def test_decision_replay_is_idempotent_and_does_not_double_count_resolution() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    task = next(
        item
        for item in authoritative_queue(repo_root)["tasks"]
        if item["work_type"] == "analysis_required"
    )
    initial = {task["id"]: initial_occurrence_state(task)}
    decision = {
        "occurrence_id": task["id"],
        "decision": "approved",
        "decision_digest_sha256": "d" * 64,
    }
    receipt = build_resolution_receipt(
        occurrence_id=task["id"],
        decision_digest_sha256="d" * 64,
        implementation_tree_sha="e" * 40,
        commands=[],
        outputs=[],
        terminal_status="passed",
        lineage_match=True,
        resolution_claim_allowed=True,
    )
    first = replay_decisions(initial, [decision, decision], {task["id"]: receipt})
    second = replay_decisions(initial, [decision], {task["id"]: receipt})
    assert first == second
    assert first["processed_decision_digests"] == ["d" * 64]
    assert first["occurrences"][task["id"]]["status"] == "resolved"
    assert first["occurrences"][task["id"]]["attempts"] == 1
