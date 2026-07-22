"""Night04 validation, publication indirection, and morning handoff."""

from __future__ import annotations

import argparse
import json
import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import yaml

from .night03 import load_json, load_yaml, sha256_file, stable_payload, write_json
from .night03_decisions import resolution_eligibility
from .night03_execution import aggregate_parent, dependency_unlock
from .night04 import (
    EXPECTED_QUEUE_SHA256,
    MISSION_ID,
    OUTPUT_ROOT,
    SOURCE_COMMIT,
    TARGET_BRANCH,
    Night04Error,
    authoritative_queue,
)
from .night04_acceleration import (
    build_first_parent_path,
    build_max_unlock_path,
    build_review_groups,
    build_reviewer_dashboard,
    build_unblock_leverage,
    dashboard_html,
    dashboard_markdown,
)
from .night04_execution import (
    Night04ExecutionError,
    build_blocker_ledger,
    build_next_night_queue,
    build_parent_recompute,
    execute_typed_adapter,
)
from .night04_review import (
    DECISION_SCHEMA_VERSION,
    apply_replay_guard,
    validate_decision_batch,
)
from .queue import atomic_write
from .receipts import canonical_json_bytes, sha256_bytes


CI_WORKFLOW = Path(".github/workflows/ci.yml")
REMOTE_RECEIPT = OUTPUT_ROOT / "publication/remote_delivery_receipt.json"
CI_STATUS = OUTPUT_ROOT / "publication/ci_status.md"
HISTORICAL_PATHS = (
    "reports/p1_6/r5_bundle17r",
    "reports/p1_6/r5_night_shift/r5_overnight_02_20260720",
    "reports/p1_6/r5_night_shift/r5_overnight_03_20260721",
)


