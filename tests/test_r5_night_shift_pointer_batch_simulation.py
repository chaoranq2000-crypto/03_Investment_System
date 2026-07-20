from __future__ import annotations

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_non_overlapping_semantic_hunks_form_four_two_item_batches() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "pointer_prevalidation/batch_simulation.yaml").read_text(encoding="utf-8"))
    assert payload["pointer_count"] == 8
    assert payload["batch_count"] == 4
    assert payload["max_batch_size"] == 2
    assert sum(len(batch["occurrence_ids"]) for batch in payload["batches"]) == 8
    assert all(batch["execution_performed"] is False for batch in payload["batches"])
    assert payload["simulation_only"] is True
