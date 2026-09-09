from __future__ import annotations

import hashlib
import posixpath
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from conftest import (
    GIT_HISTORY, GOVERNANCE_BASELINE, GOVERNANCE_MANIFEST, governance_paths,
    governance_snapshot, governance_text, governance_text_index, prefetch_governance_recovery,
)
import pytest

# Published historical results; current algorithms are covered in the default suite.
pytestmark = pytest.mark.legacy_compatibility


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs/meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml"


def load_manifest() -> dict[str, Any]:
    prefetch_governance_recovery()
    return governance_snapshot()


def groups_by_status(manifest: dict[str, Any], status: str) -> list[dict[str, Any]]:
    return [group for group in manifest["candidate_groups"] if group["status"] == status]


def test_manifest_is_a_decision_record_not_a_deletion_executor() -> None:
    manifest = load_manifest()
    control = manifest["deletion_control"]

    assert control["codex_delete_authorized"] is False
    assert control["codex_quarantine_move_authorized"] is True
    assert control["directories_authorized"] is False
    assert control["execution_actor"] == (
        "codex_exact_path_quarantine_then_user_manual_directory_delete"
    )
    assert control["git_history_is_recovery_basis"] is True
    assert set(control["state_contract"]) == {
        "not_started",
        "quarantine_move_in_progress",
        "user_quarantined_pending_manual_delete",
        "user_deleted_pending_commit",
        "completed",
    }
    assert control["execution_state"] in control["state_contract"]
    assert set(control["approval"]) == {
        "approved_closure_ids",
        "approved_exact_paths",
    }
    assert isinstance(control["approval"]["approved_closure_ids"], list)
    assert isinstance(control["approval"]["approved_exact_paths"], list)
    rendered = governance_text(GOVERNANCE_MANIFEST).lower()
    for forbidden in (
        "remove-item",
        "rm -rf",
        "git clean",
        "delete-wave",
        "unlink(",
        "rmdir(",
    ):
        assert forbidden not in rendered


def test_every_candidate_group_has_dependency_and_replacement_evidence() -> None:
    manifest = load_manifest()

    for group in manifest["candidate_groups"]:
        assert group["status"] in manifest["status_definitions"]
        assert group["replacement_authority"]
        assert "inbound_reference_policy" in group
        assert group["items"]
        for item in group["items"]:
            assert set(item) >= {
                "path",
                "inbound_references",
                "replacement_authority",
                "recovery_basis",
            }
            assert item["replacement_authority"]
            assert isinstance(item["inbound_references"], list)


def test_ready_paths_are_literal_files_and_never_directories() -> None:
    manifest = load_manifest()
    ready = [
        item
        for group in groups_by_status(manifest, "READY_FOR_MANUAL_DELETE")
        for item in group["items"]
    ]

    for item in ready:
        pure = PurePosixPath(item["path"])
        assert pure.suffix
        assert item["path"] == pure.as_posix()
        assert not pure.is_absolute()
        assert ".." not in pure.parts
        assert item["recovery_basis"]["kind"] == "git_blob"


def test_phase2_replay_is_an_exact_ready_closure_with_equivalent_evidence() -> None:
    manifest = load_manifest()
    replay_prefix = (
        "reports/workflow_runs/"
        "wf_20260723_stock_first_002837_v1_replay/"
    )
    ready = {
        item["path"]
        for group in groups_by_status(manifest, "READY_FOR_MANUAL_DELETE")
        for item in group["items"]
    }
    phase2 = manifest["phase2_retirement"]
    baseline = phase2["baseline_commit"]
    tracked_replay = {
        path.replace("\\", "/")
        for path in subprocess.check_output(
            ["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", baseline],
            text=True,
            encoding="utf-8",
        ).splitlines()
        if path.startswith(replay_prefix)
    }

    assert tracked_replay
    assert tracked_replay <= ready
    assert tracked_replay == set(
        phase2["closures"]["phase2_closure_004_replay_20260723"]["exact_paths"]
    )
    assert phase2["evidence_equivalence"]["replay_metric_candidates"] == {
        "candidate_count": 136,
        "exact_row_match_count": 136,
        "replacement_path": "data/manifests/metrics_draft.csv",
        "promoted_count": 0,
    }
    assert phase2["evidence_equivalence"]["replay_issue_lineage"][
        "mapped_issue_count"
    ] == 4


