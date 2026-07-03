from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ingest"))

from official_financial_reconciliation import FIELDNAMES, build_reconciliation_rows  # noqa: E402


DATA_LAYER_RUN = ROOT / "reports/workflow_runs/wf_20260703_data_layer_002837_invic"


def test_official_financial_reconciliation_schema_and_core_coverage() -> None:
    path = DATA_LAYER_RUN / "official_financial_reconciliation.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert list(rows[0].keys()) == FIELDNAMES
    metrics = {row["normalized_metric_name"] for row in rows}
    assert {"total_revenue", "n_income_attr_p", "basic_eps"}.issubset(metrics)
    for metric in ["total_revenue", "n_income_attr_p", "basic_eps"]:
        row = next(item for item in rows if item["normalized_metric_name"] == metric)
        assert row["official_evidence_id"] != "official_missing"
        assert row["official_page_or_table_locator"].startswith("page:")


def test_official_missing_and_mismatch_are_not_silent_matches() -> None:
    rows = build_reconciliation_rows(DATA_LAYER_RUN / "financial_metric_pack.csv")
    status_by_metric = {row["normalized_metric_name"]: row["reconciliation_status"] for row in rows}

    assert status_by_metric["total_revenue"] == "mismatch"
    assert status_by_metric["n_income_attr_p"] == "mismatch"
    assert status_by_metric["basic_eps"] == "mismatch"
    assert status_by_metric["gross_margin"] == "official_missing"
    assert status_by_metric["gross_margin"] != "matched"


def test_reconciliation_result_does_not_create_business_exposure_claim() -> None:
    text = (DATA_LAYER_RUN / "official_financial_reconciliation.csv").read_text(encoding="utf-8")
    assert "liquid_cooling_revenue_pct" not in text
    assert "business exposure fact" not in text

    readout = (DATA_LAYER_RUN / "official_financial_reconciliation_readout.md").read_text(encoding="utf-8")
    assert "mismatch" in readout
    assert "not promoted to reported fact" in readout
