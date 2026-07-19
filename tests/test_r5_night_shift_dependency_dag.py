from __future__ import annotations

from pathlib import Path

from src.maintenance.night_shift.backflow import (
    build_dependency_dag,
    build_occurrence_queue,
    load_occurrences,
)


def test_dependency_blockers_have_acyclic_non_orphan_unlock_conditions() -> None:
    root = Path(__file__).resolve().parents[1]
    queue = build_occurrence_queue(load_occurrences(root), source_commit="4" * 40)
    dag = build_dependency_dag(queue)
    assert dag["node_count"] == 69
    assert dag["dependency_blocker_count"] == 20
    assert dag["cycle_count"] == 0
    assert dag["orphan_dependency_blockers"] == []
    dependency_tasks = [
        task for task in queue.tasks if task.work_type == "dependency_blocked"
    ]
    assert all(task.depends_on for task in dependency_tasks)
