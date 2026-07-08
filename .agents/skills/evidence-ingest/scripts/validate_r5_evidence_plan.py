#!/usr/bin/env python3
"""Validate an R5 stock evidence snapshot plan."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: pip install pyyaml") from exc

REQUIRED_FAMILIES = {
    "official_filings",
    "structured_financial_metrics",
    "market_snapshot",
    "peer_snapshot",
    "industry_context_clues",
    "news_event_clues",
    "investor_relations",
}
CONTEXT_ONLY_FAMILIES = {"market_snapshot", "peer_snapshot", "industry_context_clues", "news_event_clues"}
REQUIRED_REQUEST_FIELDS = {
    "request_id",
    "evidence_need",
    "source_type",
    "source_rank",
    "as_of_date",
    "freshness_policy",
    "allowed_usage",
    "required_for_pack",
    "status",
}
REQUIRED_HANDOFF_FIELDS = {
    "evidence_manifest_path",
    "claim_candidates_path",
    "metric_candidates_path",
    "source_gap_register_path",
    "evidence_counts",
    "official_filing_requests",
    "structured_metric_requests",
    "market_snapshot_requests",
    "peer_snapshot_requests",
    "context_clue_requests",
    "missing_inputs",
}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("root YAML object must be a mapping")
    return data


def issue(severity: str, path: str, message: str) -> dict[str, str]:
    return {"severity": severity, "path": path, "message": message}


def _items(plan: dict[str, Any], family: str) -> list[dict[str, Any]]:
    value = (plan.get("evidence_requests") or {}).get(family)
    return value if isinstance(value, list) else []


def validate_plan(plan: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if plan.get("artifact_type") != "R5_stock_evidence_snapshot_plan":
        issues.append(issue("high", "artifact_type", "artifact_type must be R5_stock_evidence_snapshot_plan"))

    boundary = plan.get("implementation_boundary") or {}
    if boundary.get("no_live_api") is not True or boundary.get("plan_only") is not True:
        issues.append(issue("high", "implementation_boundary", "R5 evidence plan must be plan-only and no-live-API"))

    requests = plan.get("evidence_requests")
    if not isinstance(requests, dict):
        issues.append(issue("high", "evidence_requests", "evidence_requests must be a mapping"))
        return issues

    missing_families = sorted(REQUIRED_FAMILIES - set(requests))
    for family in missing_families:
        severity = "high" if family == "official_filings" else "medium"
        issues.append(issue(severity, f"evidence_requests.{family}", f"missing evidence family: {family}"))

    official_items = _items(plan, "official_filings")
    if not official_items:
        issues.append(issue("high", "evidence_requests.official_filings", "official filing requests are required"))
    if not any("annual" in str(item.get("evidence_need", "")).lower() for item in official_items):
        issues.append(issue("high", "evidence_requests.official_filings", "recent annual report request is required"))

    for family in REQUIRED_FAMILIES & set(requests):
        family_items = _items(plan, family)
        if not family_items:
            issues.append(issue("medium", f"evidence_requests.{family}", f"{family} must contain at least one request"))
            continue
        for idx, item in enumerate(family_items):
            path = f"evidence_requests.{family}[{idx}]"
            if not isinstance(item, dict):
                issues.append(issue("high", path, "evidence request must be a mapping"))
                continue
            for field in sorted(REQUIRED_REQUEST_FIELDS):
                if item.get(field) in (None, "", []):
                    issues.append(issue("high" if family == "official_filings" else "medium", f"{path}.{field}", f"missing field: {field}"))
            if item.get("status") == "collected" and not (item.get("evidence_id") or item.get("source_path")):
                issues.append(issue("high", f"{path}.evidence_id", "collected evidence requires evidence_id or source_path"))
            if item.get("status") in {"planned", "TODO", "MISSING"} and not (item.get("missing_reason") or item.get("next_action")):
                issues.append(issue("medium", f"{path}.missing_reason", "planned/TODO evidence requires missing_reason or next_action"))
            allowed_usage = set(item.get("allowed_usage") or [])
            if family in CONTEXT_ONLY_FAMILIES and allowed_usage & {"business_exposure", "business_exposure_after_review", "profit_exposure", "customer_exposure"}:
                issues.append(issue("high", f"{path}.allowed_usage", f"{family} cannot independently prove business exposure"))
            if family == "official_filings" and item.get("source_rank") not in {"A", "B"}:
                issues.append(issue("high", f"{path}.source_rank", "official filings should use A/B source rank"))

    handoff = plan.get("handoff_to_stock_deep_dive")
    if not isinstance(handoff, dict):
        issues.append(issue("high", "handoff_to_stock_deep_dive", "handoff_to_stock_deep_dive must be a mapping"))
    else:
        for field in sorted(REQUIRED_HANDOFF_FIELDS - set(handoff)):
            issues.append(issue("medium", f"handoff_to_stock_deep_dive.{field}", f"missing handoff field: {field}"))
    return issues


def decision_for(issues: list[dict[str, str]]) -> str:
    if any(item["severity"] == "high" for item in issues):
        return "blocked"
    if issues:
        return "accepted_with_todos"
    return "accepted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate R5 evidence snapshot plan YAML.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        issues = validate_plan(load_yaml(args.path))
    except Exception as exc:  # noqa: BLE001
        issues = [issue("high", str(args.path), f"failed to load YAML: {exc}")]
    decision = decision_for(issues)
    print(json.dumps({"decision": decision, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if decision in {"accepted", "accepted_with_todos"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
