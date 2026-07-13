from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import yaml

from src.ingest.evidence_io import (
    CLAIM_CANDIDATE_FIELDNAMES,
    EVIDENCE_FIELDNAMES,
    INGEST_RUN_FIELDNAMES,
    METRIC_CANDIDATE_FIELDNAMES,
    detect_period,
    evidence_id,
    hash_json,
    immutable_copy_or_write_bytes,
    is_number,
    normalize_stock_code,
    read_csv_dicts,
    repo_rel,
    safe_slug,
    short_hash,
    utc_now_iso,
    write_csv_rows,
    write_json,
)


@dataclass(frozen=True)
class EndpointContract:
    expected_fields: tuple[str, ...]
    metric_fields: Mapping[str, str] = field(default_factory=dict)
    claim_fields: tuple[str, ...] = ()
    claim_type: str = ""
    claim_boundary: str = "metric_only"
    empty_result_allowed: bool = False


@dataclass(frozen=True)
class AdapterSpec:
    adapter_id: str
    source_name: str
    source_group: str
    source_type: str
    publisher: str
    reliability_rank: str
    material_claim_allowed: str
    allowed_claim_types: str
    default_endpoint_hint: str
    endpoints: Mapping[str, EndpointContract]
    raw_bucket: str = "market_data"
    stale_after: str = "30d"
    license_note: str = "Public endpoint snapshot; source terms apply; internal research evidence only"


@dataclass(frozen=True)
class FetchResult:
    raw_payload: Any
    rows: list[dict[str, Any]]
    source_url: str
    http_status: int = 200
    attempts: int = 1
    transport: str = "live"
    notes: str = ""


LiveFetcher = Callable[[argparse.Namespace], FetchResult]


def standard_parser(description: str, default_endpoint_hint: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--stock-code", required=True)
    parser.add_argument("--company-id", default="")
    parser.add_argument("--company-name", default="")
    parser.add_argument("--workflow-id", default="wf_20260703_stock_first_002837_invic")
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--endpoint-hint", default=default_endpoint_hint)
    parser.add_argument("--begin-date", default="")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--page-size", type=int, default=30)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--industry-code", default="*")
    parser.add_argument("--keyword", default="")
    parser.add_argument("--mode", choices=["fixture", "dry-run", "live"], default="live")
    parser.add_argument("--fixture-json", default="")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--receipt-output", default="")
    return parser


def _append_unique(path: Path, fields: list[str], rows: list[dict[str, Any]], key: str) -> int:
    existing = {row.get(key, "") for row in read_csv_dicts(path)}
    fresh = [row for row in rows if str(row.get(key, "")) not in existing]
    return write_csv_rows(path, fields, fresh)


def _raw_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8") + b"\n"


def _normalized_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, Mapping)]
    if isinstance(payload, Mapping):
        raw_rows = payload.get("rows")
        if isinstance(raw_rows, list):
            return [dict(item) for item in raw_rows if isinstance(item, Mapping)]
        return [dict(payload)]
    raise ValueError("fixture/live payload must be a mapping or list of mappings")


def _write_normalized(
    path: Path,
    rows: list[dict[str, Any]],
    fallback_fields: Sequence[str] = (),
) -> list[str]:
    fields = sorted({str(key) for row in rows for key in row})
    if not fields:
        fields = sorted(set(fallback_fields) | {"empty_result"})
        rows = [{"empty_result": "true"}]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})
    return fields


