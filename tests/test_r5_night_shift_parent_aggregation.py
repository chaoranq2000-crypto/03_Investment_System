from __future__ import annotations

from pathlib import Path

from src.maintenance.night_shift.night03 import authoritative_queue
from src.maintenance.night_shift.night03_execution import aggregate_parent


def test_parent_closes_only_after_every_required_occurrence_is_resolved() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    tasks = authoritative_queue(repo_root)["tasks"]
    parent = next(item for item in tasks if item["work_type"] == "bf2_work_order")
    states = {item: {"status": "candidate_ready"} for item in parent["depends_on"]}
    pending = aggregate_parent(parent, states)
    assert pending["status"] == "pending"
    assert pending["resolved_occurrences"] == 0
    for occurrence_id in states:
        states[occurrence_id] = {"status": "resolved"}
    resolved = aggregate_parent(parent, states)
    assert resolved["status"] == "resolved"
    assert resolved["resolved_occurrences"] == resolved["required_occurrences"]
    assert resolved["unresolved_occurrence_ids"] == []
