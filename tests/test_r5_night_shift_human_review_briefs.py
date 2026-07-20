from __future__ import annotations

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_three_human_briefs_do_not_prepopulate_decisions() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "review_acceleration/human_review_briefs.yaml").read_text(encoding="utf-8"))
    assert payload["brief_count"] == 3
    assert all(item["reviewer_fields_machine_empty"] is True for item in payload["briefs"])
    assert all(item["subject_summary"]["automatic_change"] == "none" for item in payload["briefs"])
