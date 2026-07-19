from __future__ import annotations

from pathlib import Path

import yaml

from src.maintenance.night_shift.night03 import OUTPUT_ROOT
from src.maintenance.night_shift.night03_backflow import build_four_case_dashboard


def test_dashboard_reports_each_golden_case_without_hiding_gaps_in_a_score() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    expected = build_four_case_dashboard(repo_root)
    actual = yaml.safe_load(
        (repo_root / OUTPUT_ROOT / "progress/four_case_dashboard.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert actual == expected
    assert actual["case_count"] == 4
    assert actual["score_aggregation_used"] is False
    assert {item["company"] for item in actual["cases"]} == {
        "铜冠铜箔",
        "药明康德",
        "赤峰黄金",
        "东阳光",
    }
    for item in actual["cases"]:
        assert item["approved_count"] == item["resolved_count"] == 0
        assert item["candidate_ready_count"] + item["dependency_blocked_count"] == item[
            "occurrence_count"
        ]
        assert item["next_actions"]
