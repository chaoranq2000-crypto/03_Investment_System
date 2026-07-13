from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ingest"))

from market_snapshot_pull import build_market_snapshot  # noqa: E402
from structured_api_pull import infer_metric_unit, metric_candidates_from_rows  # noqa: E402


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


def test_event_date_fields_do_not_become_numeric_metrics() -> None:
    rows = [
        {
            "ts_code": "002837.SZ",
            "ann_date": "20260701",
            "end_date": "20260630",
            "pre_date": "20260825",
            "actual_date": "",
            "modify_date": "",
        }
    ]
    metrics = metric_candidates_from_rows(
        rows=rows,
        source_evidence_id="ev_event_001",
        source_name="tushare",
        stock_code="002837",
        company_id="cn_002837_invic",
        api_name="disclosure_date",
        api_params_hash="event123",
        unit="",
    )
    assert metrics == []


def test_structured_unit_inference_keeps_source_scaling_explicit() -> None:
    assert infer_metric_unit("tushare", "daily", "close") == "CNY_per_share"
    assert infer_metric_unit("tushare", "daily", "vol") == "100_shares"
    assert infer_metric_unit("tushare", "daily_basic", "total_mv") == "10k_CNY"
    assert infer_metric_unit("tushare", "income", "total_revenue") == "CNY"
    assert infer_metric_unit("tushare", "fina_indicator", "grossprofit_margin") == (
        "source_ratio_unscaled"
    )
    assert infer_metric_unit("baostock", "query_history_k_data_plus", "volume") == "shares"
    assert infer_metric_unit("baostock", "query_dupont_data", "dupontROE") == (
        "source_ratio_unscaled"
    )


def test_numeric_code_fields_do_not_create_metric_candidates() -> None:
    metrics = metric_candidates_from_rows(
        rows=[
            {
                "ts_code": "002837.SZ",
                "end_date": "20251231",
                "end_type": "4",
                "update_flag": "1",
                "total_revenue": "100",
            }
        ],
        source_evidence_id="ev_metric_code_001",
        source_name="tushare",
        stock_code="002837",
        company_id="cn_002837_invic",
        api_name="income",
        api_params_hash="code123",
        unit="",
    )
    assert [row["metric_name"] for row in metrics] == ["total_revenue"]
    assert metrics[0]["unit"] == "CNY"


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
