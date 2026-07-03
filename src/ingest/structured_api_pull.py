from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

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


MARKET_APIS = {
    "daily",
    "daily_basic",
    "pro_bar",
    "query_history_k_data_plus",
    "query_stock_basic",
    "stock_basic",
}

SOURCE_DEFAULTS = {
    "local_fixture": {
        "source_group": "structured_database",
        "reliability_rank": "B",
        "token_env": "",
        "requires_token": False,
        "license_note": "local fixture for offline adapter validation",
    },
    "tushare": {
        "source_group": "structured_database",
        "reliability_rank": "B",
        "token_env": "TUSHARE_TOKEN",
        "requires_token": True,
        "license_note": "Tushare terms; verify permission before redistribution",
    },
    "baostock": {
        "source_group": "structured_database_fallback",
        "reliability_rank": "B",
        "token_env": "",
        "requires_token": False,
        "license_note": "Baostock terms; verify before redistribution",
    },
    "tencent_finance": {
        "source_group": "market_data_adapter",
        "reliability_rank": "C",
        "token_env": "",
        "requires_token": False,
        "license_note": "public HTTP market data; verify terms before redistribution",
    },
    "mootdx": {
        "source_group": "market_data_adapter",
        "reliability_rank": "C",
        "token_env": "",
        "requires_token": False,
        "license_note": "mootdx market data; verify terms before redistribution",
    },
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register a structured API/local fixture snapshot.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--plan", default="")
    parser.add_argument("--source-name", default="local_fixture")
    parser.add_argument("--api-name", default="")
    parser.add_argument("--stock-code", default="")
    parser.add_argument("--company-id", default="")
    parser.add_argument("--company-name", default="")
    parser.add_argument("--input-csv", default="")
    parser.add_argument("--input-json", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--publish-date", default="")
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--fields", default="")
    parser.add_argument("--unit", default="")
    parser.add_argument("--license-note", default="adapter terms; verify before redistribution")
    parser.add_argument("--manifest-path", default="")
    parser.add_argument("--metrics-path", default="")
    parser.add_argument("--ingest-runs-path", default="")
    parser.add_argument("--log-dir", default="")
    parser.add_argument("--raw-dir", default="")
    parser.add_argument("--normalized-dir", default="")
    parser.add_argument("--readout-output", default="")
    return parser.parse_args(argv)


def load_plan(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Plan must be a YAML mapping: {path}")
    return data


def _first_api_from_plan(plan: Mapping[str, Any], source_name: str) -> str:
    source_layers = plan.get("source_layers", {})
    if not isinstance(source_layers, Mapping):
        return ""
    structured = source_layers.get("structured_database", {})
    if not isinstance(structured, Mapping):
        return ""
    apis = structured.get("APIs", {})
    if isinstance(apis, Mapping):
        source_apis = apis.get(source_name, [])
        if isinstance(source_apis, list) and source_apis:
            return str(source_apis[0])
    return ""


def apply_plan_defaults(args: argparse.Namespace) -> argparse.Namespace:
    if not args.plan:
        return args

    plan = load_plan(Path(args.plan))
    obj = plan.get("object", {}) if isinstance(plan.get("object"), Mapping) else {}
    time_range = plan.get("time_range", {}) if isinstance(plan.get("time_range"), Mapping) else {}
    params = plan.get("params", {}) if isinstance(plan.get("params"), Mapping) else {}
    structured = {}
    source_layers = plan.get("source_layers", {})
    if isinstance(source_layers, Mapping):
        candidate = source_layers.get("structured_database", {})
        if isinstance(candidate, Mapping):
            structured = candidate

    if args.source_name == "local_fixture":
        args.source_name = str(structured.get("primary") or args.source_name)
    args.api_name = args.api_name or str(params.get("api_name") or _first_api_from_plan(plan, args.source_name))
    args.stock_code = args.stock_code or str(obj.get("stock_code") or "")
    args.company_id = args.company_id or str(obj.get("company_id") or "")
    args.company_name = args.company_name or str(obj.get("company_name") or "")
    args.as_of_date = args.as_of_date or str(time_range.get("as_of_date") or "")
    args.start_date = args.start_date or str(time_range.get("start_date") or params.get("start_date") or "")
    args.end_date = args.end_date or str(time_range.get("end_date") or params.get("end_date") or "")
    args.fields = args.fields or str(params.get("fields") or "")
    token_env = structured.get("token_env")
    if token_env and args.source_name == structured.get("primary"):
        defaults = SOURCE_DEFAULTS.setdefault(args.source_name, {})
        defaults["token_env"] = str(token_env)
        defaults["requires_token"] = True
    return args


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


def source_type_for_api(api_name: str) -> str:
    return "structured_market_data" if api_name in MARKET_APIS else "structured_financial_data"


def defaults_for_source(source_name: str) -> dict[str, Any]:
    return {
        "source_group": "structured_database",
        "reliability_rank": "B",
        "token_env": "",
        "requires_token": False,
        "license_note": "adapter terms; verify before redistribution",
        **SOURCE_DEFAULTS.get(source_name, {}),
    }


def metric_candidates_from_rows(
    *,
    rows: list[dict[str, str]],
    source_evidence_id: str,
    source_name: str,
    source_type: str = "structured_financial_data",
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
            if key in {
                "ts_code",
                "symbol",
                "name",
                "stock_code",
                "ann_date",
                "f_ann_date",
                "end_date",
                "trade_date",
                "report_type",
                "comp_type",
            }:
                continue
            if not is_number(value):
                continue
            metric_hash = short_hash(hash_json([source_evidence_id, row_index, key, period, value]), 8)
            candidates.append(
                {
                    "metric_candidate_id": f"metric_{safe_slug(api_name)}_{stock_code}_{period}_{safe_slug(key)}_{metric_hash}",
                    "source_evidence_id": source_evidence_id,
                    "source_name": source_name,
                    "source_type": source_type,
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


def build_api_params_hash(
    *,
    source_name: str,
    api_name: str,
    stock_code: str,
    as_of_date: str,
    start_date: str = "",
    end_date: str = "",
    fields: str = "",
    input_csv: str = "",
    input_json: str = "",
) -> str:
    return hash_json(
        {
            "source_name": source_name,
            "api_name": api_name,
            "stock_code": stock_code,
            "as_of_date": as_of_date,
            "start_date": start_date,
            "end_date": end_date,
            "fields": fields,
            "input_csv": input_csv,
            "input_json": input_json,
        }
    )


def output_path(repo_root: Path, override: str, default: Path) -> Path:
    if not override:
        return default
    path = Path(override)
    return path if path.is_absolute() else repo_root / path


def write_readout(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".md":
        lines = [
            "# Source Adapter Run Readout",
            "",
            f"run_id: {payload.get('run_id', '')}",
            f"source_name: {payload.get('source_name', '')}",
            f"api_name: {payload.get('api_name', '')}",
            f"result: {payload.get('result', '')}",
            f"adapter_status: {payload.get('adapter_status', '')}",
            "",
            "## Notes",
            "",
            f"- {payload.get('notes', '')}",
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    write_json(path, payload)


def dry_run_payload(args: argparse.Namespace, api_hash: str, stem: str) -> dict[str, object]:
    defaults = defaults_for_source(args.source_name)
    token_env = str(defaults.get("token_env") or "")
    token_present = bool(token_env and os.environ.get(token_env))
    result = "BLOCKED" if defaults.get("requires_token") and not token_present else "SUCCESS"
    return {
        "run_id": f"dry_run_{safe_slug(args.source_name)}_{safe_slug(args.api_name)}_{short_hash(api_hash, 6)}",
        "source_name": args.source_name,
        "api_name": args.api_name,
        "result": result,
        "adapter_status": "blocked" if result == "BLOCKED" else "offline_fixture_supported",
        "endpoint": f"{args.source_name}.{args.api_name}",
        "params": {
            "stock_code": args.stock_code,
            "start_date": args.start_date,
            "end_date": args.end_date,
            "as_of_date": args.as_of_date,
            "fields": args.fields,
            "token_env": token_env,
        },
        "api_params_hash": api_hash,
        "planned_outputs": {
            "raw_snapshot": f"data/raw/market_data/{stem}.csv|json",
            "normalized_table": f"data/processed/normalized/{stem}.csv",
            "manifest": args.manifest_path or "data/manifests/evidence_manifest.csv",
            "metric_candidates": args.metrics_path or "data/manifests/metrics_draft.csv",
        },
        "notes": "dry-run only; no network call was made and no API token value was stored",
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = apply_plan_defaults(parse_args(argv))
    repo_root = Path(args.repo_root).resolve()
    if not args.api_name:
        raise SystemExit("Provide --api-name or a plan with a structured database API.")
    if not args.stock_code:
        raise SystemExit("Provide --stock-code or a plan with object.stock_code.")
    stock_code = normalize_stock_code(args.stock_code)
    as_of_date = args.as_of_date or utc_now_iso()[:10]
    publish_date = args.publish_date or as_of_date
    source_type = source_type_for_api(args.api_name)
    source_defaults = defaults_for_source(args.source_name)
    source_group = str(source_defaults["source_group"])
    reliability_rank = str(source_defaults["reliability_rank"])
    license_note = args.license_note
    if license_note == "adapter terms; verify before redistribution":
        license_note = str(source_defaults["license_note"])
    api_hash = build_api_params_hash(
        source_name=args.source_name,
        api_name=args.api_name,
        stock_code=stock_code,
        as_of_date=as_of_date,
        start_date=args.start_date,
        end_date=args.end_date,
        fields=args.fields,
        input_csv=args.input_csv,
        input_json=args.input_json,
    )
    stem = f"{safe_slug(args.source_name)}_{safe_slug(args.api_name)}_{stock_code}_{as_of_date}_{short_hash(api_hash, 8)}"

    if args.dry_run:
        payload = dry_run_payload(args, api_hash, stem)
        if args.readout_output:
            write_readout(output_path(repo_root, args.readout_output, repo_root / "dry_run.json"), payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    raw_dir = output_path(repo_root, args.raw_dir, repo_root / "data" / "raw" / "market_data")
    if args.input_csv:
        input_path = Path(args.input_csv)
        raw_path = raw_dir / f"{stem}.csv"
        raw_status, file_hash = immutable_copy_file(input_path, raw_path)
        rows = load_rows_from_csv(input_path)
        file_format = "csv"
    elif args.input_json:
        input_path = Path(args.input_json)
        raw_path = raw_dir / f"{stem}.json"
        raw_status, file_hash = immutable_copy_file(input_path, raw_path)
        raw_payload = json.loads(input_path.read_text(encoding="utf-8"))
        rows = raw_payload if isinstance(raw_payload, list) else raw_payload.get("rows", [])
        rows = [{str(k): str(v) for k, v in row.items()} for row in rows]
        file_format = "json"
    else:
        raise SystemExit("Provide --input-csv or --input-json for the first offline-capable implementation.")

    normalized_dir = output_path(
        repo_root, args.normalized_dir, repo_root / "data" / "processed" / "normalized"
    )
    processed_path = normalized_dir / f"{stem}.csv"
    write_normalized_csv(processed_path, rows)

    ev_id = evidence_id(
        source_type=source_type,
        entity=stock_code,
        date_value=publish_date,
        hash_value=api_hash,
    )
    manifest_row = {
        "evidence_id": ev_id,
        "source_type": source_type,
        "source_name": args.source_name,
        "source_group": source_group,
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
        "raw_archive_policy": "snapshot_archived",
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
        "reliability_rank": reliability_rank,
        "material_claim_allowed": "metric_only",
        "allowed_claim_types": "metric_statement",
        "license_note": license_note,
        "stale_after": "90d",
        "status": "active",
        "parse_status": "parsed",
        "candidate_status": "generated",
        "review_status": "draft",
        "previous_evidence_id": "",
        "superseded_by": "",
        "notes": f"raw_status={raw_status}; structured snapshot is metric-only.",
    }
    metric_rows = metric_candidates_from_rows(
        rows=rows,
        source_evidence_id=ev_id,
        source_name=args.source_name,
        source_type=source_type,
        stock_code=stock_code,
        company_id=args.company_id,
        api_name=args.api_name,
        api_params_hash=api_hash,
        unit=args.unit,
    )
    if not metric_rows:
        manifest_row["candidate_status"] = "not_generated"

    manifest_path = output_path(
        repo_root,
        args.manifest_path,
        repo_root / "data" / "manifests" / "evidence_manifest.csv",
    )
    write_csv_rows(manifest_path, EVIDENCE_FIELDNAMES, [manifest_row])

    metric_path = output_path(
        repo_root, args.metrics_path, repo_root / "data" / "manifests" / "metrics_draft.csv"
    )
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
        "source_type": source_type,
        "api_name": args.api_name,
        "manifest_rows_created": "1",
        "manifest_rows_updated": "0",
        "metric_candidates": str(len(metric_rows)),
        "claim_candidates": "0",
        "issues": "",
        "notes": "offline-capable structured snapshot ingest",
    }
    ingest_runs_path = output_path(
        repo_root,
        args.ingest_runs_path,
        repo_root / "data" / "manifests" / "ingest_runs.csv",
    )
    write_csv_rows(ingest_runs_path, INGEST_RUN_FIELDNAMES, [log_row])
    log_dir = output_path(repo_root, args.log_dir, repo_root / "data" / "processed" / "logs")
    write_json(log_dir / f"{ev_id}__ingest_log.json", log_row)
    if args.readout_output:
        write_readout(
            output_path(repo_root, args.readout_output, repo_root / "source_adapter_readout.json"),
            {
                **log_row,
                "adapter_status": "offline_fixture_supported",
                "api_params_hash": api_hash,
                "evidence_id": ev_id,
                "raw_file_path": manifest_row["raw_file_path"],
                "processed_table_path": manifest_row["processed_table_path"],
            },
        )
    print(
        json.dumps(
            {
                "evidence_id": ev_id,
                "metric_candidates": len(metric_rows),
                "manifest_path": str(manifest_path),
                "metrics_path": str(metric_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
