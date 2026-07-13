from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate_r5_bundle10_close.py"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_r5_bundle10_close", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bundle10_completion_and_external_review_lifecycle_passes() -> None:
    result = load_module().validate_bundle10(ROOT, "wf_20260703_stock_first_002837_invic")
    assert result["decision"] == "pass", result["errors"]
    assert result["checks"]["reader_quality_gate"]["score"] >= 82
    assert result["checks"]["reader_quality_gate"]["critical_blockers"] == 0
    assert result["checks"]["cross_industry_regression"]["case_count"] == 2
    assert result["checks"]["cross_industry_regression"]["fixture_boundary"] == "synthetic_layout_and_schema_regression_only"
    assert result["checks"]["cross_industry_regression"]["narrative_quality"]["status"] == "pass"
    assert result["checks"]["cross_industry_regression"]["narrative_quality"]["total_duplicate_paragraph_count"] == 0
    assert result["checks"]["cross_industry_regression"]["narrative_quality"]["total_judgment_restatement_count"] == 0
    assert result["checks"]["human_review_boundary"]["lifecycle"] == "passed_external_human_review"
    assert result["checks"]["human_review_boundary"]["handoff_status"] == "passed_external_human_review"
    assert result["checks"]["human_review_boundary"]["external_reviewer"] == "Q"
    assert result["checks"]["human_review_boundary"]["sample_quality_allowed"] is True
    assert result["checks"]["human_review_boundary"]["p2_allowed"] is False
    assert result["checks"]["human_review_boundary"]["submission_validation"] == "pass"
    assert result["checks"]["human_review_boundary"]["final_close_validation"] == "pass"
    assert result["checks"]["human_review_boundary"]["submission_validator"] == "validate_r5_bundle10_human_review_submission.py"
    assert result["checks"]["human_review_boundary"]["finalizer"] == "finalize_r5_bundle10_after_human_review.py"
