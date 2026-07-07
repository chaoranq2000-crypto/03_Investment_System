#!/usr/bin/env python3
"""Validate an R5 technical market pack."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: pip install pyyaml") from exc

REQUIRED_FIELDS = {
    "current_price",
    "return_1m",
    "return_3m",
    "return_6m",
    "return_12m",
    "ytd_return",
    "52w_high",
    "52w_low",
    "MA5",
    "MA10",
    "MA20",
    "MA60",
    "turnover",
    "volume_percentile",
}
LEVEL_FIELDS = {"level", "basis", "source_id_or_missing_reason"}
FORBIDDEN = ["建议买入", "建议卖出", "止损", "仓位", "目标买点", "目标卖点"]


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("root YAML object must be a mapping")
    return data


def _walk_text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_walk_text(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(_walk_text(v) for v in value)
    return value if isinstance(value, str) else ""


def _value_has_source_or_missing(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("value") is None:
            return bool(value.get("missing_reason") or value.get("source_id"))
        return bool(value.get("source_id") or value.get("metric_id") or value.get("missing_reason"))
    return value is not None


def validate_pack(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("artifact_type") != "R5_technical_market_pack":
        errors.append("artifact_type must be R5_technical_market_pack")
    if not data.get("as_of_date"):
        errors.append("as_of_date is required before market-state language")

    for field in sorted(REQUIRED_FIELDS):
        if field not in data:
            errors.append(f"{field} is required")
        elif not _value_has_source_or_missing(data.get(field)):
            errors.append(f"{field} requires source_id/metric_id or missing_reason")

    for list_name in ["support_levels", "resistance_levels"]:
        rows = data.get(list_name)
        if not isinstance(rows, list) or not rows:
            errors.append(f"{list_name} must be a non-empty list")
            continue
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append(f"{list_name}[{idx}] must be a mapping")
                continue
            missing = sorted(LEVEL_FIELDS - set(row))
            if missing:
                errors.append(f"{list_name}[{idx}] missing: {', '.join(missing)}")

    if data.get("market_state_judgement") and not data.get("as_of_date"):
        errors.append("market_state_judgement requires as_of_date")
    text = _walk_text(data)
    for phrase in FORBIDDEN:
        if phrase in text:
            errors.append(f"forbidden trading action phrase: {phrase}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate R5 technical market pack.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_yaml(args.path)
        errors = validate_pack(data)
    except Exception as exc:  # noqa: BLE001
        print("outcome: blocked")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    outcome = "needs_fix" if errors else "accepted_with_todos"
    print(f"outcome: {outcome}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
