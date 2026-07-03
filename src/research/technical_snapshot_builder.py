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


def _ma(values: list[float], window: int) -> float | str:
    if len(values) < window:
        return "MISSING_DISCLOSURE"
    return round(mean(values[-window:]), 4)


def _pct_change(values: list[float], window: int) -> float | str:
    if len(values) <= window or values[-window - 1] == 0:
        return "MISSING_DISCLOSURE"
    return round((values[-1] / values[-window - 1] - 1) * 100, 4)


def _volume_ratio(rows: list[dict[str, str]]) -> float | str:
    volumes = [_to_float(row.get("volume", "") or row.get("vol", "")) for row in rows]
    volumes = [value for value in volumes if value is not None]
    if len(volumes) < 5:
        return "MISSING_DISCLOSURE"
    base = mean(volumes[-5:])
    if base == 0:
        return "MISSING_DISCLOSURE"
    return round(volumes[-1] / base, 4)


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
    ma5_value = _ma(closes, 5)
    ma10_value = _ma(closes, 10)
    ma20_value = _ma(closes, 20)
    ma60_value = _ma(closes, 60)
    trend = "MISSING_PRICE_HISTORY"
    if close is not None and isinstance(ma5_value, float):
        trend = "above_ma5" if close >= ma5_value else "below_ma5"
    as_of = latest.get("trade_date") or latest.get("as_of_date") or as_of_date
    snapshot = {
        "stock_code": stock_code,
        "as_of_date": as_of,
        "price_series_source": str(market_csv),
        "adjustment_policy": "unknown",
        "windows": {
            "daily": {
                "ma5": ma5_value,
                "ma10": ma10_value,
                "ma20": ma20_value,
                "ma60": ma60_value,
                "pct_chg_20d": _pct_change(closes, 20),
                "pct_chg_60d": _pct_change(closes, 60),
                "volume_ratio": _volume_ratio(rows),
            },
            "weekly": {"ma5": "MISSING_DISCLOSURE", "ma10": "MISSING_DISCLOSURE", "ma20": "MISSING_DISCLOSURE"},
        },
        "support_resistance": {
            "source_method": "computed" if closes else "unknown",
            "levels": [
                {"type": "support", "value": min(closes[-20:]) if closes else "MISSING_DISCLOSURE"},
                {"type": "resistance", "value": max(closes[-20:]) if closes else "MISSING_DISCLOSURE"},
            ],
        },
        "close": close if close is not None else "MISSING_DISCLOSURE",
        "ma5": ma5_value,
        "ma10": ma10_value,
        "ma20": ma20_value,
        "ma60": ma60_value,
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
