from __future__ import annotations

import argparse
import csv
from pathlib import Path
from statistics import mean
from typing import Sequence

import yaml


def _to_float(value: str) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def build_technical_snapshot(
    *,
    market_csv: Path,
    output_path: Path,
    stock_code: str,
    as_of_date: str,
) -> dict[str, object]:
    rows = list(csv.DictReader(market_csv.open("r", encoding="utf-8", newline=""))) if market_csv.exists() else []
    closes = [_to_float(row.get("close", "")) for row in rows]
    closes = [value for value in closes if value is not None]
    latest = rows[-1] if rows else {}
    close = _to_float(latest.get("close", "")) if latest else None
    ma5 = mean(closes[-5:]) if len(closes) >= 5 else None
    ma20 = mean(closes[-20:]) if len(closes) >= 20 else None
    trend = "MISSING_PRICE_HISTORY"
    if close is not None and ma5 is not None:
        trend = "above_ma5" if close >= ma5 else "below_ma5"
    snapshot = {
        "stock_code": stock_code,
        "as_of_date": latest.get("trade_date") or latest.get("as_of_date") or as_of_date,
        "close": close if close is not None else "MISSING_DISCLOSURE",
        "ma5": round(ma5, 4) if ma5 is not None else "MISSING_DISCLOSURE",
        "ma20": round(ma20, 4) if ma20 is not None else "MISSING_DISCLOSURE",
        "support": min(closes[-20:]) if closes else "MISSING_DISCLOSURE",
        "resistance": max(closes[-20:]) if closes else "MISSING_DISCLOSURE",
        "trend_status": trend,
        "source": str(market_csv),
        "notes": "Technical snapshot is a market-state observation, not trading advice.",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(snapshot, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return snapshot


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a technical snapshot from market history.")
    parser.add_argument("--market-csv", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stock-code", required=True)
    parser.add_argument("--as-of-date", required=True)
    args = parser.parse_args(argv)
    print(
        build_technical_snapshot(
            market_csv=Path(args.market_csv),
            output_path=Path(args.output),
            stock_code=args.stock_code,
            as_of_date=args.as_of_date,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
