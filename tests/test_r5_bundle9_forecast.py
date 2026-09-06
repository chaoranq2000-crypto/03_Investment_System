from __future__ import annotations

import csv
import io
from pathlib import Path

import yaml
import pytest

# Published historical results; current algorithms are covered in the default suite.
pytestmark = pytest.mark.legacy_compatibility


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def historical_yaml(historical_blob_bytes, name: str):
    return yaml.safe_load(historical_blob_bytes(f"{HISTORICAL_RUN}/{name}").decode("utf-8"))


def historical_csv(historical_blob_bytes, name: str) -> list[dict[str, str]]:
    text = historical_blob_bytes(f"{HISTORICAL_RUN}/{name}").decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def test_bundle9_forecast_is_bottom_up_and_reconciled(historical_blob_bytes) -> None:
    model = historical_yaml(historical_blob_bytes, "segment_forecast_model.yaml")
    bridge = historical_yaml(historical_blob_bytes, "forecast_bridge.yaml")
    assert model["status"] == "ready"
    assert model["model_type"].startswith("bottom_up_")
    assert set(model["business_line_anchors"]) == {
        "room_cooling",
        "cabinet_cooling",
        "other_businesses",
    }
    assert bridge["reconciliation"]["max_abs_profit_bridge_difference"] <= 0.01
    assert bridge["reconciliation"]["expense_tax_minority_separated"] is True
    assert bridge["reconciliation"]["cashflow_and_capex_bridge_present"] is True
    for scenario in ("base_case", "bull_case", "bear_case"):
        for year in ("2026E", "2027E", "2028E"):
            row = bridge["scenarios"][scenario][year]
            assert round(sum(line["revenue"] for line in row["business_lines"].values()), 2) == row["bridge"]["revenue"]
            assert row["bridge"]["operating_cashflow"] is not None
            assert row["bridge"]["free_cashflow"] is not None


def test_bundle9_forecast_keeps_liquid_cooling_boundary_and_assumptions(
    historical_blob_bytes,
) -> None:
    model = historical_yaml(historical_blob_bytes, "segment_forecast_model.yaml")
    registry = historical_yaml(
        historical_blob_bytes, "R5_bundle9_forecast_assumption_registry.yaml"
    )
    assert model["liquid_cooling_boundary"]["claim_type"] == "management_comment"
    assert model["liquid_cooling_boundary"]["2025_revenue"] == "MISSING_DISCLOSURE"
    assert model["liquid_cooling_boundary"]["gross_margin"] == "MISSING_DISCLOSURE"
    assert registry["review_status"] == "reviewed"
    assert all(row["review_status"] == "reviewed" for row in registry["assumptions"])
    assert {row["driver"] for row in registry["assumptions"]}.issuperset(
        {"revenue_growth", "gross_margin", "opex", "net_profit", "eps"}
    )


def test_bundle9_forecast_sensitivity_is_parseable_and_no_advice(
    historical_blob_bytes,
) -> None:
    rows = historical_csv(historical_blob_bytes, "forecast_sensitivity.csv")
    assert len(rows) == 12
    assert {row["driver"] for row in rows} == {
        "room_cooling_revenue_growth",
        "consolidated_gross_margin",
        "opex_ratio",
        "nwc_to_revenue",
    }
    text = "\n".join(
        historical_blob_bytes(f"{HISTORICAL_RUN}/{name}").decode("utf-8")
        for name in (
            "segment_forecast_model.yaml",
            "forecast_bridge.yaml",
            "R5_bundle9_forecast_assumption_registry.yaml",
        )
    )
    assert not any(token in text for token in ("买入", "卖出", "目标价", "仓位", "保证收益"))
