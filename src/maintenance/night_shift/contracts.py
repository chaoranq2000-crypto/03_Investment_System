"""Executable-contract authority, review locks, and per-task scope guards."""

from __future__ import annotations

import fnmatch
import json
import re
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from .models import ContractError, QueueDocument, Task, QUEUE_SCHEMA_VERSION_V2
from .queue import atomic_write
from .receipts import canonical_json_bytes, parse_trusted_command, sha256_bytes, sha256_file


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PLACEHOLDER_PATTERN = re.compile(r"(?:<[^>]+>|\{\{[^}]+\}\}|\bTODO_PATH\b)")
REVIEW_STATES = {"proposed", "approved", "rejected"}
EXECUTABLE_WORK_TYPES = {"engineering", "analysis_automation", "audit", "test"}


def _normalized_pattern(value: str) -> str:
    pattern = value.replace("\\", "/").strip()
    if " (" in pattern:
        pattern = pattern.split(" (", 1)[0].rstrip()
    return pattern


def _path_is_broad(pattern: str) -> bool:
    normalized = _normalized_pattern(pattern)
    return normalized in {"", ".", "./", "*", "**", "**/*", "/"}


def validate_allowed_paths(paths: Sequence[str]) -> tuple[str, ...]:
    if not paths:
        raise ContractError("allowed_paths: executable contract must declare exact paths")
    normalized: list[str] = []
    for index, value in enumerate(paths):
        pattern = _normalized_pattern(str(value))
        if _path_is_broad(pattern):
            raise ContractError(f"allowed_paths[{index}]: repository-wide pattern is forbidden")
        if PLACEHOLDER_PATTERN.search(pattern):
            raise ContractError(f"allowed_paths[{index}]: unresolved placeholder")
        pure = PurePosixPath(pattern)
        if pure.is_absolute() or ".." in pure.parts or re.match(r"^[A-Za-z]:", pattern):
            raise ContractError(f"allowed_paths[{index}]: must be repository-relative")
        normalized.append(pattern)
    return tuple(normalized)


def _is_executable_task(task: Task) -> bool:
    return bool(
        task.work_type in EXECUTABLE_WORK_TYPES
        or task.acceptance_commands
        or task.allowed_paths
    ) and not task.human_gate


def lint_executable_contract(task: Task) -> dict[str, Any]:
    errors: list[str] = []
    if not _is_executable_task(task):
        return {"task_id": task.id, "executable": False, "passed": True, "errors": []}

    try:
        validate_allowed_paths(task.allowed_paths)
    except ContractError as exc:
        errors.append(str(exc))
    if not task.acceptance_commands:
        errors.append("acceptance_commands: executable contract must not be empty")
    else:
        for index, command in enumerate(task.acceptance_commands):
            try:
                parse_trusted_command(command)
            except ContractError as exc:
                errors.append(f"acceptance_commands[{index}]: {exc}")
    for name, value in (
        ("contract_origin", task.contract_origin),
        ("path_authority", task.path_authority),
        ("acceptance_authority", task.acceptance_authority),
    ):
        if not str(value).strip():
            errors.append(f"{name}: must not be empty")
    if task.review_state != "approved":
        errors.append("review_state: executable task must be exact-hash approved")
    if not task.review_sha or not SHA256_PATTERN.fullmatch(task.review_sha.casefold()):
        errors.append("review_sha: must be a 64-character hexadecimal digest")
    return {
        "task_id": task.id,
        "executable": True,
        "passed": not errors,
        "errors": errors,
    }


def authorize_packaged_task(task: Task, *, package_digest_sha256: str) -> Task:
    digest = str(package_digest_sha256 or "").casefold()
    if not SHA256_PATTERN.fullmatch(digest):
        raise ContractError("package_digest_sha256: must be 64 hexadecimal characters")
    return replace(
        task,
        contract_origin="human_reviewed_package:R5_Overnight_Mission_02_20260719",
        path_authority="package:task_queue.yaml#allowed_paths",
        acceptance_authority="package:ACCEPTANCE_MATRIX.md",
        review_state="approved",
        review_sha=digest,
    )


def authorize_packaged_queue(
    queue: QueueDocument, *, package_digest_sha256: str
) -> QueueDocument:
    tasks = tuple(
        authorize_packaged_task(task, package_digest_sha256=package_digest_sha256)
        for task in queue.tasks
    )
    authorized = replace(queue, schema_version=QUEUE_SCHEMA_VERSION_V2, tasks=tasks)
    authorized.validate_graph(path="authorized_queue")
    return authorized


def lint_queue_contracts(queue: QueueDocument) -> dict[str, Any]:
    tasks = [lint_executable_contract(task) for task in queue.tasks]
    report: dict[str, Any] = {
        "schema_version": "r5_night_shift_contract_lint_v1",
        "mission_id": queue.mission_id,
        "task_count": len(tasks),
        "executable_task_count": sum(item["executable"] for item in tasks),
        "failed_task_count": sum(not item["passed"] for item in tasks),
        "tasks": tasks,
    }
    report["stable_receipt_sha256"] = sha256_bytes(canonical_json_bytes(report))
    return report


def write_contract_lint(path: Path, report: Mapping[str, Any]) -> None:
    atomic_write(
        path,
        (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
            "utf-8"
        ),
    )


def _review_projection(packet: Mapping[str, Any]) -> dict[str, Any]:
    excluded = {
        "proposal_sha256",
        "review_state",
        "review_sha",
        "reviewer",
        "reviewed_at",
        "decision",
        "decision_notes",
    }
    return {key: value for key, value in packet.items() if key not in excluded}


def review_packet_hash(packet: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(_review_projection(packet)))


