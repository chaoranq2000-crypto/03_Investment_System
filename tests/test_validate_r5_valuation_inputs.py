from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_valuation_inputs.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_valuation_inputs", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def source_gapped_registry():
    return {
        "artifact_type": "R5_valuation_input_registry",
        "workflow_id": "wf",
        "stock_code": "002837",
        "no_live_api": True,
        "market_snapshot": {"review_status": "TODO_MARKET_DATA", "source_evidence_ids": []},
        "peer_snapshot": {"review_status": "TODO_PEER_DATA", "source_evidence_ids": []},
        "forecast_model": {"review_status": "TODO_MODEL_INPUT", "assumption_ids": []},
        "business_line_split": {"review_status": "MISSING_DISCLOSURE"},
        "valuation_methods": [{"method": "relative_pe", "eligibility": "blocked_for_sample_quality"}],
        "limitations": ["TODO_MARKET_DATA", "TODO_PEER_DATA", "TODO_MODEL_INPUT"],
    }


def test_todo_inputs_stay_source_gapped():
    validator = load_validator()
    data = source_gapped_registry()
    issues = validator.validate_valuation_inputs(data)

    assert validator.derive_decision(data, issues) == "source_gapped_research_draft"


def test_relative_valuation_cannot_be_eligible_without_reviewed_market_and_peers():
    validator = load_validator()
    data = source_gapped_registry()
    data["valuation_methods"][0]["eligibility"] = "eligible"

    issues = validator.validate_valuation_inputs(data)

    assert validator.derive_decision(data, issues) == "blocked"
    assert any(issue["issue_id"] == "R5VALIN-REL-001" for issue in issues)


def test_sotp_requires_business_line_split():
    validator = load_validator()
    data = source_gapped_registry()
    data["market_snapshot"] = {"review_status": "reviewed", "source_evidence_ids": ["ev_market"]}
    data["peer_snapshot"] = {"review_status": "reviewed", "source_evidence_ids": ["ev_peer"]}
    data["forecast_model"] = {"review_status": "reviewed", "assumption_ids": ["asm_cashflow"]}
    data["valuation_methods"] = [{"method": "sotp", "eligibility": "eligible"}]

    issues = validator.validate_valuation_inputs(data)

    assert any(issue["issue_id"] == "R5VALIN-SOTP-001" for issue in issues)


def test_reviewed_market_peer_forecast_can_be_candidate():
    validator = load_validator()
    data = source_gapped_registry()
    data["market_snapshot"] = {"review_status": "reviewed", "source_evidence_ids": ["ev_market"]}
    data["peer_snapshot"] = {"review_status": "reviewed", "source_evidence_ids": ["ev_peer"]}
    data["forecast_model"] = {"review_status": "reviewed", "assumption_ids": ["asm_cashflow"]}
    data["valuation_methods"] = [{"method": "relative_pe", "eligibility": "eligible"}]

    issues = validator.validate_valuation_inputs(data)

    assert validator.derive_decision(data, issues) == "sample_quality_candidate"
