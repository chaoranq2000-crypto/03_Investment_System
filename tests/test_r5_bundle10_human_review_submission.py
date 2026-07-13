from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
SCRIPT = ROOT / "scripts/validate_r5_bundle10_human_review_submission.py"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_r5_bundle10_human_review_submission", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pending_template_cannot_be_mistaken_for_human_signoff() -> None:
    result = load_module().validate_submission(
        RUN,
        RUN / "R5_stock_research_report_reader_v3_human_review_submission_template.yaml",
    )
    assert result["decision"] == "fail"
    assert result["eligible_for_bundle10_final_close"] is False
    assert any("external_reviewer" in error for error in result["errors"])
    assert any("attestation" in error for error in result["errors"])


def test_finalized_human_submission_validates_without_mutating_handoff() -> None:
    handoff_path = RUN / "R5_stock_research_report_reader_v3_human_review.yaml"
    before = handoff_path.read_bytes()
    result = load_module().validate_submission(
        RUN,
        RUN / "R5_stock_research_report_reader_v3_human_review_submission.yaml",
    )
    assert result["decision"] == "pass", result["errors"]
    assert result["eligible_for_bundle10_final_close"] is True
    assert result["checklist_pass_count"] == 6
    assert result["reviewer"] == "Q"
    assert result["handoff_status"] == "passed_external_human_review"
    assert handoff_path.read_bytes() == before
