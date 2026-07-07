#!/usr/bin/env python3
"""Validate quality issue CSV files for workflow and R5 gates."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

REQUIRED_FIELDS = [
    "issue_id",
    "severity",
    "gate_id",
    "section",
    "artifact",
    "description",
    "fix_owner_skill",
    "blocking_decision",
    "next_action",
    "status",
]
SEVERITIES = {"high", "medium", "low"}
GLOBAL_GATES = {f"G{i}" for i in range(1, 11)}
R5_GATES = {f"R5-G{i}" for i in range(1, 12)}
ACTIVE_STATUSES = {"open", "blocked"}
HIGH_RISK_PATTERNS = {
    "direct trading instruction",
    "hidden TODO",
    "hidden todo",
    "unsupported number",
}


def load_issues(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV header is required")
        missing = [field for field in REQUIRED_FIELDS if field not in reader.fieldnames]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")
        return list(reader)


def _valid_gate_id(gate_id: str) -> bool:
    return gate_id in GLOBAL_GATES or gate_id in R5_GATES or gate_id.startswith("QR-")


def _row_text(row: dict[str, str]) -> str:
    return " ".join(str(value) for value in row.values())


def _is_active(row: dict[str, str]) -> bool:
    return row.get("status", "").strip() in ACTIVE_STATUSES


def validate_quality_issues(rows: list[dict[str, str]], expected_outcome: str | None = None) -> list[str]:
    errors: list[str] = []
    represented_gates = {row.get("gate_id", "").strip() for row in rows}

    if "R5-G10" not in represented_gates:
        errors.append("R5-G10 No-Advice Gate must be represented")

    for idx, row in enumerate(rows):
        for field in REQUIRED_FIELDS:
            if row.get(field, "") == "":
                errors.append(f"row {idx}: {field} is required")

        severity = row.get("severity", "").strip()
        if severity not in SEVERITIES:
            errors.append(f"row {idx}: severity is invalid: {severity}")

        gate_id = row.get("gate_id", "").strip()
        if not _valid_gate_id(gate_id):
            errors.append(f"row {idx}: gate_id is invalid: {gate_id}")

        text = _row_text(row)
        for pattern in HIGH_RISK_PATTERNS:
            if pattern in text and severity != "high":
                errors.append(f"row {idx}: {pattern} issues must be high severity")

    active_high = [row for row in rows if row.get("severity") == "high" and _is_active(row)]
    if expected_outcome == "accepted" and active_high:
        errors.append("accepted outcome is blocked by active high severity issues")

    return errors


def derive_outcome(rows: list[dict[str, str]], errors: list[str]) -> str:
    if errors:
        return "blocked"
    active_rows = [row for row in rows if _is_active(row)]
    if any(row.get("severity") == "high" for row in active_rows):
        return "needs_fix"
    if active_rows or any(row.get("status") == "accepted_todo" for row in rows):
        return "accepted_with_todos"
    return "accepted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate quality issue CSV rows.")
    parser.add_argument("--issues", required=True, type=Path, help="quality issue CSV path")
    parser.add_argument("--outcome", choices=["accepted", "accepted_with_todos", "needs_fix", "blocked"], help="Expected outcome to enforce")
    args = parser.parse_args(argv)

    try:
        rows = load_issues(args.issues)
        errors = validate_quality_issues(rows, args.outcome)
    except Exception as exc:  # noqa: BLE001
        print("outcome: blocked")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    outcome = derive_outcome(rows, errors)
    print(f"outcome: {outcome}")
    if args.outcome and args.outcome != outcome:
        errors.append(f"expected outcome {args.outcome}, got {outcome}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {args.issues}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
