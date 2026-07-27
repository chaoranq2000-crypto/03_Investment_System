from pathlib import Path

import hashlib
import yaml


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def historical_yaml(historical_blob_bytes, name: str):
    return yaml.safe_load(historical_blob_bytes(f"{HISTORICAL_RUN}/{name}").decode("utf-8"))


def test_human_review_is_blank_pending_and_hash_bound(historical_blob_bytes):
    review = historical_yaml(
        historical_blob_bytes, "R5_stock_research_report_reader_v2_human_review.yaml"
    )
    report_hash = hashlib.sha256(
        historical_blob_bytes(f"{HISTORICAL_RUN}/R5_stock_research_report_reader_v2.md")
    ).hexdigest()
    assert review["report_sha256"] == report_hash
    assert review["status"] == "pending"
    assert review["reviewer"] is None and review["reviewed_at"] is None
    assert review["blocking_comments"] == [] and review["nonblocking_comments"] == []


def test_before_after_only_compares_surface_behavior(historical_blob_bytes):
    data = historical_yaml(
        historical_blob_bytes, "R5_bundle6_before_after_comparison.yaml"
    )
    assert data["comparison_scope"] == "structure_density_and_presentation_only"
    assert data["bundle6_candidate"]["raw_internal_ids"] == 0
    assert data["bundle6_candidate"]["reader_quality_score"] >= 82
    assert data["human_review_status"] == "pending"