def _metric_candidates(
    *,
    rows: list[dict[str, Any]],
    contract: EndpointContract,
    spec: AdapterSpec,
    evidence_id_value: str,
    company_id: str,
    stock_code: str,
    created_at: str,
) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for row_index, row in enumerate(rows):
        period = detect_period({str(k): str(v) for k, v in row.items()})
        for field_name, unit in contract.metric_fields.items():
            value = row.get(field_name)
            if value is None or str(value).strip() == "" or not is_number(str(value)):
                continue
            identity = [evidence_id_value, row_index, field_name, period, str(value)]
            is_estimate = contract.claim_boundary in {"estimate_only", "analyst_view_only"}
            candidates.append(
                {
                    "metric_candidate_id": (
                        f"metric_company_{safe_slug(company_id or stock_code)}_"
                        f"{safe_slug(field_name)}_{safe_slug(period)}_{short_hash(hash_json(identity), 8)}"
                    ),
                    "source_evidence_id": evidence_id_value,
                    "source_name": spec.source_name,
                    "source_type": spec.source_type,
                    "entity_type": "company",
                    "entity_id": company_id,
                    "segment_id": "",
                    "company_id": company_id,
                    "stock_code": stock_code,
                    "metric_name": field_name,
                    "metric_category": spec.adapter_id,
                    "period": period,
                    "period_type": "snapshot" if period == "UNKNOWN" else "reported_or_observed",
                    "value": str(value),
                    "unit": unit,
                    "currency": "CNY" if unit in {"CNY", "CNY_per_share"} else "",
                    "original_value_text": str(value),
                    "original_unit_text": unit,
                    "table_id": f"row_{row_index + 1}",
                    "page_no_or_section": "adapter normalized snapshot",
                    "calculation_method": "source_field_mapping_no_research_inference",
                    "is_estimate": str(is_estimate).lower(),
                    "is_reported": str(not is_estimate).lower(),
                    "confidence": "medium" if spec.reliability_rank in {"A", "B"} else "low",
                    "review_status": "draft",
                    "promote_to_metric_id": "",
                    "created_at": created_at,
                    "notes": f"claim_boundary={contract.claim_boundary}; no business-exposure inference",
                }
            )
    return candidates


def _claim_candidates(
    *,
    rows: list[dict[str, Any]],
    contract: EndpointContract,
    spec: AdapterSpec,
    evidence_id_value: str,
    company_id: str,
    stock_code: str,
    created_at: str,
) -> list[dict[str, str]]:
    if not contract.claim_type or spec.reliability_rank == "D":
        return []
    candidates: list[dict[str, str]] = []
    for row_index, row in enumerate(rows):
        for field_name in contract.claim_fields:
            value = str(row.get(field_name, "")).strip()
            if not value:
                continue
            identity = [evidence_id_value, row_index, field_name, value]
            candidates.append(
                {
                    "claim_candidate_id": (
                        f"claim_candidate_{safe_slug(company_id or stock_code)}_"
                        f"{safe_slug(contract.claim_type)}_{short_hash(hash_json(identity), 10)}"
                    ),
                    "evidence_id": evidence_id_value,
                    "source_type": spec.source_type,
                    "source_name": spec.source_name,
                    "reliability_rank": spec.reliability_rank,
                    "entity_type": "company",
                    "entity_id": company_id,
                    "segment_id": "",
                    "company_id": company_id,
                    "stock_code": stock_code,
                    "claim_text": value,
                    "claim_type": contract.claim_type,
                    "claim_scope": "source_specific_context",
                    "quote_or_excerpt": value[:500],
                    "page_no_or_section": f"normalized row {row_index + 1} field {field_name}",
                    "table_id": f"row_{row_index + 1}",
                    "confidence": "medium" if spec.reliability_rank in {"A", "B"} else "low",
                    "materiality": "context",
                    "support_level": "single_source_draft",
                    "needs_review_reason": f"claim_boundary={contract.claim_boundary}",
                    "review_status": "draft",
                    "promote_to_claim_id": "",
                    "created_at": created_at,
                    "notes": "Candidate only; not a verified material fact and not trading advice.",
                }
            )
    return candidates


def _load_fixture(path: str) -> FetchResult:
    if not path:
        raise ValueError("fixture mode requires --fixture-json")
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = _normalized_rows(payload)
    return FetchResult(
        raw_payload=payload,
        rows=rows,
        source_url=f"fixture://{Path(path).name}",
        http_status=200,
        attempts=0,
        transport="fixture",
    )


