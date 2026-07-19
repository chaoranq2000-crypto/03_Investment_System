"""Command-line entrypoints for queue inspection and deterministic validation."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

from .models import ContractError
from .lock import LockError, RunLock
from .models import QueueDocument, Task
from .queue import (
    atomic_write,
    claiming_open,
    dependencies_passed,
    load_queue,
    queue_bytes,
    ready_tasks,
    save_queue,
)
from .receipts import (
    canonical_json_bytes,
    execute_acceptance,
    sha256_bytes,
    write_receipt,
    write_validation_report,
)
from .bf2_seed import seed_bf2
from .readout import (
    build_scope_audit,
    compare_files,
    generate_morning_readout,
    write_json as write_readout_json,
)


STATE_METADATA_SCHEMA_VERSION = "r5_night_shift_state_metadata_v1"
ALLOWED_BLOCK_STATUSES = (
    "dependency_blocked",
    "evidence_required",
    "human_gate",
    "skipped_cutoff",
)


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"--at: invalid ISO-8601 datetime {value!r}") from exc


def _git_branch(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "branch", "--show-current"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode:
        raise ContractError(f"cannot resolve current branch: {completed.stderr.strip()}")
    return completed.stdout.strip()


def metadata_path_for(state_path: Path) -> Path:
    return state_path.with_name(f"{state_path.stem}_metadata.json")


def load_metadata(state_path: Path, *, run_id: str) -> dict[str, Any]:
    path = metadata_path_for(state_path)
    if not path.exists():
        return {
            "schema_version": STATE_METADATA_SCHEMA_VERSION,
            "run_id": run_id,
            "tasks": {},
        }
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"state metadata[{path}]: cannot read JSON: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != STATE_METADATA_SCHEMA_VERSION:
        raise ContractError(f"state metadata[{path}]: invalid schema version")
    if value.get("run_id") != run_id:
        raise ContractError(
            f"state metadata[{path}]: run ID mismatch {value.get('run_id')!r} != {run_id!r}"
        )
    if not isinstance(value.get("tasks"), dict):
        raise ContractError(f"state metadata[{path}].tasks: must be an object")
    return value


def save_metadata(state_path: Path, metadata: dict[str, Any]) -> None:
    payload = (
        json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    atomic_write(metadata_path_for(state_path), payload)


def initialize_state(source_queue: Path, state_path: Path, *, run_id: str) -> QueueDocument:
    queue = load_queue(source_queue)
    if state_path.exists():
        existing = load_queue(state_path)
        if existing.mission_id != queue.mission_id:
            raise ContractError(
                f"state[{state_path}]: existing mission {existing.mission_id!r} "
                f"does not match {queue.mission_id!r}"
            )
        load_metadata(state_path, run_id=run_id)
        return existing
    save_queue(state_path, queue)
    save_metadata(
        state_path,
        {
            "schema_version": STATE_METADATA_SCHEMA_VERSION,
            "run_id": run_id,
            "tasks": {},
        },
    )
    return queue


def _iso_now(value: datetime | None) -> datetime:
    current = value or datetime.now(tz=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current


def _refresh_ready(queue: QueueDocument, now: datetime) -> QueueDocument:
    if not claiming_open(queue.run_window, now):
        return queue
    result = queue
    for task in queue.tasks:
        if task.status == "pending" and dependencies_passed(task, result) and not task.human_gate:
            result = result.replace_task(task.with_status("ready"))
    return result


def _transition_target(
    task: Task,
    *,
    action: str,
    queue: QueueDocument,
    metadata: dict[str, Any],
    now: datetime,
    block_status: str | None,
    terminal: bool,
) -> str:
    if action == "claim":
        if task.status not in {"pending", "ready"}:
            raise ContractError(
                f"task[{task.id}]: claim requires pending/ready, got {task.status}"
            )
        if not dependencies_passed(task, queue):
            raise ContractError(f"task[{task.id}]: dependencies are not passed")
        if not claiming_open(queue.run_window, now):
            raise ContractError(f"task[{task.id}]: claim cutoff has passed")
        return "claimed"
    if action == "start":
        if task.status != "claimed":
            raise ContractError(f"task[{task.id}]: start requires claimed, got {task.status}")
        return "running"
    if action == "complete":
        if task.status != "running":
            raise ContractError(f"task[{task.id}]: complete requires running, got {task.status}")
        return "passed"
    if action == "fail":
        if task.status not in {"claimed", "running"}:
            raise ContractError(
                f"task[{task.id}]: fail requires claimed/running, got {task.status}"
            )
        attempts = int(metadata.get("tasks", {}).get(task.id, {}).get("attempts", 0))
        return "failed_terminal" if terminal or attempts > task.retry_limit else "failed_retryable"
    if action == "block":
        if block_status not in ALLOWED_BLOCK_STATUSES:
            raise ContractError(
                f"task[{task.id}]: block status must be one of {', '.join(ALLOWED_BLOCK_STATUSES)}"
            )
        if task.status not in {"pending", "ready", "claimed", "running"}:
            raise ContractError(
                f"task[{task.id}]: block is not allowed from {task.status}"
            )
        return str(block_status)
    if action == "resume":
        if task.status not in {"failed_retryable", "dependency_blocked"}:
            raise ContractError(
                f"task[{task.id}]: resume requires failed_retryable/dependency_blocked, "
                f"got {task.status}"
            )
        if not dependencies_passed(task, queue):
            raise ContractError(f"task[{task.id}]: dependencies are not passed")
        if not claiming_open(queue.run_window, now):
            raise ContractError(f"task[{task.id}]: resume cutoff has passed")
        return "ready"
    raise ContractError(f"task[{task.id}]: unsupported action {action!r}")


def transition_state(
    state_path: Path,
    *,
    task_id: str,
    action: str,
    run_id: str,
    actor: str,
    at: datetime | None = None,
    reason: str = "",
    block_status: str | None = None,
    terminal: bool = False,
    lock_path: Path | None = None,
    stale_after_seconds: int = 900,
) -> tuple[QueueDocument, Task]:
    now = _iso_now(at)
    repo_root = Path(__file__).resolve().parents[3]
    lock = RunLock(
        lock_path or state_path.parent / "run.lock",
        stale_after=timedelta(seconds=stale_after_seconds),
    )
    branch = _git_branch(repo_root)
    lock.acquire(run_id=run_id, branch=branch, recover_stale=True)
    try:
        queue = load_queue(state_path)
        metadata = load_metadata(state_path, run_id=run_id)
        task = queue.task_map.get(task_id)
        if task is None:
            raise ContractError(f"queue.tasks[{task_id}]: task does not exist")
        target = _transition_target(
            task,
            action=action,
            queue=queue,
            metadata=metadata,
            now=now,
            block_status=block_status,
            terminal=terminal,
        )
        entry = metadata["tasks"].setdefault(task_id, {"attempts": 0, "history": []})
        if not isinstance(entry, dict) or not isinstance(entry.get("history"), list):
            raise ContractError(f"state metadata task[{task_id}] is malformed")
        if action == "claim":
            entry["attempts"] = int(entry.get("attempts", 0)) + 1
        entry["history"].append(
            {
                "action": action,
                "actor": actor,
                "at": now.astimezone(timezone.utc).isoformat(),
                "from": task.status,
                "reason": reason,
                "to": target,
            }
        )
        updated_task = task.with_status(target)
        queue = queue.replace_task(updated_task)
        queue = _refresh_ready(queue, now)
        save_queue(state_path, queue)
        save_metadata(state_path, metadata)
        return queue, queue.task_map[task_id]
    finally:
        lock.release(run_id)


def run_safe_pilot(
    *,
    queue_path: Path,
    inventory_path: Path,
    run_id: str,
    repo_root: Path,
    receipts_dir: Path,
    report_path: Path,
    backflow_path: Path,
) -> dict[str, Any]:
    queue = load_queue(queue_path)
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"BF2 inventory[{inventory_path}]: cannot read JSON: {exc}") from exc
    if not isinstance(inventory, dict) or not isinstance(inventory.get("summary"), dict):
        raise ContractError("BF2 inventory is missing its summary")
    summary = inventory["summary"]
    if summary.get("blocker_occurrences_resolved") != 0:
        raise ContractError("safe pilot refuses an input that does not preserve zero resolved blockers")

    engineering_tasks = [task for task in queue.tasks if task.work_type == "engineering_local"]
    eligible = [
        task
        for task in engineering_tasks
        if task.status in {"pending", "ready"}
        and task.allowed_paths
        and task.acceptance_commands
        and not task.human_gate
    ]
    eligible.sort(key=lambda task: (-task.priority, task.id))
    receipts_dir.mkdir(parents=True, exist_ok=True)
    if eligible:
        selected = eligible[0]
        receipt_path = receipts_dir / f"{selected.id}.json"
        receipt = execute_acceptance(
            run_id=run_id,
            task_id=selected.id,
            attempt=1,
            executor="codex",
            cwd=repo_root,
            commands=selected.acceptance_commands,
            artifacts=selected.required_artifacts,
            receipt_path=receipt_path,
            blocker_claimed=1,
            blocker_resolved=0,
            blocker_unchanged=1,
            reason="safe pilot acceptance run; research blocker remains unresolved unless separately evidenced",
        )
        outcome = {
            "schema_version": "r5_night_shift_safe_pilot_v1",
            "run_id": run_id,
            "outcome": "pilot_acceptance_executed",
            "selected_task_id": selected.id,
            "receipt_path": receipt_path.as_posix(),
            "terminal_status": receipt["terminal_status"],
            "blocker_occurrences_resolved": 0,
            "research_gate": "needs_targeted_backflow",
            "sample_quality_allowed": False,
            "p2_allowed": False,
        }
    else:
        reasons = Counter()
        for task in engineering_tasks:
            if task.status not in {"pending", "ready"}:
                reasons["status_not_claimable"] += 1
            if not task.allowed_paths:
                reasons["missing_allowed_paths"] += 1
            if not task.acceptance_commands:
                reasons["missing_acceptance_commands"] += 1
        outcome = {
            "schema_version": "r5_night_shift_safe_pilot_v1",
            "run_id": run_id,
            "outcome": "no_safe_pilot",
            "engineering_local_occurrence_count": len(engineering_tasks),
            "eligible_task_count": 0,
            "ineligibility_reasons": dict(sorted(reasons.items())),
            "blocker_occurrences_claimed": 0,
            "blocker_occurrences_resolved": 0,
            "blocker_occurrences_unchanged": int(summary["blocker_occurrences_total"]),
            "work_orders_pending": int(summary["work_orders_pending"]),
            "research_gate": "needs_targeted_backflow",
            "sample_quality_allowed": False,
            "p2_allowed": False,
            "canonical_state_allowed": False,
        }
        outcome["stable_receipt_sha256"] = sha256_bytes(canonical_json_bytes(outcome))
        write_receipt(receipts_dir / "no_safe_pilot.json", outcome)

    report_lines = [
        "# R5 night-shift safe pilot result",
        "",
        f"- Run ID: `{run_id}`",
        f"- Outcome: `{outcome['outcome']}`",
        f"- Engineering-local occurrences: `{len(engineering_tasks)}`",
        f"- Eligible tasks: `{len(eligible)}`",
        "- Resolved blocker occurrences: `0`",
        "- Research gate: `needs_targeted_backflow`",
        "- Canonical/sample-quality/P2 mutation: `false`",
        "",
    ]
    if not eligible:
        report_lines.extend(
            [
                "The eight pointer-oriented occurrences remain ineligible because the source",
                "contracts provide neither an allowed-path whitelist nor executable acceptance",
                "commands.  Treating them as executable would widen scope by guessing.",
                "",
            ]
        )
    atomic_write(report_path, "\n".join(report_lines).encode("utf-8"))

    backflow_lines = [
        "# No-safe-pilot backflow packet",
        "",
        "- Owner: `research-orchestrator` with the source work-order owner skill",
        "- Severity: `medium`",
        "- Status: `dependency_blocked`",
        "- Missing contract fields: `allowed_paths`, executable `acceptance_commands`",
        "- Next step: issue a reviewed, occurrence-scoped engineering work order with exact paths and tests",
        "- Research blocker resolved: `false`",
        "- Canonical/sample-quality/P2 mutation: `false`",
        "",
    ]
    atomic_write(backflow_path, "\n".join(backflow_lines).encode("utf-8"))
    return outcome


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate a queue contract")
    validate.add_argument("--queue", type=Path, required=True)

    list_ready = commands.add_parser("list-ready", help="list claimable tasks")
    list_ready.add_argument("--queue", type=Path, required=True)
    list_ready.add_argument("--at")
    list_ready.add_argument("--json", action="store_true")

    show = commands.add_parser("show", help="show one task")
    show.add_argument("--queue", type=Path, required=True)
    show.add_argument("--task-id", required=True)

    canonicalize = commands.add_parser(
        "canonicalize", help="write deterministic queue YAML"
    )
    canonicalize.add_argument("--queue", type=Path, required=True)
    canonicalize.add_argument("--output", type=Path, required=True)

    initialize = commands.add_parser("init", help="initialize an atomic runtime state")
    initialize.add_argument("--queue", type=Path, required=True)
    initialize.add_argument("--state", type=Path, required=True)
    initialize.add_argument("--run-id", required=True)

    for name in ("claim", "start", "complete", "fail", "block", "resume"):
        command = commands.add_parser(name, help=f"{name} one task")
        command.add_argument("--state", type=Path, required=True)
        command.add_argument("--task-id", required=True)
        command.add_argument("--run-id", required=True)
        command.add_argument("--actor", default="codex")
        command.add_argument("--at")
        command.add_argument("--reason", default="")
        command.add_argument("--lock", type=Path)
        command.add_argument("--stale-after-seconds", type=int, default=900)
        if name == "fail":
            command.add_argument("--terminal", action="store_true")
        if name == "block":
            command.add_argument("--status", choices=ALLOWED_BLOCK_STATUSES, required=True)

    release = commands.add_parser("release-lock", help="release a lock owned by this run")
    release.add_argument("--lock", type=Path, required=True)
    release.add_argument("--run-id", required=True)

    acceptance = commands.add_parser(
        "run-acceptance", help="execute trusted task acceptance commands and write a receipt"
    )
    acceptance.add_argument("--queue", type=Path, required=True)
    acceptance.add_argument("--task-id", required=True)
    acceptance.add_argument("--run-id", required=True)
    acceptance.add_argument("--attempt", type=int, default=1)
    acceptance.add_argument("--executor", default="codex")
    acceptance.add_argument("--cwd", type=Path, required=True)
    acceptance.add_argument("--receipt", type=Path, required=True)
    acceptance.add_argument("--report", type=Path)
    acceptance.add_argument("--artifact", action="append", default=[])
    acceptance.add_argument("--failure-status", default="failed_retryable")
    acceptance.add_argument("--reason", default="")
    acceptance.add_argument("--blocker-claimed", type=int, default=0)
    acceptance.add_argument("--blocker-resolved", type=int, default=0)
    acceptance.add_argument("--blocker-unchanged", type=int, default=0)

    seed = commands.add_parser(
        "seed-bf2", help="inventory and deterministically seed immutable BF2 inputs"
    )
    seed.add_argument("--input-manifest", type=Path, required=True)
    seed.add_argument("--repo-root", type=Path, required=True)
    seed.add_argument("--output", type=Path, required=True)
    seed.add_argument("--inventory-output", type=Path, required=True)
    seed.add_argument("--receipt-output", type=Path, required=True)
    seed.add_argument("--summary-output", type=Path, required=True)
    seed.add_argument("--compatibility-output", type=Path, required=True)
    seed.add_argument("--expected-work-orders", type=int, default=6)
    seed.add_argument("--expected-blockers", type=int, default=63)
    seed.add_argument("--assert-idempotent", action="store_true")

    pilot = commands.add_parser(
        "safe-pilot", help="run the highest safe engineering pilot or record no-safe-pilot"
    )
    pilot.add_argument("--queue", type=Path, required=True)
    pilot.add_argument("--inventory", type=Path, required=True)
    pilot.add_argument("--run-id", required=True)
    pilot.add_argument("--repo-root", type=Path, required=True)
    pilot.add_argument("--receipts-dir", type=Path, required=True)
    pilot.add_argument("--report", type=Path, required=True)
    pilot.add_argument("--backflow", type=Path, required=True)

    scope = commands.add_parser("scope-audit", help="audit changed and tracked mission paths")
    scope.add_argument("--repo-root", type=Path, required=True)
    scope.add_argument("--baseline-sha", required=True)
    scope.add_argument("--output", type=Path, required=True)

    compare = commands.add_parser(
        "compare-files", help="write a byte-for-byte determinism receipt"
    )
    compare.add_argument("--pair", nargs=2, action="append", required=True)
    compare.add_argument("--receipt", type=Path, required=True)

    readout = commands.add_parser(
        "morning-readout", help="generate deterministic morning readout and next queue"
    )
    readout.add_argument("--run-id", required=True)
    readout.add_argument("--baseline", type=Path, required=True)
    readout.add_argument("--state", type=Path, required=True)
    readout.add_argument("--seed-receipt", type=Path, required=True)
    readout.add_argument("--validation-receipt", type=Path, required=True)
    readout.add_argument("--determinism-receipt", type=Path, required=True)
    readout.add_argument("--scope-audit", type=Path, required=True)
    readout.add_argument("--inventory", type=Path, required=True)
    readout.add_argument("--repo-root", type=Path, required=True)
    readout.add_argument("--target-branch", required=True)
    readout.add_argument("--output", type=Path, required=True)
    readout.add_argument("--output-json", type=Path, required=True)
    readout.add_argument("--next-queue", type=Path, required=True)
    readout.add_argument("--assert-idempotent", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            queue = initialize_state(args.queue, args.state, run_id=args.run_id)
            print(f"OK: initialized state={args.state} tasks={len(queue.tasks)}")
            return 0
        if args.command in {"claim", "start", "complete", "fail", "block", "resume"}:
            _, task = transition_state(
                args.state,
                task_id=args.task_id,
                action=args.command,
                run_id=args.run_id,
                actor=args.actor,
                at=_parse_datetime(args.at),
                reason=args.reason,
                block_status=getattr(args, "status", None),
                terminal=getattr(args, "terminal", False),
                lock_path=args.lock,
                stale_after_seconds=args.stale_after_seconds,
            )
            print(f"OK: task={task.id} status={task.status}")
            return 0
        if args.command == "release-lock":
            RunLock(args.lock).release(args.run_id)
            print(f"OK: released {args.lock}")
            return 0
        if args.command == "run-acceptance":
            queue = load_queue(args.queue)
            task = queue.task_map.get(args.task_id)
            if task is None:
                raise ContractError(f"queue.tasks[{args.task_id}]: task does not exist")
            artifacts = args.artifact or list(task.required_artifacts)
            receipt = execute_acceptance(
                run_id=args.run_id,
                task_id=task.id,
                attempt=args.attempt,
                executor=args.executor,
                cwd=args.cwd,
                commands=task.acceptance_commands,
                artifacts=artifacts,
                receipt_path=args.receipt,
                failure_status=args.failure_status,
                reason=args.reason,
                blocker_claimed=args.blocker_claimed,
                blocker_resolved=args.blocker_resolved,
                blocker_unchanged=args.blocker_unchanged,
            )
            if args.report:
                write_validation_report(args.report, receipt, receipt_path=args.receipt)
            print(
                f"OK: task={task.id} status={receipt['terminal_status']} "
                f"receipt={args.receipt}"
            )
            return 0 if receipt["terminal_status"] == "passed" else 1
        if args.command == "seed-bf2":
            receipt = seed_bf2(
                manifest_path=args.input_manifest,
                repo_root=args.repo_root,
                output_path=args.output,
                inventory_output=args.inventory_output,
                receipt_output=args.receipt_output,
                summary_output=args.summary_output,
                compatibility_output=args.compatibility_output,
                expected_work_orders=args.expected_work_orders,
                expected_blockers=args.expected_blockers,
                assert_idempotent=args.assert_idempotent,
            )
            print(
                "OK: "
                f"work_orders={receipt['work_orders_total']} "
                f"blockers={receipt['blocker_occurrences_total']} "
                f"resolved={receipt['blocker_occurrences_resolved']} "
                f"tasks={receipt['seeded_task_count']} "
                f"idempotency={receipt['idempotency']}"
            )
            return 0
        if args.command == "safe-pilot":
            outcome = run_safe_pilot(
                queue_path=args.queue,
                inventory_path=args.inventory,
                run_id=args.run_id,
                repo_root=args.repo_root,
                receipts_dir=args.receipts_dir,
                report_path=args.report,
                backflow_path=args.backflow,
            )
            print(
                f"OK: outcome={outcome['outcome']} "
                f"resolved={outcome['blocker_occurrences_resolved']}"
            )
            return 0
        if args.command == "scope-audit":
            audit = build_scope_audit(args.repo_root, baseline_sha=args.baseline_sha)
            write_readout_json(args.output, audit)
            print(
                f"OK: scope_guard={audit['scope_guard_pass']} "
                f"forbidden={audit['forbidden_paths_changed']}"
            )
            return 0 if audit["scope_guard_pass"] else 1
        if args.command == "compare-files":
            receipt = compare_files(
                [(Path(left), Path(right)) for left, right in args.pair], args.receipt
            )
            print(
                f"OK: comparisons={len(receipt['comparisons'])} "
                f"equal={receipt['all_byte_for_byte_equal']}"
            )
            return 0
        if args.command == "morning-readout":
            payload = generate_morning_readout(
                run_id=args.run_id,
                baseline_path=args.baseline,
                state_path=args.state,
                seed_receipt_path=args.seed_receipt,
                validation_receipt_path=args.validation_receipt,
                determinism_receipt_path=args.determinism_receipt,
                scope_audit_path=args.scope_audit,
                inventory_path=args.inventory,
                repo_root=args.repo_root,
                target_branch=args.target_branch,
                output_path=args.output,
                output_json_path=args.output_json,
                next_queue_path=args.next_queue,
                assert_idempotent=args.assert_idempotent,
            )
            print(
                f"OK: run={payload['run_id']} gate={payload['research_gate']} "
                f"output={args.output}"
            )
            return 0

        queue = load_queue(args.queue)
        if args.command == "validate":
            print(f"OK: mission={queue.mission_id} tasks={len(queue.tasks)}")
            return 0
        if args.command == "list-ready":
            tasks = ready_tasks(queue, _parse_datetime(args.at))
            if args.json:
                print(
                    json.dumps(
                        [task.to_mapping() for task in tasks],
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
            else:
                for task in tasks:
                    print(f"{task.id}\t{task.priority}\t{task.title}")
            return 0
        if args.command == "show":
            task = queue.task_map.get(args.task_id)
            if task is None:
                raise ContractError(f"queue.tasks[{args.task_id}]: task does not exist")
            print(json.dumps(task.to_mapping(), ensure_ascii=False, sort_keys=True, indent=2))
            return 0
        if args.command == "canonicalize":
            save_queue(args.output, queue)
            if args.output.read_bytes() != queue_bytes(queue):
                raise ContractError("canonical queue write did not round-trip byte-for-byte")
            print(f"OK: wrote {args.output}")
            return 0
    except (ContractError, LockError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    return 2
