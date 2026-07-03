from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

TODO_MARKET_DATA = "TODO_MARKET_DATA"

FIELDNAMES = [
    "as_of_date",
    "stock_code",
    "company_id",
    "company_name",
    "peer_group",
    "price",
    "market_cap",
    "pe_ttm",
    "pe_forward",
    "pb",
    "ps",
    "revenue_ttm",
    "net_profit_ttm",
    "source_name",
    "source_evidence_id",
    "api_params_hash",
    "missing_fields",
    "notes",
]

MARKET_FIELDS = [
    "price",
    "market_cap",
    "pe_ttm",
    "pe_forward",
    "pb",
    "ps",
    "revenue_ttm",
    "net_profit_ttm",
]


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _first_source(snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
    sources = snapshot.get("sources", [])
    if isinstance(sources, list) and sources and isinstance(sources[0], Mapping):
        return sources[0]
    return {}


def _valuation_by_stock(valuation_snapshot: Mapping[str, Any]) -> dict[str, str]:
    stock_code = str(valuation_snapshot.get("stock_code", "")).strip()
    if not stock_code:
        return {}
    values = valuation_snapshot.get("market_values", {})
    if not isinstance(values, Mapping):
        values = {}
    source = _first_source(valuation_snapshot)
    return {
        "stock_code": stock_code,
        "as_of_date": str(valuation_snapshot.get("as_of_date", TODO_MARKET_DATA)).strip() or TODO_MARKET_DATA,
        "price": str(values.get("price", TODO_MARKET_DATA)).strip() or TODO_MARKET_DATA,
        "market_cap": str(values.get("market_cap", TODO_MARKET_DATA)).strip() or TODO_MARKET_DATA,
        "pe_ttm": str(values.get("pe_ttm", TODO_MARKET_DATA)).strip() or TODO_MARKET_DATA,
        "pe_forward": str(values.get("pe_forward", TODO_MARKET_DATA)).strip() or TODO_MARKET_DATA,
        "pb": str(values.get("pb", TODO_MARKET_DATA)).strip() or TODO_MARKET_DATA,
        "ps": str(values.get("ps", TODO_MARKET_DATA)).strip() or TODO_MARKET_DATA,
        "revenue_ttm": TODO_MARKET_DATA,
        "net_profit_ttm": TODO_MARKET_DATA,
        "source_name": str(source.get("source_name", TODO_MARKET_DATA)).strip() or TODO_MARKET_DATA,
        "source_evidence_id": str(source.get("evidence_id", TODO_MARKET_DATA)).strip() or TODO_MARKET_DATA,
        "api_params_hash": str(source.get("api_params_hash", TODO_MARKET_DATA)).strip() or TODO_MARKET_DATA,
    }


def _missing_fields(row: Mapping[str, str]) -> str:
    missing = [field for field in MARKET_FIELDS + ["source_evidence_id", "api_params_hash"] if row.get(field) == TODO_MARKET_DATA]
    return ";".join(missing) if missing else ""


def build_peer_market_snapshot(
    *,
    peer_source_csv: Path,
    valuation_snapshot_path: Path,
    output_path: Path,
    as_of_date: str,
    peer_group: str,
) -> list[dict[str, str]]:
    peers = read_csv_dicts(peer_source_csv)
    valuation_snapshot = load_yaml(valuation_snapshot_path)
    valuation = _valuation_by_stock(valuation_snapshot if isinstance(valuation_snapshot, Mapping) else {})
    valuation_stock = valuation.get("stock_code", "")
    rows: list[dict[str, str]] = []

    for peer in peers:
        stock_code = peer.get("stock_code", "")
        market_values = valuation if stock_code == valuation_stock else {}
        row = {
            "as_of_date": market_values.get("as_of_date") or as_of_date or TODO_MARKET_DATA,
            "stock_code": stock_code,
            "company_id": peer.get("company_id", ""),
            "company_name": peer.get("stock_name") or peer.get("company_name", ""),
            "peer_group": peer.get("segment_id") or peer_group,
            "price": market_values.get("price", TODO_MARKET_DATA),
            "market_cap": market_values.get("market_cap", TODO_MARKET_DATA),
            "pe_ttm": market_values.get("pe_ttm", TODO_MARKET_DATA),
            "pe_forward": market_values.get("pe_forward", TODO_MARKET_DATA),
            "pb": market_values.get("pb", TODO_MARKET_DATA),
            "ps": market_values.get("ps", TODO_MARKET_DATA),
            "revenue_ttm": market_values.get("revenue_ttm", TODO_MARKET_DATA),
            "net_profit_ttm": market_values.get("net_profit_ttm", TODO_MARKET_DATA),
            "source_name": market_values.get("source_name", "local_fixture"),
            "source_evidence_id": market_values.get("source_evidence_id", TODO_MARKET_DATA),
            "api_params_hash": market_values.get("api_params_hash", TODO_MARKET_DATA),
            "missing_fields": "",
            "notes": "Fixture-only peer valuation context; no trading conclusion.",
        }
        row["missing_fields"] = _missing_fields(row)
        rows.append(row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a fixture-only peer_market_snapshot.csv.")
    parser.add_argument("--peer-source-csv", required=True)
    parser.add_argument("--valuation-snapshot", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--peer-group", required=True)
    args = parser.parse_args(argv)
    rows = build_peer_market_snapshot(
        peer_source_csv=Path(args.peer_source_csv),
        valuation_snapshot_path=Path(args.valuation_snapshot),
        output_path=Path(args.output),
        as_of_date=args.as_of_date,
        peer_group=args.peer_group,
    )
    print({"rows": len(rows), "output": args.output})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
