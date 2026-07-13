from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Mapping, Sequence

import yaml


FIELD_ALIASES = {
    "price": ("price", "close", "last_price"),
    "market_cap": ("market_cap", "total_mv", "total_market_cap"),
    "float_market_cap": ("float_market_cap", "circ_mv", "float_mv"),
    "pe_ttm": ("pe_ttm", "pe"),
    "pe_forward": ("pe_forward", "forward_pe"),
    "pb": ("pb", "pb_lf"),
    "ps": ("ps", "ps_ttm"),
    "turnover_rate": ("turnover_rate", "turn"),
    "volume": ("volume", "vol"),
    "amount": ("amount",),
}


def _first_present(row: Mapping[str, str], aliases: Sequence[str]) -> str:
    for key in aliases:
        value = str(row.get(key, "")).strip()
        if value:
            return value
    return "TODO_MARKET_DATA"


def _iso_date(value: str) -> str:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text


def _read_latest_row(path: Path) -> dict[str, str]:
    rows = list(csv.DictReader(path.open("r", encoding="utf-8", newline=""))) if path.exists() else []
    if not rows:
        return {}
    return max(
        rows,
        key=lambda row: str(
            row.get("trade_date") or row.get("date") or row.get("as_of_date") or ""
        ),
    )


def build_valuation_snapshot(
    *,
    input_csv: Path,
    output_path: Path,
    stock_code: str,
    company_id: str = "",
    as_of_date: str = "",
    source_name: str = "local_fixture",
    source_evidence_id: str = "",
    api_params_hash: str = "",
) -> dict[str, object]:
    row = _read_latest_row(input_csv)
    trade_date = _iso_date(
        row.get("trade_date") or row.get("date") or row.get("as_of_date") or as_of_date
    )
    market_values = {
        field: _first_present(row, aliases) for field, aliases in FIELD_ALIASES.items()
    }
    missing_fields = [field for field, value in market_values.items() if value == "TODO_MARKET_DATA"]
    if not trade_date:
        missing_fields.append("trade_date")
        trade_date = "TODO_MARKET_DATA"
    if not source_evidence_id:
        source_evidence_id = row.get("source_evidence_id") or row.get("evidence_id") or "TODO_MARKET_DATA"
    if source_evidence_id == "TODO_MARKET_DATA":
        missing_fields.append("source_evidence_id")

    snapshot = {
        "stock_code": stock_code,
        "company_id": company_id,
        "as_of_date": trade_date,
        "sources": [
            {
                "source_name": source_name,
                "evidence_id": source_evidence_id,
                "api_params_hash": api_params_hash or row.get("api_params_hash", "TODO_MARKET_DATA"),
            }
        ],
        "market_values": market_values,
        "market_value_units": {
            "price": "CNY_per_share" if source_name == "tushare" else "source_unit_unverified",
            "market_cap": "10k_CNY" if source_name == "tushare" else "source_unit_unverified",
            "float_market_cap": "10k_CNY" if source_name == "tushare" else "source_unit_unverified",
            "pe_ttm": "multiple",
            "pe_forward": "multiple",
            "pb": "multiple",
            "ps": "multiple",
            "turnover_rate": "percent",
            "volume": "source_unit_unverified",
            "amount": "source_unit_unverified",
        },
        "missing_fields": sorted(set(missing_fields)),
        "notes": "Valuation snapshot is metric-only market context and not a company fact.",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(snapshot, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return snapshot


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build valuation_snapshot.yaml from a market fixture.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stock-code", required=True)
    parser.add_argument("--company-id", default="")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--source-name", default="local_fixture")
    parser.add_argument("--source-evidence-id", default="")
    parser.add_argument("--api-params-hash", default="")
    args = parser.parse_args(argv)
    print(
        build_valuation_snapshot(
            input_csv=Path(args.input_csv),
            output_path=Path(args.output),
            stock_code=args.stock_code,
            company_id=args.company_id,
            as_of_date=args.as_of_date,
            source_name=args.source_name,
            source_evidence_id=args.source_evidence_id,
            api_params_hash=args.api_params_hash,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
