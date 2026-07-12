from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_forecast_assumption_registry.py"
RUN_REGISTRY = REPO_ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_forecast_assumption_registry.yaml"
FORECAST_MODEL = REPO_ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_forecast_model_candidate.yaml"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_forecast_assumption_registry", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def registry():
    assumptions = []
    for driver in ["revenue_growth", "gross_margin", "opex", "net_profit", "eps"]:
        assumptions.append(
            {
                "assumption_id": f"TODO_{driver}",
                "driver": driver,
                "periods": ["2026E", "2027E", "2028E"],
                "value": "TODO_MODEL_INPUT",
                "unit": "pct",
                "evidence_ids": [],
                "metric_ids": [],
                "missing_reason": "TODO_MODEL_INPUT",
                "allowed_usage": "degraded_forecast_only",
                "review_status": "pending",
            }
        )
    return {
        "artifact_type": "R5_forecast_assumption_registry",
        "review_status": "pending",
        "no_live_api": True,
        "assumptions": assumptions,
    }


def test_pending_registry_passes_but_keeps_todos():
    validator = load_validator()
    data = registry()
    issues = validator.validate_registry(data)

    assert validator.derive_decision(data, issues) == "accepted_with_todos"


def test_run_registry_and_rebuilt_pack_use_reviewed_numeric_forecast():
    validator = load_validator()
    data = validator.load_yaml(RUN_REGISTRY)
    forecast = yaml.safe_load(FORECAST_MODEL.read_text(encoding="utf-8"))

    assert validator.derive_decision(data, validator.validate_registry(data)) == "accepted"
    assert data["review_status"] == "reviewed"
    assert {row["driver"] for row in data["assumptions"]} == {
        "revenue_growth",
        "gross_margin",
        "opex",
        "net_profit",
        "eps",
    }
    assert forecast["status"] == "ready"
    assert forecast["scenarios"]["base_case"]["forecast_table"]["2026E"]["revenue"]["value"] > 0
    assert "TODO_MODEL_INPUT" not in RUN_REGISTRY.read_text(encoding="utf-8")


def test_reviewed_assumption_requires_anchor_and_reviewer_note():
    validator = load_validator()
    data = registry()
    data["review_status"] = "reviewed"
    data["assumptions"][0]["review_status"] = "reviewed"
    data["assumptions"][0]["value"] = 0.05
    data["assumptions"][0]["allowed_usage"] = "forecast_input_after_review"

    issues = validator.validate_registry(data)

    assert {issue["issue_id"] for issue in issues} >= {"R5FAR-ANCHOR-001", "R5FAR-REVIEW-001"}
    assert validator.derive_decision(data, issues) == "blocked"


def test_core_driver_gap_is_blocked():
    validator = load_validator()
    data = registry()
    data["assumptions"] = data["assumptions"][:-1]

    issues = validator.validate_registry(data)

    assert any(issue["issue_id"] == "R5FAR-CORE-001" for issue in issues)
