"""Occurrence-level execution and resolution contracts for Night03."""

from __future__ import annotations

import fnmatch
import re
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

from .night03 import (
    EXPECTED_QUEUE_SHA256,
    MISSION_ID,
    OUTPUT_ROOT,
    Night03Error,
    authoritative_queue,
    stable_payload,
    write_json,
    write_yaml,
)
from .night03_decisions import resolution_eligibility
from .receipts import canonical_json_bytes, parse_trusted_command, sha256_bytes


OCCURRENCE_STATUSES = {
    "pending",
    "candidate_ready",
    "blocked_external",
    "approved",
    "running",
    "passed",
    "failed",
    "resolved",
}
ALLOWED_TRANSITIONS = {
    "pending": {"candidate_ready", "blocked_external"},
    "candidate_ready": {"approved", "blocked_external"},
    "blocked_external": {"candidate_ready", "approved"},
    "approved": {"running", "blocked_external"},
    "running": {"passed", "failed"},
    "passed": {"resolved", "failed"},
    "failed": {"approved", "blocked_external"},
    "resolved": set(),
}
FORBIDDEN_COMMAND_FRAGMENTS = (
    "push --force",
    "push -f",
    "git push",
    "gh pr create",
    "git merge",
    "git reset --hard",
    "git clean -f",
    "curl ",
    "invoke-webrequest",
    "start-process",
    "remove-item",
    "rm ",
    "rmdir ",
    "del ",
    "<",
    "{{",
    "todo_path",
)
READ_ONLY_GIT_SUBCOMMANDS = {
    "status",
    "diff",
    "rev-parse",
    "ls-files",
    "show",
    "branch",
    "log",
}


