from __future__ import annotations

import hashlib
import posixpath
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs/meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml"


def load_manifest() -> dict[str, Any]:
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def groups_by_status(manifest: dict[str, Any], status: str) -> list[dict[str, Any]]:
    return [group for group in manifest["candidate_groups"] if group["status"] == status]


def test_manifest_is_a_decision_record_not_a_deletion_executor() -> None:
    manifest = load_manifest()
    control = manifest["deletion_control"]

    assert control["codex_delete_authorized"] is False
    assert control["directories_authorized"] is False
    assert control["execution_actor"] == "user_manual_exact_file_only"
    assert control["git_history_is_recovery_basis"] is True
    assert set(control["state_contract"]) == {
        "not_started",
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
    rendered = MANIFEST_PATH.read_text(encoding="utf-8").lower()
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


def test_user_decision_keeps_the_2026_07_23_replay_out_of_ready() -> None:
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
    user_decision = {
        item["path"]
        for group in groups_by_status(manifest, "USER_DECISION")
        for item in group["items"]
    }
    tracked_replay = {
        path.replace("\\", "/")
        for path in subprocess.check_output(
            ["git", "-C", str(ROOT), "ls-files", f"{replay_prefix}*"],
            text=True,
            encoding="utf-8",
        ).splitlines()
        if path
    }

    assert tracked_replay
    assert tracked_replay <= user_decision
    assert tracked_replay.isdisjoint(ready)


def test_modified_file_allowlist_is_exact_and_contains_only_authorized_paths() -> None:
    manifest = load_manifest()
    allowlist = manifest["audit"]["modified_file_allowlist"]

    assert allowlist == sorted(set(allowlist))
    assert "docs/meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml" in allowlist
    assert not any(path.startswith("data/") for path in allowlist)
    assert not any(path.startswith("src/portfolio/") for path in allowlist)
    assert not any(path.startswith("src/investment_review/") for path in allowlist)


def test_declared_inbound_references_are_exact_and_auditable() -> None:
    manifest = load_manifest()
    baseline = manifest["audit"]["baseline_commit"]
    candidate_paths = {
        item["path"]
        for group in manifest["candidate_groups"]
        for item in group["items"]
    }

    def historical_text(relative: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(ROOT), "show", f"{baseline}:{relative}"],
        ).decode("utf-8", errors="replace")

    def mentions(source_path: str, source_text: str, target: str) -> bool:
        if target in source_text.replace("\\", "/"):
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
                if source.is_file():
                    source_text = source.read_text(encoding="utf-8", errors="replace")
                else:
                    assert (
                        reference["source_path"] in candidate_paths
                        or relation in {"closure_internal", "self_reference", "git_history_only"}
                    ), reference
                    source_text = historical_text(reference["source_path"])
                assert mentions(reference["source_path"], source_text, target), reference
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

    tracked = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
    ).decode("utf-8").split("\0")
    actual: dict[str, set[str]] = {target: set() for target in candidates}
    for source_path in tracked:
        if not source_path or source_path == MANIFEST_PATH.relative_to(ROOT).as_posix():
            continue
        source = ROOT / source_path
        if not source.is_file():
            continue
        try:
            source_text = source.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
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
    baseline = manifest["audit"]["baseline_commit"]

    for group in manifest["candidate_groups"]:
        for item in group["items"]:
            relative = item["path"]
            payload = subprocess.check_output(
                ["git", "-C", str(ROOT), "show", f"{baseline}:{relative}"],
            )
            oid = subprocess.check_output(
                ["git", "-C", str(ROOT), "rev-parse", f"{baseline}:{relative}"],
                text=True,
                encoding="utf-8",
            ).strip()
            assert item["recovery_basis"] == {
                "kind": "git_blob",
                "commit": baseline,
            }
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
    for relative, item in ready.items():
        grouped.setdefault(item["closure_id"], set()).add(relative)

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
    ready = {
        item["path"]: item
        for group in groups_by_status(manifest, "READY_FOR_MANUAL_DELETE")
        for item in group["items"]
    }
    closures = {
        row["closure_id"]: {
            path
            for path, item in ready.items()
            if item["closure_id"] == row["closure_id"]
        }
        for row in manifest["manual_delete_closures"]
    }
    missing = {path for path in ready if not (ROOT / path).is_file()}
    approved_ids = set(control["approval"]["approved_closure_ids"])
    approved_paths = set(control["approval"]["approved_exact_paths"])
    baseline = manifest["audit"]["baseline_commit"]
    diff_rows = [
        line.split("\t", 1)
        for line in subprocess.check_output(
            ["git", "-C", str(ROOT), "diff", "--no-renames", "--name-status", baseline, "--"],
            text=True,
        ).splitlines()
    ]
    changed_from_baseline = {path for _, path in diff_rows}
    deleted_from_baseline = {path for status, path in diff_rows if status == "D"}
    added_from_baseline = {path for status, path in diff_rows if status == "A"}
    baseline_files = set(
        subprocess.check_output(
            ["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", baseline],
            text=True,
        ).splitlines()
    )
    declared_allowlist = set(manifest["audit"]["modified_file_allowlist"])
    declared_additions = declared_allowlist - baseline_files
    untracked = set(
        subprocess.check_output(
            ["git", "-C", str(ROOT), "ls-files", "--others", "--exclude-standard"],
            text=True,
        ).splitlines()
    )
    staged = set(
        subprocess.check_output(
            ["git", "-C", str(ROOT), "diff", "--cached", "--name-only"],
            text=True,
        ).splitlines()
    )

    assert approved_ids <= set(closures)
    expected = set().union(*(closures[closure_id] for closure_id in approved_ids))
    assert missing == expected
    assert deleted_from_baseline == expected
    assert changed_from_baseline <= declared_allowlist | expected
    assert added_from_baseline <= declared_additions
    if control["execution_state"] == "not_started":
        assert approved_ids == set()
        assert approved_paths == set()
        assert untracked <= declared_additions
    elif control["execution_state"] == "user_deleted_pending_commit":
        assert approved_ids
        assert approved_paths == expected
        assert untracked == set()
        assert staged == set()
    elif control["execution_state"] == "completed":
        assert approved_ids
        assert approved_paths == expected
        assert untracked == set()
        assert staged == set()
        for path in expected:
            current_head = subprocess.run(
                ["git", "-C", str(ROOT), "cat-file", "-e", f"HEAD:{path}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            assert current_head.returncode != 0, path
    else:
        raise AssertionError(f"unknown deletion state: {control['execution_state']}")


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
        payload = subprocess.check_output(
            ["git", "-C", str(ROOT), "show", f"{baseline}:{row['path']}"],
        )
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
            if source.is_file():
                source_text = source.read_text(encoding="utf-8", errors="replace")
            else:
                assert reference["source_path"] in candidate_status, reference
                source_text = subprocess.check_output(
                    [
                        "git",
                        "-C",
                        str(ROOT),
                        "show",
                        f"{baseline}:{reference['source_path']}",
                    ],
                ).decode("utf-8", errors="replace")
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
        payload = subprocess.check_output(
            ["git", "-C", str(ROOT), "show", f"{baseline}:{row['path']}"],
        )
        assert row["status"] == "KEEP_ACTIVE"
        assert row["route_id"] == "old_002837_workflow"
        assert row["write_targets"]
        assert row["recovery_basis"] == {"kind": "git_blob", "commit": baseline}
        assert row["byte_count"] == len(payload)
        assert row["content_sha256"] == hashlib.sha256(payload).hexdigest()
        for reference in row["inbound_references"]:
            source = ROOT / reference["source_path"]
            if source.is_file():
                source_text = source.read_text(encoding="utf-8", errors="replace")
            else:
                assert reference["source_path"] in candidate_paths, reference
                source_text = subprocess.check_output(
                    [
                        "git",
                        "-C",
                        str(ROOT),
                        "show",
                        f"{baseline}:{reference['source_path']}",
                    ],
                ).decode("utf-8", errors="replace")
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
    stale_markers = (
        "state: \"running",
        "Current checkpoint",
        "current checkpoint",
        "latest working",
        "Current workflow",
    )
    scoped_roots = (
        ROOT / "docs/codex_tasks",
        ROOT / "docs/plans",
        ROOT / "reports/p1_6",
    )
    stale_paths: set[str] = set()
    for scoped_root in scoped_roots:
        for path in scoped_root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".md", ".yaml", ".yml"}:
                text = path.read_text(encoding="utf-8", errors="replace")
                if any(marker in text for marker in stale_markers):
                    stale_paths.add(path.relative_to(ROOT).as_posix())

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


def test_retired_governance_control_plane_has_explicit_exception_for_p5_evidence() -> None:
    manifest = load_manifest()
    ready = {
        item["path"]
        for group in groups_by_status(manifest, "READY_FOR_MANUAL_DELETE")
        for item in group["items"]
    }
    bound = {
        item["path"]
        for group in groups_by_status(manifest, "LEGACY_BOUND")
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
        in bound
    )
