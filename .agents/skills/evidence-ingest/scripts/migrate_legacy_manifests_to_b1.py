#!/usr/bin/env python3
"""Migrate legacy P1 manifest/draft CSVs to the B1 evidence-ingest schema."""
from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

MANIFEST_FIELDS = [
    "evidence_id",
    "source_type",
    "source_name",
    "source_group",
    "title",
    "publisher",
    "publish_date",
    "retrieved_at",
    "ingested_at",
    "as_of_date",
    "entity_type",
    "entity_id",
    "segment_id",
    "company_id",
    "stock_code",
    "source_url",
    "raw_file_path",
    "raw_archive_policy",
    "file_hash",
    "content_hash",
    "api_params_hash",
    "processed_text_path",
    "processed_table_path",
    "page_map_path",
    "page_count",
    "language",
    "file_format",
    "ingest_mode",
    "reliability_rank",
    "material_claim_allowed",
    "allowed_claim_types",
    "license_note",
    "stale_after",
    "status",
    "parse_status",
    "candidate_status",
    "review_status",
    "previous_evidence_id",
    "superseded_by",
    "notes",
]

CLAIM_FIELDS = [
    "claim_candidate_id",
    "evidence_id",
    "source_type",
    "source_name",
    "reliability_rank",
    "entity_type",
    "entity_id",
    "segment_id",
    "company_id",
    "stock_code",
    "claim_text",
    "claim_type",
    "claim_scope",
    "quote_or_excerpt",
    "page_no_or_section",
    "table_id",
    "confidence",
    "materiality",
    "support_level",
    "needs_review_reason",
    "review_status",
    "promote_to_claim_id",
    "created_at",
    "notes",
]

METRIC_FIELDS = [
    "metric_candidate_id",
    "source_evidence_id",
    "source_name",
    "source_type",
    "entity_type",
    "entity_id",
    "segment_id",
    "company_id",
    "stock_code",
    "metric_name",
    "metric_category",
    "period",
    "period_type",
    "value",
    "unit",
    "currency",
    "original_value_text",
    "original_unit_text",
    "table_id",
    "page_no_or_section",
    "calculation_method",
    "is_estimate",
    "is_reported",
    "confidence",
    "review_status",
    "promote_to_metric_id",
    "created_at",
    "notes",
]

CLUE_FIELDS = [
    "clue_id",
    "evidence_id",
    "source_name",
    "source_type",
    "entity_type",
    "entity_id",
    "clue_text",
    "reliability_rank",
    "needs_verification_with",
    "created_at",
    "review_status",
    "notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(fh)]


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fields} for row in rows])


def sha256_file(repo: Path, rel_path: str) -> str:
    path = repo / rel_path
    if not rel_path or not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def stock_code_from_entity(entity_id: str) -> str:
    parts = entity_id.split("_")
    code = parts[1] if len(parts) > 1 and parts[0] == "cn" else ""
    if not code or len(code) != 6 or not code.isdigit():
        return ""
    suffix = "SH" if code.startswith("6") else "SZ"
    return f"{code}.{suffix}"


def metric_category(metric_name: str, evidence_id: str) -> str:
    if "income" in evidence_id:
        return "income_statement"
    if "fina_indicator" in evidence_id:
        return "financial_indicator"
    if "cashflow" in evidence_id:
        return "cash_flow"
    if "balancesheet" in evidence_id:
        return "balance_sheet"
    if metric_name in {"stock_basic", "list_status", "industry"}:
        return "security_reference"
    return "structured_snapshot"


def period_type(period: str) -> str:
    if period.endswith("1231"):
        return "annual"
    if len(period) == 8 and period[-4:] in {"0331", "0630", "0930"}:
        return "quarterly"
    return "as_reported"


