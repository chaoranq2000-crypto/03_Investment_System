from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.r5_bundle13r_evidence_backflow import validate_generation_lock  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Bundle 13R self-contained generation lock.")
    parser.add_argument("--lock", required=True)
    args = parser.parse_args()
    issues = validate_generation_lock(Path(args.lock))
    if issues:
        for row in issues:
            print(row, file=sys.stderr)
        return 2
    print("Bundle 13R generation lock: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
