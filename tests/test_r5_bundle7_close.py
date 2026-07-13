from __future__ import annotations

import csv
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
CLOSE = ROOT / "reports/p1_6/R5_BUNDLE_7_QUALITY_REBASE_AND_BACKFLOW_CLOSE_READOUT.md"
QUALITY = RUN / "R5_bundle7_quality_gate_report.md"
BUNDLE6_CLOSE = "reports/p1_6/R5_BUNDLE_6_READER_REPORT_QUALITY_REMEDIATION_CLOSE_READOUT.md"
BUNDLE7_CLOSE = "reports/p1_6/R5_BUNDLE_7_QUALITY_REBASE_AND_BACKFLOW_CLOSE_READOUT.md"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_bundle7_reader_remains_historical_fail_closed_while_current_workflow_advances() -> None:
    scorecard = load_yaml(RUN / "R5_stock_research_report_reader_v2_quality_scorecard.yaml")
    state = load_yaml(RUN / "workflow_state.yaml")

    assert scorecard["decision"] == "rejected"
    assert scorecard["quality_band"] == "research_draft"
    assert scorecard["score"] == 59 and scorecard["threshold"] == 82
    assert scorecard["truthfulness_status"] == "pass"
    assert scorecard["human_review_status"] == "not_ready"
    assert not scorecard["sample_quality_report_allowed"] and not scorecard["p2_allowed"]
    assert state["status"] == "accepted_with_todos"
    assert state["current_stage"] in {"T10_close_readout", "R5_bundle9r_closed"}
    assert state["next_stage"] is None
    assert state["required_next_skill"] is None
    assert state["bundle10_close"]["bundle_closed"] is True
    assert state.get("quality_backflow", {}).get("sample_quality_report_allowed") is (
        False if state["current_stage"] == "R5_bundle9r_closed" else True
    )
    assert state.get("quality_backflow", {}).get("p2_allowed") is False


def test_backflow_issues_routes_and_manifest_are_unique() -> None:
    plan = load_yaml(RUN / "R5_bundle7_quality_backflow_plan.yaml")
    assert len(plan["generated_issues"]) == 12
    assert len({row["issue_id"] for row in plan["generated_issues"]}) == 12
    assert len(plan["fix_routes"]) == 7
    assert plan["fix_routes"][0]["owner_skill"] == "evidence-ingest"

    with (RUN / "open_todos.csv").open(encoding="utf-8", newline="") as handle:
        todos = [row for row in csv.DictReader(handle) if row["issue_id"].startswith("R5Q-B7-")]
    assert len(todos) == len({row["issue_id"] for row in todos}) == 12

    with (RUN / "artifact_manifest.csv").open(encoding="utf-8", newline="") as handle:
        manifest_paths = [row["path"] for row in csv.DictReader(handle)]
    expected = {
        "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_report_reader_v2_quality_scorecard.yaml",
        "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle7_quality_backflow_plan.yaml",
        "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle7_quality_backflow_readout.md",
        "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle7_quality_gate_report.md",
        BUNDLE7_CLOSE,
    }
    assert all(manifest_paths.count(path) == 1 for path in expected)


def test_current_quality_report_supersedes_old_sample_quality_surface() -> None:
    current = QUALITY.read_text(encoding="utf-8")
    historical = (RUN / "quality_gate_report.md").read_text(encoding="utf-8")

    assert "status: `needs_fix`" in current
    assert "12 个 medium issue" in current
    assert "first owner" not in current
    assert "首个修复 owner 是 `evidence-ingest`" in current
    assert "historical_snapshot_superseded_by_bundle7_quality_rebaseline" in historical
    assert "R5_bundle7_quality_gate_report.md" in historical


def test_canonical_indexes_supersede_bundle6_and_activate_bundle7_close() -> None:
    index_md = (ROOT / "reports/p1_6/R5_READOUT_CANONICAL_INDEX.md").read_text(encoding="utf-8")
    index_yaml = load_yaml(ROOT / "config/r5_readout_canonical_index.yaml")
    entries = {row["path"]: row for row in index_yaml["readouts"]}

    assert f"| `{BUNDLE6_CLOSE}` | `superseded` | `false` |" in index_md
    assert f"| `{BUNDLE7_CLOSE}` | `canonical` | `true` |" in index_md
    assert entries[BUNDLE6_CLOSE]["canonical_status"] == "superseded"
    assert entries[BUNDLE6_CLOSE]["blocking_for_strict_smoke"] is False
    assert entries[BUNDLE6_CLOSE]["replacement_or_supplement_path"] == BUNDLE7_CLOSE
    assert entries[BUNDLE7_CLOSE]["canonical_status"] == "canonical"
    assert entries[BUNDLE7_CLOSE]["blocking_for_strict_smoke"] is True


def test_close_readout_contains_auditable_execution_and_hard_boundaries() -> None:
    text = CLOSE.read_text(encoding="utf-8")
    for token in (
        "files_added",
        "files_modified",
        "commands_run",
        "exit_code",
        "stdout_or_stderr_summary",
        "artifact_evidence",
        "known_todos",
        "next_recommended_patch",
    ):
        assert token in text
    assert "current_reader_score: `59/100`" in text
    assert "historical_bundle6_score_100_superseded: `true`" in text
    assert "sample_quality_report_allowed: `false`" in text
    assert "p2_allowed: `false`" in text
    assert "candidate_blockers: `12`" in text
    for forbidden in ("买入", "卖出", "持有评级", "建议仓位", "目标价"):
        assert forbidden not in text


def test_close_readout_records_rollback_ci_and_merge_evidence() -> None:
    text = CLOSE.read_text(encoding="utf-8")
    assert "tracked_worktree_clean=true" in text
    assert "29196388267" in text and "29196389723" in text
    assert "https://github.com/chaoranq2000-crypto/03_Investment_System/pull/1" in text
    assert "1530e7e291efe9176aca0e93b54d3dc482d3d2f9" in text
    assert "TODO_FINAL_" not in text
