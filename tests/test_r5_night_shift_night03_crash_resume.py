from __future__ import annotations

from datetime import datetime, timezone

from src.maintenance.night_shift.night03_validation import (
    build_crash_resume_receipt,
    cutoff_claim_policy,
)


def test_late_external_decision_resumes_once_without_duplicate_consumption() -> None:
    receipt = build_crash_resume_receipt()
    assert receipt["external_gate_preserved"] is True
    assert receipt["late_decision_resume_status"] == "resolved"
    assert receipt["replay_byte_equivalent"] is True
    assert receipt["attempt_count_after_replay"] == 1


def test_cutoff_stops_new_claims_but_keeps_inflight_acceptance() -> None:
    cutoff = datetime(2026, 7, 21, 5, 15, tzinfo=timezone.utc)
    after = datetime(2026, 7, 21, 5, 16, tzinfo=timezone.utc)
    assert cutoff_claim_policy(now=after, cutoff=cutoff, in_flight=False) == "do_not_claim_new_task"
    assert cutoff_claim_policy(now=after, cutoff=cutoff, in_flight=True) == "finish_in_flight"
