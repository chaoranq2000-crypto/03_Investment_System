from __future__ import annotations

import json

from src.maintenance.night_shift.night04 import OUTPUT_ROOT

from tests.night04_test_support import REPO_ROOT


def test_machine_owned_human_fields_remain_empty() -> None:
    receipt = json.loads((REPO_ROOT / OUTPUT_ROOT / "review_control/human_field_integrity.json").read_text(encoding="utf-8"))
    assert receipt["bundle_count"] == 43
    assert receipt["violations"] == []
    assert receipt["passed"] is True
