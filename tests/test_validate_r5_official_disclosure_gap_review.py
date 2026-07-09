from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".agents/skills/evidence-ingest/scripts/validate_r5_official_disclosure_gap_review.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_official_disclosure_gap_review", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def base_review():
    return {
        "artifact_type": "R5_official_disclosure_gap_review",
        "workflow_id": "wf_20260703_stock_first_002837_invic",
        "stock_code": "002837",
        "no_live_api": True,
        "reviews": [
            {
                "gap_id": "R5_002837_GAP_BUSINESS_001",
                "requested_disclosure": "liquid-cooling revenue and margin",
                "official_source_candidates": ["annual_report"],
                "reviewed_source_ids": [],
                "finding_status": "not_found",
                "extracted_metric_candidates": [],
                "limitations": ["MISSING_DISCLOSURE"],
                "allowed_usage": ["source_gap_visibility"],
            }
        ],
    }


def test_not_found_review_preserves_missing_disclosure():
    validator = load_validator()
    data = base_review()
    issues = validator.validate_gap_review(data)

    assert validator.derive_decision(data, issues) == "accepted_with_todos"


def test_partial_review_requires_promoted_source_metadata():
    validator = load_validator()
    data = base_review()
    row = data["reviews"][0]
    row["finding_status"] = "partial"
    row["reviewed_source_ids"] = [{"evidence_id": "ev_annual"}]

    issues = validator.validate_gap_review(data)

    assert validator.derive_decision(data, issues) == "blocked"
    assert any(issue["issue_id"] == "R5DISC-SRC-003" for issue in issues)
    assert any(issue["issue_id"] == "R5DISC-SRC-004" for issue in issues)


def test_found_review_with_source_metadata_is_accepted():
    validator = load_validator()
    data = base_review()
    row = data["reviews"][0]
    row["finding_status"] = "found"
    row["reviewed_source_ids"] = [{"evidence_id": "ev_annual", "source_rank": "A", "filing_date": "2026-04-21"}]
    row["extracted_metric_candidates"] = [{"metric_name": "segment_revenue", "value": 1, "unit": "CNY"}]
    row["limitations"] = ["exact extracted scope only"]

    issues = validator.validate_gap_review(data)

    assert validator.derive_decision(data, issues) == "accepted"
