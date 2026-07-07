#!/usr/bin/env python3
"""Validate an R5 sentiment/event pack."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: pip install pyyaml") from exc

SENTIMENT_LAYERS = ["macro_sentiment", "industry_sentiment", "company_sentiment"]
EVENT_FIELDS = {"event_date", "event_name", "impact_path", "verification_metric", "counterevidence_condition"}
SCENARIOS = {"base", "upside", "downside"}
TRACE_FIELDS = {"source_id", "metric_id", "claim_id", "missing_reason", "source_id_or_missing_reason"}
FORBIDDEN = ["建议买入", "建议卖出", "仓位", "交易动作"]


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("root YAML object must be a mapping")
    return data


def _has_trace(row: dict[str, Any]) -> bool:
    return any(row.get(field) not in (None, "", []) for field in TRACE_FIELDS)


def _walk_text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_walk_text(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(_walk_text(v) for v in value)
    return value if isinstance(value, str) else ""


def validate_pack(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("artifact_type") != "R5_sentiment_event_pack":
        errors.append("artifact_type must be R5_sentiment_event_pack")

    for layer in SENTIMENT_LAYERS:
        rows = data.get(layer)
        if not isinstance(rows, list) or not rows:
            errors.append(f"{layer} must be a non-empty list")
            continue
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append(f"{layer}[{idx}] must be a mapping")
            elif not _has_trace(row):
                errors.append(f"{layer}[{idx}] requires source_id, metric_id, claim_id, or missing_reason")

    events = data.get("catalyst_calendar")
    if not isinstance(events, list) or not events:
        errors.append("catalyst_calendar must be a non-empty list")
    else:
        for idx, row in enumerate(events):
            if not isinstance(row, dict):
                errors.append(f"catalyst_calendar[{idx}] must be a mapping")
                continue
            missing = sorted(EVENT_FIELDS - set(row))
            if missing:
                errors.append(f"catalyst_calendar[{idx}] missing: {', '.join(missing)}")
            if not row.get("source_id_or_missing_reason"):
                errors.append(f"catalyst_calendar[{idx}] requires source_id_or_missing_reason")

    matrix = data.get("event_scenario_matrix")
    if not isinstance(matrix, dict):
        errors.append("event_scenario_matrix must be a mapping")
    else:
        missing = sorted(SCENARIOS - set(matrix))
        if missing:
            errors.append(f"event_scenario_matrix missing: {', '.join(missing)}")
        for name, row in matrix.items():
            if not isinstance(row, dict):
                errors.append(f"event_scenario_matrix.{name} must be a mapping")
            elif not row.get("source_id_or_missing_reason"):
                errors.append(f"event_scenario_matrix.{name} requires source_id_or_missing_reason")

    text = _walk_text(data)
    for phrase in FORBIDDEN:
        if phrase in text:
            errors.append(f"forbidden trading action phrase: {phrase}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate R5 sentiment/event pack.")
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
