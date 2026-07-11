#!/usr/bin/env python3
"""Build the fail-closed R5 Bundle 5.1 real-input inventory."""
from __future__ import annotations

import argparse
import csv
import importlib.util
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

CORE_INPUT_TYPES = (
    "business_disclosure",
    "market_snapshot",
    "peer_snapshot",
    "forecast_assumptions",
    "valuation_inputs",
)
OPTIONAL_INPUT_TYPES = ("sentiment_event_sources",)
ACCEPTED_STATUSES = {"accepted", "accepted_degraded"}
FORBIDDEN_ACCEPTED_TOKENS = {
    "TODO_MARKET_DATA",
    "TODO_PEER_DATA",
    "TODO_MODEL_INPUT",
    "TODO_SOURCE_REQUIRED",
    "MISSING_DISCLOSURE",
    "LOW_CONFIDENCE_CLUE_ONLY",
}
PLACEHOLDER_ORIGIN = re.compile(
    r"(?:^|[/_.\s-])(fixture|template|sample)(?:$|[/_.\s-])",
    re.IGNORECASE,
)
REGISTRY_TARGETS = {
    "business_disclosure": "R5_valuation_input_registry.yaml::business_line_split",
    "market_snapshot": "R5_market_peer_input_registry.yaml::market_inputs",
    "peer_snapshot": "R5_market_peer_input_registry.yaml::peer_inputs",
    "forecast_assumptions": "R5_forecast_assumption_registry.yaml",
    "valuation_inputs": "R5_valuation_input_registry.yaml",
    "sentiment_event_sources": "sentiment_event_pack_candidate",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"", "null", "none", "nan", "na", "n/a", "~"}
    return False


def _is_true(value: Any) -> bool:
    if value is True:
        return True
    return isinstance(value, str) and value.strip().lower() in {"true", "1", "yes", "y"}


def _as_list(value: Any) -> list[str]:
    if _is_missing(value):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if not _is_missing(item)]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[;,|]", value) if item.strip()]
    return [str(value)]


