#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any

from src.report.r5_bundle10r_contracts import dump_yaml, load_yaml, validate_model_generation_lock


def transition_state(state: dict[str, Any], binding: dict[str, Any], model_lock: dict[str, Any]) -> dict[str, Any]:
    check = validate_model_generation_lock(model_lock, binding)
    if check["decision"] != "pass":
        raise ValueError("model-generation binding must pass before starting Bundle 10R")

    out = copy.deepcopy(state)
    historical_keys = sorted(
        key for key in out
        if "bundle10" in str(key).lower() and "bundle10r" not in str(key).lower()
    )
    out["status"] = "needs_fix"
    out["current_stage"] = "R5_bundle10r_reader_rebuild"
    out["required_next_skill"] = "stock-deep-dive"
    out["canonical_reader_status"] = "stale_pending_bundle10r_reader_generation"
    out["canonical_sample_quality_allowed"] = False
    out["sample_quality_allowed"] = False
    out["p2_allowed"] = False
    out["bundle10r_rebuild"] = {
        "status": "in_progress",
        "input_model_generation_id": model_lock["generation_id"],
        "input_model_aggregate_sha256": model_lock["aggregate_sha256"],
        "historical_bundle10_keys_preserved": historical_keys,
        "human_review_status": "not_started",
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or write the Bundle 10R workflow-state transition")
    parser.add_argument("--workflow-state", required=True)
    parser.add_argument("--binding", required=True)
    parser.add_argument("--model-lock", required=True)
    parser.add_argument("--output")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    state_path = Path(args.workflow_state)
    transitioned = transition_state(load_yaml(state_path), load_yaml(args.binding), load_yaml(args.model_lock))
    if args.write:
        backup = state_path.with_suffix(state_path.suffix + ".pre_bundle10r")
        if not backup.exists():
            backup.write_bytes(state_path.read_bytes())
        dump_yaml(transitioned, state_path)
        output = state_path
    else:
        output = Path(args.output or "/tmp/R5_bundle10r_state_preview.yaml")
        dump_yaml(transitioned, output)
    print(f"wrote={output} bundle10r_status={transitioned['bundle10r_rebuild']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
