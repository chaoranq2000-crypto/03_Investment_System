from __future__ import annotations

import json
import subprocess

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from src.maintenance.night_shift.night04_validation import build_morning_readout
from tests.night04_test_support import REPO_ROOT


def test_night04_morning_readout_distinguishes_delivery_from_resolution() -> None:
    expected = build_morning_readout(REPO_ROOT)
    actual = json.loads(
        (REPO_ROOT / OUTPUT_ROOT / "morning_readout.json").read_text(encoding="utf-8")
    )
    markdown = (REPO_ROOT / OUTPUT_ROOT / "morning_readout.md").read_text(
        encoding="utf-8"
    )
    assert actual == expected
    assert actual["mission_outcome"] == "delivered_review_acceleration_ready"
    assert actual["review_readiness"]["review_bundles_complete"] == 43
    assert actual["review_readiness"]["pointer_dry_runs_complete"] == 8
    assert actual["research_truth"]["blocker_occurrences_resolved"] == 0
    assert actual["research_truth"]["dependency_unlocked"] == 0
    assert actual["research_truth"]["work_orders_resolved"] == 0
    assert actual["research_truth"]["program_goal"] == "open_needs_targeted_backflow"
    assert "不表示研究计划完成" in markdown


def test_night04_publication_is_non_self_referential_and_carries_69_ids() -> None:
    tracked = json.loads(
        (REPO_ROOT / OUTPUT_ROOT / "publication/tracked_delivery_receipt.json").read_text(
            encoding="utf-8"
        )
    )
    queue = yaml.safe_load(
        (REPO_ROOT / OUTPUT_ROOT / "next_night_queue.yaml").read_text(encoding="utf-8")
    )
    remote_path = OUTPUT_ROOT / "publication/remote_delivery_receipt.json"
    tracked_remote = subprocess.run(
        ["git", "ls-files", "--error-unmatch", remote_path.as_posix()],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    assert tracked["final_publication_head"] is None
    assert tracked["final_publication_resolution_policy"] == "authoritative_post_push_remote_receipt"
    assert tracked_remote.returncode != 0
    assert queue["carry_forward"]["task_count"] == 69
    assert len({item["id"] for item in queue["tasks"]}) == 69
