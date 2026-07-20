from __future__ import annotations

import json

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from src.maintenance.night_shift.night04_execution import execute_typed_adapter
from tests.night04_test_support import REPO_ROOT


def test_evidence_adapter_stays_idle_without_external_approval() -> None:
    artifact = json.loads(
        (REPO_ROOT / OUTPUT_ROOT / "execution/evidence_execution_receipts.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifact["candidate_kind"] == "evidence_required"
    assert artifact["approved_input_count"] == artifact["executed_count"] == 0
    assert artifact["independent_resolution_receipt_count"] == artifact["resolved_count"] == 0
    assert artifact["outcome"] == "blocked_external_no_approved_decisions"


def test_evidence_approval_alone_does_not_create_a_receipt() -> None:
    decision = {
        "occurrence_id": "synthetic_evidence_fixture",
        "candidate_kind": "evidence_required",
        "decision": "approve",
        "decision_digest_sha256": "a" * 64,
    }
    result = execute_typed_adapter(
        REPO_ROOT,
        [decision],
        candidate_kind="evidence_required",
    )
    assert result["approved_input_count"] == 1
    assert result["executed_count"] == result["resolved_count"] == 0
    assert result["pending_occurrence_ids"] == ["synthetic_evidence_fixture"]
