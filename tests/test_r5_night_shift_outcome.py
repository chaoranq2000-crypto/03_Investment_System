from __future__ import annotations

from src.maintenance.night_shift.night03 import (
    Night03Outcome,
    evaluate_night03_outcome,
)
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


def test_night03_distinguishes_resolution_delta_from_candidate_ready_delivery() -> None:
    assert evaluate_night03_outcome(
        delivery_tasks_passed=True,
        resolved_delta=1,
        candidate_packets_complete=True,
    ) is Night03Outcome.DELIVERED_WITH_RESOLUTION_DELTA
    assert evaluate_night03_outcome(
        delivery_tasks_passed=True,
        resolved_delta=0,
        candidate_packets_complete=True,
    ) is Night03Outcome.DELIVERED_CANDIDATE_READY
    assert evaluate_night03_outcome(
        delivery_tasks_passed=True,
        resolved_delta=0,
        candidate_packets_complete=False,
    ) is Night03Outcome.PARTIAL
