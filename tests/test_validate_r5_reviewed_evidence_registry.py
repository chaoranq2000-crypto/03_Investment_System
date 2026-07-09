from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".agents/skills/evidence-ingest/scripts/validate_r5_reviewed_evidence_registry.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_reviewed_evidence_registry", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def base_registry():
    return {
        "artifact_type": "R5_reviewed_evidence_registry",
        "registry_id": "reg_001",
        "workflow_id": "wf_20260703_stock_first_002837_invic",
        "stock_code": "002837",
        "no_live_api": True,
        "records": [
            {
                "source_gap_id": "gap_market",
                "request_id": "req_market",
                "evidence_id": None,
                "source_type": "market_data_snapshot",
                "source_rank": "B",
                "as_of_date": None,
                "review_status": "planned",
                "reviewer": "TODO_REVIEWER",
                "allowed_usage": ["source_gapped_research_draft"],
                "claim_scope": ["TODO_SOURCE_REQUIRED"],
                "metric_scope": ["TODO_MARKET_DATA"],
                "limitations": ["TODO_SOURCE_REQUIRED"],
                "no_live_api": True,
            }
        ],
    }


def test_planned_null_evidence_rows_are_accepted_with_todos():
    validator = load_validator()
    data = base_registry()
    issues = validator.validate_registry(data)

    assert validator.derive_decision(issues, data) == "accepted_with_todos"
    assert not [issue for issue in issues if issue["severity"] == "high"]


def test_reviewed_market_row_requires_evidence_id_and_as_of_date():
    validator = load_validator()
    data = base_registry()
    row = data["records"][0]
    row["review_status"] = "reviewed"
    row["limitations"] = ["reviewed by analyst"]

    issues = validator.validate_registry(data)

    assert {issue["issue_id"] for issue in issues} >= {"R5REV-REVIEW-001", "R5REV-DATE-001"}
    assert validator.derive_decision(issues, data) == "blocked"


def test_allowed_usage_rejects_trading_instructions():
    validator = load_validator()
    data = base_registry()
    data["records"][0]["allowed_usage"] = ["trading instruction: buy rating"]

    issues = validator.validate_registry(data)

    assert any(issue["issue_id"] == "R5REV-NOADV-001" for issue in issues)
