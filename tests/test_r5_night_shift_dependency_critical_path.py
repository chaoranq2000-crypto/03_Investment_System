from __future__ import annotations

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_max_unlock_path_covers_20_dependencies_but_unlocks_none() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "review_acceleration/max_unlock_path.yaml").read_text(encoding="utf-8"))
    assert payload["candidate_count"] == len(payload["steps"]) == 43
    assert payload["dependency_universe_count"] == 20
    assert all(step["actual_dependencies_unlocked"] == 0 for step in payload["steps"])
    assert payload["simulation_only"] is True
