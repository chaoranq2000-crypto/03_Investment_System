from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ingest"))

from business_segment_extraction import FIELDNAMES, build_business_segment_rows  # noqa: E402


STOCK_RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def test_business_segment_metric_pack_schema_is_stable() -> None:
    with (STOCK_RUN / "business_segment_metric_pack.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert list(rows[0].keys()) == FIELDNAMES
    assert any(row["review_status"] == "missing_disclosure" for row in rows)


def test_narrative_and_product_clues_do_not_generate_revenue_or_profit_pct() -> None:
    rows = build_business_segment_rows()
    narrative_rows = [row for row in rows if row["review_status"] == "narrative_only"]
    product_rows = [row for row in rows if row["review_status"] == "product_line_clue"]

    assert narrative_rows
    assert product_rows
    assert all(row["revenue_pct"] == "MISSING_DISCLOSURE" for row in narrative_rows)
    assert all(row["profit_pct"] == "MISSING_DISCLOSURE" for row in product_rows)


def test_reviewed_official_rows_have_official_evidence_id() -> None:
    rows = build_business_segment_rows()
    reviewed = [row for row in rows if row["review_status"] == "reviewed_official"]
    assert reviewed
    assert all(row["official_evidence_id"].startswith("ev_annual_report_") for row in reviewed)


def test_missing_disclosure_continues_into_source_gap_report() -> None:
    gaps = (STOCK_RUN / "remaining_source_gaps_after_data_layer_bridge.md").read_text(encoding="utf-8")
    assert "DISCLOSURE-SEGMENT-002" in gaps
    assert "MISSING_DISCLOSURE" in gaps
