from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Move non-HTTP transport endpoints from source_url to notes.")
    parser.add_argument("--manifest", default="data/manifests/evidence_manifest.csv")
    args = parser.parse_args()
    path = Path(args.manifest)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    changed = 0
    for row in rows:
        source_url = str(row.get("source_url", "")).strip()
        if source_url and not source_url.startswith(("http://", "https://")):
            note = f"non_http_transport_endpoint={source_url}"
            prior = str(row.get("notes", "")).strip()
            row["notes"] = f"{prior}; {note}" if prior else note
            row["source_url"] = ""
            changed += 1
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)
    print(f"changed={changed} manifest={path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