def source_for_legacy(row: dict[str, str]) -> dict[str, str]:
    evidence_id = row.get("evidence_id", "")
    old_type = row.get("source_type", "")
    source_url = row.get("source_url", "")

    if evidence_id.startswith("policy_") or old_type == "policy":
        return {
            "source_type": "policy_document",
            "source_name": "policy_document",
            "source_group": "regulator_policy",
            "reliability_rank": "B",
            "allowed_claim_types": "fact;inference",
            "material_claim_allowed": "false",
            "raw_archive_policy": "evidence_card_only",
            "ingest_mode": "web_page_snapshot",
            "file_format": "html",
        }
    if evidence_id.startswith("industry_report_") or old_type == "industry_report":
        return {
            "source_type": "third_party_research",
            "source_name": "industry_report",
            "source_group": "third_party_analysis",
            "reliability_rank": "B",
            "allowed_claim_types": "fact;analyst_view;estimate;inference;clue",
            "material_claim_allowed": "false",
            "raw_archive_policy": "evidence_card_only",
            "ingest_mode": "url_file",
            "file_format": "pdf",
        }
    if old_type == "annual_report":
        return {
            "source_type": "annual_report",
            "source_name": "sse" if "sse.com" in source_url or "szse.cn" in source_url else "cninfo",
            "source_group": "official_disclosure",
            "reliability_rank": "A",
            "allowed_claim_types": "fact;metric_statement;management_comment",
            "material_claim_allowed": "false",
            "raw_archive_policy": "evidence_card_only",
            "ingest_mode": "url_file",
            "file_format": "pdf",
        }
    if evidence_id.startswith("market_data_tushare_probe_"):
        return {
            "source_type": "structured_market_data",
            "source_name": "tushare",
            "source_group": "structured_database",
            "reliability_rank": "D",
            "allowed_claim_types": "clue",
            "material_claim_allowed": "false",
            "raw_archive_policy": "snapshot_archived",
            "ingest_mode": "structured_api_pull",
            "file_format": "txt",
        }
    if evidence_id.startswith("market_data_tushare_stock_basic_"):
        return {
            "source_type": "structured_market_data",
            "source_name": "tushare",
            "source_group": "structured_database",
            "reliability_rank": "B",
            "allowed_claim_types": "metric_statement",
            "material_claim_allowed": "metric_only",
            "raw_archive_policy": "snapshot_archived",
            "ingest_mode": "structured_api_pull",
            "file_format": "csv",
        }
    if evidence_id.startswith("market_data_tushare_"):
        return {
            "source_type": "structured_financial_data",
            "source_name": "tushare",
            "source_group": "structured_database",
            "reliability_rank": "B",
            "allowed_claim_types": "metric_statement",
            "material_claim_allowed": "metric_only",
            "raw_archive_policy": "snapshot_archived",
            "ingest_mode": "structured_api_pull",
            "file_format": "csv",
        }
    return {
        "source_type": "unknown_source",
        "source_name": "unknown_source",
        "source_group": "user_uploaded",
        "reliability_rank": "unknown",
        "allowed_claim_types": "clue",
        "material_claim_allowed": "false",
        "raw_archive_policy": "metadata_only",
        "ingest_mode": "manual_file",
        "file_format": "unknown",
    }


def processed_table_for(evidence_id: str) -> str:
    table_names = {
        "market_data_tushare_probe_20260701_8bbf20": "tushare_probe_2026-07-01.csv",
        "market_data_tushare_stock_basic_20260701_a6d9f2": "tushare_stock_basic_ai_server_liquid_cooling_2026-07-01.csv",
        "market_data_tushare_income_selected_stocks_20260701_f1c8b2": "tushare_income_selected_stocks_2026-07-01.csv",
        "market_data_tushare_fina_indicator_selected_stocks_20260701_c3e4a9": "tushare_fina_indicator_selected_stocks_2026-07-01.csv",
        "market_data_tushare_cashflow_selected_stocks_20260701_d5b6c1": "tushare_cashflow_selected_stocks_2026-07-01.csv",
        "market_data_tushare_balancesheet_selected_stocks_20260701_a8f0d7": "tushare_balancesheet_selected_stocks_2026-07-01.csv",
    }
    table = table_names.get(evidence_id, "")
    return f"data/processed/tables/{table}" if table else ""


