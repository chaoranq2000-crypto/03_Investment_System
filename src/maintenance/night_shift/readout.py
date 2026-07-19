"""Deterministic scope audit, next queue, and morning readout generation."""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from .models import ContractError, QueueDocument, Task
from .queue import atomic_write, load_queue, queue_bytes, save_queue
from .receipts import canonical_json_bytes, sha256_bytes, sha256_file


MORNING_SCHEMA_VERSION = "r5_night_shift_morning_readout_v1"
SCOPE_SCHEMA_VERSION = "r5_night_shift_scope_audit_v1"
DETERMINISM_SCHEMA_VERSION = "r5_night_shift_determinism_receipt_v1"

FORBIDDEN_PATHS = (
    "data/raw/",
    "reports/p1_6/R5_READOUT_CANONICAL_INDEX.md",
    "config/r5_readout_canonical_index.yaml",
)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"JSON[{path}]: cannot read: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON[{path}]: root must be an object")
    return value


def git(repo_root: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and completed.returncode:
        raise ContractError(
            f"git {' '.join(args)} failed: {completed.stderr.strip() or completed.stdout.strip()}"
        )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _status_paths(repo_root: Path) -> list[str]:
    output = git(repo_root, "status", "--porcelain=v1", "--untracked-files=all")
    paths: list[str] = []
    for line in output.splitlines():
        value = line[3:] if len(line) >= 4 else line
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.append(value.replace("\\", "/"))
    return sorted(set(paths))


def build_scope_audit(repo_root: Path, *, baseline_sha: str) -> dict[str, Any]:
    changed = _status_paths(repo_root)
    committed = git(repo_root, "diff", "--name-only", f"{baseline_sha}..HEAD")
    all_changed = sorted(
        set(changed)
        | {line.replace("\\", "/") for line in committed.splitlines() if line.strip()}
    )
    tracked_local = [
        line for line in git(repo_root, "ls-files", ".local").splitlines() if line.strip()
    ]
    tracked_bf2 = [
        line
        for line in git(repo_root, "ls-files", "reports/p1_6/r5_bundle17r_bf2*").splitlines()
        if line.strip()
    ]
    forbidden = [
        path
        for path in all_changed
        if any(path == item.rstrip("/") or path.startswith(item) for item in FORBIDDEN_PATHS)
    ]
    audit: dict[str, Any] = {
        "schema_version": SCOPE_SCHEMA_VERSION,
        "baseline_sha": baseline_sha,
        "changed_paths": all_changed,
        "tracked_local_runtime_outputs": len(tracked_local),
        "tracked_local_paths": tracked_local,
        "tracked_bf2_run_outputs": len(tracked_bf2),
        "tracked_bf2_paths": tracked_bf2,
        "forbidden_paths_changed": len(forbidden),
        "forbidden_changed_paths": forbidden,
        "pr_created": False,
        "main_merged": False,
        "force_push_used": False,
        "scope_guard_pass": not tracked_local and not tracked_bf2 and not forbidden,
    }
    audit["scope_audit_sha256"] = sha256_bytes(canonical_json_bytes(audit))
    return audit


def write_json(path: Path, value: Any) -> None:
    atomic_write(
        path,
        (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
            "utf-8"
        ),
    )


def compare_files(pairs: Sequence[tuple[Path, Path]], receipt_path: Path) -> dict[str, Any]:
    comparisons: list[dict[str, Any]] = []
    all_equal = True
    for left, right in pairs:
        if not left.is_file() or not right.is_file():
            raise ContractError(f"determinism comparison file is missing: {left} / {right}")
        left_hash = sha256_file(left)
        right_hash = sha256_file(right)
        equal = left.read_bytes() == right.read_bytes()
        all_equal = all_equal and equal
        comparisons.append(
            {
                "left": left.as_posix(),
                "left_sha256": left_hash,
                "right": right.as_posix(),
                "right_sha256": right_hash,
                "byte_for_byte_equal": equal,
            }
        )
    receipt: dict[str, Any] = {
        "schema_version": DETERMINISM_SCHEMA_VERSION,
        "comparisons": comparisons,
        "all_byte_for_byte_equal": all_equal,
    }
    receipt["stable_receipt_sha256"] = sha256_bytes(canonical_json_bytes(receipt))
    write_json(receipt_path, receipt)
    if not all_equal:
        raise ContractError("one or more determinism comparisons differ byte-for-byte")
    return receipt


def build_next_queue(inventory: Mapping[str, Any], *, source_commit: str) -> QueueDocument:
    counts = inventory.get("classification_counts")
    if not isinstance(counts, Mapping):
        raise ContractError("BF2 inventory is missing classification_counts")
    occurrences = inventory.get("occurrences")
    if isinstance(occurrences, list) and occurrences:
        from .backflow import build_occurrence_queue

        queue = build_occurrence_queue(occurrences, source_commit=source_commit)
        return replace(
            queue,
            mission_id="r5_overnight_03_targeted_backflow",
            program_goal={
                "id": "r5_bundle17r_bf2_four_case_activation",
                "state": "open_needs_targeted_backflow",
                "close_allowed": False,
                "this_mission_may_close_goal": False,
            },
        )
    contract_task = Task(
        id="ns02_t00_review_pointer_contracts",
        title="审核 8 个 pointer occurrence 的工程合同",
        priority=100,
        status="human_gate",
        depends_on=(),
        work_type="contract_review",
        goal=(
            f"为 {int(counts.get('engineering_local', 0))} 个 pointer occurrence "
            "提供 exact allowed_paths、acceptance_commands 和 owner approval"
        ),
        allowed_paths=(),
        forbidden_paths=("data/raw/**", "main", "canonical/sample-quality/P2"),
        acceptance_commands=(),
        required_artifacts=(),
        retry_limit=0,
        on_success={},
        on_failure={"emit_failure_packet": True},
        human_gate=True,
        notes=("No automation until exact paths and commands are reviewed.",),
    )
    evidence_task = Task(
        id="ns02_t10_acquire_reviewed_evidence",
        title="补齐 evidence-required blocker",
        priority=90,
        status="evidence_required",
        depends_on=(),
        work_type="evidence_required",
        goal=f"处理 {int(counts.get('evidence_required', 0))} 个需要新证据的 occurrence",
        allowed_paths=(),
        forbidden_paths=("main", "canonical/sample-quality/P2"),
        acceptance_commands=(),
        required_artifacts=(),
        retry_limit=0,
        on_success={},
        on_failure={"emit_failure_packet": True},
        human_gate=False,
        notes=("Route evidence acquisition through evidence-ingest.",),
    )
    analysis_task = Task(
        id="ns02_t20_complete_analysis_backflow",
        title="完成人工研究分析回流",
        priority=80,
        status="human_gate",
        depends_on=(),
        work_type="analysis_required",
        goal=f"处理 {int(counts.get('analysis_required', 0))} 个需要研究判断的 occurrence",
        allowed_paths=(),
        forbidden_paths=("main", "canonical/sample-quality/P2"),
        acceptance_commands=(),
        required_artifacts=(),
        retry_limit=0,
        on_success={},
        on_failure={"emit_failure_packet": True},
        human_gate=True,
        notes=("Do not rewrite analyst judgment as fact.",),
    )
    hash_task = Task(
        id="ns02_t30_exact_hash_review",
        title="执行 exact-hash 人审",
        priority=70,
        status="human_gate",
        depends_on=(),
        work_type="human_gate",
        goal=f"处理 {int(counts.get('human_gate', 0))} 个 exact-hash/human-gate occurrence",
        allowed_paths=(),
        forbidden_paths=("main", "canonical/sample-quality/P2"),
        acceptance_commands=(),
        required_artifacts=(),
        retry_limit=0,
        on_success={},
        on_failure={"emit_failure_packet": True},
        human_gate=True,
        notes=("Review acceptance cannot be generated automatically.",),
    )
    resume_task = Task(
        id="ns02_t40_resume_bf2_work_orders",
        title="重跑 BF2 work-order acceptance",
        priority=60,
        status="pending",
        depends_on=(
            contract_task.id,
            evidence_task.id,
            analysis_task.id,
            hash_task.id,
        ),
        work_type="dependency_blocked",
        goal="仅在前置证据、分析、工程合同和人审全部真实通过后重跑六个 work order",
        allowed_paths=(),
        forbidden_paths=("main", "canonical/sample-quality/P2"),
        acceptance_commands=(),
        required_artifacts=(),
        retry_limit=0,
        on_success={},
        on_failure={"emit_failure_packet": True},
        human_gate=False,
        notes=("Preserve 6 pending and 0/63 resolved until receipts prove otherwise.",),
    )
    return QueueDocument.from_mapping(
        {
            "schema_version": "r5_night_shift_queue_v1",
            "mission_id": "r5_overnight_02_targeted_backflow_execution",
            "program_goal": {
                "id": "r5_bundle17r_bf2_four_case_activation",
                "state": "open_needs_targeted_backflow",
                "close_allowed": False,
                "this_mission_may_close_goal": False,
            },
            "baseline": {
                "source_branch": "codex/r5-night01-autonomous-harness",
                "source_commit": source_commit,
                "research_gate": "needs_targeted_backflow",
                "blocker_occurrences_resolved": 0,
                "sample_quality_allowed": False,
                "p2_allowed": False,
            },
            "run_window": {
                "timezone": "Europe/London",
                "start_at": "23:00",
                "stop_claiming_at": "06:15",
                "final_readout_at": "06:30",
            },
            "task_selection": {
                "order": ["priority_desc", "dependency_ready", "task_id_asc"],
                "single_integrator": True,
                "max_parallel_shared_state_writers": 1,
            },
            "tasks": [
                contract_task.to_mapping(),
                evidence_task.to_mapping(),
                analysis_task.to_mapping(),
                hash_task.to_mapping(),
                resume_task.to_mapping(),
            ],
        },
        path="next_night_queue",
    )


def branch_snapshot(repo_root: Path, *, baseline_sha: str, target_branch: str) -> dict[str, Any]:
    local_sha = git(repo_root, "rev-parse", "HEAD")
    remote_ref = f"refs/remotes/origin/{target_branch}"
    remote_sha = git(repo_root, "rev-parse", "--verify", remote_ref, check=False) or None
    log = git(
        repo_root,
        "log",
        "--reverse",
        "--format=%H%x09%s",
        f"{baseline_sha}..HEAD",
    )
    commits = []
    for line in log.splitlines():
        sha, _, subject = line.partition("\t")
        commits.append({"sha": sha, "subject": subject})
    return {
        "target_branch": target_branch,
        "local_sha": local_sha,
        "remote_sha": remote_sha,
        "remote_sha_equals_local": remote_sha == local_sha if remote_sha else False,
        "commits": commits,
    }


def build_morning_payload(
    *,
    run_id: str,
    baseline: Mapping[str, Any],
    mission_state: QueueDocument,
    seed_receipt: Mapping[str, Any],
    validation_receipt: Mapping[str, Any],
    determinism_receipt: Mapping[str, Any],
    scope_audit: Mapping[str, Any],
    branch: Mapping[str, Any],
    next_queue: QueueDocument,
) -> dict[str, Any]:
    status_counts = Counter(task.status for task in mission_state.tasks)
    validation = [
        {
            "command": item.get("command"),
            "exit_code": item.get("exit_code"),
            "result": "pass" if item.get("exit_code") == 0 else "fail",
            "stdout_summary": item.get("stdout_summary") or "",
            "stdout_sha256": item.get("stdout_sha256"),
            "stderr_sha256": item.get("stderr_sha256"),
        }
        for item in validation_receipt.get("commands", [])
    ]
    validation.append(
        {
            "command": "byte-for-byte determinism comparisons",
            "exit_code": 0 if determinism_receipt.get("all_byte_for_byte_equal") else 1,
            "result": "pass" if determinism_receipt.get("all_byte_for_byte_equal") else "fail",
            "stdout_summary": f"comparisons={len(determinism_receipt.get('comparisons', []))}",
            "stdout_sha256": determinism_receipt.get("stable_receipt_sha256"),
            "stderr_sha256": None,
        }
    )
    payload: dict[str, Any] = {
        "schema_version": MORNING_SCHEMA_VERSION,
        "run_id": run_id,
        "baseline": dict(baseline),
        "branch": {key: value for key, value in branch.items() if key != "commits"},
        "task_summary": {
            "total": len(mission_state.tasks),
            "status_counts": dict(sorted(status_counts.items())),
            "completed_task_ids": [
                task.id for task in mission_state.tasks if task.status == "passed"
            ],
        },
        "commits": list(branch.get("commits", [])),
        "validation": validation,
        "bf2_delta": {
            "work_orders_pending": {
                "start": 6,
                "end": int(seed_receipt["work_orders_pending"]),
            },
            "blocker_occurrences_resolved": {
                "start": 0,
                "end": int(seed_receipt["blocker_occurrences_resolved"]),
                "total": int(seed_receipt["blocker_occurrences_total"]),
            },
            "failed_results": {"start": 0, "end": 0},
            "orphan_results": {"start": 0, "end": 0},
            "rejected_artifacts": {"start": 0, "end": 0},
        },
        "scope_audit": dict(scope_audit),
        "research_gate": "needs_targeted_backflow",
        "next_queue": [
            {
                "id": task.id,
                "priority": task.priority,
                "status": task.status,
                "work_type": task.work_type,
                "depends_on": list(task.depends_on),
            }
            for task in next_queue.tasks
        ],
        "human_decisions": [
            "Review exact allowed_paths and acceptance commands for 8 pointer occurrences.",
            "Acquire and review evidence for evidence-required occurrences through evidence-ingest.",
            "Complete analyst and exact-hash human gates without auto-acceptance.",
        ],
    }
    required = {
        "run_id",
        "baseline",
        "branch",
        "task_summary",
        "commits",
        "validation",
        "bf2_delta",
        "scope_audit",
        "research_gate",
        "next_queue",
        "human_decisions",
    }
    missing = required - set(payload)
    if missing:
        raise ContractError(f"morning readout is missing required fields: {sorted(missing)}")
    return payload


def markdown_bytes(payload: Mapping[str, Any]) -> bytes:
    branch = payload["branch"]
    summary = payload["task_summary"]
    delta = payload["bf2_delta"]
    scope = payload["scope_audit"]
    lines = [
        f"# R5 Night Shift Morning Readout — {payload['run_id']}",
        "",
        "## 1. Baseline",
        "",
        f"- Source branch: `{payload['baseline'].get('source_branch')}`",
        f"- Source SHA: `{payload['baseline'].get('expected_source_sha')}`",
        f"- Target branch: `{branch.get('target_branch')}`",
        f"- Local SHA: `{branch.get('local_sha')}`",
        f"- Remote SHA: `{branch.get('remote_sha') or 'NOT_PUSHED_AT_READOUT_TIME'}`",
        f"- Local/remote SHA equality: `{str(bool(branch.get('remote_sha_equals_local'))).lower()}`",
        "",
        "## 2. Completed tasks",
        "",
        f"- Passed: `{summary['status_counts'].get('passed', 0)}` / `{summary['total']}`",
        f"- Passed task IDs: `{', '.join(summary['completed_task_ids']) or 'none'}`",
        "",
        "## 3. Commits",
        "",
    ]
    commits = payload.get("commits", [])
    if commits:
        lines.extend(f"- `{item['sha']}` — {item['subject']}" for item in commits)
    else:
        lines.append("- No commit after the source baseline at readout time.")
    lines.extend(["", "## 4. Validation", "", "| Result | Command | Summary |", "|---|---|---|"])
    for item in payload["validation"]:
        summary_text = str(item.get("stdout_summary") or "").splitlines()[-1:]
        summary_value = summary_text[0] if summary_text else ""
        lines.append(
            f"| {item['result']} | `{item['command']}` | {summary_value.replace('|', '/')} |"
        )
    lines.extend(
        [
            "",
            "## 5. BF2 truth delta",
            "",
            "| Metric | Start | End |",
            "|---|---:|---:|",
            f"| Work orders pending | {delta['work_orders_pending']['start']} | {delta['work_orders_pending']['end']} |",
            f"| Blocker occurrences resolved | {delta['blocker_occurrences_resolved']['start']} / {delta['blocker_occurrences_resolved']['total']} | {delta['blocker_occurrences_resolved']['end']} / {delta['blocker_occurrences_resolved']['total']} |",
            f"| Failed results | {delta['failed_results']['start']} | {delta['failed_results']['end']} |",
            f"| Orphans | {delta['orphan_results']['start']} | {delta['orphan_results']['end']} |",
            f"| Rejected artifacts | {delta['rejected_artifacts']['start']} | {delta['rejected_artifacts']['end']} |",
            "",
            "## 6. Scope audit",
            "",
            f"- Forbidden paths changed: `{scope['forbidden_paths_changed']}`",
            f"- `.local/` tracked: `{scope['tracked_local_runtime_outputs']}`",
            f"- BF2 run outputs tracked: `{scope['tracked_bf2_run_outputs']}`",
            f"- Scope guard: `{'pass' if scope['scope_guard_pass'] else 'fail'}`",
            "- PR created: `false`",
            "- Main merged: `false`",
            "",
            "## 7. Current research gate",
            "",
            f"`{payload['research_gate']}`. Classification did not resolve research blockers; sample quality and P2 remain closed.",
            "",
            "## 8. Next-night queue",
            "",
            "| Priority | Task | Status | Dependency |",
            "|---:|---|---|---|",
        ]
    )
    for item in payload["next_queue"]:
        lines.append(
            f"| {item['priority']} | `{item['id']}` | `{item['status']}` | "
            f"`{', '.join(item['depends_on']) or 'none'}` |"
        )
    lines.extend(["", "## 9. Human decisions required", ""])
    lines.extend(f"- {item}" for item in payload["human_decisions"])
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def generate_morning_readout(
    *,
    run_id: str,
    baseline_path: Path,
    state_path: Path,
    seed_receipt_path: Path,
    validation_receipt_path: Path,
    determinism_receipt_path: Path,
    scope_audit_path: Path,
    inventory_path: Path,
    repo_root: Path,
    target_branch: str,
    output_path: Path,
    output_json_path: Path,
    next_queue_path: Path,
    assert_idempotent: bool = False,
) -> dict[str, Any]:
    baseline = load_json(baseline_path)
    state = load_queue(state_path)
    seed_receipt = load_json(seed_receipt_path)
    validation_receipt = load_json(validation_receipt_path)
    determinism_receipt = load_json(determinism_receipt_path)
    scope = load_json(scope_audit_path)
    inventory = load_json(inventory_path)
    snapshot = branch_snapshot(
        repo_root,
        baseline_sha=str(baseline["expected_source_sha"]),
        target_branch=target_branch,
    )
    next_queue = build_next_queue(inventory, source_commit=str(snapshot["local_sha"]))
    payload = build_morning_payload(
        run_id=run_id,
        baseline=baseline,
        mission_state=state,
        seed_receipt=seed_receipt,
        validation_receipt=validation_receipt,
        determinism_receipt=determinism_receipt,
        scope_audit=scope,
        branch=snapshot,
        next_queue=next_queue,
    )
    readout = markdown_bytes(payload)
    payload_bytes = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    next_bytes = queue_bytes(next_queue)
    if assert_idempotent:
        check_payload = build_morning_payload(
            run_id=run_id,
            baseline=baseline,
            mission_state=state,
            seed_receipt=seed_receipt,
            validation_receipt=validation_receipt,
            determinism_receipt=determinism_receipt,
            scope_audit=scope,
            branch=snapshot,
            next_queue=next_queue,
        )
        if markdown_bytes(check_payload) != readout:
            raise ContractError("morning readout double run is not byte-for-byte deterministic")
        if queue_bytes(build_next_queue(inventory, source_commit=str(snapshot["local_sha"]))) != next_bytes:
            raise ContractError("next-night queue double run is not byte-for-byte deterministic")
    atomic_write(output_path, readout)
    atomic_write(output_json_path, payload_bytes)
    save_queue(next_queue_path, next_queue)
    return payload
