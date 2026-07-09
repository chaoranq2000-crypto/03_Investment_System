#!/usr/bin/env python3
"""Validate an R5 forecast assumption registry."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

FORBIDDEN = re.compile(r"买入|卖出|持有|仓位|目标价|buy\s+rating|sell\s+rating|hold\s+rating|position\s+sizing", re.IGNORECASE)
SCOPES = {"company", "segment", "product", "margin", "opex", "tax", "capex", "cashflow"}
SCENARIOS = {"base", "bull", "bear"}
STATUSES = {"planned", "needs_review", "reviewed"}
REQUIRED_FIELDS = [
    "assumption_id",
    "scope",
    "periods",
    "unit",
    "scenario",
    "supporting_evidence_ids",
    "supporting_metric_ids",
    "rationale",
    "limitations",
    "review_status",
]


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


def _period_key(assumption: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    periods = assumption.get("periods")
    if isinstance(periods, list):
        normalized = tuple(str(item) for item in periods)
    else:
        normalized = (str(periods),)
    return str(assumption.get("scope")), normalized


def validate_assumptions(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if data.get("artifact_type") != "R5_forecast_assumption_registry":
        issues.append(_issue("R5ASM-ROOT-001", "high", "artifact_type", "artifact_type must be R5_forecast_assumption_registry"))
    if data.get("no_live_api") is not True:
        issues.append(_issue("R5ASM-ROOT-002", "high", "no_live_api", "no_live_api must be true"))
    if FORBIDDEN.search(_text(data)):
        issues.append(_issue("R5ASM-NOADV-001", "high", "registry", "forecast assumptions contain direct trading language"))

    assumptions = data.get("assumptions") or []
    if not isinstance(assumptions, list) or not assumptions:
        issues.append(_issue("R5ASM-ROW-000", "high", "assumptions", "assumptions must be a non-empty list"))
        return issues

    base_keys: set[tuple[str, tuple[str, ...]]] = set()
    reviewed_rows: list[tuple[int, dict[str, Any]]] = []
    for idx, raw in enumerate(assumptions):
        path = f"assumptions[{idx}]"
        if not isinstance(raw, dict):
            issues.append(_issue("R5ASM-ROW-001", "high", path, "assumption row must be a mapping"))
            continue
        for field in REQUIRED_FIELDS:
            if raw.get(field) in (None, "", []):
                issues.append(_issue("R5ASM-ROW-002", "medium", f"{path}.{field}", f"{field} is required"))
        if raw.get("value") in (None, "") and raw.get("formula") in (None, ""):
            issues.append(_issue("R5ASM-ROW-003", "medium", path, "value or formula is required"))
        if raw.get("scope") not in SCOPES:
            issues.append(_issue("R5ASM-ROW-004", "high", f"{path}.scope", "scope is invalid"))
        if raw.get("scenario") not in SCENARIOS:
            issues.append(_issue("R5ASM-ROW-005", "high", f"{path}.scenario", "scenario is invalid"))
        if raw.get("review_status") not in STATUSES:
            issues.append(_issue("R5ASM-ROW-006", "high", f"{path}.review_status", "review_status is invalid"))
        if raw.get("scenario") == "base" and raw.get("review_status") == "reviewed":
            base_keys.add(_period_key(raw))
        if raw.get("review_status") == "reviewed":
            reviewed_rows.append((idx, raw))

    for idx, row in reviewed_rows:
        path = f"assumptions[{idx}]"
        if not (row.get("supporting_evidence_ids") or row.get("supporting_metric_ids")):
            issues.append(_issue("R5ASM-ANCHOR-001", "high", path, "reviewed assumptions require evidence or metric anchors"))
        if row.get("scope") in {"segment", "product"} and not row.get("business_disclosure_evidence_ids"):
            issues.append(_issue("R5ASM-DISCLOSURE-001", "high", path, "segment/product assumptions require reviewed business disclosure evidence"))
        if row.get("scenario") in {"bull", "bear"} and _period_key(row) not in base_keys:
            issues.append(_issue("R5ASM-SCENARIO-001", "high", path, "bull/bear assumptions require a reviewed base case"))
    return issues


def derive_decision(data: dict[str, Any], issues: list[dict[str, str]]) -> str:
    if any(issue["severity"] == "high" for issue in issues):
        return "blocked"
    assumptions = data.get("assumptions") or []
    if any(isinstance(row, dict) and row.get("review_status") != "reviewed" for row in assumptions):
        return "accepted_with_todos"
    return "accepted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate R5 forecast assumptions.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_yaml(args.path)
        issues = validate_assumptions(data)
        decision = derive_decision(data, issues)
    except Exception as exc:  # noqa: BLE001
        decision = "blocked"
        issues = [_issue("R5ASM-LOAD-001", "high", str(args.path), f"ERROR: {exc}")]
    print(json.dumps({"decision": decision, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if decision in {"accepted", "accepted_with_todos"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
