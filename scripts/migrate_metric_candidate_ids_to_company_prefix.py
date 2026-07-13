from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Sequence


def safe_slug(value: str, fallback: str = "unknown") -> str:
    slug = re.sub(r"[^A-Za-z0-9_\-]+", "_", str(value).strip()).strip("_").lower()
    return slug or fallback


def canonical_metric_candidate_id(row: dict[str, str]) -> str:
    current = row.get("metric_candidate_id", "")
    if current.startswith("metric_company_"):
        return current
    entity = row.get("entity_id") or row.get("company_id") or row.get("stock_code") or "unknown"
    metric_name = row.get("metric_name") or "unknown"
    period = row.get("period") or "unknown"
    suffix_match = re.search(r"_([0-9a-fA-F]{6,12})$", current)
    if suffix_match:
        suffix = suffix_match.group(1).lower()
    else:
        payload = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        suffix = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]
    return (
        f"metric_company_{safe_slug(entity)}_{safe_slug(metric_name)}_"
        f"{safe_slug(period)}_{suffix}"
    )


def migrate(path: Path) -> dict[str, int]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    changed = 0
    for row in rows:
        canonical = canonical_metric_candidate_id(row)
        if canonical != row.get("metric_candidate_id"):
            row["metric_candidate_id"] = canonical
            changed += 1
    ids = [row.get("metric_candidate_id", "") for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("metric_candidate_id migration would create duplicates")
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)
    return {"rows": len(rows), "changed": changed, "unique": len(set(ids))}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Canonicalize draft company metric candidate ids.")
    parser.add_argument("--metrics", default="data/manifests/metrics_draft.csv")
    args = parser.parse_args(argv)
    result = migrate(Path(args.metrics))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
