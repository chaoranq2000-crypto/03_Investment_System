from __future__ import annotations

import json

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from src.maintenance.night_shift.night04_execution import execute_typed_adapter
from tests.night04_test_support import REPO_ROOT


def test_analysis_adapter_stays_idle_without_external_approval() -> None:
    artifact = json.loads(
        (REPO_ROOT / OUTPUT_ROOT / "execution/analysis_execution_receipts.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifact["candidate_kind"] == "analysis_required"
    assert artifact["approved_input_count"] == artifact["executed_count"] == 0
    assert artifact["independent_resolution_receipt_count"] == artifact["resolved_count"] == 0
    assert artifact["outcome"] == "blocked_external_no_approved_decisions"


def test_analysis_adapter_filters_other_decision_kinds() -> None:
    result = execute_typed_adapter(
        REPO_ROOT,
        [
            {
                "occurrence_id": "synthetic_fixture",
                "candidate_kind": "evidence_required",
                "decision": "approve",
                "decision_digest_sha256": "b" * 64,
            }
        ],
        candidate_kind="analysis_required",
    )
    assert result["approved_input_count"] == 0
    assert result["resolved_count"] == 0
