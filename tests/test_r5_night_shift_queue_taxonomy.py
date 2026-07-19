from __future__ import annotations

import json
from pathlib import Path

from src.maintenance.night_shift.night03 import (
    EXPECTED_OCCURRENCES,
    EXPECTED_PARENTS,
    EXPECTED_TAXONOMY,
    OUTPUT_ROOT,
    build_taxonomy_audit,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_night03_queue_preserves_all_occurrences_parents_and_taxonomy() -> None:
    expected = build_taxonomy_audit(REPO_ROOT)
    path = REPO_ROOT / OUTPUT_ROOT / "queue/taxonomy_audit.json"
    actual = json.loads(path.read_text(encoding="utf-8"))
    assert actual == expected
    assert actual["occurrence_items"] == EXPECTED_OCCURRENCES
    assert actual["parent_aggregators"] == EXPECTED_PARENTS
    assert actual["occurrence_taxonomy"] == EXPECTED_TAXONOMY
    assert actual["unknown_occurrence_ids"] == []
    assert actual["passed"] is True
