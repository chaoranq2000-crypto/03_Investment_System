from __future__ import annotations

from src.maintenance.night_shift.models import QueueDocument
from src.maintenance.night_shift.outcome import resumable_task_ids

from tests.test_r5_night_shift_contract import queue, task


def test_partial_blocked_and_cutoff_tasks_remain_resumable() -> None:
    values = [
        task("ns01_t00_passed", status="passed"),
        task("ns01_t10_failed", status="failed_retryable"),
        task("ns01_t20_dependency", status="dependency_blocked"),
        task("ns01_t30_evidence", status="evidence_required"),
        task("ns01_t40_human", status="human_gate"),
        task("ns01_t50_cutoff", status="skipped_cutoff"),
    ]
    document = QueueDocument.from_mapping(queue(values))
    assert resumable_task_ids(document) == (
        "ns01_t10_failed",
        "ns01_t20_dependency",
        "ns01_t30_evidence",
        "ns01_t40_human",
        "ns01_t50_cutoff",
    )
