from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate_r5_bundle10_close.py"
HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
RUN_ARTIFACTS = (
    "R5_bundle10_technical_market_pack.yaml",
    "R5_bundle10_sentiment_event_pack.yaml",
    "R5_bundle10_reader_gate_forecast.yaml",
    "R5_bundle10_reader_gate_valuation.yaml",
    "R5_bundle10_reader_pack.yaml",
    "R5_bundle10_reader_pack_build_readout.yaml",
    "R5_stock_research_report_reader_v3.md",
    "R5_stock_research_report_traceability_v3.yaml",
    "R5_stock_research_report_reader_v3_quality_scorecard.yaml",
    "R5_bundle10_cross_industry_writer_regression.yaml",
    "bundle10_cross_industry_regression/industrial_equipment_reader.md",
    "bundle10_cross_industry_regression/healthcare_services_reader.md",
    "R5_stock_research_report_reader_v3_human_review.yaml",
    "R5_stock_research_report_reader_v3_human_review_form.md",
    "R5_stock_research_report_reader_v3_human_review_submission_template.yaml",
    "R5_bundle10_ai_assisted_semantic_precheck.yaml",
    "R5_stock_research_report_reader_v3_human_review_submission.yaml",
    "R5_bundle10_human_review_submission_validation.json",
    "R5_bundle10_final_close_validation.json",
    "bundle10_final_close_readout.md",
    "workflow_state.yaml",
)


def load_module():
    spec = importlib.util.spec_from_file_location("validate_r5_bundle10_close", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bundle10_completion_and_external_review_lifecycle_passes(
    tmp_path: Path,
    historical_blob_bytes,
) -> None:
    run = tmp_path / "bundle10_close_inputs"
    for name in RUN_ARTIFACTS:
        target = run / name
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = historical_blob_bytes(f"{HISTORICAL_RUN}/{name}")
        if name in {
            "R5_stock_research_report_reader_v3.md",
            "R5_stock_research_report_traceability_v3.yaml",
        }:
            payload = payload.replace(b"\n", b"\r\n")
        target.write_bytes(payload)

    manifest = load_module().load_yaml(
        ROOT / "reports/p1_6/r5_v1_governance_cleanup/historical_baseline_manifest.yaml"
    )
    historical_paths = {row["path"] for row in manifest["files"]}

    def source_path_exists(source_path: str) -> bool:
        if (ROOT / source_path).exists():
            return True
        if source_path not in historical_paths:
            return False
        historical_blob_bytes(source_path)
        return True

    result = load_module().validate_bundle10(
        ROOT,
        "fixture_stock_first_002837",
        run_dir=run,
        source_path_exists=source_path_exists,
    )
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
