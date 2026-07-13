from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingest.evidence_generation import build_generation_record


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an evidence-generation lock for downstream Bundle 9R/10R")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default="config/r5_bundle8r_generation_inputs.yaml")
    parser.add_argument("--created-at", default="2026-07-13")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
    record = build_generation_record(
        repo_root=args.repo_root,
        input_paths=config.get("required_inputs", []),
        generation_label=str(config.get("generation_label", "r5_bundle8r")),
        created_at=args.created_at,
    )
    record["downstream_consumers"] = config.get("downstream_consumers", [])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(record, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"generation_id={record['generation_id']} missing={record['missing_input_count']}")
    return 0 if record["missing_input_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
