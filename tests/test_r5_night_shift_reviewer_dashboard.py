from __future__ import annotations

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_dashboard_is_consistent_across_yaml_markdown_and_html() -> None:
    root = REPO_ROOT / OUTPUT_ROOT / "review_acceleration"
    payload = yaml.safe_load((root / "reviewer_dashboard.yaml").read_text(encoding="utf-8"))
    markdown = (root / "reviewer_dashboard.md").read_text(encoding="utf-8")
    html = (root / "reviewer_dashboard.html").read_text(encoding="utf-8")
    assert payload["review_candidates"] == len(payload["rankings"]) == 43
    assert payload["research_truth"]["resolved_occurrences"] == 0
    assert payload["ranking_is_research_confidence"] is False
    assert "0/63 resolved" in markdown
    assert "0/63 resolved" in html
    assert "<script" not in html.casefold()
