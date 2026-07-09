from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_peer_snapshot.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_peer_snapshot", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def todo_snapshot():
    return {
        "artifact_type": "R5_peer_snapshot",
        "status": "TODO_PEER_DATA",
        "no_live_api": True,
        "peer_set": [],
        "peer_metrics": [],
        "allowed_usage": ["source_gapped_research_draft"],
    }


def reviewed_peer(idx: int):
    return {
        "peer_id": f"peer_{idx}",
        "stock_code": f"00000{idx}",
        "company_name": f"peer {idx}",
        "exchange": "SZSE",
        "selection_reason": "same thermal-management segment",
        "segment_overlap": ["data_center_thermal_management"],
        "source_evidence_ids": [f"ev_peer_{idx}"],
    }


def reviewed_metric(idx: int):
    return {
        "peer_id": f"peer_{idx}",
        "as_of_date": "2026-07-08",
        "market_cap": 100,
        "pe_ttm": 20,
        "pb": 2,
        "ps": 3,
        "source_evidence_ids": [f"ev_metric_{idx}"],
    }


def test_todo_peer_snapshot_stays_source_gapped():
    validator = load_validator()
    data = todo_snapshot()
    issues = validator.validate_peer_snapshot(data)

    assert validator.derive_decision(data, issues) == "source_gapped_research_draft"


def test_less_than_three_reviewed_peers_is_blocked():
    validator = load_validator()
    data = todo_snapshot()
    data["status"] = "reviewed"
    data["peer_set"] = [reviewed_peer(1), reviewed_peer(2)]
    data["peer_metrics"] = [reviewed_metric(1), reviewed_metric(2)]

    issues = validator.validate_peer_snapshot(data)

    assert validator.derive_decision(data, issues) == "blocked"
    assert any(issue["issue_id"] == "R5PEER-SET-001" for issue in issues)


def test_three_reviewed_peers_with_metrics_can_be_candidate():
    validator = load_validator()
    data = todo_snapshot()
    data["status"] = "reviewed"
    data["peer_set"] = [reviewed_peer(1), reviewed_peer(2), reviewed_peer(3)]
    data["peer_metrics"] = [reviewed_metric(1), reviewed_metric(2), reviewed_metric(3)]

    issues = validator.validate_peer_snapshot(data)

    assert validator.derive_decision(data, issues) == "sample_quality_candidate"