def test_phase2_inventory_and_quarantine_state_are_exact() -> None:
    manifest = load_manifest()
    phase2 = manifest["phase2_retirement"]
    closures = phase2["closures"]
    expected = {
        "phase2_closure_001_docs_codex_tasks": (17, 303_117),
        "phase2_closure_002_docs_plans": (17, 234_521),
        "phase2_closure_003_reports_p1_6": (148, 493_977),
        "phase2_closure_004_replay_20260723": (16, 132_529),
        "phase2_closure_005_top_codex_tasks": (207, 418_965),
        "phase2_closure_006_migrated_rules": (2, 3_470),
    }

    assert set(closures) == set(expected)
    path_sets = {key: set(row["exact_paths"]) for key, row in closures.items()}
    all_paths = set().union(*path_sets.values())
    assert sum(len(paths) for paths in path_sets.values()) == len(all_paths) == 407
    assert sum(row["git_blob_bytes"] for row in closures.values()) == 1_586_579
    for closure_id, (file_count, byte_count) in expected.items():
        row = closures[closure_id]
        assert row["all_or_none"] is True
        assert row["file_count"] == file_count == len(path_sets[closure_id])
        assert row["git_blob_bytes"] == byte_count

    ready = {
        item["path"]
        for group in groups_by_status(manifest, "READY_FOR_MANUAL_DELETE")
        for item in group["items"]
    }
    assert all_paths <= ready
    candidate_oids = {
        item["path"]: item["blob_oid"]
        for group in manifest["candidate_groups"]
        for item in group["items"]
    }
    changed = set(
        subprocess.check_output(
            ["git", "-C", str(ROOT), "diff", "--name-only", phase2["baseline_commit"], GOVERNANCE_BASELINE],
            text=True,
        ).splitlines()
    )
    gate = phase2["approval_gate"]
    assert gate["required_selection"] == "all_six_phase2_closures_all_or_none"
    assert gate["codex_delete_authorized"] is False
    quarantine_relative = PurePosixPath(gate["quarantine_root_after_approval"])
    assert quarantine_relative.parts[:1] == (".codex_tmp",)
    assert ".." not in quarantine_relative.parts
    quarantine_root = ROOT.joinpath(*quarantine_relative.parts)
    assert ROOT.resolve() in quarantine_root.resolve().parents
    assert not quarantine_root.is_symlink()
    ignore_check = subprocess.run(
        ["git", "-C", str(ROOT), "check-ignore", "-q", str(quarantine_root / "probe")],
        check=False,
    )
    assert ignore_check.returncode == 0
    quarantine_descendants = list(quarantine_root.rglob("*")) if quarantine_root.is_dir() else []
    assert not any(path.is_symlink() for path in quarantine_descendants)
    quarantine_files = {
        path.relative_to(quarantine_root).as_posix()
        for path in quarantine_descendants
        if path.is_file()
    }
    source_files = {relative for relative in all_paths if (ROOT / relative).is_file()}
    assert source_files.isdisjoint(quarantine_files)

    execution_state = gate["execution_state"]
    if execution_state == "not_started":
        assert phase2["status"] == "awaiting_user_approval"
        assert gate["user_approved"] is False
        assert gate["approved_closure_ids"] == []
        assert gate["approved_exact_paths"] == []
        assert gate["codex_quarantine_move_authorized"] is False
        assert source_files == all_paths
        assert quarantine_files == set()
        assert changed <= set(phase2["modified_file_allowlist"])
        assert changed.isdisjoint(all_paths)
    else:
        assert execution_state in {
            "quarantine_move_in_progress",
            "user_quarantined_pending_manual_delete",
            "user_deleted_pending_commit",
            "completed",
        }
        assert phase2["status"] == execution_state
        assert gate["user_approved"] is True
        assert gate["approved_closure_ids"] == list(closures)
        assert len(gate["approved_exact_paths"]) == len(set(gate["approved_exact_paths"]))
        assert set(gate["approved_exact_paths"]) == all_paths
        assert gate["codex_quarantine_move_authorized"] is True
        assert changed <= set(phase2["modified_file_allowlist"]) | all_paths
        if execution_state == "quarantine_move_in_progress":
            assert source_files | quarantine_files == all_paths
        elif execution_state == "user_quarantined_pending_manual_delete":
            assert source_files == set()
            assert quarantine_files == all_paths
        else:
            assert source_files == set()
            assert quarantine_files == set()

    for relative in quarantine_files:
        filtered_oid = subprocess.check_output(
            [
                "git",
                "-C",
                str(ROOT),
                "hash-object",
                f"--path={relative}",
                "--",
                str(quarantine_root.joinpath(*PurePosixPath(relative).parts)),
            ],
            text=True,
        ).strip()
        assert filtered_oid == candidate_oids[relative], relative


