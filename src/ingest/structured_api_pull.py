from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Sequence

from evidence_io import (
    EVIDENCE_FIELDNAMES,
    INGEST_RUN_FIELDNAMES,
    METRIC_CANDIDATE_FIELDNAMES,
    detect_period,
    evidence_id,
    hash_json,
    immutable_copy_file,
    is_number,
    normalize_stock_code,
    repo_rel,
    safe_slug,
    short_hash,
    utc_now_iso,
    write_csv_rows,
    write_json,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register a structured API/local fixture snapshot.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-name", default="local_fixture")
    parser.add_argument("--api-name", required=True)
    parser.add_argument("--stock-code", required=True)
    parser.add_argument("--company-id", default="")
    parser.add_argument("--company-name", default="")
    parser.add_argument("--input-csv", default="")
    parser.add_argument("--input-json", default="")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--publish-date", default="")
    parser.add_argument("--fields", default="")
    parser.add_argument("--unit", default="")
    parser.add_argument("--license-note", default="adapter terms; verify before redistribution")
    return parser.parse_args(argv)


def load_rows_from_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_normalized_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def metric_candidates_from_rows(
    *,
    rows: list[dict[str, str]],
    source_evidence_id: str,
    source_name: str,
    stock_code: str,
    company_id: str,
    api_name: str,
    api_params_hash: str,
    unit: str,
) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    created_at = utc_now_iso()
    for row_index, row in enumerate(rows, start=1):
        period = detect_period(row)
        for key, value in row.items():
            if key in {"ts_code", "symbol", "name", "stock_code", "ann_date", "f_ann_date", "end_date", "trade_date", "report_type", "comp_type"}:
                continue
            if not is_number(value):
                continue
            metric_hash = short_hash(hash_json([source_evidence_id, row_index, key, period, value]), 8)
            candidates.append(
                {
                    "metric_candidate_id": f"metric_{safe_slug(api_name)}_{stock_code}_{period}_{safe_slug(key)}_{metric_hash}",
                    "source_evidence_id": source_evidence_id,
                    "source_name": source_name,
                    "source_type": "structured_financial_data",
                    "entity_type": "company",
                    "entity_id": company_id,
                    "segment_id": "",
                    "company_id": company_id,
                    "stock_code": stock_code,
                    "metric_name": key,
                    "metric_category": api_name,
                    "period": period,
                    "period_type": "unknown",
                    "value": value,
                    "unit": unit,
                    "currency": "",
                    "original_value_text": value,
                    "original_unit_text": unit,
                    "table_id": f"{source_name}_{api_name}",
                    "page_no_or_section": "",
                    "calculation_method": "raw_adapter_snapshot_no_recalculation",
                    "is_estimate": "false",
                    "is_reported": "true",
                    "confidence": "medium",
                    "review_status": "draft",
                    "promote_to_metric_id": "",
                    "created_at": created_at,
                    "notes": f"Metric-only candidate generated from structured snapshot; api_params_hash={api_params_hash}; not business exposure evidence.",
                }
            )
    return candidates


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    stock_code = normalize_stock_code(args.stock_code)
    as_of_date = args.as_of_date or utc_now_iso()[:10]
    publish_date = args.publish_date or as_of_date
    params = {
        "source_name": args.source_name,
        "api_name": args.api_name,
        "stock_code": stock_code,
        "as_of_date": as_of_date,
        "fields": args.fields,
        "input_csv": args.input_csv,
        "input_json": args.input_json,
    }
    api_hash = hash_json(params)
    stem = f"{safe_slug(args.source_name)}_{safe_slug(args.api_name)}_{stock_code}_{as_of_date}_{short_hash(api_hash, 8)}"

    if args.input_csv:
        input_path = Path(args.input_csv)
        raw_path = repo_root / "data" / "raw" / "market_data" / f"{stem}.csv"
        raw_status, file_hash = immutable_copy_file(input_path, raw_path)
        rows = load_rows_from_csv(input_path)
        file_format = "csv"
    elif args.input_json:
        input_path = Path(args.input_json)
        raw_path = repo_root / "data" / "raw" / "market_data" / f"{stem}.json"
        raw_status, file_hash = immutable_copy_file(input_path, raw_path)
        raw_payload = json.loads(input_path.read_text(encoding="utf-8"))
        rows = raw_payload if isinstance(raw_payload, list) else raw_payload.get("rows", [])
        rows = [{str(k): str(v) for k, v in row.items()} for row in rows]
        file_format = "json"
    else:
        raise SystemExit("Provide --input-csv or --input-json for the first offline-capable implementation.")

    processed_path = repo_root / "data" / "processed" / "normalized" / f"{stem}.csv"
    write_normalized_csv(processed_path, rows)

    ev_id = evidence_id(
        source_type="structured_financial_data",
        entity=stock_code,
        date_value=publish_date,
        hash_value=api_hash,
    )
    manifest_row = {
        "evidence_id": ev_id,
        "source_type": "structured_financial_data",
        "source_name": args.source_name,
        "source_group": "structured_api",
        "title": f"{args.source_name} {args.api_name} snapshot for {stock_code}",
        "publisher": args.source_name,
        "publish_date": publish_date,
        "retrieved_at": utc_now_iso(),
        "ingested_at": utc_now_iso(),
        "as_of_date": as_of_date,
        "entity_type": "company",
        "entity_id": args.company_id,
        "segment_id": "",
        "company_id": args.company_id,
        "stock_code": stock_code,
        "source_url": "",
        "raw_file_path": repo_rel(raw_path, repo_root),
        "raw_archive_policy": "immutable",
        "file_hash": file_hash,
        "content_hash": file_hash,
        "api_params_hash": api_hash,
        "processed_text_path": "",
        "processed_table_path": repo_rel(processed_path, repo_root),
        "page_map_path": "",
        "page_count": "",
        "language": "zh-CN",
        "file_format": file_format,
        "ingest_mode": "structured_api_pull",
        "reliability_rank": "B",
        "material_claim_allowed": "metric_only",
        "allowed_claim_types": "metric_snapshot",
        "license_note": args.license_note,
        "stale_after": "90d",
        "status": "active",
        "parse_status": "snapshot_normalized",
        "candidate_status": "metric_candidates_generated",
        "review_status": "draft",
        "previous_evidence_id": "",
        "superseded_by": "",
        "notes": f"raw_status={raw_status}; structured snapshot is metric-only.",
    }
    manifest_path = repo_root / "data" / "manifests" / "evidence_manifest.csv"
    write_csv_rows(manifest_path, EVIDENCE_FIELDNAMES, [manifest_row])

    metric_rows = metric_candidates_from_rows(
        rows=rows,
        source_evidence_id=ev_id,
        source_name=args.source_name,
        stock_code=stock_code,
        company_id=args.company_id,
        api_name=args.api_name,
        api_params_hash=api_hash,
        unit=args.unit,
    )
    metric_path = repo_root / "data" / "manifests" / "metrics_draft.csv"
    write_csv_rows(metric_path, METRIC_CANDIDATE_FIELDNAMES, metric_rows)

    run_id = f"ingest_structured_{stock_code}_{safe_slug(args.api_name)}_{short_hash(api_hash, 6)}"
    log_row = {
        "run_id": run_id,
        "ingest_mode": "structured_api_pull",
        "started_at": manifest_row["retrieved_at"],
        "finished_at": utc_now_iso(),
        "result": "SUCCESS",
        "stock_code": stock_code,
        "source_name": args.source_name,
        "source_type": "structured_financial_data",
        "api_name": args.api_name,
        "manifest_rows_created": "1",
        "manifest_rows_updated": "0",
        "metric_candidates": str(len(metric_rows)),
        "claim_candidates": "0",
        "issues": "",
        "notes": "offline-capable structured snapshot ingest",
    }
    write_csv_rows(repo_root / "data" / "manifests" / "ingest_runs.csv", INGEST_RUN_FIELDNAMES, [log_row])
    write_json(repo_root / "data" / "processed" / "logs" / f"{ev_id}__ingest_log.json", log_row)
    print(json.dumps({"evidence_id": ev_id, "metric_candidates": len(metric_rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
