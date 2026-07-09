#!/usr/bin/env python3
"""Validate an R5 market / peer input registry."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

FORBIDDEN = re.compile(r"买入|卖出|持有|建仓|减仓|仓位|目标价|保证收益|buy\s+rating|sell\s+rating|hold\s+rating|position\s+sizing", re.IGNORECASE)
STATUSES = {"pending", "reviewed", "explicitly_degraded_but_reviewed"}
CORE_BLOCKS = ["market_inputs", "peer_inputs"]


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


def _walk_fields(data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    for block_name in CORE_BLOCKS:
        block = data.get(block_name)
        if not isinstance(block, dict):
            continue
        for field_name, raw in block.items():
            if isinstance(raw, dict):
                rows.append((f"{block_name}.{field_name}", raw))
    return rows


def validate_registry(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if data.get("artifact_type") != "R5_market_peer_input_registry":
        issues.append(_issue("R5MP-ROOT-001", "high", "artifact_type", "artifact_type must be R5_market_peer_input_registry"))
    if data.get("no_live_api") is not True:
        issues.append(_issue("R5MP-ROOT-002", "high", "no_live_api", "no_live_api must be true"))
    if FORBIDDEN.search(_text(data)):
        issues.append(_issue("R5MP-NOADV-001", "high", "registry", "direct trading language is forbidden"))
    status = data.get("review_status")
    if status not in STATUSES:
        issues.append(_issue("R5MP-STATUS-001", "high", "review_status", "review_status must be pending, reviewed, or explicitly_degraded_but_reviewed"))
    if status != "pending" and not data.get("as_of_date"):
        issues.append(_issue("R5MP-DATE-001", "high", "as_of_date", "non-pending registries require as_of_date"))
    if status in {"reviewed", "explicitly_degraded_but_reviewed"} and not data.get("reviewer"):
        issues.append(_issue("R5MP-REVIEW-001", "high", "reviewer", "reviewed registries require reviewer"))
    for block_name in CORE_BLOCKS:
        if not isinstance(data.get(block_name), dict):
            issues.append(_issue("R5MP-BLOCK-001", "high", block_name, f"{block_name} must be a mapping"))

    for path, field in _walk_fields(data):
        for required in ["value", "source_type"]:
            if field.get(required) in (None, ""):
                issues.append(_issue("R5MP-FIELD-001", "medium", f"{path}.{required}", f"{required} is required"))
        evidence_id = field.get("evidence_id")
        value = field.get("value")
        missing_reason = field.get("missing_reason")
        if status == "reviewed" and not evidence_id:
            issues.append(_issue("R5MP-EVID-001", "high", f"{path}.evidence_id", "reviewed fields require evidence_id"))
        if status == "pending" and not evidence_id and not missing_reason:
            issues.append(_issue("R5MP-TODO-001", "high", f"{path}.missing_reason", "pending null-evidence fields require missing_reason"))
        if status == "explicitly_degraded_but_reviewed" and not evidence_id and not str(missing_reason).startswith("TODO"):
            issues.append(_issue("R5MP-DEG-001", "high", f"{path}.missing_reason", "reviewed-degraded TODO fields require explicit TODO missing_reason"))
        if value not in ("TODO_MARKET_DATA", "TODO_PEER_DATA", None) and not evidence_id:
            issues.append(_issue("R5MP-NUM-001", "high", f"{path}.evidence_id", "non-TODO market/peer values require evidence_id"))
    return issues


def derive_decision(data: dict[str, Any], issues: list[dict[str, str]]) -> str:
    if any(issue["severity"] == "high" for issue in issues):
        return "blocked"
    if data.get("review_status") == "reviewed":
        return "accepted"
    return "accepted_with_todos"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate R5 market / peer input registry YAML.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_yaml(args.path)
        issues = validate_registry(data)
        decision = derive_decision(data, issues)
    except Exception as exc:  # noqa: BLE001
        decision = "blocked"
        issues = [_issue("R5MP-LOAD-001", "high", str(args.path), f"ERROR: {exc}")]
    print(json.dumps({"decision": decision, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if decision in {"accepted", "accepted_with_todos"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
