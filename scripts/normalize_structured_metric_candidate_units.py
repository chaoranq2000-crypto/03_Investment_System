from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ingest"))

from structured_api_pull import NON_METRIC_FIELDS, infer_metric_unit  # noqa: E402


STRUCTURED_APIS = {
    "daily",
    "daily_basic",
    "pro_bar",
    "income",
    "balancesheet",
    "cashflow",
    "fina_indicator",
    "fina_mainbz",
    "query_history_k_data_plus",
    "query_profit_data",
    "query_balance_data",
    "query_cash_flow_data",
    "query_dupont_data",
}


def normalize(path: Path) -> dict[str, int]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    retained: list[dict[str, str]] = []
    changed = 0
    removed_nonmetrics = 0
    for row in rows:
        api_name = row.get("metric_category", "")
        metric_name = row.get("metric_name", "")
        if api_name in STRUCTURED_APIS and metric_name in NON_METRIC_FIELDS:
            removed_nonmetrics += 1
            continue
        if api_name in STRUCTURED_APIS and row.get("source_name") in {"tushare", "baostock"}:
            inferred = infer_metric_unit(row["source_name"], api_name, metric_name)
            if row.get("unit", "").strip().lower() in {"", "mixed"}:
                row["unit"] = inferred
                row["original_unit_text"] = inferred
                row["currency"] = (
                    "CNY"
                    if inferred in {"CNY", "CNY_per_share", "1000_CNY", "10k_CNY"}
                    else ""
                )
                note = row.get("notes", "")
                marker = "unit normalized from source field semantics without value rescaling"
                if marker not in note:
                    row["notes"] = f"{note} {marker}.".strip()
                changed += 1
        retained.append(row)
    ids = [row.get("metric_candidate_id", "") for row in retained]
    if len(ids) != len(set(ids)):
        raise ValueError("unit normalization found duplicate metric_candidate_id values")
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(retained)
    temporary.replace(path)
    return {
        "rows_before": len(rows),
        "rows_after": len(retained),
        "units_changed": changed,
        "nonmetric_rows_removed": removed_nonmetrics,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize units in structured draft metrics.")
    parser.add_argument("--metrics", default="data/manifests/metrics_draft.csv")
    args = parser.parse_args(argv)
    result = normalize(Path(args.metrics))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
