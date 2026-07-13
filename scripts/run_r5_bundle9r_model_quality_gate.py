from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.r5_bundle9r_contracts import (  # noqa: E402
    decision_from_issues,
    issues_payload,
    load_yaml,
    validate_evidence_generation_lock,
    validate_model_pack,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed quality gate for Bundle 9R forecast and valuation model packs.")
    parser.add_argument("--model-pack", required=True)
    parser.add_argument("--contract", default="config/r5_bundle9r_model_contract.yaml")
    parser.add_argument("--evidence-lock", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    model = load_yaml(Path(args.model_pack))
    contract = load_yaml(Path(args.contract))
    lock = load_yaml(Path(args.evidence_lock))
    lock_issues = validate_evidence_generation_lock(lock, required_consumer="R5_BUNDLE_9R_FORECAST_VALUATION_REBUILD")
    issues = [*lock_issues, *validate_model_pack(model, contract, expected_generation_id=str(lock.get("generation_id") or ""))]
    decision = decision_from_issues(issues)
    report = {
        "artifact_type": "R5_bundle9r_model_quality_scorecard",
        "decision": decision,
        "input_evidence_generation_id": lock.get("generation_id"),
        "critical_blocker_count": sum(1 for x in issues if x.severity == "critical"),
        "high_blocker_count": sum(1 for x in issues if x.severity == "high"),
        "issues": issues_payload(issues),
        "bundle10r_allowed": decision == "pass",
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(report, allow_unicode=True, sort_keys=False)
    output.write_bytes(rendered.encode("utf-8"))
    print(json.dumps({"decision": decision, "critical": report["critical_blocker_count"], "high": report["high_blocker_count"]}, ensure_ascii=False))
    return 0 if decision == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