def generate_contract_proposal(
    *,
    task_id: str,
    source_artifact: str,
    owner_skill: str,
    requested_action: str,
    candidate_paths: Sequence[str],
    acceptance_commands: Sequence[str],
    generator_version: str,
) -> dict[str, Any]:
    paths = validate_allowed_paths(candidate_paths)
    if not acceptance_commands:
        raise ContractError("proposal.acceptance_commands: must not be empty")
    for command in acceptance_commands:
        parse_trusted_command(command)
    packet: dict[str, Any] = {
        "schema_version": "r5_night_shift_contract_proposal_v1",
        "task_id": task_id,
        "source_artifact": source_artifact,
        "owner_skill": owner_skill,
        "requested_action": requested_action,
        "candidate_paths": list(paths),
        "acceptance_commands": list(acceptance_commands),
        "contract_origin": "repository_owned_deterministic_generator",
        "generator_version": generator_version,
        "review_state": "proposed",
        "review_sha": None,
        "reviewer": None,
        "reviewed_at": None,
        "decision": None,
        "decision_notes": None,
        "resolution_claim_allowed": False,
    }
    packet["proposal_sha256"] = review_packet_hash(packet)
    return packet


def validate_review_packet(packet: Mapping[str, Any], *, require_approved: bool) -> str:
    state = str(packet.get("review_state") or "")
    if state not in REVIEW_STATES:
        raise ContractError(f"review_state: unsupported value {state!r}")
    calculated = review_packet_hash(packet)
    proposal_sha = str(packet.get("proposal_sha256") or "").casefold()
    if proposal_sha != calculated:
        raise ContractError(
            f"proposal exact-hash mismatch: supplied={proposal_sha}, calculated={calculated}"
        )
    if require_approved:
        if state != "approved":
            raise ContractError("review packet is not approved")
        review_sha = str(packet.get("review_sha") or "").casefold()
        if review_sha != calculated:
            raise ContractError(
                f"review exact-hash mismatch: supplied={review_sha}, calculated={calculated}"
            )
        if not str(packet.get("reviewer") or "").strip():
            raise ContractError("approved review packet is missing reviewer")
        if not str(packet.get("reviewed_at") or "").strip():
            raise ContractError("approved review packet is missing reviewed_at")
    return calculated


def route_pointer_contract(
    *,
    missing_pointer: str,
    observed_fields: Sequence[str],
    semantically_equivalent_aliases: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    aliases = semantically_equivalent_aliases or {}
    if missing_pointer in aliases and aliases[missing_pointer] in observed_fields:
        return {
            "route": "pointer_alias_correction",
            "candidate_pointer": aliases[missing_pointer],
            "resolution_claim_allowed": False,
        }
    if missing_pointer == "/generation_id":
        route = "upstream_generation_contract"
    elif missing_pointer == "/candidate_ready_for_exact_hash_review":
        route = "upstream_quality_contract"
    else:
        route = "upstream_schema_contract"
    return {
        "route": route,
        "candidate_pointer": None,
        "observed_fields": sorted(set(observed_fields)),
        "resolution_claim_allowed": False,
    }


@dataclass(frozen=True)
class TreeSnapshot:
    files: dict[str, str]


def capture_tree_snapshot(repo_root: Path) -> TreeSnapshot:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-co", "--exclude-standard", "-z"],
        check=False,
        capture_output=True,
    )
    if completed.returncode:
        raise ContractError("cannot capture repository file inventory")
    root = repo_root.resolve()
    records: dict[str, str] = {}
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        path = (root / PurePosixPath(relative)).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ContractError(f"tracked path escapes repository: {relative}") from exc
        if path.is_symlink():
            records[relative] = "SYMLINK"
        elif path.is_file():
            records[relative] = sha256_file(path)
        else:
            records[relative] = "MISSING"
    return TreeSnapshot(files=dict(sorted(records.items())))


def _matches(path: str, pattern: str) -> bool:
    normalized = _normalized_pattern(pattern)
    if normalized.endswith("/**"):
        prefix = normalized[:-3].rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    return fnmatch.fnmatchcase(path, normalized)


def enforce_task_scope(
    before: TreeSnapshot,
    after: TreeSnapshot,
    *,
    allowed_paths: Sequence[str],
    forbidden_paths: Sequence[str],
) -> dict[str, Any]:
    allowed = validate_allowed_paths(allowed_paths)
    changed = sorted(
        path
        for path in set(before.files) | set(after.files)
        if before.files.get(path) != after.files.get(path)
    )
    forbidden = [
        path for path in changed if any(_matches(path, pattern) for pattern in forbidden_paths)
    ]
    outside = [
        path for path in changed if not any(_matches(path, pattern) for pattern in allowed)
    ]
    result = {
        "changed_paths": changed,
        "forbidden_paths_changed": forbidden,
        "outside_allowed_paths": outside,
        "passed": not forbidden and not outside,
    }
    if not result["passed"]:
        raise ContractError(
            "task diff scope violation: "
            + json.dumps(
                {"forbidden": forbidden, "outside_allowed": outside},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return result


def pilot_eligibility(task: Task, *, review_packet: Mapping[str, Any] | None) -> dict[str, Any]:
    reasons: list[str] = []
    lint = lint_executable_contract(task)
    reasons.extend(lint["errors"])
    if review_packet is not None:
        try:
            validate_review_packet(review_packet, require_approved=True)
        except ContractError as exc:
            reasons.append(str(exc))
    elif task.contract_origin.startswith("repository_owned_deterministic_generator"):
        reasons.append("generated proposal is missing its exact-hash approval packet")
    return {
        "task_id": task.id,
        "eligible": not reasons,
        "status": "ready" if not reasons else "blocked_external",
        "reasons": reasons,
        "resolution_claim_allowed": False,
    }
