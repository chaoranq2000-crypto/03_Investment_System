from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def main() -> int:
    parser = argparse.ArgumentParser(description="Reject Bundle 9R/10R artifacts built from an older evidence generation")
    parser.add_argument("--current-lock", required=True)
    parser.add_argument("--downstream-artifact", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    current = yaml.safe_load(Path(args.current_lock).read_text(encoding="utf-8")) or {}
    downstream = yaml.safe_load(Path(args.downstream_artifact).read_text(encoding="utf-8")) or {}
    current_id = str(current.get("generation_id", ""))
    recorded = str(downstream.get("input_evidence_generation_id", ""))
    fresh = bool(current_id) and current_id == recorded
    report = {
        "decision": "pass" if fresh else "needs_fix",
        "current_generation_id": current_id,
        "recorded_generation_id": recorded or None,
        "status": "current" if fresh else "stale_due_to_upstream_evidence_generation_change",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"decision={report['decision']} status={report['status']}")
    return 0 if fresh else 1


if __name__ == "__main__":
    raise SystemExit(main())
