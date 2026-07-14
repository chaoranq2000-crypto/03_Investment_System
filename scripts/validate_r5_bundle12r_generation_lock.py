#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.r5_bundle12r_operating_evidence import validate_generation_lock


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an R5 Bundle 12R generation lock")
    parser.add_argument("lock", type=Path)
    args = parser.parse_args()
    issues = validate_generation_lock(args.lock.resolve())
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 2
    print("pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
