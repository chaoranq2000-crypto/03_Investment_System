#!/usr/bin/env python3
"""Validate evidence_manifest.csv for Phase B1 evidence-ingest contract."""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

REQUIRED_FIELDS = {
    "evidence_id",
    "source_type",
    "source_name",
    "title",
    "ingested_at",
    "raw_archive_policy",
    "ingest_mode",
    "reliability_rank",
    "material_claim_allowed",
    "status",
    "parse_status",
    "candidate_status",
    "review_status",
    "license_note",
}

STATUS = {"registered", "active", "duplicate", "superseded", "stale", "contradicted", "archived", "failed"}
PARSE_STATUS = {"not_required", "pending", "parsed", "partial", "failed", "ocr_required", "manual_required"}
CANDIDATE_STATUS = {"not_generated", "generated", "partial", "blocked", "not_allowed"}
REVIEW_STATUS = {"draft", "needs_review", "reviewed", "accepted", "accepted_with_todos", "rejected", "blocked"}
RELIABILITY = {"A", "B", "C", "D", "unknown"}
MATERIAL = {"true", "false", "metric_only"}
ARCHIVE_POLICY = {"full_file_archived", "snapshot_archived", "metadata_only", "evidence_card_only", "not_archived_license"}
PATH_FIELDS = ["raw_file_path", "processed_text_path", "processed_table_path", "page_map_path"]
DATE_FIELDS = ["publish_date", "retrieved_at", "ingested_at", "as_of_date"]
HASH_RE = re.compile(r"^[0-9a-fA-F]{6,128}$")


@dataclass
class Issue:
    severity: str
    row: int
    evidence_id: str
    field: str
    issue: str
    fix: str


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]
        return rows, list(reader.fieldnames or [])


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def parse_any_date(value: str) -> date | None:
    if not value:
        return None
    clean = value.strip()
    try:
        if clean.endswith("Z"):
            clean = clean[:-1] + "+00:00"
        return datetime.fromisoformat(clean).date()
    except ValueError:
        pass
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def add(issues: list[Issue], severity: str, row: int, evidence_id: str, field: str, issue: str, fix: str) -> None:
    issues.append(Issue(severity, row, evidence_id, field, issue, fix))


