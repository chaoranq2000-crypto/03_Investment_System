from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.r5_bundle11r_runtime import run_runtime, write_yaml  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the R5 Bundle 11R operating-research runtime")
    parser.add_argument("--registry", default="config/economic_archetype_registry.yaml")
    parser.add_argument("--contract", default="config/r5_bundle11r_runtime_contract.yaml")
    parser.add_argument("--segment-plan", required=True)
    parser.add_argument("--evidence-status", required=True)
    parser.add_argument("--peer-pack", required=True)
    parser.add_argument("--semantic-payload", required=True)
    parser.add_argument("--semantic-config", default="config/r5_bundle11r_semantic_gate.yaml")
    parser.add_argument("--output", required=True)
    parser.add_argument("--json-summary")
    args = parser.parse_args()

    result = run_runtime(
        registry_path=args.registry,
        runtime_contract_path=args.contract,
        segment_plan_path=args.segment_plan,
        evidence_status_path=args.evidence_status,
        peer_pack_path=args.peer_pack,
        semantic_payload_path=args.semantic_payload,
        semantic_config_path=args.semantic_config,
    )
    write_yaml(args.output, result)
    summary = {
        "decision": result["decision"],
        "issues": len(result["all_issues"]),
        "backflow_tasks": len(result["backflow_plan"]["tasks"]),
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    if args.json_summary:
        Path(args.json_summary).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if result["decision"] == "candidate_inputs_ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
