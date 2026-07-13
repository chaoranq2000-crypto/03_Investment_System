from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "research"))

from market_sentiment_pack_builder import build_market_sentiment_pack  # noqa: E402
from technical_snapshot_builder import build_technical_snapshot  # noqa: E402


def test_technical_and_sentiment_builders_write_yaml(tmp_path: Path) -> None:
    market = tmp_path / "market.csv"
    market.write_text(
        "trade_date,close\n20260701,10\n20260702,11\n20260703,12\n20260704,13\n20260705,14\n",
        encoding="utf-8",
    )
    tech = build_technical_snapshot(
        market_csv=market,
        output_path=tmp_path / "technical_snapshot.yaml",
        stock_code="002837",
        as_of_date="2026-07-05",
    )
    sentiment = build_market_sentiment_pack(
        output_path=tmp_path / "market_sentiment_pack.yaml",
        as_of_date="2026-07-05",
        stock_code="002837",
    )
    assert tech["as_of_date"] == "20260705"
    assert tech["trend_status"] == "above_ma5"
    assert tech["windows"]["daily"]["ma5"] == 12
    assert tech["windows"]["daily"]["ma10"] == "INSUFFICIENT_PRICE_WINDOW"
    assert tech["windows"]["daily"]["volume_ratio"] == "TODO_MARKET_DATA"
    assert tech["windows"]["daily"]["pct_chg_20d"] == "INSUFFICIENT_PRICE_WINDOW"
    assert tech["windows"]["weekly"]["ma20"] == "INSUFFICIENT_PRICE_WINDOW"
    text = (tmp_path / "technical_snapshot.yaml").read_text(encoding="utf-8")
    parsed = yaml.safe_load(text)
    assert parsed["notes"] == "Technical snapshot is a market-state observation, not trading advice."
    assert "MISSING_DISCLOSURE" not in text
    assert "\\" not in parsed["price_series_source"]
    assert "\\" not in parsed["source"]
    assert sentiment["industry_sentiment"]["claim_type"] == "clue"


def test_technical_builder_sorts_descending_dates_and_accepts_baostock_date_alias(
    tmp_path: Path,
) -> None:
    market = tmp_path / "market_desc.csv"
    market.write_text(
        "date,close,volume,adjustflag\n"
        "2026-07-05,15,150,3\n"
        "2026-07-04,14,140,3\n"
        "2026-07-03,13,130,3\n"
        "2026-07-02,12,120,3\n"
        "2026-07-01,11,110,3\n",
        encoding="utf-8",
    )

    snapshot = build_technical_snapshot(
        market_csv=market,
        output_path=tmp_path / "technical_desc.yaml",
        stock_code="002837",
        as_of_date="2026-07-06",
    )

    assert snapshot["as_of_date"] == "2026-07-05"
    assert snapshot["close"] == 15
    assert snapshot["ma5"] == 13
    assert snapshot["adjustment_policy"] == "none"
