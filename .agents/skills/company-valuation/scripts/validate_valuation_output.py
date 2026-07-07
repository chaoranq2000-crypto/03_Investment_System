#!/usr/bin/env python3
"""Validate company-valuation output for R5 handoff."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: pip install pyyaml") from exc

REQUIRED_TOP = {
    "valuation_as_of_date",
    "input_status",
    "market_snapshot",
    "peer_set",
    "method_selection",
    "scenario_outputs",
    "sensitivity",
    "source_gap",
    "no_advice_disclaimer",
}
INPUT_STATUS = {"complete", "partial_with_todos", "blocked"}
SCENARIOS = {"base", "bull", "bear"}
FORBIDDEN = ["买入", "卖出", "持有", "评级", "仓位建议", "止盈", "止损", "guaranteed return", "position sizing"]


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("root YAML object must be a mapping")
    return data


def _walk_values(value: Any) -> list[Any]:
    if isinstance(value, dict):
        out: list[Any] = []
        for item in value.values():
            out.extend(_walk_values(item))
        return out
    if isinstance(value, list):
        out: list[Any] = []
        for item in value:
            out.extend(_walk_values(item))
        return out
    return [value]


def _walk_number_objects(value: Any, path: str = "") -> list[tuple[str, dict[str, Any]]]:
    found: list[tuple[str, dict[str, Any]]] = []
    if isinstance(value, dict):
        if "value" in value:
            found.append((path, value))
        for key, item in value.items():
            found.extend(_walk_number_objects(item, f"{path}.{key}" if path else key))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            found.extend(_walk_number_objects(item, f"{path}[{idx}]"))
    return found


def validate_output(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in sorted(REQUIRED_TOP - set(data)):
        errors.append(f"missing top-level field: {field}")
    if data.get("input_status") not in INPUT_STATUS:
        errors.append(f"input_status is invalid: {data.get('input_status')}")

    market = data.get("market_snapshot")
    if not isinstance(market, dict):
        errors.append("market_snapshot must be a mapping")
    else:
        missing_market = any(
            isinstance(market.get(field), dict) and market[field].get("value") is None
            for field in ["current_price", "market_cap", "share_count"]
        )
        if missing_market and data.get("input_status") == "complete":
            errors.append("input_status cannot be complete when market_snapshot is missing")

    scenarios = data.get("scenario_outputs")
    if not isinstance(scenarios, dict):
        errors.append("scenario_outputs must be a mapping")
    else:
        missing = sorted(SCENARIOS - set(scenarios))
        if missing:
            errors.append(f"scenario_outputs missing: {', '.join(missing)}")
        if "base" not in scenarios:
            errors.append("scenario_outputs.base is required")

    for path, obj in _walk_number_objects(data):
        if obj.get("value") is not None and not (obj.get("assumption_id") or obj.get("missing_reason")):
            errors.append(f"{path} requires assumption_id or missing_reason")
        if obj.get("value") is None and not obj.get("missing_reason"):
            errors.append(f"{path} requires missing_reason when value is null")

    disclaimer = str(data.get("no_advice_disclaimer") or "")
    if "research context" not in disclaimer.lower():
        errors.append("no_advice_disclaimer must state research context boundary")
    text = "\n".join(str(item) for item in _walk_values(data))
    for phrase in FORBIDDEN:
        if phrase in text:
            errors.append(f"forbidden advice language: {phrase}")
    return errors


def derive_outcome(errors: list[str], data: dict[str, Any]) -> str:
    if errors:
        return "needs_fix"
    return "accepted_with_todos" if data.get("input_status") == "partial_with_todos" else "accepted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate company valuation output YAML.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_yaml(args.path)
        errors = validate_output(data)
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