def note_fields(task: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for note in task.get("notes") or []:
        text = str(note)
        if "=" in text:
            key, value = text.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def initial_occurrence_state(task: Mapping[str, Any]) -> dict[str, Any]:
    if task.get("work_type") == "bf2_work_order":
        raise Night03Error("parent work orders are not occurrence states")
    original_status = str(task.get("status") or "")
    status = "pending" if original_status == "pending" else "blocked_external"
    return {
        "occurrence_id": str(task["id"]),
        "status": status,
        "source_status": original_status,
        "source_queue_sha256": EXPECTED_QUEUE_SHA256,
        "attempts": 0,
        "candidate_artifact_sha256": None,
        "decision_digest_sha256": None,
        "resolution_receipt_sha256": None,
        "events": [],
    }


def transition_occurrence(
    state: Mapping[str, Any],
    target: str,
    *,
    event_id: str,
    candidate_artifact_sha256: str | None = None,
    validated_decision: Mapping[str, Any] | None = None,
    execution_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    current = str(state.get("status") or "")
    if current not in OCCURRENCE_STATUSES or target not in OCCURRENCE_STATUSES:
        raise Night03Error(f"unsupported occurrence transition: {current!r} -> {target!r}")
    if any(event.get("event_id") == event_id for event in state.get("events") or []):
        return deepcopy(dict(state))
    if target not in ALLOWED_TRANSITIONS[current]:
        raise Night03Error(f"forbidden occurrence transition: {current} -> {target}")
    result = deepcopy(dict(state))
    if target == "candidate_ready":
        candidate = str(candidate_artifact_sha256 or "").casefold()
        if not re.fullmatch(r"[0-9a-f]{64}", candidate):
            raise Night03Error("candidate_ready requires an exact candidate SHA-256")
        result["candidate_artifact_sha256"] = candidate
    if target == "approved":
        if not validated_decision or validated_decision.get("decision") != "approved":
            raise Night03Error("approved transition requires a validated approved decision")
        digest = str(validated_decision.get("decision_digest_sha256") or "").casefold()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise Night03Error("approved transition requires a decision digest")
        result["decision_digest_sha256"] = digest
    if target == "running":
        if not result.get("decision_digest_sha256"):
            raise Night03Error("running transition requires a bound approved decision")
        result["attempts"] = int(result.get("attempts") or 0) + 1
    if target == "passed":
        if not execution_receipt or execution_receipt.get("terminal_status") != "passed":
            raise Night03Error("passed transition requires a passed execution receipt")
    if target == "resolved":
        eligibility = resolution_eligibility(validated_decision, execution_receipt)
        if not eligibility["resolved"]:
            raise Night03Error(
                "resolved transition rejected: " + ",".join(eligibility["reasons"])
            )
        receipt_sha = str(execution_receipt.get("stable_receipt_sha256") or "").casefold()
        if not re.fullmatch(r"[0-9a-f]{64}", receipt_sha):
            raise Night03Error("resolved transition requires a stable receipt SHA-256")
        result["resolution_receipt_sha256"] = receipt_sha
    result["events"].append(
        {
            "event_id": event_id,
            "from": current,
            "to": target,
            "decision_digest_sha256": result.get("decision_digest_sha256"),
            "resolution_receipt_sha256": result.get("resolution_receipt_sha256"),
        }
    )
    result["status"] = target
    return result


def aggregate_parent(
    parent: Mapping[str, Any], occurrence_states: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    dependencies = [str(item) for item in parent.get("depends_on") or []]
    missing = [item for item in dependencies if item not in occurrence_states]
    if missing:
        raise Night03Error(f"parent work order has orphan occurrences: {missing}")
    resolved = [
        item for item in dependencies if occurrence_states[item].get("status") == "resolved"
    ]
    return {
        "parent_task_id": str(parent["id"]),
        "required_occurrences": len(dependencies),
        "resolved_occurrences": len(resolved),
        "unresolved_occurrence_ids": [item for item in dependencies if item not in resolved],
        "status": "resolved" if len(resolved) == len(dependencies) else "pending",
    }


def validate_dependency_graph(tasks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    task_map = {str(task["id"]): task for task in tasks}
    orphans: list[dict[str, str]] = []
    cross_case: list[dict[str, str]] = []
    graph: dict[str, list[str]] = {}
    for task in tasks:
        task_id = str(task["id"])
        dependencies = [str(item) for item in task.get("depends_on") or []]
        graph[task_id] = dependencies
        case_id = note_fields(task).get("case_id")
        for dependency in dependencies:
            if dependency not in task_map:
                orphans.append({"task_id": task_id, "dependency_id": dependency})
                continue
            dependency_case = note_fields(task_map[dependency]).get("case_id")
            if (
                task.get("work_type") == "dependency_blocked"
                and case_id not in {None, "__suite__"}
                and dependency_case not in {case_id, "__suite__"}
            ):
                cross_case.append({"task_id": task_id, "dependency_id": dependency})
    visiting: set[str] = set()
    visited: set[str] = set()
    cycles: list[str] = []

    def visit(task_id: str) -> None:
        if task_id in visiting:
            cycles.append(task_id)
            return
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in graph.get(task_id, []):
            if dependency in graph:
                visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in graph:
        visit(task_id)
    result = {
        "task_count": len(tasks),
        "orphan_dependencies": orphans,
        "cycle_task_ids": sorted(set(cycles)),
        "cross_case_dependencies": cross_case,
        "passed": not orphans and not cycles and not cross_case,
    }
    if not result["passed"]:
        raise Night03Error(f"invalid dependency graph: {result}")
    return result


def dependency_unlock(
    task: Mapping[str, Any], occurrence_states: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    dependencies = [str(item) for item in task.get("depends_on") or []]
    missing = [item for item in dependencies if item not in occurrence_states]
    if missing:
        raise Night03Error(f"dependency occurrence has orphan prerequisites: {missing}")
    unresolved = [
        item for item in dependencies if occurrence_states[item].get("status") != "resolved"
    ]
    return {
        "occurrence_id": str(task["id"]),
        "unlocked": not unresolved,
        "next_status": "pending" if not unresolved else "blocked_external",
        "unresolved_prerequisites": unresolved,
    }


def _matches(path: str, pattern: str) -> bool:
    normalized = str(pattern).replace("\\", "/").strip()
    if normalized.endswith("/**"):
        prefix = normalized[:-3].rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    return fnmatch.fnmatchcase(path, normalized)


def validate_occurrence_diff(
    changed_paths: Sequence[str],
    *,
    approved_paths: Sequence[str],
    forbidden_paths: Sequence[str] = (),
) -> dict[str, Any]:
    if not approved_paths:
        raise Night03Error("approved pointer contract has no allowed paths")
    normalized = [str(path).replace("\\", "/") for path in changed_paths]
    outside = [
        path for path in normalized if not any(_matches(path, pattern) for pattern in approved_paths)
    ]
    forbidden = [
        path for path in normalized if any(_matches(path, pattern) for pattern in forbidden_paths)
    ]
    result = {
        "changed_paths": sorted(set(normalized)),
        "outside_approved_paths": sorted(set(outside)),
        "forbidden_paths_changed": sorted(set(forbidden)),
        "passed": not outside and not forbidden,
    }
    if not result["passed"]:
        raise Night03Error(f"pointer child diff escaped approved scope: {result}")
    return result


def validate_approved_command(command: str, *, approved_command_sha256: str) -> list[str]:
    actual = sha256_bytes(command.encode("utf-8"))
    if actual != str(approved_command_sha256 or "").casefold():
        raise Night03Error("acceptance command exact-hash mismatch")
    lowered = command.casefold()
    if any(fragment in lowered for fragment in FORBIDDEN_COMMAND_FRAGMENTS):
        raise Night03Error("acceptance command contains a forbidden fragment")
    argv = parse_trusted_command(command)
    if argv and Path(argv[0]).name.casefold() == "git":
        arguments = [item for item in argv[1:] if item not in {"-C"}]
        # Commands with `git -C path <subcommand>` are normalised by locating
        # the first recognised subcommand rather than trusting position alone.
        subcommand = next((item for item in arguments if item in READ_ONLY_GIT_SUBCOMMANDS), None)
        if subcommand is None:
            raise Night03Error("pointer acceptance permits read-only git commands only")
    return argv


def execute_pointer_wave(
    contracts: Sequence[Mapping[str, Any]],
    *,
    executor: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    approved = [item for item in contracts if item.get("decision") == "approved"]
    if not approved:
        return {
            "outcome": "blocked_external_no_approved_contracts",
            "executed_count": 0,
            "resolved_count": 0,
            "results": [],
        }
    if len(approved) > 2:
        raise Night03Error("pointer wave exceeds the two-task maximum")
    if executor is None:
        raise Night03Error("approved pointer contracts require an explicit executor")
    results: list[dict[str, Any]] = []
    for contract in approved:
        for command in contract.get("acceptance_commands") or []:
            hashes = contract.get("acceptance_command_sha256") or {}
            validate_approved_command(
                str(command), approved_command_sha256=str(hashes.get(str(command)) or "")
            )
        execution = dict(executor(contract))
        scope = validate_occurrence_diff(
            execution.get("changed_paths") or [],
            approved_paths=contract.get("allowed_paths") or [],
            forbidden_paths=contract.get("forbidden_paths") or [],
        )
        passed = bool(execution.get("acceptance_passed")) and scope["passed"]
        results.append(
            {
                "occurrence_id": contract.get("occurrence_id"),
                "terminal_status": "passed" if passed else "failed",
                "scope": scope,
                "resolution_claimed": False,
            }
        )
    return {
        "outcome": "pilot_acceptance_executed",
        "executed_count": len(results),
        "resolved_count": 0,
        "results": results,
    }


def resolution_receipt_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "r5_night03_resolution_receipt_v1",
        "type": "object",
        "required": [
            "occurrence_id",
            "decision_digest_sha256",
            "source_queue_sha256",
            "implementation_tree_sha",
            "commands",
            "outputs",
            "terminal_status",
            "lineage_match",
            "resolution_claim_allowed",
            "stable_receipt_sha256",
        ],
        "properties": {
            "occurrence_id": {"type": "string", "minLength": 1},
            "decision_digest_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "source_queue_sha256": {"const": EXPECTED_QUEUE_SHA256},
            "implementation_tree_sha": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            "commands": {"type": "array"},
            "outputs": {"type": "array"},
            "terminal_status": {"enum": ["passed", "failed"]},
            "lineage_match": {"type": "boolean"},
            "resolution_claim_allowed": {"type": "boolean"},
            "stable_receipt_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        },
        "additionalProperties": True,
        "publication_head_forbidden": True,
    }


def build_resolution_receipt(
    *,
    occurrence_id: str,
    decision_digest_sha256: str,
    implementation_tree_sha: str,
    commands: Sequence[Mapping[str, Any]],
    outputs: Sequence[Mapping[str, Any]],
    terminal_status: str,
    lineage_match: bool,
    resolution_claim_allowed: bool,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", decision_digest_sha256):
        raise Night03Error("decision_digest_sha256 is invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", implementation_tree_sha):
        raise Night03Error("implementation_tree_sha is invalid")
    if terminal_status not in {"passed", "failed"}:
        raise Night03Error("terminal_status is invalid")
    payload = stable_payload(
        {
            "schema_version": "r5_night03_resolution_receipt_v1",
            "occurrence_id": occurrence_id,
            "decision_digest_sha256": decision_digest_sha256,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "implementation_tree_sha": implementation_tree_sha,
            "publication_head": None,
            "commands": [dict(item) for item in commands],
            "outputs": [dict(item) for item in outputs],
            "terminal_status": terminal_status,
            "lineage_match": bool(lineage_match),
            "resolution_claim_allowed": bool(resolution_claim_allowed),
        }
    )
    return payload


def generation_lock(receipts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    records = [
        {
            "occurrence_id": str(receipt.get("occurrence_id") or ""),
            "stable_receipt_sha256": str(receipt.get("stable_receipt_sha256") or ""),
        }
        for receipt in receipts
    ]
    records.sort(key=lambda item: item["occurrence_id"])
    return stable_payload(
        {
            "schema_version": "r5_night03_resolution_generation_lock_v1",
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "receipt_count": len(records),
            "receipts": records,
        }
    )


def replay_decisions(
    initial_states: Mapping[str, Mapping[str, Any]],
    validated_decisions: Sequence[Mapping[str, Any]],
    receipts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    states = {key: deepcopy(dict(value)) for key, value in initial_states.items()}
    processed: list[str] = []
    for decision in sorted(
        validated_decisions, key=lambda item: str(item.get("decision_digest_sha256") or "")
    ):
        digest = str(decision.get("decision_digest_sha256") or "")
        occurrence_id = str(decision.get("occurrence_id") or "")
        if digest in processed:
            continue
        if occurrence_id not in states:
            raise Night03Error(f"decision references unknown state: {occurrence_id}")
        state = states[occurrence_id]
        if state["status"] in {"pending", "blocked_external"}:
            if state["status"] == "pending":
                state = transition_occurrence(
                    state,
                    "blocked_external",
                    event_id=f"{digest}:external",
                )
            state = transition_occurrence(
                state,
                "approved",
                event_id=f"{digest}:approved",
                validated_decision=decision,
            )
        receipt = receipts.get(occurrence_id)
        if receipt and state["status"] == "approved":
            state = transition_occurrence(state, "running", event_id=f"{digest}:running")
            state = transition_occurrence(
                state,
                "passed",
                event_id=f"{digest}:passed",
                execution_receipt=receipt,
            )
            state = transition_occurrence(
                state,
                "resolved",
                event_id=f"{digest}:resolved",
                validated_decision=decision,
                execution_receipt=receipt,
            )
        states[occurrence_id] = state
        processed.append(digest)
    return {
        "schema_version": "r5_night03_replay_state_v1",
        "source_queue_sha256": EXPECTED_QUEUE_SHA256,
        "processed_decision_digests": processed,
        "occurrences": dict(sorted(states.items())),
    }


def execution_contracts(repo_root: Path) -> dict[str, Any]:
    queue = authoritative_queue(repo_root)
    tasks = queue["tasks"]
    dependency_graph = validate_dependency_graph(tasks)
    dependency_items = [task for task in tasks if task.get("work_type") == "dependency_blocked"]
    parent_items = [task for task in tasks if task.get("work_type") == "bf2_work_order"]
    return {
        "occurrence": {
            "schema_version": "r5_night03_occurrence_state_contract_v1",
            "statuses": sorted(OCCURRENCE_STATUSES),
            "allowed_transitions": {
                key: sorted(value) for key, value in ALLOWED_TRANSITIONS.items()
            },
            "resolution_requires_independent_receipt": True,
        },
        "parent": {
            "schema_version": "r5_night03_parent_aggregation_contract_v1",
            "parent_count": len(parent_items),
            "close_rule": "all_required_occurrences_resolved",
            "candidate_ready_counts_as_resolved": False,
            "blocked_external_counts_as_resolved": False,
        },
        "dependency": {
            "schema_version": "r5_night03_dependency_unblock_contract_v1",
            "dependency_occurrence_count": len(dependency_items),
            "unlock_rule": "all_prerequisites_have_independent_resolution_receipts",
            "graph_audit": dependency_graph,
        },
        "sandbox": {
            "schema_version": "r5_night03_sandbox_contract_v1",
            "child_diff_must_be_subset_of_approved_paths": True,
            "single_shared_state_integrator": True,
            "scope_violation_outcome": "failed_and_rollback_required",
        },
        "commands": {
            "schema_version": "r5_night03_command_safety_contract_v1",
            "exact_command_hash_required": True,
            "trusted_executables": ["python", "pytest", "git"],
            "git_mode": "read_only_acceptance_only",
            "forbidden_fragments": list(FORBIDDEN_COMMAND_FRAGMENTS),
        },
        "pointer": {
            "schema_version": "r5_night03_pointer_executor_contract_v1",
            "max_tasks_per_wave": 2,
            "approval_required": True,
            "no_approval_outcome": "blocked_external_no_approved_contracts",
            "no_approval_resolved_delta": 0,
        },
        "replay": {
            "schema_version": "r5_night03_replay_contract_v1",
            "decision_digest_is_idempotency_key": True,
            "duplicate_decision_consumption_allowed": False,
            "duplicate_resolution_count_allowed": False,
            "same_input_same_output_bytes": True,
        },
    }


def materialize_execution_contracts(repo_root: Path) -> dict[str, Any]:
    root = repo_root / OUTPUT_ROOT / "execution"
    contracts = execution_contracts(repo_root)
    write_yaml(root / "occurrence_state_contract.yaml", contracts["occurrence"])
    write_yaml(root / "parent_aggregation_contract.yaml", contracts["parent"])
    write_yaml(root / "dependency_unblock_contract.yaml", contracts["dependency"])
    write_yaml(root / "sandbox_contract.yaml", contracts["sandbox"])
    write_yaml(root / "command_safety_contract.yaml", contracts["commands"])
    write_yaml(root / "pointer_executor_contract.yaml", contracts["pointer"])
    write_json(root / "resolution_receipt_schema.json", resolution_receipt_schema())
    write_yaml(root / "replay_contract.yaml", contracts["replay"])
    return contracts
