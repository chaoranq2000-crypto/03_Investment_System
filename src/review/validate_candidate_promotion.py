from __future__ import annotations

import csv
from pathlib import Path
from typing import Mapping


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def evidence_ids_from_manifest(path: Path) -> set[str]:
    return {row.get("evidence_id", "") for row in read_csv_dicts(path) if row.get("evidence_id")}


def validate_claim_candidate(row: Mapping[str, str], evidence_ids: set[str]) -> list[str]:
    issues: list[str] = []
    if row.get("evidence_id", "") not in evidence_ids:
        issues.append("missing_or_unknown_evidence_id")
    material = row.get("materiality") == "material" or row.get("claim_scope") in {
        "business_exposure",
        "financial_material",
    }
    if material and not row.get("quote_or_excerpt"):
        issues.append("material_claim_missing_quote")
    if material and not (row.get("page_no_or_section") or row.get("table_id")):
        issues.append("material_claim_missing_locator")
    if material and row.get("reliability_rank") == "D":
        issues.append("d_level_material_claim_blocked")
    if row.get("claim_type") in {"estimate", "inference"} and not row.get("notes"):
        issues.append("estimate_or_inference_needs_notes")
    return issues


def validate_metric_candidate(row: Mapping[str, str], evidence_ids: set[str]) -> list[str]:
    issues: list[str] = []
    if row.get("source_evidence_id", "") not in evidence_ids:
        issues.append("missing_or_unknown_source_evidence_id")
    for field in ("metric_name", "period", "value", "unit"):
        if not row.get(field):
            issues.append(f"missing_{field}")
    if row.get("is_estimate", "").lower() == "true" and "estimate" not in row.get("notes", "").lower():
        issues.append("estimate_metric_needs_note")
    return issues


def validate_candidates(
    *,
    claims_path: Path | None,
    metrics_path: Path | None,
    manifest_path: Path,
) -> dict[str, object]:
    evidence_ids = evidence_ids_from_manifest(manifest_path)
    claim_issues = []
    metric_issues = []
    for row in read_csv_dicts(claims_path) if claims_path else []:
        issues = validate_claim_candidate(row, evidence_ids)
        if issues:
            claim_issues.append({"candidate_id": row.get("claim_candidate_id", ""), "issues": issues})
    for row in read_csv_dicts(metrics_path) if metrics_path else []:
        issues = validate_metric_candidate(row, evidence_ids)
        if issues:
            metric_issues.append({"candidate_id": row.get("metric_candidate_id", ""), "issues": issues})
    return {
        "claim_issue_count": len(claim_issues),
        "metric_issue_count": len(metric_issues),
        "claim_issues": claim_issues,
        "metric_issues": metric_issues,
    }
