from __future__ import annotations

import json

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_all_pointer_sandboxes_pass_exact_targeted_tests() -> None:
    payload = json.loads((REPO_ROOT / OUTPUT_ROOT / "pointer_prevalidation/targeted_test_receipts.json").read_text(encoding="utf-8"))
    assert payload["pointer_count"] == len(payload["receipts"]) == 8
    assert payload["all_passed"] is True
    assert all(item["exit_code"] == 0 and item["passed_tests"] == 4 for item in payload["receipts"])
    assert all(item["terminal_status"] == "passed" for item in payload["receipts"])
