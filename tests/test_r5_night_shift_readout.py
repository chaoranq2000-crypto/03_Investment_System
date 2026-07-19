from __future__ import annotations

from pathlib import Path

from src.maintenance.night_shift.bf2_seed import build_seed_queue
from src.maintenance.night_shift.readout import (
    build_morning_payload,
    build_next_queue,
    compare_files,
    markdown_bytes,
)

from tests.test_r5_night_shift_bf2_seed import synthetic_inventory


def test_morning_readout_and_next_queue_are_deterministic() -> None:
    inventory = synthetic_inventory()
    inventory["classification_counts"] = {
        "engineering_local": 8,
        "evidence_required": 8,
        "analysis_required": 24,
        "human_gate": 3,
        "dependency_blocked": 20,
    }
    state = build_seed_queue(inventory)
    next_queue = build_next_queue(inventory, source_commit="a" * 40)
    payload = build_morning_payload(
        run_id="run-a",
        baseline={"source_branch": "source", "expected_source_sha": "b" * 40},
        mission_state=state,
        seed_receipt={
            "work_orders_pending": 6,
            "blocker_occurrences_resolved": 0,
            "blocker_occurrences_total": 63,
        },
        validation_receipt={"commands": []},
        determinism_receipt={
            "all_byte_for_byte_equal": True,
            "comparisons": [],
            "stable_receipt_sha256": "c" * 64,
        },
        scope_audit={
            "forbidden_paths_changed": 0,
            "tracked_local_runtime_outputs": 0,
            "tracked_bf2_run_outputs": 0,
            "scope_guard_pass": True,
        },
        branch={
            "target_branch": "target",
            "local_sha": "a" * 40,
            "remote_sha": "a" * 40,
            "remote_sha_equals_local": True,
            "commits": [],
        },
        next_queue=next_queue,
    )
    assert markdown_bytes(payload) == markdown_bytes(payload)
    assert payload["bf2_delta"]["blocker_occurrences_resolved"]["end"] == 0
    assert next_queue.task_map["ns02_t00_review_pointer_contracts"].status == "human_gate"
    assert next_queue.task_map["ns02_t40_resume_bf2_work_orders"].status == "pending"


def test_compare_files_writes_deterministic_receipt(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("same\n", encoding="utf-8")
    right.write_text("same\n", encoding="utf-8")
    receipt_path = tmp_path / "receipt.json"
    receipt = compare_files([(left, right)], receipt_path)
    assert receipt["all_byte_for_byte_equal"] is True
    assert receipt_path.is_file()
