#!/usr/bin/env python3
"""Validate an R5 evidence request review ledger."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

DECISIONS = {"pending", "rejected", "accepted", "needs_manual_collection"}
FORBIDDEN = re.compile(r"买入|卖出|持有|建仓|减仓|仓位|目标价|保证收益|buy\s+rating|sell\s+rating|hold\s+rating|position\s+sizing", re.IGNORECASE)


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


def validate_ledger(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if data.get("artifact_type") != "R5_evidence_request_review_ledger":
        issues.append(_issue("R5LEDGER-ROOT-001", "high", "artifact_type", "artifact_type must be R5_evidence_request_review_ledger"))
    if data.get("no_live_api") is not True:
        issues.append(_issue("R5LEDGER-ROOT-002", "high", "no_live_api", "no_live_api must be true"))
    if FORBIDDEN.search(_text(data)):
        issues.append(_issue("R5LEDGER-NOADV-001", "high", "ledger", "direct trading language is forbidden"))
    items = data.get("items") or []
    if not isinstance(items, list) or not items:
        issues.append(_issue("R5LEDGER-ROW-000", "high", "items", "items must be a non-empty list"))
        return issues
    for idx, row in enumerate(items):
        path = f"items[{idx}]"
        if not isinstance(row, dict):
            issues.append(_issue("R5LEDGER-ROW-001", "high", path, "ledger item must be a mapping"))
            continue
        decision = row.get("review_decision")
        if decision not in DECISIONS:
            issues.append(_issue("R5LEDGER-ROW-002", "high", f"{path}.review_decision", "review_decision is invalid"))
        for field in ["request_id", "source_gap_id", "pack_section", "review_decision", "reason", "next_action"]:
            if row.get(field) in (None, ""):
                issues.append(_issue("R5LEDGER-ROW-003", "medium", f"{path}.{field}", f"{field} is required"))
        if decision == "accepted":
            if not row.get("evidence_id"):
                issues.append(_issue("R5LEDGER-ACCEPT-001", "high", f"{path}.evidence_id", "accepted rows require evidence_id"))
            if not row.get("source_rank"):
                issues.append(_issue("R5LEDGER-ACCEPT-002", "high", f"{path}.source_rank", "accepted rows require source_rank"))
        if decision in {"pending", "needs_manual_collection"} and (not row.get("reason") or not row.get("next_action")):
            issues.append(_issue("R5LEDGER-PENDING-001", "high", path, "pending rows require reason and next_action"))
    return issues


def derive_decision(data: dict[str, Any], issues: list[dict[str, str]]) -> str:
    if any(issue["severity"] == "high" for issue in issues):
        return "blocked"
    items = data.get("items") or []
    if any(isinstance(row, dict) and row.get("review_decision") != "accepted" for row in items):
        return "accepted_with_todos"
    return "accepted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an R5 evidence request review ledger.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_yaml(args.path)
        issues = validate_ledger(data)
        decision = derive_decision(data, issues)
    except Exception as exc:  # noqa: BLE001
        decision = "blocked"
        issues = [_issue("R5LEDGER-LOAD-001", "high", str(args.path), f"ERROR: {exc}")]
    print(json.dumps({"decision": decision, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if decision in {"accepted", "accepted_with_todos"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
