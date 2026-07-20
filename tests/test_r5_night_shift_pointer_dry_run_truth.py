from __future__ import annotations

import json

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_dry_runs_neither_mutate_target_nor_resolve_occurrences() -> None:
    payload = json.loads((REPO_ROOT / OUTPUT_ROOT / "pointer_prevalidation/dry_run_truth_receipt.json").read_text(encoding="utf-8"))
    assert payload["pointer_dry_runs"] == 8
    assert payload["target_branch_pointer_changes"] == []
    assert payload["resolution_receipts_emitted"] == 0
    assert payload["resolved_delta"] == 0
    assert payload["passed"] is True
