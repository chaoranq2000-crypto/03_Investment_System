from __future__ import annotations

import json
from pathlib import Path

from src.maintenance.night_shift.night04 import OUTPUT_ROOT, build_non_self_reference_audit


def test_final_remote_receipt_is_not_part_of_the_commit_it_identifies() -> None:
    root = Path(__file__).resolve().parents[1]
    actual = json.loads((root / OUTPUT_ROOT / "preflight/non_self_reference_audit.json").read_text(encoding="utf-8"))
    assert actual == build_non_self_reference_audit(root)
    assert actual["tracked_receipt_final_head"] is None
    assert actual["post_push_remote_receipt_tracked"] is False
    assert actual["passed"] is True
