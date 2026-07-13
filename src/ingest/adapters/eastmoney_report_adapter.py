from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import ProxyHandler, build_opener

from evidence_io import (
    EVIDENCE_FIELDNAMES,
    INGEST_RUN_FIELDNAMES,
    METRIC_CANDIDATE_FIELDNAMES,
    evidence_id,
    hash_json,
    immutable_copy_or_write_bytes,
    normalize_stock_code,
    read_csv_dicts,
    repo_rel,
    safe_slug,
    short_hash,
    utc_now_iso,
    write_csv_rows,
    write_json,
)
from http_acquisition import (
    HttpAcquisitionError,
    HttpRequestSpec,
    PoliteHttpClient,
    RateLimitPolicy,
    RetryPolicy,
)


REPORT_API_URL = "https://reportapi.eastmoney.com/report/list"
NORMALIZED_FIELDS = [
    "stock_code",
    "stock_name",
    "title",
    "org_name",
    "publish_date",
    "info_code",
    "industry_name",
    "predict_this_year_eps",
    "predict_this_year_pe",
    "predict_next_year_eps",
    "predict_next_year_pe",
    "predict_next_two_year_eps",
    "predict_next_two_year_pe",
]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive Eastmoney research-report metadata.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--stock-code", required=True)
    parser.add_argument("--company-id", default="")
    parser.add_argument("--company-name", default="")
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--begin-date", default="")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--fixture-json", default="")
    parser.add_argument("--mode", choices=["fixture", "dry-run", "live"], default="")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--proxy-mode", choices=["auto", "inherit", "direct"], default="auto")
    parser.add_argument("--readout-output", default="")
    return parser.parse_args(argv)


def _query_url(args: argparse.Namespace) -> str:
    params = {
        "pageNo": "1",
        "pageSize": str(max(1, min(args.page_size, 100))),
        "code": normalize_stock_code(args.stock_code),
        "industryCode": "*",
        "industry": "*",
        "rating": "*",
        "ratingChange": "*",
        "beginTime": args.begin_date or f"{int(args.as_of_date[:4]) - 1}-01-01",
        "endTime": args.end_date or args.as_of_date,
        "fields": "",
        "qType": "0",
    }
    return f"{REPORT_API_URL}?{urlencode(params)}"


def _decode_payload(body: bytes) -> dict[str, Any]:
    text = body.decode("utf-8-sig").strip()
    if not text.startswith("{"):
        match = re.match(r"^[^(]+\((.*)\)\s*;?\s*$", text, flags=re.DOTALL)
        if not match:
            raise ValueError("Eastmoney reportapi response is neither JSON nor JSONP")
        text = match.group(1)
    payload = json.loads(text)
    if not isinstance(payload, dict) or not isinstance(payload.get("data", []), list):
        raise ValueError("Eastmoney reportapi payload lacks a data list")
    return payload


def _fetch_live(args: argparse.Namespace, url: str) -> tuple[bytes, str, int, int]:
    def request(proxy_mode: str) -> tuple[bytes, int, int]:
        opener = build_opener(ProxyHandler({})) if proxy_mode == "direct" else build_opener()
        client = PoliteHttpClient(
            opener=opener,
            retry_policy=RetryPolicy(max_attempts=3),
            rate_limit_policy=RateLimitPolicy(min_interval_seconds=0.8, serial_only=True),
        )
        response = client.request(
            HttpRequestSpec(
                url=url,
                source_name="eastmoney_push2",
                capability="research_metadata",
                timeout_seconds=20,
                referer="https://data.eastmoney.com/report/",
            )
        )
        return response.body, response.status, response.attempts

    if args.proxy_mode in {"inherit", "direct"}:
        body, status, attempts = request(args.proxy_mode)
        return body, args.proxy_mode, status, attempts
    try:
        body, status, attempts = request("inherit")
        return body, "inherit", status, attempts
    except HttpAcquisitionError as exc:
        # A source-specific direct fallback is permitted only for transport
        # failures.  HTTP permission/contract responses are not bypassed.
        if exc.status is not None:
            raise
        body, status, attempts = request("direct")
        return body, "direct_fallback", status, attempts


