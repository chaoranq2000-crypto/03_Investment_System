from __future__ import annotations

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_first_parent_path_is_bounded_and_receipt_gated() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "review_acceleration/first_parent_path.yaml").read_text(encoding="utf-8"))
    selected = payload["selected_parent"]
    assert len(payload["parent_options"]) == 4
    assert selected["candidate_count"] == len(selected["candidate_ids"])
    assert selected["candidate_count"] > 0
    assert payload["simulation_only"] is True
    assert "independent" in payload["completion_rule"]