def validate_rows(rows: list[dict[str, str]], fields: list[str], repo: Path, check_paths: bool = True, today: date | None = None) -> list[Issue]:
    # Manifest date-only fields follow the operator/workspace local calendar.
    # Using the UTC date creates false "future" errors during the local day
    # immediately after midnight in an eastern timezone.
    today = today or datetime.now().astimezone().date()
    issues: list[Issue] = []

    missing_columns = sorted(REQUIRED_FIELDS - set(fields))
    for col in missing_columns:
        add(issues, "critical", 0, "", col, f"Missing required manifest column: {col}", "Add the column to evidence_manifest.csv")
    if missing_columns:
        return issues

    ids = [r.get("evidence_id", "") for r in rows]
    for evidence_id, count in Counter(ids).items():
        if evidence_id and count > 1:
            add(issues, "high", 0, evidence_id, "evidence_id", f"Duplicate evidence_id appears {count} times", "Keep one active row; mark duplicates explicitly")

    hash_to_ids: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        key = r.get("file_hash") or r.get("content_hash")
        if key:
            hash_to_ids[key].append(r.get("evidence_id", ""))
    for h, evidence_ids in hash_to_ids.items():
        active_ids = [eid for eid in evidence_ids if eid]
        if len(active_ids) > 1:
            add(issues, "medium", 0, ";".join(active_ids), "file_hash/content_hash", "Same hash appears in multiple rows", "Ensure duplicates are marked status=duplicate where appropriate")

    for idx, row in enumerate(rows, start=2):
        eid = row.get("evidence_id", "")
        for field in REQUIRED_FIELDS:
            if not row.get(field):
                add(issues, "high", idx, eid, field, "Required field is empty", "Fill the field or mark row failed with explanatory notes")

        if not row.get("publish_date") and not row.get("as_of_date"):
            add(issues, "medium", idx, eid, "publish_date/as_of_date", "Neither publish_date nor as_of_date is set", "Fill at least one date or explain in notes")

        if row.get("status") and row["status"] not in STATUS:
            add(issues, "high", idx, eid, "status", f"Invalid status: {row['status']}", f"Use one of {sorted(STATUS)}")
        if row.get("parse_status") and row["parse_status"] not in PARSE_STATUS:
            add(issues, "high", idx, eid, "parse_status", f"Invalid parse_status: {row['parse_status']}", f"Use one of {sorted(PARSE_STATUS)}")
        if row.get("candidate_status") and row["candidate_status"] not in CANDIDATE_STATUS:
            add(issues, "high", idx, eid, "candidate_status", f"Invalid candidate_status: {row['candidate_status']}", f"Use one of {sorted(CANDIDATE_STATUS)}")
        if row.get("review_status") and row["review_status"] not in REVIEW_STATUS:
            add(issues, "high", idx, eid, "review_status", f"Invalid review_status: {row['review_status']}", f"Use one of {sorted(REVIEW_STATUS)}")
        if row.get("reliability_rank") and row["reliability_rank"] not in RELIABILITY:
            add(issues, "high", idx, eid, "reliability_rank", f"Invalid reliability_rank: {row['reliability_rank']}", f"Use one of {sorted(RELIABILITY)}")
        if row.get("material_claim_allowed") and row["material_claim_allowed"] not in MATERIAL:
            add(issues, "high", idx, eid, "material_claim_allowed", f"Invalid material_claim_allowed: {row['material_claim_allowed']}", "Use true, false, or metric_only")
        if row.get("raw_archive_policy") and row["raw_archive_policy"] not in ARCHIVE_POLICY:
            add(issues, "high", idx, eid, "raw_archive_policy", f"Invalid archive policy: {row['raw_archive_policy']}", f"Use one of {sorted(ARCHIVE_POLICY)}")

        if row.get("reliability_rank") == "D" and row.get("material_claim_allowed") != "false":
            add(issues, "high", idx, eid, "material_claim_allowed", "D-level source cannot support material claims", "Set material_claim_allowed=false and generate clue/TODO only")

        if not (row.get("file_hash") or row.get("content_hash") or row.get("api_params_hash")):
            add(issues, "high", idx, eid, "hash", "No file_hash/content_hash/api_params_hash present", "Compute a hash or explain failed row")
        for hf in ["file_hash", "content_hash", "api_params_hash"]:
            val = row.get(hf, "")
            if val and not HASH_RE.match(val):
                add(issues, "medium", idx, eid, hf, f"Hash value has unexpected format: {val}", "Use lowercase SHA-style hex hash")

        src_url = row.get("source_url", "")
        if src_url and not is_url(src_url):
            add(issues, "medium", idx, eid, "source_url", "source_url is not an http(s) URL", "Move local paths to raw_file_path or leave source_url blank")

        for pf in PATH_FIELDS:
            value = row.get(pf, "")
            if value and is_url(value):
                add(issues, "high", idx, eid, pf, "Local path field contains a URL", "Move URL to source_url and keep path repo-relative")
            if value and check_paths:
                path = repo / value
                if not path.exists():
                    severity = "high" if pf == "raw_file_path" and row.get("raw_archive_policy") in {"full_file_archived", "snapshot_archived"} and row.get("status") != "failed" else "medium"
                    add(issues, severity, idx, eid, pf, f"Path does not exist: {value}", "Create the file, correct the path, or change archive policy/status")

        if row.get("raw_archive_policy") in {"full_file_archived", "snapshot_archived"} and not row.get("raw_file_path") and row.get("status") != "failed":
            add(issues, "high", idx, eid, "raw_file_path", "Archive policy requires a raw path", "Fill raw_file_path or change archive policy")

        for df in DATE_FIELDS:
            val = row.get(df, "")
            if val:
                parsed = parse_any_date(val)
                if parsed is None:
                    add(issues, "medium", idx, eid, df, f"Date not parseable: {val}", "Use ISO date or datetime")
                elif parsed > today:
                    add(issues, "high", idx, eid, df, f"Date is in the future: {val}", "Correct the date or explain only if it is a future due date field")

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate evidence manifest.")
    parser.add_argument("manifest_path", nargs="?", help="Path to evidence_manifest.csv")
    parser.add_argument("--manifest", dest="manifest_option", help="Path to evidence_manifest.csv")
    parser.add_argument("--repo", default=".", help="Repo root for path validation")
    parser.add_argument("--no-path-check", action="store_true", help="Skip local path existence checks")
    parser.add_argument("--json", action="store_true", help="Output JSON issues")
    args = parser.parse_args()

    manifest_arg = args.manifest_option or args.manifest_path
    if not manifest_arg:
        parser.error("manifest path is required as a positional argument or --manifest")

    manifest = Path(manifest_arg)
    repo = Path(args.repo).resolve()
    rows, fields = read_csv(manifest)
    issues = validate_rows(rows, fields, repo=repo, check_paths=not args.no_path_check)

    if args.json:
        print(json.dumps([asdict(i) for i in issues], ensure_ascii=False, indent=2))
    else:
        if not issues:
            print("PASS: manifest validation succeeded")
        else:
            for issue in issues:
                print(f"{issue.severity.upper()} row={issue.row} evidence_id={issue.evidence_id} field={issue.field}: {issue.issue} | fix={issue.fix}")

    return 1 if any(i.severity in {"critical", "high"} for i in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
