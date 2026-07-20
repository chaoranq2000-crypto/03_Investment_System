from __future__ import annotations

import json

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_every_patch_has_a_verified_exact_reverse_plan() -> None:
    payload = json.loads((REPO_ROOT / OUTPUT_ROOT / "pointer_prevalidation/rollback_receipt.json").read_text(encoding="utf-8"))
    assert payload["pointer_count"] == len(payload["records"]) == 8
    assert payload["all_reverse_checks_passed"] is True
    assert all(item["reverse_check_passed"] is True for item in payload["records"])
    assert all(item["strategy"] == "git_apply_reverse_exact_patch" for item in payload["records"])