def _normalize_rows(payload: Mapping[str, Any], stock_code: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in payload.get("data", []):
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "stock_code": stock_code,
                "stock_name": str(item.get("stockName") or ""),
                "title": str(item.get("title") or ""),
                "org_name": str(item.get("orgSName") or item.get("orgName") or ""),
                "publish_date": str(item.get("publishDate") or "")[:10],
                "info_code": str(item.get("infoCode") or ""),
                "industry_name": str(item.get("indvInduName") or item.get("industryName") or ""),
                "predict_this_year_eps": str(item.get("predictThisYearEps") or ""),
                "predict_this_year_pe": str(item.get("predictThisYearPe") or ""),
                "predict_next_year_eps": str(item.get("predictNextYearEps") or ""),
                "predict_next_year_pe": str(item.get("predictNextYearPe") or ""),
                "predict_next_two_year_eps": str(item.get("predictNextTwoYearEps") or ""),
                "predict_next_two_year_pe": str(item.get("predictNextTwoYearPe") or ""),
            }
        )
    return rows


def _write_normalized(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=NORMALIZED_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _estimate_metrics(
    rows: list[dict[str, str]], *, evidence_id_value: str, company_id: str, stock_code: str
) -> list[dict[str, str]]:
    metrics: list[dict[str, str]] = []
    mappings = [
        (0, "predict_this_year_eps", "analyst_eps_estimate", "CNY_per_share"),
        (0, "predict_this_year_pe", "analyst_pe_estimate", "multiple"),
        (1, "predict_next_year_eps", "analyst_eps_estimate", "CNY_per_share"),
        (1, "predict_next_year_pe", "analyst_pe_estimate", "multiple"),
        (2, "predict_next_two_year_eps", "analyst_eps_estimate", "CNY_per_share"),
        (2, "predict_next_two_year_pe", "analyst_pe_estimate", "multiple"),
    ]
    created_at = utc_now_iso()
    for row in rows:
        try:
            publish_year = int(row["publish_date"][:4])
        except (TypeError, ValueError):
            continue
        for offset, source_field, metric_name, unit in mappings:
            value = row.get(source_field, "").strip()
            if not value:
                continue
            period = str(publish_year + offset)
            identity = [evidence_id_value, row.get("info_code"), metric_name, period, value]
            metrics.append(
                {
                    "metric_candidate_id": (
                        f"metric_company_{safe_slug(company_id or stock_code)}_"
                        f"{safe_slug(metric_name)}_{safe_slug(period)}_"
                        f"{short_hash(hash_json(identity), 8)}"
                    ),
                    "source_evidence_id": evidence_id_value,
                    "source_name": "eastmoney_push2",
                    "source_type": "third_party_research",
                    "entity_type": "company",
                    "entity_id": company_id,
                    "segment_id": "",
                    "company_id": company_id,
                    "stock_code": stock_code,
                    "metric_name": metric_name,
                    "metric_category": "research_report_metadata",
                    "period": period,
                    "period_type": "annual",
                    "value": value,
                    "unit": unit,
                    "currency": "CNY" if metric_name == "analyst_eps_estimate" else "",
                    "original_value_text": value,
                    "original_unit_text": unit,
                    "table_id": row.get("info_code", ""),
                    "page_no_or_section": "reportapi metadata",
                    "calculation_method": "raw_broker_report_metadata_field_mapping",
                    "is_estimate": "true",
                    "is_reported": "false",
                    "confidence": "low",
                    "review_status": "draft",
                    "promote_to_metric_id": "",
                    "created_at": created_at,
                    "notes": (
                        f"Single-broker estimate from {row.get('org_name')}; not issuer guidance, "
                        "not a verified consensus, and not trading advice."
                    ),
                }
            )
    return metrics


def _append_unique(path: Path, fields: list[str], rows: list[dict[str, str]], key: str) -> int:
    existing = {row.get(key, "") for row in read_csv_dicts(path)}
    fresh = [row for row in rows if row.get(key, "") not in existing]
    return write_csv_rows(path, fields, fresh)


def ingest(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(args.repo_root).resolve()
    stock_code = normalize_stock_code(args.stock_code)
    url = _query_url(args)
    mode = args.mode or ("fixture" if args.fixture_json else "live")
    if mode == "fixture":
        body = Path(args.fixture_json).read_bytes()
        proxy_route = "fixture"
        http_status = 200
        attempts = 0
    else:
        body, proxy_route, http_status, attempts = _fetch_live(args, url)
    payload = _decode_payload(body)
    rows = _normalize_rows(payload, stock_code)
    body_hash = hash_json(payload)
    ev_id = evidence_id(
        source_type="third_party_research",
        entity=stock_code,
        date_value=args.as_of_date,
        hash_value=body_hash,
    )
    raw_path = (
        repo_root
        / "data/raw/market_data"
        / f"eastmoney_report_metadata_{stock_code}_{args.as_of_date}_{short_hash(body_hash, 8)}.json"
    )
    raw_status, file_hash = immutable_copy_or_write_bytes(
        raw_path, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    )
    normalized_path = (
        repo_root
        / "data/processed/normalized"
        / f"eastmoney_report_metadata_{stock_code}_{args.as_of_date}_{short_hash(body_hash, 8)}.csv"
    )
    _write_normalized(normalized_path, rows)
    now = utc_now_iso()
    api_params_hash = hash_json(
        {
            "source_name": "eastmoney_push2",
            "capability": "research_metadata",
            "stock_code": stock_code,
            "begin_date": args.begin_date,
            "end_date": args.end_date,
            "page_size": args.page_size,
        }
    )
    manifest_row = {
        "evidence_id": ev_id,
        "source_type": "third_party_research",
        "source_name": "eastmoney_push2",
        "source_group": "market_signal_adapter",
        "title": f"Eastmoney brokerage research metadata snapshot for {stock_code}",
        "publisher": "Eastmoney",
        "publish_date": args.as_of_date,
        "retrieved_at": now,
        "ingested_at": now,
        "as_of_date": args.as_of_date,
        "entity_type": "company",
        "entity_id": args.company_id,
        "segment_id": "",
        "company_id": args.company_id,
        "stock_code": stock_code,
        "source_url": url,
        "raw_file_path": repo_rel(raw_path, repo_root),
        "raw_archive_policy": "snapshot_archived",
        "file_hash": file_hash,
        "content_hash": body_hash,
        "api_params_hash": api_params_hash,
        "processed_text_path": "",
        "processed_table_path": repo_rel(normalized_path, repo_root),
        "page_map_path": "",
        "page_count": "",
        "language": "zh-CN",
        "file_format": "json",
        "ingest_mode": "structured_api_pull",
        "reliability_rank": "C",
        "material_claim_allowed": "false",
        "allowed_claim_types": "analyst_view;estimate",
        "license_note": "Eastmoney public report metadata; terms apply; metadata and estimate context only",
        "stale_after": "30d",
        "status": "active",
        "parse_status": "parsed",
        "candidate_status": "generated" if rows else "not_generated",
        "review_status": "draft",
        "previous_evidence_id": "",
        "superseded_by": "",
        "notes": (
            f"raw_status={raw_status}; proxy_route={proxy_route}; report titles and per-broker estimates "
            "are analyst context only and do not authorize rating or trading advice."
        ),
    }
    manifest_path = repo_root / "data/manifests/evidence_manifest.csv"
    manifest_created = _append_unique(
        manifest_path, EVIDENCE_FIELDNAMES, [manifest_row], "evidence_id"
    )
    metric_rows = _estimate_metrics(
        rows, evidence_id_value=ev_id, company_id=args.company_id, stock_code=stock_code
    )
    metric_created = _append_unique(
        repo_root / "data/manifests/metrics_draft.csv",
        METRIC_CANDIDATE_FIELDNAMES,
        metric_rows,
        "metric_candidate_id",
    )
    run_id = f"ingest_eastmoney_report_{stock_code}_{short_hash(body_hash, 6)}"
    run_row = {
        "run_id": run_id,
        "ingest_mode": "structured_api_pull",
        "started_at": now,
        "finished_at": utc_now_iso(),
        "result": "SUCCESS",
        "stock_code": stock_code,
        "source_name": "eastmoney_push2",
        "source_type": "third_party_research",
        "api_name": "reportapi_metadata",
        "manifest_rows_created": str(manifest_created),
        "manifest_rows_updated": "0",
        "metric_candidates": str(metric_created),
        "claim_candidates": "0",
        "issues": "",
        "notes": f"analyst_view_only; proxy_route={proxy_route}; http_status={http_status}",
    }
    _append_unique(
        repo_root / "data/manifests/ingest_runs.csv",
        INGEST_RUN_FIELDNAMES,
        [run_row],
        "run_id",
    )
    write_json(repo_root / "data/processed/logs" / f"{ev_id}__ingest_log.json", run_row)
    result = {
        "result": "SUCCESS",
        "evidence_id": ev_id,
        "rows": len(rows),
        "hits": int(payload.get("hits") or len(rows)),
        "metric_candidates": metric_created,
        "proxy_route": proxy_route,
        "http_status": http_status,
        "attempts": attempts,
        "raw_file_path": manifest_row["raw_file_path"],
        "processed_table_path": manifest_row["processed_table_path"],
    }
    if args.readout_output:
        write_json(Path(args.readout_output), result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    mode = args.mode or ("fixture" if args.fixture_json else "live")
    if mode == "dry-run":
        print(json.dumps({"result": "BLOCKED", "reason": "dry_run", "url": _query_url(args)}))
        return 0
    if mode == "live" and not args.allow_network:
        print(json.dumps({"result": "BLOCKED", "reason": "live mode requires --allow-network"}))
        return 0
    result = ingest(args)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
