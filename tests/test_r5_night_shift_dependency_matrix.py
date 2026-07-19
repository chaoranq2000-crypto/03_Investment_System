from __future__ import annotations

from pathlib import Path

import yaml

from src.maintenance.night_shift.night03 import OUTPUT_ROOT
from src.maintenance.night_shift.night03_backflow import build_dependency_matrix, packet_hash


def test_dependency_matrix_keeps_all_twenty_items_locked_to_real_receipts() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    expected = build_dependency_matrix(repo_root)
    actual = yaml.safe_load(
        (repo_root / OUTPUT_ROOT / "candidates/dependency_unlock_matrix.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert actual == expected
    assert actual["dependency_count"] == 20
    assert actual["unlocked_count"] == 0
    for item in actual["dependencies"]:
        assert item["current_status"] == "dependency_blocked"
        assert item["unlocked"] is False
        assert item["unresolved_prerequisite_count"] == len(item["prerequisites"])
        assert all(not prerequisite["resolved"] for prerequisite in item["prerequisites"])
        assert item["packet_sha256"] == packet_hash(item)
