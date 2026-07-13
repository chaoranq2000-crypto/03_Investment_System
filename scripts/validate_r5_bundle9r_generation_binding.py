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
    validate_generation_bound_artifact,
    validate_locked_input_hashes,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Bundle 9R evidence-generation binding and reject stale downstream inputs.")
    parser.add_argument("--binding", default="config/r5_bundle9r_generation_binding.yaml")
    parser.add_argument("--current-lock", required=True)
    parser.add_argument("--downstream-artifact", action="append", default=[])
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--verify-locked-input-hashes", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    binding = load_yaml(Path(args.binding))
    lock = load_yaml(Path(args.current_lock))
    expected = binding["input_evidence_generation"]
    issues = validate_evidence_generation_lock(
        lock,
        expected_generation_id=str(expected["generation_id"]),
        expected_aggregate_sha256=str(expected["aggregate_sha256"]),
        required_consumer=str(expected["required_consumer"]),
    )
    current_id = str(lock.get("generation_id") or "")
    for raw_path in args.downstream_artifact:
        path = Path(raw_path)
        artifact = load_yaml(path)
        issues.extend(validate_generation_bound_artifact(artifact, current_generation_id=current_id, artifact_label=str(path)))
    if args.verify_locked_input_hashes:
        issues.extend(validate_locked_input_hashes(lock, Path(args.repo_root)))

    report = {
        "artifact_type": "R5_bundle9r_generation_binding_validation",
        "decision": decision_from_issues(issues),
        "current_generation_id": current_id or None,
        "checked_downstream_artifacts": args.downstream_artifact,
        "locked_input_hashes_checked": bool(args.verify_locked_input_hashes),
        "issues": issues_payload(issues),
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(report, allow_unicode=True, sort_keys=False)
    out.write_bytes(rendered.encode("utf-8"))
    print(json.dumps({"decision": report["decision"], "issues": len(issues), "generation_id": current_id}, ensure_ascii=False))
    return 0 if report["decision"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
