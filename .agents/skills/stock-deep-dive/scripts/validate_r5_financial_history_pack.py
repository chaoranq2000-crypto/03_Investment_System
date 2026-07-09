#!/usr/bin/env python3
"""Validate an R5 financial history pack."""
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
    "currency",
    "periods",
    "income_statement",
    "balance_sheet",
    "cashflow_statement",
    "key_metrics",
    "financial_quality",
    "adjusted_profit_bridge",
    "cashflow_quality",
    "working_capital_flags",
    "roe_roic_commentary",
    "evidence_ids",
    "missing_items",
]
REQUIRED_SECTIONS = ["income_statement", "balance_sheet", "cashflow_statement", "key_metrics"]
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


def _missing_items(data: dict[str, Any]) -> set[str]:
    items = data.get("missing_items") or []
    result: set[str] = set()
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                result.add(str(item.get("item") or item.get("metric_name") or ""))
            else:
                result.add(str(item))
    return result


def _is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_metric_row(row: dict[str, Any], path: str, missing_items: set[str]) -> list[str]:
    errors: list[str] = []
    for field in ["metric_name", "period", "value", "unit"]:
        if field not in row:
            errors.append(f"{path}.{field} is required")
    value = row.get("value")
    has_anchor = bool(row.get("evidence_id") or row.get("metric_id"))
    if _is_numeric(value) and not has_anchor:
        errors.append(f"{path}.value requires evidence_id or metric_id when non-null")
    if value is None:
        metric_name = str(row.get("metric_name") or "")
        if not row.get("missing_reason") and metric_name not in missing_items:
            errors.append(f"{path}.value requires missing_reason or missing_items entry when null")
    return errors


def validate_financial_history_pack(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("artifact_type") != "R5_financial_history_pack":
        errors.append("artifact_type must be R5_financial_history_pack")
    for field in REQUIRED_ROOT:
        if field not in data:
            errors.append(f"{field} is required")
    if data.get("status") not in STATUSES:
        errors.append("status must be one of TODO, partial, ready, blocked")
    if "periods" in data and not isinstance(data.get("periods"), list):
        errors.append("periods must be a list")
    if FORBIDDEN.search(_text(data)):
        errors.append("forbidden direct trading language found")

    missing_items = _missing_items(data)
    for section in REQUIRED_SECTIONS:
        rows = data.get(section)
        if rows is None:
            continue
        if not isinstance(rows, list):
            errors.append(f"{section} must be a list")
            continue
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append(f"{section}[{idx}] must be a mapping")
                continue
            errors.extend(validate_metric_row(row, f"{section}[{idx}]", missing_items))

    if data.get("status") == "ready":
        for section in REQUIRED_SECTIONS:
            if not data.get(section):
                errors.append(f"status ready requires non-empty {section}")
        if "TODO" in _text(data) or "missing_reason" in _text(data):
            errors.append("status ready cannot contain hidden TODO or missing_reason markers")
    return errors


def derive_outcome(errors: list[str], data: dict[str, Any]) -> str:
    if errors:
        return "needs_fix"
    if "TODO" in _text(data) or "missing_reason" in _text(data):
        return "accepted_with_todos"
    return "accepted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate R5 financial history pack YAML.")
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--input", dest="input_path", type=Path)
    args = parser.parse_args(argv)
    path = args.input_path or args.path
    if path is None:
        parser.error("an input path is required")
    try:
        data = load_yaml(path)
        errors = validate_financial_history_pack(data)
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
