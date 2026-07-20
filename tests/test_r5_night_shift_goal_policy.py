from __future__ import annotations

import json
from pathlib import Path

from src.maintenance.night_shift.night03 import OUTPUT_ROOT, build_truth_snapshot
from src.maintenance.night_shift.night04 import (
    OUTPUT_ROOT as NIGHT04_OUTPUT_ROOT,
    build_truth_snapshot as build_night04_truth_snapshot,
)
from src.maintenance.night_shift.outcome import MissionOutcome, ProgramGoalPolicy


def test_night02_cannot_close_long_term_program_goal() -> None:
    policy = ProgramGoalPolicy.from_mapping(
        {
            "id": "r5_bundle17r_bf2_four_case_activation",
            "close_allowed": False,
            "this_mission_may_close_goal": False,
        }
    )
    assert not policy.can_close(
        mission_outcome=MissionOutcome.DELIVERED,
        explicit_human_authority=True,
    )


def test_goal_close_requires_all_three_authority_conditions() -> None:
    policy = ProgramGoalPolicy.from_mapping(
        {
            "id": "future_goal",
            "close_allowed": True,
            "this_mission_may_close_goal": True,
        }
    )
    assert not policy.can_close(mission_outcome=MissionOutcome.DELIVERED)
    assert not policy.can_close(
        mission_outcome=MissionOutcome.PARTIAL,
        explicit_human_authority=True,
    )
    assert policy.can_close(
        mission_outcome=MissionOutcome.DELIVERED,
        explicit_human_authority=True,
    )


def test_night03_truth_snapshot_keeps_goal_and_downstream_gates_closed() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    expected = build_truth_snapshot(repo_root)
    path = repo_root / OUTPUT_ROOT / "queue/truth_snapshot.json"
    actual = json.loads(path.read_text(encoding="utf-8"))
    assert actual == expected
    assert actual["starting_truth"]["goal_state"] == "open_needs_targeted_backflow"
    assert actual["starting_truth"]["goal_close_allowed"] is False
    assert actual["starting_truth"]["sample_quality_allowed"] is False
    assert actual["starting_truth"]["p2_allowed"] is False
    assert actual["mission_delivery_may_close_program_goal"] is False


def test_night04_truth_snapshot_keeps_research_goal_open() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    expected = build_night04_truth_snapshot(repo_root)
    actual = json.loads((repo_root / NIGHT04_OUTPUT_ROOT / "queue/truth_snapshot.json").read_text(encoding="utf-8"))
    assert actual == expected
    assert actual["starting_truth"]["blocker_occurrences_resolved"] == 0
    assert actual["starting_truth"]["program_goal"] == "open_needs_targeted_backflow"
    assert actual["mission_delivery_may_close_program_goal"] is False
    assert actual["dry_run_is_resolution"] is False
