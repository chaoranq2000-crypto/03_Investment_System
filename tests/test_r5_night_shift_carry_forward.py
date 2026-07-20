from __future__ import annotations

from copy import deepcopy

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT, authoritative_queue
from src.maintenance.night_shift.night04_execution import build_next_night_queue
from tests.night04_test_support import REPO_ROOT


def test_night05_queue_carries_all_unresolved_ids_and_source_fields_verbatim() -> None:
    source = authoritative_queue(REPO_ROOT)
    expected = build_next_night_queue(REPO_ROOT)
    actual = yaml.safe_load(
        (REPO_ROOT / OUTPUT_ROOT / "next_night_queue.yaml").read_text(encoding="utf-8")
    )
    assert actual == expected
    assert actual["carry_forward"]["mode"] == "all_unresolved_ids_verbatim"
    assert actual["carry_forward"]["task_count"] == 69
    assert [item["id"] for item in actual["tasks"]] == [item["id"] for item in source["tasks"]]
    for original, carried in zip(source["tasks"], actual["tasks"], strict=True):
        projection = deepcopy(carried)
        projection.pop("night04_state")
        projection.pop("night04_resolution_receipt_sha256", None)
        assert projection == original


def test_night05_queue_keeps_research_gates_closed() -> None:
    queue = build_next_night_queue(REPO_ROOT)
    assert queue["program_goal"]["close_allowed"] is False
    assert queue["truth_at_start"] == {
        "work_orders_pending": 6,
        "blocker_occurrences_total": 63,
        "blocker_occurrences_resolved": 0,
        "candidate_ready": 43,
        "dependency_blocked": 20,
        "dependency_unlocked": 0,
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
