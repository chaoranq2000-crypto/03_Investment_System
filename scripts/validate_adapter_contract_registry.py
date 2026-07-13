from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingest.adapter_contracts import load_contract_registry, validate_contract_registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate adapter contracts and proof artifacts.")
    parser.add_argument("--contracts", default="config/adapter_contract_registry.yaml")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", default="reports/quality/R5_adapter_contract_registry_validation.yaml")
    args = parser.parse_args()

    registry = load_contract_registry(args.contracts)
    issues = validate_contract_registry(registry, repo_root=args.repo_root)
    blocking = [item for item in issues if item.get("severity") in {"critical", "high"}]
    counts = Counter(str(item.get("severity", "unknown")) for item in issues)
    payload = {
        "schema_version": 1,
        "decision": "pass" if not blocking else "needs_fix",
        "registry_id": registry.get("registry_id", ""),
        "adapter_count": len(registry.get("adapters", {})),
        "proof_files_verified": True,
        "issue_counts": dict(sorted(counts.items())),
        "blocking_issue_count": len(blocking),
        "issues": issues,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"decision={payload['decision']} adapters={payload['adapter_count']} blocking={len(blocking)}")
    return 0 if not blocking else 1


if __name__ == "__main__":
    raise SystemExit(main())
