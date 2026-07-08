#!/usr/bin/env python3
"""Validate company-valuation to R5 valuation_pack handoff artifacts."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


REQUIRED_FIELDS = {
    "valuation_as_of_date",
    "market_snapshot",
    "peer_context",
    "method_used",
    "scenario_values",
    "assumptions",
    "sensitivity",
    "source_evidence_ids",
    "missing_items",
    "no_advice_statement",
}
MARKET_REQUIRED = {"current_price", "market_cap", "share_count"}
SUPPORT_KEYS = {"source_evidence_id", "evidence_id", "source_evidence_ids", "metric_id", "assumption_id", "missing_reason"}
FORBIDDEN_PATTERNS = [
    re.compile(r"建议\s*买入|建议\s*卖出|建议\s*持有"),
    re.compile(r"买入评级|卖出评级|持有评级"),
    re.compile(r"仓位\s*建议|建议\s*仓位"),
    re.compile(r"目标价\s*(为|:|：)"),
    re.compile(r"\b(buy|sell|hold)\s+rating\b", re.IGNORECASE),
    re.compile(r"\bprice target\s*(is|:)", re.IGNORECASE),
    re.compile(r"\bposition sizing recommendation\b", re.IGNORECASE),
]


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("root YAML object must be a mapping")
    return data


def _issue(severity: str, path: str, message: str) -> dict[str, str]:
    return {"severity": severity, "path": path, "message": message}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _has_support(obj: dict[str, Any]) -> bool:
    return any(obj.get(key) not in (None, "", []) for key in SUPPORT_KEYS)


def _walk_text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join([*map(str, value.keys()), *(_walk_text(item) for item in value.values())])
    if isinstance(value, list):
        return "\n".join(_walk_text(item) for item in value)
    return "" if value is None else str(value)


def _check_numeric_support(value: Any, path: str, issues: list[dict[str, str]]) -> None:
    if isinstance(value, dict):
        if "value" in value:
            if value.get("value") is not None and not _has_support(value):
                issues.append(_issue("high", path, "valuation number requires evidence_id, metric_id, assumption_id, or missing_reason"))
            return
        for key, item in value.items():
            _check_numeric_support(item, f"{path}.{key}", issues)
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            _check_numeric_support(item, f"{path}[{idx}]", issues)
    elif _is_number(value):
        issues.append(_issue("high", path, "raw numeric valuation value must be wrapped with support metadata"))


def _valid_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def validate_handoff(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if data.get("artifact_type") != "R5_valuation_handoff":
        issues.append(_issue("high", "artifact_type", "artifact_type must be R5_valuation_handoff"))

    for field in sorted(REQUIRED_FIELDS - set(data)):
        issues.append(_issue("high", field, f"missing required field: {field}"))

    if not _valid_date(data.get("valuation_as_of_date")):
        issues.append(_issue("high", "valuation_as_of_date", "valuation_as_of_date must be YYYY-MM-DD"))

    market = data.get("market_snapshot")
    if not isinstance(market, dict):
        issues.append(_issue("high", "market_snapshot", "market_snapshot must be a mapping"))
    else:
        for field in sorted(MARKET_REQUIRED):
            value = market.get(field)
            if value is None:
                issues.append(_issue("high", f"market_snapshot.{field}", f"market_snapshot.{field} is required for R5 valuation gate"))
            elif isinstance(value, dict) and value.get("value") is None and not value.get("missing_reason"):
                issues.append(_issue("high", f"market_snapshot.{field}", f"market_snapshot.{field} requires missing_reason when missing"))

    peer = data.get("peer_context")
    if not isinstance(peer, dict):
        issues.append(_issue("high", "peer_context", "peer_context must be a mapping"))
    else:
        peers = peer.get("peers")
        if peer.get("status") not in {"reviewed", "ready", "accepted"} or not isinstance(peers, list) or not peers:
            issues.append(_issue("high", "peer_context", "missing peer context requires valuation downgrade"))

    for field in ["method_used", "scenario_values", "assumptions", "sensitivity", "source_evidence_ids"]:
        if not isinstance(data.get(field), list) or not data.get(field):
            issues.append(_issue("high", field, f"{field} must be a non-empty list"))

    if not data.get("no_advice_statement"):
        issues.append(_issue("high", "no_advice_statement", "no_advice_statement is required"))

    _check_numeric_support(data.get("market_snapshot"), "market_snapshot", issues)
    _check_numeric_support(data.get("peer_context"), "peer_context", issues)
    _check_numeric_support(data.get("scenario_values"), "scenario_values", issues)
    _check_numeric_support(data.get("sensitivity"), "sensitivity", issues)

    text = _walk_text(data)
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(text):
            issues.append(_issue("high", "no_advice_scan", f"forbidden advice language matched: {pattern.pattern}"))

    return issues


def decision_for(issues: list[dict[str, str]]) -> str:
    if any(issue["severity"] == "high" for issue in issues):
        return "blocked"
    if issues:
        return "accepted_with_todos"
    return "accepted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate R5 valuation handoff YAML.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        issues = validate_handoff(load_yaml(args.path))
    except Exception as exc:  # noqa: BLE001
        issues = [_issue("high", str(args.path), f"failed to load YAML: {exc}")]
    decision = decision_for(issues)
    print(json.dumps({"decision": decision, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if decision in {"accepted", "accepted_with_todos"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
