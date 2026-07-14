from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.r5_bundle13r_evidence_backflow import load_yaml, write_bundle13r_outputs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute Bundle 12R backflow into a reviewed, hash-bound promoted operating-evidence input."
    )
    parser.add_argument("--bundle12r-context-dir", required=True)
    parser.add_argument("--reviewed-backfill", required=True)
    parser.add_argument(
        "--contract",
        default="config/r5_bundle13r_backflow_execution_contract.yaml",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--bundle12r-rerun-result")
    parser.add_argument("--skip-upstream-hash-check", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    written = write_bundle13r_outputs(
        context_dir=Path(args.bundle12r_context_dir),
        reviewed_backfill_path=Path(args.reviewed_backfill),
        contract_path=Path(args.contract),
        output_dir=Path(args.output_dir),
        downstream_bundle12r_result_path=(
            Path(args.bundle12r_rerun_result) if args.bundle12r_rerun_result else None
        ),
        verify_bundle12r_hashes=not args.skip_upstream_hash_check,
    )
    result = written["result"]
    print(
        " ".join(
            [
                f"decision={result['decision']}",
                f"resolved={result['resolved_t1_t2_item_count']}",
                f"unresolved={result['unresolved_t1_t2_item_count']}",
                f"blockers={result['blocker_count']}",
                f"generation_id={written['generation_lock']['generation_id']}",
            ]
        )
    )
    if not args.strict:
        return 0
    contract = load_yaml(Path(args.contract))
    exit_codes = contract.get("exit_codes", {})
    return int(exit_codes.get(result["decision"], 3))


if __name__ == "__main__":
    raise SystemExit(main())
