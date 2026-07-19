#!/usr/bin/env python3
"""CLI wrapper for the local R5 night-shift runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.maintenance.night_shift.night03 import MISSION_ID  # noqa: E402
from src.maintenance.night_shift.night03_backflow import consume_approved_inputs  # noqa: E402
from src.maintenance.night_shift.runner import main as runtime_main  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--mission" not in arguments:
        return runtime_main(arguments)
    parser = argparse.ArgumentParser(description="R5 Night03 mission dispatcher")
    parser.add_argument("--mission", required=True)
    parser.add_argument("--mode", choices=("consume-approved",), required=True)
    parser.add_argument("--continue-on-external-block", action="store_true")
    args = parser.parse_args(arguments)
    if args.mission != MISSION_ID:
        parser.error(f"unsupported mission: {args.mission}")
    result = consume_approved_inputs(
        REPO_ROOT,
        continue_on_external_block=args.continue_on_external_block,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
