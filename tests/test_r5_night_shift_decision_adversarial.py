from __future__ import annotations

from pathlib import Path

from src.maintenance.night_shift.night03_validation import build_adversarial_matrix


def test_night03_adversarial_matrix_fails_closed_without_resolution() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    matrix = build_adversarial_matrix(repo_root)
    assert matrix["case_count"] == 7
    assert matrix["all_fail_closed"] is True
    assert matrix["resolved_delta"] == 0
    assert {item["result"] for item in matrix["cases"]} == {"rejected"}
