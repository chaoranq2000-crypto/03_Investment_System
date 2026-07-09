#!/usr/bin/env python3
"""Validate an R5 reviewed evidence registry."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

FORBIDDEN = re.compile(
    r"买入|卖出|持有|仓位|目标价|保证收益|buy\s+rating|sell\s+rating|hold\s+rating|position\s+sizing|trading\s+instruction",
    re.IGNORECASE,
)
DATED_USAGE = {"market", "peer", "event", "sentiment", "valuation_context", "technical_context", "peer_context"}
STATUSES = {"planned", "needs_review", "reviewed"}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _issue(issue_id: str, severity: str, path: str, description: str) -> dict[str, str]:
    return {"issue_id": issue_id, "severity": severity, "path": path, "description": description}


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_text(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(_text(v) for v in value)
    return value if isinstance(value, str) else ""


def _records(data: dict[str, Any]) -> list[Any]:
    records = data.get("records", data.get("items", data.get("requests", [])))
    return records if isinstance(records, list) else []


def _uses_dated_context(row: dict[str, Any]) -> bool:
    source_type = str(row.get("source_type", "")).lower()
    usage = {str(item).lower() for item in row.get("allowed_usage", []) if item is not None}
    return any(token in source_type for token in ["market", "peer", "event", "sentiment"]) or bool(usage & DATED_USAGE)


def validate_registry(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if data.get("artifact_type") != "R5_reviewed_evidence_registry":
        issues.append(_issue("R5REV-ROOT-001", "high", "artifact_type", "artifact_type must be R5_reviewed_evidence_registry"))
    if data.get("no_live_api") is not True:
        issues.append(_issue("R5REV-ROOT-002", "high", "no_live_api", "no_live_api must be true"))
    for field in ["registry_id", "workflow_id", "stock_code"]:
        if not data.get(field):
            issues.append(_issue("R5REV-ROOT-003", "high", field, f"{field} is required"))

    records = _records(data)
    if not records:
        issues.append(_issue("R5REV-ROW-000", "high", "records", "records must be a non-empty list"))

    for idx, raw in enumerate(records):
        path = f"records[{idx}]"
        if not isinstance(raw, dict):
            issues.append(_issue("R5REV-ROW-001", "high", path, "record must be a mapping"))
            continue
        status = raw.get("review_status", raw.get("status"))
        if status not in STATUSES:
            issues.append(_issue("R5REV-ROW-002", "high", f"{path}.review_status", "review_status must be planned, needs_review, or reviewed"))
        for field in ["source_gap_id", "request_id", "source_type", "source_rank", "allowed_usage", "claim_scope", "metric_scope", "limitations"]:
            if raw.get(field) in (None, "", []):
                issues.append(_issue("R5REV-ROW-003", "medium", f"{path}.{field}", f"{field} is required"))
        if raw.get("no_live_api", data.get("no_live_api")) is not True:
            issues.append(_issue("R5REV-ROW-004", "high", f"{path}.no_live_api", "row no_live_api must be true"))
        if FORBIDDEN.search(_text(raw.get("allowed_usage", []))):
            issues.append(_issue("R5REV-NOADV-001", "high", f"{path}.allowed_usage", "allowed_usage contains direct trading language"))

        evidence_id = raw.get("evidence_id")
        if status == "reviewed":
            if not evidence_id:
                issues.append(_issue("R5REV-REVIEW-001", "high", f"{path}.evidence_id", "reviewed records require evidence_id"))
            if not raw.get("reviewer"):
                issues.append(_issue("R5REV-REVIEW-002", "high", f"{path}.reviewer", "reviewed records require reviewer"))
            if "TODO_SOURCE_REQUIRED" in _text(raw.get("limitations", [])):
                issues.append(_issue("R5REV-REVIEW-003", "high", f"{path}.limitations", "reviewed records cannot carry unresolved TODO_SOURCE_REQUIRED"))
            if _uses_dated_context(raw) and not raw.get("as_of_date"):
                issues.append(_issue("R5REV-DATE-001", "high", f"{path}.as_of_date", "reviewed market/peer/event/sentiment usage requires as_of_date"))
        elif not evidence_id and "TODO" not in _text(raw):
            issues.append(_issue("R5REV-TODO-001", "medium", path, "planned/needs_review records without evidence_id must remain visible TODO rows"))
    return issues


def derive_decision(issues: list[dict[str, str]], data: dict[str, Any]) -> str:
    if any(issue["severity"] == "high" for issue in issues):
        return "blocked"
    if any((row.get("review_status", row.get("status")) in {"planned", "needs_review"}) for row in _records(data) if isinstance(row, dict)):
        return "accepted_with_todos"
    return "accepted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an R5 reviewed evidence registry.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_yaml(args.path)
        issues = validate_registry(data)
        decision = derive_decision(issues, data)
    except Exception as exc:  # noqa: BLE001
        decision = "blocked"
        issues = [_issue("R5REV-LOAD-001", "high", str(args.path), f"ERROR: {exc}")]
    print(json.dumps({"decision": decision, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if decision in {"accepted", "accepted_with_todos"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
