from __future__ import annotations

import json

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from src.maintenance.night_shift.night04_validation import build_determinism_receipt
from tests.night04_test_support import REPO_ROOT


def test_night04_dashboard_ledger_and_queue_are_double_run_deterministic() -> None:
    dashboard_paths = [
        OUTPUT_ROOT / "review_acceleration/reviewer_dashboard.yaml",
        OUTPUT_ROOT / "review_acceleration/reviewer_dashboard.md",
        OUTPUT_ROOT / "review_acceleration/reviewer_dashboard.html",
    ]
    before = {path.as_posix(): (REPO_ROOT / path).read_bytes() for path in dashboard_paths}
    expected = build_determinism_receipt(REPO_ROOT)
    after = {path.as_posix(): (REPO_ROOT / path).read_bytes() for path in dashboard_paths}
    actual = json.loads(
        (REPO_ROOT / OUTPUT_ROOT / "validation/determinism_receipt.json").read_text(
            encoding="utf-8"
        )
    )
    assert actual == expected
    assert actual["all_bytes_equal"] is True
    assert actual["comparison_count"] == 3
    assert all(item["bytes_equal"] for item in actual["comparisons"])
    assert before == after
