from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingest.adapter_contracts import (
    load_contract_registry,
    load_yaml,
    validate_contract_registry,
    validate_route_adapter_readiness,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate that enabled routes point to operational adapters")
    parser.add_argument("--routes", default="config/evidence_source_routes.yaml")
    parser.add_argument("--contracts", default="config/adapter_contract_registry.yaml")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--import-check", action="store_true")
    parser.add_argument("--output", default="reports/quality/R5_adapter_operational_gate.yaml")
    parser.add_argument("--allow-needs-fix", action="store_true")
    args = parser.parse_args()

    registry = load_contract_registry(args.contracts)
    issues = validate_contract_registry(registry, repo_root=args.repo_root)
    issues.extend(
        validate_route_adapter_readiness(
            load_yaml(args.routes),
            registry,
            repo_root=args.repo_root,
            import_check=args.import_check,
        )
    )
    counts = Counter(str(item.get("severity", "unknown")) for item in issues)
    blocking = [item for item in issues if item.get("severity") in {"critical", "high"}]
    report = {
        "schema_version": 1,
        "decision": "pass" if not blocking else "needs_fix",
        "mode": "operational_not_merely_routed",
        "import_check": bool(args.import_check),
        "issue_counts": dict(sorted(counts.items())),
        "blocking_issue_count": len(blocking),
        "issues": issues,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"decision={report['decision']} blocking={len(blocking)}")
    if report["decision"] == "needs_fix" and args.allow_needs_fix:
        return 0
    return 0 if report["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
