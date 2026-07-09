from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".agents/skills/evidence-ingest/scripts/validate_r5_evidence_request_review_ledger.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_evidence_request_review_ledger", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def ledger():
    return {
        "artifact_type": "R5_evidence_request_review_ledger",
        "no_live_api": True,
        "items": [
            {
                "request_id": "req_1",
                "source_gap_id": "gap_1",
                "pack_section": "valuation_pack",
                "review_decision": "pending",
                "evidence_id": None,
                "source_rank": "B",
                "reason": "TODO_MARKET_DATA",
                "next_action": "manual collection",
            }
        ],
    }


def test_pending_ledger_is_accepted_with_todos():
    validator = load_validator()
    data = ledger()
    issues = validator.validate_ledger(data)

    assert validator.derive_decision(data, issues) == "accepted_with_todos"


def test_accepted_null_evidence_is_blocked():
    validator = load_validator()
    data = ledger()
    data["items"][0]["review_decision"] = "accepted"

    issues = validator.validate_ledger(data)

    assert any(issue["issue_id"] == "R5LEDGER-ACCEPT-001" for issue in issues)
    assert validator.derive_decision(data, issues) == "blocked"


def test_accepted_row_requires_source_rank():
    validator = load_validator()
    data = ledger()
    data["items"][0]["review_decision"] = "accepted"
    data["items"][0]["evidence_id"] = "ev_1"
    data["items"][0]["source_rank"] = None

    issues = validator.validate_ledger(data)

    assert any(issue["issue_id"] == "R5LEDGER-ACCEPT-002" for issue in issues)
