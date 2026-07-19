from __future__ import annotations

from src.maintenance.night_shift.night03 import EXPECTED_QUEUE_SHA256
from src.maintenance.night_shift.night03_decisions import resolution_eligibility


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
