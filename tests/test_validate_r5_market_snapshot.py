from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_market_snapshot.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_market_snapshot", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def todo_snapshot():
    return {
        "artifact_type": "R5_market_snapshot",
        "status": "TODO_MARKET_DATA",
        "no_live_api": True,
        "as_of_date": None,
        "currency": "CNY",
        "current_price": None,
        "market_cap": None,
        "share_count": None,
        "pe_ttm": None,
        "pb": None,
        "ps": None,
        "source_evidence_ids": [],
        "allowed_usage": ["source_gapped_research_draft"],
    }


def test_todo_market_snapshot_stays_source_gapped():
    validator = load_validator()
    data = todo_snapshot()
    issues = validator.validate_market_snapshot(data)

    assert validator.derive_decision(data, issues) == "source_gapped_research_draft"


def test_numeric_market_fields_without_source_ids_are_blocked():
    validator = load_validator()
    data = todo_snapshot()
    data["current_price"] = 10.0

    issues = validator.validate_market_snapshot(data)

    assert validator.derive_decision(data, issues) == "blocked"
    assert any(issue["issue_id"] == "R5MKT-SRC-001" for issue in issues)


def test_reviewed_snapshot_with_required_fields_can_be_candidate():
    validator = load_validator()
    data = todo_snapshot()
    data.update(
        {
            "status": "reviewed",
            "as_of_date": "2026-07-08",
            "current_price": 10.0,
            "market_cap": 100.0,
            "share_count": 10.0,
            "pe_ttm": 20.0,
            "pb": 2.0,
            "ps": 3.0,
            "source_evidence_ids": ["ev_reviewed_market"],
        }
    )

    issues = validator.validate_market_snapshot(data)

    assert validator.derive_decision(data, issues) == "sample_quality_candidate"
