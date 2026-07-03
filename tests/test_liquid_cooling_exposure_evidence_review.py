from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "qa"))

from r4_disclosure_backflow_review import LIQUID_REVIEW_FIELDS, liquid_cooling_review_rows  # noqa: E402


STOCK_RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def test_liquid_cooling_review_schema_and_rows() -> None:
    with (STOCK_RUN / "liquid_cooling_exposure_evidence_review.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 6
    assert list(rows[0].keys()) == LIQUID_REVIEW_FIELDS
    assert any(row["review_decision"] == "supports_product_exposure_only" for row in rows)
    assert any(row["review_decision"] == "still_missing_disclosure" for row in rows)


def test_product_and_customer_clues_do_not_generate_revenue_pct() -> None:
    rows = liquid_cooling_review_rows(ROOT)
    clue_rows = [row for row in rows if row["review_decision"] == "supports_product_exposure_only"]

    assert clue_rows
    assert all(row["allowed_exposure_type"] == "product" for row in clue_rows)
    assert all(row["revenue_pct_decision"] == "MISSING_DISCLOSURE" for row in clue_rows)
    assert all(row["profit_pct_decision"] == "MISSING_DISCLOSURE" for row in clue_rows)


def test_missing_disclosure_stays_in_source_gap_report() -> None:
    gaps = (STOCK_RUN / "R4_source_gap_report_v0_2.md").read_text(encoding="utf-8")

    assert "R4-GAP-001" in gaps
    assert "still_missing_disclosure" in gaps
    assert "MISSING_DISCLOSURE" in gaps


def test_energy_storage_revenue_is_not_mapped_to_liquid_cooling_revenue() -> None:
    rows = liquid_cooling_review_rows(ROOT)
    energy = next(row for row in rows if row["metric_name"] == "energy_storage_application_revenue")

    assert energy["review_decision"] == "not_ai_server_liquid_cooling_revenue"
    assert energy["allowed_exposure_type"] == "none"
