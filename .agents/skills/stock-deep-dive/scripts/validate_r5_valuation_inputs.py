#!/usr/bin/env python3
"""Validate an R5 valuation input registry."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

FORBIDDEN = re.compile(r"买入|卖出|持有|仓位|目标价|buy\s+rating|sell\s+rating|hold\s+rating|position\s+sizing", re.IGNORECASE)
RELATIVE_METHODS = {"relative_pe", "relative_pb", "relative_ps", "relative_valuation"}


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


def _reviewed(block: Any) -> bool:
    return isinstance(block, dict) and block.get("review_status") in {"reviewed", "ready"} and bool(block.get("source_evidence_ids") or block.get("assumption_ids"))


def _eligible(value: Any) -> bool:
    return value in {True, "eligible", "sample_quality_candidate", "ready"}


def validate_valuation_inputs(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if data.get("artifact_type") != "R5_valuation_input_registry":
        issues.append(_issue("R5VALIN-ROOT-001", "high", "artifact_type", "artifact_type must be R5_valuation_input_registry"))
    if data.get("no_live_api") is not True:
        issues.append(_issue("R5VALIN-ROOT-002", "high", "no_live_api", "no_live_api must be true"))
    if FORBIDDEN.search(_text(data)):
        issues.append(_issue("R5VALIN-NOADV-001", "high", "registry", "valuation inputs contain direct trading language"))

    market_ready = _reviewed(data.get("market_snapshot"))
    peer_ready = _reviewed(data.get("peer_snapshot"))
    forecast = data.get("forecast_model")
    forecast_ready = isinstance(forecast, dict) and forecast.get("review_status") in {"reviewed", "ready"} and bool(forecast.get("assumption_ids"))
    business = data.get("business_line_split")
    business_ready = isinstance(business, dict) and business.get("review_status") in {"reviewed", "explicitly_scoped"}

    for block_name in ["market_snapshot", "peer_snapshot", "forecast_model", "valuation_methods"]:
        if data.get(block_name) in (None, "", []):
            issues.append(_issue("R5VALIN-ROOT-003", "high", block_name, f"{block_name} is required"))

    methods = data.get("valuation_methods") or []
    if not isinstance(methods, list):
        issues.append(_issue("R5VALIN-METHOD-000", "high", "valuation_methods", "valuation_methods must be a list"))
        methods = []
    for idx, method in enumerate(methods):
        path = f"valuation_methods[{idx}]"
        if not isinstance(method, dict):
            issues.append(_issue("R5VALIN-METHOD-001", "high", path, "valuation method row must be a mapping"))
            continue
        name = str(method.get("method", ""))
        if _eligible(method.get("eligibility")):
            if name in RELATIVE_METHODS and not (market_ready and peer_ready):
                issues.append(_issue("R5VALIN-REL-001", "high", path, "relative valuation requires reviewed market and peer inputs"))
            if name == "sotp" and not business_ready:
                issues.append(_issue("R5VALIN-SOTP-001", "high", path, "SOTP requires reviewed or explicitly scoped business-line split"))
            if name == "dcf" and not forecast_ready:
                issues.append(_issue("R5VALIN-DCF-001", "high", path, "DCF requires reviewed forecast cashflow assumptions"))
    return issues


def derive_decision(data: dict[str, Any], issues: list[dict[str, str]]) -> str:
    if any(issue["severity"] == "high" for issue in issues):
        return "blocked"
    market_ready = _reviewed(data.get("market_snapshot"))
    peer_ready = _reviewed(data.get("peer_snapshot"))
    forecast = data.get("forecast_model")
    forecast_ready = isinstance(forecast, dict) and forecast.get("review_status") in {"reviewed", "ready"} and bool(forecast.get("assumption_ids"))
    if market_ready and peer_ready and forecast_ready:
        return "sample_quality_candidate"
    if any(token in _text(data) for token in ["TODO_MARKET_DATA", "TODO_PEER_DATA", "TODO_MODEL_INPUT", "MISSING_DISCLOSURE"]):
        return "source_gapped_research_draft"
    return "blocked_for_sample_quality"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an R5 valuation input registry.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_yaml(args.path)
        issues = validate_valuation_inputs(data)
        decision = derive_decision(data, issues)
    except Exception as exc:  # noqa: BLE001
        decision = "blocked"
        issues = [_issue("R5VALIN-LOAD-001", "high", str(args.path), f"ERROR: {exc}")]
    print(json.dumps({"decision": decision, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if decision in {"sample_quality_candidate", "source_gapped_research_draft", "blocked_for_sample_quality"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
