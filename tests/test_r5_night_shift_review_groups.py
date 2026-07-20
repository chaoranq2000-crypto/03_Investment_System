from __future__ import annotations

from collections import Counter

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from src.maintenance.night_shift.night04_review import EXPECTED_KIND_COUNTS
from tests.night04_test_support import REPO_ROOT


def test_review_groups_preserve_case_and_archetype_counts() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "review_acceleration/review_groups.yaml").read_text(encoding="utf-8"))
    assert payload["candidate_count"] == 43
    totals = Counter()
    for group in payload["groups"]:
        assert group["count"] == len(group["occurrence_ids"])
        totals[group["candidate_kind"]] += group["count"]
    assert dict(totals) == EXPECTED_KIND_COUNTS