def execute_standard_adapter(
    argv: Sequence[str] | None,
    *,
    spec: AdapterSpec,
    live_fetcher: LiveFetcher,
    description: str,
) -> tuple[int, dict[str, Any]]:
    parser = standard_parser(description, spec.default_endpoint_hint)
    args = parser.parse_args(argv)
    endpoint_hint = str(args.endpoint_hint)
    contract = spec.endpoints.get(endpoint_hint)
    if contract is None:
        return 2, {"decision": "needs_fix", "reason": f"unsupported endpoint hint: {endpoint_hint}"}
    if args.mode == "dry-run":
        return 0, {
            "decision": "planned",
            "adapter_id": spec.adapter_id,
            "source_name": spec.source_name,
            "endpoint_hint": endpoint_hint,
        }
    if args.mode == "live" and not args.allow_network:
        return 2, {"decision": "needs_fix", "reason": "live mode requires --allow-network"}

    repo_root = Path(args.repo_root).resolve()
    stock_code = normalize_stock_code(args.stock_code)
    try:
        fetched = _load_fixture(args.fixture_json) if args.mode == "fixture" else live_fetcher(args)
    except Exception as exc:
        failure = {
            "schema_version": 1,
            "decision": "needs_fix",
            "adapter_id": spec.adapter_id,
            "source_name": spec.source_name,
            "endpoint_hint": endpoint_hint,
            "mode": args.mode,
            "workflow_id": args.workflow_id,
            "stock_code": normalize_stock_code(args.stock_code),
            "as_of_date": args.as_of_date,
            "claim_boundary": contract.claim_boundary,
            "failure_class": type(exc).__name__,
            "failure_message": str(exc),
            "checks": {
                "fixture_verified": False,
                "live_smoke_verified": False,
                "raw_archive_verified": False,
                "manifest_write_verified": False,
                "schema_fingerprint_verified": False,
                "claim_boundary_verified": bool(contract.claim_boundary),
            },
        }
        if args.receipt_output:
            receipt_path = Path(args.receipt_output)
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(
                yaml.safe_dump(failure, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            failure["receipt_path"] = str(receipt_path)
        return 1, failure
    rows = [dict(item) for item in fetched.rows]
    body = _raw_bytes(fetched.raw_payload)
    body_hash = hash_json(fetched.raw_payload)
    stem = (
        f"{safe_slug(spec.adapter_id)}_{safe_slug(endpoint_hint)}_{stock_code}_"
        f"{args.as_of_date}_{short_hash(body_hash, 8)}"
    )
    raw_path = repo_root / "data" / "raw" / spec.raw_bucket / f"{stem}.json"
    raw_status, file_hash = immutable_copy_or_write_bytes(raw_path, body)
    normalized_path = repo_root / "data" / "processed" / "normalized" / f"{stem}.csv"
    observed_fields = _write_normalized(
        normalized_path,
        rows,
        contract.expected_fields if contract.empty_result_allowed else (),
    )
    missing_fields = sorted(set(contract.expected_fields) - set(observed_fields))
    schema_verified = not missing_fields and (bool(rows) or contract.empty_result_allowed)
    now = utc_now_iso()
    ev_id = evidence_id(
        source_type=spec.source_type,
        entity=stock_code,
        date_value=args.as_of_date,
        hash_value=body_hash,
    )
    api_params_hash = hash_json(
        {
            "adapter_id": spec.adapter_id,
            "source_name": spec.source_name,
            "endpoint_hint": endpoint_hint,
            "stock_code": stock_code,
            "as_of_date": args.as_of_date,
            "begin_date": args.begin_date,
            "end_date": args.end_date,
            "page_size": args.page_size,
            "limit": args.limit,
            "industry_code": args.industry_code,
            "keyword": args.keyword,
        }
    )
    manifest_row = {
        "evidence_id": ev_id,
        "source_type": spec.source_type,
        "source_name": spec.source_name,
        "source_group": spec.source_group,
        "title": f"{spec.publisher} {endpoint_hint} snapshot for {stock_code}",
        "publisher": spec.publisher,
        "publish_date": args.as_of_date,
        "retrieved_at": now,
        "ingested_at": now,
        "as_of_date": args.as_of_date,
        "entity_type": "company",
        "entity_id": args.company_id,
        "segment_id": "",
        "company_id": args.company_id,
        "stock_code": stock_code,
        "source_url": fetched.source_url,
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
        "ingest_mode": "structured_api_pull" if args.mode == "live" else "local_fixture",
        "reliability_rank": spec.reliability_rank,
        "material_claim_allowed": spec.material_claim_allowed,
        "allowed_claim_types": spec.allowed_claim_types,
        "license_note": spec.license_note,
        "stale_after": spec.stale_after,
        "status": "active" if schema_verified else "failed",
        "parse_status": "parsed" if schema_verified else "partial",
        "candidate_status": (
            "not_allowed"
            if spec.reliability_rank == "D"
            else ("generated" if rows else "not_generated")
        ),
        "review_status": "blocked" if spec.reliability_rank == "D" else "draft",
        "previous_evidence_id": "",
        "superseded_by": "",
        "notes": (
            f"raw_status={raw_status}; transport={fetched.transport}; "
            f"claim_boundary={contract.claim_boundary}; {fetched.notes}"
        ).strip(),
    }
    manifest_created = _append_unique(
        repo_root / "data" / "manifests" / "evidence_manifest.csv",
        EVIDENCE_FIELDNAMES,
        [manifest_row],
        "evidence_id",
    )
    metric_rows = _metric_candidates(
        rows=rows,
        contract=contract,
        spec=spec,
        evidence_id_value=ev_id,
        company_id=args.company_id,
        stock_code=stock_code,
        created_at=now,
    )
    claim_rows = _claim_candidates(
        rows=rows,
        contract=contract,
        spec=spec,
        evidence_id_value=ev_id,
        company_id=args.company_id,
        stock_code=stock_code,
        created_at=now,
    )
    metric_created = _append_unique(
        repo_root / "data" / "manifests" / "metrics_draft.csv",
        METRIC_CANDIDATE_FIELDNAMES,
        metric_rows,
        "metric_candidate_id",
    )
    claim_created = _append_unique(
        repo_root / "data" / "manifests" / "claims_draft.csv",
        CLAIM_CANDIDATE_FIELDNAMES,
        claim_rows,
        "claim_candidate_id",
    )
    run_id = f"r5_bundle8r_{safe_slug(spec.adapter_id)}_{safe_slug(endpoint_hint)}_{short_hash(body_hash, 8)}"
    run_row = {
        "run_id": run_id,
        "ingest_mode": manifest_row["ingest_mode"],
        "started_at": now,
        "finished_at": utc_now_iso(),
        "result": "SUCCESS" if schema_verified else "PARTIAL_SUCCESS",
        "stock_code": stock_code,
        "source_name": spec.source_name,
        "source_type": spec.source_type,
        "api_name": endpoint_hint,
        "manifest_rows_created": str(manifest_created),
        "manifest_rows_updated": "0",
        "metric_candidates": str(metric_created),
        "claim_candidates": str(claim_created),
        "issues": ";".join(f"missing_field:{item}" for item in missing_fields),
        "notes": f"claim_boundary={contract.claim_boundary}; transport={fetched.transport}",
    }
    _append_unique(
        repo_root / "data" / "manifests" / "ingest_runs.csv",
        INGEST_RUN_FIELDNAMES,
        [run_row],
        "run_id",
    )
    log_path = repo_root / "data" / "processed" / "logs" / f"{ev_id}__ingest_log.json"
    write_json(log_path, run_row)
    receipt = {
        "schema_version": 1,
        "decision": "pass" if schema_verified else "needs_fix",
        "adapter_id": spec.adapter_id,
        "source_name": spec.source_name,
        "endpoint_hint": endpoint_hint,
        "mode": args.mode,
        "workflow_id": args.workflow_id,
        "stock_code": stock_code,
        "as_of_date": args.as_of_date,
        "run_id": run_id,
        "evidence_id": ev_id,
        "claim_boundary": contract.claim_boundary,
        "checks": {
            "fixture_verified": args.mode == "fixture" and schema_verified,
            "live_smoke_verified": args.mode == "live" and schema_verified,
            "raw_archive_verified": raw_path.is_file(),
            "manifest_write_verified": bool(ev_id) and (
                manifest_created == 1
                or any(row.get("evidence_id") == ev_id for row in read_csv_dicts(repo_root / "data/manifests/evidence_manifest.csv"))
            ),
            "schema_fingerprint_verified": schema_verified,
            "claim_boundary_verified": bool(contract.claim_boundary),
        },
        "raw_file_path": manifest_row["raw_file_path"],
        "processed_table_path": manifest_row["processed_table_path"],
        "ingest_log_path": repo_rel(log_path, repo_root),
        "source_url": fetched.source_url,
        "http_status": fetched.http_status,
        "attempts": fetched.attempts,
        "row_count": len(rows),
        "metric_candidates_created": metric_created,
        "claim_candidates_created": claim_created,
        "observed_fields": observed_fields,
        "expected_fields": list(contract.expected_fields),
        "missing_fields": missing_fields,
        "schema_fingerprint": hash_json(observed_fields),
        "notes": fetched.notes,
    }
    receipt_path = (
        Path(args.receipt_output)
        if args.receipt_output
        else repo_root / "reports" / "quality" / "adapter_receipts" / f"{stem}_{args.mode}.yaml"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(yaml.safe_dump(receipt, allow_unicode=True, sort_keys=False), encoding="utf-8")
    receipt["receipt_path"] = repo_rel(receipt_path, repo_root)
    return (0 if schema_verified else 1), receipt


def adapter_main(
    argv: Sequence[str] | None,
    *,
    spec: AdapterSpec,
    live_fetcher: LiveFetcher,
    description: str,
) -> int:
    code, result = execute_standard_adapter(
        argv,
        spec=spec,
        live_fetcher=live_fetcher,
        description=description,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return code
