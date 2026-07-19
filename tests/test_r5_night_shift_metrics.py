from __future__ import annotations

from pathlib import Path

from src.maintenance.night_shift.backflow import build_occurrence_queue, load_occurrences
from src.maintenance.night_shift.outcome import queue_metrics


def test_queue_metrics_report_capacity_not_only_total_count() -> None:
    root = Path(__file__).resolve().parents[1]
    queue = build_occurrence_queue(load_occurrences(root), source_commit="4" * 40)
    metrics = queue_metrics(queue)
    assert metrics["total_count"] == 69
    assert metrics["blocked_by_type"]["dependency_blocked"] == 20
    assert metrics["blocked_by_type"]["evidence_required"] == 8
    assert metrics["blocked_by_type"]["human_gate"] == 3
    assert metrics["remaining_work_units"] == 69
    assert metrics["delivery_required_remaining"] == 0
