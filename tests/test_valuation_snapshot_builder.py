from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ingest"))

from build_valuation_snapshot import build_valuation_snapshot  # noqa: E402


def test_valuation_snapshot_builder_maps_required_fields(tmp_path: Path) -> None:
    fixture = tmp_path / "daily_basic.csv"
    fixture.write_text(
        "trade_date,close,total_mv,circ_mv,pe_ttm,pb,ps_ttm,turnover_rate,volume,amount,source_evidence_id\n"
        "20260701,10.5,100000,80000,25,3,4,1.2,1000,10500,ev_market_001\n",
        encoding="utf-8",
    )
    snapshot = build_valuation_snapshot(
        input_csv=fixture,
        output_path=tmp_path / "valuation_snapshot.yaml",
        stock_code="002837",
        company_id="cn_002837_invic",
        source_name="tushare",
        api_params_hash="abc123",
    )
    assert snapshot["as_of_date"] == "2026-07-01"
    assert snapshot["market_values"]["price"] == "10.5"
    assert snapshot["market_values"]["market_cap"] == "100000"
    assert snapshot["market_value_units"]["market_cap"] == "10k_CNY"
    assert snapshot["market_values"]["ps"] == "4"
    assert snapshot["sources"][0]["evidence_id"] == "ev_market_001"
    assert snapshot["missing_fields"] == ["pe_forward"]


def test_valuation_snapshot_marks_missing_fields_without_invention(tmp_path: Path) -> None:
    fixture = tmp_path / "daily_basic.csv"
    fixture.write_text("trade_date,close\n20260701,10.5\n", encoding="utf-8")
    snapshot = build_valuation_snapshot(
        input_csv=fixture,
        output_path=tmp_path / "valuation_snapshot.yaml",
        stock_code="002837",
    )
    assert snapshot["market_values"]["market_cap"] == "TODO_MARKET_DATA"
    assert "source_evidence_id" in snapshot["missing_fields"]


def test_valuation_snapshot_selects_latest_date_from_descending_rows(tmp_path: Path) -> None:
    fixture = tmp_path / "daily_basic_desc.csv"
    fixture.write_text(
        "trade_date,close,total_mv,source_evidence_id\n"
        "20260710,73.54,1000,ev_latest\n"
        "20260709,72.00,900,ev_older\n",
        encoding="utf-8",
    )

    snapshot = build_valuation_snapshot(
        input_csv=fixture,
        output_path=tmp_path / "valuation_latest.yaml",
        stock_code="002837",
        source_name="tushare",
    )

    assert snapshot["as_of_date"] == "2026-07-10"
    assert snapshot["market_values"]["price"] == "73.54"
    assert snapshot["sources"][0]["evidence_id"] == "ev_latest"
