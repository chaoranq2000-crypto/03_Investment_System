#!/usr/bin/env python3
"""Validate an R5 reviewed peer snapshot."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

FORBIDDEN = re.compile(r"买入|卖出|持有|仓位|buy\s+rating|sell\s+rating|hold\s+rating|position\s+sizing", re.IGNORECASE)
PEER_FIELDS = ["peer_id", "stock_code", "company_name", "exchange", "selection_reason", "segment_overlap", "source_evidence_ids"]
METRIC_FIELDS = ["as_of_date", "market_cap", "pe_ttm", "pb", "ps", "source_evidence_ids"]


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


def validate_peer_snapshot(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if data.get("artifact_type") != "R5_peer_snapshot":
        issues.append(_issue("R5PEER-ROOT-001", "high", "artifact_type", "artifact_type must be R5_peer_snapshot"))
    if data.get("no_live_api") is not True:
        issues.append(_issue("R5PEER-ROOT-002", "high", "no_live_api", "no_live_api must be true"))
    if FORBIDDEN.search(_text(data.get("allowed_usage", []))):
        issues.append(_issue("R5PEER-NOADV-001", "high", "allowed_usage", "allowed_usage contains direct trading language"))

    peer_set = data.get("peer_set") or []
    peer_metrics = data.get("peer_metrics") or []
    if not isinstance(peer_set, list):
        issues.append(_issue("R5PEER-SET-000", "high", "peer_set", "peer_set must be a list"))
        peer_set = []
    if not isinstance(peer_metrics, list):
        issues.append(_issue("R5PEER-METRIC-000", "high", "peer_metrics", "peer_metrics must be a list"))
        peer_metrics = []

    if data.get("status") == "TODO_PEER_DATA" or (not peer_set and not peer_metrics):
        return issues

    if len(peer_set) < 3:
        issues.append(_issue("R5PEER-SET-001", "high", "peer_set", "sample-quality peer context requires at least 3 peers"))

    for idx, peer in enumerate(peer_set):
        path = f"peer_set[{idx}]"
        if not isinstance(peer, dict):
            issues.append(_issue("R5PEER-SET-002", "high", path, "peer row must be a mapping"))
            continue
        for field in PEER_FIELDS:
            if peer.get(field) in (None, "", []):
                issues.append(_issue("R5PEER-SET-003", "high", f"{path}.{field}", f"{field} is required"))

    metric_peer_ids: set[str] = set()
    for idx, metric in enumerate(peer_metrics):
        path = f"peer_metrics[{idx}]"
        if not isinstance(metric, dict):
            issues.append(_issue("R5PEER-METRIC-001", "high", path, "peer metric row must be a mapping"))
            continue
        if metric.get("peer_id"):
            metric_peer_ids.add(str(metric["peer_id"]))
        for field in METRIC_FIELDS:
            if metric.get(field) in (None, "", []):
                issues.append(_issue("R5PEER-METRIC-002", "high", f"{path}.{field}", f"{field} is required"))

    peer_ids = {str(peer.get("peer_id")) for peer in peer_set if isinstance(peer, dict) and peer.get("peer_id")}
    if peer_ids and not peer_ids.issubset(metric_peer_ids):
        issues.append(_issue("R5PEER-METRIC-003", "high", "peer_metrics", "every reviewed peer needs dated metric coverage"))
    return issues


def derive_decision(data: dict[str, Any], issues: list[dict[str, str]]) -> str:
    if any(issue["severity"] == "high" for issue in issues):
        return "blocked"
    if data.get("status") == "TODO_PEER_DATA" or not data.get("peer_set"):
        return "source_gapped_research_draft"
    return "sample_quality_candidate"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an R5 peer snapshot.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_yaml(args.path)
        issues = validate_peer_snapshot(data)
        decision = derive_decision(data, issues)
    except Exception as exc:  # noqa: BLE001
        decision = "blocked"
        issues = [_issue("R5PEER-LOAD-001", "high", str(args.path), f"ERROR: {exc}")]
    print(json.dumps({"decision": decision, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if decision in {"sample_quality_candidate", "source_gapped_research_draft"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
