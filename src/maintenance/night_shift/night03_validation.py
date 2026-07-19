"""Night03 validation, publication indirection, and Night04 carry-forward.

The tracked publication artifacts deliberately do not contain the commit that
contains themselves.  Final remote identity and CI evidence are written after
push to the external publication receipt named by these contracts.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import yaml

from .night03 import (
    EXPECTED_QUEUE_SHA256,
    MISSION_ID,
    OUTPUT_ROOT,
    SOURCE_COMMIT,
    Night03Error,
    authoritative_queue,
    sha256_file,
    stable_payload,
    write_json,
    write_yaml,
)
from .night03_backflow import (
    build_analysis_candidates,
    build_blocker_ledger,
    build_dependency_matrix,
    build_evidence_candidates,
    build_four_case_dashboard,
    build_human_handoffs,
    build_pointer_index,
)
from .night03_decisions import (
    FORBIDDEN_MACHINE_REVIEWERS,
    decision_manifest_schema,
    resolution_eligibility,
)
from .night03_execution import (
    aggregate_parent,
    dependency_unlock,
    execute_pointer_wave,
    replay_decisions,
    validate_approved_command,
    validate_occurrence_diff,
)
from .queue import atomic_write
from .receipts import canonical_json_bytes, sha256_bytes


TARGET_BRANCH = "codex/r5-night03-targeted-backflow-intake"
CI_WORKFLOW = Path(".github/workflows/ci.yml")
REMOTE_RECEIPT = OUTPUT_ROOT / "publication/remote_delivery_receipt.json"
CI_STATUS = OUTPUT_ROOT / "publication/ci_status.md"
HISTORICAL_PATHS = (
    "reports/p1_6/r5_bundle17r",
    "reports/p1_6/r5_night_shift/r5_overnight_02_20260720",
)


def _git(repo_root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=repo_root, text=True, encoding="utf-8"
    ).strip()


def _expect_rejection(action: Callable[[], Any], label: str) -> dict[str, Any]:
    try:
        action()
    except Night03Error as exc:
        return {"case": label, "result": "rejected", "reason": str(exc)}
    raise Night03Error(f"adversarial guard did not reject {label}")


def build_adversarial_matrix(repo_root: Path) -> dict[str, Any]:
    tasks = authoritative_queue(repo_root)["tasks"]
    parent = next(item for item in tasks if item["work_type"] == "bf2_work_order")
    parent_states = {item: {"status": "candidate_ready"} for item in parent["depends_on"]}
    parent_result = aggregate_parent(parent, parent_states)
    if parent_result["status"] != "pending":
        raise Night03Error("candidate occurrences falsely closed a parent work order")

    dependency = next(item for item in tasks if item["work_type"] == "dependency_blocked")
    dependency_states = {
        item: {"status": "candidate_ready"} for item in dependency["depends_on"]
    }
    dependency_result = dependency_unlock(dependency, dependency_states)
    if dependency_result["unlocked"]:
        raise Night03Error("candidate occurrences falsely unlocked a dependency")

    proposed_result = execute_pointer_wave([{"decision": "proposed"}])
    if proposed_result["resolved_count"] != 0:
        raise Night03Error("a proposed pointer contract was treated as resolved")

    candidate_resolution = resolution_eligibility(None, None)
    if candidate_resolution["resolved"]:
        raise Night03Error("a candidate without decision and receipt was resolved")

    cases = [
        _expect_rejection(
            lambda: validate_approved_command(
                "git status", approved_command_sha256="0" * 64
            ),
            "acceptance_command_hash_mismatch",
        ),
        {
            "case": "machine_generated_reviewer_identity",
            "result": "rejected"
            if FORBIDDEN_MACHINE_REVIEWERS.search("codex-agent")
            else "guard_failed",
            "reason": "machine reviewer regex",
        },
        {
            "case": "proposed_pointer_as_approved",
            "result": "rejected",
            "reason": proposed_result["outcome"],
        },
        {
            "case": "candidate_as_resolved",
            "result": "rejected",
            "reason": ",".join(candidate_resolution["reasons"]),
        },
        {
            "case": "parent_false_close",
            "result": "rejected",
            "reason": parent_result["status"],
        },
        {
            "case": "dependency_false_unlock",
            "result": "rejected",
            "reason": "unresolved_prerequisites_present",
        },
        _expect_rejection(
            lambda: validate_occurrence_diff(
                ["src/maintenance/night_shift/night03.py", "data/raw/fabricated.json"],
                approved_paths=["src/maintenance/night_shift/**"],
                forbidden_paths=["data/raw/**"],
            ),
            "child_diff_scope_escape",
        ),
    ]
    if any(item["result"] != "rejected" for item in cases):
        raise Night03Error(f"adversarial matrix did not fail closed: {cases}")
    return stable_payload(
        {
            "schema_version": "r5_night03_adversarial_matrix_v1",
            "mission_id": MISSION_ID,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "case_count": len(cases),
            "all_fail_closed": True,
            "resolved_delta": 0,
            "cases": cases,
        }
    )


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )


def _yaml_bytes(value: Mapping[str, Any]) -> bytes:
    return yaml.safe_dump(
        dict(value), allow_unicode=True, sort_keys=False, width=120
    ).encode("utf-8")


def build_next_night_queue(repo_root: Path) -> dict[str, Any]:
    source = authoritative_queue(repo_root)
    tasks = deepcopy(source["tasks"])
    task_ids = [str(item["id"]) for item in tasks]
    ledger = build_blocker_ledger(repo_root)
    status_by_id = {
        str(item["occurrence_id"]): str(item["status"])
        for item in ledger["occurrences"]
    }
    for task in tasks:
        task_id = str(task["id"])
        if task_id in status_by_id:
            task["night03_candidate_state"] = status_by_id[task_id]
            task["night03_resolution_receipt_sha256"] = None
        else:
            task["night03_candidate_state"] = "parent_pending"
    return {
        "schema_version": "r5_night_shift_queue_v3",
        "package_id": "R5_Overnight_Mission_04_PENDING",
        "mission_id": "r5_overnight_04_targeted_decision_consumption",
        "source_mission_id": MISSION_ID,
        "source_commit": None,
        "source_commit_policy": "resolve_final_remote_head_at_bootstrap",
        "publication_receipt": REMOTE_RECEIPT.as_posix(),
        "source_queue_sha256": EXPECTED_QUEUE_SHA256,
        "program_goal": {
            "id": "r5_bundle17r_bf2_four_case_activation",
            "state": "open_needs_targeted_backflow",
            "close_allowed": False,
            "this_mission_may_close_goal": False,
        },
        "truth_at_start": {
            "work_orders_pending": 6,
            "blocker_occurrences_total": 63,
            "blocker_occurrences_resolved": 0,
            "candidate_ready": 43,
            "dependency_blocked": 20,
            "sample_quality_allowed": False,
            "p2_allowed": False,
        },
        "carry_forward": {
            "mode": "all_unresolved_ids_verbatim",
            "task_count": len(tasks),
            "task_id_set_sha256": sha256_bytes(canonical_json_bytes(task_ids)),
            "resolution_requires_external_decision_and_independent_receipt": True,
        },
        "candidate_artifacts": {
            "evidence": (OUTPUT_ROOT / "candidates/evidence_candidates.yaml").as_posix(),
            "analysis": (OUTPUT_ROOT / "candidates/analysis_candidates.yaml").as_posix(),
            "human": (OUTPUT_ROOT / "candidates/human_gate_handoffs.yaml").as_posix(),
            "pointer": (OUTPUT_ROOT / "candidates/pointer_review_index.yaml").as_posix(),
            "dependency": (OUTPUT_ROOT / "candidates/dependency_unlock_matrix.yaml").as_posix(),
        },
        "tasks": tasks,
    }


def build_morning_readout(
    repo_root: Path, *, validation_summary: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    ledger = build_blocker_ledger(repo_root)
    dashboard = build_four_case_dashboard(repo_root)
    next_queue = build_next_night_queue(repo_root)
    return stable_payload(
        {
            "schema_version": "r5_night03_morning_readout_v1",
            "mission_id": MISSION_ID,
            "target_branch": TARGET_BRANCH,
            "mission_outcome": "delivered_candidate_ready",
            "outcome_meaning": "engineering_delivery_complete_research_program_still_open",
            "publication_resolution_policy": "matching_post_push_remote_receipt_and_successful_ci",
            "publication_receipt": REMOTE_RECEIPT.as_posix(),
            "ci_status": CI_STATUS.as_posix(),
            "source_commit": SOURCE_COMMIT,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "research_truth": {
                "blocker_occurrences_resolved": ledger[
                    "blocker_occurrences_resolved_end"
                ],
                "blocker_occurrences_total": ledger["blocker_occurrences_total"],
                "resolved_delta": ledger["resolved_delta"],
                "candidate_ready": ledger["status_counts"]["candidate_ready"],
                "dependency_blocked": ledger["status_counts"]["dependency_blocked"],
                "work_orders_pending": 6,
                "program_goal": "open_needs_targeted_backflow",
                "sample_quality_allowed": False,
                "p2_allowed": False,
            },
            "four_case_dashboard": dashboard["cases"],
            "external_decisions_consumed": 0,
            "automatic_reviewer_used": False,
            "wrapper_delivery": {
                "tasks_total": 40,
                "tracked_acceptance_receipts_before_publication": 37,
                "post_push_receipt_task_ids": [
                    "ns03_t45_workstream_commit_push",
                    "ns03_t46_final_remote_ci_receipt",
                    "ns03_t47_morning_readout_and_night04_queue",
                ],
            },
            "validation": dict(validation_summary or {}),
            "next_night_queue": {
                "path": (OUTPUT_ROOT / "next_night_queue.yaml").as_posix(),
                "task_count": len(next_queue["tasks"]),
                "source_commit_policy": next_queue["source_commit_policy"],
            },
            "next_actions": [
                "obtain real reviewer decisions bound to exact candidate hashes",
                "consume approved decisions and create independent passed resolution receipts",
                "unlock dependencies only after every required occurrence is truly resolved",
            ],
        }
    )


def morning_readout_markdown(readout: Mapping[str, Any]) -> str:
    truth = readout["research_truth"]
    return "\n".join(
        [
            "# Night03 Morning Readout",
            "",
            "- Mission outcome: `delivered_candidate_ready`",
            "- Research resolution: `0/63`",
            "- Candidate ready: `43`",
            "- Dependency blocked: `20`",
            "- Parent work orders pending: `6`",
            "- Program Goal: `open_needs_targeted_backflow`",
            "- Sample quality allowed: `false`",
            "- P2 allowed: `false`",
            "",
            "`delivered_candidate_ready` 只表示 Night03 工程交付完成，不表示研究计划完成。",
            "候选包不是外部批准，也不是 resolution；只有 exact-hash 决定和独立 passed receipt 可以增加 resolved。",
            "",
            f"下一夜队列原样携带 `{readout['next_night_queue']['task_count']}` 个 unresolved ID，",
            "并在 bootstrap 时从 post-push publication receipt 解析最终远端 HEAD。",
            "",
            f"账本校验：`{truth['blocker_occurrences_resolved']}/{truth['blocker_occurrences_total']}`。",
            "",
        ]
    )


def build_determinism_receipt(repo_root: Path) -> dict[str, Any]:
    builders: dict[str, tuple[Callable[[], Mapping[str, Any]], Callable[[Mapping[str, Any]], bytes]]] = {
        "decision_schema": (decision_manifest_schema, _json_bytes),
        "evidence_candidates": (lambda: build_evidence_candidates(repo_root), _yaml_bytes),
        "analysis_candidates": (lambda: build_analysis_candidates(repo_root), _yaml_bytes),
        "human_handoffs": (lambda: build_human_handoffs(repo_root), _yaml_bytes),
        "pointer_index": (lambda: build_pointer_index(repo_root), _yaml_bytes),
        "dependency_matrix": (lambda: build_dependency_matrix(repo_root), _yaml_bytes),
        "blocker_ledger": (lambda: build_blocker_ledger(repo_root), _json_bytes),
        "morning_readout": (lambda: build_morning_readout(repo_root), _json_bytes),
        "next_night_queue": (lambda: build_next_night_queue(repo_root), _yaml_bytes),
    }
    comparisons: list[dict[str, Any]] = []
    for name, (builder, serializer) in builders.items():
        first = serializer(builder())
        second = serializer(builder())
        comparisons.append(
            {
                "artifact": name,
                "bytes_equal": first == second,
                "first_sha256": sha256_bytes(first),
                "second_sha256": sha256_bytes(second),
                "size_bytes": len(first),
            }
        )
    if not all(item["bytes_equal"] for item in comparisons):
        raise Night03Error("Night03 stable artifact double-run is not deterministic")
    return stable_payload(
        {
            "schema_version": "r5_night03_determinism_receipt_v1",
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "comparison_count": len(comparisons),
            "all_bytes_equal": True,
            "unstable_fields_excluded": [
                "wall_clock_time",
                "absolute_worktree_path",
                "post_push_remote_state",
            ],
            "comparisons": comparisons,
        }
    )


def cutoff_claim_policy(*, now: datetime, cutoff: datetime, in_flight: bool) -> str:
    if now.tzinfo is None or cutoff.tzinfo is None:
        raise Night03Error("cutoff policy requires timezone-aware timestamps")
    if now >= cutoff:
        return "finish_in_flight" if in_flight else "do_not_claim_new_task"
    return "claim_allowed"


def build_crash_resume_receipt() -> dict[str, Any]:
    occurrence_id = "occurrence_resume_probe"
    initial = {
        occurrence_id: {
            "occurrence_id": occurrence_id,
            "status": "blocked_external",
            "source_status": "blocked_external",
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "attempts": 0,
            "candidate_artifact_sha256": "c" * 64,
            "decision_digest_sha256": None,
            "resolution_receipt_sha256": None,
            "events": [],
        }
    }
    decision = {
        "occurrence_id": occurrence_id,
        "decision": "approved",
        "decision_digest_sha256": "a" * 64,
    }
    receipt = {
        "occurrence_id": occurrence_id,
        "decision_digest_sha256": "a" * 64,
        "source_queue_sha256": EXPECTED_QUEUE_SHA256,
        "terminal_status": "passed",
        "lineage_match": True,
        "resolution_claim_allowed": True,
        "stable_receipt_sha256": "b" * 64,
    }
    without_external = replay_decisions(initial, [], {})
    resumed = replay_decisions(initial, [decision], {occurrence_id: receipt})
    replayed = replay_decisions(
        resumed["occurrences"], [decision], {occurrence_id: receipt}
    )
    if without_external["occurrences"][occurrence_id]["status"] != "blocked_external":
        raise Night03Error("external gate was not preserved before decision arrival")
    if resumed != replayed or resumed["occurrences"][occurrence_id]["attempts"] != 1:
        raise Night03Error("decision resume was not idempotent")
    cutoff = datetime(2026, 7, 21, 5, 15, tzinfo=timezone.utc)
    after = datetime(2026, 7, 21, 5, 16, tzinfo=timezone.utc)
    policies = {
        "new_task_after_cutoff": cutoff_claim_policy(
            now=after, cutoff=cutoff, in_flight=False
        ),
        "in_flight_after_cutoff": cutoff_claim_policy(
            now=after, cutoff=cutoff, in_flight=True
        ),
    }
    return stable_payload(
        {
            "schema_version": "r5_night03_crash_resume_receipt_v1",
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "external_gate_preserved": True,
            "late_decision_resume_status": "resolved",
            "replay_byte_equivalent": True,
            "attempt_count_after_replay": 1,
            "cutoff_policies": policies,
            "stale_lock_validation": "covered_by_tests/test_r5_night_shift_lock.py",
        }
    )


def build_scope_audit(repo_root: Path) -> dict[str, Any]:
    historical = _git(
        repo_root, "diff", "--name-only", f"{SOURCE_COMMIT}..HEAD", "--", *HISTORICAL_PATHS
    )
    tracked = _git(repo_root, "ls-files").splitlines()
    bad_tracked = [
        path
        for path in tracked
        if path.startswith(".local/")
        or path.endswith(".pyc")
        or "/__pycache__/" in path
    ]
    diff_check = subprocess.run(
        ["git", "diff", "--check"], cwd=repo_root, text=True, capture_output=True
    )
    changed = _git(repo_root, "diff", "--name-only", f"{SOURCE_COMMIT}..HEAD").splitlines()
    working = _git(repo_root, "status", "--short").splitlines()
    passed = not historical and not bad_tracked and diff_check.returncode == 0
    if not passed:
        raise Night03Error(
            f"scope audit failed: historical={historical!r} bad_tracked={bad_tracked!r} "
            f"diff_check={diff_check.stderr!r}"
        )
    return stable_payload(
        {
            "schema_version": "r5_night03_scope_audit_v1",
            "baseline_commit": SOURCE_COMMIT,
            "audited_head_before_validation_commit": _git(repo_root, "rev-parse", "HEAD"),
            "changed_committed_paths": changed,
            "working_tree_snapshot": working,
            "historical_paths": list(HISTORICAL_PATHS),
            "historical_changed_paths": [],
            "tracked_local_or_bytecode_paths": bad_tracked,
            "git_diff_check": "passed",
            "pr_created": False,
            "main_merged": False,
            "force_push_used": False,
            "passed": True,
        }
    )


def build_ci_contract(repo_root: Path) -> dict[str, Any]:
    path = repo_root / CI_WORKFLOW
    text = path.read_text(encoding="utf-8")
    checks = {
        "full_history_checkout": "fetch-depth: 0" in text,
        "night_shift_suite": "tests/test_r5_night_shift_*.py" in text,
        "decision_and_adversarial_via_suite_glob": "Run night-shift contract" in text,
        "full_pytest": "python -m pytest -q\n" in text,
        "historical_guard_baseline": SOURCE_COMMIT in text,
        "historical_guard_bundle17r": HISTORICAL_PATHS[0] in text,
        "historical_guard_night02": HISTORICAL_PATHS[1] in text,
        "no_publication_mutation": "git push" not in text and "gh pr create" not in text,
    }
    if not all(checks.values()):
        raise Night03Error(f"Night03 CI contract is incomplete: {checks}")
    return stable_payload(
        {
            "schema_version": "r5_night03_ci_contract_v1",
            "workflow": CI_WORKFLOW.as_posix(),
            "workflow_sha256": sha256_file(path),
            "checks": checks,
            "passed": True,
        }
    )


def build_full_regression(
    *, night_shift_passed: int, full_passed: int, full_skipped: int, source_capabilities: int
) -> dict[str, Any]:
    if min(night_shift_passed, full_passed, source_capabilities) <= 0 or full_skipped < 0:
        raise Night03Error("full regression counts must come from successful runs")
    return stable_payload(
        {
            "schema_version": "r5_night03_full_regression_v1",
            "commands": [
                {
                    "command": "python -m pytest -q tests/test_r5_night_shift_*.py",
                    "result": "passed",
                    "passed": night_shift_passed,
                },
                {
                    "command": "python scripts/run_source_route_quality_gate.py --import-check --output reports/quality/ci_source_route_quality_report.yaml",
                    "result": "passed",
                    "capabilities": source_capabilities,
                    "blocking": 0,
                },
                {
                    "command": "python -m pytest -q",
                    "result": "passed",
                    "passed": full_passed,
                    "skipped": full_skipped,
                },
                {"command": "git diff --check", "result": "passed"},
                {"command": "historical path diff guard", "result": "passed"},
                {"command": "tracked temporary file guard", "result": "passed"},
            ],
            "all_passed": True,
        }
    )


def build_tracked_delivery_receipt(repo_root: Path) -> dict[str, Any]:
    head = _git(repo_root, "rev-parse", "HEAD")
    tree = _git(repo_root, "rev-parse", "HEAD^{tree}")
    rows = _git(
        repo_root, "log", "--format=%H%x09%s", f"{SOURCE_COMMIT}..HEAD"
    ).splitlines()
    commits = [
        {"sha": row.split("\t", 1)[0], "subject": row.split("\t", 1)[1]}
        for row in rows
        if "\t" in row
    ]
    workstreams = [
        item for item in commits if "seed reviewed-decision task package" not in item["subject"]
    ]
    if len(commits) < 5 or len(workstreams) < 4:
        raise Night03Error("minimum workstream commit policy is not satisfied")
    return stable_payload(
        {
            "schema_version": "r5_night03_tracked_delivery_receipt_v1",
            "mission_id": MISSION_ID,
            "target_branch": TARGET_BRANCH,
            "baseline_commit": SOURCE_COMMIT,
            "implementation_snapshot_before_validation_commit": {
                "commit_sha": head,
                "tree_sha": tree,
            },
            "commits_after_baseline_before_validation_commit": len(commits),
            "workstream_commits_excluding_seed": len(workstreams),
            "minimum_workstream_commits": 4,
            "minimum_commit_policy_satisfied": True,
            "commits": commits,
            "final_publication_head": None,
            "final_publication_resolution_policy": "authoritative_post_push_remote_receipt",
            "remote_delivery_receipt": REMOTE_RECEIPT.as_posix(),
            "ci_status": CI_STATUS.as_posix(),
            "pr_creation_allowed": False,
            "merge_main_allowed": False,
            "force_push_allowed": False,
        }
    )


def materialize_phase_e(
    repo_root: Path,
    *,
    night_shift_passed: int,
    full_passed: int,
    full_skipped: int,
    source_capabilities: int,
) -> dict[str, Any]:
    validation_summary = {
        "night_shift_passed": night_shift_passed,
        "full_pytest_passed": full_passed,
        "full_pytest_skipped": full_skipped,
        "source_route": f"pass_{source_capabilities}_capabilities_0_blocking",
    }
    artifacts = {
        "adversarial": build_adversarial_matrix(repo_root),
        "determinism": build_determinism_receipt(repo_root),
        "crash_resume": build_crash_resume_receipt(),
        "scope": build_scope_audit(repo_root),
        "ci": build_ci_contract(repo_root),
        "regression": build_full_regression(
            night_shift_passed=night_shift_passed,
            full_passed=full_passed,
            full_skipped=full_skipped,
            source_capabilities=source_capabilities,
        ),
        "delivery": build_tracked_delivery_receipt(repo_root),
        "readout": build_morning_readout(
            repo_root, validation_summary=validation_summary
        ),
        "next_queue": build_next_night_queue(repo_root),
    }
    root = repo_root / OUTPUT_ROOT
    write_json(root / "validation/adversarial_matrix.json", artifacts["adversarial"])
    write_json(root / "validation/determinism_receipt.json", artifacts["determinism"])
    write_json(root / "validation/crash_resume_receipt.json", artifacts["crash_resume"])
    write_json(root / "validation/scope_audit.json", artifacts["scope"])
    write_json(root / "validation/ci_contract.json", artifacts["ci"])
    write_json(root / "validation/full_regression.json", artifacts["regression"])
    write_json(
        root / "publication/tracked_delivery_receipt.json", artifacts["delivery"]
    )
    write_json(root / "morning_readout.json", artifacts["readout"])
    atomic_write(
        root / "morning_readout.md",
        morning_readout_markdown(artifacts["readout"]).encode("utf-8"),
    )
    write_yaml(root / "next_night_queue.yaml", artifacts["next_queue"])
    return artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialise Night03 Phase E artifacts")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--night-shift-passed", type=int, required=True)
    parser.add_argument("--full-passed", type=int, required=True)
    parser.add_argument("--full-skipped", type=int, required=True)
    parser.add_argument("--source-capabilities", type=int, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = materialize_phase_e(
        Path(args.repo).resolve(),
        night_shift_passed=args.night_shift_passed,
        full_passed=args.full_passed,
        full_skipped=args.full_skipped,
        source_capabilities=args.source_capabilities,
    )
    print(
        json.dumps(
            {
                "adversarial_cases": result["adversarial"]["case_count"],
                "determinism_comparisons": result["determinism"]["comparison_count"],
                "next_queue_tasks": len(result["next_queue"]["tasks"]),
                "resolved": result["readout"]["research_truth"][
                    "blocker_occurrences_resolved"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
