from __future__ import annotations

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
