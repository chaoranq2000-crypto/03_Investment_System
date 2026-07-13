from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def load(path: str) -> dict:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise ValueError(f"YAML root must be mapping: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Reject Bundle 10R artifacts built from an older Bundle 9R model generation.")
    parser.add_argument("--current-model-lock", required=True)
    parser.add_argument("--downstream-artifact", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    lock = load(args.current_model_lock)
    downstream = load(args.downstream_artifact)
    current_id = str(lock.get("generation_id") or "")
    recorded = str(downstream.get("input_model_generation_id") or "")
    fresh = bool(current_id) and current_id == recorded
    report = {
        "decision": "pass" if fresh else "needs_fix",
        "current_model_generation_id": current_id or None,
        "recorded_model_generation_id": recorded or None,
        "status": "current" if fresh else "stale_due_to_bundle9r_model_generation_change",
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return 0 if fresh else 2


if __name__ == "__main__":
    raise SystemExit(main())
