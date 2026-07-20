from __future__ import annotations

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_eight_pointer_briefs_bind_paths_commands_and_hashes() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "review_acceleration/pointer_review_briefs.yaml").read_text(encoding="utf-8"))
    assert payload["brief_count"] == 8
    for item in payload["briefs"]:
        assert item["subject_summary"]["exact_paths"]
        assert item["subject_summary"]["acceptance_commands"]
        assert len(item["candidate_sha256"]) == len(item["review_packet_sha256"]) == 64