def _git(repo_root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise Night04Error(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(value), ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )


def _yaml_bytes(value: Mapping[str, Any]) -> bytes:
    return yaml.safe_dump(
        dict(value), allow_unicode=True, sort_keys=False, width=120, line_break="\n"
    ).encode("utf-8")


def _reviewer_dashboard_bytes(repo_root: Path) -> dict[Path, bytes]:
    """Render the deterministic dashboard without touching Night04 history."""

    leverage = build_unblock_leverage(repo_root)
    first_parent = build_first_parent_path(repo_root, leverage)
    max_unlock = build_max_unlock_path(repo_root, leverage)
    groups = build_review_groups(repo_root)
    dashboard = build_reviewer_dashboard(leverage, first_parent, max_unlock, groups)
    root = OUTPUT_ROOT / "review_acceleration"
    return {
        root / "reviewer_dashboard.yaml": _yaml_bytes(dashboard),
        root / "reviewer_dashboard.md": dashboard_markdown(dashboard).encode("utf-8"),
        root / "reviewer_dashboard.html": dashboard_html(dashboard).encode("utf-8"),
    }


def _decision_manifest(entry: Mapping[str, Any], *, decision: str = "approve") -> tuple[dict[str, Any], set[tuple[str, str]]]:
    reviewer = "external_validation_fixture"
    authority = str(entry["required_reviewer_authority"])
    return (
        {
            "schema_version": DECISION_SCHEMA_VERSION,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "records": [
                {
                    "occurrence_id": entry["occurrence_id"],
                    "candidate_sha256": entry["candidate_sha256"],
                    "review_packet_sha256": entry["review_packet_sha256"],
                    "reviewer": reviewer,
                    "reviewer_authority": authority,
                    "reviewed_at": "2026-07-20T12:00:00+00:00",
                    "decision": decision,
                    "notes": ["synthetic adversarial validation fixture"],
                }
            ],
        },
        {(reviewer, authority)},
    )


def _invalid_case(label: str, result: Mapping[str, Any], reason: str) -> dict[str, Any]:
    passed = result.get("accepted_count") == 0 and any(
        reason in str(item.get("reason")) for item in result.get("invalid_records") or []
    )
    if not passed:
        raise Night04Error(f"adversarial case did not fail closed: {label}: {result}")
    return {"case": label, "result": "rejected", "reason": reason}


def build_adversarial_matrix(repo_root: Path) -> dict[str, Any]:
    registry = load_yaml(repo_root / OUTPUT_ROOT / "review_control/candidate_registry.yaml")
    entries = registry["candidates"]
    first_manifest, first_authorities = _decision_manifest(entries[0])
    second_manifest, second_authorities = _decision_manifest(entries[1])
    now = datetime(2026, 7, 21, tzinfo=timezone.utc)
    cases: list[dict[str, Any]] = []

    forged = deepcopy(first_manifest)
    forged["records"][0]["reviewer"] = "codex-agent"
    forged_authority = {
        ("codex-agent", str(forged["records"][0]["reviewer_authority"]))
    }
    cases.append(
        _invalid_case(
            "forged_machine_reviewer",
            validate_decision_batch(repo_root, forged, authority_registry=forged_authority, now=now),
            "reviewer_identity_invalid",
        )
    )

    stale_candidate = deepcopy(first_manifest)
    stale_candidate["records"][0]["candidate_sha256"] = "0" * 64
    cases.append(
        _invalid_case(
            "stale_candidate_hash",
            validate_decision_batch(repo_root, stale_candidate, authority_registry=first_authorities, now=now),
            "stale_candidate_hash",
        )
    )

    stale_packet = deepcopy(first_manifest)
    stale_packet["records"][0]["review_packet_sha256"] = "1" * 64
    cases.append(
        _invalid_case(
            "stale_review_packet_hash",
            validate_decision_batch(repo_root, stale_packet, authority_registry=first_authorities, now=now),
            "stale_review_packet_hash",
        )
    )

    cases.append(
        _invalid_case(
            "missing_external_authority",
            validate_decision_batch(repo_root, first_manifest, authority_registry=set(), now=now),
            "reviewer_authority_not_externally_verified",
        )
    )

    conflict = deepcopy(first_manifest)
    opposite = deepcopy(conflict["records"][0])
    opposite["decision"] = "reject"
    conflict["records"].append(opposite)
    conflict_result = validate_decision_batch(
        repo_root, conflict, authority_registry=first_authorities, now=now
    )
    if conflict_result["accepted_count"] or conflict_result["invalid_count"] != 2:
        raise Night04Error("conflicting duplicate was not rejected atomically")
    cases.append(
        {"case": "conflicting_duplicate", "result": "rejected", "reason": "conflicting_duplicate"}
    )

    partial = deepcopy(first_manifest)
    bad_second = deepcopy(second_manifest["records"][0])
    bad_second["review_packet_sha256"] = "f" * 64
    partial["records"].append(bad_second)
    partial_result = validate_decision_batch(
        repo_root,
        partial,
        authority_registry=first_authorities | second_authorities,
        now=now,
    )
    if partial_result["accepted_count"] != 1 or partial_result["invalid_count"] != 1:
        raise Night04Error("partial batch did not isolate the stale record")
    cases.append(
        {"case": "partial_batch_isolation", "result": "rejected", "reason": "stale_record_isolated"}
    )

    approved = validate_decision_batch(
        repo_root, first_manifest, authority_registry=first_authorities, now=now
    )["accepted_records"][0]
    approval_only = resolution_eligibility(approved, None)
    if approval_only["resolved"]:
        raise Night04Error("approval without an independent receipt was treated as resolution")
    cases.append(
        {"case": "approval_without_receipt", "result": "rejected", "reason": "missing_independent_receipt"}
    )

    mismatched_receipt = {
        "occurrence_id": approved["occurrence_id"],
        "decision_digest_sha256": "e" * 64,
        "terminal_status": "passed",
        "lineage_match": True,
        "resolution_claim_allowed": True,
        "source_queue_sha256": EXPECTED_QUEUE_SHA256,
    }
    mismatch = resolution_eligibility(approved, mismatched_receipt)
    if mismatch["resolved"] or "decision_digest_mismatch" not in mismatch["reasons"]:
        raise Night04Error("mismatched receipt digest was not rejected")
    cases.append(
        {"case": "mismatched_receipt_digest", "result": "rejected", "reason": "decision_digest_mismatch"}
    )

    pointer_entry = next(
        item for item in entries if item["candidate_kind"] == "engineering_local_pointer"
    )
    pointer_manifest, pointer_authorities = _decision_manifest(pointer_entry)
    pointer_decision = validate_decision_batch(
        repo_root, pointer_manifest, authority_registry=pointer_authorities, now=now
    )["accepted_records"][0]
    try:
        execute_typed_adapter(
            repo_root,
            [pointer_decision],
            candidate_kind="engineering_local_pointer",
            executor=lambda _: {
                "sandboxed": True,
                "target_branch_changed": True,
                "implementation_tree_sha": "a" * 40,
                "terminal_status": "passed",
                "lineage_match": True,
                "resolution_claim_allowed": True,
            },
        )
    except Night04ExecutionError:
        cases.append(
            {"case": "pointer_target_branch_escape", "result": "rejected", "reason": "sandbox_boundary"}
        )
    else:
        raise Night04Error("pointer target-branch escape was not rejected")

    tasks = authoritative_queue(repo_root)["tasks"]
    parent = next(item for item in tasks if item["work_type"] == "bf2_work_order" and all(str(dep).startswith("ns02_t30_occ_") for dep in item["depends_on"]))
    parent_result = aggregate_parent(
        parent, {str(item): {"status": "candidate_ready"} for item in parent["depends_on"]}
    )
    dependency = next(item for item in tasks if item["work_type"] == "dependency_blocked")
    dependency_result = dependency_unlock(
        dependency,
        {str(item): {"status": "candidate_ready"} for item in dependency["depends_on"]},
    )
    if parent_result["status"] != "pending" or dependency_result["unlocked"]:
        raise Night04Error("candidate state falsely closed a parent or unlocked a dependency")
    cases.extend(
        [
            {"case": "candidate_false_parent_close", "result": "rejected", "reason": "parent_pending"},
            {"case": "candidate_false_dependency_unlock", "result": "rejected", "reason": "unresolved_prerequisites"},
        ]
    )

    return stable_payload(
        {
            "schema_version": "r5_night04_adversarial_matrix_v1",
            "mission_id": MISSION_ID,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "case_count": len(cases),
            "all_fail_closed": True,
            "resolved_delta": 0,
            "cases": cases,
        }
    )


def build_determinism_receipt(repo_root: Path) -> dict[str, Any]:
    def materialized_hashes() -> dict[str, str]:
        return {
            path.as_posix(): sha256_bytes(payload)
            for path, payload in _reviewer_dashboard_bytes(repo_root).items()
        }

    first_dashboard = materialized_hashes()
    second_dashboard = materialized_hashes()
    builders: dict[str, tuple[Callable[[], Mapping[str, Any]], Callable[[Mapping[str, Any]], bytes]]] = {
        "blocker_ledger": (lambda: build_blocker_ledger(repo_root), _json_bytes),
        "next_night_queue": (lambda: build_next_night_queue(repo_root), _yaml_bytes),
    }
    comparisons: list[dict[str, Any]] = [
        {
            "artifact": "reviewer_dashboard_materialized",
            "bytes_equal": first_dashboard == second_dashboard,
            "first_hashes": first_dashboard,
            "second_hashes": second_dashboard,
        }
    ]
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
        raise Night04Error("Night04 dashboard or ledger double-run is not deterministic")
    return stable_payload(
        {
            "schema_version": "r5_night04_determinism_receipt_v1",
            "mission_id": MISSION_ID,
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


def build_crash_resume_receipt() -> dict[str, Any]:
    decision = {
        "occurrence_id": "synthetic_resume_probe",
        "candidate_kind": "evidence_required",
        "decision": "approve",
        "decision_digest_sha256": "a" * 64,
    }
    first_seen: set[str] = set()
    first = apply_replay_guard([decision], first_seen)
    checkpoint = stable_payload(
        {
            "schema_version": "r5_night04_resume_checkpoint_v1",
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "records": first["new_records"],
        }
    )
    resumed_seen = {str(item["decision_digest_sha256"]) for item in checkpoint["records"]}
    resumed = apply_replay_guard([decision], resumed_seen)
    if len(first["new_records"]) != 1 or resumed["new_records"] or len(resumed["replayed_digests"]) != 1:
        raise Night04Error("decision checkpoint replay is not idempotent")
    return stable_payload(
        {
            "schema_version": "r5_night04_crash_resume_receipt_v1",
            "mission_id": MISSION_ID,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "checkpoint_stable_sha256": checkpoint["stable_receipt_sha256"],
            "first_consumed_count": 1,
            "resumed_new_count": 0,
            "resumed_replay_count": 1,
            "replay_idempotent": True,
            "atomic_write_validation": "covered_by_tests/test_r5_night_shift_lock.py",
            "single_writer_lock_validation": "covered_by_tests/test_r5_night_shift_lock.py",
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
        if path.startswith(".local/") or path.endswith(".pyc") or "/__pycache__/" in path
    ]
    diff_check = subprocess.run(
        ["git", "diff", "--check"], cwd=repo_root, text=True, capture_output=True, check=False
    )
    if historical or bad_tracked or diff_check.returncode:
        raise Night04Error(
            f"scope audit failed: historical={historical!r} bad_tracked={bad_tracked!r} "
            f"diff_check={diff_check.stdout!r}{diff_check.stderr!r}"
        )
    return stable_payload(
        {
            "schema_version": "r5_night04_scope_audit_v1",
            "mission_id": MISSION_ID,
            "baseline_commit": SOURCE_COMMIT,
            "audited_head_before_validation_commit": _git(repo_root, "rev-parse", "HEAD"),
            "historical_paths": list(HISTORICAL_PATHS),
            "historical_changed_paths": [],
            "tracked_local_or_bytecode_paths": [],
            "git_diff_check": "passed",
            "pr_created": False,
            "main_merged": False,
            "force_push_used": False,
            "passed": True,
        }
    )


def build_full_regression(
    *, night_shift_passed: int, full_passed: int, full_skipped: int, source_capabilities: int
) -> dict[str, Any]:
    if min(night_shift_passed, full_passed, source_capabilities) <= 0 or full_skipped < 0:
        raise Night04Error("full regression counts must come from successful runs")
    return stable_payload(
        {
            "schema_version": "r5_night04_full_regression_v1",
            "mission_id": MISSION_ID,
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


def build_ci_contract(repo_root: Path) -> dict[str, Any]:
    path = repo_root / CI_WORKFLOW
    text = path.read_text(encoding="utf-8")
    checks = {
        "full_history_checkout": "fetch-depth: 0" in text,
        "night_shift_suite": "tests/test_r5_night_shift_*.py" in text,
        "source_route_gate": "run_source_route_quality_gate.py --import-check" in text,
        "full_pytest": "python -m pytest -q\n" in text,
        "historical_guard_baseline": SOURCE_COMMIT in text,
        "historical_guard_bundle17r": HISTORICAL_PATHS[0] in text,
        "historical_guard_night02": HISTORICAL_PATHS[1] in text,
        "historical_guard_night03": HISTORICAL_PATHS[2] in text,
        "no_publication_mutation": "git push" not in text and "gh pr create" not in text,
    }
    if not all(checks.values()):
        raise Night04Error(f"Night04 CI contract is incomplete: {checks}")
    return stable_payload(
        {
            "schema_version": "r5_night04_ci_contract_v1",
            "mission_id": MISSION_ID,
            "workflow": CI_WORKFLOW.as_posix(),
            "workflow_sha256": sha256_file(path),
            "checks": checks,
            "passed": True,
        }
    )


def build_tracked_delivery_receipt(repo_root: Path) -> dict[str, Any]:
    rows = _git(
        repo_root, "log", "--reverse", "--format=%H%x09%s", f"{SOURCE_COMMIT}..HEAD"
    ).splitlines()
    commits = [
        {"sha": row.split("\t", 1)[0], "subject": row.split("\t", 1)[1]}
        for row in rows
        if "\t" in row
    ]
    workstreams = [item for item in commits if "seed review-acceleration task package" not in item["subject"]]
    if len(workstreams) < 6:
        raise Night04Error(
            f"minimum six workstream commits after seed not satisfied: {len(workstreams)}"
        )
    return stable_payload(
        {
            "schema_version": "r5_night04_tracked_delivery_receipt_v1",
            "mission_id": MISSION_ID,
            "target_branch": TARGET_BRANCH,
            "baseline_commit": SOURCE_COMMIT,
            "implementation_snapshot_before_publication_commit": {
                "commit_sha": _git(repo_root, "rev-parse", "HEAD"),
                "tree_sha": _git(repo_root, "rev-parse", "HEAD^{tree}"),
            },
            "commits_after_baseline_before_publication_commit": len(commits),
            "workstream_commits_excluding_seed": len(workstreams),
            "minimum_workstream_commits": 6,
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


def build_morning_readout(repo_root: Path) -> dict[str, Any]:
    ledger = build_blocker_ledger(repo_root)
    parents = build_parent_recompute(repo_root)
    queue = build_next_night_queue(repo_root)
    registry = load_yaml(repo_root / OUTPUT_ROOT / "review_control/candidate_registry.yaml")
    patches = load_yaml(repo_root / OUTPUT_ROOT / "pointer_prevalidation/dry_run_patch_index.yaml")
    consumption = load_json(repo_root / OUTPUT_ROOT / "execution/startup_decision_consumption.json")
    validation = {
        "adversarial": load_json(repo_root / OUTPUT_ROOT / "validation/adversarial_matrix.json")["all_fail_closed"],
        "determinism": load_json(repo_root / OUTPUT_ROOT / "validation/determinism_receipt.json")["all_bytes_equal"],
        "crash_resume": load_json(repo_root / OUTPUT_ROOT / "validation/crash_resume_receipt.json")["replay_idempotent"],
        "full_regression": load_json(repo_root / OUTPUT_ROOT / "validation/full_regression.json")["all_passed"],
        "ci_contract": load_json(repo_root / OUTPUT_ROOT / "validation/ci_contract.json")["passed"],
        "scope_audit": load_json(repo_root / OUTPUT_ROOT / "validation/scope_audit.json")["passed"],
    }
    tracked = load_json(repo_root / OUTPUT_ROOT / "publication/tracked_delivery_receipt.json")
    return stable_payload(
        {
            "schema_version": "r5_night04_morning_readout_v1",
            "mission_id": MISSION_ID,
            "target_branch": TARGET_BRANCH,
            "mission_outcome": "delivered_review_acceleration_ready",
            "outcome_meaning": "engineering_delivery_complete_research_program_still_open",
            "publication_resolution_policy": "matching_post_push_remote_receipt_and_successful_ci",
            "publication_receipt": REMOTE_RECEIPT.as_posix(),
            "ci_status": CI_STATUS.as_posix(),
            "source_commit": SOURCE_COMMIT,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "review_readiness": {
                "review_bundles_complete": registry["candidate_count"],
                "pointer_dry_runs_complete": patches["pointer_count"],
                "external_decision_manifests": consumption["scanned_manifest_count"],
                "approved_decisions": consumption["approved_decision_count"],
                "automatic_reviewer_used": False,
            },
            "research_truth": {
                "blocker_occurrences_total": ledger["blocker_occurrences_total"],
                "blocker_occurrences_resolved": ledger["blocker_occurrences_resolved_end"],
                "resolved_delta": ledger["resolved_delta"],
                "candidate_ready": ledger["status_counts"].get("candidate_ready", 0),
                "dependency_blocked": ledger["status_counts"].get("dependency_blocked", 0),
                "dependency_unlocked": ledger["dependency_unlocked_count"],
                "work_orders_pending": parents["pending_parent_count"],
                "work_orders_resolved": parents["resolved_parent_count"],
                "program_goal": "open_needs_targeted_backflow",
                "sample_quality_allowed": False,
                "p2_allowed": False,
            },
            "validation": validation,
            "delivery": {
                "workstream_commits_excluding_seed": tracked["workstream_commits_excluding_seed"],
                "minimum_commit_policy_satisfied": tracked["minimum_commit_policy_satisfied"],
                "historical_path_diff": 0,
                "pr_created": False,
                "main_merged": False,
                "force_push_used": False,
                "final_remote_identity_deferred_to_post_push_receipt": True,
            },
            "next_night_queue": {
                "path": (OUTPUT_ROOT / "next_night_queue.yaml").as_posix(),
                "task_count": queue["carry_forward"]["task_count"],
                "source_commit_policy": queue["source_commit_policy"],
            },
            "next_actions": [
                "obtain authentic external exact-hash reviewer decisions",
                "run explicit typed executors and issue independent passed receipts",
                "recompute dependencies and parents only from those atomic receipts",
            ],
        }
    )


def morning_readout_markdown(readout: Mapping[str, Any]) -> str:
    truth = readout["research_truth"]
    review = readout["review_readiness"]
    delivery = readout["delivery"]
    return "\n".join(
        [
            "# Night04 晨间交接",
            "",
            f"- 工程交付：`{readout['mission_outcome']}`",
            f"- 评审包：`{review['review_bundles_complete']}/43`",
            f"- 指针沙盒预验证：`{review['pointer_dry_runs_complete']}/8`",
            f"- 外部审批：`{review['approved_decisions']}`",
            f"- 阻塞项已解决：`{truth['blocker_occurrences_resolved']}/{truth['blocker_occurrences_total']}`",
            f"- 依赖解除：`{truth['dependency_unlocked']}/20`",
            f"- 父任务完成：`{truth['work_orders_resolved']}/6`",
            f"- 工作流提交（不含 seed）：`{delivery['workstream_commits_excluding_seed']}`",
            "- 历史路径改动：`0`",
            "- Program Goal：`open_needs_targeted_backflow`",
            "- Sample quality / P2：`false / false`",
            "",
            "`delivered_review_acceleration_ready` 只表示 Night04 工程交付完成，不表示研究计划完成。",
            "候选、评审排序和沙盒测试均不是 resolution；只有真实审批与匹配的独立 passed receipt 才能增加 resolved。",
            "",
            f"Night05 队列原样结转 `{readout['next_night_queue']['task_count']}` 个 unresolved ID。",
            "最终远端 SHA 与 CI 由 post-push remote receipt 给出，避免提交自引用。",
            "",
        ]
    )


def build_remote_delivery_receipt(
    repo_root: Path,
    *,
    remote_head: str,
    ci_run_id: int,
    ci_url: str,
    ci_conclusion: str,
) -> dict[str, Any]:
    local_head = _git(repo_root, "rev-parse", "HEAD")
    remote_ref = _git(repo_root, "ls-remote", "origin", f"refs/heads/{TARGET_BRANCH}")
    remote_sha = remote_ref.split()[0] if remote_ref else ""
    if local_head != remote_head or remote_sha != remote_head:
        raise Night04Error(
            f"remote head mismatch: local={local_head} declared={remote_head} remote={remote_sha}"
        )
    if ci_conclusion != "success":
        raise Night04Error(f"final exact-head CI is not successful: {ci_conclusion}")
    return stable_payload(
        {
            "schema_version": "r5_night04_remote_delivery_receipt_v1",
            "mission_id": MISSION_ID,
            "target_branch": TARGET_BRANCH,
            "local_head": local_head,
            "remote_head": remote_sha,
            "exact_head_match": True,
            "ci": {
                "database_id": ci_run_id,
                "head_sha": remote_head,
                "conclusion": ci_conclusion,
                "url": ci_url,
            },
            "tracked_receipt": (OUTPUT_ROOT / "publication/tracked_delivery_receipt.json").as_posix(),
            "tracked_in_identified_commit": False,
            "pr_created": False,
            "main_merged": False,
            "force_push_used": False,
        }
    )


def materialize_core_validation(repo_root: Path) -> dict[str, Any]:
    artifacts = {
        "adversarial": build_adversarial_matrix(repo_root),
        "determinism": build_determinism_receipt(repo_root),
        "crash_resume": build_crash_resume_receipt(),
    }
    root = repo_root / OUTPUT_ROOT / "validation"
    write_json(root / "adversarial_matrix.json", artifacts["adversarial"])
    write_json(root / "determinism_receipt.json", artifacts["determinism"])
    write_json(root / "crash_resume_receipt.json", artifacts["crash_resume"])
    return artifacts


def materialize_regression_validation(
    repo_root: Path,
    *,
    night_shift_passed: int,
    full_passed: int,
    full_skipped: int,
    source_capabilities: int,
) -> dict[str, Any]:
    artifacts = {
        "scope": build_scope_audit(repo_root),
        "regression": build_full_regression(
            night_shift_passed=night_shift_passed,
            full_passed=full_passed,
            full_skipped=full_skipped,
            source_capabilities=source_capabilities,
        ),
        "ci": build_ci_contract(repo_root),
    }
    root = repo_root / OUTPUT_ROOT / "validation"
    write_json(root / "scope_audit.json", artifacts["scope"])
    write_json(root / "full_regression.json", artifacts["regression"])
    write_json(root / "ci_contract.json", artifacts["ci"])
    return artifacts


def materialize_tracked_publication(repo_root: Path) -> dict[str, Any]:
    receipt = build_tracked_delivery_receipt(repo_root)
    write_json(repo_root / OUTPUT_ROOT / "publication/tracked_delivery_receipt.json", receipt)
    return receipt


def materialize_morning_readout(repo_root: Path) -> dict[str, Any]:
    readout = build_morning_readout(repo_root)
    write_json(repo_root / OUTPUT_ROOT / "morning_readout.json", readout)
    atomic_write(
        repo_root / OUTPUT_ROOT / "morning_readout.md",
        morning_readout_markdown(readout).encode("utf-8"),
    )
    return readout


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialise Night04 validation artifacts")
    parser.add_argument("--repo", default=".")
    parser.add_argument(
        "--mode", choices=("core", "regression", "tracked", "morning", "remote"), required=True
    )
    parser.add_argument("--night-shift-passed", type=int)
    parser.add_argument("--full-passed", type=int)
    parser.add_argument("--full-skipped", type=int, default=0)
    parser.add_argument("--source-capabilities", type=int)
    parser.add_argument("--remote-head")
    parser.add_argument("--ci-run-id", type=int)
    parser.add_argument("--ci-url")
    parser.add_argument("--ci-conclusion")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo).resolve()
    if args.mode == "core":
        result = materialize_core_validation(repo_root)
    elif args.mode == "regression":
        if args.night_shift_passed is None or args.full_passed is None or args.source_capabilities is None:
            raise Night04Error("regression mode requires observed test and source-route counts")
        result = materialize_regression_validation(
            repo_root,
            night_shift_passed=args.night_shift_passed,
            full_passed=args.full_passed,
            full_skipped=args.full_skipped,
            source_capabilities=args.source_capabilities,
        )
    elif args.mode == "tracked":
        result = materialize_tracked_publication(repo_root)
    elif args.mode == "morning":
        result = materialize_morning_readout(repo_root)
    else:
        if not all((args.remote_head, args.ci_run_id, args.ci_url, args.ci_conclusion)):
            raise Night04Error("remote mode requires exact remote head and CI evidence")
        result = build_remote_delivery_receipt(
            repo_root,
            remote_head=args.remote_head,
            ci_run_id=args.ci_run_id,
            ci_url=args.ci_url,
            ci_conclusion=args.ci_conclusion,
        )
        write_json(repo_root / REMOTE_RECEIPT, result)
        atomic_write(
            repo_root / CI_STATUS,
            (
                "# Night04 CI status\n\n"
                f"- Head: `{args.remote_head}`\n"
                f"- Run: `{args.ci_run_id}`\n"
                f"- Conclusion: `{args.ci_conclusion}`\n"
                f"- URL: {args.ci_url}\n"
            ).encode("utf-8"),
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
