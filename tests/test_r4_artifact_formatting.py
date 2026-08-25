from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _historical_file(historical_blob_file, name: str) -> Path:
    return historical_blob_file(f"{HISTORICAL_RUN}/{name}", f"r4_formatting/{name}")


def test_r4_v0_1_artifacts_are_physically_multiline(historical_blob_file) -> None:
    assert _line_count(_historical_file(historical_blob_file, "R4_stock_deep_dive_v0_1.md")) >= 80
    assert _line_count(_historical_file(historical_blob_file, "R4_quality_gate_report.md")) >= 20
    assert _line_count(_historical_file(historical_blob_file, "R4_source_gap_report.md")) >= 30


def test_business_segment_pack_is_normal_csv(historical_blob_file) -> None:
    path = _historical_file(historical_blob_file, "business_segment_metric_pack.csv")
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 6
    assert _line_count(path) == 7
    assert any(row["review_status"] == "product_line_clue" for row in rows)


def test_r4_markdown_sections_do_not_collapse_to_one_line(historical_blob_file) -> None:
    text = _historical_file(
        historical_blob_file, "R4_stock_deep_dive_v0_1.md"
    ).read_text(encoding="utf-8")
    for marker in ["## 2.", "## 3.", "## 4.", "## 10."]:
        assert f"\n{marker}" in text
    assert "## 2. 一句话结论\n\n-" in text


def test_new_r4_review_artifacts_use_posix_paths(historical_blob_file) -> None:
    for path in [
        _historical_file(historical_blob_file, "official_reconciliation_review_decision.md"),
        _historical_file(historical_blob_file, "liquid_cooling_exposure_evidence_review.md"),
        _historical_file(historical_blob_file, "exposure_backflow_review.md"),
        _historical_file(historical_blob_file, "R4_stock_deep_dive_v0_2.md"),
        historical_blob_file(
            "reports/p1_6/R4_DISCLOSURE_BACKFLOW_MASTER_READOUT.md",
            "r4_formatting/R4_DISCLOSURE_BACKFLOW_MASTER_READOUT.md",
        ),
    ]:
        text = path.read_text(encoding="utf-8")
        assert "reports\\workflow_runs" not in text
        assert "data\\raw" not in text
