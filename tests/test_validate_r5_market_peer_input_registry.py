from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_market_peer_input_registry.py"
RUN_REGISTRY = REPO_ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_market_peer_input_registry.yaml"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_market_peer_input_registry", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pending_registry():
    return {
        "artifact_type": "R5_market_peer_input_registry",
        "review_status": "pending",
        "as_of_date": None,
        "no_live_api": True,
        "market_inputs": {
            "current_price": {
                "value": "TODO_MARKET_DATA",
                "source_type": "market_snapshot",
                "evidence_id": None,
                "missing_reason": "TODO_MARKET_DATA",
            }
        },
        "peer_inputs": {
            "peer_set": {
                "value": "TODO_PEER_DATA",
                "source_type": "peer_snapshot",
                "evidence_id": None,
                "missing_reason": "TODO_PEER_DATA",
            }
        },
    }


def test_pending_registry_passes_with_visible_todos():
    validator = load_validator()
    data = pending_registry()
    issues = validator.validate_registry(data)

    assert validator.derive_decision(data, issues) == "accepted_with_todos"


def test_run_registry_is_source_gapped_not_sample_quality():
    validator = load_validator()
    data = validator.load_yaml(RUN_REGISTRY)
    issues = validator.validate_registry(data)

    assert validator.derive_decision(data, issues) == "accepted_with_todos"
    assert data["sample_quality_report_allowed"] is False
    assert data["p2_allowed"] is False


def test_reviewed_registry_requires_evidence_ids_and_as_of_date():
    validator = load_validator()
    data = pending_registry()
    data["review_status"] = "reviewed"
    data["reviewer"] = "analyst"

    issues = validator.validate_registry(data)

    assert {issue["issue_id"] for issue in issues} >= {"R5MP-DATE-001", "R5MP-EVID-001"}
    assert validator.derive_decision(data, issues) == "blocked"


def test_non_todo_market_value_requires_evidence():
    validator = load_validator()
    data = pending_registry()
    data["market_inputs"]["current_price"]["value"] = 10.0

    issues = validator.validate_registry(data)

    assert any(issue["issue_id"] == "R5MP-NUM-001" for issue in issues)
