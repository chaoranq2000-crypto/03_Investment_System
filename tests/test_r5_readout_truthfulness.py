from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/check_r5_readout_truthfulness.py"


def load_checker():
    spec = importlib.util.spec_from_file_location(
        "check_r5_readout_truthfulness", SCRIPT_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_minimal_repo(root: Path) -> None:
    for path in (
        "AGENTS.md",
        "docs/workflows/RESEARCH_WORKFLOW.md",
        "docs/meta/DOC_OWNERSHIP_MATRIX.md",
        "docs/meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml",
    ):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fixture\n", encoding="utf-8")

    workflow_id = "wf_fixture_current"
    run = root / "reports/workflow_runs" / workflow_id
    run.mkdir(parents=True)
    state_path = f"reports/workflow_runs/{workflow_id}/workflow_state.yaml"
    readout_path = f"reports/workflow_runs/{workflow_id}/workflow_readout.md"
    state = {
        "workflow_id": workflow_id,
        "status": "accepted_with_todos",
        "p2_ready": False,
        "artifacts": [
            {"path": state_path, "status": "current"},
            {"path": readout_path, "status": "current"},
        ],
    }
    (run / "workflow_state.yaml").write_text(
        yaml.safe_dump(state, sort_keys=False), encoding="utf-8"
    )
    (run / "workflow_readout.md").write_text(
        "# Current workflow readout\n\n"
        f"- Workflow: `{workflow_id}`\n"
        "- Derived automatic status: `accepted_with_todos`\n",
        encoding="utf-8",
    )
    index = {
        "schema_version": "research_current_run_pointer_v1",
        "status": "active",
        "authority": {
            "project_rules": "AGENTS.md",
            "research_workflow": "docs/workflows/RESEARCH_WORKFLOW.md",
            "document_ownership": "docs/meta/DOC_OWNERSHIP_MATRIX.md",
            "retention_manifest": "docs/meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml",
        },
        "history": {
            "storage": "git_history",
            "current_selection_allowed": False,
        },
        "current_runs": {
            "fixture": {
                "workflow_id": workflow_id,
                "state_path": state_path,
                "readout_path": readout_path,
            }
        },
    }
    config = root / "config"
    config.mkdir()
    (config / "r5_readout_canonical_index.yaml").write_text(
        yaml.safe_dump(index, sort_keys=False), encoding="utf-8"
    )


def test_current_pointer_and_readout_pass(tmp_path: Path) -> None:
    checker = load_checker()
    write_minimal_repo(tmp_path)

    report = checker.check_current_pointers(tmp_path, checker.DEFAULT_RULES)

    assert report["truthfulness_status"] == "pass"
    assert report["checked"] == 1
    assert report["failed"] == 0
    assert report["results"][0]["workflow_status"] == "accepted_with_todos"
    assert report["results"][0]["p2_ready"] is False


def test_legacy_registry_keys_fail_current_control_plane(tmp_path: Path) -> None:
    checker = load_checker()
    write_minimal_repo(tmp_path)
    path = tmp_path / "config/r5_readout_canonical_index.yaml"
    index = yaml.safe_load(path.read_text(encoding="utf-8"))
    index["readouts"] = [{"path": "reports/p1_6/legacy.md"}]
    path.write_text(yaml.safe_dump(index, sort_keys=False), encoding="utf-8")

    report = checker.check_current_pointers(tmp_path, checker.DEFAULT_RULES)

    assert report["truthfulness_status"] == "fail"
    assert any("legacy top-level key" in issue for issue in report["issues"])


def test_pointer_state_mismatch_and_missing_current_artifact_fail(tmp_path: Path) -> None:
    checker = load_checker()
    write_minimal_repo(tmp_path)
    state_path = tmp_path / "reports/workflow_runs/wf_fixture_current/workflow_state.yaml"
    state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    state["workflow_id"] = "wf_wrong"
    state["artifacts"] = state["artifacts"][:1]
    state_path.write_text(yaml.safe_dump(state, sort_keys=False), encoding="utf-8")

    report = checker.check_current_pointers(tmp_path, checker.DEFAULT_RULES)

    assert report["truthfulness_status"] == "fail"
    issues = report["results"][0]["issues"]
    assert "workflow_id differs between pointer and state" in issues
    assert any("current artifact registry is missing" in issue for issue in issues)


def test_near_match_status_cannot_pass_exact_readout_projection(tmp_path: Path) -> None:
    checker = load_checker()
    write_minimal_repo(tmp_path)
    state_path = tmp_path / "reports/workflow_runs/wf_fixture_current/workflow_state.yaml"
    state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    state["status"] = "accepted"
    state_path.write_text(yaml.safe_dump(state, sort_keys=False), encoding="utf-8")

    report = checker.check_current_pointers(tmp_path, checker.DEFAULT_RULES)

    assert report["truthfulness_status"] == "fail"
    assert "workflow status differs between state and readout" in report["results"][0]["issues"]


def test_unsafe_or_non_run_scoped_paths_fail(tmp_path: Path) -> None:
    checker = load_checker()
    write_minimal_repo(tmp_path)
    path = tmp_path / "config/r5_readout_canonical_index.yaml"
    index = yaml.safe_load(path.read_text(encoding="utf-8"))
    index["current_runs"]["fixture"]["state_path"] = "../outside.yaml"
    path.write_text(yaml.safe_dump(index, sort_keys=False), encoding="utf-8")

    report = checker.check_current_pointers(tmp_path, checker.DEFAULT_RULES)

    assert report["truthfulness_status"] == "fail"
    assert "unsafe repository path" in report["results"][0]["issues"][0]


def test_cli_strict_returns_nonzero_for_invalid_pointer(tmp_path: Path, capsys) -> None:
    checker = load_checker()
    write_minimal_repo(tmp_path)
    (tmp_path / "docs/meta/DOC_OWNERSHIP_MATRIX.md").unlink()

    exit_code = checker.main(["--repo-root", str(tmp_path), "--strict"])

    assert exit_code == 1
    assert "truthfulness_status=fail" in capsys.readouterr().out
