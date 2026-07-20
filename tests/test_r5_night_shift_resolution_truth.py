from __future__ import annotations

from src.maintenance.night_shift.night03 import EXPECTED_QUEUE_SHA256
from src.maintenance.night_shift.night03_decisions import resolution_eligibility
from src.maintenance.night_shift.night04_execution import build_blocker_ledger
from tests.night04_test_support import REPO_ROOT


def test_resolution_requires_matching_independent_passed_receipt() -> None:
    decision = {
        "occurrence_id": "occ_001",
        "decision": "approved",
        "decision_digest_sha256": "a" * 64,
    }
    receipt = {
        "occurrence_id": "occ_001",
        "decision_digest_sha256": "a" * 64,
        "terminal_status": "passed",
        "lineage_match": True,
        "resolution_claim_allowed": True,
        "source_queue_sha256": EXPECTED_QUEUE_SHA256,
    }
    assert resolution_eligibility(decision, receipt) == {
        "eligible": True,
        "resolved": True,
        "reasons": [],
    }
    receipt["lineage_match"] = False
    result = resolution_eligibility(decision, receipt)
    assert result["resolved"] is False
    assert "lineage_mismatch" in result["reasons"]


def test_night04_resolution_delta_remains_receipt_backed_and_zero() -> None:
    ledger = build_blocker_ledger(REPO_ROOT)
    assert ledger["blocker_occurrences_resolved_end"] == ledger["resolved_delta"] == 0
    assert not any(item["resolved"] for item in ledger["occurrences"])
    assert not any(item["resolution_receipt_sha256"] for item in ledger["occurrences"])
