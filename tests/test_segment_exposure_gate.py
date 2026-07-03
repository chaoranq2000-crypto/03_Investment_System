from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STOCK_RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def test_segment_exposure_keeps_revenue_and_profit_missing() -> None:
    data = yaml.safe_load((STOCK_RUN / "segment_exposure.yaml").read_text(encoding="utf-8"))
    liquid = next(item for item in data["linked_segments"] if item["segment_id"] == "ai_server_liquid_cooling")

    assert liquid["exposure_type"] == "product"
    assert liquid["revenue_pct"] == "MISSING_DISCLOSURE"
    assert liquid["profit_pct"] == "MISSING_DISCLOSURE"
    assert liquid["backflow_decision"] == "blocked"


def test_product_line_clue_does_not_imply_global_registry_update() -> None:
    data = yaml.safe_load((STOCK_RUN / "segment_exposure.yaml").read_text(encoding="utf-8"))
    liquid = next(item for item in data["linked_segments"] if item["segment_id"] == "ai_server_liquid_cooling")

    assert liquid["exposure_score"] <= 2
    assert "global exposure registry update is allowed yet" in liquid["notes"]
