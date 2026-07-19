from __future__ import annotations

from pathlib import Path

import yaml

from src.maintenance.night_shift.night03 import OUTPUT_ROOT, sha256_file
from src.maintenance.night_shift.night03_backflow import build_human_handoffs, packet_hash


def test_three_human_handoffs_rebind_physical_hashes_without_filling_review_fields() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    expected = build_human_handoffs(repo_root)
    actual = yaml.safe_load(
        (repo_root / OUTPUT_ROOT / "candidates/human_gate_handoffs.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert actual == expected
    assert actual["handoff_count"] == 3
    assert actual["approved_count"] == actual["resolved_count"] == 0
    for item in actual["handoffs"]:
        assert sha256_file(repo_root / item["candidate_artifact_path"]) == item[
            "candidate_artifact_sha256"
        ]
        assert item["reviewer"] is item["reviewed_at"] is item["decision"] is None
        assert item["auto_accept_allowed"] is False
        assert item["packet_sha256"] == packet_hash(item)
