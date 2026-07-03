from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_candidate_promotion import evidence_ids_from_manifest, read_csv_dicts, validate_claim_candidate  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingest"))
from evidence_io import hash_json, safe_slug, short_hash, utc_now_iso  # noqa: E402


CLAIMS_REGISTRY_FIELDNAMES = [
    "claim_id",
    "evidence_id",
    "entity_type",
    "entity_id",
    "claim_text",
    "claim_type",
    "quote_or_excerpt",
    "page_no_or_section",
    "confidence",
    "valid_until",
    "status",
    "review_status",
    "notes",
]


def promote_claim_candidates(
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
        issues = validate_claim_candidate(row, evidence_ids)
        candidate_id = row.get("claim_candidate_id", "")
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
        claim_id = row.get("promote_to_claim_id") or "claim_{entity}_{hash}".format(
            entity=safe_slug(row.get("entity_id") or row.get("stock_code") or "unknown"),
            hash=short_hash(hash_json([candidate_id, row.get("claim_text", "")]), 8),
        )
        promoted.append(
            {
                "claim_id": claim_id,
                "evidence_id": row.get("evidence_id", ""),
                "entity_type": row.get("entity_type", ""),
                "entity_id": row.get("entity_id") or row.get("company_id", ""),
                "claim_text": row.get("claim_text", ""),
                "claim_type": row.get("claim_type", "unknown"),
                "quote_or_excerpt": row.get("quote_or_excerpt", ""),
                "page_no_or_section": row.get("page_no_or_section") or row.get("table_id", ""),
                "confidence": row.get("confidence", "medium"),
                "valid_until": row.get("valid_until", "next_refresh"),
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
        writer = csv.DictWriter(handle, fieldnames=CLAIMS_REGISTRY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(promoted)
    promotion_log_path.parent.mkdir(parents=True, exist_ok=True)
    with promotion_log_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["candidate_id", "result", "issues", "created_at"])
        writer.writeheader()
        writer.writerows(log_rows)
    return {"promoted": len(promoted), "rejected": len(log_rows) - len(promoted)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote reviewed claim candidates to a registry.")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-registry", required=True)
    parser.add_argument("--promotion-log", required=True)
    args = parser.parse_args(argv)
    print(
        promote_claim_candidates(
            candidates_path=Path(args.candidates),
            manifest_path=Path(args.manifest),
            output_registry_path=Path(args.output_registry),
            promotion_log_path=Path(args.promotion_log),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
