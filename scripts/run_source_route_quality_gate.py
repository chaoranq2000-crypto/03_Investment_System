from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml

from src.ingest.source_routing import (
    load_route_catalog,
    load_source_registry,
    validate_route_catalog,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate source routes and claim boundaries")
    parser.add_argument(
        "--routes",
        default="config/evidence_source_routes.yaml",
        help="Path to route catalog",
    )
    parser.add_argument(
        "--registry",
        default="config/source_registry.yaml",
        help="Path to source registry",
    )
    parser.add_argument(
        "--output",
        default="reports/quality/source_route_quality_report.yaml",
        help="Quality report path",
    )
    args = parser.parse_args()

    catalog = load_route_catalog(args.routes)
    registry = load_source_registry(args.registry)
    issues = validate_route_catalog(catalog, registry)
    counts = Counter(item["severity"] for item in issues)
    blocking = [item for item in issues if item["severity"] in {"critical", "high"}]
    payload = {
        "schema_version": 1,
        "decision": "pass" if not blocking else "needs_fix",
        "capability_count": len(catalog.get("capabilities", {})),
        "source_count": len(registry.get("sources", {})),
        "issue_counts": dict(counts),
        "blocking_issue_count": len(blocking),
        "issues": issues,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(
        f"decision={payload['decision']} capabilities={payload['capability_count']} "
        f"blocking={payload['blocking_issue_count']}"
    )
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
