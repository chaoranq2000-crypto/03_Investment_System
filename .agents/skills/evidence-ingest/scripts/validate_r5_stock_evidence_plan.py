#!/usr/bin/env python3
"""Validate an R5 stock evidence plan."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: pip install pyyaml") from exc

REQUIRED_FAMILIES = [
    "official_filings",
    "structured_financial_data",
    "market_snapshot",
    "peer_snapshot",
    "industry_context",
    "news_event_clues",
    "investor_relations",
]
REQUEST_FIELDS = {"source_priority", "required_for_pack", "freshness_requirement", "fallback_if_missing"}
EXPECTED_ARTIFACTS = {"manifest_rows", "claim_candidates", "metric_candidates", "ingest_log"}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("root YAML object must be a mapping")
    return data


def issue(severity: str, path: str, message: str) -> dict[str, str]:
    return {"severity": severity, "path": path, "message": message}


def validate_plan(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if data.get("artifact_type") != "R5_stock_evidence_plan":
        issues.append(issue("high", "artifact_type", "artifact_type must be R5_stock_evidence_plan"))
    boundary = data.get("implementation_boundary") or {}
    if boundary.get("no_downloader_added") is not True or boundary.get("no_live_api") is not True:
        issues.append(issue("high", "implementation_boundary", "plan must not add downloader or live API"))

    policy = data.get("source_gap_policy") or {}
    if policy.get("missing_disclosure_token") != "MISSING_DISCLOSURE":
        issues.append(issue("high", "source_gap_policy.missing_disclosure_token", "missing disclosure must use MISSING_DISCLOSURE"))

    plan = data.get("evidence_plan")
    if not isinstance(plan, dict):
        return [*issues, issue("high", "evidence_plan", "evidence_plan must be a mapping")]

    priorities: dict[str, int] = {}
    for family in REQUIRED_FAMILIES:
        section = plan.get(family)
        if not isinstance(section, dict):
            issues.append(issue("high", f"evidence_plan.{family}", f"missing evidence family: {family}"))
            continue
        priority = section.get("source_priority")
        if not isinstance(priority, int):
            issues.append(issue("high", f"evidence_plan.{family}.source_priority", "source_priority must be integer"))
        else:
            priorities[family] = priority
        requests = section.get("requests")
        if not isinstance(requests, list) or not requests:
            issues.append(issue("high", f"evidence_plan.{family}.requests", "requests must be non-empty"))
            continue
        for idx, request in enumerate(requests):
            if not isinstance(request, dict):
                issues.append(issue("high", f"evidence_plan.{family}.requests[{idx}]", "request must be mapping"))
                continue
            for field in REQUEST_FIELDS - set(section):
                if not request.get(field):
                    issues.append(issue("high", f"evidence_plan.{family}.requests[{idx}].{field}", f"missing {field}"))
            if family == "official_filings" and request.get("fallback_if_missing") != "MISSING_DISCLOSURE":
                issues.append(issue("high", f"evidence_plan.{family}.requests[{idx}].fallback_if_missing", "missing official disclosure must be MISSING_DISCLOSURE"))

    official_priority = priorities.get("official_filings")
    for family in ["industry_context", "news_event_clues", "investor_relations"]:
        if official_priority is not None and priorities.get(family, 99) <= official_priority:
            issues.append(issue("high", f"evidence_plan.{family}.source_priority", "official disclosures must outrank third-party/context sources"))

    artifacts = data.get("expected_artifacts")
    if not isinstance(artifacts, dict):
        issues.append(issue("high", "expected_artifacts", "expected_artifacts must be a mapping"))
    else:
        for key in sorted(EXPECTED_ARTIFACTS):
            if artifacts.get(key) is not True:
                issues.append(issue("high", f"expected_artifacts.{key}", f"{key} must be true"))
    return issues


def decision_for(issues: list[dict[str, str]]) -> str:
    return "blocked" if any(item["severity"] == "high" for item in issues) else "accepted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate R5 stock evidence plan YAML.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        issues = validate_plan(load_yaml(args.path))
    except Exception as exc:  # noqa: BLE001
        issues = [issue("high", str(args.path), f"failed to load YAML: {exc}")]
    decision = decision_for(issues)
    print(json.dumps({"decision": decision, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if decision == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
