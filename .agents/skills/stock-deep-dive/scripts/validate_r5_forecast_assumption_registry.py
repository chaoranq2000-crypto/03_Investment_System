#!/usr/bin/env python3
"""Validate an R5 forecast assumption registry."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

FORBIDDEN = re.compile(r"买入|卖出|持有|建仓|减仓|仓位|目标价|保证收益|buy\s+rating|sell\s+rating|hold\s+rating|position\s+sizing", re.IGNORECASE)
STATUSES = {"pending", "reviewed", "explicitly_degraded_but_reviewed"}
CORE_DRIVERS = {"revenue_growth", "gross_margin", "opex", "net_profit", "eps"}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _issue(issue_id: str, severity: str, path: str, description: str) -> dict[str, str]:
    return {"issue_id": issue_id, "severity": severity, "path": path, "description": description}


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_text(item) for item in value)
    return value if isinstance(value, str) else ""


def validate_registry(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if data.get("artifact_type") != "R5_forecast_assumption_registry":
        issues.append(_issue("R5FAR-ROOT-001", "high", "artifact_type", "artifact_type must be R5_forecast_assumption_registry"))
    if data.get("no_live_api") is not True:
        issues.append(_issue("R5FAR-ROOT-002", "high", "no_live_api", "no_live_api must be true"))
    if data.get("review_status") not in STATUSES:
        issues.append(_issue("R5FAR-STATUS-001", "high", "review_status", "review_status is invalid"))
    if FORBIDDEN.search(_text(data)):
        issues.append(_issue("R5FAR-NOADV-001", "high", "registry", "direct trading language is forbidden"))
    assumptions = data.get("assumptions") or []
    if not isinstance(assumptions, list) or not assumptions:
        issues.append(_issue("R5FAR-ROW-000", "high", "assumptions", "assumptions must be a non-empty list"))
        return issues

    seen_drivers: set[str] = set()
    for idx, raw in enumerate(assumptions):
        path = f"assumptions[{idx}]"
        if not isinstance(raw, dict):
            issues.append(_issue("R5FAR-ROW-001", "high", path, "assumption row must be a mapping"))
            continue
        for field in ["assumption_id", "driver", "periods", "value", "unit", "allowed_usage", "review_status"]:
            if raw.get(field) in (None, "", []):
                issues.append(_issue("R5FAR-ROW-002", "medium", f"{path}.{field}", f"{field} is required"))
        for field in ["evidence_ids", "metric_ids"]:
            if field not in raw or raw.get(field) is None:
                issues.append(_issue("R5FAR-ROW-002", "medium", f"{path}.{field}", f"{field} is required"))
        driver = str(raw.get("driver", ""))
        if driver:
            seen_drivers.add(driver)
        status = raw.get("review_status")
        if status not in STATUSES:
            issues.append(_issue("R5FAR-ROW-003", "high", f"{path}.review_status", "review_status is invalid"))
        if status == "reviewed":
            if not (raw.get("evidence_ids") or raw.get("metric_ids")):
                issues.append(_issue("R5FAR-ANCHOR-001", "high", path, "reviewed assumptions require evidence_ids or accepted metric_ids"))
            if not raw.get("reviewer_note"):
                issues.append(_issue("R5FAR-REVIEW-001", "high", f"{path}.reviewer_note", "reviewed assumptions require reviewer_note"))
        if status == "pending" and raw.get("value") != "TODO_MODEL_INPUT" and not raw.get("missing_reason"):
            issues.append(_issue("R5FAR-TODO-001", "high", f"{path}.missing_reason", "pending assumptions require TODO_MODEL_INPUT or missing_reason"))
        if raw.get("allowed_usage") != "degraded_forecast_only" and status != "reviewed":
            issues.append(_issue("R5FAR-USAGE-001", "high", f"{path}.allowed_usage", "non-reviewed assumptions must be degraded_forecast_only"))

    missing = sorted(CORE_DRIVERS - seen_drivers)
    if missing:
        issues.append(_issue("R5FAR-CORE-001", "high", "assumptions", f"missing core forecast drivers: {', '.join(missing)}"))
    return issues


def derive_decision(data: dict[str, Any], issues: list[dict[str, str]]) -> str:
    if any(issue["severity"] == "high" for issue in issues):
        return "blocked"
    if data.get("review_status") == "reviewed":
        return "accepted"
    return "accepted_with_todos"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate R5 forecast assumption registry YAML.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_yaml(args.path)
        issues = validate_registry(data)
        decision = derive_decision(data, issues)
    except Exception as exc:  # noqa: BLE001
        decision = "blocked"
        issues = [_issue("R5FAR-LOAD-001", "high", str(args.path), f"ERROR: {exc}")]
    print(json.dumps({"decision": decision, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if decision in {"accepted", "accepted_with_todos"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
