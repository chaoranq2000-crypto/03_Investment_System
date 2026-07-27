from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "qa"))

from r4_disclosure_backflow_review import LIQUID_REVIEW_FIELDS, liquid_cooling_review_rows  # noqa: E402


HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
FIXTURE_RUN = Path("fixture_runs/liquid_review")


def _historical_path(name: str) -> str:
    return f"{HISTORICAL_RUN}/{name}"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _minimal_review_root(tmp_path: Path, historical_blob_file) -> Path:
    source = historical_blob_file(
        _historical_path("business_segment_metric_pack.csv"),
        "liquid_review_source/business_segment_metric_pack.csv",
    )
    root = tmp_path / "liquid_review_repo"
    target = root / FIXTURE_RUN / "business_segment_metric_pack.csv"
    target.parent.mkdir(parents=True)
    target.write_bytes(source.read_bytes())
    return root


def test_liquid_cooling_review_schema_and_rows(historical_blob_file) -> None:
    path = historical_blob_file(
        _historical_path("liquid_cooling_exposure_evidence_review.csv"),
        "liquid_review/liquid_cooling_exposure_evidence_review.csv",
    )
    rows = _read_csv(path)

    assert len(rows) == 6
    assert list(rows[0].keys()) == LIQUID_REVIEW_FIELDS
    assert any(row["review_decision"] == "supports_product_exposure_only" for row in rows)
    assert any(row["review_decision"] == "still_missing_disclosure" for row in rows)


def test_product_and_customer_clues_do_not_generate_revenue_pct(
    tmp_path, historical_blob_file
) -> None:
    rows = liquid_cooling_review_rows(
        _minimal_review_root(tmp_path, historical_blob_file),
        FIXTURE_RUN,
    )
    clue_rows = [row for row in rows if row["review_decision"] == "supports_product_exposure_only"]

    assert clue_rows
    assert all(row["allowed_exposure_type"] == "product" for row in clue_rows)
    assert all(row["revenue_pct_decision"] == "MISSING_DISCLOSURE" for row in clue_rows)
    assert all(row["profit_pct_decision"] == "MISSING_DISCLOSURE" for row in clue_rows)


def test_missing_disclosure_stays_in_source_gap_report(historical_blob_file) -> None:
    path = historical_blob_file(
        _historical_path("R4_source_gap_report_v0_2.md"),
        "liquid_review/R4_source_gap_report_v0_2.md",
    )
    gaps = _read_text(path)

    assert "R4-GAP-001" in gaps
    assert "still_missing_disclosure" in gaps
    assert "MISSING_DISCLOSURE" in gaps


def test_energy_storage_revenue_is_not_mapped_to_liquid_cooling_revenue(
    tmp_path, historical_blob_file
) -> None:
    rows = liquid_cooling_review_rows(
        _minimal_review_root(tmp_path, historical_blob_file),
        FIXTURE_RUN,
    )
    energy = next(row for row in rows if row["metric_name"] == "energy_storage_application_revenue")

    assert energy["review_decision"] == "not_ai_server_liquid_cooling_revenue"
    assert energy["allowed_exposure_type"] == "none"
