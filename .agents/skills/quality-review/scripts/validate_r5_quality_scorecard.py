#!/usr/bin/env python3
"""Validate an R5 quality scorecard v2 artifact."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

FORBIDDEN = re.compile(r"买入|卖出|持有|仓位|目标价|buy\s+rating|sell\s+rating|hold\s+rating|position\s+sizing", re.IGNORECASE)
READINESS = {"ready", "ready_with_limitations", "source_gapped", "blocked"}
REQUIRED_SECTION_FIELDS = ["section_id", "readiness", "evidence_ids", "issues", "limitations", "fix_owner_skill"]


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


def validate_scorecard(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if data.get("artifact_type") != "R5_quality_scorecard_v2":
        issues.append(_issue("R5SC-ROOT-001", "high", "artifact_type", "artifact_type must be R5_quality_scorecard_v2"))
    for field in ["allowed_report_level", "sample_quality_blockers", "next_actions"]:
        if data.get(field) in (None, ""):
            issues.append(_issue("R5SC-ROOT-002", "high", field, f"{field} is required"))
    if FORBIDDEN.search(_text(data)):
        issues.append(_issue("R5SC-NOADV-001", "high", "scorecard", "scorecard contains direct trading language"))

    flags = data.get("reviewed_input_flags") if isinstance(data.get("reviewed_input_flags"), dict) else {}
    sections = data.get("sections") or []
    if not isinstance(sections, list) or not sections:
        issues.append(_issue("R5SC-SEC-000", "high", "sections", "sections must be a non-empty list"))
        return issues

    for idx, section in enumerate(sections):
        path = f"sections[{idx}]"
        if not isinstance(section, dict):
            issues.append(_issue("R5SC-SEC-001", "high", path, "section must be a mapping"))
            continue
        for field in REQUIRED_SECTION_FIELDS:
            if section.get(field) is None:
                issues.append(_issue("R5SC-SEC-002", "medium", f"{path}.{field}", f"{field} is required"))
        if section.get("readiness") not in READINESS:
            issues.append(_issue("R5SC-SEC-003", "high", f"{path}.readiness", "readiness is invalid"))
        section_id = section.get("section_id")
        readiness = section.get("readiness")
        if section_id == "forecast" and readiness == "ready" and flags.get("reviewed_forecast_assumptions_available") is not True:
            issues.append(_issue("R5SC-FCST-001", "high", path, "forecast cannot be ready without reviewed forecast assumptions"))
        if section_id == "valuation" and readiness == "ready":
            required = ["reviewed_market_inputs_available", "reviewed_peer_inputs_available", "reviewed_valuation_inputs_available"]
            missing = [flag for flag in required if flags.get(flag) is not True]
            if missing:
                issues.append(_issue("R5SC-VAL-001", "high", path, "valuation cannot be ready without reviewed market, peer, and valuation inputs"))
    return issues


def derive_decision(data: dict[str, Any], issues: list[dict[str, str]]) -> str:
    if any(issue["severity"] == "high" for issue in issues):
        return "blocked"
    if data.get("sample_quality_blockers"):
        return "source_gapped_research_draft"
    return str(data.get("allowed_report_level", "source_gapped_research_draft"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate R5 quality scorecard v2.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_yaml(args.path)
        issues = validate_scorecard(data)
        decision = derive_decision(data, issues)
    except Exception as exc:  # noqa: BLE001
        decision = "blocked"
        issues = [_issue("R5SC-LOAD-001", "high", str(args.path), f"ERROR: {exc}")]
    print(json.dumps({"decision": decision, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if decision != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
