#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.r5_bundle12r_operating_evidence import write_bundle12r_outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the R5 Bundle 12R operating-evidence qualification gate")
    parser.add_argument("--input", required=True, type=Path, help="Operating-evidence input YAML")
    parser.add_argument(
        "--contract",
        type=Path,
        default=ROOT / "config" / "r5_bundle12r_operating_evidence_contract.yaml",
        help="Bundle 12R contract YAML",
    )
    parser.add_argument("--output-dir", required=True, type=Path, help="Output directory")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 2 when the operating gate needs backflow",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    built = write_bundle12r_outputs(args.input.resolve(), args.contract.resolve(), args.output_dir.resolve())
    decision = built["result"]["decision"]
    print(f"decision={decision}")
    print(f"generation_id={built['generation_lock']['generation_id']}")
    print(f"output_dir={args.output_dir.resolve()}")
    if args.strict and decision != "operating_evidence_ready":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
