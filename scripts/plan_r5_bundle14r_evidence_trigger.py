from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.maintenance.evidence_trigger_backflow import evaluate_from_files


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate Bundle 14R official-evidence triggers and emit a selective "
            "backflow plan."
        )
    )
    parser.add_argument("--registry", required=True, help="Bundle 14R trigger registry YAML")
    parser.add_argument("--candidates", required=True, help="Reviewed candidate evidence pack YAML")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument(
        "--workflow-state",
        help="Optional workflow_state.yaml; a proposed copy is emitted, never overwritten",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    paths = evaluate_from_files(
        registry_path=Path(args.registry),
        candidate_pack_path=Path(args.candidates),
        output_dir=Path(args.output_dir),
        workflow_state_path=Path(args.workflow_state) if args.workflow_state else None,
    )
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
