from __future__ import annotations

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_twenty_four_analysis_briefs_keep_falsifiable_unknowns() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "review_acceleration/analysis_review_briefs.yaml").read_text(encoding="utf-8"))
    assert payload["brief_count"] == 24
    assert all(item["subject_summary"]["falsification_condition"] for item in payload["briefs"])
    assert all(item["uncertainties"] for item in payload["briefs"])
