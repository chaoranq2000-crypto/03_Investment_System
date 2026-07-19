from __future__ import annotations

from src.maintenance.night_shift.night03_decisions import resolution_eligibility


def test_candidate_ready_no_input_and_approval_without_receipt_never_resolve() -> None:
    for state in ("candidate_ready", "packet_generated", "no_input"):
        result = resolution_eligibility(
            {"occurrence_id": "occ_001", "decision": state}, None
        )
        assert result["resolved"] is False
        assert "decision_not_approved" in result["reasons"]
        assert "missing_independent_receipt" in result["reasons"]
    approved_only = resolution_eligibility(
        {
            "occurrence_id": "occ_001",
            "decision": "approved",
            "decision_digest_sha256": "a" * 64,
        },
        None,
    )
    assert approved_only["resolved"] is False
    assert approved_only["reasons"] == ["missing_independent_receipt"]
