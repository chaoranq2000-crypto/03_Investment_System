"""Night04 external-decision intake, typed execution, and truth recomputation.

The production path is intentionally fail closed.  A review decision is usable
only when it is present in the external inbox, matches the immutable Night04
registry, and its reviewer authority is confirmed by a separate external
registry.  Even an approved decision is not resolution: an independent passed
execution receipt with matching lineage and decision digest is also required.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import yaml

from .night03 import load_json, load_yaml, sha256_file, stable_payload, write_json, write_yaml
from .night03_backflow import blocker_id
from .night03_decisions import resolution_eligibility
from .night03_execution import aggregate_parent, dependency_unlock, validate_dependency_graph
from .night04 import (
    EXPECTED_DEPENDENCY_BLOCKED,
    EXPECTED_OCCURRENCES,
    EXPECTED_PARENTS,
    EXPECTED_QUEUE_SHA256,
    MISSION_ID,
    OUTPUT_ROOT,
    TARGET_BRANCH,
    Night04Error,
    _note_fields,
    authoritative_queue,
)
from .night04_review import apply_replay_guard, validate_decision_batch
from .queue import atomic_write
from .receipts import canonical_json_bytes, sha256_bytes


AUTHORITY_REGISTRY_NAME = "external_authority_registry.yaml"
AUTHORITY_REGISTRY_SCHEMA = "r5_night04_external_authority_registry_v1"
DECISION_LEDGER = OUTPUT_ROOT / "execution/decision_replay_ledger.json"
RESOLUTION_RECEIPT_ROOT = OUTPUT_ROOT / "execution/resolution_receipts"
ADAPTER_KIND_TO_FILE = {
    "evidence_required": "evidence_execution_receipts.json",
    "analysis_required": "analysis_execution_receipts.json",
    "human_exact_hash_gate": "human_gate_receipts.json",
    "engineering_local_pointer": "pointer_execution_receipts.json",
}


class Night04ExecutionError(Night04Error):
    """Raised when conditional execution would cross an external gate."""


def _read_structured(path: Path) -> dict[str, Any]:
    try:
        value = (
            json.loads(path.read_text(encoding="utf-8"))
            if path.suffix.casefold() == ".json"
            else yaml.safe_load(path.read_text(encoding="utf-8"))
        )
    except (OSError, UnicodeError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise Night04ExecutionError(f"cannot read external input {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise Night04ExecutionError(f"external input must be a mapping: {path}")
    return value


def load_external_authorities(
    repo_root: Path,
) -> tuple[set[tuple[str, str]], dict[str, Any]]:
    """Load the separate, externally supplied reviewer-authority registry."""

    path = repo_root / OUTPUT_ROOT / "external_decisions" / AUTHORITY_REGISTRY_NAME
    if not path.is_file():
        return set(), {
            "path": path.relative_to(repo_root).as_posix(),
            "status": "missing_external_registry",
            "reviewer_count": 0,
            "authority_binding_count": 0,
            "sha256": None,
        }
    if path.is_symlink():
        raise Night04ExecutionError("external authority registry must not be a symlink")
    value = _read_structured(path)
    if value.get("schema_version") != AUTHORITY_REGISTRY_SCHEMA:
        raise Night04ExecutionError("external authority registry schema mismatch")
    reviewers = value.get("reviewers")
    if not isinstance(reviewers, list):
        raise Night04ExecutionError("external authority registry reviewers must be a list")
    bindings: set[tuple[str, str]] = set()
    names: set[str] = set()
    for item in reviewers:
        if not isinstance(item, dict):
            raise Night04ExecutionError("external authority registry entry must be a mapping")
        reviewer = str(item.get("reviewer") or "").strip()
        authorities = item.get("authorities")
        if not reviewer or not isinstance(authorities, list) or not authorities:
            raise Night04ExecutionError("external authority registry entry is incomplete")
        names.add(reviewer)
        bindings.update((reviewer, str(authority).strip()) for authority in authorities if str(authority).strip())
    return bindings, {
        "path": path.relative_to(repo_root).as_posix(),
        "status": "verified_external_registry",
        "reviewer_count": len(names),
        "authority_binding_count": len(bindings),
        "sha256": sha256_file(path),
    }


def _decision_files(repo_root: Path) -> list[Path]:
    root = repo_root / OUTPUT_ROOT / "external_decisions"
    if not root.is_dir():
        return []
    return sorted(
        path
        for path in root.iterdir()
        if path.is_file()
        and not path.is_symlink()
        and path.name != AUTHORITY_REGISTRY_NAME
        and path.suffix.casefold() in {".json", ".yaml", ".yml"}
    )


def _existing_decision_ledger(repo_root: Path) -> dict[str, Any]:
    path = repo_root / DECISION_LEDGER
    if not path.is_file():
        return {"records": []}
    value = load_json(path)
    records = value.get("records")
    if not isinstance(records, list):
        raise Night04ExecutionError("decision replay ledger records must be a list")
    supplied = str(value.get("stable_receipt_sha256") or "")
    projection = {key: child for key, child in value.items() if key != "stable_receipt_sha256"}
    if supplied != sha256_bytes(canonical_json_bytes(projection)):
        raise Night04ExecutionError("decision replay ledger hash mismatch")
    return value


def consume_external_decisions(
    repo_root: Path,
    *,
    checkpoint: str,
    continue_on_external_block: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate the external inbox and update an idempotent decision ledger."""

    if checkpoint not in {"startup", "phase_b", "phase_c", "phase_d", "phase_e"}:
        raise Night04ExecutionError(f"unsupported decision checkpoint: {checkpoint}")
    authorities, authority_receipt = load_external_authorities(repo_root)
    files = _decision_files(repo_root)
    manifest_receipts: list[dict[str, Any]] = []
    accepted_candidates: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    for path in files:
        relative = path.relative_to(repo_root).as_posix()
        try:
            validated = validate_decision_batch(
                repo_root,
                _read_structured(path),
                authority_registry=authorities,
                now=now,
            )
        except Night04Error as exc:
            manifest_receipts.append(
                {
                    "path": relative,
                    "sha256": sha256_file(path),
                    "status": "invalid_manifest",
                    "reason": str(exc),
                    "accepted_count": 0,
                    "invalid_count": 1,
                }
            )
            invalid_records.append({"manifest_path": relative, "reason": str(exc)})
            continue
        manifest_receipts.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "status": "partially_valid" if validated["invalid_count"] else "valid",
                "input_count": validated["input_count"],
                "accepted_count": validated["accepted_count"],
                "invalid_count": validated["invalid_count"],
                "replayed_count": validated["replayed_count"],
            }
        )
        for item in validated["accepted_records"]:
            accepted_candidates.append({**item, "source_manifest_path": relative})
        invalid_records.extend(
            {**item, "manifest_path": relative} for item in validated["invalid_records"]
        )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in accepted_candidates:
        grouped[str(item["occurrence_id"])].append(item)
    conflict_free: list[dict[str, Any]] = []
    cross_manifest_conflicts: list[dict[str, Any]] = []
    for occurrence_id, records in sorted(grouped.items()):
        digests = {str(item["decision_digest_sha256"]) for item in records}
        if len(digests) > 1:
            cross_manifest_conflicts.append(
                {
                    "occurrence_id": occurrence_id,
                    "reason": "cross_manifest_conflict",
                    "decision_digests": sorted(digests),
                    "source_manifest_paths": sorted(str(item["source_manifest_path"]) for item in records),
                }
            )
            continue
        conflict_free.append(records[0])

    previous = _existing_decision_ledger(repo_root)
    previous_records = [dict(item) for item in previous.get("records") or []]
    previous_by_digest = {
        str(item["decision_digest_sha256"]): item for item in previous_records
    }
    replay = apply_replay_guard(conflict_free, set(previous_by_digest))
    for item in replay["new_records"]:
        previous_by_digest[str(item["decision_digest_sha256"])] = item
    ledger_records = sorted(
        previous_by_digest.values(),
        key=lambda item: (str(item["occurrence_id"]), str(item["decision_digest_sha256"])),
    )
    ledger = stable_payload(
        {
            "schema_version": "r5_night04_decision_replay_ledger_v1",
            "mission_id": MISSION_ID,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "records": ledger_records,
        }
    )
    write_json(repo_root / DECISION_LEDGER, ledger)
    approved = [item for item in conflict_free if item.get("decision") == "approve"]
    outcome = (
        "no_external_decisions"
        if not files
        else "validated_decisions_available"
        if conflict_free
        else "external_decisions_rejected"
    )
    payload = stable_payload(
        {
            "schema_version": "r5_night04_external_decision_consumption_v1",
            "mission_id": MISSION_ID,
            "checkpoint": checkpoint,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "authority_registry": authority_receipt,
            "scanned_manifest_count": len(files),
            "manifests": manifest_receipts,
            "validated_decision_count": len(conflict_free),
            "approved_decision_count": len(approved),
            "newly_consumed_count": len(replay["new_records"]),
            "replayed_decision_count": len(replay["replayed_digests"]),
            "invalid_record_count": len(invalid_records) + len(cross_manifest_conflicts),
            "invalid_records": invalid_records,
            "cross_manifest_conflicts": cross_manifest_conflicts,
            "accepted_records": conflict_free,
            "approved_records": approved,
            "resolved_delta": 0,
            "outcome": outcome,
            "continue_on_external_block": continue_on_external_block,
            "external_gate_state": "open" if approved else "blocked_external",
            "machine_generated_decisions": 0,
            "program_goal_state": "open_needs_targeted_backflow",
        }
    )
    write_json(repo_root / OUTPUT_ROOT / f"execution/{checkpoint}_decision_consumption.json", payload)
    if not approved and not continue_on_external_block:
        raise Night04ExecutionError("no approved external decisions are available")
    return payload


