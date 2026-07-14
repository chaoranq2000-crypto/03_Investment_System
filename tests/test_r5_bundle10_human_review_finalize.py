from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
SCRIPT = ROOT / "scripts/finalize_r5_bundle10_after_human_review.py"


def load_module():
    spec = importlib.util.spec_from_file_location("finalize_r5_bundle10_after_human_review", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare_run(tmp_path: Path) -> tuple[Path, Path]:
    run = tmp_path / RUN.name
    run.mkdir()
    for name in (
        "R5_stock_research_report_reader_v3.md",
        "R5_stock_research_report_traceability_v3.yaml",
        "R5_stock_research_report_reader_v3_quality_scorecard.yaml",
        "R5_stock_research_report_reader_v3_human_review.yaml",
        "R5_stock_research_report_reader_v3_human_review_submission_template.yaml",
        "workflow_state.yaml",
        "open_todos.csv",
        "R5_bundle10_quality_issues.csv",
        "artifact_manifest.csv",
        "run_log.md",
    ):
        shutil.copy2(RUN / name, run / name)
    handoff_path = run / "R5_stock_research_report_reader_v3_human_review.yaml"
    handoff = yaml.safe_load(handoff_path.read_text(encoding="utf-8"))
    handoff.update(
        {
            "external_reviewer": None,
            "reviewed_at": None,
            "status": "pending_external_human_review",
            "blocking_comments": [],
            "nonblocking_comments": [],
            "signoff_fields": {
                "decision": None,
                "reviewer_name": None,
                "reviewed_at": None,
                "report_sha256_confirmed": None,
                "blocking_comment_count": None,
            },
            "sample_quality_report_allowed": False,
            "p2_allowed": False,
        }
    )
    handoff.pop("external_review_submission_path", None)
    for row in handoff["required_checklist"]:
        row["status"] = "pending"
        row.pop("comment", None)
    handoff_path.write_text(
        yaml.safe_dump(handoff, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    state_path = run / "workflow_state.yaml"
    state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    state.update(
        {
            "status": "needs_fix",
            "quality_target": "R5_candidate_ready_for_human_review",
            "current_stage": "R5_bundle10_external_human_review_pending",
            "next_stage": "R5_bundle10_external_human_review",
            "required_next_skill": "quality-review",
            "external_action_required": "human_review",
        }
    )
    state.pop("bundle10_close", None)
    state["reader_candidate_snapshot"].update(
        {
            "decision": "candidate_ready_for_human_review",
            "quality_band": "candidate_ready_for_human_review",
            "human_review_status": "pending_external",
            "sample_quality_report_allowed": False,
            "p2_allowed": False,
        }
    )
    state["bundle10_internal_completion"].update(
        {
            "decision": "candidate_ready_for_human_review",
            "bundle_closed": False,
            "external_human_review": "pending",
            "sample_quality_allowed": False,
            "p2_allowed": False,
            "next_gate": "R5_bundle10_external_human_review",
        }
    )
    state["quality_backflow"].update(
        {
            "decision": "candidate_ready_for_human_review",
            "quality_band": "candidate_ready_for_human_review",
            "current_first_route": "external_human_review",
            "current_first_stage": "R5_bundle10_external_human_review",
            "sample_quality_report_allowed": False,
            "p2_allowed": False,
        }
    )
    state_path.write_text(
        yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    submission = yaml.safe_load(
        (run / "R5_stock_research_report_reader_v3_human_review_submission_template.yaml").read_text(
            encoding="utf-8"
        )
    )
    submission.update(
        {
            "external_reviewer": "test_human_reviewer",
            "reviewed_at": "2026-07-13T12:00:00+08:00",
            "decision": "pass",
            "attestation": {
                "external_human_review_confirmed": True,
                "report_read_in_full": True,
                "traceability_consulted_as_needed": True,
                "automated_agent_generated": False,
            },
        }
    )
    for row in submission["required_checklist"]:
        row["status"] = "pass"
        row["comment"] = "test fixture only"
    submission_path = run / "R5_stock_research_report_reader_v3_human_review_submission.yaml"
    submission_path.write_text(
        yaml.safe_dump(submission, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return run, submission_path


def test_finalizer_closes_only_a_validated_temp_human_submission(tmp_path: Path) -> None:
    run, submission_path = prepare_run(tmp_path)
    result = load_module().finalize_bundle10(run, submission_path)
    assert result["decision"] == "pass"
    assert result["sample_quality_allowed"] is True
    assert result["p2_allowed"] is False
    state = yaml.safe_load((run / "workflow_state.yaml").read_text(encoding="utf-8"))
    handoff = yaml.safe_load(
        (run / "R5_stock_research_report_reader_v3_human_review.yaml").read_text(encoding="utf-8")
    )
    assert state["status"] == "accepted_with_todos"
    assert state["bundle10_close"]["bundle_closed"] is True
    assert state["bundle10_close"]["sample_quality_allowed"] is True
    assert state["bundle10_close"]["p2_allowed"] is False
    assert handoff["status"] == "passed_external_human_review"
    assert handoff["external_reviewer"] == "test_human_reviewer"
    assert (run / "bundle10_final_close_readout.md").exists()
    assert (run / "R5_bundle10_final_close_validation.json").exists()


def test_real_workflow_remains_finalized_after_temp_finalizer_test() -> None:
    state = yaml.safe_load((RUN / "workflow_state.yaml").read_text(encoding="utf-8"))
    handoff = yaml.safe_load(
        (RUN / "R5_stock_research_report_reader_v3_human_review.yaml").read_text(encoding="utf-8")
    )
    assert state["current_stage"] in {"T10_close_readout", "R5_bundle9r_closed", "T9_quality_review"}
    if state["current_stage"] == "R5_bundle9r_closed":
        assert state["bundle9r_close"]["bundle_closed"] is True
        assert state["bundle9r_close"]["historical_bundle10_preserved"] is True
    if state["current_stage"] == "T9_quality_review":
        assert state["bundle10r_v5_human_review"]["decision"] == "revision_required"
        assert state["sample_quality_allowed"] is False
    assert state["bundle10_internal_completion"]["bundle_closed"] is True
    assert state["bundle10_internal_completion"]["p2_allowed"] is False
    assert handoff["status"] == "passed_external_human_review"
    assert handoff["external_reviewer"] == "Q"
    assert handoff["p2_allowed"] is False
    assert (RUN / "R5_stock_research_report_reader_v3_human_review_submission.yaml").exists()
