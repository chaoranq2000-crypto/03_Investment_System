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
    "stage",
    "target_artifact",
    "section",
    "description",
    "fix_owner_skill",
    "blocking_decision",
    "next_action",
    "status",
]
SEVERITIES = {"critical", "high", "medium", "low"}
GLOBAL_GATES = {f"G{i}" for i in range(1, 11)}
R5_GATES = {f"R5-G{i}" for i in range(1, 12)}
ACTIVE_STATUSES = {"open"}
TERMINAL_STATUSES = {"resolved", "waived_with_reason"}
STATUSES = {"open", "resolved", "accepted_todo", "waived_with_reason"}
HIGH_RISK_PATTERNS = {
    "direct trading instruction",
    "hidden TODO",
    "hidden todo",
    "unsupported number",
    "unsupported numbers",
}
OUTCOMES = {"accepted", "accepted_with_todos", "needs_fix", "blocked"}


def load_issues(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV header is required")
        missing = [field for field in REQUIRED_FIELDS if field not in reader.fieldnames]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def _valid_gate_id(gate_id: str) -> bool:
    return gate_id in GLOBAL_GATES or gate_id in R5_GATES or gate_id.startswith("QR-")


def _row_text(row: dict[str, str]) -> str:
    return " ".join(str(value) for value in row.values())


def _is_active(row: dict[str, str]) -> bool:
    return row.get("status", "").strip() in ACTIVE_STATUSES


def validate_quality_issues(rows: list[dict[str, str]], expected_outcome: str | None = None) -> list[str]:
    errors: list[str] = []
    represented_gates = {row.get("gate_id", "").strip() for row in rows}
    missing_r5_gates = sorted(R5_GATES - represented_gates)
    if missing_r5_gates:
        errors.append(f"missing R5 gates: {', '.join(missing_r5_gates)}")
    if "R5-G10" not in represented_gates:
        errors.append("R5-G10 No-Advice Gate must be represented")

    for idx, row in enumerate(rows):
        for field in REQUIRED_FIELDS:
            if row.get(field, "") == "":
                errors.append(f"row {idx}: {field} is required")

        severity = row.get("severity", "").strip()
        if severity not in SEVERITIES:
            errors.append(f"row {idx}: severity is invalid: {severity}")

        status = row.get("status", "").strip()
        if status not in STATUSES:
            errors.append(f"row {idx}: status is invalid: {status}")

        gate_id = row.get("gate_id", "").strip()
        if not _valid_gate_id(gate_id):
            errors.append(f"row {idx}: gate_id is invalid: {gate_id}")

        if row.get("blocking_decision") not in OUTCOMES:
            errors.append(f"row {idx}: blocking_decision is invalid: {row.get('blocking_decision')}")

        if status == "waived_with_reason" and len(row.get("next_action", "")) < 8:
            errors.append(f"row {idx}: waived_with_reason requires visible reason in next_action")

        text = _row_text(row)
        for pattern in HIGH_RISK_PATTERNS:
            if pattern in text and severity not in {"critical", "high"}:
                errors.append(f"row {idx}: {pattern} issues must be high or critical severity")

    active_blockers = [
        row
        for row in rows
        if row.get("severity") in {"critical", "high"} and row.get("status") not in TERMINAL_STATUSES
    ]
    if expected_outcome == "accepted" and active_blockers:
        errors.append("accepted outcome is blocked by active high or critical severity issues")

    return errors


def derive_outcome(rows: list[dict[str, str]], errors: list[str]) -> str:
    if errors:
        return "blocked"
    active_rows = [row for row in rows if _is_active(row)]
    if any(row.get("severity") == "critical" for row in active_rows):
        return "blocked"
    if any(row.get("severity") == "high" for row in active_rows):
        return "needs_fix"
    if active_rows or any(row.get("status") == "accepted_todo" for row in rows):
        return "accepted_with_todos"
    return "accepted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate quality issue CSV rows.")
    parser.add_argument("path", nargs="?", type=Path, help="quality issue CSV path")
    parser.add_argument("--issues", dest="issues_path", type=Path, help="quality issue CSV path")
    parser.add_argument(
        "--expected-decision",
        "--outcome",
        dest="expected_decision",
        choices=sorted(OUTCOMES),
        help="Expected decision to enforce",
    )
    args = parser.parse_args(argv)
    issues_path = args.issues_path or args.path
    if issues_path is None:
        parser.error("provide a path or --issues")

    try:
        rows = load_issues(issues_path)
        errors = validate_quality_issues(rows, args.expected_decision)
    except Exception as exc:  # noqa: BLE001
        print("outcome: blocked")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    outcome = derive_outcome(rows, errors)
    print(f"outcome: {outcome}")
    if args.expected_decision and args.expected_decision != outcome:
        errors.append(f"expected outcome {args.expected_decision}, got {outcome}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {issues_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
