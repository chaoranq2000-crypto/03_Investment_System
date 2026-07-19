from __future__ import annotations

from src.maintenance.night_shift.outcome import MissionOutcome, outcome_for_pilot_evidence


def test_no_safe_pilot_is_blocking_evidence_not_a_passed_task() -> None:
    assert outcome_for_pilot_evidence("no_safe_pilot") is MissionOutcome.BLOCKED
    assert MissionOutcome.DELIVERED not in {
        outcome_for_pilot_evidence("no_safe_pilot"),
        outcome_for_pilot_evidence(
            "no_safe_pilot", delivery_work_already_passed=True
        ),
    }
