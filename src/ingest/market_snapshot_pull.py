from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path
from typing import Sequence


def build_market_snapshot(
    *,
    repo_root: Path,
    source_name: str,
    run_id: str,
    input_csv: Path,
    as_of_date: str,
) -> dict[str, str]:
    raw_dir = repo_root / "data" / "raw" / "structured_api" / source_name / run_id
    normalized_dir = repo_root / "data" / "processed" / "normalized" / run_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "market_snapshot.csv"
    normalized_path = normalized_dir / "market_snapshot.csv"
    if raw_path.exists():
        if raw_path.read_bytes() != input_csv.read_bytes():
            raise FileExistsError(f"Refusing to overwrite market snapshot with different bytes: {raw_path}")
    else:
        shutil.copy2(input_csv, raw_path)
    rows = list(csv.DictReader(input_csv.open("r", encoding="utf-8", newline="")))
    fieldnames = list(rows[0].keys()) if rows else ["as_of_date"]
    if "as_of_date" not in fieldnames:
        fieldnames.append("as_of_date")
    with normalized_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row.setdefault("as_of_date", as_of_date)
            writer.writerow(row)
    return {"raw_path": str(raw_path), "normalized_path": str(normalized_path), "rows": str(len(rows))}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Register an offline market snapshot fixture.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--as-of-date", required=True)
    args = parser.parse_args(argv)
    result = build_market_snapshot(
        repo_root=Path(args.repo_root),
        source_name=args.source_name,
        run_id=args.run_id,
        input_csv=Path(args.input_csv),
        as_of_date=args.as_of_date,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
