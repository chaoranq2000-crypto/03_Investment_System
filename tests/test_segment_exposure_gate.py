from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_EXPOSURE = (
    "reports/workflow_runs/wf_20260703_stock_first_002837_invic/segment_exposure.yaml"
)


def _load_yaml(input_file: Path) -> dict:
    return yaml.safe_load(input_file.read_text(encoding="utf-8"))


def _exposure(historical_blob_file) -> dict:
    exposure_file = historical_blob_file(
        HISTORICAL_EXPOSURE, "segment_exposure/segment_exposure.yaml"
    )
    return _load_yaml(exposure_file)


def test_segment_exposure_keeps_revenue_and_profit_missing(historical_blob_file) -> None:
    data = _exposure(historical_blob_file)
    liquid = next(item for item in data["linked_segments"] if item["segment_id"] == "ai_server_liquid_cooling")

    assert liquid["exposure_type"] == "product"
    assert liquid["revenue_pct"] == "MISSING_DISCLOSURE"
    assert liquid["profit_pct"] == "MISSING_DISCLOSURE"
    assert liquid["backflow_decision"] == "update_exposure"


def test_product_line_clue_allows_product_only_global_registry_update(historical_blob_file) -> None:
    data = _exposure(historical_blob_file)
    liquid = next(item for item in data["linked_segments"] if item["segment_id"] == "ai_server_liquid_cooling")

    assert liquid["exposure_score"] <= 2
    assert "product-only" in liquid["notes"]
    assert "revenue_pct and profit_pct remain MISSING_DISCLOSURE" in liquid["notes"]
