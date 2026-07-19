from __future__ import annotations

from pathlib import Path

import yaml

from src.maintenance.night_shift.strategic import evaluate_semantic_fixture


def test_all_negative_semantic_fixtures_fail_for_the_declared_reason() -> None:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures/r5_night_shift/semantic_negative_cases.yaml"
    )
    payload = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    assert len(payload["fixtures"]) == 5
    for fixture in payload["fixtures"]:
        issues = evaluate_semantic_fixture(fixture)
        assert fixture["expected_issue"] in issues
        assert issues
