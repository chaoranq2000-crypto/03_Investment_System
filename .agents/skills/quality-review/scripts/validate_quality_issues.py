#!/usr/bin/env python3
"""Validate quality issue CSV files for workflow and R5 gates."""
from __future__ import annotations

import argparse
import csv
import re
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
CURRENT_GOAL_FIELDS = [
    "impact_scope",
    "active_disposition",
    "affected_capabilities",
    "blocks_current_goal",
]
SEVERITIES = {"critical", "high", "medium", "low"}
GLOBAL_GATES = {f"G{i}" for i in range(11)}
R5_GATES = {f"R5-G{i}" for i in range(1, 12)}
R5_GATE_MAPPINGS = {
    "R5-G1": ("G1",),
    "R5-G2": ("G3", "G7"),
    "R5-G3": ("G2", "G3", "G7"),
    "R5-G4": ("G4", "G7"),
    "R5-G5": ("G3", "G7"),
    "R5-G6": ("G3", "G7"),
    "R5-G7": ("G3", "G7"),
    "R5-G8": ("G1", "G2", "G7"),
    "R5-G9": ("G2", "G7"),
    "R5-G10": ("G9",),
    "R5-G11": ("G7",),
}
ACTIVE_STATUSES = {"open"}
TERMINAL_STATUSES = {"resolved", "waived_with_reason"}
STATUSES = {"open", "resolved", "accepted_todo", "waived_with_reason"}
IMPACT_SCOPES = {"workflow", "report", "section", "claim", "method", "none"}
ACTIVE_DISPOSITIONS = {
    "active_defect",
    "unknown",
    "method_unavailable",
    "report_limitation",
    "historical_backlog",
    "policy_retired",
    "not_required_for_active_v1",
}
NON_ACTIVE_DISPOSITIONS = {
    "historical_backlog",
    "policy_retired",
    "not_required_for_active_v1",
}
ACTIVE_DEFECT_PATTERNS = {
    "direct trading instruction",
    "hidden todo",
    "unsupported number",
    "unsupported numbers",
    "real double-count",
    "real double count",
    "no-advice violation",
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
    return gate_id in GLOBAL_GATES


def _valid_legacy_gate_id(gate_id: str) -> bool:
    return _valid_gate_id(gate_id) or gate_id in R5_GATES or gate_id.startswith("QR-")


def _valid_local_check_id(local_check_id: str) -> bool:
    return bool(re.fullmatch(r"(?:R5-G\d+|QR-[A-Z0-9-]+|DLQ-\d+)", local_check_id))


def _mapped_gate_ids(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split("|") if part.strip())


def _row_text(row: dict[str, str]) -> str:
    return " ".join(str(value) for value in row.values())


def _is_active(row: dict[str, str]) -> bool:
    return row.get("status", "").strip() in ACTIVE_STATUSES


def _uses_current_goal_schema(rows: list[dict[str, str]]) -> bool:
    return bool(rows) and all(
        all(field in row for field in CURRENT_GOAL_FIELDS) for row in rows
    )


def _parse_bool(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


def _capabilities(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split("|") if part.strip())


def _scoped_row_outcome(
    row: dict[str, str], idx: int, errors: list[str]
) -> str | None:
    for field in CURRENT_GOAL_FIELDS:
        if field != "affected_capabilities" and row.get(field, "") == "":
            errors.append(f"row {idx}: {field} is required")

    scope = row.get("impact_scope", "").strip()
    disposition = row.get("active_disposition", "").strip()
    capabilities = _capabilities(row.get("affected_capabilities", ""))
    blocks = _parse_bool(row.get("blocks_current_goal", ""))

    if scope not in IMPACT_SCOPES:
        errors.append(f"row {idx}: impact_scope is invalid: {scope}")
    if disposition not in ACTIVE_DISPOSITIONS:
        errors.append(f"row {idx}: active_disposition is invalid: {disposition}")
    if blocks is None:
        errors.append(
            f"row {idx}: blocks_current_goal must be true or false: "
            f"{row.get('blocks_current_goal', '')}"
        )
    if len(capabilities) != len(set(capabilities)):
        errors.append(f"row {idx}: affected_capabilities must not contain duplicates")

    if (
        scope not in IMPACT_SCOPES
        or disposition not in ACTIVE_DISPOSITIONS
        or blocks is None
    ):
        return None

    if disposition in NON_ACTIVE_DISPOSITIONS:
        if scope != "none" or capabilities or blocks:
            errors.append(
                f"row {idx}: {disposition} requires impact_scope=none, "
                "empty affected_capabilities, and blocks_current_goal=false"
            )
        return "accepted"

    if scope == "none":
        errors.append(f"row {idx}: {disposition} cannot use impact_scope=none")
    if not capabilities:
        errors.append(f"row {idx}: {disposition} requires affected_capabilities")

    if disposition == "active_defect":
        if not blocks:
            errors.append(f"row {idx}: active_defect must block the current goal")
        return "blocked" if scope == "workflow" else "needs_fix"

    if disposition == "unknown":
        if scope == "workflow":
            errors.append(f"row {idx}: unknown must be scoped below workflow")
        return "needs_fix" if blocks else "accepted_with_todos"

    if disposition == "method_unavailable":
        if scope != "method":
            errors.append(
                f"row {idx}: method_unavailable requires impact_scope=method"
            )
        return "blocked" if blocks else "accepted_with_todos"

    if disposition == "report_limitation":
        if blocks:
            errors.append(
                f"row {idx}: a visible report_limitation cannot block the current goal"
            )
        if scope == "workflow":
            errors.append(
                f"row {idx}: report_limitation must be scoped below workflow"
            )
        return "accepted_with_todos"

    raise AssertionError(f"unhandled active disposition: {disposition}")


def validate_quality_issues(
    rows: list[dict[str, str]],
    expected_outcome: str | None = None,
    *,
    require_current_goal: bool = False,
) -> list[str]:
    errors: list[str] = []
    has_local_column = bool(rows) and all("local_check_id" in row for row in rows)
    has_mapping_column = bool(rows) and all("mapped_global_gate_ids" in row for row in rows)
    active_mapping_schema = has_local_column and has_mapping_column
    if has_local_column != has_mapping_column:
        errors.append("local_check_id and mapped_global_gate_ids columns must appear together")

    has_any_current_goal_column = bool(rows) and any(
        any(field in row for field in CURRENT_GOAL_FIELDS) for row in rows
    )
    current_goal_schema = _uses_current_goal_schema(rows)
    if has_any_current_goal_column and not current_goal_schema:
        errors.append(
            "impact_scope, active_disposition, affected_capabilities, and "
            "blocks_current_goal columns must appear together"
        )
    if require_current_goal and not current_goal_schema:
        errors.append("current-goal issue fields are required for an active V1 issue list")

    represented_r5_gates = {
        row.get("local_check_id", "").strip() if active_mapping_schema else row.get("gate_id", "").strip()
        for row in rows
    } & R5_GATES
    if represented_r5_gates:
        missing_r5_gates = sorted(R5_GATES - represented_r5_gates)
        if missing_r5_gates:
            errors.append(f"missing R5 gates: {', '.join(missing_r5_gates)}")
        if "R5-G10" not in represented_r5_gates:
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
        gate_is_valid = _valid_gate_id(gate_id) if active_mapping_schema else _valid_legacy_gate_id(gate_id)
        if not gate_is_valid:
            errors.append(f"row {idx}: gate_id is invalid: {gate_id}")

        if active_mapping_schema:
            local_check_id = row.get("local_check_id", "").strip()
            mapped_gate_ids = _mapped_gate_ids(row.get("mapped_global_gate_ids", ""))
            if local_check_id and not _valid_local_check_id(local_check_id):
                errors.append(f"row {idx}: local_check_id is invalid: {local_check_id}")
            if local_check_id and not mapped_gate_ids:
                errors.append(f"row {idx}: mapped_global_gate_ids is required for a local check")
            invalid_mapped = [gate for gate in mapped_gate_ids if gate not in GLOBAL_GATES]
            if invalid_mapped:
                errors.append(
                    f"row {idx}: mapped_global_gate_ids contains invalid gates: "
                    + ", ".join(invalid_mapped)
                )
            if mapped_gate_ids and gate_id not in mapped_gate_ids:
                errors.append(f"row {idx}: gate_id must be included in mapped_global_gate_ids")
            if local_check_id in R5_GATE_MAPPINGS:
                expected_mapping = R5_GATE_MAPPINGS[local_check_id]
                if mapped_gate_ids != expected_mapping:
                    errors.append(
                        f"row {idx}: {local_check_id} mapping must be "
                        + "|".join(expected_mapping)
                    )
                if gate_id != expected_mapping[0]:
                    errors.append(
                        f"row {idx}: {local_check_id} primary gate_id must be "
                        f"{expected_mapping[0]}"
                    )

        if row.get("blocking_decision") not in OUTCOMES:
            errors.append(f"row {idx}: blocking_decision is invalid: {row.get('blocking_decision')}")
        elif (
            not current_goal_schema
            and severity in {"critical", "high"}
            and row.get("blocking_decision") == "accepted"
        ):
            errors.append(f"row {idx}: high or critical severity cannot have accepted blocking_decision")

        if status == "waived_with_reason" and len(row.get("next_action", "")) < 8:
            errors.append(f"row {idx}: waived_with_reason requires visible reason in next_action")

        scoped_outcome = (
            _scoped_row_outcome(row, idx, errors) if current_goal_schema else None
        )
        if (
            current_goal_schema
            and scoped_outcome is not None
            and row.get("blocking_decision") in OUTCOMES
            and row.get("blocking_decision") != scoped_outcome
        ):
            errors.append(
                f"row {idx}: blocking_decision must be {scoped_outcome} "
                "for the current-goal fields"
            )
        if (
            current_goal_schema
            and status == "accepted_todo"
            and _parse_bool(row.get("blocks_current_goal", "")) is True
        ):
            errors.append(
                f"row {idx}: accepted_todo cannot have blocks_current_goal=true"
            )

        text = _row_text(row).lower()
        for pattern in ACTIVE_DEFECT_PATTERNS:
            if pattern in text and severity not in {"critical", "high"}:
                errors.append(f"row {idx}: {pattern} issues must be high or critical severity")
            if pattern in text and current_goal_schema:
                if row.get("active_disposition") != "active_defect":
                    errors.append(
                        f"row {idx}: {pattern} must use active_disposition=active_defect"
                    )
                if _parse_bool(row.get("blocks_current_goal", "")) is not True:
                    errors.append(
                        f"row {idx}: {pattern} must block the current goal"
                    )

    return errors


def derive_outcome(rows: list[dict[str, str]], errors: list[str]) -> str:
    if errors:
        return "blocked"
    if _uses_current_goal_schema(rows):
        row_outcomes: list[str] = []
        for idx, row in enumerate(rows):
            if not _is_active(row):
                continue
            outcome = _scoped_row_outcome(row, idx, [])
            if outcome:
                row_outcomes.append(outcome)
        if "blocked" in row_outcomes:
            return "blocked"
        if "needs_fix" in row_outcomes:
            return "needs_fix"
        if (
            "accepted_with_todos" in row_outcomes
            or any(row.get("status") == "accepted_todo" for row in rows)
        ):
            return "accepted_with_todos"
        return "accepted"

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
    parser.add_argument(
        "--require-current-goal",
        action="store_true",
        help="Reject legacy compatibility rows that omit current-goal issue fields",
    )
    args = parser.parse_args(argv)
    issues_path = args.issues_path or args.path
    if issues_path is None:
        parser.error("provide a path or --issues")

    try:
        rows = load_issues(issues_path)
        errors = validate_quality_issues(
            rows,
            args.expected_decision,
            require_current_goal=args.require_current_goal,
        )
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
