from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Sequence

from evidence_io import (
    EVIDENCE_FIELDNAMES,
    INGEST_RUN_FIELDNAMES,
    evidence_id,
    immutable_copy_file,
    immutable_copy_or_write_bytes,
    normalize_stock_code,
    repo_rel,
    safe_slug,
    short_hash,
    utc_now_iso,
    write_csv_rows,
    write_json,
)

OFFICIAL_SOURCE_TYPES = {
    "annual_report",
    "interim_report",
    "quarterly_report",
    "announcement",
    "official_disclosure",
    "exchange_inquiry_reply",
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download or register an official disclosure file.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--stock-code", required=True)
    parser.add_argument("--company-id", default="")
    parser.add_argument("--company-name", default="")
    parser.add_argument("--source-name", default="manual")
    parser.add_argument("--source-type", default="official_disclosure", choices=sorted(OFFICIAL_SOURCE_TYPES))
    parser.add_argument("--filing-type", default="official_disclosure")
    parser.add_argument("--title", required=True)
    parser.add_argument("--publisher", default="")
    parser.add_argument("--publish-date", required=True)
    parser.add_argument("--source-url", default="")
    parser.add_argument("--local-file", default="")
    parser.add_argument("--allow-metadata-only", action="store_true")
    parser.add_argument("--license-note", default="official disclosure; verify redistribution terms")
    return parser.parse_args(argv)


def download_url(url: str, timeout_seconds: int = 30) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 evidence-ingest"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return response.read()


def extension_from_title_or_url(title: str, url: str) -> str:
    lower_url = url.lower()
    for ext in (".pdf", ".html", ".htm", ".txt", ".md"):
        if lower_url.endswith(ext):
            return ext
    if "pdf" in lower_url or "年度报告" in title or "报告" in title:
        return ".pdf"
    return ".json"


def raw_dir_for_source_type(repo_root: Path, source_type: str) -> Path:
    if source_type == "annual_report":
        return repo_root / "data" / "raw" / "annual_reports"
    return repo_root / "data" / "raw" / "announcements"


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    stock_code = normalize_stock_code(args.stock_code)
    retrieved_at = utc_now_iso()
    publisher = args.publisher or args.source_name
    base_stem = f"{safe_slug(args.source_name)}_{safe_slug(args.filing_type)}_{stock_code}_{args.publish_date}"

    raw_dir = raw_dir_for_source_type(repo_root, args.source_type)
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_status = ""
    issue = ""

    if args.local_file:
        source_path = Path(args.local_file)
        ext = source_path.suffix or extension_from_title_or_url(args.title, args.source_url)
        raw_path = raw_dir / f"{base_stem}{ext}"
        raw_status, file_hash = immutable_copy_file(source_path, raw_path)
        file_format = ext.lstrip(".") or "unknown"
        status = "active"
        parse_status = "not_parsed"
    elif args.source_url:
        ext = extension_from_title_or_url(args.title, args.source_url)
        raw_path = raw_dir / f"{base_stem}{ext}"
        try:
            data = download_url(args.source_url)
            raw_status, file_hash = immutable_copy_or_write_bytes(raw_path, data)
            file_format = ext.lstrip(".") or "unknown"
            status = "active"
            parse_status = "not_parsed"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if not args.allow_metadata_only:
                raise
            metadata = {
                "title": args.title,
                "source_url": args.source_url,
                "download_error": repr(exc),
                "retrieved_at": retrieved_at,
            }
            raw_path = raw_dir / f"{base_stem}_metadata_only.json"
            payload = json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8")
            raw_status, file_hash = immutable_copy_or_write_bytes(raw_path, payload)
            file_format = "json"
            status = "download_todo"
            parse_status = "metadata_only"
            issue = f"download_failed: {exc!r}"
    else:
        raise SystemExit("Provide --local-file or --source-url.")

    ev_id = evidence_id(
        source_type=args.source_type,
        entity=stock_code,
        date_value=args.publish_date,
        hash_value=file_hash,
    )
    manifest_row = {
        "evidence_id": ev_id,
        "source_type": args.source_type,
        "source_name": args.source_name,
        "source_group": "official_disclosure" if args.source_name != "manual" else "manual",
        "title": args.title,
        "publisher": publisher,
        "publish_date": args.publish_date,
        "retrieved_at": retrieved_at,
        "ingested_at": utc_now_iso(),
        "as_of_date": args.publish_date,
        "entity_type": "company",
        "entity_id": args.company_id,
        "segment_id": "",
        "company_id": args.company_id,
        "stock_code": stock_code,
        "source_url": args.source_url,
        "raw_file_path": repo_rel(raw_path, repo_root),
        "raw_archive_policy": "full_file_archived",
        "file_hash": file_hash,
        "content_hash": file_hash,
        "api_params_hash": "",
        "processed_text_path": "",
        "processed_table_path": "",
        "page_map_path": "",
        "page_count": "",
        "language": "zh-CN",
        "file_format": file_format,
        "ingest_mode": "official_disclosure_search" if args.source_url else "manual_file",
        "reliability_rank": "A" if args.source_name in {"cninfo", "sse", "szse", "bse", "manual"} else "C",
        "material_claim_allowed": "true",
        "allowed_claim_types": "fact,management_comment,estimate,inference_after_review",
        "license_note": args.license_note,
        "stale_after": "365d",
        "status": status,
        "parse_status": parse_status,
        "candidate_status": "not_generated",
        "review_status": "draft",
        "previous_evidence_id": "",
        "superseded_by": "",
        "notes": f"raw_status={raw_status}; {issue}".strip(),
    }
    write_csv_rows(repo_root / "data" / "manifests" / "evidence_manifest.csv", EVIDENCE_FIELDNAMES, [manifest_row])

    run_id = f"ingest_official_{stock_code}_{short_hash(file_hash, 6)}"
    log_row = {
        "run_id": run_id,
        "ingest_mode": manifest_row["ingest_mode"],
        "started_at": retrieved_at,
        "finished_at": utc_now_iso(),
        "result": "PARTIAL_SUCCESS" if status == "download_todo" else "SUCCESS",
        "stock_code": stock_code,
        "source_name": args.source_name,
        "source_type": args.source_type,
        "api_name": "",
        "manifest_rows_created": "1",
        "manifest_rows_updated": "0",
        "metric_candidates": "0",
        "claim_candidates": "0",
        "issues": issue,
        "notes": "official disclosure registered; parse later before material claims",
    }
    write_csv_rows(repo_root / "data" / "manifests" / "ingest_runs.csv", INGEST_RUN_FIELDNAMES, [log_row])
    write_json(repo_root / "data" / "processed" / "logs" / f"{ev_id}__ingest_log.json", log_row)
    print(json.dumps({"evidence_id": ev_id, "status": status}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
