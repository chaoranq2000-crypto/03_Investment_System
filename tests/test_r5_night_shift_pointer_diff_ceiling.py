from __future__ import annotations

import json

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_each_pointer_dry_run_stays_within_two_path_ceiling() -> None:
    payload = json.loads((REPO_ROOT / OUTPUT_ROOT / "pointer_prevalidation/diff_ceiling_receipt.json").read_text(encoding="utf-8"))
    assert payload["pointer_count"] == 8
    assert payload["all_passed"] is True
    assert all(0 < item["changed_path_count"] <= item["diff_ceiling"] == 2 for item in payload["records"])
