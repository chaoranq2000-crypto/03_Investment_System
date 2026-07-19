from __future__ import annotations

from pathlib import Path

from src.maintenance.night_shift.night03_validation import (
    build_determinism_receipt,
    build_next_night_queue,
)


def test_night03_decisions_candidates_ledger_readout_and_queue_are_deterministic() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    receipt = build_determinism_receipt(repo_root)
    assert receipt["all_bytes_equal"] is True
    assert receipt["comparison_count"] >= 9
    assert all(item["first_sha256"] == item["second_sha256"] for item in receipt["comparisons"])


def test_night04_queue_carries_every_unresolved_id_and_defers_remote_head() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    queue = build_next_night_queue(repo_root)
    assert queue["program_goal"]["close_allowed"] is False
    assert queue["source_commit_policy"] == "resolve_final_remote_head_at_bootstrap"
    assert queue["carry_forward"]["task_count"] == 69
    assert len({item["id"] for item in queue["tasks"]}) == 69
    assert queue["truth_at_start"]["blocker_occurrences_resolved"] == 0
