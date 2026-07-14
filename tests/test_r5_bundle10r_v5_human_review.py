from copy import deepcopy
from pathlib import Path

import yaml

from scripts.validate_r5_bundle10r_human_review import validate
from src.report.r5_bundle10r_contracts import load_yaml


RUN = Path("reports/workflow_runs/wf_20260703_stock_first_002837_invic")


def _validate(submission: Path) -> dict:
    return validate(
        report=RUN / "R5_bundle10r_reader_v5.md",
        appendix=RUN / "R5_bundle10r_traceability_v5.yaml",
        scorecard=RUN / "R5_bundle10r_reader_v5_quality_scorecard.yaml",
        handoff=RUN / "R5_bundle10r_human_review_handoff_v5.yaml",
        reader_lock=RUN / "R5_bundle10r_reader_generation_lock_v5.yaml",
        submission=submission,
    )


def _write_yaml(path: Path, value: dict) -> None:
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_real_v5_human_review_submission_passes_exact_hash_validation():
    result = _validate(RUN / "R5_bundle10r_human_review_submission_v5.yaml")
    assert result["decision"] == "pass"
    assert result["issue_count"] == 0
    assert result["verified_input_hash_count"] == 5
    assert result["verified_locked_artifact_count"] == 6


def test_failed_checklist_cannot_be_recorded_as_accepted(tmp_path: Path):
    submission = deepcopy(load_yaml(RUN / "R5_bundle10r_human_review_submission_v5.yaml"))
    submission["review_checklist"][0]["status"] = "fail"
    target = tmp_path / "submission.yaml"
    _write_yaml(target, submission)
    result = _validate(target)
    assert result["decision"] == "needs_fix"
    assert any(item["code"] == "review_check_not_passed" for item in result["issues"])


def test_stale_report_hash_cannot_be_recorded_as_accepted(tmp_path: Path):
    submission = deepcopy(load_yaml(RUN / "R5_bundle10r_human_review_submission_v5.yaml"))
    submission["input_hashes"]["report_sha256"] = "0" * 64
    target = tmp_path / "submission.yaml"
    _write_yaml(target, submission)
    result = _validate(target)
    assert result["decision"] == "needs_fix"
    assert any(item["code"] == "review_input_hash_mismatch" for item in result["issues"])
