from pathlib import Path

import hashlib
import yaml


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def test_human_review_is_blank_pending_and_hash_bound():
    review = yaml.safe_load((RUN / "R5_stock_research_report_reader_v2_human_review.yaml").read_text(encoding="utf-8"))
    report_hash = hashlib.sha256((RUN / "R5_stock_research_report_reader_v2.md").read_bytes()).hexdigest()
    assert review["report_sha256"] == report_hash
    assert review["status"] == "pending"
    assert review["reviewer"] is None and review["reviewed_at"] is None
    assert review["blocking_comments"] == [] and review["nonblocking_comments"] == []


def test_before_after_only_compares_surface_behavior():
    data = yaml.safe_load((RUN / "R5_bundle6_before_after_comparison.yaml").read_text(encoding="utf-8"))
    assert data["comparison_scope"] == "structure_density_and_presentation_only"
    assert data["bundle6_candidate"]["raw_internal_ids"] == 0
    assert data["bundle6_candidate"]["reader_quality_score"] >= 82
    assert data["human_review_status"] == "pending"
