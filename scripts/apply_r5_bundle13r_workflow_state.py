from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.r5_bundle13r_evidence_backflow import load_yaml, write_text_lf  # noqa: E402
from src.research.r5_bundle13r_workflow_state import apply_bundle13r_result_to_state  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or apply a Bundle 13R result to workflow_state.yaml.")
    parser.add_argument("--workflow-state", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--generation-lock", required=True)
    parser.add_argument("--output")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--backup")
    parser.add_argument("--as-of")
    args = parser.parse_args()

    state_path = Path(args.workflow_state).resolve()
    result = load_yaml(Path(args.result))
    lock = load_yaml(Path(args.generation_lock))
    state = load_yaml(state_path)
    updated = apply_bundle13r_result_to_state(
        state,
        result,
        generation_id=str(lock.get("generation_id", "")),
        as_of=args.as_of,
    )
    rendered = yaml.safe_dump(updated, allow_unicode=True, sort_keys=False, width=120)
    if args.write:
        backup = Path(args.backup).resolve() if args.backup else state_path.with_suffix(state_path.suffix + ".pre_bundle13r.bak")
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(state_path, backup)
        write_text_lf(state_path, rendered)
    if args.output:
        write_text_lf(Path(args.output), rendered)
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
