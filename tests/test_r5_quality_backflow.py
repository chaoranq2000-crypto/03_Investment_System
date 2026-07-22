import csv
import shutil
from pathlib import Path

import pytest
import yaml

from scripts.reconcile_r5_quality_backflow import (
    apply_reconciliation,
    build_reconciliation_plan,
    main,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def _copy_run(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    run = root / "reports/workflow_runs/wf_test"
    run.mkdir(parents=True)
    for name in ("workflow_state.yaml", "workflow_readout.md", "open_todos.csv", "artifact_manifest.csv"):
        shutil.copy2(SOURCE_RUN / name, run / name)
    scorecard = yaml.safe_load((SOURCE_RUN / "R5_stock_research_report_reader_v2_quality_scorecard.yaml").read_text(encoding="utf-8"))
    (run / "R5_stock_research_report_reader_v2_quality_scorecard.yaml").write_text(
        yaml.safe_dump(scorecard, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return root, run


def test_plan_routes_reader_quality_failure_to_evidence_first(tmp_path):
    root, run = _copy_run(tmp_path)
    scorecard = yaml.safe_load((run / "R5_stock_research_report_reader_v2_quality_scorecard.yaml").read_text(encoding="utf-8"))
    state = yaml.safe_load((run / "workflow_state.yaml").read_text(encoding="utf-8"))

    plan = build_reconciliation_plan(
        scorecard,
        state,
        as_of_date="2026-07-12",
        scorecard_path="reports/workflow_runs/wf_test/R5_stock_research_report_reader_v2_quality_scorecard.yaml",
    )

    assert plan["target_state"]["status"] == "needs_fix"
    assert plan["target_state"]["next_stage"] == "T2_evidence_acquire_parse"
    assert plan["target_state"]["required_next_skill"] == "evidence-ingest"
    assert plan["prior_state"]["status"] == state["status"]
    assert len(plan["generated_issues"]) == len(scorecard["candidate_blockers"])


def test_apply_updates_state_todos_manifest_and_supersedes_historical_readout(tmp_path):
    root, run = _copy_run(tmp_path)
    scorecard_path = run / "R5_stock_research_report_reader_v2_quality_scorecard.yaml"
    plan_path = run / "R5_bundle7_quality_backflow_plan.yaml"
    readout_path = run / "R5_bundle7_quality_backflow_readout.md"

    plan = apply_reconciliation(
        root=root,
        run=run,
        scorecard_path=scorecard_path,
        plan_path=plan_path,
        readout_path=readout_path,
        as_of_date="2026-07-12",
    )

    state = yaml.safe_load((run / "workflow_state.yaml").read_text(encoding="utf-8"))
    assert state["status"] == "needs_fix"
    assert state["quality_target"] == "R5_candidate_ready_for_human_review"
    assert state["required_next_skill"] == "evidence-ingest"
    assert state["quality_backflow"]["score"] == plan["score"]
    assert state["quality_backflow"]["historical_acceptance_superseded"] is True
    assert any(
        gate["gate_id"] == "G7"
        and gate["local_check_id"] == "R5_READER_QUALITY_V2"
        and gate["mapped_global_gate_ids"] == ["G7", "G9"]
        and gate["status"] == "fail"
        for gate in state["quality_gates"]
    )
    assert any(item["issue_id"].startswith("R5Q-B7-") for item in state["open_todos"])

    with (run / "open_todos.csv").open(encoding="utf-8", newline="") as handle:
        todo_rows = list(csv.DictReader(handle))
    assert sum(row["issue_id"].startswith("R5Q-B7-") for row in todo_rows) == len(plan["generated_issues"])

    with (run / "artifact_manifest.csv").open(encoding="utf-8", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))
    paths = {row["path"] for row in manifest_rows}
    assert str(scorecard_path.relative_to(root)).replace("\\", "/") in paths
    assert str(plan_path.relative_to(root)).replace("\\", "/") in paths
    assert str(readout_path.relative_to(root)).replace("\\", "/") in paths

    historical = (run / "workflow_readout.md").read_text(encoding="utf-8")
    assert "## Status needs_fix" in historical
    assert "v1_current_control_notice" in historical
    assert "historical_snapshot_superseded_by_bundle7_quality_rebaseline" not in historical

    readout = readout_path.read_text(encoding="utf-8")
    for token in (
        "files_added",
        "files_modified",
        "commands_run",
        "exit_code",
        "stdout_or_stderr_summary",
        "known_todos",
        "next_recommended_patch",
        "inventory_status",
    ):
        assert token in readout
    assert "checked=12" in readout

    # Idempotence: a second application must not duplicate generated issues or artifacts.
    state_before_second_apply = (run / "workflow_state.yaml").read_text(encoding="utf-8")
    prior_state = state["quality_backflow"]["prior_state"]
    prior_exit_criteria = state["quality_backflow"]["prior_exit_criteria"]
    second_plan = apply_reconciliation(
        root=root,
        run=run,
        scorecard_path=scorecard_path,
        plan_path=plan_path,
        readout_path=readout_path,
        as_of_date="2026-07-12",
    )
    with (run / "open_todos.csv").open(encoding="utf-8", newline="") as handle:
        todo_rows_2 = list(csv.DictReader(handle))
    with (run / "artifact_manifest.csv").open(encoding="utf-8", newline="") as handle:
        manifest_rows_2 = list(csv.DictReader(handle))
    state_2 = yaml.safe_load((run / "workflow_state.yaml").read_text(encoding="utf-8"))
    assert len(todo_rows_2) == len(todo_rows)
    assert len(manifest_rows_2) == len(manifest_rows)
    assert second_plan["prior_state"] == prior_state
    assert second_plan["prior_exit_criteria"] == prior_exit_criteria
    assert state_2["quality_backflow"]["prior_state"] == prior_state
    assert state_2["quality_backflow"]["prior_exit_criteria"] == prior_exit_criteria
    assert (run / "workflow_state.yaml").read_text(encoding="utf-8") == state_before_second_apply


def test_cli_requires_explicit_legacy_compatibility_run() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2


def test_cli_rejects_active_v1_state(tmp_path: Path) -> None:
    run = tmp_path / "reports/workflow_runs/wf_v1"
    run.mkdir(parents=True)
    (run / "workflow_state.yaml").write_text(
        "state_schema_version: r5_v1\n", encoding="utf-8"
    )
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--repo-root",
                str(tmp_path),
                "--workflow-run",
                str(run.relative_to(tmp_path)),
                "--legacy-compatibility",
            ]
        )
    assert exc_info.value.code == 2
