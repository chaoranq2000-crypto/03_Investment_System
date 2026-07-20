from __future__ import annotations

import pytest

from src.maintenance.night_shift.night04 import Night04Error, Night04Outcome, evaluate_night04_outcome


def test_review_acceleration_ready_does_not_claim_resolution() -> None:
    outcome = evaluate_night04_outcome(
        delivery_tasks_passed=True,
        resolved_delta=0,
        independent_resolution_receipts=0,
        review_bundles_complete=43,
        pointer_dry_runs_complete=8,
    )
    assert outcome is Night04Outcome.DELIVERED_REVIEW_ACCELERATION_READY


def test_resolution_delta_requires_independent_receipts() -> None:
    with pytest.raises(Night04Error, match="receipt"):
        evaluate_night04_outcome(
            delivery_tasks_passed=True,
            resolved_delta=1,
            independent_resolution_receipts=0,
            review_bundles_complete=43,
            pointer_dry_runs_complete=8,
        )
