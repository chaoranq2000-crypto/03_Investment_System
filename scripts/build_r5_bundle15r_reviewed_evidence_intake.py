#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.maintenance.reviewed_evidence_intake import write_intake_outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a reviewed-evidence intake pack compatible with the existing "
            "R5 Bundle 14R trigger evaluator."
        )
    )
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--reviewed-input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--workflow-state", type=Path)
    parser.add_argument(
        "--fail-on-conflict",
        action="store_true",
        help="Return exit code 2 when conflicting reviewed values are present.",
    )
    parser.add_argument(
        "--require-candidate",
        action="store_true",
        help="Return exit code 3 when no eligible candidate is produced.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = write_intake_outputs(
        registry_path=args.registry,
        reviewed_input_path=args.reviewed_input,
        output_dir=args.output_dir,
        workflow_state_path=args.workflow_state,
    )
    summary = result["summary"]
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    for name, path in result["paths"].items():
        print(f"{name}: {path}")
    if args.fail_on_conflict and summary["conflict_group_count"]:
        return 2
    if args.require_candidate and summary["eligible_candidate_count"] == 0:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
