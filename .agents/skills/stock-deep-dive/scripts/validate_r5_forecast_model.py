#!/usr/bin/env python3
"""Validate an R5 forecast model pack."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: pip install pyyaml") from exc

YEARS = {"2026E", "2027E", "2028E"}
METRICS = {"revenue", "gross_margin", "net_profit_attributable", "eps"}
SCENARIOS = {"base_case", "bull_case", "bear_case"}
SENSITIVITY_FIELDS = {"driver", "change", "impact_metric", "impact_value", "assumption_id_or_missing_reason"}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("root YAML object must be a mapping")
    return data


def _has_assumption_or_missing(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get("assumption_id") or value.get("missing_reason"))


def validate_forecast_model(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("artifact_type") != "R5_forecast_model_pack":
        errors.append("artifact_type must be R5_forecast_model_pack")

    years = set(data.get("forecast_years") or [])
    missing_years = sorted(YEARS - years)
    if missing_years:
        errors.append(f"forecast_years missing: {', '.join(missing_years)}")

    scenarios = data.get("scenarios")
    if not isinstance(scenarios, dict):
        return [*errors, "scenarios must be a mapping"]
    for scenario_name in sorted(SCENARIOS):
        if scenario_name not in scenarios:
            errors.append(f"scenario missing: {scenario_name}")
    base_case = scenarios.get("base_case")
    if not isinstance(base_case, dict):
        errors.append("base_case must be a mapping")
    else:
        table = base_case.get("forecast_table")
        if not isinstance(table, dict):
            errors.append("base_case.forecast_table must be a mapping")
        else:
            for year in sorted(YEARS):
                year_row = table.get(year)
                if not isinstance(year_row, dict):
                    errors.append(f"base_case.forecast_table.{year} must be a mapping")
                    continue
                for metric in sorted(METRICS):
                    metric_obj = year_row.get(metric)
                    if metric_obj is None:
                        errors.append(f"base_case.forecast_table.{year}.{metric} is required")
                    elif not _has_assumption_or_missing(metric_obj):
                        errors.append(f"base_case.forecast_table.{year}.{metric} requires assumption_id or missing_reason")

    for scenario_name in ["bull_case", "bear_case"]:
        scenario = scenarios.get(scenario_name)
        if isinstance(scenario, dict) and scenario.get("status") not in {None, "TODO_MODEL_INPUT", "partial", "ready", "blocked"}:
            errors.append(f"{scenario_name}.status is invalid")

    sensitivity = data.get("sensitivity_table")
    if not isinstance(sensitivity, list) or not sensitivity:
        errors.append("sensitivity_table must be a non-empty list")
    else:
        for idx, row in enumerate(sensitivity):
            if not isinstance(row, dict):
                errors.append(f"sensitivity_table[{idx}] must be a mapping")
                continue
            missing = sorted(SENSITIVITY_FIELDS - set(row))
            if missing:
                errors.append(f"sensitivity_table[{idx}] missing: {', '.join(missing)}")

    if data.get("sample_quality_allowed") is True and data.get("status") != "ready":
        errors.append("sample_quality_allowed requires status ready and reviewed assumptions")
    return errors


def derive_outcome(errors: list[str], data: dict[str, Any]) -> str:
    if errors:
        return "needs_fix"
    if "TODO" in str(data) or "missing_reason" in str(data):
        return "accepted_with_todos"
    return "accepted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate R5 forecast model YAML.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_yaml(args.path)
        errors = validate_forecast_model(data)
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
    print(f"OK: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
