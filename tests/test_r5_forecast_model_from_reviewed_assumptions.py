from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = REPO_ROOT / "src/research/forecast_model_builder.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("forecast_model_builder", BUILDER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def metrics():
    return [
        {
            "metric_name": "revenue",
            "period": "20260331",
            "value": "100",
            "unit": "CNY",
            "metric_id": "metric_revenue",
        }
    ]


def reviewed_registry():
    return {
        "artifact_type": "R5_forecast_assumption_registry",
        "assumptions": [
            {
                "assumption_id": "asm_revenue_growth_base_2026",
                "scope": "company",
                "metric_name": "revenue_growth",
                "periods": ["2026E"],
                "value": 0.05,
                "unit": "pct",
                "scenario": "base",
                "supporting_evidence_ids": ["ev_reviewed"],
                "supporting_metric_ids": ["metric_revenue"],
                "rationale": "reviewed local fixture",
                "limitations": ["company level only"],
                "review_status": "reviewed",
            }
        ],
    }


def test_all_todo_path_without_reviewed_registry():
    builder = load_builder()
    model = builder.build_forecast_model(metrics())

    assert model["model_input_status"]["revenue_forecast"] == "TODO_MODEL_INPUT"
    assert all(row["value"] == "TODO_MODEL_INPUT" for row in model["revenue_forecast"])
    assert model["reviewed_assumptions"]["status"] == "TODO_MODEL_INPUT"


def test_partial_reviewed_assumption_path_uses_only_covered_period():
    builder = load_builder()
    model = builder.build_forecast_model(metrics(), reviewed_assumptions=reviewed_registry())

    assert model["revenue_forecast"][0]["value"] == 105.0
    assert model["revenue_forecast"][1]["value"] == "TODO_MODEL_INPUT"
    assert model["reviewed_assumptions"]["source"] == "reviewed_assumption_registry"


def test_invalid_reviewed_assumption_without_anchor_is_rejected():
    builder = load_builder()
    registry = reviewed_registry()
    registry["assumptions"][0]["supporting_evidence_ids"] = []
    registry["assumptions"][0]["supporting_metric_ids"] = []

    with pytest.raises(ValueError, match="evidence or metric anchors"):
        builder.build_forecast_model(metrics(), reviewed_assumptions=registry)


def test_segment_attribution_without_disclosure_is_rejected():
    builder = load_builder()
    registry = reviewed_registry()
    registry["assumptions"][0]["scope"] = "segment"

    with pytest.raises(ValueError, match="business disclosure"):
        builder.build_forecast_model(metrics(), reviewed_assumptions=registry)
