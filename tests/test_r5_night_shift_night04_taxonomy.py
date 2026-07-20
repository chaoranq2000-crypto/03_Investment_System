from __future__ import annotations

import json
from pathlib import Path

from src.maintenance.night_shift.night04 import OUTPUT_ROOT, build_taxonomy_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_night04_taxonomy_is_exactly_43_20_6_and_zero_resolved() -> None:
    actual = json.loads((REPO_ROOT / OUTPUT_ROOT / "queue/taxonomy_audit.json").read_text(encoding="utf-8"))
    assert actual == build_taxonomy_audit(REPO_ROOT)
    assert actual["night03_state_counts"] == {
        "candidate_ready": 43,
        "dependency_blocked": 20,
        "parent_pending": 6,
    }
    assert actual["occurrence_items"] == 63
    assert actual["passed"] is True
