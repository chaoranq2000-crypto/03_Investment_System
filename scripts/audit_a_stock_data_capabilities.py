from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingest.capability_coverage import build_coverage_report, load_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit normalized a-stock-data capability adoption")
    parser.add_argument("--catalog", default="config/a_stock_data_capability_catalog.yaml")
    parser.add_argument("--output", default="reports/quality/R5_a_stock_data_capability_coverage.yaml")
    parser.add_argument("--decisions-output", default="reports/quality/R5_a_stock_data_adoption_decisions.csv")
    parser.add_argument("--allow-needs-fix", action="store_true")
    args = parser.parse_args()
    catalog = load_catalog(args.catalog)
    report = build_coverage_report(catalog)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    decisions_output = Path(args.decisions_output)
    decisions_output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "capability_id", "upstream_layer", "upstream_source", "adoption_decision",
        "priority", "required_for_bundle8r_close", "claim_boundary",
        "current_implementation_status", "target_adapter", "resolution_type",
    ]
    with decisions_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in catalog.get("capabilities", []):
            resolution = item.get("operational_resolution") or {}
            writer.writerow({
                **{field: item.get(field, "") for field in fields},
                "resolution_type": resolution.get("resolution_type", ""),
            })
    print(
        f"decision={report['decision']} capabilities={report['capability_count']} "
        f"core_ready={report['bundle8r_core_operational_count']}/{report['bundle8r_core_count']}"
    )
    if report["decision"] == "needs_fix" and args.allow_needs_fix:
        return 0
    return 0 if report["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
