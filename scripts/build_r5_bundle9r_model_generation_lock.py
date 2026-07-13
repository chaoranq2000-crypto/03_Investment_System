from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.r5_bundle9r_contracts import load_yaml, sha256_file, stable_aggregate, validate_evidence_generation_lock  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a hash-bound Bundle 9R model generation for Bundle 10R consumption.")
    parser.add_argument("--evidence-lock", required=True)
    parser.add_argument("--artifact", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    evidence_lock = load_yaml(Path(args.evidence_lock))
    issues = validate_evidence_generation_lock(evidence_lock, required_consumer="R5_BUNDLE_9R_FORECAST_VALUATION_REBUILD")
    if issues:
        raise SystemExit("ineligible evidence generation: " + ",".join(x.code for x in issues))

    rows = []
    missing = []
    for raw in args.artifact:
        path = Path(raw)
        if not path.exists():
            missing.append(str(path))
            continue
        rows.append({"path": str(path).replace("\\", "/"), "sha256": sha256_file(path)})
    if missing:
        raise SystemExit("missing artifacts: " + ", ".join(missing))
    rows.sort(key=lambda row: row["path"])
    aggregate = stable_aggregate(rows)
    payload = {
        "schema_version": 1,
        "generation_label": "r5_bundle9r_model",
        "generation_id": f"model_gen_r5_bundle9r_{aggregate[:16]}",
        "created_at": date.today().isoformat(),
        "input_evidence_generation_id": evidence_lock["generation_id"],
        "input_evidence_aggregate_sha256": evidence_lock.get("aggregate_sha256"),
        "artifact_count": len(rows),
        "missing_artifact_count": 0,
        "artifacts": rows,
        "aggregate_sha256": aggregate,
        "downstream_consumers": ["R5_BUNDLE_10R_READER_REBUILD"],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    output.write_bytes(rendered.encode("utf-8"))
    print(payload["generation_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
