#!/usr/bin/env python3
"""Validate R5 official disclosure gap review artifacts."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

FORBIDDEN = re.compile(r"买入|卖出|持有|仓位|buy\s+rating|sell\s+rating|hold\s+rating|position\s+sizing", re.IGNORECASE)
STATUSES = {"found", "not_found", "partial", "needs_manual_review"}


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


def validate_gap_review(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if data.get("artifact_type") != "R5_official_disclosure_gap_review":
        issues.append(_issue("R5DISC-ROOT-001", "high", "artifact_type", "artifact_type must be R5_official_disclosure_gap_review"))
    if data.get("no_live_api") is not True:
        issues.append(_issue("R5DISC-ROOT-002", "high", "no_live_api", "no_live_api must be true"))
    reviews = data.get("reviews") or data.get("records") or []
    if not isinstance(reviews, list) or not reviews:
        issues.append(_issue("R5DISC-ROW-000", "high", "reviews", "reviews must be a non-empty list"))
        return issues

    for idx, raw in enumerate(reviews):
        path = f"reviews[{idx}]"
        if not isinstance(raw, dict):
            issues.append(_issue("R5DISC-ROW-001", "high", path, "review row must be a mapping"))
            continue
        status = raw.get("finding_status")
        if status not in STATUSES:
            issues.append(_issue("R5DISC-ROW-002", "high", f"{path}.finding_status", "finding_status is invalid"))
        for field in ["gap_id", "requested_disclosure", "official_source_candidates", "reviewed_source_ids", "extracted_metric_candidates", "limitations", "allowed_usage"]:
            if raw.get(field) is None:
                issues.append(_issue("R5DISC-ROW-003", "medium", f"{path}.{field}", f"{field} is required"))
        if FORBIDDEN.search(_text(raw.get("allowed_usage", []))):
            issues.append(_issue("R5DISC-NOADV-001", "high", f"{path}.allowed_usage", "allowed_usage contains direct trading language"))
        sources = raw.get("reviewed_source_ids") or []
        if status in {"found", "partial"} and not sources:
            issues.append(_issue("R5DISC-SRC-001", "high", f"{path}.reviewed_source_ids", "found/partial disclosure requires reviewed_source_ids"))
        if status == "not_found" and "MISSING_DISCLOSURE" not in _text(raw.get("limitations", [])):
            issues.append(_issue("R5DISC-GAP-001", "high", f"{path}.limitations", "not_found reviews must preserve MISSING_DISCLOSURE"))
        for src_idx, source in enumerate(sources):
            src_path = f"{path}.reviewed_source_ids[{src_idx}]"
            if not isinstance(source, dict):
                issues.append(_issue("R5DISC-SRC-002", "high", src_path, "reviewed source must be a mapping"))
                continue
            for field in ["evidence_id", "source_rank"]:
                if not source.get(field):
                    issues.append(_issue("R5DISC-SRC-003", "high", f"{src_path}.{field}", f"{field} is required for promoted sources"))
            if not (source.get("as_of_date") or source.get("filing_date")):
                issues.append(_issue("R5DISC-SRC-004", "high", src_path, "promoted sources require as_of_date or filing_date"))
    return issues


def derive_decision(data: dict[str, Any], issues: list[dict[str, str]]) -> str:
    if any(issue["severity"] == "high" for issue in issues):
        return "blocked"
    reviews = data.get("reviews") or []
    if any(isinstance(row, dict) and row.get("finding_status") in {"not_found", "needs_manual_review"} for row in reviews):
        return "accepted_with_todos"
    return "accepted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate R5 official disclosure gap review YAML.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_yaml(args.path)
        issues = validate_gap_review(data)
        decision = derive_decision(data, issues)
    except Exception as exc:  # noqa: BLE001
        decision = "blocked"
        issues = [_issue("R5DISC-LOAD-001", "high", str(args.path), f"ERROR: {exc}")]
    print(json.dumps({"decision": decision, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if decision in {"accepted", "accepted_with_todos"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
