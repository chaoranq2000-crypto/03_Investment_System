from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = REPO_ROOT / "src/research/forecast_model_builder.py"
FORECAST_PATH = REPO_ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic/forecast_model.yaml"


def load_builder():
    spec = importlib.util.spec_from_file_location("forecast_model_builder", BUILDER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_builder_keeps_forecast_values_todo_without_reviewed_assumptions():
    builder = load_builder()
    model = builder.build_forecast_model(
        [
            {
                "metric_name": "revenue",
                "period": "20260331",
                "value": "1175329313.61",
                "unit": "CNY",
                "metric_id": "metric_revenue",
            }
        ]
    )

    assert model["model_input_status"]["revenue_forecast"] == "TODO_MODEL_INPUT"
    assert all(row["value"] == "TODO_MODEL_INPUT" for row in model["revenue_forecast"])
    assert model["historical_metric_anchors"][0]["use_in_model"] == "historical_anchor_only"


def test_builder_uses_reviewed_growth_only_when_explicitly_supplied():
    builder = load_builder()
    model = builder.build_forecast_model(
        [
            {
                "metric_name": "revenue",
                "period": "20260331",
                "value": "100",
                "unit": "CNY",
                "metric_id": "metric_revenue",
            }
        ],
        reviewed_assumptions={"revenue_growth": {"2026E": 0.05}},
    )

    assert model["revenue_forecast"][0]["value"] == 105.0
    assert model["revenue_forecast"][1]["value"] == "TODO_MODEL_INPUT"


def test_workflow_forecast_model_has_no_default_growth_forecast_values():
    data = yaml.safe_load(FORECAST_PATH.read_text(encoding="utf-8"))

    assert data["model_input_status"]["revenue_forecast"] in (
        "TODO_MODEL_INPUT",
        "blocked_without_reviewed_assumptions",
    )
    assert all(row["value"] == "TODO_MODEL_INPUT" for row in data["revenue_forecast"])
    assert data["historical_metric_anchors"]
