from __future__ import annotations

from src.maintenance.night_shift.outcome import (
    MissionOutcome,
    evaluate_mission_outcome,
    outcome_for_pilot_evidence,
)


def task(status: str, *, required: bool = True) -> dict:
    return {"status": status, "delivery_required": required}


def test_delivered_requires_all_required_tasks_and_publication() -> None:
    tasks = [task("passed"), task("passed"), task("pending", required=False)]
    assert evaluate_mission_outcome(
        tasks,
        branch_pushed=True,
        remote_sha_matches=True,
        ci_verified=True,
    ) is MissionOutcome.DELIVERED
    assert evaluate_mission_outcome(
        tasks,
        branch_pushed=True,
        remote_sha_matches=True,
        ci_verified=False,
    ) is MissionOutcome.PARTIAL


def test_blocked_failed_and_cutoff_are_not_delivered() -> None:
    assert evaluate_mission_outcome(
        [task("evidence_required")],
        branch_pushed=False,
        remote_sha_matches=False,
        ci_verified=False,
    ) is MissionOutcome.BLOCKED
    assert evaluate_mission_outcome(
        [task("failed_terminal")],
        branch_pushed=False,
        remote_sha_matches=False,
        ci_verified=False,
    ) is MissionOutcome.FAILED
    assert evaluate_mission_outcome(
        [task("running")],
        branch_pushed=False,
        remote_sha_matches=False,
        ci_verified=False,
        cutoff_reached=True,
    ) is MissionOutcome.CUTOFF


def test_no_safe_pilot_never_maps_to_success() -> None:
    assert outcome_for_pilot_evidence("no_safe_pilot") is MissionOutcome.BLOCKED
    assert outcome_for_pilot_evidence(
        "no_safe_pilot", delivery_work_already_passed=True
    ) is MissionOutcome.PARTIAL
