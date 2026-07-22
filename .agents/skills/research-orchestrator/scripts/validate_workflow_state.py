#!/usr/bin/env python3
"""Validate a minimal workflow_state.yaml file for research-orchestrator.

Usage:
    python .agents/skills/research-orchestrator/scripts/validate_workflow_state.py reports/workflow_runs/<workflow_id>/workflow_state.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: pip install pyyaml") from exc

REQUIRED_FIELDS = [
    "workflow_id",
    "workflow_type",
    "status",
    "created_at",
    "updated_at",
    "current_stage",
    "completed_stages",
    "next_stage",
    "active_skill",
    "required_next_skill",
    "evidence_snapshot",
    "claims_snapshot",
    "metrics_snapshot",
    "artifacts",
    "open_todos",
    "quality_gates",
]

VALID_WORKFLOW_TYPES = {
    "segment_to_stock_closed_loop",
    "stock_first_closed_loop",
    "segment_stock_interlock",
    "refresh_existing_research",
    "comparison_readiness_gate",
}

VALID_STATUSES = {
    "planned",
    "in_progress",
    "blocked",
    "needs_fix",
    "ready_for_review",
    "accepted",
    "accepted_with_todos",
    "archived",
}

V1_STATE_SCHEMA_VERSION = "r5_v1"
VALID_RUN_MODES = {"normal", "diagnostic"}
VALID_GATE_IDS = {f"G{i}" for i in range(11)}
VALID_GATE_STATUSES = {"pass", "fail", "not_checked", "not_applicable"}
VALID_TODO_SEVERITIES = {"high", "medium", "low"}
VALID_TODO_STATUSES = {"open", "in_progress", "blocked", "closed"}
CURRENT_ASSET_NAMES = (
    "workflow_state.yaml",
    "open_todos.csv",
    "quality_gate_report.md",
    "workflow_readout.md",
)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        fail(f"file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        fail("workflow_state.yaml must contain a YAML mapping")
    return data


def validate_v1_controls(data: dict[str, Any]) -> None:
    """Validate the active V1 control plane without rewriting legacy states."""

    if data.get("run_mode") not in VALID_RUN_MODES:
        fail(f"invalid or missing run_mode: {data.get('run_mode')}")

    seen_gate_ids: set[str] = set()
    for index, item in enumerate(data.get("quality_gates", [])):
        if not isinstance(item, dict):
            fail(f"quality_gates[{index}] must be a mapping")
        gate_id = item.get("gate_id")
        if gate_id not in VALID_GATE_IDS:
            fail(f"quality_gates[{index}].gate_id is not canonical G0-G10: {gate_id}")
        if gate_id in seen_gate_ids:
            fail(f"duplicate canonical quality gate: {gate_id}")
        seen_gate_ids.add(gate_id)

        gate_status = item.get("status")
        if gate_status not in VALID_GATE_STATUSES:
            fail(f"quality_gates[{index}].status is invalid: {gate_status}")

        local_check_id = item.get("local_check_id")
        mapped_gate_ids = item.get("mapped_global_gate_ids")
        if local_check_id:
            if not isinstance(mapped_gate_ids, list) or not mapped_gate_ids:
                fail(
                    f"quality_gates[{index}] local_check_id requires "
                    "mapped_global_gate_ids"
                )
            invalid_mapped = [gate for gate in mapped_gate_ids if gate not in VALID_GATE_IDS]
            if invalid_mapped:
                fail(
                    f"quality_gates[{index}].mapped_global_gate_ids contains "
                    f"non-canonical values: {', '.join(invalid_mapped)}"
                )
            if gate_id not in mapped_gate_ids:
                fail(
                    f"quality_gates[{index}].gate_id must be included in "
                    "mapped_global_gate_ids"
                )

    for index, item in enumerate(data.get("open_todos", [])):
        if not isinstance(item, dict):
            fail(f"open_todos[{index}] must be a mapping")
        for field in ("issue_id", "severity", "stage", "description", "fix_owner_skill", "status"):
            if not item.get(field):
                fail(f"open_todos[{index}].{field} is required")
        if item.get("severity") not in VALID_TODO_SEVERITIES:
            fail(f"open_todos[{index}].severity is invalid: {item.get('severity')}")
        if item.get("status") not in VALID_TODO_STATUSES:
            fail(f"open_todos[{index}].status is invalid: {item.get('status')}")
        todo_gate_id = item.get("gate_id")
        if todo_gate_id and todo_gate_id not in VALID_GATE_IDS:
            fail(f"open_todos[{index}].gate_id is not canonical G0-G10: {todo_gate_id}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip())
        return 2

    path = Path(argv[1])
    data = load_yaml(path)

    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        fail("missing required fields: " + ", ".join(missing))

    if data["workflow_type"] not in VALID_WORKFLOW_TYPES:
        fail(f"invalid workflow_type: {data['workflow_type']}")

    if data["status"] not in VALID_STATUSES:
        fail(f"invalid status: {data['status']}")

    if not isinstance(data["completed_stages"], list):
        fail("completed_stages must be a list")
    if not isinstance(data["artifacts"], list):
        fail("artifacts must be a list")
    if not isinstance(data["open_todos"], list):
        fail("open_todos must be a list")
    if not isinstance(data["quality_gates"], list):
        fail("quality_gates must be a list")

    schema_version = data.get("state_schema_version")
    if schema_version is not None and schema_version != V1_STATE_SCHEMA_VERSION:
        fail(f"unsupported state_schema_version: {schema_version}")
    if schema_version == V1_STATE_SCHEMA_VERSION:
        validate_v1_controls(data)

    high_open = []
    for item in data.get("open_todos", []):
        if isinstance(item, dict) and item.get("severity") == "high" and item.get("status") != "closed":
            high_open.append(item.get("issue_id", "<unknown>"))

    if high_open and data["status"] in {"accepted", "accepted_with_todos"}:
        fail("accepted status is not allowed while high severity issues remain open: " + ", ".join(high_open))

    compatibility = "" if schema_version == V1_STATE_SCHEMA_VERSION else " (legacy compatibility)"
    print(f"OK{compatibility}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
