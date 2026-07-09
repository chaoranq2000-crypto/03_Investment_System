#!/usr/bin/env python3
"""Validate an R5 reviewed market snapshot."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

FORBIDDEN = re.compile(r"买入|卖出|持有|仓位|buy\s+rating|sell\s+rating|hold\s+rating|position\s+sizing", re.IGNORECASE)
REQUIRED_FIELDS = ["as_of_date", "currency", "current_price", "market_cap", "share_count", "pe_ttm", "pb", "ps"]
NUMERIC_FIELDS = ["current_price", "market_cap", "share_count", "pe_ttm", "pb", "ps"]


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


def _field(data: dict[str, Any], field: str) -> Any:
    if field in data:
        return data.get(field)
    market_fields = data.get("market_fields")
    return market_fields.get(field) if isinstance(market_fields, dict) else None


def validate_market_snapshot(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if data.get("artifact_type") != "R5_market_snapshot":
        issues.append(_issue("R5MKT-ROOT-001", "high", "artifact_type", "artifact_type must be R5_market_snapshot"))
    if data.get("no_live_api") is not True:
        issues.append(_issue("R5MKT-ROOT-002", "high", "no_live_api", "no_live_api must be true"))
    if FORBIDDEN.search(_text(data.get("allowed_usage", []))):
        issues.append(_issue("R5MKT-NOADV-001", "high", "allowed_usage", "allowed_usage contains direct trading language"))

    source_ids = data.get("source_evidence_ids") or data.get("evidence_ids") or []
    numeric_present = [field for field in NUMERIC_FIELDS if _field(data, field) not in (None, "", "TODO_MARKET_DATA")]
    if numeric_present and not source_ids:
        issues.append(_issue("R5MKT-SRC-001", "high", "source_evidence_ids", "numeric market fields require source_evidence_ids"))
    if data.get("status") not in {"TODO_MARKET_DATA", "reviewed", "ready", "source_gapped_research_draft", None}:
        issues.append(_issue("R5MKT-STATUS-001", "medium", "status", "status should be TODO_MARKET_DATA, reviewed, ready, or source_gapped_research_draft"))
    return issues


def derive_decision(data: dict[str, Any], issues: list[dict[str, str]]) -> str:
    if any(issue["severity"] == "high" for issue in issues):
        return "blocked"
    source_ids = data.get("source_evidence_ids") or data.get("evidence_ids") or []
    if data.get("status") == "TODO_MARKET_DATA" or any(_field(data, field) in (None, "", "TODO_MARKET_DATA") for field in REQUIRED_FIELDS):
        return "source_gapped_research_draft"
    if source_ids:
        return "sample_quality_candidate"
    return "blocked"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an R5 market snapshot.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_yaml(args.path)
        issues = validate_market_snapshot(data)
        decision = derive_decision(data, issues)
    except Exception as exc:  # noqa: BLE001
        decision = "blocked"
        issues = [_issue("R5MKT-LOAD-001", "high", str(args.path), f"ERROR: {exc}")]
    print(json.dumps({"decision": decision, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if decision in {"sample_quality_candidate", "source_gapped_research_draft"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
