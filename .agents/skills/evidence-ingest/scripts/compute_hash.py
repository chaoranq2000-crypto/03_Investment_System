#!/usr/bin/env python3
"""Compute hashes for evidence-ingest raw files or snapshots."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import BinaryIO


def hash_stream(stream: BinaryIO, algo: str = "sha256", chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.new(algo)
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        h.update(chunk)
    return h.hexdigest()


def hash_file(path: Path, algo: str = "sha256") -> str:
    with path.open("rb") as fh:
        return hash_stream(fh, algo=algo)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute a file hash for evidence ingest.")
    parser.add_argument("path", help="File path to hash.")
    parser.add_argument("--algo", default="sha256", help="Hash algorithm. Default: sha256")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists() or not path.is_file():
        raise SystemExit(f"File not found: {path}")

    digest = hash_file(path, args.algo)
    if args.json:
        print(json.dumps({"path": str(path), "algo": args.algo, "hash": digest}, ensure_ascii=False, indent=2))
    else:
        print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
