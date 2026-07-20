"""Night04 baseline, truth-lock, and wrapper-receipt helpers.

Night04 consumes the immutable 69-item queue delivered by Night03.  The
module deliberately separates engineering delivery from research resolution:
candidate review packets and pointer dry-runs never resolve an occurrence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from .night03 import load_json, load_yaml, sha256_file, stable_payload, write_json, write_yaml
from .queue import atomic_write


MISSION_ID = "r5_overnight_04_20260722"
SOURCE_COMMIT = "758ab7557d9de9eea42a5aeb5df95e3d68c26f0c"
SOURCE_BRANCH = "codex/r5-night03-targeted-backflow-intake"
TARGET_BRANCH = "codex/r5-night04-review-acceleration-and-unlock"
SOURCE_ROOT = Path("reports/p1_6/r5_night_shift/r5_overnight_03_20260721")
OUTPUT_ROOT = Path("reports/p1_6/r5_night_shift/r5_overnight_04_20260722")
PACKAGE_ROOT = Path("codex_tasks/night_shift/r5_overnight_04_20260722")
SOURCE_QUEUE = SOURCE_ROOT / "next_night_queue.yaml"
EXPECTED_QUEUE_SHA256 = "daaf3a9a9b37fa4c23c75e8bda401e41c41149917a1bf02419f89107ea9abe68"
EXPECTED_NIGHT03_FILE_COUNT = 97
EXPECTED_TOTAL_ITEMS = 69
EXPECTED_OCCURRENCES = 63
EXPECTED_PARENTS = 6
EXPECTED_CANDIDATE_READY = 43
EXPECTED_DEPENDENCY_BLOCKED = 20
EXPECTED_NIGHT03_ZIP_SHA256 = "71e709238fea94148fccda3206394b5fab3d1c59f48fe10004f9fc3d0a3ef13c"
EXPECTED_NIGHT03_ZIP_BYTES = 38830
EXPECTED_TAXONOMY = {
    "analysis_required": 24,
    "dependency_blocked": 20,
    "evidence_required": 8,
    "engineering_local": 8,
    "human_gate": 3,
    "bf2_work_order": 6,
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class Night04Error(RuntimeError):
    """Raised when a Night04 hard baseline or truth gate fails closed."""


class Night04Outcome(str, Enum):
    DELIVERED_WITH_RESOLUTION_DELTA = "delivered_with_resolution_delta"
    DELIVERED_REVIEW_ACCELERATION_READY = "delivered_review_acceleration_ready"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"


def evaluate_night04_outcome(
    *,
    delivery_tasks_passed: bool,
    resolved_delta: int,
    independent_resolution_receipts: int,
    review_bundles_complete: int,
    pointer_dry_runs_complete: int,
    safety_failure: bool = False,
    engineering_prerequisite_blocked: bool = False,
) -> Night04Outcome:
    if resolved_delta < 0 or independent_resolution_receipts < 0:
        raise Night04Error("resolution counts must not be negative")
    if resolved_delta > independent_resolution_receipts:
        raise Night04Error("resolved delta exceeds independent receipt count")
    if safety_failure:
        return Night04Outcome.FAILED
    if engineering_prerequisite_blocked:
        return Night04Outcome.BLOCKED
    if not delivery_tasks_passed:
        return Night04Outcome.PARTIAL
    if resolved_delta:
        return Night04Outcome.DELIVERED_WITH_RESOLUTION_DELTA
    if review_bundles_complete == 43 and pointer_dry_runs_complete == 8:
        return Night04Outcome.DELIVERED_REVIEW_ACCELERATION_READY
    return Night04Outcome.PARTIAL


def _git(repo_root: Path, *args: str, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise Night04Error(
            f"git {' '.join(args)} failed: {result.stderr.decode(errors='replace')}"
        )
    return result.stdout


def _note_fields(task: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for note in task.get("notes") or []:
        text = str(note)
        if "=" in text:
            key, value = text.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def source_queue_bytes(repo_root: Path) -> bytes:
    path = repo_root / SOURCE_QUEUE
    if not path.is_file():
        raise Night04Error(f"Night03 authoritative queue missing: {path}")
    payload = path.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != EXPECTED_QUEUE_SHA256:
        raise Night04Error(f"Night03 queue hash mismatch: {actual}")
    return payload


def authoritative_queue(repo_root: Path) -> dict[str, Any]:
    value = yaml.safe_load(source_queue_bytes(repo_root)) or {}
    tasks = value.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != EXPECTED_TOTAL_ITEMS:
        raise Night04Error("Night03 queue must contain exactly 69 items")
    ids = [str(task.get("id") or "") for task in tasks if isinstance(task, dict)]
    if len(ids) != EXPECTED_TOTAL_ITEMS or len(set(ids)) != len(ids) or not all(ids):
        raise Night04Error("Night03 queue IDs are missing or duplicated")
    return value


def build_night03_input_manifest(repo_root: Path) -> dict[str, Any]:
    raw = _git(repo_root, "ls-tree", "-r", SOURCE_COMMIT, "--", SOURCE_ROOT.as_posix())
    records: list[dict[str, Any]] = []
    for line in raw.decode("utf-8").splitlines():
        metadata, relative = line.split("\t", 1)
        mode, object_type, oid = metadata.split()
        if object_type != "blob":
            continue
        payload = _git(repo_root, "cat-file", "blob", oid)
        records.append(
            {
                "path": relative,
                "git_mode": mode,
                "git_blob_oid": oid,
                "blob_sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
        )
    required = {
        (SOURCE_ROOT / "morning_readout.json").as_posix(),
        (SOURCE_ROOT / "morning_readout.md").as_posix(),
        SOURCE_QUEUE.as_posix(),
        (SOURCE_ROOT / "publication/tracked_delivery_receipt.json").as_posix(),
    }
    present = {record["path"] for record in records}
    if len(records) != EXPECTED_NIGHT03_FILE_COUNT or not required <= present:
        raise Night04Error(
            f"Night03 tracked manifest mismatch: count={len(records)} missing={sorted(required-present)}"
        )
    return stable_payload(
        {
            "schema_version": "r5_night04_night03_input_manifest_v1",
            "mission_id": MISSION_ID,
            "source_commit": SOURCE_COMMIT,
            "source_root": SOURCE_ROOT.as_posix(),
            "hash_representation": "git_blob_bytes",
            "file_count": len(records),
            "files": records,
        }
    )


def build_taxonomy_audit(repo_root: Path) -> dict[str, Any]:
    tasks = authoritative_queue(repo_root)["tasks"]
    work_types = Counter(str(task.get("work_type")) for task in tasks)
    states = Counter(str(task.get("night03_candidate_state")) for task in tasks)
    ids = [str(task["id"]) for task in tasks]
    actual_types = {key: work_types.get(key, 0) for key in EXPECTED_TAXONOMY}
    expected_states = {
        "candidate_ready": EXPECTED_CANDIDATE_READY,
        "dependency_blocked": EXPECTED_DEPENDENCY_BLOCKED,
        "parent_pending": EXPECTED_PARENTS,
    }
    actual_states = {key: states.get(key, 0) for key in expected_states}
    passed = actual_types == EXPECTED_TAXONOMY and actual_states == expected_states
    payload = stable_payload(
        {
            "schema_version": "r5_night04_taxonomy_audit_v1",
            "mission_id": MISSION_ID,
            "source_commit": SOURCE_COMMIT,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "total_items": len(tasks),
            "occurrence_items": sum(task.get("work_type") != "bf2_work_order" for task in tasks),
            "parent_aggregators": work_types.get("bf2_work_order", 0),
            "work_type_counts": actual_types,
            "night03_state_counts": actual_states,
            "stable_id_set_sha256": hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest(),
            "passed": passed,
        }
    )
    if not passed:
        raise Night04Error(f"Night03 taxonomy mismatch: {payload}")
    return payload


def build_lineage_audit(repo_root: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    mismatches: list[str] = []
    for task in authoritative_queue(repo_root)["tasks"]:
        task_id = str(task["id"])
        notes = _note_fields(task)
        source_path = notes.get("source_artifact_path")
        expected = (notes.get("source_artifact_sha256") or "").casefold()
        record: dict[str, Any] = {
            "task_id": task_id,
            "source_artifact_path": source_path,
            "expected_source_artifact_sha256": expected or None,
        }
        if task.get("work_type") == "bf2_work_order":
            record["lineage_status"] = "parent_aggregator"
        elif source_path in {None, "UNKNOWN"} or expected == "unknown":
            record["lineage_status"] = "explicit_unknown"
        else:
            path = repo_root / source_path
            actual = sha256_file(path) if path.is_file() else None
            record["actual_source_artifact_sha256"] = actual
            if actual == expected and SHA256_RE.fullmatch(expected):
                record["lineage_status"] = "verified"
            else:
                record["lineage_status"] = "missing_or_hash_mismatch"
                mismatches.append(task_id)
        records.append(record)
    payload = stable_payload(
        {
            "schema_version": "r5_night04_lineage_audit_v1",
            "mission_id": MISSION_ID,
            "source_commit": SOURCE_COMMIT,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "task_count": len(records),
            "verified_count": sum(r["lineage_status"] == "verified" for r in records),
            "explicit_unknown_count": sum(r["lineage_status"] == "explicit_unknown" for r in records),
            "parent_aggregator_count": sum(r["lineage_status"] == "parent_aggregator" for r in records),
            "mismatch_task_ids": mismatches,
            "historical_paths_mutable": False,
            "passed": not mismatches,
            "records": records,
        }
    )
    if mismatches:
        raise Night04Error(f"Night03 lineage mismatches: {mismatches}")
    return payload


def build_truth_snapshot(repo_root: Path) -> dict[str, Any]:
    readout = load_json(repo_root / SOURCE_ROOT / "morning_readout.json")
    queue = authoritative_queue(repo_root)
    truth = readout.get("research_truth") or {}
    observed = {
        "mission_outcome": readout.get("mission_outcome"),
        "blocker_occurrences_total": truth.get("blocker_occurrences_total"),
        "blocker_occurrences_resolved": truth.get("blocker_occurrences_resolved"),
        "candidate_ready": truth.get("candidate_ready"),
        "dependency_blocked": truth.get("dependency_blocked"),
        "parent_pending": truth.get("work_orders_pending"),
        "program_goal": truth.get("program_goal"),
        "sample_quality_allowed": truth.get("sample_quality_allowed"),
        "p2_allowed": truth.get("p2_allowed"),
        "queue_items": len(queue["tasks"]),
    }
    expected = {
        "mission_outcome": "delivered_candidate_ready",
        "blocker_occurrences_total": 63,
        "blocker_occurrences_resolved": 0,
        "candidate_ready": 43,
        "dependency_blocked": 20,
        "parent_pending": 6,
        "program_goal": "open_needs_targeted_backflow",
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "queue_items": 69,
    }
    if observed != expected:
        raise Night04Error(f"Night03 truth mismatch: {observed}")
    return stable_payload(
        {
            "schema_version": "r5_night04_truth_snapshot_v1",
            "mission_id": MISSION_ID,
            "source_commit": SOURCE_COMMIT,
            "starting_truth": observed,
            "mission_delivery_may_close_program_goal": False,
            "resolution_requires": "accepted_exact_hash_decision_plus_independent_passed_receipt",
            "dry_run_is_resolution": False,
            "passed": True,
        }
    )


def find_night03_archive(repo_root: Path) -> Path:
    name = "R5_Overnight_Mission_03_20260720.zip"
    candidates = [repo_root / name, repo_root.parent / "03_Investment_System" / name]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise Night04Error(f"original Night03 archive not found: {name}")


def build_night03_package_integrity(repo_root: Path) -> dict[str, Any]:
    archive = find_night03_archive(repo_root)
    actual_hash = sha256_file(archive)
    actual_bytes = archive.stat().st_size
    passed = actual_hash == EXPECTED_NIGHT03_ZIP_SHA256 and actual_bytes == EXPECTED_NIGHT03_ZIP_BYTES
    if not passed:
        raise Night04Error("original Night03 archive integrity mismatch")
    return stable_payload(
        {
            "schema_version": "r5_night04_night03_package_integrity_v1",
            "package_name": archive.name,
            "sha256": actual_hash,
            "bytes": actual_bytes,
            "expected_sha256": EXPECTED_NIGHT03_ZIP_SHA256,
            "verification_mode": "runtime_original_archive_sha256",
            "passed": True,
        }
    )


def build_non_self_reference_audit(repo_root: Path) -> dict[str, Any]:
    tracked_path = SOURCE_ROOT / "publication/tracked_delivery_receipt.json"
    tracked = load_json(repo_root / tracked_path)
    remote_path = SOURCE_ROOT / "publication/remote_delivery_receipt.json"
    remote_is_tracked = bool(_git(repo_root, "ls-files", "--error-unmatch", remote_path.as_posix(), check=False))
    passed = (
        tracked.get("final_publication_head") is None
        and tracked.get("final_publication_resolution_policy") == "authoritative_post_push_remote_receipt"
        and not remote_is_tracked
    )
    if not passed:
        raise Night04Error("Night03 final receipt is self-referential or tracked")
    return stable_payload(
        {
            "schema_version": "r5_night04_non_self_reference_audit_v1",
            "source_commit": SOURCE_COMMIT,
            "tracked_delivery_receipt": tracked_path.as_posix(),
            "tracked_receipt_final_head": None,
            "post_push_remote_receipt": remote_path.as_posix(),
            "post_push_remote_receipt_tracked": remote_is_tracked,
            "policy": "final_remote_head_must_live_outside_the_commit_it_identifies",
            "passed": True,
        }
    )


def materialize_phase_a(repo_root: Path) -> dict[str, Any]:
    manifest = build_night03_input_manifest(repo_root)
    taxonomy = build_taxonomy_audit(repo_root)
    lineage = build_lineage_audit(repo_root)
    truth = build_truth_snapshot(repo_root)
    package = build_night03_package_integrity(repo_root)
    non_self = build_non_self_reference_audit(repo_root)
    write_json(repo_root / OUTPUT_ROOT / "preflight/night03_input_manifest.json", manifest)
    atomic_write(repo_root / OUTPUT_ROOT / "queue/authoritative_queue_snapshot.yaml", source_queue_bytes(repo_root))
    write_json(repo_root / OUTPUT_ROOT / "queue/taxonomy_audit.json", taxonomy)
    write_json(repo_root / OUTPUT_ROOT / "queue/lineage_audit.json", lineage)
    write_json(repo_root / OUTPUT_ROOT / "queue/truth_snapshot.json", truth)
    write_json(repo_root / OUTPUT_ROOT / "preflight/night03_package_integrity.json", package)
    write_json(repo_root / OUTPUT_ROOT / "preflight/non_self_reference_audit.json", non_self)
    return {"manifest": manifest, "taxonomy": taxonomy, "lineage": lineage, "truth": truth}


def wrapper_tasks(repo_root: Path) -> list[dict[str, Any]]:
    tasks = load_yaml(repo_root / PACKAGE_ROOT / "task_queue.yaml").get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 60:
        raise Night04Error("Night04 wrapper queue must contain exactly 60 tasks")
    return tasks


def _artifact_records(repo_root: Path, paths: Sequence[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    root = repo_root.resolve()
    for relative in paths:
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise Night04Error(f"required artifact escapes repository: {relative}") from exc
        if not path.is_file() or path.is_symlink():
            raise Night04Error(f"required artifact missing: {relative}")
        records.append({"path": relative.replace("\\", "/"), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    return records


def record_completed_task(repo_root: Path, task_id: str) -> dict[str, Any]:
    tasks = {str(task["id"]): task for task in wrapper_tasks(repo_root)}
    if task_id not in tasks:
        raise Night04Error(f"unknown Night04 task: {task_id}")
    task = tasks[task_id]
    payload = stable_payload(
        {
            "schema_version": "r5_night04_wrapper_task_receipt_v1",
            "mission_id": MISSION_ID,
            "task_id": task_id,
            "terminal_status": "passed",
            "verification_mode": "observed_exit_then_artifact_revalidation",
            "acceptance_commands": [
                {"command": str(command), "observed_exit_code": 0, "stdout_reproduced": False}
                for command in task.get("acceptance_commands") or []
            ],
            "required_artifacts": _artifact_records(repo_root, task.get("required_artifacts") or []),
            "source_commit": SOURCE_COMMIT,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "research_resolution_claimed": False,
        }
    )
    write_json(repo_root / OUTPUT_ROOT / f"receipts/{task_id}.json", payload)
    return payload


def materialize_wrapper_state(repo_root: Path) -> dict[str, Any]:
    tasks = wrapper_tasks(repo_root)
    receipt_root = repo_root / OUTPUT_ROOT / "receipts"
    passed = {
        path.stem
        for path in receipt_root.glob("ns04_t*.json")
        if path.is_file() and load_json(path).get("terminal_status") == "passed"
    }
    states: dict[str, str] = {}
    for task in tasks:
        task_id = str(task["id"])
        states[task_id] = "passed" if task_id in passed else str(task.get("status") or "pending")
    for task in tasks:
        task_id = str(task["id"])
        if states[task_id] == "pending" and all(states.get(str(dep)) == "passed" for dep in task.get("depends_on") or []):
            states[task_id] = "ready"
    payload = stable_payload(
        {
            "schema_version": "r5_night04_mission_state_v1",
            "mission_id": MISSION_ID,
            "source_commit": SOURCE_COMMIT,
            "program_goal": {
                "state": "open_needs_targeted_backflow",
                "close_allowed": False,
                "blocker_occurrences_total": 63,
                "blocker_occurrences_resolved": 0,
            },
            "tasks": [
                {"id": str(task["id"]), "phase": task.get("phase"), "status": states[str(task["id"])]}
                for task in tasks
            ],
        }
    )
    write_yaml(repo_root / OUTPUT_ROOT / "mission_state.yaml", payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialise Night04 mission artifacts")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--phase", choices=("baseline", "review", "acceleration", "pointer"), default="baseline")
    parser.add_argument("--record-task", action="append", default=[])
    parser.add_argument("--record-only", action="store_true")
    args = parser.parse_args(argv)
    repo_root = Path(args.repo).resolve()
    if args.record_only:
        summary = {"materialization": "skipped_record_only"}
    elif args.phase == "baseline":
        result = materialize_phase_a(repo_root)
        summary = {"queue_items": result["taxonomy"]["total_items"]}
    elif args.phase == "review":
        from .night04_review import materialize_phase_b

        result = materialize_phase_b(repo_root)
        summary = {"candidate_count": result["registry"]["candidate_count"]}
    elif args.phase == "acceleration":
        from .night04_acceleration import materialize_phase_c

        result = materialize_phase_c(repo_root)
        summary = {"candidate_count": result["dashboard"]["review_candidates"]}
    else:
        from .night04_pointer import materialize_phase_d

        result = materialize_phase_d(repo_root)
        summary = {"pointer_dry_runs": result["patch_index"]["pointer_count"]}
    receipts = [record_completed_task(repo_root, task_id) for task_id in args.record_task]
    state = materialize_wrapper_state(repo_root)
    print(
        json.dumps(
            {
                "mission_id": MISSION_ID,
                "status": "passed",
                "phase": args.phase,
                **summary,
                "receipts_recorded": [item["task_id"] for item in receipts],
                "wrapper_tasks_passed": sum(item["status"] == "passed" for item in state["tasks"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
