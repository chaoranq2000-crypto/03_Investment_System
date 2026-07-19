from __future__ import annotations

from pathlib import Path

import yaml

from src.maintenance.night_shift.night03 import OUTPUT_ROOT
from src.maintenance.night_shift.night03_backflow import (
    build_analysis_candidates,
    packet_hash,
)


def test_twenty_four_analysis_candidates_preserve_unknowns_and_reviewer_boundary() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    expected = build_analysis_candidates(repo_root)
    actual = yaml.safe_load(
        (repo_root / OUTPUT_ROOT / "candidates/analysis_candidates.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert actual == expected
    assert actual["candidate_count"] == 24
    assert actual["accepted_count"] == actual["resolved_count"] == 0
    assert {item["company"] for item in actual["candidates"]} == {
        "铜冠铜箔",
        "药明康德",
        "赤峰黄金",
        "东阳光",
    }
    for item in actual["candidates"]:
        assert item["status"] == "candidate_pending_review"
        assert item["candidate_conclusion"] == "UNKNOWN_PENDING_EXTERNAL_ANALYST_REVIEW"
        assert item["quantitative_bridge"]["result"] == "MISSING"
        assert item["reviewer"] is item["decision"] is None
        assert item["counter_evidence"] == ["MISSING_REVIEWED_COUNTER_EVIDENCE"]
        assert item["packet_sha256"] == packet_hash(item)
