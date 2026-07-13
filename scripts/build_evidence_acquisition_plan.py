from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingest.acquisition_orchestrator import build_queue_from_files


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a health-aware evidence adapter run queue. Dry-run is the default."
    )
    parser.add_argument("--request", required=True, help="Path to data_request_plan.yaml")
    parser.add_argument(
        "--routes",
        default="config/evidence_source_routes.yaml",
        help="Path to evidence source route catalog",
    )
    parser.add_argument(
        "--registry",
        default="config/source_registry.yaml",
        help="Path to source registry",
    )
    parser.add_argument(
        "--health-ledger",
        default="data/manifests/source_health_ledger.yaml",
        help="Path to source health ledger",
    )
    parser.add_argument(
        "--output",
        default="data/processed/logs/adapter_run_queue.yaml",
        help="Output adapter queue path",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Mark queue as live. This script still does not call adapters itself.",
    )
    args = parser.parse_args()

    queue = build_queue_from_files(
        request_path=Path(args.request),
        routes_path=Path(args.routes),
        registry_path=Path(args.registry),
        health_path=Path(args.health_ledger),
        output_path=Path(args.output),
        mode="live" if args.live else "dry_run",
    )
    print(
        f"request_id={queue['request_id']} queue={len(queue['queue'])} "
        f"blocked={len(queue['blocked_capabilities'])} mode={queue['mode']}"
    )
    return 1 if queue["blocked_capabilities"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