def test_phase2_decision_buckets_are_exact_and_exhaustive() -> None:
    phase2 = load_manifest()["phase2_retirement"]
    buckets = phase2["decision_buckets"]
    expected = {
        "DIRECT_RETIRE": (241, 513_650),
        "MIGRATE_THEN_RETIRE": (151, 784_888),
        "EVIDENCE_EQUIVALENCE_THEN_RETIRE": (15, 288_041),
    }
    path_sets = {
        key: set(row["exact_paths"])
        for key, row in buckets.items()
    }
    closure_paths = {
        path
        for row in phase2["closures"].values()
        for path in row["exact_paths"]
    }

    assert set(buckets) == set(expected)
    assert sum(len(paths) for paths in path_sets.values()) == 407
    assert set().union(*path_sets.values()) == closure_paths
    for bucket, (file_count, byte_count) in expected.items():
        row = buckets[bucket]
        assert row["replacement_complete"] is True
        assert len(path_sets[bucket]) == row["file_count"] == file_count
        assert row["git_blob_bytes"] == byte_count


def test_modified_file_allowlist_is_exact_and_contains_only_authorized_paths() -> None:
    manifest = load_manifest()
    allowlist = manifest["audit"]["modified_file_allowlist"]
    retirement = manifest["audit"]["retirement_execution"]
    approved = manifest["deletion_control"]["approval"]["approved_exact_paths"]

    assert allowlist == sorted(set(allowlist))
    assert "docs/meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml" in allowlist
    assert not any(path.startswith("data/") for path in allowlist)
    assert not any(path.startswith("src/portfolio/") for path in allowlist)
    assert not any(path.startswith("src/investment_review/") for path in allowlist)
    assert retirement["dependency_decoupling_commit"] == (
        "bbb95318156820bd5c1d8a49d4a20a7df8758754"
    )
    assert retirement["control_paths"] == [
        ".github/workflows/ci.yml",
        "docs/meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml",
        "tests/test_r5_v1_active_routing_retirement.py",
        "tests/test_r5_v1_historical_cleanup_manifest.py",
    ]
    assert retirement["approved_paths_source"] == (
        "deletion_control.approval.approved_exact_paths"
    )
    assert retirement["expected_worktree_change_count"] == (
        len(retirement["control_paths"]) + len(approved)
    )
    assert retirement["quarantine_root"] == manifest["deletion_control"]["quarantine"]["path"]


def test_ci_quality_report_is_written_only_to_the_ignored_temp_root() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "--output .codex_tmp/ci_source_route_quality_report.yaml" in workflow
    assert "reports/quality/ci_source_route_quality_report.yaml" not in workflow


