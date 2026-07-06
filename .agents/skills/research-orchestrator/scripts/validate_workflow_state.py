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

    high_open = []
    for item in data.get("open_todos", []):
        if isinstance(item, dict) and item.get("severity") == "high" and item.get("status") != "closed":
            high_open.append(item.get("issue_id", "<unknown>"))

    if high_open and data["status"] in {"accepted", "accepted_with_todos"}:
        fail("accepted status is not allowed while high severity issues remain open: " + ", ".join(high_open))

    print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
