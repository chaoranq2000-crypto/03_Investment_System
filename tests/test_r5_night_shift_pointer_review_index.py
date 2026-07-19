from __future__ import annotations

from pathlib import Path

import yaml

from src.maintenance.night_shift.night03 import OUTPUT_ROOT
from src.maintenance.night_shift.night03_backflow import build_pointer_index, packet_hash


def test_eight_pointer_proposals_have_exact_diff_ceilings_and_blank_approvals() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    expected = build_pointer_index(repo_root)
    actual = yaml.safe_load(
        (repo_root / OUTPUT_ROOT / "candidates/pointer_review_index.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert actual == expected
    assert actual["proposal_count"] == 8
    assert actual["approved_count"] == actual["resolved_count"] == 0
    assert actual["max_tasks_per_wave"] == 2
    for item in actual["proposals"]:
        assert item["exact_paths"]
        assert item["acceptance_commands"]
        assert item["diff_ceiling"]["allowed_paths"] == item["exact_paths"]
        assert not any(path.startswith("reports/p1_6/r5_bundle17r/") for path in item["exact_paths"])
        assert item["review_state"] == "proposed"
        assert item["reviewer"] is item["review_sha"] is item["decision"] is None
        assert item["packet_sha256"] == packet_hash(item)