def test_declared_inbound_references_are_exact_and_auditable() -> None:
    manifest = load_manifest()
    baseline = manifest["audit"]["baseline_commit"]
    candidate_recovery = {
        item["path"]: item["recovery_basis"]["commit"]
        for group in manifest["candidate_groups"]
        for item in group["items"]
    }
    candidate_paths = set(candidate_recovery)

    def historical_text(relative: str) -> str:
        recovery_commit = candidate_recovery.get(relative, baseline)
        return GIT_HISTORY.text(recovery_commit, relative, errors="replace")

    def mentions(source_path: str, source_text: str, target: str) -> bool:
        if target in source_text.replace("\\", "/"):
            return True
        adjacent_literal_text = re.sub(r"([\"'])\s*\1", "", source_text)
        if target in adjacent_literal_text.replace("\\", "/"):
            return True
        if not source_path.endswith(".md"):
            return False
        source_dir = posixpath.dirname(source_path)
        for raw_link in re.findall(r"\]\(([^)]+)\)", source_text):
            link = raw_link.split("#", 1)[0]
            if not link or "://" in link:
                continue
            resolved = posixpath.normpath(posixpath.join(source_dir, link))
            if resolved == target:
                return True
        return False

    for group in manifest["candidate_groups"]:
        for item in group["items"]:
            target = item["path"]
            for reference in item["inbound_references"]:
                source = ROOT / reference["source_path"]
                relation = reference["relation"]
                if reference["source_path"] in governance_paths():
                    source_text = governance_text(reference["source_path"])
                else:
                    assert (
                        reference["source_path"] in candidate_paths
                        or relation in {"closure_internal", "self_reference", "git_history_only"}
                    ), reference
                    source_text = historical_text(reference["source_path"])
                if not mentions(reference["source_path"], source_text, target):
                    via = reference.get("via_source_path")
                    assert relation == "git_history_only" and isinstance(via, str), reference
                    assert mentions(reference["source_path"], source_text, via), reference
                    via_path = ROOT / via
                    via_text = (
                        governance_text(via)
                        if via in governance_paths()
                        else historical_text(via)
                    )
                    assert mentions(via, via_text, target), reference
                assert reference["relation"] in {
                    "closure_internal",
                    "current_worktree_physical",
                    "git_history_only",
                    "historical_cross_reference",
                    "historical_metadata_only",
                    "negative_assertion_only",
                    "retained_evidence_reference",
                    "retirement_assertion_only",
                    "self_reference",
                }


def test_internal_relations_and_actual_full_path_references_are_closed() -> None:
    manifest = load_manifest()
    candidates = {
        item["path"]: item
        for group in manifest["candidate_groups"]
        for item in group["items"]
    }
    ready = {
        item["path"]
        for group in groups_by_status(manifest, "READY_FOR_MANUAL_DELETE")
        for item in group["items"]
    }
    candidate_status = {
        item["path"]: group["status"]
        for group in manifest["candidate_groups"]
        for item in group["items"]
    }
    declared = {
        target: {reference["source_path"] for reference in item["inbound_references"]}
        for target, item in candidates.items()
    }

    for target, item in candidates.items():
        for reference in item["inbound_references"]:
            if reference["relation"] == "closure_internal":
                source = reference["source_path"]
                assert source in candidates, (target, reference)
                assert candidate_status[source] == candidate_status[target], (
                    target,
                    reference,
                )
                if target in ready:
                    assert source in ready, (target, reference)
            if reference["relation"] == "self_reference":
                assert reference["source_path"] == target, (target, reference)

    actual: dict[str, set[str]] = {target: set() for target in candidates}
    for source_path, source_text in governance_text_index().items():
        normalized_source_text = source_text.replace("\\", "/")
        for target in candidates:
            if target in normalized_source_text:
                actual[target].add(source_path)

    undeclared = {
        target: sorted(sources - declared[target])
        for target, sources in actual.items()
        if sources - declared[target]
    }
    assert undeclared == {}


def test_every_candidate_has_exact_dual_hash_git_recovery() -> None:
    manifest = load_manifest()

    for group in manifest["candidate_groups"]:
        for item in group["items"]:
            relative = item["path"]
            baseline = item["recovery_basis"]["commit"]
            blob = GIT_HISTORY.blob(baseline, relative)
            oid, payload = blob.oid, blob.payload
            assert item["recovery_basis"] == {"kind": "git_blob", "commit": baseline}
            assert item["blob_oid"] == oid
            assert item["byte_count"] == len(payload)
            assert item["content_sha256"] == hashlib.sha256(payload).hexdigest()


