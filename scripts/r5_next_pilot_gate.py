#!/usr/bin/env python3
"""Write the R5 after-patch24 close gate result without running a pilot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def evaluate_gate(readiness: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    decision = str(readiness.get("decision", "R5_BLOCKED"))
    source_gapped_allowed = decision == "R5_READY_FOR_SOURCE_GAPPED_REAL_SAMPLE_PILOT"
    candidate_tasks = list(rules.get("candidate_tasks") or [])[: int(rules.get("max_next_candidate_tasks", 3))]
    return {
        "status": "closed_with_todos" if decision == "R5_CONTRACTS_EXECUTABLE_WITH_TODOS_ONLY" else "closed",
        "current_r5_state": decision,
        "source_gapped_real_sample_pilot_allowed": source_gapped_allowed,
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
        "blockers": readiness.get("blockers", []),
        "non_blockers": readiness.get("non_blockers", []),
        "next_candidate_tasks": candidate_tasks,
        "boundary": {
            "no_live_api": True,
            "do_not_execute_next_tasks_in_this_patch": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate R5 next pilot gate from readiness output.")
    parser.add_argument("--readiness", required=True, type=Path)
    parser.add_argument("--rules", default=Path("config/r5_next_pilot_gate_rules.yaml"), type=Path)
    parser.add_argument("--json", required=True, type=Path)
    args = parser.parse_args(argv)

    result = evaluate_gate(load_json(args.readiness), load_yaml(args.rules))
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "r5_next_pilot_gate state={state} source_gapped_allowed={source} sample_quality_allowed={sample} p2_allowed={p2}".format(
            state=result["current_r5_state"],
            source=str(result["source_gapped_real_sample_pilot_allowed"]).lower(),
            sample=str(result["sample_quality_report_allowed"]).lower(),
            p2=str(result["p2_allowed"]).lower(),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
