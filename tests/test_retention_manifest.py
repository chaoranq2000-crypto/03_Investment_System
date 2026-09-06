from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs/meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml"


def validate(data):
    spec = importlib.util.spec_from_file_location("retention_doc_check", ROOT / "scripts/check_doc_drift.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    errors = []
    module.check_retention_manifest(errors, manifest=data)
    return errors


@pytest.fixture
def manifest():
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_current_retention_contract_and_recovery_identity_pass(manifest):
    assert validate(manifest) == []
    assert len(manifest["retired_paths"]) == 476
    assert "candidate_groups" not in manifest
    assert "phase2_retirement" not in manifest


def test_current_products_evidence_and_pointer_selected_runs_remain_protected(manifest):
    exact = {row["path"] for row in manifest["protected_paths"] if "path" in row}
    prefixes = {row["path_prefix"] for row in manifest["protected_paths"] if "path_prefix" in row}
    assert {
        "AGENTS.md", "README.md", "docs/index.md",
        "docs/workflows/RESEARCH_WORKFLOW.md", "docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md",
        "config/r5_readout_canonical_index.yaml",
        "docs/policies/PERSONAL_HIGH_RISK_EQUITY_STRATEGY_CHARTER.md",
    } <= exact
    assert {path.relative_to(ROOT).as_posix() for path in (ROOT / "docs/contracts").glob("*.json")} <= exact
    assert {"data/raw/", "data/manifests/", "reports/segments/", "reports/stocks/"} <= prefixes
    pointer = yaml.safe_load((ROOT / "config/r5_readout_canonical_index.yaml").read_text(encoding="utf-8"))
    for run in pointer["current_runs"].values():
        state = run["state_path"]
        assert state in exact or any(state.startswith(prefix) for prefix in prefixes)


@pytest.mark.parametrize("value", ["../outside.yaml", "C:/outside.yaml", "config/*.yaml"])
def test_retention_rejects_nonliteral_or_escaping_candidates(manifest, value):
    manifest["manual_delete_candidates"][0]["path"] = value
    assert any("unsafe or non-literal" in error for error in validate(manifest))


def test_retention_rejects_protected_deletion_and_reused_approval(manifest):
    manifest["manual_delete_candidates"][0]["path"] = "AGENTS.md"
    manifest["deletion_control"]["prior_approvals_apply_to_new_candidates"] = True
    errors = validate(manifest)
    assert any("conflicts with retired/protected" in error for error in errors)
    assert any("old approvals cannot be reused" in error for error in errors)


def test_retention_rejects_corrupted_recovery_snapshot(manifest):
    manifest["history"]["snapshot"]["content_sha256"] = "0" * 64
    assert any("integrity mismatch" in error for error in validate(manifest))


def test_retention_rejects_restored_paths_and_physical_readers(manifest):
    manifest["retired_paths"].append("pyproject.toml")
    manifest["allowed_retired_references"][0]["relation"] = "current_worktree_physical"
    errors = validate(manifest)
    assert any("has reappeared" in error for error in errors)
    assert any("current physical dependency" in error for error in errors)


def test_retention_rejects_candidate_with_live_dependency(manifest):
    manifest["manual_delete_candidates"][0]["inbound_references"][0]["relation"] = "current_worktree_physical"
    assert any("candidate still has a current physical dependency" in error for error in validate(manifest))


def test_retention_rejects_policy_and_ledger_boundary_changes(manifest):
    for row in manifest["protected_invariants"]:
        if row["id"] == "C-HUMAN-005":
            row["effective_machine_value"] = 0.3
        if row["id"] == "formal_portfolio_database":
            row["access"] = "read_write"
    errors = validate(manifest)
    assert any("C-HUMAN-005" in error for error in errors)
    assert any("database protection" in error for error in errors)


@pytest.mark.legacy_compatibility
def test_v2_preserves_all_published_retirements_and_protected_evidence(manifest):
    from conftest import governance_snapshot

    old = governance_snapshot()
    retired = {
        row["path"]
        for group in old["candidate_groups"]
        if group["status"] == "READY_FOR_MANUAL_DELETE"
        for row in group["items"]
    }
    assert set(manifest["retired_paths"]) == retired
    assert manifest["protected_paths"] == old["protected_paths"]
    assert manifest["protected_invariants"] == old["protected_invariants"]
    assert manifest["retired_route_tokens"] == old["retired_route_tokens"]