def test_manual_delete_closures_are_complete_and_atomic() -> None:
    manifest = load_manifest()
    ready = {
        item["path"]: item
        for group in groups_by_status(manifest, "READY_FOR_MANUAL_DELETE")
        for item in group["items"]
    }
    grouped: dict[str, set[str]] = {}
    group_closure = {
        item["path"]: item.get("closure_id", group.get("closure_id"))
        for group in groups_by_status(manifest, "READY_FOR_MANUAL_DELETE")
        for item in group["items"]
    }
    for relative, item in ready.items():
        closure_id = group_closure[relative]
        assert closure_id
        grouped.setdefault(closure_id, set()).add(relative)

    declared = {row["closure_id"]: row for row in manifest["manual_delete_closures"]}
    assert set(grouped) == set(declared)
    assert all(row["all_or_none"] is True for row in declared.values())
    for closure_id, paths in grouped.items():
        row = declared[closure_id]
        assert row["file_count"] == len(paths)
        assert row["byte_count"] == sum(ready[path]["byte_count"] for path in paths)
        assert row["first_path"] == min(paths)


def test_deletion_state_matches_exact_worktree_absence_and_approval() -> None:
    manifest = load_manifest()
    control = manifest["deletion_control"]
    phase2 = manifest["phase2_retirement"]["approval_gate"]
    assert control["execution_state"] == phase2["execution_state"] == "completed"
    ready = {item["path"] for group in groups_by_status(manifest, "READY_FOR_MANUAL_DELETE") for item in group["items"]}
    approved = set(control["approval"]["approved_exact_paths"]) | set(phase2["approved_exact_paths"])
    assert ready == approved
    assert ready.isdisjoint(governance_paths())
    rows = subprocess.check_output(
        ["git", "-C", str(ROOT), "diff", "--no-renames", "--name-status", manifest["audit"]["baseline_commit"], GOVERNANCE_BASELINE],
        text=True, encoding="utf-8",
    ).splitlines()
    changes = [row.split("\t", 1) for row in rows]
    assert {path for status, path in changes if status == "D"} == ready
    allowlist = set(manifest["audit"]["modified_file_allowlist"]) | set(manifest["phase2_retirement"]["modified_file_allowlist"])
    assert {path for _, path in changes} <= ready | allowlist
    # Current worktree changes belong to v2 validation, never this completed receipt.


def test_baseline_docs_and_reports_have_one_effective_classification() -> None:
    manifest = load_manifest()
    resolution = manifest["classification_resolution"]
    summary = resolution["effective_summary"]

    assert resolution["scope"]["expected_file_count"] == 522
    assert resolution["scope"]["expected_git_blob_bytes"] == 7_152_475
    assert sum(row["file_count"] for row in summary.values()) == 522
    assert sum(row["git_blob_bytes"] for row in summary.values()) == 7_152_475
    assert set(summary) == set(manifest["status_definitions"])
    assert resolution["conflict_policy"] == {
        "duplicate_exact_status": "error",
        "equal_specificity_prefix_status": "error",
        "unmatched_baseline_path": "error",
        "ready_selector_type": "exact_file_only",
        "effective_sets_disjoint": True,
    }


def test_legacy_route_surfaces_are_hash_bound_and_never_current_defaults() -> None:
    manifest = load_manifest()
    baseline = manifest["audit"]["baseline_commit"]
    surfaces = manifest["legacy_route_surfaces"]
    candidate_status = {
        item["path"]: group["status"]
        for group in manifest["candidate_groups"]
        for item in group["items"]
    }

    assert len(surfaces) == 10
    assert len({row["path"] for row in surfaces}) == len(surfaces)
    for row in surfaces:
        payload = GIT_HISTORY.blob(baseline, row["path"]).payload
        assert row["route_policy"] == (
            "explicit input or historical fixture only; never a current default"
        )
        assert row["recovery_basis"] == {"kind": "git_blob", "commit": baseline}
        assert row["byte_count"] == len(payload)
        assert row["content_sha256"] == hashlib.sha256(payload).hexdigest()
        if row["status_source"] == "candidate_groups":
            assert row["status"] == candidate_status[row["path"]]
        else:
            assert row["status"] == "LEGACY_BOUND"
        for reference in row["inbound_references"]:
            source = ROOT / reference["source_path"]
            if reference["source_path"] in governance_paths():
                source_text = governance_text(reference["source_path"])
            else:
                assert reference["source_path"] in candidate_status, reference
                source_text = GIT_HISTORY.text(baseline, reference["source_path"], errors="replace")
            assert row["path"] in source_text, reference


