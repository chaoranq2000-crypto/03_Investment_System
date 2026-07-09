#!/usr/bin/env python3
"""Validate an R5 forecast model pack."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

YEARS = {"2026E", "2027E", "2028E"}
METRICS = {"revenue", "gross_margin", "gross_profit", "net_profit_attributable", "eps"}
SCENARIOS = {"base_case", "bull_case", "bear_case"}
STATUSES = {"TODO", "partial", "ready", "blocked"}
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


def validate_forecast_row(row: Any, path: str) -> list[str]:
    if not isinstance(row, dict):
        return [f"{path} must be a mapping"]
    value = row.get("value")
    if value is None:
        if row.get("missing_reason") not in {"TODO_MODEL_INPUT", "MISSING_FORECAST_INPUT"}:
            return [f"{path}.missing_reason must be TODO_MODEL_INPUT when value is null"]
        return []
    errors: list[str] = []
    if not row.get("assumption_id"):
        errors.append(f"{path}.assumption_id is required for non-null forecast values")
    if not (row.get("evidence_id") or row.get("metric_id")):
        errors.append(f"{path} requires evidence_id or metric_id for non-null forecast values")
    return errors


def validate_forecast_model_pack(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("artifact_type") != "R5_forecast_model_pack":
        errors.append("artifact_type must be R5_forecast_model_pack")
    if data.get("status") not in STATUSES:
        errors.append("status must be one of TODO, partial, ready, blocked")
    years = set(data.get("forecast_years") or [])
    missing_years = sorted(YEARS - years)
    if missing_years:
        errors.append(f"forecast_years missing: {', '.join(missing_years)}")
    if FORBIDDEN.search(_text(data)):
        errors.append("forbidden direct trading language found")

    scenarios = data.get("scenarios")
    if not isinstance(scenarios, dict):
        errors.append("scenarios must be a mapping")
        return errors
    for scenario in sorted(SCENARIOS):
        if scenario not in scenarios:
            errors.append(f"scenario missing: {scenario}")

    base = scenarios.get("base_case")
    base_table = base.get("forecast_table") if isinstance(base, dict) else None
    if not isinstance(base_table, dict):
        errors.append("base_case.forecast_table must be a mapping")
    else:
        for year in sorted(YEARS):
            year_row = base_table.get(year)
            if not isinstance(year_row, dict):
                errors.append(f"base_case.forecast_table.{year} must be a mapping")
                continue
            for metric in sorted(METRICS):
                if metric not in year_row:
                    errors.append(f"base_case.forecast_table.{year}.{metric} is required")
                else:
                    errors.extend(validate_forecast_row(year_row[metric], f"base_case.forecast_table.{year}.{metric}"))

    consensus = data.get("consensus_comparison")
    if isinstance(consensus, dict) and consensus.get("status") not in {None, "not_supplied", "TODO"}:
        if not consensus.get("as_of_date"):
            errors.append("consensus_comparison.as_of_date is required when consensus comparison is present")
        if not (consensus.get("source_evidence_id") or consensus.get("source_path")):
            errors.append("consensus_comparison requires source_evidence_id or source_path")

    if data.get("status") == "ready":
        if not data.get("sensitivity_tests"):
            errors.append("status ready requires at least one sensitivity test")
        if isinstance(base_table, dict):
            for year in sorted(YEARS):
                year_row = base_table.get(year) or {}
                for metric in sorted(METRICS):
                    row = year_row.get(metric)
                    if not isinstance(row, dict) or row.get("value") is None:
                        errors.append(f"status ready requires base_case {year}.{metric}")
        if "TODO_MODEL_INPUT" in _text(data):
            errors.append("status ready cannot contain TODO_MODEL_INPUT")
    return errors


def derive_outcome(errors: list[str], data: dict[str, Any]) -> str:
    if errors:
        return "needs_fix"
    if "TODO_MODEL_INPUT" in _text(data) or "missing_reason" in _text(data):
        return "accepted_with_todos"
    return "accepted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate R5 forecast model pack YAML.")
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--input", dest="input_path", type=Path)
    args = parser.parse_args(argv)
    path = args.input_path or args.path
    if path is None:
        parser.error("an input path is required")
    try:
        data = load_yaml(path)
        errors = validate_forecast_model_pack(data)
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
