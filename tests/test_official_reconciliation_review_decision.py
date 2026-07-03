from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "qa"))

from r4_disclosure_backflow_review import OFFICIAL_DECISION_FIELDS, official_reconciliation_decision_rows  # noqa: E402


STOCK_RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def test_every_official_reconciliation_row_has_review_decision() -> None:
    with (STOCK_RUN / "official_reconciliation_review_decision.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert list(rows[0].keys()) == OFFICIAL_DECISION_FIELDS
    assert all(row["review_decision"] for row in rows)
    assert all(row["owner_skill"] == "quality-review" for row in rows)


def test_mismatch_and_missing_rows_are_not_promoted() -> None:
    rows = official_reconciliation_decision_rows(ROOT)
    status_by_metric = {row["metric_name"]: row for row in rows}

    assert status_by_metric["total_revenue"]["current_status"] == "mismatch"
    assert status_by_metric["total_revenue"]["promotion_allowed"] == "false"
    assert status_by_metric["gross_margin"]["current_status"] == "official_missing"
    assert status_by_metric["gross_margin"]["review_decision"] == "explicit_official_missing"
    assert status_by_metric["gross_margin"]["promotion_allowed"] == "false"


def test_promotion_allowed_true_requires_official_locator() -> None:
    rows = official_reconciliation_decision_rows(ROOT)
    for row in rows:
        if row["promotion_allowed"] == "true":
            assert row["official_evidence_id"].startswith("ev_")
            assert row["official_locator"].startswith("page:")


def test_review_decision_does_not_create_business_exposure_claim() -> None:
    text = (STOCK_RUN / "official_reconciliation_review_decision.md").read_text(encoding="utf-8")
    csv_text = (STOCK_RUN / "official_reconciliation_review_decision.csv").read_text(encoding="utf-8")

    assert "liquid_cooling_revenue_pct" not in csv_text
    assert "does not create liquid-cooling exposure evidence" in text
