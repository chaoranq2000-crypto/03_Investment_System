from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_forecast_assumptions.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_forecast_assumptions", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def base_registry():
    return {
        "artifact_type": "R5_forecast_assumption_registry",
        "workflow_id": "wf",
        "stock_code": "002837",
        "no_live_api": True,
        "assumptions": [
            {
                "assumption_id": "asm_revenue_growth_base_2026",
                "scope": "company",
                "metric_name": "revenue_growth",
                "periods": ["2026E"],
                "value": 0.05,
                "unit": "pct",
                "scenario": "base",
                "supporting_evidence_ids": ["ev_1"],
                "supporting_metric_ids": ["metric_revenue"],
                "rationale": "reviewed local fixture",
                "limitations": ["company level only"],
                "review_status": "reviewed",
            }
        ],
    }


def test_reviewed_assumption_with_anchors_is_accepted():
    validator = load_validator()
    data = base_registry()
    issues = validator.validate_assumptions(data)

    assert validator.derive_decision(data, issues) == "accepted"


def test_reviewed_assumption_without_anchor_is_blocked():
    validator = load_validator()
    data = base_registry()
    data["assumptions"][0]["supporting_evidence_ids"] = []
    data["assumptions"][0]["supporting_metric_ids"] = []

    issues = validator.validate_assumptions(data)

    assert validator.derive_decision(data, issues) == "blocked"
    assert any(issue["issue_id"] == "R5ASM-ANCHOR-001" for issue in issues)


def test_segment_assumption_requires_business_disclosure():
    validator = load_validator()
    data = base_registry()
    data["assumptions"][0]["scope"] = "segment"

    issues = validator.validate_assumptions(data)

    assert any(issue["issue_id"] == "R5ASM-DISCLOSURE-001" for issue in issues)


def test_bull_case_requires_reviewed_base_case():
    validator = load_validator()
    data = base_registry()
    data["assumptions"][0]["scenario"] = "bull"

    issues = validator.validate_assumptions(data)

    assert any(issue["issue_id"] == "R5ASM-SCENARIO-001" for issue in issues)
