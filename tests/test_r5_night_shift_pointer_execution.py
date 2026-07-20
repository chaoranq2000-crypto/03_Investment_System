from __future__ import annotations

import json

import pytest

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from src.maintenance.night_shift.night04_execution import (
    Night04ExecutionError,
    execute_typed_adapter,
)
from tests.night04_test_support import REPO_ROOT


def test_pointer_adapter_stays_idle_without_external_approval() -> None:
    artifact = json.loads(
        (REPO_ROOT / OUTPUT_ROOT / "execution/pointer_execution_receipts.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifact["candidate_kind"] == "engineering_local_pointer"
    assert artifact["approved_input_count"] == artifact["executed_count"] == 0
    assert artifact["independent_resolution_receipt_count"] == artifact["resolved_count"] == 0


def test_pointer_executor_cannot_report_a_target_branch_change() -> None:
    decision = {
        "occurrence_id": "synthetic_pointer_fixture",
        "candidate_kind": "engineering_local_pointer",
        "decision": "approve",
        "decision_digest_sha256": "d" * 64,
    }
    with pytest.raises(Night04ExecutionError, match="target branch"):
        execute_typed_adapter(
            REPO_ROOT,
            [decision],
            candidate_kind="engineering_local_pointer",
            executor=lambda _: {
                "sandboxed": True,
                "target_branch_changed": True,
                "implementation_tree_sha": "e" * 40,
                "terminal_status": "passed",
                "lineage_match": True,
                "resolution_claim_allowed": True,
            },
        )
