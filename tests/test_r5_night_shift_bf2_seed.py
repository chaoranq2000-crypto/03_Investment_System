from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.maintenance.night_shift.bf2_seed import (
    build_seed_queue,
    classify_occurrence,
    compute_input_set_sha,
    verify_input_manifest,
)
from src.maintenance.night_shift.queue import save_queue
from src.maintenance.night_shift.runner import run_safe_pilot


def synthetic_inventory() -> dict:
    blockers = [
        {
            "blocker_occurrence_id": "BF17R-I-aaaa",
            "work_order_id": "BF17R-WO-1111",
            "classification": "engineering_local",
            "message": "bind a pointer",
            "requested_action": "bind the assertion",
            "source_artifact_path": "reports/example.json",
            "source_artifact_sha256": "a" * 64,
        },
        {
            "blocker_occurrence_id": "BF17R-I-bbbb",
            "work_order_id": "BF17R-WO-1111",
            "classification": "evidence_required",
            "message": "official evidence is missing",
            "requested_action": "acquire reviewed evidence",
            "source_artifact_path": "reports/example.json",
            "source_artifact_sha256": "a" * 64,
        },
    ]
    return {
        "input_set_sha256": "1" * 64,
        "source_commit": "2" * 40,
        "blocker_occurrences": blockers,
        "work_orders": [
            {
                "work_order_id": "BF17R-WO-1111",
                "case_id": "__suite__",
                "route_id": "semantic_reader_traceability",
                "source_generation_id": "generation-a",
                "source_priority": 60,
                "issue_ids": ["BF17R-I-aaaa", "BF17R-I-bbbb"],
                "depends_on": [],
                "requested_actions": ["complete the evidence-backed work order"],
                "acceptance_checks": ["evidence is reviewed"],
            }
        ],
    }


def test_occurrence_classification_is_explicit_and_not_resolution() -> None:
    assert classify_occurrence(
        {"code": "ASSERTION_POINTER_UNRESOLVED", "field": "assertions.path.pointer"}
    ) == "engineering_local"
    assert classify_occurrence(
        {"code": "ASSERTION_FAILED", "field": "assertions.evidence_complete"}
    ) == "evidence_required"
    assert classify_occurrence(
        {"code": "ASSERTION_FAILED", "field": "assertions.suite_hash_bound"}
    ) == "human_gate"


def test_seed_queue_preserves_parent_work_order_and_blocks_unsafe_pilot() -> None:
    queue = build_seed_queue(synthetic_inventory())
    assert len(queue.tasks) == 3
    parent = next(task for task in queue.tasks if task.work_type == "bf2_work_order")
    assert parent.status == "pending"
    assert len(parent.depends_on) == 2
    engineering = next(task for task in queue.tasks if task.work_type == "engineering_local")
    assert engineering.status == "dependency_blocked"
    assert engineering.allowed_paths == ()
    evidence = next(task for task in queue.tasks if task.work_type == "evidence_required")
    assert evidence.status == "evidence_required"
    assert queue.baseline["blocker_occurrences_resolved"] == 0


def test_input_manifest_recomputes_set_and_file_hashes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    destination = repo / ".local/night_shift/inputs/abc/input.txt"
    destination.parent.mkdir(parents=True)
    destination.write_text("immutable\n", encoding="utf-8")
    file_hash = hashlib.sha256(destination.read_bytes()).hexdigest()
    record = {
        "logical_path": "source/input.txt",
        "destination_relative_path": ".local/night_shift/inputs/abc/input.txt",
        "sha256": file_hash,
        "size_bytes": destination.stat().st_size,
        "source_absolute_path": "C:/source/input.txt",
        "mtime_utc": "2026-07-19T00:00:00+00:00",
    }
    manifest = {
        "schema_version": "r5_night_shift_input_manifest_v1",
        "input_set_sha256": compute_input_set_sha([record]),
        "source_commit": "0" * 40,
        "file_count": 1,
        "files": [record],
    }
    path = repo / ".local/night_shift/input_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    loaded, paths = verify_input_manifest(path, repo)
    assert loaded["input_set_sha256"] == manifest["input_set_sha256"]
    assert paths["source/input.txt"] == destination


def test_safe_pilot_truthfully_records_missing_execution_contract(tmp_path: Path) -> None:
    inventory = synthetic_inventory()
    inventory["summary"] = {
        "work_orders_pending": 6,
        "blocker_occurrences_total": 63,
        "blocker_occurrences_resolved": 0,
    }
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    queue_path = tmp_path / "queue.yaml"
    save_queue(queue_path, build_seed_queue(inventory))
    outcome = run_safe_pilot(
        queue_path=queue_path,
        inventory_path=inventory_path,
        run_id="run-a",
        repo_root=tmp_path,
        receipts_dir=tmp_path / "receipts",
        report_path=tmp_path / "pilot.md",
        backflow_path=tmp_path / "backflow.md",
    )
    assert outcome["outcome"] == "no_safe_pilot"
    assert outcome["blocker_occurrences_resolved"] == 0
    assert (tmp_path / "receipts/no_safe_pilot.json").is_file()
    assert "Research blocker resolved: `false`" in (tmp_path / "backflow.md").read_text(
        encoding="utf-8"
    )
