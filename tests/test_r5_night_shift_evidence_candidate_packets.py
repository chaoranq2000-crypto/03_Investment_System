from __future__ import annotations

from pathlib import Path

import yaml

from src.maintenance.night_shift.night03 import OUTPUT_ROOT
from src.maintenance.night_shift.night03_backflow import (
    build_evidence_candidates,
    packet_hash,
)


def test_eight_evidence_candidates_are_hash_locked_reviewable_and_not_accepted() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    expected = build_evidence_candidates(repo_root)
    actual = yaml.safe_load(
        (repo_root / OUTPUT_ROOT / "candidates/evidence_candidates.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert actual == expected
    assert actual["candidate_count"] == 8
    assert actual["accepted_count"] == actual["resolved_count"] == 0
    for item in actual["candidates"]:
        assert item["status"] == "candidate_pending_review"
        assert item["reviewer"] is item["decision"] is None
        assert item["visible_gaps"]
        assert item["conflict_evidence_status"] == "UNKNOWN_NOT_REVIEWED"
        assert all(source["hash_verified"] for source in item["candidate_source_paths"])
        assert item["packet_sha256"] == packet_hash(item)
