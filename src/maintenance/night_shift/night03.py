"""Night03 exact-baseline, decision-intake, and targeted-backflow helpers.

The Night03 mission consumes the immutable 69-item queue produced by Night02.
This module keeps the source queue and historical reports read-only while
materialising deterministic Night03 audit artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from .queue import atomic_write
from .receipts import canonical_json_bytes, sha256_bytes


MISSION_ID = "r5_overnight_03_20260721"
SOURCE_COMMIT = "069da527452def6c59c3772750e933d8611ccadf"
SOURCE_ROOT = Path("reports/p1_6/r5_night_shift/r5_overnight_02_20260720")
OUTPUT_ROOT = Path("reports/p1_6/r5_night_shift/r5_overnight_03_20260721")
PACKAGE_ROOT = Path("codex_tasks/night_shift/r5_overnight_03_20260721")
SOURCE_QUEUE = SOURCE_ROOT / "next_night_queue.yaml"
EXPECTED_QUEUE_SHA256 = "dc2d6d6bb91b7ff326d3985d96f8eb8956a43710c61230eb06e6144e490e8ea1"
EXPECTED_TOTAL_ITEMS = 69
EXPECTED_OCCURRENCES = 63
EXPECTED_PARENTS = 6
EXPECTED_NIGHT02_FILE_COUNT = 78
EXPECTED_TAXONOMY = {
    "engineering_local_pointer": 8,
    "evidence_required": 8,
    "analysis_required": 24,
    "dependency_blocked": 20,
    "human_exact_hash_gate": 3,
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class Night03Error(RuntimeError):
    """Raised when a Night03 truth or lineage gate fails closed."""


class Night03Outcome(str, Enum):
    DELIVERED_WITH_RESOLUTION_DELTA = "delivered_with_resolution_delta"
    DELIVERED_CANDIDATE_READY = "delivered_candidate_ready"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"
    CUTOFF = "cutoff"


def evaluate_night03_outcome(
    *,
    delivery_tasks_passed: bool,
    resolved_delta: int,
    candidate_packets_complete: bool,
    safety_failure: bool = False,
    cutoff_reached: bool = False,
    engineering_prerequisite_blocked: bool = False,
) -> Night03Outcome:
    """Evaluate Mission delivery without changing the long-term research goal."""

    if resolved_delta < 0:
        raise Night03Error("resolved_delta must not be negative")
    if safety_failure:
        return Night03Outcome.FAILED
    if engineering_prerequisite_blocked:
        return Night03Outcome.BLOCKED
    if cutoff_reached and not delivery_tasks_passed:
        return Night03Outcome.CUTOFF
    if not delivery_tasks_passed:
        return Night03Outcome.PARTIAL
    if resolved_delta > 0:
        return Night03Outcome.DELIVERED_WITH_RESOLUTION_DELTA
    if candidate_packets_complete:
        return Night03Outcome.DELIVERED_CANDIDATE_READY
    return Night03Outcome.PARTIAL


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise Night03Error(f"YAML root must be a mapping: {path}")
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Night03Error(f"JSON root must be a mapping: {path}")
    return value


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    atomic_write(
        path,
        (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
            "utf-8"
        ),
    )


def write_yaml(path: Path, value: Mapping[str, Any]) -> None:
    atomic_write(
        path,
        yaml.safe_dump(
            dict(value),
            allow_unicode=True,
            sort_keys=False,
            width=120,
        ).encode("utf-8"),
    )


def stable_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(value)
    payload["stable_receipt_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def source_queue_bytes(repo_root: Path) -> bytes:
    path = repo_root / SOURCE_QUEUE
    if not path.is_file():
        raise Night03Error(f"authoritative Night02 queue missing: {path}")
    payload = path.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != EXPECTED_QUEUE_SHA256:
        raise Night03Error(
            f"authoritative queue hash mismatch: {actual} != {EXPECTED_QUEUE_SHA256}"
        )
    return payload


def authoritative_queue(repo_root: Path) -> dict[str, Any]:
    payload = yaml.safe_load(source_queue_bytes(repo_root)) or {}
    if not isinstance(payload, dict):
        raise Night03Error("authoritative queue root must be a mapping")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != EXPECTED_TOTAL_ITEMS:
        raise Night03Error(
            f"authoritative queue must contain {EXPECTED_TOTAL_ITEMS} tasks"
        )
    ids = [str(task.get("id") or "") for task in tasks if isinstance(task, dict)]
    if len(ids) != EXPECTED_TOTAL_ITEMS or len(ids) != len(set(ids)) or not all(ids):
        raise Night03Error("authoritative queue IDs are missing or duplicated")
    return payload


def _note_fields(task: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for note in task.get("notes") or []:
        text = str(note)
        if "=" in text:
            key, value = text.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def _taxonomy_key(task: Mapping[str, Any]) -> str | None:
    work_type = str(task.get("work_type") or "")
    return {
        "engineering_local": "engineering_local_pointer",
        "evidence_required": "evidence_required",
        "analysis_required": "analysis_required",
        "dependency_blocked": "dependency_blocked",
        "human_gate": "human_exact_hash_gate",
    }.get(work_type)


def build_night02_input_manifest(repo_root: Path) -> dict[str, Any]:
    root = repo_root / SOURCE_ROOT
    if not root.is_dir():
        raise Night03Error(f"Night02 output root missing: {root}")
    records: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(repo_root).as_posix()
        records.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    required = {
        (SOURCE_ROOT / "mission_completion_receipt.json").as_posix(),
        (SOURCE_ROOT / "morning_readout.md").as_posix(),
        (SOURCE_ROOT / "morning_readout.json").as_posix(),
        SOURCE_QUEUE.as_posix(),
        (SOURCE_ROOT / "receipts/ns02_t46_commit_push_remote_ci.json").as_posix(),
    }
    present = {record["path"] for record in records}
    missing = sorted(required - present)
    if missing:
        raise Night03Error(f"required Night02 tracked artifacts missing: {missing}")
    if len(records) != EXPECTED_NIGHT02_FILE_COUNT:
        raise Night03Error(
            "Night02 physical artifact count mismatch: "
            f"{len(records)} != {EXPECTED_NIGHT02_FILE_COUNT}"
        )
    return stable_payload(
        {
            "schema_version": "r5_night03_input_manifest_v1",
            "mission_id": MISSION_ID,
            "source_commit": SOURCE_COMMIT,
            "source_root": SOURCE_ROOT.as_posix(),
            "file_count": len(records),
            "files": records,
        }
    )


def build_authoritative_queue_lock(repo_root: Path) -> dict[str, Any]:
    raw = source_queue_bytes(repo_root)
    queue = authoritative_queue(repo_root)
    tasks = queue["tasks"]
    ids = [str(task["id"]) for task in tasks]
    return stable_payload(
        {
            "schema_version": "r5_night03_authoritative_queue_lock_v1",
            "mission_id": MISSION_ID,
            "source_commit": SOURCE_COMMIT,
            "source_path": SOURCE_QUEUE.as_posix(),
            "source_queue_sha256": hashlib.sha256(raw).hexdigest(),
            "source_queue_bytes": len(raw),
            "task_count": len(tasks),
            "task_ids_sha256": hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest(),
            "import_mode": "read_only_exact_hash",
        }
    )


def build_taxonomy_audit(repo_root: Path) -> dict[str, Any]:
    tasks = authoritative_queue(repo_root)["tasks"]
    occurrences = [task for task in tasks if task.get("work_type") != "bf2_work_order"]
    parents = [task for task in tasks if task.get("work_type") == "bf2_work_order"]
    counts = Counter(
        key for task in occurrences if (key := _taxonomy_key(task)) is not None
    )
    actual = {key: counts.get(key, 0) for key in EXPECTED_TAXONOMY}
    unknown = sorted(
        str(task.get("id")) for task in occurrences if _taxonomy_key(task) is None
    )
    passed = (
        len(tasks) == EXPECTED_TOTAL_ITEMS
        and len(occurrences) == EXPECTED_OCCURRENCES
        and len(parents) == EXPECTED_PARENTS
        and actual == EXPECTED_TAXONOMY
        and not unknown
    )
    payload = stable_payload(
        {
            "schema_version": "r5_night03_taxonomy_audit_v1",
            "mission_id": MISSION_ID,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "total_items": len(tasks),
            "occurrence_items": len(occurrences),
            "parent_aggregators": len(parents),
            "occurrence_taxonomy": actual,
            "unknown_occurrence_ids": unknown,
            "passed": passed,
        }
    )
    if not passed:
        raise Night03Error(f"Night02 queue taxonomy mismatch: {payload}")
    return payload


def taxonomy_markdown(audit: Mapping[str, Any]) -> str:
    lines = [
        "# Night03 Queue Taxonomy Audit",
        "",
        f"- Total items: `{audit['total_items']}`",
        f"- Occurrences: `{audit['occurrence_items']}`",
        f"- Parent aggregators: `{audit['parent_aggregators']}`",
        f"- Passed: `{str(audit['passed']).lower()}`",
        "",
        "| taxonomy | count |",
        "|---|---:|",
    ]
    for key, value in audit["occurrence_taxonomy"].items():
        lines.append(f"| `{key}` | {value} |")
    return "\n".join(lines) + "\n"


def build_lineage_audit(repo_root: Path) -> dict[str, Any]:
    tasks = authoritative_queue(repo_root)["tasks"]
    records: list[dict[str, Any]] = []
    mismatches: list[str] = []
    explicit_unknown: list[str] = []
    for task in tasks:
        task_id = str(task["id"])
        notes = _note_fields(task)
        source_path = notes.get("source_artifact_path")
        expected_hash = (notes.get("source_artifact_sha256") or "").casefold()
        record: dict[str, Any] = {
            "task_id": task_id,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "source_commit": SOURCE_COMMIT,
            "source_artifact_path": source_path,
            "expected_source_artifact_sha256": expected_hash or None,
        }
        if not source_path:
            record["lineage_status"] = "parent_aggregator"
        elif source_path == "UNKNOWN" or expected_hash == "unknown":
            record["lineage_status"] = "explicit_unknown"
            explicit_unknown.append(task_id)
        else:
            path = repo_root / source_path
            actual = sha256_file(path) if path.is_file() else None
            record["actual_source_artifact_sha256"] = actual
            if actual is None:
                record["lineage_status"] = "missing"
                mismatches.append(task_id)
            elif not SHA256_RE.fullmatch(expected_hash) or actual != expected_hash:
                record["lineage_status"] = "hash_mismatch"
                mismatches.append(task_id)
            else:
                record["lineage_status"] = "verified"
        records.append(record)
    payload = stable_payload(
        {
            "schema_version": "r5_night03_lineage_audit_v1",
            "mission_id": MISSION_ID,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "source_commit": SOURCE_COMMIT,
            "task_count": len(records),
            "verified_count": sum(r["lineage_status"] == "verified" for r in records),
            "parent_aggregator_count": sum(
                r["lineage_status"] == "parent_aggregator" for r in records
            ),
            "explicit_unknown_count": len(explicit_unknown),
            "explicit_unknown_task_ids": explicit_unknown,
            "mismatch_task_ids": mismatches,
            "stale_decision_policy": "invalidate_on_any_bound_hash_change",
            "records": records,
            "passed": not mismatches,
        }
    )
    if mismatches:
        raise Night03Error(f"Night02 lineage mismatches: {mismatches}")
    return payload


def build_truth_snapshot(repo_root: Path) -> dict[str, Any]:
    receipt = load_json(repo_root / SOURCE_ROOT / "mission_completion_receipt.json")
    queue = authoritative_queue(repo_root)
    receipt_goal = receipt.get("program_goal") or {}
    queue_goal = queue.get("program_goal") or {}
    truth = {
        "work_orders_pending": receipt_goal.get("work_orders_pending"),
        "blocker_occurrences_total": receipt_goal.get("blocker_occurrences_total"),
        "blocker_occurrences_resolved": receipt_goal.get("blocker_occurrences_resolved"),
        "goal_state": receipt_goal.get("state"),
        "goal_close_allowed": queue_goal.get("close_allowed"),
        "sample_quality_allowed": receipt.get("sample_quality_allowed"),
        "p2_allowed": receipt.get("p2_allowed"),
    }
    expected = {
        "work_orders_pending": 6,
        "blocker_occurrences_total": 63,
        "blocker_occurrences_resolved": 0,
        "goal_state": "open_needs_targeted_backflow",
        "goal_close_allowed": False,
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    passed = truth == expected
    payload = stable_payload(
        {
            "schema_version": "r5_night03_truth_snapshot_v1",
            "mission_id": MISSION_ID,
            "source_commit": SOURCE_COMMIT,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "starting_truth": truth,
            "allowed_delivery_outcomes": [
                "delivered_with_resolution_delta",
                "delivered_candidate_ready",
                "partial",
                "blocked",
                "failed",
                "cutoff",
            ],
            "mission_delivery_may_close_program_goal": False,
            "passed": passed,
        }
    )
    if not passed:
        raise Night03Error(f"Night03 starting truth mismatch: {truth} != {expected}")
    return payload


def materialize_phase_a(repo_root: Path) -> dict[str, Any]:
    output = repo_root / OUTPUT_ROOT
    manifest = build_night02_input_manifest(repo_root)
    queue_lock = build_authoritative_queue_lock(repo_root)
    taxonomy = build_taxonomy_audit(repo_root)
    lineage = build_lineage_audit(repo_root)
    truth = build_truth_snapshot(repo_root)

    write_json(output / "preflight/night02_input_manifest.json", manifest)
    atomic_write(
        output / "queue/authoritative_queue_snapshot.yaml",
        source_queue_bytes(repo_root),
    )
    write_json(output / "queue/authoritative_queue_lock.json", queue_lock)
    write_json(output / "queue/taxonomy_audit.json", taxonomy)
    atomic_write(
        output / "queue/taxonomy_audit.md",
        taxonomy_markdown(taxonomy).encode("utf-8"),
    )
    write_json(output / "queue/lineage_audit.json", lineage)
    write_json(output / "queue/truth_snapshot.json", truth)
    return {
        "manifest": manifest,
        "queue_lock": queue_lock,
        "taxonomy": taxonomy,
        "lineage": lineage,
        "truth": truth,
    }


def _artifact_records(repo_root: Path, paths: Sequence[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    root = repo_root.resolve()
    for relative in paths:
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise Night03Error(f"required artifact escapes repository: {relative}") from exc
        if not path.is_file() or path.is_symlink():
            raise Night03Error(f"required artifact missing for receipt: {relative}")
        records.append(
            {
                "path": str(relative).replace("\\", "/"),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return records


def wrapper_tasks(repo_root: Path) -> list[dict[str, Any]]:
    queue = load_yaml(repo_root / PACKAGE_ROOT / "task_queue.yaml")
    tasks = queue.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 40:
        raise Night03Error("Night03 wrapper queue must contain exactly 40 tasks")
    return tasks


def record_completed_task(repo_root: Path, task_id: str) -> dict[str, Any]:
    """Record an already-observed successful acceptance deterministically.

    The operator runs the package command first.  This function then rechecks
    every required artifact and records the observed zero exit status without
    inventing stdout, timestamps, reviewer identity, or blocker resolution.
    """

    tasks = {str(task["id"]): task for task in wrapper_tasks(repo_root)}
    if task_id not in tasks:
        raise Night03Error(f"unknown Night03 wrapper task: {task_id}")
    task = tasks[task_id]
    artifacts = _artifact_records(repo_root, task.get("required_artifacts") or [])
    payload = stable_payload(
        {
            "schema_version": "r5_night03_wrapper_task_receipt_v1",
            "mission_id": MISSION_ID,
            "task_id": task_id,
            "terminal_status": "passed",
            "verification_mode": "observed_exit_then_artifact_revalidation",
            "acceptance_commands": [
                {
                    "command": str(command),
                    "observed_exit_code": 0,
                    "stdout_reproduced": False,
                }
                for command in task.get("acceptance_commands") or []
            ],
            "required_artifacts": artifacts,
            "source_commit": SOURCE_COMMIT,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "blocker_occurrences": {
                "resolved": 0,
                "resolution_claimed": False,
            },
        }
    )
    write_json(repo_root / OUTPUT_ROOT / f"receipts/{task_id}.json", payload)
    return payload


def materialize_wrapper_state(repo_root: Path) -> dict[str, Any]:
    tasks = wrapper_tasks(repo_root)
    receipt_root = repo_root / OUTPUT_ROOT / "receipts"
    passed = {
        path.stem
        for path in receipt_root.glob("ns03_t*.json")
        if path.is_file()
        and load_json(path).get("terminal_status") == "passed"
    }
    states: dict[str, str] = {}
    for task in tasks:
        task_id = str(task["id"])
        states[task_id] = "passed" if task_id in passed else str(task.get("status") or "pending")
    changed = True
    while changed:
        changed = False
        for task in tasks:
            task_id = str(task["id"])
            if states[task_id] not in {"pending", "ready"}:
                continue
            dependencies = [str(item) for item in task.get("depends_on") or []]
            desired = "ready" if all(states.get(dep) == "passed" for dep in dependencies) else "pending"
            if states[task_id] != desired:
                states[task_id] = desired
                changed = True
    payload = stable_payload(
        {
            "schema_version": "r5_night03_mission_state_v1",
            "mission_id": MISSION_ID,
            "source_commit": SOURCE_COMMIT,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "program_goal": {
                "state": "open_needs_targeted_backflow",
                "close_allowed": False,
                "blocker_occurrences_total": 63,
                "blocker_occurrences_resolved": 0,
            },
            "tasks": [
                {
                    "id": str(task["id"]),
                    "phase": task.get("phase"),
                    "delivery_required": bool(task.get("delivery_required")),
                    "status": states[str(task["id"])],
                }
                for task in tasks
            ],
        }
    )
    write_yaml(repo_root / OUTPUT_ROOT / "mission_state.yaml", payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialise deterministic Night03 artifacts")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--phase", choices=("baseline", "decisions"), default="baseline")
    parser.add_argument("--record-task", action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo).resolve()
    if args.phase == "baseline":
        result = materialize_phase_a(repo_root)
        phase_summary = {
            "task_count": result["queue_lock"]["task_count"],
            "lineage_verified": result["lineage"]["verified_count"],
            "explicit_unknown": result["lineage"]["explicit_unknown_count"],
        }
    else:
        from .night03_decisions import materialize_decision_contracts

        result = materialize_decision_contracts(repo_root)
        phase_summary = {
            "decision_kinds": len(result["authority"]["decision_authorities"]),
            "resolution_requires_independent_receipt": True,
        }
    receipts = [record_completed_task(repo_root, task_id) for task_id in args.record_task]
    state = materialize_wrapper_state(repo_root)
    print(
        json.dumps(
            {
                "mission_id": MISSION_ID,
                "phase": args.phase,
                "status": "passed",
                **phase_summary,
                "receipts_recorded": [item["task_id"] for item in receipts],
                "wrapper_tasks_passed": sum(
                    item["status"] == "passed" for item in state["tasks"]
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
