#!/usr/bin/env python3
"""Validate claim and metric candidates for Phase B1 evidence-ingest."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

CLAIM_TYPES = {
    "fact",
    "metric_statement",
    "management_comment",
    "company_claim",
    "analyst_view",
    "estimate",
    "inference",
    "clue",
    "risk",
    "counter_evidence",
}
REVIEW_STATUS = {"draft", "needs_review", "reviewed", "accepted", "accepted_with_todos", "rejected", "blocked"}


def read_manifest(path: Path) -> dict[str, dict[str, str]]:
    if not path or not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return {row.get("evidence_id", "").strip(): {k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(fh)}


def validate_claims(path: Path, manifest: dict[str, dict[str, str]]) -> list[str]:
    issues: list[str] = []
    if not path or not path.exists():
        return issues
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row_no, row in enumerate(reader, start=2):
            row = {k: (v or "").strip() for k, v in row.items()}
            cid = row.get("claim_candidate_id", "")
            eid = row.get("evidence_id", "")
            ctype = row.get("claim_type", "")
            review = row.get("review_status", "")
            materiality = row.get("materiality", "").lower()
            locator = row.get("quote_or_excerpt") or row.get("page_no_or_section") or row.get("table_id")

            if not eid:
                issues.append(f"HIGH row={row_no} claim={cid}: missing evidence_id")
            elif manifest and eid not in manifest:
                issues.append(f"HIGH row={row_no} claim={cid}: dangling evidence_id {eid}")
            if ctype not in CLAIM_TYPES:
                issues.append(f"HIGH row={row_no} claim={cid}: invalid claim_type {ctype}")
            if review and review not in REVIEW_STATUS:
                issues.append(f"HIGH row={row_no} claim={cid}: invalid review_status {review}")
            if ctype != "clue" and not locator:
                issues.append(f"HIGH row={row_no} claim={cid}: missing quote/page/table locator")
            if manifest and eid in manifest:
                ev = manifest[eid]
                if ev.get("reliability_rank") == "D" and ctype != "clue":
                    issues.append(f"HIGH row={row_no} claim={cid}: D-level evidence can only generate clue candidates")
                if ev.get("reliability_rank") == "D" and materiality in {"high", "material", "true"}:
                    issues.append(f"HIGH row={row_no} claim={cid}: D-level evidence cannot support material claim")
                if ev.get("reliability_rank") == "C" and ctype == "fact":
                    issues.append(f"MEDIUM row={row_no} claim={cid}: C-level evidence should not create verified fact without A/B support")
            if ctype == "estimate" and "estimate" not in row.get("claim_scope", "").lower() and "estimate" not in row.get("notes", "").lower():
                issues.append(f"MEDIUM row={row_no} claim={cid}: estimate should be explicitly marked in scope or notes")
    return issues


def validate_metrics(path: Path, manifest: dict[str, dict[str, str]]) -> list[str]:
    issues: list[str] = []
    if not path or not path.exists():
        return issues
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row_no, row in enumerate(reader, start=2):
            row = {k: (v or "").strip() for k, v in row.items()}
            mid = row.get("metric_candidate_id", "")
            eid = row.get("source_evidence_id", "")
            if not eid:
                issues.append(f"HIGH row={row_no} metric={mid}: missing source_evidence_id")
            elif manifest and eid not in manifest:
                issues.append(f"HIGH row={row_no} metric={mid}: dangling source_evidence_id {eid}")
            for field in ["metric_name", "period", "value", "unit"]:
                if not row.get(field):
                    issues.append(f"HIGH row={row_no} metric={mid}: missing {field}")
            if row.get("is_estimate", "").lower() not in {"true", "false", "1", "0", "yes", "no"}:
                issues.append(f"MEDIUM row={row_no} metric={mid}: is_estimate should be explicit true/false")
            if manifest and eid in manifest and manifest[eid].get("reliability_rank") == "D":
                issues.append(f"HIGH row={row_no} metric={mid}: D-level evidence cannot produce metric candidate")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate draft claim/metric candidates.")
    parser.add_argument("--repo", default=".", help="Repo root; accepted for command compatibility.")
    parser.add_argument("--manifest", default="data/manifests/evidence_manifest.csv")
    parser.add_argument("--claim-candidates", "--claims", dest="claim_candidates", default=None)
    parser.add_argument("--metric-candidates", "--metrics", dest="metric_candidates", default=None)
    args = parser.parse_args()

    manifest = read_manifest(Path(args.manifest)) if args.manifest else {}
    issues: list[str] = []
    if args.claim_candidates:
        issues.extend(validate_claims(Path(args.claim_candidates), manifest))
    if args.metric_candidates:
        issues.extend(validate_metrics(Path(args.metric_candidates), manifest))

    if issues:
        print("\n".join(issues))
        return 1 if any(i.startswith("HIGH") for i in issues) else 0
    print("PASS: candidate validation succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
