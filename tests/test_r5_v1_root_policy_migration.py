from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from conftest import governance_snapshot
import pytest


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "config/r5_readout_canonical_index.yaml"
MANIFEST = ROOT / "docs/meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml"
STATE_REL = (
    "reports/workflow_runs/"
    "wf_20260725_stock_first_002837_v1_policy_refresh/workflow_state.yaml"
)
READOUT_REL = (
    "reports/workflow_runs/"
    "wf_20260725_stock_first_002837_v1_policy_refresh/workflow_readout.md"
)


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_current_pointer_replaces_root_policy_migration_as_authority() -> None:
    index = load_yaml(INDEX)

    assert "policy_migrations" not in index
    assert "readouts" not in index
    assert index["schema_version"] == "research_current_run_pointer_v1"
    assert index["authority"] == {
        "project_rules": "AGENTS.md",
        "research_workflow": "docs/workflows/RESEARCH_WORKFLOW.md",
        "document_ownership": "docs/meta/DOC_OWNERSHIP_MATRIX.md",
        "retention_manifest": "docs/meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml",
    }
    assert index["history"]["storage"] == "git_history"
    assert index["history"]["current_selection_allowed"] is False


def test_current_policy_refresh_state_keeps_exact_outcome_and_p2_boundary() -> None:
    state = load_yaml(ROOT / STATE_REL)

    assert state["status"] == "accepted_with_todos"
    assert state["p2_ready"] is False
    assert state["system_v1_complete"] is False
    assert state["sample_quality_ready"] is False
    assert state["release_ready"] is False
    assert state["final_report_review_status"] == "not_requested"
    assert state["final_report_review"]["report_path"] is None
    assert state["final_report_review"]["decision"] == "not_requested"


def test_current_state_validator_and_readout_projection_agree() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / ".agents/skills/research-orchestrator/scripts/"
                "validate_workflow_state.py"
            ),
            str(ROOT / STATE_REL),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr

    state = load_yaml(ROOT / STATE_REL)
    readout = (ROOT / READOUT_REL).read_text(encoding="utf-8")
    assert state["workflow_id"] in readout
    assert state["status"] in readout
    assert "p2_ready=false" in readout
    assert "system_v1_complete=false" in readout


def test_unresolved_research_limits_remain_visible_nonblocking_and_unused() -> None:
    state = load_yaml(ROOT / STATE_REL)
    todos = state["open_todos"]

    assert len(todos) == 4
    assert len({row["issue_id"] for row in todos}) == 4
    assert all(row["status"] == "open" for row in todos)
    assert all(row["blocks_current_goal"] is False for row in todos)
    assert all(row["used_in_numeric_calculation"] is False for row in todos)
    assert {row["active_disposition"] for row in todos} == {
        "unknown",
        "method_unavailable",
    }
    assert all(row.get("resolved_at") in {"", None} for row in todos)


def test_quality_gates_and_current_artifacts_remain_complete() -> None:
    state = load_yaml(ROOT / STATE_REL)
    gates = {row["gate_id"]: row["status"] for row in state["quality_gates"]}

    assert set(gates) == {f"G{i}" for i in range(11)}
    assert gates["G5"] == "not_applicable"
    assert all(status == "pass" for gate, status in gates.items() if gate != "G5")
    current_paths = {
        row["path"]
        for row in state["artifacts"]
        if row["status"] == "current" and row["required"] is True
    }
    assert STATE_REL in current_paths
    assert READOUT_REL in current_paths
    assert all((ROOT / path).is_file() for path in current_paths)


def run_mutated_state(tmp_path: Path, mutate) -> subprocess.CompletedProcess[str]:
    state = load_yaml(ROOT / STATE_REL)
    mutate(state)
    target = tmp_path / "workflow_state.yaml"
    target.write_text(yaml.safe_dump(state, sort_keys=False), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / ".agents/skills/research-orchestrator/scripts/"
                "validate_workflow_state.py"
            ),
            str(target),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_current_state_rejects_fake_p2_promotion(tmp_path: Path) -> None:
    completed = run_mutated_state(
        tmp_path,
        lambda state: state.__setitem__("p2_ready", True),
    )

    assert completed.returncode == 1
    assert "p2_ready=true requires workflow_type=comparison_readiness_gate" in completed.stderr


def test_current_state_rejects_hidden_blocking_unknown(tmp_path: Path) -> None:
    def mutate(state: dict[str, Any]) -> None:
        state["open_todos"][0]["blocks_current_goal"] = True

    completed = run_mutated_state(tmp_path, mutate)

    assert completed.returncode == 1
    assert "expected needs_fix" in completed.stderr


def test_current_state_rejects_fake_historical_resolution(tmp_path: Path) -> None:
    def mutate(state: dict[str, Any]) -> None:
        for todo in state["open_todos"]:
            todo["status"] = "closed"
            todo["resolved_at"] = "2026-08-22"

    completed = run_mutated_state(tmp_path, mutate)

    assert completed.returncode == 1
    assert "workflow status accepted_with_todos is inconsistent" in completed.stderr


@pytest.mark.legacy_compatibility
def test_retired_root_policy_artifacts_are_git_recoverable_not_current_authority() -> None:
    manifest = governance_snapshot()
    ready = {
        item["path"]: item
        for group in manifest["candidate_groups"]
        if group["status"] == "READY_FOR_MANUAL_DELETE"
        for item in group["items"]
    }
    expectations = {
        "reports/p1_6/r5_v1_governance_cleanup/root_policy_migration.yaml": [
            "AGENTS.md",
            "docs/workflows/RESEARCH_WORKFLOW.md",
            "docs/meta/DOC_OWNERSHIP_MATRIX.md",
            "config/r5_readout_canonical_index.yaml.current_runs",
        ],
        "reports/p1_6/r5_v1_governance_cleanup/validation/blocker_root_reconciliation.yaml": [
            "AGENTS.md",
            "docs/workflows/RESEARCH_WORKFLOW.md",
            "docs/meta/DOC_OWNERSHIP_MATRIX.md",
            "config/r5_readout_canonical_index.yaml.current_runs",
        ],
        "scripts/validate_r5_v1_root_policy_migration.py": [
            "AGENTS.md",
            "docs/workflows/RESEARCH_WORKFLOW.md",
            STATE_REL,
        ],
        "schemas/r5_v1_root_policy_migration.schema.json": [
            "AGENTS.md",
            "docs/workflows/RESEARCH_WORKFLOW.md",
            STATE_REL,
        ],
    }
    for path, replacement in expectations.items():
        assert path in ready
        item = ready[path]
        assert item["recovery_basis"]["kind"] == "git_blob"
        assert item["replacement_authority"] == replacement