def test_explicit_legacy_writers_are_kept_and_git_recoverable() -> None:
    manifest = load_manifest()
    baseline = manifest["audit"]["baseline_commit"]
    writers = manifest["legacy_route_writers"]
    candidate_paths = {
        item["path"]
        for group in manifest["candidate_groups"]
        for item in group["items"]
    }

    assert len(writers) == 5
    assert len({row["path"] for row in writers}) == len(writers)
    for row in writers:
        payload = GIT_HISTORY.blob(baseline, row["path"]).payload
        assert row["status"] == "KEEP_ACTIVE"
        assert row["route_id"] == "old_002837_workflow"
        assert row["write_targets"]
        assert row["recovery_basis"] == {"kind": "git_blob", "commit": baseline}
        assert row["byte_count"] == len(payload)
        assert row["content_sha256"] == hashlib.sha256(payload).hexdigest()
        for reference in row["inbound_references"]:
            source = ROOT / reference["source_path"]
            if reference["source_path"] in governance_paths():
                source_text = governance_text(reference["source_path"])
            else:
                assert reference["source_path"] in candidate_paths, reference
                source_text = GIT_HISTORY.text(baseline, reference["source_path"], errors="replace")
            assert row["path"] in source_text, reference


def test_human_policy_and_formal_database_invariants_remain_untouched() -> None:
    manifest = load_manifest()
    invariants = {row["id"]: row for row in manifest["protected_invariants"]}

    human = invariants["C-HUMAN-005"]
    assert human["status"] == "pending"
    assert human["effective_machine_value"] is None
    assert human["mutation_authorized"] is False
    assert human["authority"] == [
        "AGENTS.md",
        "docs/policies/PERSONAL_HIGH_RISK_EQUITY_STRATEGY_CHARTER.md",
    ]
    database = invariants["formal_portfolio_database"]
    assert database["access"] == "read_only"
    assert database["copy_delete_rebuild_authorized"] is False
    assert database["tracked_or_manifested_content"] is False


def test_ready_expected_configs_are_only_the_closed_three_file_set() -> None:
    manifest = load_manifest()
    ready = {
        item["path"]
        for group in groups_by_status(manifest, "READY_FOR_MANUAL_DELETE")
        for item in group["items"]
        if item["path"].startswith("config/")
        and item["path"].endswith("expected_artifacts.yaml")
    }
    bound = {
        item["path"]
        for group in groups_by_status(manifest, "LEGACY_BOUND")
        for item in group["items"]
        if item["path"].startswith("config/")
    }

    assert ready == {
        "config/r5_bundle8r_expected_artifacts.yaml",
        "config/r5_bundle9r_expected_artifacts.yaml",
        "config/r5_bundle10r_expected_artifacts.yaml",
    }
    assert bound >= {
        "config/r5_bundle3_expected_artifacts.yaml",
        "config/r5_bundle4_expected_artifacts.yaml",
        "config/r5_bundle5_expected_artifacts.yaml",
        "config/r5_patch_1_12_expected_artifacts.yaml",
        "config/r5_patch_49_55_expected_artifacts.yaml",
    }


def test_legacy_generation_bindings_are_ready_only_after_default_cli_retirement() -> None:
    manifest = load_manifest()
    ready = {
        item["path"]
        for group in groups_by_status(manifest, "READY_FOR_MANUAL_DELETE")
        for item in group["items"]
    }

    assert {
        "config/r5_bundle10r_generation_binding.yaml",
        "config/r5_bundle9r_generation_binding.yaml",
    } <= ready
    assert all(
        row["route_policy"]
        == "explicit input or historical fixture only; never a current default"
        for row in manifest["legacy_route_surfaces"]
    )


