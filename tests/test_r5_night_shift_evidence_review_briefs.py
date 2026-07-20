from __future__ import annotations

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_eight_evidence_briefs_keep_lineage_gaps_and_counterevidence() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "review_acceleration/evidence_review_briefs.yaml").read_text(encoding="utf-8"))
    assert payload["brief_count"] == 8
    assert all(item["source_lineage"] and item["uncertainties"] and item["counterevidence"] for item in payload["briefs"])
