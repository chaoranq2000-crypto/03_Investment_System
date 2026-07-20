from __future__ import annotations

import json
from pathlib import Path

from src.maintenance.night_shift.night03_validation import (
    build_adversarial_matrix as build_night03_adversarial_matrix,
)
from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from src.maintenance.night_shift.night04_validation import (
    build_adversarial_matrix as build_night04_adversarial_matrix,
)
from tests.night04_test_support import REPO_ROOT


def test_night03_adversarial_matrix_fails_closed_without_resolution() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    matrix = build_night03_adversarial_matrix(repo_root)
    assert matrix["case_count"] == 7
    assert matrix["all_fail_closed"] is True
    assert matrix["resolved_delta"] == 0
    assert {item["result"] for item in matrix["cases"]} == {"rejected"}


def test_night04_adversarial_matrix_fails_closed_without_resolution() -> None:
    expected = build_night04_adversarial_matrix(REPO_ROOT)
    actual = json.loads(
        (REPO_ROOT / OUTPUT_ROOT / "validation/adversarial_matrix.json").read_text(
            encoding="utf-8"
        )
    )
    assert actual == expected
    assert actual["all_fail_closed"] is True
    assert actual["case_count"] >= 10
    assert actual["resolved_delta"] == 0
    assert {item["result"] for item in actual["cases"]} == {"rejected"}
