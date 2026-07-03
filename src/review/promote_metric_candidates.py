from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_candidate_promotion import evidence_ids_from_manifest, read_csv_dicts, validate_metric_candidate  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingest"))
from evidence_io import hash_json, safe_slug, short_hash, utc_now_iso  # noqa: E402


METRICS_REGISTRY_FIELDNAMES = [
    "metric_id",
    "entity_type",
    "entity_id",
    "metric_name",
    "period",
    "value",
    "unit",
    "source_evidence_id",
    "calculation_method",
    "is_estimate",
    "confidence",
    "created_at",
    "status",
    "review_status",
    "notes",
]


def promote_metric_candidates(
    *,
    candidates_path: Path,
    manifest_path: Path,
    output_registry_path: Path,
    promotion_log_path: Path,
) -> dict[str, int]:
    evidence_ids = evidence_ids_from_manifest(manifest_path)
    promoted: list[dict[str, str]] = []
    log_rows: list[dict[str, str]] = []
    for row in read_csv_dicts(candidates_path):
        issues = validate_metric_candidate(row, evidence_ids)
        candidate_id = row.get("metric_candidate_id", "")
        if issues:
            log_rows.append(
                {
                    "candidate_id": candidate_id,
                    "result": "rejected",
                    "issues": "|".join(issues),
                    "created_at": utc_now_iso(),
                }
            )
            continue
        metric_id = row.get("promote_to_metric_id") or "metric_{entity}_{name}_{period}_{hash}".format(
            entity=safe_slug(row.get("entity_id") or row.get("stock_code") or "unknown"),
            name=safe_slug(row.get("metric_name", "metric")),
            period=safe_slug(row.get("period", "unknown")),
            hash=short_hash(hash_json([candidate_id, row.get("value", "")]), 6),
        )
        promoted.append(
            {
                "metric_id": metric_id,
                "entity_type": row.get("entity_type", ""),
                "entity_id": row.get("entity_id") or row.get("company_id", ""),
                "metric_name": row.get("metric_name", ""),
                "period": row.get("period", ""),
                "value": row.get("value", ""),
                "unit": row.get("unit", ""),
                "source_evidence_id": row.get("source_evidence_id", ""),
                "calculation_method": row.get("calculation_method", ""),
                "is_estimate": row.get("is_estimate", "false"),
                "confidence": row.get("confidence", "medium"),
                "created_at": row.get("created_at") or utc_now_iso(),
                "status": "active",
                "review_status": "reviewed_r3_candidate",
                "notes": row.get("notes", "") + f"; promoted_from={candidate_id}",
            }
        )
        log_rows.append(
            {
                "candidate_id": candidate_id,
                "result": "promoted",
                "issues": "",
                "created_at": utc_now_iso(),
            }
        )

    output_registry_path.parent.mkdir(parents=True, exist_ok=True)
    with output_registry_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=METRICS_REGISTRY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(promoted)
    promotion_log_path.parent.mkdir(parents=True, exist_ok=True)
    with promotion_log_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["candidate_id", "result", "issues", "created_at"])
        writer.writeheader()
        writer.writerows(log_rows)
    return {"promoted": len(promoted), "rejected": len(log_rows) - len(promoted)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote reviewed metric candidates to a registry.")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-registry", required=True)
    parser.add_argument("--promotion-log", required=True)
    args = parser.parse_args(argv)
    print(
        promote_metric_candidates(
            candidates_path=Path(args.candidates),
            manifest_path=Path(args.manifest),
            output_registry_path=Path(args.output_registry),
            promotion_log_path=Path(args.promotion_log),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
