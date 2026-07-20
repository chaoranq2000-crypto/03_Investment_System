from __future__ import annotations

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_downstream_impact_is_complete_and_does_not_claim_resolution() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "review_acceleration/downstream_impact.yaml").read_text(encoding="utf-8"))
    assert payload["record_count"] == 43
    assert payload["resolution_delta"] == 0
    assert all(item["resolution_effect"] == "recompute_from_independent_receipt_only" for item in payload["records"])
