#!/usr/bin/env python3
"""Write standardized ingest run logs."""
from __future__ import annotations

import argparse
import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

FIELDS = [
    "run_id",
    "created_at",
    "ingest_mode",
    "result",
    "input_count",
    "manifest_rows_created",
    "manifest_rows_updated",
    "duplicates_skipped",
    "claim_candidates",
    "metric_candidates",
    "clues",
    "issues_critical",
    "issues_high",
    "issues_medium",
    "issues_low",
    "notes",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Append a standardized evidence ingest log row.")
    parser.add_argument("--output", default="data/manifests/ingest_runs.csv")
    parser.add_argument("--ingest-mode", required=True)
    parser.add_argument("--result", required=True, choices=["SUCCESS", "PARTIAL_SUCCESS", "SKIPPED_DUPLICATE", "FAILED"])
    parser.add_argument("--input-count", default="0")
    parser.add_argument("--manifest-rows-created", default="0")
    parser.add_argument("--manifest-rows-updated", default="0")
    parser.add_argument("--duplicates-skipped", default="0")
    parser.add_argument("--claim-candidates", default="0")
    parser.add_argument("--metric-candidates", default="0")
    parser.add_argument("--clues", default="0")
    parser.add_argument("--issues-critical", default="0")
    parser.add_argument("--issues-high", default="0")
    parser.add_argument("--issues-medium", default="0")
    parser.add_argument("--issues-low", default="0")
    parser.add_argument("--notes", default="")
    parser.add_argument("--json", action="store_true", help="Print row JSON in addition to writing CSV")
    args = parser.parse_args()

    row = {
        "run_id": f"ingest_{uuid.uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "ingest_mode": args.ingest_mode,
        "result": args.result,
        "input_count": args.input_count,
        "manifest_rows_created": args.manifest_rows_created,
        "manifest_rows_updated": args.manifest_rows_updated,
        "duplicates_skipped": args.duplicates_skipped,
        "claim_candidates": args.claim_candidates,
        "metric_candidates": args.metric_candidates,
        "clues": args.clues,
        "issues_critical": args.issues_critical,
        "issues_high": args.issues_high,
        "issues_medium": args.issues_medium,
        "issues_low": args.issues_low,
        "notes": args.notes,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    exists = out.exists()
    with out.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)

    if args.json:
        print(json.dumps(row, ensure_ascii=False, indent=2))
    else:
        print(f"WROTE ingest log row: {row['run_id']} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
