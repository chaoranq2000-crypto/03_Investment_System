from __future__ import annotations

from collections import Counter
from pathlib import Path

from src.maintenance.night_shift.backflow import (
    EXPECTED_CLASSIFICATION,
    build_occurrence_queue,
    load_occurrences,
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_real_63_occurrences_expand_losslessly_to_69_tasks() -> None:
    occurrences = load_occurrences(repo_root())
    queue = build_occurrence_queue(occurrences, source_commit="4" * 40)
    counts = Counter(item["classification"] for item in occurrences)
    assert dict(sorted(counts.items())) == EXPECTED_CLASSIFICATION
    assert len(occurrences) == 63
    assert len(queue.tasks) == 69
    assert sum(task.work_type == "bf2_work_order" for task in queue.tasks) == 6
    assert queue.baseline["blocker_occurrences_resolved"] == 0
    assert all(item["resolved"] is False for item in occurrences)
