from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ingest"))

from market_snapshot_pull import build_market_snapshot  # noqa: E402
from structured_api_pull import metric_candidates_from_rows  # noqa: E402


def test_metric_candidates_from_rows_are_metric_only() -> None:
    rows = [{"ts_code": "002837.SZ", "end_date": "20251231", "total_revenue": "100", "note": "x"}]
    metrics = metric_candidates_from_rows(
        rows=rows,
        source_evidence_id="ev_metric_001",
        source_name="local_fixture",
        stock_code="002837",
        company_id="cn_002837_invic",
        api_name="income",
        api_params_hash="abc123",
        unit="CNY",
    )
    assert len(metrics) == 1
    assert metrics[0]["source_type"] == "structured_financial_data"
    assert "not business exposure evidence" in metrics[0]["notes"]


def test_market_snapshot_pull_writes_structured_api_folder(tmp_path: Path) -> None:
    fixture = tmp_path / "market.csv"
    fixture.write_text("trade_date,close,volume\n20260701,10,100\n", encoding="utf-8")
    result = build_market_snapshot(
        repo_root=tmp_path,
        source_name="local_fixture",
        run_id="run_001",
        input_csv=fixture,
        as_of_date="2026-07-01",
    )
    assert result["rows"] == "1"
    assert (tmp_path / "data/raw/structured_api/local_fixture/run_001/market_snapshot.csv").exists()
    normalized_rows = list(
        csv.DictReader((tmp_path / "data/processed/normalized/run_001/market_snapshot.csv").open("r", encoding="utf-8", newline=""))
    )
    assert normalized_rows[0]["as_of_date"] == "2026-07-01"
