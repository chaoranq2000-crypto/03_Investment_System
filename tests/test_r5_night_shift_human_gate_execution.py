from __future__ import annotations

import json

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from src.maintenance.night_shift.night04_execution import execute_typed_adapter
from tests.night04_test_support import REPO_ROOT


def test_human_gate_adapter_never_manufactures_approval() -> None:
    artifact = json.loads(
        (REPO_ROOT / OUTPUT_ROOT / "execution/human_gate_receipts.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifact["candidate_kind"] == "human_exact_hash_gate"
    assert artifact["approved_input_count"] == artifact["executed_count"] == 0
    assert artifact["receipts"] == []
    assert artifact["resolved_count"] == 0


def test_rejected_human_decision_is_not_executable() -> None:
    result = execute_typed_adapter(
        REPO_ROOT,
        [
            {
                "occurrence_id": "synthetic_human_fixture",
                "candidate_kind": "human_exact_hash_gate",
                "decision": "reject",
                "decision_digest_sha256": "c" * 64,
            }
        ],
        candidate_kind="human_exact_hash_gate",
    )
    assert result["approved_input_count"] == result["executed_count"] == 0
