from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable


def _read(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write(path: Path, fields: list[str], rows: Iterable[dict[str, str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".quarantine_tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def quarantine(
    *,
    manifest_path: Path,
    metrics_path: Path,
    claims_path: Path,
    evidence_id: str,
    superseded_by: str,
    reason: str,
    candidate_only: bool = False,
) -> dict[str, int | str]:
    fields, manifest = _read(manifest_path)
    updated = 0
    for row in manifest:
        if row.get("evidence_id") != evidence_id:
            continue
        if not candidate_only:
            row["status"] = "superseded"
        row["candidate_status"] = "blocked"
        row["review_status"] = "rejected"
        if not candidate_only:
            row["superseded_by"] = superseded_by
        row["notes"] = f"{row.get('notes', '')}; QUARANTINED: {reason}".strip("; ")
        updated += 1
    if updated != 1:
        raise ValueError(f"expected one manifest row for {evidence_id}, found {updated}")
    _write(manifest_path, fields, manifest)

    metric_fields, metrics = _read(metrics_path)
    retained_metrics = [row for row in metrics if row.get("source_evidence_id") != evidence_id]
    removed_metrics = len(metrics) - len(retained_metrics)
    _write(metrics_path, metric_fields, retained_metrics)

    removed_claims = 0
    if claims_path.exists():
        claim_fields, claims = _read(claims_path)
        retained_claims = [row for row in claims if row.get("evidence_id") != evidence_id]
        removed_claims = len(claims) - len(retained_claims)
        _write(claims_path, claim_fields, retained_claims)
    return {
        "evidence_id": evidence_id,
        "superseded_by": superseded_by,
        "manifest_rows_updated": updated,
        "metric_candidates_removed": removed_metrics,
        "claim_candidates_removed": removed_claims,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Quarantine draft candidates from an over-broad evidence snapshot.")
    parser.add_argument("--manifest", default="data/manifests/evidence_manifest.csv")
    parser.add_argument("--metrics", default="data/manifests/metrics_draft.csv")
    parser.add_argument("--claims", default="data/manifests/claims_draft.csv")
    parser.add_argument("--evidence-id", required=True)
    parser.add_argument("--superseded-by", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--candidate-only", action="store_true")
    args = parser.parse_args()
    result = quarantine(
        manifest_path=Path(args.manifest),
        metrics_path=Path(args.metrics),
        claims_path=Path(args.claims),
        evidence_id=args.evidence_id,
        superseded_by=args.superseded_by,
        reason=args.reason,
        candidate_only=args.candidate_only,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