def _execution_receipt(
    decision: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> dict[str, Any]:
    tree_sha = str(execution.get("implementation_tree_sha") or "")
    if len(tree_sha) != 40 or any(char not in "0123456789abcdef" for char in tree_sha.casefold()):
        raise Night04ExecutionError("typed executor must report a 40-character implementation tree SHA")
    terminal_status = str(execution.get("terminal_status") or "")
    if terminal_status not in {"passed", "failed"}:
        raise Night04ExecutionError("typed executor terminal_status must be passed or failed")
    return stable_payload(
        {
            "schema_version": "r5_night04_independent_resolution_receipt_v1",
            "mission_id": MISSION_ID,
            "occurrence_id": decision["occurrence_id"],
            "candidate_kind": decision["candidate_kind"],
            "decision_digest_sha256": decision["decision_digest_sha256"],
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "implementation_tree_sha": tree_sha.casefold(),
            "commands": [dict(item) for item in execution.get("commands") or []],
            "outputs": [dict(item) for item in execution.get("outputs") or []],
            "terminal_status": terminal_status,
            "lineage_match": bool(execution.get("lineage_match")),
            "resolution_claim_allowed": bool(execution.get("resolution_claim_allowed")),
            "executor_independent": True,
            "publication_head": None,
        }
    )


def execute_typed_adapter(
    repo_root: Path,
    decisions: Sequence[Mapping[str, Any]],
    *,
    candidate_kind: str,
    executor: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    persist_receipts: bool = False,
) -> dict[str, Any]:
    """Execute one decision kind without treating approval alone as resolution."""

    if candidate_kind not in ADAPTER_KIND_TO_FILE:
        raise Night04ExecutionError(f"unsupported typed adapter: {candidate_kind}")
    approved = [
        dict(item)
        for item in decisions
        if item.get("candidate_kind") == candidate_kind and item.get("decision") == "approve"
    ]
    receipts: list[dict[str, Any]] = []
    pending: list[str] = []
    if executor is None:
        pending = [str(item["occurrence_id"]) for item in approved]
    else:
        for decision in approved:
            execution = dict(executor(decision))
            if candidate_kind == "engineering_local_pointer":
                if not execution.get("sandboxed") or execution.get("target_branch_changed"):
                    raise Night04ExecutionError(
                        "approved pointer execution must remain sandboxed and leave the target branch unchanged"
                    )
            receipt = _execution_receipt(decision, execution)
            receipts.append(receipt)
            if persist_receipts:
                write_json(
                    repo_root / RESOLUTION_RECEIPT_ROOT / f"{decision['occurrence_id']}.json",
                    receipt,
                )
    passed = [item for item in receipts if item["terminal_status"] == "passed"]
    outcome = (
        "blocked_external_no_approved_decisions"
        if not approved
        else "approved_decisions_pending_explicit_executor"
        if pending
        else "typed_execution_complete"
    )
    return stable_payload(
        {
            "schema_version": "r5_night04_typed_execution_receipts_v1",
            "mission_id": MISSION_ID,
            "candidate_kind": candidate_kind,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "approved_input_count": len(approved),
            "executed_count": len(receipts),
            "passed_execution_count": len(passed),
            "pending_explicit_executor_count": len(pending),
            "pending_occurrence_ids": sorted(pending),
            "independent_resolution_receipt_count": len(receipts),
            "resolved_count": 0,
            "outcome": outcome,
            "receipts": sorted(receipts, key=lambda item: str(item["occurrence_id"])),
        }
    )


def _validated_resolution_state(
    repo_root: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    ledger = _existing_decision_ledger(repo_root)
    decisions = {
        str(item["occurrence_id"]): dict(item)
        for item in ledger.get("records") or []
        if item.get("decision") == "approve"
    }
    receipts: dict[str, dict[str, Any]] = {}
    root = repo_root / RESOLUTION_RECEIPT_ROOT
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            receipt = load_json(path)
            supplied = str(receipt.get("stable_receipt_sha256") or "")
            projection = {key: value for key, value in receipt.items() if key != "stable_receipt_sha256"}
            if supplied != sha256_bytes(canonical_json_bytes(projection)):
                raise Night04ExecutionError(f"resolution receipt hash mismatch: {path}")
            occurrence_id = str(receipt.get("occurrence_id") or "")
            if occurrence_id in receipts:
                raise Night04ExecutionError(f"duplicate resolution receipt: {occurrence_id}")
            receipts[occurrence_id] = receipt
    states: dict[str, dict[str, Any]] = {}
    for task in authoritative_queue(repo_root)["tasks"]:
        if task.get("work_type") in {"bf2_work_order", "dependency_blocked"}:
            continue
        occurrence_id = str(task["id"])
        eligibility = resolution_eligibility(decisions.get(occurrence_id), receipts.get(occurrence_id))
        states[occurrence_id] = {
            "status": "resolved" if eligibility["resolved"] else "candidate_ready",
            "resolution_receipt_sha256": (
                receipts[occurrence_id]["stable_receipt_sha256"] if eligibility["resolved"] else None
            ),
            "eligibility": eligibility,
        }
    return states, receipts


def build_dependency_recompute(repo_root: Path) -> dict[str, Any]:
    tasks = authoritative_queue(repo_root)["tasks"]
    validate_dependency_graph(tasks)
    states, receipts = _validated_resolution_state(repo_root)
    rows: list[dict[str, Any]] = []
    for task in tasks:
        if task.get("work_type") != "dependency_blocked":
            continue
        missing = [str(item) for item in task.get("depends_on") or [] if str(item) not in states]
        if missing:
            raise Night04ExecutionError(f"dependency prerequisites lack atomic state: {missing}")
        result = dependency_unlock(task, states)
        rows.append(
            {
                **result,
                "status": "pending_unlocked" if result["unlocked"] else "dependency_blocked",
                "independent_prerequisite_receipt_count": sum(
                    str(item) in receipts for item in task.get("depends_on") or []
                ),
                "resolution_claimed": False,
            }
        )
    if len(rows) != EXPECTED_DEPENDENCY_BLOCKED:
        raise Night04ExecutionError("dependency recompute must cover exactly twenty occurrences")
    return stable_payload(
        {
            "schema_version": "r5_night04_dependency_recompute_v1",
            "mission_id": MISSION_ID,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "dependency_count": len(rows),
            "unlocked_count": sum(bool(item["unlocked"]) for item in rows),
            "blocked_count": sum(not bool(item["unlocked"]) for item in rows),
            "resolved_count": 0,
            "dependencies": sorted(rows, key=lambda item: str(item["occurrence_id"])),
        }
    )


def build_parent_recompute(repo_root: Path) -> dict[str, Any]:
    tasks = authoritative_queue(repo_root)["tasks"]
    states, _ = _validated_resolution_state(repo_root)
    dependency = build_dependency_recompute(repo_root)
    for item in dependency["dependencies"]:
        states[str(item["occurrence_id"])] = {"status": "pending"}
    pending = {
        str(task["id"]): task
        for task in tasks
        if task.get("work_type") == "bf2_work_order"
    }
    parents: list[dict[str, Any]] = []
    while pending:
        ready_ids = sorted(
            task_id
            for task_id, task in pending.items()
            if all(str(item) in states for item in task.get("depends_on") or [])
        )
        if not ready_ids:
            raise Night04ExecutionError(
                f"parent recompute cannot resolve parent dependency order: {sorted(pending)}"
            )
        for task_id in ready_ids:
            result = aggregate_parent(pending.pop(task_id), states)
            parents.append(result)
            states[task_id] = {"status": result["status"]}
    if len(parents) != EXPECTED_PARENTS:
        raise Night04ExecutionError("parent recompute must cover exactly six work orders")
    return stable_payload(
        {
            "schema_version": "r5_night04_parent_recompute_v1",
            "mission_id": MISSION_ID,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "parent_count": len(parents),
            "resolved_parent_count": sum(item["status"] == "resolved" for item in parents),
            "pending_parent_count": sum(item["status"] == "pending" for item in parents),
            "parents": sorted(parents, key=lambda item: str(item["parent_task_id"])),
        }
    )


def build_blocker_ledger(repo_root: Path) -> dict[str, Any]:
    tasks = authoritative_queue(repo_root)["tasks"]
    candidate_states, _ = _validated_resolution_state(repo_root)
    dependency = build_dependency_recompute(repo_root)
    dependency_by_id = {str(item["occurrence_id"]): item for item in dependency["dependencies"]}
    rows: list[dict[str, Any]] = []
    for task in tasks:
        work_type = str(task.get("work_type"))
        if work_type == "bf2_work_order":
            continue
        occurrence_id = str(task["id"])
        if work_type == "dependency_blocked":
            state = dependency_by_id[occurrence_id]
            status = str(state["status"])
            resolved = False
            receipt_sha = None
        else:
            state = candidate_states[occurrence_id]
            status = str(state["status"])
            resolved = status == "resolved"
            receipt_sha = state["resolution_receipt_sha256"]
        rows.append(
            {
                "occurrence_id": occurrence_id,
                "blocker_occurrence_id": blocker_id(task),
                "case_id": _note_fields(task).get("case_id"),
                "work_type": work_type,
                "status": status,
                "external_gate": "blocked_external" if status == "candidate_ready" else None,
                "resolved": resolved,
                "resolution_receipt_sha256": receipt_sha,
            }
        )
    counts = Counter(str(item["status"]) for item in rows)
    resolved = sum(bool(item["resolved"]) for item in rows)
    parent = build_parent_recompute(repo_root)
    if len(rows) != EXPECTED_OCCURRENCES:
        raise Night04ExecutionError("blocker ledger must cover exactly sixty-three occurrences")
    return stable_payload(
        {
            "schema_version": "r5_night04_blocker_ledger_v1",
            "mission_id": MISSION_ID,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "blocker_occurrences_total": EXPECTED_OCCURRENCES,
            "blocker_occurrences_resolved_start": 0,
            "blocker_occurrences_resolved_end": resolved,
            "resolved_delta": resolved,
            "status_counts": dict(sorted(counts.items())),
            "external_decision_pending_count": counts.get("candidate_ready", 0),
            "dependency_unlocked_count": counts.get("pending_unlocked", 0),
            "parent_work_orders_total": EXPECTED_PARENTS,
            "parent_work_orders_resolved": parent["resolved_parent_count"],
            "program_goal_state": "open_needs_targeted_backflow",
            "sample_quality_allowed": False,
            "p2_allowed": False,
            "occurrences": sorted(rows, key=lambda item: str(item["occurrence_id"])),
        }
    )


def build_next_night_queue(repo_root: Path) -> dict[str, Any]:
    source = authoritative_queue(repo_root)
    ledger = build_blocker_ledger(repo_root)
    parent = build_parent_recompute(repo_root)
    status_by_id = {str(item["occurrence_id"]): item for item in ledger["occurrences"]}
    parent_by_id = {str(item["parent_task_id"]): item for item in parent["parents"]}
    tasks: list[dict[str, Any]] = []
    for original in source["tasks"]:
        task = deepcopy(original)
        task_id = str(task["id"])
        if task_id in status_by_id:
            state = status_by_id[task_id]
            if state["resolved"]:
                continue
            task["night04_state"] = state["status"]
            task["night04_resolution_receipt_sha256"] = state["resolution_receipt_sha256"]
        else:
            state = parent_by_id[task_id]
            if state["status"] == "resolved":
                continue
            task["night04_state"] = "parent_pending"
        tasks.append(task)
    task_ids = [str(item["id"]) for item in tasks]
    source_hashes = [
        {
            "id": str(item["id"]),
            "source_artifact_sha256": _note_fields(item).get("source_artifact_sha256"),
        }
        for item in source["tasks"]
        if str(item["id"]) in set(task_ids)
    ]
    return {
        "schema_version": "r5_night_shift_queue_v3",
        "package_id": "R5_Overnight_Mission_05_PENDING",
        "mission_id": "r5_overnight_05_pending",
        "source_mission_id": MISSION_ID,
        "source_commit": None,
        "source_commit_policy": "resolve_final_remote_head_at_bootstrap",
        "publication_receipt": (OUTPUT_ROOT / "publication/remote_delivery_receipt.json").as_posix(),
        "source_queue_sha256": EXPECTED_QUEUE_SHA256,
        "program_goal": {
            "id": "r5_bundle17r_bf2_four_case_activation",
            "state": "open_needs_targeted_backflow",
            "close_allowed": False,
            "this_mission_may_close_goal": False,
        },
        "truth_at_start": {
            "work_orders_pending": parent["pending_parent_count"],
            "blocker_occurrences_total": EXPECTED_OCCURRENCES,
            "blocker_occurrences_resolved": ledger["blocker_occurrences_resolved_end"],
            "candidate_ready": ledger["status_counts"].get("candidate_ready", 0),
            "dependency_blocked": ledger["status_counts"].get("dependency_blocked", 0),
            "dependency_unlocked": ledger["status_counts"].get("pending_unlocked", 0),
            "sample_quality_allowed": False,
            "p2_allowed": False,
        },
        "carry_forward": {
            "mode": "all_unresolved_ids_verbatim",
            "task_count": len(tasks),
            "task_id_set_sha256": sha256_bytes(canonical_json_bytes(task_ids)),
            "source_hash_set_sha256": sha256_bytes(canonical_json_bytes(source_hashes)),
            "resolution_requires_external_decision_and_independent_receipt": True,
        },
        "candidate_artifacts": {
            "registry": (OUTPUT_ROOT / "review_control/candidate_registry.yaml").as_posix(),
            "dashboard": (OUTPUT_ROOT / "review_acceleration/reviewer_dashboard.yaml").as_posix(),
            "ledger": (OUTPUT_ROOT / "progress/blocker_ledger.json").as_posix(),
        },
        "tasks": tasks,
    }


def _blocker_ledger_markdown(ledger: Mapping[str, Any]) -> str:
    counts = ledger["status_counts"]
    return "\n".join(
        [
            "# Night04 Blocker Ledger",
            "",
            f"- 阻塞项总数：`{ledger['blocker_occurrences_total']}`",
            f"- 已解决：`{ledger['blocker_occurrences_resolved_end']}`",
            f"- 候选待外部评审：`{counts.get('candidate_ready', 0)}`",
            f"- 依赖阻塞：`{counts.get('dependency_blocked', 0)}`",
            f"- 已解除依赖但未解决：`{counts.get('pending_unlocked', 0)}`",
            f"- 父任务完成：`{ledger['parent_work_orders_resolved']}/{ledger['parent_work_orders_total']}`",
            "- Program Goal：`open_needs_targeted_backflow`",
            "- 候选就绪、沙盒测试通过和依赖模拟均不等于研究阻塞已解决。",
            "",
        ]
    )


def materialize_phase_e(
    repo_root: Path,
    *,
    checkpoint: str,
    continue_on_external_block: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    consumption = consume_external_decisions(
        repo_root,
        checkpoint=checkpoint,
        continue_on_external_block=continue_on_external_block,
        now=now,
    )
    adapters: dict[str, dict[str, Any]] = {}
    for kind, filename in ADAPTER_KIND_TO_FILE.items():
        result = execute_typed_adapter(
            repo_root,
            consumption["approved_records"],
            candidate_kind=kind,
        )
        write_json(repo_root / OUTPUT_ROOT / "execution" / filename, result)
        adapters[kind] = result
    dependency = build_dependency_recompute(repo_root)
    parent = build_parent_recompute(repo_root)
    ledger = build_blocker_ledger(repo_root)
    next_queue = build_next_night_queue(repo_root)
    write_json(repo_root / OUTPUT_ROOT / "execution/dependency_recompute.json", dependency)
    write_json(repo_root / OUTPUT_ROOT / "execution/parent_recompute.json", parent)
    write_json(repo_root / OUTPUT_ROOT / "progress/blocker_ledger.json", ledger)
    atomic_write(
        repo_root / OUTPUT_ROOT / "progress/blocker_ledger.md",
        _blocker_ledger_markdown(ledger).encode("utf-8"),
    )
    write_yaml(repo_root / OUTPUT_ROOT / "next_night_queue.yaml", next_queue)
    return {
        "mission_id": MISSION_ID,
        "target_branch": TARGET_BRANCH,
        "consumption": consumption,
        "adapters": adapters,
        "dependency": dependency,
        "parent": parent,
        "ledger": ledger,
        "next_queue": next_queue,
    }
