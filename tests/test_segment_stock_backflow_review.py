from __future__ import annotations

import csv
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STOCK_RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_product_line_clue_backflows_only_product_exposure() -> None:
    review = yaml.safe_load((STOCK_RUN / "exposure_backflow_review.yaml").read_text(encoding="utf-8"))
    local = yaml.safe_load((STOCK_RUN / "segment_exposure.yaml").read_text(encoding="utf-8"))
    liquid = next(item for item in local["linked_segments"] if item["segment_id"] == "ai_server_liquid_cooling")

    assert review["decision"] == "update_exposure"
    assert review["status"] == "update_exposure_product_only"
    assert liquid["backflow_decision"] == "update_exposure"
    assert liquid["exposure_type"] == "product"
    assert liquid["revenue_pct"] == "MISSING_DISCLOSURE"
    assert liquid["profit_pct"] == "MISSING_DISCLOSURE"


def test_global_registry_keeps_revenue_and_profit_missing() -> None:
    rows = _read_csv(ROOT / "data/processed/normalized/segment_company_exposure.csv")
    row = next(item for item in rows if item["company_id"] == "cn_002837_invic")

    assert row["exposure_type"] == "product"
    assert row["revenue_pct"].startswith("MISSING")
    assert row["profit_pct"].startswith("MISSING")
    assert "annual_report_002837_invic_2025_0f8fcf" in row["evidence_ids"]
    assert "ev_annual_report_002837_20260421_ce7f64" not in row["evidence_ids"]
    assert row["verification_status"] == "product_only_reviewed_revenue_profit_missing"


def test_company_universe_matches_backflow_registry_update() -> None:
    universe = _read_csv(ROOT / "reports/segments/ai_server_liquid_cooling/company_universe.csv")
    exposure = _read_csv(ROOT / "data/processed/normalized/segment_company_exposure.csv")
    universe_row = next(item for item in universe if item["company_id"] == "cn_002837_invic")
    exposure_row = next(item for item in exposure if item["company_id"] == "cn_002837_invic")

    for field in ["exposure_type", "exposure_score", "revenue_pct", "profit_pct", "evidence_ids"]:
        assert universe_row[field] == exposure_row[field]


def test_backflow_review_has_change_note_and_next_action() -> None:
    text = (STOCK_RUN / "exposure_backflow_review.md").read_text(encoding="utf-8")
    review = yaml.safe_load((STOCK_RUN / "exposure_backflow_review.yaml").read_text(encoding="utf-8"))

    assert "product-only" in text
    assert review["next_action"]
    assert "revenue_pct promotion" in review["blocked_updates"]
