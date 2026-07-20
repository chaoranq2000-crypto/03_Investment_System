from __future__ import annotations

import json
from pathlib import Path

from src.maintenance.night_shift.night03 import (
    EXPECTED_QUEUE_SHA256,
    OUTPUT_ROOT,
    SOURCE_COMMIT,
    build_lineage_audit,
)
from src.maintenance.night_shift.night04 import (
    OUTPUT_ROOT as NIGHT04_OUTPUT_ROOT,
    build_lineage_audit as build_night04_lineage_audit,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_lineage_guard_verifies_bound_hashes_and_keeps_unknowns_visible() -> None:
    expected = build_lineage_audit(REPO_ROOT)
    path = REPO_ROOT / OUTPUT_ROOT / "queue/lineage_audit.json"
    actual = json.loads(path.read_text(encoding="utf-8"))
    assert actual == expected
    assert actual["source_commit"] == SOURCE_COMMIT
    assert actual["source_queue_sha256"] == EXPECTED_QUEUE_SHA256
    assert actual["task_count"] == 69
    assert actual["verified_count"] + actual["explicit_unknown_count"] + actual[
        "parent_aggregator_count"
    ] == 69
    assert actual["mismatch_task_ids"] == []
    assert actual["stale_decision_policy"] == "invalidate_on_any_bound_hash_change"
    assert actual["passed"] is True


def test_night04_lineage_guard_rechecks_all_69_stable_items() -> None:
    expected = build_night04_lineage_audit(REPO_ROOT)
    actual = json.loads((REPO_ROOT / NIGHT04_OUTPUT_ROOT / "queue/lineage_audit.json").read_text(encoding="utf-8"))
    assert actual == expected
    assert actual["task_count"] == 69
    assert actual["mismatch_task_ids"] == []
    assert actual["historical_paths_mutable"] is False
