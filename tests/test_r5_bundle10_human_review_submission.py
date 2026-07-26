from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
SCRIPT = ROOT / "scripts/validate_r5_bundle10_human_review_submission.py"
SUBMISSION_INPUTS = (
    "R5_stock_research_report_reader_v3_human_review.yaml",
    "R5_stock_research_report_reader_v3_quality_scorecard.yaml",
    "R5_stock_research_report_reader_v3.md",
    "R5_stock_research_report_traceability_v3.yaml",
    "R5_stock_research_report_reader_v3_human_review_submission_template.yaml",
    "R5_stock_research_report_reader_v3_human_review_submission.yaml",
)
WINDOWS_HASH_INPUTS = {
    "R5_stock_research_report_reader_v3.md",
    "R5_stock_research_report_traceability_v3.yaml",
}


def load_module():
    spec = importlib.util.spec_from_file_location("validate_r5_bundle10_human_review_submission", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def materialize_submission_run(tmp_path: Path, historical_blob_bytes) -> Path:
    run = tmp_path / "bundle10_submission_run"
    for name in SUBMISSION_INPUTS:
        target = run / name
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = historical_blob_bytes(f"{HISTORICAL_RUN}/{name}")
        if name in WINDOWS_HASH_INPUTS:
            assert b"\r\n" not in payload
            payload = payload.replace(b"\n", b"\r\n")
        target.write_bytes(payload)
    return run


def test_pending_template_cannot_be_mistaken_for_human_signoff(
    tmp_path: Path,
    historical_blob_bytes,
) -> None:
    run = materialize_submission_run(tmp_path, historical_blob_bytes)
    result = load_module().validate_submission(
        run,
        run / "R5_stock_research_report_reader_v3_human_review_submission_template.yaml",
    )
    assert result["decision"] == "fail"
    assert result["eligible_for_bundle10_final_close"] is False
    assert any("external_reviewer" in error for error in result["errors"])
    assert any("attestation" in error for error in result["errors"])


def test_finalized_human_submission_validates_without_mutating_handoff(
    tmp_path: Path,
    historical_blob_bytes,
) -> None:
    run = materialize_submission_run(tmp_path, historical_blob_bytes)
    handoff_path = run / "R5_stock_research_report_reader_v3_human_review.yaml"
    before = handoff_path.read_bytes()
    result = load_module().validate_submission(
        run,
        run / "R5_stock_research_report_reader_v3_human_review_submission.yaml",
    )
    assert result["decision"] == "pass", result["errors"]
    assert result["eligible_for_bundle10_final_close"] is True
    assert result["checklist_pass_count"] == 6
    assert result["reviewer"] == "Q"
    assert result["handoff_status"] == "passed_external_human_review"
    assert handoff_path.read_bytes() == before
