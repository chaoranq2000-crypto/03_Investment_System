from __future__ import annotations

import json

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from src.maintenance.night_shift.night04_validation import build_crash_resume_receipt
from tests.night04_test_support import REPO_ROOT


def test_night04_checkpoint_resume_consumes_a_decision_once() -> None:
    expected = build_crash_resume_receipt()
    actual = json.loads(
        (REPO_ROOT / OUTPUT_ROOT / "validation/crash_resume_receipt.json").read_text(
            encoding="utf-8"
        )
    )
    assert actual == expected
    assert actual["first_consumed_count"] == 1
    assert actual["resumed_new_count"] == 0
    assert actual["resumed_replay_count"] == 1
    assert actual["replay_idempotent"] is True