def test_stale_current_markers_are_quarantined_not_rewritten() -> None:
    manifest = load_manifest()
    status_by_path = {
        item["path"]: group["status"]
        for group in manifest["candidate_groups"]
        for item in group["items"]
    }
    recovery_by_path = {
        item["path"]: item["recovery_basis"]["commit"]
        for group in manifest["candidate_groups"]
        for item in group["items"]
    }
    stale_markers = (
        "state: \"running",
        "Current checkpoint",
        "current checkpoint",
        "latest working",
        "Current workflow",
    )
    scoped_prefixes = ("docs/codex_tasks/", "docs/plans/", "reports/p1_6/")
    phase2_gate = manifest["phase2_retirement"]["approval_gate"]
    approved_paths = set(phase2_gate["approved_exact_paths"])
    quarantine_relative = PurePosixPath(phase2_gate["quarantine_root_after_approval"])
    quarantine_root = ROOT.joinpath(*quarantine_relative.parts)
    stale_paths: set[str] = set()
    for relative in approved_paths:
        if not relative.startswith(scoped_prefixes):
            continue
        pure = PurePosixPath(relative)
        if pure.suffix.lower() not in {".md", ".yaml", ".yml"}:
            continue
        source = ROOT.joinpath(*pure.parts)
        quarantined = quarantine_root.joinpath(*pure.parts)
        locations = [path for path in (source, quarantined) if path.is_file()]
        if locations:
            assert len(locations) == 1, relative
            text = locations[0].read_text(encoding="utf-8", errors="replace")
        else:
            assert phase2_gate["execution_state"] in {
                "user_deleted_pending_commit",
                "completed",
            }
            text = GIT_HISTORY.text(recovery_by_path[relative], relative, errors="replace")
        if any(marker in text for marker in stale_markers):
            stale_paths.add(relative)

    assert stale_paths
    assert stale_paths <= set(status_by_path)
    assert all(
        status_by_path[path] in {
            "LEGACY_BOUND",
            "READY_FOR_MANUAL_DELETE",
            "USER_DECISION",
        }
        for path in stale_paths
    )


def test_protected_review_contracts_and_research_runs_remain_out_of_ready() -> None:
    manifest = load_manifest()
    ready = {
        item["path"]
        for group in groups_by_status(manifest, "READY_FOR_MANUAL_DELETE")
        for item in group["items"]
    }
    protected_exact = {
        row["path"]
        for row in manifest["protected_paths"]
        if "path" in row
    }
    review_contracts = {
        path.replace("\\", "/")
        for path in subprocess.check_output(
            ["git", "-C", str(ROOT), "ls-files", "docs/contracts/**"],
            text=True,
            encoding="utf-8",
        ).splitlines()
        if path
    }

    assert len(review_contracts) == 20
    assert review_contracts <= protected_exact
    assert review_contracts.isdisjoint(ready)
    for prefix in (
        "reports/workflow_runs/wf_20260725_stock_first_002837_v1_policy_refresh/",
        "reports/workflow_runs/wf_20260703_data_layer_002837_invic/",
        "reports/workflow_runs/wf_20260715_stock_first_301217_tongguan_copper_foil/",
        "reports/workflow_runs/wf_20260715_stock_first_600673_hec_tech/",
        "reports/workflow_runs/wf_20260715_stock_first_600988_chifeng_gold/",
        "reports/workflow_runs/wf_20260715_stock_first_603259_wuxi_apptec/",
    ):
        assert not any(path.startswith(prefix) for path in ready)


def test_phase2_closes_the_last_governance_contract_with_git_recovery() -> None:
    manifest = load_manifest()
    ready = {
        item["path"]
        for group in groups_by_status(manifest, "READY_FOR_MANUAL_DELETE")
        for item in group["items"]
    }
    for path in (
        "reports/p1_6/r5_v1_governance_cleanup/historical_baseline_manifest.yaml",
        "reports/p1_6/r5_v1_governance_cleanup/historical_cleanup_manifest.yaml",
        "docs/codex_tasks/v1_governance_integration_cleanup_v8/CONTRACT.md",
        "docs/codex_tasks/v1_governance_integration_cleanup_v11/CONTRACT.md",
        "scripts/manage_r5_v1_historical_cleanup.py",
    ):
        assert path in ready
    assert (
        "docs/codex_tasks/v1_governance_integration_cleanup_v2/CONTRACT.md"
        in ready
    )
    proof = manifest["phase2_retirement"]["evidence_equivalence"][
        "p5_contract_receipt"
    ]
    assert proof["retained_receipt"] == (
        "reports/p1_6/r5_v1_governance_cleanup/validation/p5_authority_conflict.yaml"
    )
    assert proof["recovery_commit"] == manifest["phase2_retirement"]["baseline_commit"]
