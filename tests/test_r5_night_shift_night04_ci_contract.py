from __future__ import annotations

import json

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from src.maintenance.night_shift.night04_validation import build_ci_contract
from tests.night04_test_support import REPO_ROOT


def test_night04_ci_covers_full_tests_routes_and_all_historical_roots() -> None:
    expected = build_ci_contract(REPO_ROOT)
    path = REPO_ROOT / OUTPUT_ROOT / "validation/ci_contract.json"
    if path.is_file():
        assert json.loads(path.read_text(encoding="utf-8")) == expected
    assert expected["passed"] is True
    assert all(expected["checks"].values())
