#!/usr/bin/env python3
"""Validate an R5 business breakdown pack."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

STATUSES = {"TODO", "partial", "ready", "blocked"}
REQUIRED_ROOT = [
    "artifact_type",
    "schema_version",
    "status",
    "as_of_date",
    "stock_code",
    "business_lines",
    "profit_pool_summary",
    "structural_contradictions",
    "linked_segments",
    "missing_items",
    "source_gap_register",
]
CORE_METRICS = ["revenue", "revenue_pct", "gross_margin", "gross_profit", "gross_profit_pct"]
ALLOWED_NULL_REASONS = {"MISSING_DISCLOSURE", "TODO_SOURCE_REQUIRED", "NOT_APPLICABLE"}
FORBIDDEN = re.compile(r"买入|卖出|持有|仓位|目标价|保证收益|buy\s+rating|sell\s+rating|hold\s+rating|position\s+sizing", re.IGNORECASE)


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("root YAML object must be a mapping")
    return data


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_text(item) for item in value)
    return "" if value is None else str(value)


def validate_metric(metric: Any, path: str, *, ready: bool) -> list[str]:
    errors: list[str] = []
    if not isinstance(metric, dict):
        return [f"{path} must be a mapping"]
    if "value" not in metric:
        errors.append(f"{path}.value is required")
    value = metric.get("value")
    has_anchor = bool(metric.get("evidence_id") or metric.get("metric_id"))
    if value is not None and not has_anchor:
        errors.append(f"{path}.value requires evidence_id or metric_id when non-null")
    if value is None:
        reason = metric.get("missing_reason")
        if reason not in ALLOWED_NULL_REASONS:
            errors.append(f"{path}.missing_reason must be MISSING_DISCLOSURE, TODO_SOURCE_REQUIRED, or NOT_APPLICABLE")
        if ready and reason != "NOT_APPLICABLE":
            errors.append(f"{path} cannot remain null when status is ready")
        if reason == "NOT_APPLICABLE" and not has_anchor:
            errors.append(f"{path}.NOT_APPLICABLE requires evidence_id or metric_id")
    return errors


def validate_business_breakdown_pack(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("artifact_type") != "R5_business_breakdown_pack":
        errors.append("artifact_type must be R5_business_breakdown_pack")
    for field in REQUIRED_ROOT:
        if field not in data:
            errors.append(f"{field} is required")
    if data.get("status") not in STATUSES:
        errors.append("status must be one of TODO, partial, ready, blocked")
    if FORBIDDEN.search(_text(data)):
        errors.append("forbidden direct trading language found")

    lines = data.get("business_lines")
    if not isinstance(lines, list) or not lines:
        errors.append("business_lines must be a non-empty list")
        return errors

    ready = data.get("status") == "ready"
    for idx, line in enumerate(lines):
        path = f"business_lines[{idx}]"
        if not isinstance(line, dict):
            errors.append(f"{path} must be a mapping")
            continue
        for field in ["business_name", "role", "confidence", "evidence_ids", "missing_items"]:
            if field not in line:
                errors.append(f"{path}.{field} is required")
        for metric_name in CORE_METRICS:
            errors.extend(validate_metric(line.get(metric_name), f"{path}.{metric_name}", ready=ready))
        metric_anchors = [
            line.get(metric_name, {}).get("evidence_id") or line.get(metric_name, {}).get("metric_id")
            for metric_name in CORE_METRICS
            if isinstance(line.get(metric_name), dict)
        ]
        has_supported_core_metric = any(metric_anchors)
        has_product_clue = bool(line.get("products") or line.get("customers") or line.get("capacity") or line.get("orders"))
        if line.get("confidence") == "high" and has_product_clue and not has_supported_core_metric:
            errors.append(f"{path}.confidence cannot be high from product/customer/capacity/order clues alone")
    if ready and ("MISSING_DISCLOSURE" in _text(data) or "TODO_SOURCE_REQUIRED" in _text(data)):
        errors.append("status ready cannot contain hidden MISSING_DISCLOSURE or TODO_SOURCE_REQUIRED")
    return errors


def derive_outcome(errors: list[str], data: dict[str, Any]) -> str:
    if errors:
        return "needs_fix"
    if "MISSING_DISCLOSURE" in _text(data) or "TODO_SOURCE_REQUIRED" in _text(data):
        return "accepted_with_todos"
    return "accepted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate R5 business breakdown pack YAML.")
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--input", dest="input_path", type=Path)
    args = parser.parse_args(argv)
    path = args.input_path or args.path
    if path is None:
        parser.error("an input path is required")
    try:
        data = load_yaml(path)
        errors = validate_business_breakdown_pack(data)
    except Exception as exc:  # noqa: BLE001
        print("outcome: blocked")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    outcome = derive_outcome(errors, data)
    print(f"outcome: {outcome}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
