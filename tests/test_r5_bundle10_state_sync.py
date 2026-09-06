from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path

import yaml
import pytest

# Published historical results; current algorithms are covered in the default suite.
pytestmark = pytest.mark.legacy_compatibility


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def historical_yaml(historical_blob_bytes, name: str):
    return yaml.safe_load(historical_blob_bytes(f"{HISTORICAL_RUN}/{name}").decode("utf-8"))


def historical_csv(historical_blob_bytes, name: str) -> list[dict[str, str]]:
    text = historical_blob_bytes(f"{HISTORICAL_RUN}/{name}").decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def test_bundle10_state_is_finalized_after_external_human_review(
    historical_blob_bytes,
) -> None:
    state = historical_yaml(historical_blob_bytes, "workflow_state.yaml")
    scorecard = historical_yaml(
        historical_blob_bytes, "R5_stock_research_report_reader_v3_quality_scorecard.yaml"
    )
    candidate = state["reader_candidate_snapshot"]
    assert state["status"] in {"accepted_with_todos", "needs_fix", "in_progress"}
    assert state["current_stage"] in {
        "T10_close_readout",
        "R5_bundle9r_closed",
        "T9_quality_review",
        "R5_bundle13r_t1_t2_evidence_backflow",
    }
    if state["current_stage"] == "T9_quality_review":
        assert state["next_stage"] == "T7_stock_report_draft"
        assert state["required_next_skill"] == "stock-deep-dive"
        assert state["bundle10r_v5_human_review"]["decision"] == "revision_required"
    elif state["current_stage"] == "R5_bundle13r_t1_t2_evidence_backflow":
        assert state["next_stage"] == "R5_bundle13r_t1_t2_evidence_backflow"
        assert state["required_next_skill"] == "evidence-ingest"
        assert state["bundle13r_backflow_execution"]["status"] == "backflow_execution_in_progress"
        assert state["bundle13r_backflow_execution"]["sample_quality_allowed"] is False
        assert state["bundle13r_backflow_execution"]["p2_allowed"] is False
    else:
        assert state["next_stage"] is None
    assert state["external_action_required"] is None
    assert state["bundle10_internal_completion"]["internal_execution_complete"] is True
    assert state["bundle10_internal_completion"]["bundle_closed"] is True
    assert state["bundle10_internal_completion"]["external_human_review"] == "passed"
    assert state["bundle10_internal_completion"]["sample_quality_allowed"] is True
    assert state["bundle10_internal_completion"]["p2_allowed"] is False
    assert state["bundle10_internal_completion"]["cross_industry_regression"] == {
        "fixture_boundary": "synthetic_layout_and_schema_regression_only",
        "case_count": 2,
        "distinct_industries": 2,
        "narrative_quality": "pass",
    }
    assert candidate["score"] == scorecard["score"]
    assert candidate["score"] >= scorecard["threshold"]
    assert candidate["decision"] == "R5_sample_quality_ready"
    assert candidate["truthfulness_status"] == "pass"
    assert candidate["human_review_status"] == "passed_external"
    assert candidate["external_reviewer"] == "Q"
    assert candidate["sample_quality_report_allowed"] is True
    assert candidate["p2_allowed"] is False
    if state["current_stage"] == "R5_bundle9r_closed":
        assert state["bundle9r_close"]["bundle_closed"] is True
        assert state["bundle9r_close"]["historical_bundle10_preserved"] is True
        assert state["quality_backflow"]["canonical_sample_quality_allowed"] is False
    assert scorecard["decision"] == "candidate_ready_for_human_review"
    assert scorecard["human_review_status"] == "pending"
    assert scorecard["sample_quality_report_allowed"] is False
    assert scorecard["p2_allowed"] is False
    report_payload = historical_blob_bytes(
        f"{HISTORICAL_RUN}/R5_stock_research_report_reader_v3.md"
    )
    assert b"\r\n" not in report_payload
    report_hash = hashlib.sha256(report_payload.replace(b"\n", b"\r\n")).hexdigest()
    assert candidate["report_sha256"] == report_hash


def test_bundle10_artifacts_and_historical_bundle_closes_are_preserved(
    historical_blob_bytes,
) -> None:
    state = historical_yaml(historical_blob_bytes, "workflow_state.yaml")
    assert state["bundle8_close"]["bundle_closed"] is True
    assert state["bundle9_close"]["bundle_closed"] is True
    artifacts = historical_csv(historical_blob_bytes, "artifact_manifest.csv")
    assert len({row["artifact_id"] for row in artifacts}) == len(artifacts)
    expected = {
        f"{HISTORICAL_RUN}/{name}"
        for name in (
            "R5_bundle10_reader_pack.yaml",
            "R5_stock_research_report_reader_v3.md",
            "R5_stock_research_report_traceability_v3.yaml",
            "R5_stock_research_report_reader_v3_quality_scorecard.yaml",
            "R5_stock_research_report_reader_v3_human_review.yaml",
            "R5_bundle10_cross_industry_writer_regression.yaml",
            "bundle10_internal_completion_readout.md",
            "R5_stock_research_report_reader_v3_human_review_submission.yaml",
            "R5_bundle10_human_review_submission_validation.json",
            "R5_bundle10_final_close_validation.json",
            "bundle10_final_close_readout.md",
        )
    }
    paths = [row["path"] for row in artifacts]
    assert all(paths.count(path) == 1 for path in expected)
    assert all(historical_blob_bytes(path) for path in expected)


def test_bundle7_reader_backflow_and_external_review_todos_are_resolved(
    historical_blob_bytes,
) -> None:
    todos = {
        row["issue_id"]: row
        for row in historical_csv(historical_blob_bytes, "open_todos.csv")
    }
    assert todos["R5Q-B7-A823A644"]["status"] == "resolved_bundle10_reader_density"
    assert todos["R5Q-B7-E0B818E7"]["status"] == "resolved_bundle10_sentiment_layers"
    assert todos["R5Q-B7-9A50BA49"]["status"] == "resolved_bundle10_future_event_chain"
    assert todos["R5B10-G11-001"]["status"] == "resolved_external_human_review"
    assert todos["R5B10-QR-HUMAN-001"]["status"] == "resolved_external_human_review"
    assert todos["R5B10-G11-001"]["resolved_at"] == "2026-07-13T14:07:11+08:00"
    assert todos["R5B10-QR-HUMAN-001"]["resolved_at"] == "2026-07-13T14:07:11+08:00"
