from __future__ import annotations

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_counterevidence_index_keeps_unknowns_visible_for_all_candidates() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "review_acceleration/counterevidence_index.yaml").read_text(encoding="utf-8"))
    assert payload["record_count"] == 43
    assert all(item["counterevidence"] and item["uncertainties"] for item in payload["records"])