def _load_dropzone_module(repo_root: Path):
    path = repo_root / "scripts/validate_r5_reviewed_input_dropzone.py"
    spec = importlib.util.spec_from_file_location("r5_bundle5_dropzone_validator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load dropzone validator from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _dropzone_records(repo_root: Path, dropzone_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    module = _load_dropzone_module(repo_root)
    validation = module.validate_root(dropzone_root)
    records: list[dict[str, Any]] = []
    for path in module.iter_input_files(dropzone_root):
        relative = path.relative_to(dropzone_root).as_posix()
        try:
            rows = module.read_dropzone_file(path)
        except Exception:  # pragma: no cover - validator reports the load error
            continue
        for index, row in enumerate(rows):
            if isinstance(row, dict):
                records.append({**row, "_source_path": relative, "_row_index": index})
    return records, validation


def _matches_stock(row: dict[str, str], stock_code: str) -> bool:
    identity = " ".join(
        str(row.get(key, ""))
        for key in ("stock_code", "company_id", "entity_id", "evidence_id", "title", "raw_file_path")
    )
    return stock_code in identity


def _resolve_evidence_path(
    repo_root: Path,
    workflow_dir: Path,
    raw_path: str,
    manifest_scope: str,
) -> tuple[str | None, str]:
    if not raw_path:
        return None, "missing"
    candidates = [repo_root / raw_path]
    if manifest_scope == "workflow_local":
        candidates.append(workflow_dir / raw_path)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.relative_to(repo_root).as_posix(), "resolved"
    return raw_path.replace("\\", "/"), "missing"


def _evidence_rows(repo_root: Path, workflow_id: str, stock_code: str) -> list[dict[str, Any]]:
    workflow_dir = repo_root / "reports/workflow_runs" / workflow_id
    sources = (
        (repo_root / "data/manifests/evidence_manifest.csv", "global"),
        (workflow_dir / "evidence_manifest_delta.csv", "workflow_local"),
    )
    rows: list[dict[str, Any]] = []
    for path, scope in sources:
        for row in _load_csv(path):
            if not _matches_stock(row, stock_code):
                continue
            resolved_path, path_status = _resolve_evidence_path(
                repo_root,
                workflow_dir,
                str(row.get("raw_file_path") or ""),
                scope,
            )
            origin_text = " ".join(
                str(row.get(key) or "")
                for key in ("source_name", "title", "raw_file_path", "notes")
            )
            rows.append(
                {
                    **row,
                    "manifest_scope": scope,
                    "manifest_path": path.relative_to(repo_root).as_posix(),
                    "resolved_source_path": resolved_path,
                    "source_path_status": path_status,
                    "fixture_or_template_origin": bool(PLACEHOLDER_ORIGIN.search(origin_text)),
                }
            )
    return rows


def _queue_requests(workflow_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    queue = _load_yaml(workflow_dir / "R5_evidence_request_queue.yaml")
    requests = queue.get("requests")
    return (requests if isinstance(requests, list) else []), queue


def _review_ledger_summary(workflow_dir: Path) -> dict[str, int]:
    ledger = _load_yaml(workflow_dir / "R5_evidence_request_review_ledger.yaml")
    summary = ledger.get("summary")
    if not isinstance(summary, dict):
        return {"request_count": 0, "pending_count": 0, "accepted_count": 0}
    return {
        "request_count": int(summary.get("request_count") or 0),
        "pending_count": int(summary.get("pending_count") or 0),
        "accepted_count": int(summary.get("accepted_count") or 0),
    }


def _request_ids_for_type(input_type: str, requests: list[dict[str, Any]]) -> list[str]:
    selected: list[str] = []
    for request in requests:
        request_id = str(request.get("request_id") or "")
        gap_id = str(request.get("source_gap_id") or "").upper()
        source_type = str(request.get("source_type") or "")
        required = {str(item) for item in request.get("required_for_pack", [])}
        matches = False
        if input_type == "business_disclosure":
            matches = "GAP_BUSINESS" in gap_id or "GAP_EXPOSURE" in gap_id
        elif input_type == "market_snapshot":
            matches = source_type == "market_data_snapshot"
        elif input_type == "peer_snapshot":
            matches = source_type == "peer_snapshot"
        elif input_type == "forecast_assumptions":
            matches = "GAP_FORECAST" in gap_id or (
                source_type == "structured_financial_data" and "forecast_model_pack" in required
            )
        elif input_type == "valuation_inputs":
            matches = "GAP_VALUATION" in gap_id or "valuation_pack" in required
        elif input_type == "sentiment_event_sources":
            matches = source_type in {"news_or_event_source", "investor_relations", "industry_context_clues"}
        if matches and request_id:
            selected.append(request_id)
    return sorted(set(selected))


def _record_text(record: dict[str, Any]) -> str:
    return yaml.safe_dump(record, allow_unicode=True, sort_keys=True)


def _review_record(
    record: dict[str, Any],
    evidence_by_id: dict[str, list[dict[str, Any]]],
    workflow_id: str,
    stock_code: str,
) -> dict[str, Any]:
    review_status = str(record.get("review_status") or "missing")
    evidence_ids = _as_list(record.get("source_evidence_id") or record.get("source_evidence_ids"))
    missing_fields: list[str] = []
    conflicts: list[str] = []
    limitations = record.get("limitations")
    accepted_candidate = review_status in ACCEPTED_STATUSES
    if accepted_candidate:
        for field in (
            "input_id",
            "workflow_id",
            "stock_code",
            "input_type",
            "source_rank",
            "as_of_date",
            "reviewer",
            "reviewed_at",
            "capture_method",
            "limitations",
        ):
            if _is_missing(record.get(field)):
                missing_fields.append(field)
        if str(record.get("workflow_id") or "") != workflow_id:
            conflicts.append("workflow_id_mismatch")
        if str(record.get("stock_code") or "") != stock_code:
            conflicts.append("stock_code_mismatch")
        if _is_true(record.get("template_only")) or _is_true(record.get("not_evidence")):
            conflicts.append("template_or_not_evidence")
        if not _is_true(record.get("no_live_api")):
            conflicts.append("no_live_api_not_true")
        source_path = str(record.get("_source_path") or "")
        if PLACEHOLDER_ORIGIN.search(source_path):
            conflicts.append("fixture_template_or_sample_path")
        found_tokens = sorted(token for token in FORBIDDEN_ACCEPTED_TOKENS if token in _record_text(record))
        conflicts.extend(f"forbidden_token:{token}" for token in found_tokens)
        if not evidence_ids:
            missing_fields.append("source_evidence_id")
        for evidence_id in evidence_ids:
            matched = evidence_by_id.get(evidence_id, [])
            if not matched:
                conflicts.append(f"unresolved_evidence_id:{evidence_id}")
                continue
            if not any(item.get("source_path_status") == "resolved" for item in matched):
                conflicts.append(f"missing_physical_source:{evidence_id}")
            if any(item.get("fixture_or_template_origin") for item in matched):
                conflicts.append(f"fixture_evidence:{evidence_id}")
    accepted_valid = accepted_candidate and not missing_fields and not conflicts
    return {
        "input_id": record.get("input_id"),
        "source_path": record.get("_source_path"),
        "review_status": review_status,
        "source_evidence_ids": evidence_ids,
        "source_rank": record.get("source_rank"),
        "as_of_or_publication_date": record.get("as_of_date") or record.get("publication_date"),
        "freshness_status": record.get("freshness_status") or "unknown",
        "reviewer": record.get("reviewer"),
        "reviewed_at": record.get("reviewed_at"),
        "limitations": limitations,
        "missing_fields": sorted(set(missing_fields)),
        "conflicts": sorted(set(conflicts)),
        "accepted_valid": accepted_valid,
    }


def _evidence_candidates(evidence_rows: list[dict[str, Any]], input_type: str) -> list[dict[str, Any]]:
    if input_type != "business_disclosure":
        return []
    candidates: list[dict[str, Any]] = []
    for row in evidence_rows:
        if row.get("source_type") not in {"annual_report", "announcement", "official_disclosure"}:
            continue
        if row.get("fixture_or_template_origin"):
            continue
        candidates.append(
            {
                "evidence_id": row.get("evidence_id"),
                "title": row.get("title"),
                "source_rank": row.get("reliability_rank"),
                "review_status": row.get("review_status"),
                "publish_date": row.get("publish_date"),
                "file_hash": row.get("file_hash"),
                "source_path": row.get("resolved_source_path"),
                "source_path_status": row.get("source_path_status"),
                "manifest_scope": row.get("manifest_scope"),
                "candidate_only": True,
            }
        )
    return candidates


def _duplicate_hash_aliases(evidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evidence_rows:
        file_hash = str(row.get("file_hash") or "").lower()
        if file_hash:
            grouped[file_hash].append(row)
    aliases: list[dict[str, Any]] = []
    for file_hash, rows in sorted(grouped.items()):
        evidence_ids = sorted({str(row.get("evidence_id")) for row in rows if row.get("evidence_id")})
        if len(evidence_ids) < 2:
            continue
        aliases.append(
            {
                "file_hash": file_hash,
                "evidence_ids": evidence_ids,
                "physical_sources": sorted(
                    {str(row.get("resolved_source_path")) for row in rows if row.get("resolved_source_path")}
                ),
                "decision": "provenance_alias_not_independent_evidence",
            }
        )
    return aliases


def build_inventory(
    repo_root: Path,
    workflow_id: str,
    stock_code: str,
    dropzone_root: Path,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    if not dropzone_root.is_absolute():
        dropzone_root = repo_root / dropzone_root
    workflow_dir = repo_root / "reports/workflow_runs" / workflow_id
    records, validation = _dropzone_records(repo_root, dropzone_root)
    evidence_rows = _evidence_rows(repo_root, workflow_id, stock_code)
    evidence_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evidence_rows:
        evidence_id = str(row.get("evidence_id") or "")
        if evidence_id:
            evidence_by_id[evidence_id].append(row)
    requests, queue = _queue_requests(workflow_dir)

    items: list[dict[str, Any]] = []
    valid_core_types = 0
    for input_type in (*CORE_INPUT_TYPES, *OPTIONAL_INPUT_TYPES):
        type_records = [record for record in records if record.get("input_type") == input_type]
        reviewed_records = [
            _review_record(record, evidence_by_id, workflow_id, stock_code) for record in type_records
        ]
        valid_count = sum(1 for record in reviewed_records if record["accepted_valid"])
        required = input_type in CORE_INPUT_TYPES
        if required and valid_count > 0:
            valid_core_types += 1
        request_ids = _request_ids_for_type(input_type, requests)
        missing_fields = sorted(
            {
                field
                for record in reviewed_records
                for field in record.get("missing_fields", [])
            }
        )
        if not type_records:
            missing_fields = [
                "input_id",
                "physical_input_path",
                "review_status",
                "source_evidence_id",
                "source_rank",
                "as_of_or_publication_date",
                "reviewer",
                "reviewed_at",
                "limitations",
            ]
        items.append(
            {
                "input_type": input_type,
                "required": required,
                "record_count": len(type_records),
                "valid_accepted_count": valid_count,
                "status": "accepted" if valid_count else ("missing" if not type_records else "pending_or_invalid"),
                "records": reviewed_records,
                "evidence_candidates": _evidence_candidates(evidence_rows, input_type),
                "request_ids": request_ids,
                "candidate_registry_target": REGISTRY_TARGETS[input_type],
                "missing_fields": missing_fields,
                "blocking": required and valid_count == 0,
                "blocking_reason": "missing_valid_accepted_reviewed_input" if required and valid_count == 0 else None,
            }
        )

    stop_condition = validation.get("record_count", 0) == 0
    core_complete = valid_core_types == len(CORE_INPUT_TYPES)
    status = "ready_for_later_promotion_card" if core_complete else "blocked_source_gapped"
    return {
        "schema_version": "r5_bundle5_real_input_inventory_v0.1",
        "artifact_type": "R5_bundle5_real_input_inventory",
        "workflow_id": workflow_id,
        "stock_code": stock_code,
        "dropzone_root": dropzone_root.relative_to(repo_root).as_posix(),
        "status": status,
        "generated_from_local_files_only": True,
        "dropzone_validation": {
            "status": validation.get("status"),
            "checked_file_count": len(validation.get("checked_files", [])),
            "record_count": validation.get("record_count", 0),
            "accepted_count": validation.get("accepted_count", 0),
            "accepted_degraded_count": validation.get("accepted_degraded_count", 0),
            "failed_count": validation.get("failed_count", 0),
            "interpretation": (
                "empty_valid_but_source_gapped"
                if validation.get("record_count", 0) == 0 and validation.get("status") == "pass"
                else "records_present_review_inventory_required"
            ),
        },
        "summary": {
            "required_core_input_type_count": len(CORE_INPUT_TYPES),
            "valid_accepted_core_input_type_count": valid_core_types,
            "missing_or_invalid_core_input_type_count": len(CORE_INPUT_TYPES) - valid_core_types,
            "source_request_count": int(queue.get("summary", {}).get("request_count") or len(requests)),
            "source_gap_count": int(queue.get("summary", {}).get("source_gap_count") or 0),
            "review_ledger": _review_ledger_summary(workflow_dir),
        },
        "items": items,
        "provenance_aliases": _duplicate_hash_aliases(evidence_rows),
        "quality_decision": {
            "g1_evidence_gate": "pass" if core_complete else "fail",
            "card_5_1_stop_condition_triggered": stop_condition,
            "card_5_2_allowed": core_complete and not stop_condition,
            "promotion_allowed": False,
            "sample_quality_report_allowed": False,
            "p2_allowed": False,
        },
        "limitations": [
            "Parsing or validator pass is not review acceptance.",
            "Evidence candidates are not reviewed-input records.",
            "Templates, fixtures, sample reports and TODO placeholders are excluded from accepted coverage.",
            "Card 5.1 never authorizes canonical registry promotion.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the R5 Bundle 5.1 real-input inventory.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--stock-code", required=True)
    parser.add_argument("--dropzone-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    inventory = build_inventory(args.repo_root, args.workflow_id, args.stock_code, args.dropzone_root)
    output = args.output if args.output.is_absolute() else args.repo_root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(inventory, allow_unicode=True, sort_keys=False), encoding="utf-8")
    summary = inventory["summary"]
    print(
        "r5_bundle5_real_input_inventory "
        f"status={inventory['status']} "
        f"core={summary['valid_accepted_core_input_type_count']}/{summary['required_core_input_type_count']} "
        f"records={inventory['dropzone_validation']['record_count']} "
        "promotion_allowed=false sample_quality=false p2=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
