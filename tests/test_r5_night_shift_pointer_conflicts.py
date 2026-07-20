from __future__ import annotations

from collections import Counter

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_all_28_pointer_pairs_have_explicit_conflict_classification() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "pointer_prevalidation/conflict_matrix.yaml").read_text(encoding="utf-8"))
    assert payload["pair_count"] == len(payload["pairs"]) == 28
    counts = Counter(item["conflict_type"] for item in payload["pairs"])
    assert counts["duplicate_semantic_change"] == 12
    assert counts["shared_files_non_overlapping_hunks"] == 16
    assert all(item["shared_paths"] for item in payload["pairs"])
