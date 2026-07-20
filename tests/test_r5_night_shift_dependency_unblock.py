from __future__ import annotations

from pathlib import Path

import json

from src.maintenance.night_shift.night03 import authoritative_queue
from src.maintenance.night_shift.night03_execution import (
    dependency_unlock,
    validate_dependency_graph,
)
from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from src.maintenance.night_shift.night04_execution import build_dependency_recompute


def test_dependency_unlock_requires_every_real_prerequisite_resolution() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    tasks = authoritative_queue(repo_root)["tasks"]
    audit = validate_dependency_graph(tasks)
    assert audit["passed"] is True
    dependency = next(item for item in tasks if item["work_type"] == "dependency_blocked")
    states = {item: {"status": "resolved"} for item in dependency["depends_on"]}
    first = dependency["depends_on"][0]
    states[first] = {"status": "candidate_ready"}
    blocked = dependency_unlock(dependency, states)
    assert blocked["unlocked"] is False
    assert blocked["unresolved_prerequisites"] == [first]
    states[first] = {"status": "resolved"}
    unlocked = dependency_unlock(dependency, states)
    assert unlocked["unlocked"] is True
    assert unlocked["next_status"] == "pending"


def test_night04_dependency_recompute_unlocks_none_without_atomic_receipts() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    expected = build_dependency_recompute(repo_root)
    actual = json.loads(
        (repo_root / OUTPUT_ROOT / "execution/dependency_recompute.json").read_text(
            encoding="utf-8"
        )
    )
    assert actual == expected
    assert actual["dependency_count"] == actual["blocked_count"] == 20
    assert actual["unlocked_count"] == actual["resolved_count"] == 0
