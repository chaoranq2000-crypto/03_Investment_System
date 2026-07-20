from __future__ import annotations

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_unblock_leverage_ranks_all_43_without_claiming_truth() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "review_acceleration/unblock_leverage.yaml").read_text(encoding="utf-8"))
    rows = payload["rankings"]
    assert payload["candidate_count"] == len(rows) == 43
    assert [row["rank"] for row in rows] == list(range(1, 44))
    assert [row["unblock_leverage_score"] for row in rows] == sorted((row["unblock_leverage_score"] for row in rows), reverse=True)
    assert payload["resolution_effect"].startswith("none_without")
