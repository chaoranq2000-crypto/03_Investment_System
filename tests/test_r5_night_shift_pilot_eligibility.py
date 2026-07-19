from __future__ import annotations

from src.maintenance.night_shift.contracts import (
    authorize_packaged_task,
    pilot_eligibility,
)
from src.maintenance.night_shift.models import Task
from src.maintenance.night_shift.outcome import MissionOutcome, outcome_for_pilot_evidence

from tests.test_r5_night_shift_contract import task


def test_no_safe_pilot_is_blocking_evidence_not_a_passed_task() -> None:
    assert outcome_for_pilot_evidence("no_safe_pilot") is MissionOutcome.BLOCKED
    assert MissionOutcome.DELIVERED not in {
        outcome_for_pilot_evidence("no_safe_pilot"),
        outcome_for_pilot_evidence(
            "no_safe_pilot", delivery_work_already_passed=True
        ),
    }


def test_only_approved_linted_contract_is_pilot_eligible() -> None:
    base = Task.from_mapping(task("ns02_t39_pilot_eligibility"), path="task")
    proposed = pilot_eligibility(base, review_packet=None)
    assert proposed["eligible"] is False
    assert proposed["status"] == "blocked_external"

    approved = authorize_packaged_task(base, package_digest_sha256="a" * 64)
    eligible = pilot_eligibility(approved, review_packet=None)
    assert eligible["eligible"] is True
    assert eligible["resolution_claim_allowed"] is False
