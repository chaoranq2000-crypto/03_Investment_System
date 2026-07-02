#!/usr/bin/env python3
"""Validate evidence manifest local paths and URL/path separation."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from urllib.parse import urlparse

PATH_FIELDS = ["raw_file_path", "processed_text_path", "processed_table_path", "page_map_path"]
URL_FIELDS = ["source_url"]


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check paths in evidence_manifest.csv")
    parser.add_argument("manifest")
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    issues: list[str] = []
    with Path(args.manifest).open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row_no, row in enumerate(reader, start=2):
            eid = (row.get("evidence_id") or "").strip()
            for field in URL_FIELDS:
                val = (row.get(field) or "").strip()
                if val and not is_url(val):
                    issues.append(f"HIGH row={row_no} evidence_id={eid} {field} is not an http(s) URL: {val}")
            for field in PATH_FIELDS:
                val = (row.get(field) or "").strip()
                if not val:
                    continue
                if is_url(val):
                    issues.append(f"HIGH row={row_no} evidence_id={eid} {field} contains URL; move to source_url: {val}")
                    continue
                if not (repo / val).exists():
                    issues.append(f"HIGH row={row_no} evidence_id={eid} {field} does not exist: {val}")

    if issues:
        print("\n".join(issues))
        return 1
    print("PASS: path validation succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
