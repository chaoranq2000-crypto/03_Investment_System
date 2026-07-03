from __future__ import annotations

import sys
from pathlib import Path

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
    assert tech["windows"]["daily"]["ma10"] == "MISSING_DISCLOSURE"
    assert tech["windows"]["daily"]["volume_ratio"] == "MISSING_DISCLOSURE"
    assert sentiment["industry_sentiment"]["claim_type"] == "clue"