def migrate_manifest(repo: Path, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    migrated = []
    for row in rows:
        source = source_for_legacy(row)
        evidence_id = row["evidence_id"]
        raw_file_path = row.get("raw_file_path", "")
        processed_text_path = row.get("processed_text_path", "")
        processed_table_path = row.get("processed_table_path", "") or processed_table_for(evidence_id)
        file_hash = sha256_file(repo, raw_file_path) or row.get("file_hash", "")
        content_hash = sha256_file(repo, processed_text_path) or sha256_file(repo, processed_table_path) or file_hash
        status = "superseded" if row.get("status") == "superseded" else "active"
        parse_status = "failed" if evidence_id.startswith("market_data_tushare_probe_") else "parsed"
        candidate_status = "not_allowed" if evidence_id.startswith("market_data_tushare_probe_") else "generated"
        review_status = "blocked" if evidence_id.startswith("market_data_tushare_probe_") else "reviewed"
        as_of_date = row.get("publish_date", "") if source["ingest_mode"] == "structured_api_pull" else ""
        notes = []
        if row.get("notes"):
            notes.append(row["notes"])
        notes.append(f"legacy_archive_policy={row.get('archive_policy', '')}")
        if source["raw_archive_policy"] == "evidence_card_only":
            notes.append("TODO: archive original raw source before using as material claim support")
        if source["ingest_mode"] == "structured_api_pull":
            notes.append("metric_only structured snapshot; does not prove business exposure")
            if not evidence_id.startswith("market_data_tushare_probe_"):
                notes.append("TODO: legacy row lacks original API params hash; snapshot is anchored by file/content hash")
        if evidence_id.startswith("market_data_tushare_probe_"):
            notes.append("diagnostic failed/superseded probe; not research evidence")

        migrated.append({
            "evidence_id": evidence_id,
            **source,
            "title": row.get("title", ""),
            "publisher": row.get("publisher", ""),
            "publish_date": row.get("publish_date", ""),
            "retrieved_at": row.get("retrieved_at", ""),
            "ingested_at": row.get("ingested_at", ""),
            "as_of_date": as_of_date,
            "entity_type": "market" if source["ingest_mode"] == "structured_api_pull" else "",
            "entity_id": "tushare" if source["ingest_mode"] == "structured_api_pull" else "",
            "segment_id": "ai_server_liquid_cooling" if "ai_server_liquid_cooling" in (processed_text_path + row.get("title", "")) else "",
            "company_id": "",
            "stock_code": "",
            "source_url": row.get("source_url", ""),
            "raw_file_path": raw_file_path,
            "file_hash": file_hash,
            "content_hash": content_hash,
            "api_params_hash": "",
            "processed_text_path": processed_text_path,
            "processed_table_path": processed_table_path,
            "page_map_path": "",
            "page_count": row.get("page_count", ""),
            "language": "zh-CN",
            "license_note": row.get("license_note", "") or "legacy migration note required",
            "stale_after": row.get("stale_after", ""),
            "status": status,
            "parse_status": parse_status,
            "candidate_status": candidate_status,
            "review_status": review_status,
            "previous_evidence_id": "",
            "superseded_by": "market_data_tushare_stock_basic_20260701_a6d9f2" if evidence_id.startswith("market_data_tushare_probe_") else "",
            "notes": "; ".join(notes),
        })
    return migrated


def migrate_claims(rows: list[dict[str, str]], manifest: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    migrated = []
    for row in rows:
        evidence_id = row["evidence_id"]
        ev = manifest[evidence_id]
        claim_type = row.get("claim_type", "")
        claim_scope = row.get("entity_type", "")
        support_level = "draft_evidence"
        needs_review = "manual review required before promotion"
        materiality = "medium"
        notes = row.get("notes", "")

        if evidence_id.startswith("market_data_tushare_probe_"):
            claim_type = "clue"
            claim_scope = "diagnostic_clue_only"
            support_level = "clue_only"
            needs_review = "D-level diagnostic probe cannot support material claims"
            materiality = "low"
            notes = f"{notes}; TODO: keep as diagnostic lineage only; do not promote as fact".strip("; ")
        elif evidence_id.startswith("market_data_tushare_"):
            claim_type = "metric_statement"
            claim_scope = "metric_only_structured_snapshot"
            support_level = "structured_metric_snapshot"
            needs_review = "structured data snapshot is metric-only and cannot prove business exposure"
            materiality = "medium"
            notes = f"{notes}; metric_only; not business-exposure evidence".strip("; ")
        elif claim_type == "inference":
            claim_scope = "evidence_bounded_inference"
            support_level = "requires_quality_review"
            needs_review = "inference requires quality/manual review before promotion"

        entity_type = row.get("entity_type", "")
        entity_id = row.get("entity_id", "")
        company_id = entity_id if entity_type == "company" else ""
        segment_id = entity_id if entity_type == "segment" else ""
        migrated.append({
            "claim_candidate_id": row.get("claim_id", ""),
            "evidence_id": evidence_id,
            "source_type": ev.get("source_type", ""),
            "source_name": ev.get("source_name", ""),
            "reliability_rank": ev.get("reliability_rank", ""),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "segment_id": segment_id,
            "company_id": company_id,
            "stock_code": stock_code_from_entity(entity_id),
            "claim_text": row.get("claim_text", ""),
            "claim_type": claim_type,
            "claim_scope": claim_scope,
            "quote_or_excerpt": row.get("quote_or_excerpt", ""),
            "page_no_or_section": row.get("page_no", ""),
            "table_id": "structured_snapshot" if evidence_id.startswith("market_data_tushare_") else "",
            "confidence": row.get("confidence", ""),
            "materiality": materiality,
            "support_level": support_level,
            "needs_review_reason": needs_review,
            "review_status": "draft",
            "promote_to_claim_id": "",
            "created_at": "2026-07-01T00:00:00Z",
            "notes": notes,
        })
    return migrated


def migrate_metrics(rows: list[dict[str, str]], manifest: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    migrated = []
    for row in rows:
        evidence_id = row["source_evidence_id"]
        ev = manifest[evidence_id]
        entity_id = row.get("entity_id", "")
        unit = row.get("unit", "")
        migrated.append({
            "metric_candidate_id": row.get("metric_id", ""),
            "source_evidence_id": evidence_id,
            "source_name": ev.get("source_name", ""),
            "source_type": ev.get("source_type", ""),
            "entity_type": row.get("entity_type", ""),
            "entity_id": entity_id,
            "segment_id": "",
            "company_id": entity_id if row.get("entity_type") == "company" else "",
            "stock_code": stock_code_from_entity(entity_id),
            "metric_name": row.get("metric_name", ""),
            "metric_category": metric_category(row.get("metric_name", ""), evidence_id),
            "period": row.get("period", ""),
            "period_type": period_type(row.get("period", "")),
            "value": row.get("value", ""),
            "unit": unit,
            "currency": "CNY" if unit.startswith("CNY") else "",
            "original_value_text": row.get("value", ""),
            "original_unit_text": unit,
            "table_id": "tushare_snapshot",
            "page_no_or_section": "csv",
            "calculation_method": row.get("calculation_method", ""),
            "is_estimate": row.get("is_estimate", "false"),
            "is_reported": "false" if row.get("is_estimate", "").lower() == "true" else "true",
            "confidence": row.get("confidence", ""),
            "review_status": "draft",
            "promote_to_metric_id": "",
            "created_at": row.get("created_at", ""),
            "notes": f"{row.get('notes', '')}; metric_only; does not prove business exposure".strip("; "),
        })
    return migrated


def clue_rows_from_claims(claims: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "clue_id": f"clue_{claim['claim_candidate_id'].replace('claim_', '')}",
            "evidence_id": claim["evidence_id"],
            "source_name": claim["source_name"],
            "source_type": claim["source_type"],
            "entity_type": claim["entity_type"],
            "entity_id": claim["entity_id"],
            "clue_text": claim["claim_text"],
            "reliability_rank": claim["reliability_rank"],
            "needs_verification_with": "official_disclosure_or_successful_structured_snapshot",
            "created_at": claim["created_at"],
            "review_status": "draft",
            "notes": "Diagnostic clue only; do not use as material claim.",
        }
        for claim in claims
        if claim["claim_type"] == "clue" and claim["evidence_id"].startswith("market_data_tushare_probe_")
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy manifest and draft candidates to B1 schemas.")
    parser.add_argument("--repo", default=".", help="Repository root")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    manifest_path = repo / "data/manifests/evidence_manifest.csv"
    claims_path = repo / "data/manifests/claims_draft.csv"
    metrics_path = repo / "data/manifests/metrics_draft.csv"
    clue_path = repo / "data/manifests/clue_log.csv"

    manifest_rows = migrate_manifest(repo, read_csv(manifest_path))
    manifest_by_id = {row["evidence_id"]: row for row in manifest_rows}
    claim_rows = migrate_claims(read_csv(claims_path), manifest_by_id)
    metric_rows = migrate_metrics(read_csv(metrics_path), manifest_by_id)
    clue_rows = clue_rows_from_claims(claim_rows)

    write_csv(manifest_path, MANIFEST_FIELDS, manifest_rows)
    write_csv(claims_path, CLAIM_FIELDS, claim_rows)
    write_csv(metrics_path, METRIC_FIELDS, metric_rows)
    write_csv(clue_path, CLUE_FIELDS, clue_rows)

    print(f"MIGRATED evidence_manifest rows={len(manifest_rows)}")
    print(f"MIGRATED claims_draft rows={len(claim_rows)}")
    print(f"MIGRATED metrics_draft rows={len(metric_rows)}")
    print(f"MIGRATED clue_log rows={len(clue_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
