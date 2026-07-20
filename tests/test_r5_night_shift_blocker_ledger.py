from __future__ import annotations

import json
from pathlib import Path

from src.maintenance.night_shift.night03 import OUTPUT_ROOT
from src.maintenance.night_shift.night03_backflow import build_blocker_ledger
from src.maintenance.night_shift.night04 import OUTPUT_ROOT as NIGHT04_OUTPUT_ROOT
from src.maintenance.night_shift.night04_execution import (
    build_blocker_ledger as build_night04_blocker_ledger,
)
from src.maintenance.night_shift.receipts import canonical_json_bytes, sha256_bytes


def test_blocker_ledger_reports_zero_of_sixty_three_without_false_resolution() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    expected = build_blocker_ledger(repo_root)
    actual = json.loads(
        (repo_root / OUTPUT_ROOT / "progress/blocker_ledger.json").read_text(
            encoding="utf-8"
        )
    )
    assert actual == expected
    assert actual["blocker_occurrences_total"] == 63
    assert actual["blocker_occurrences_resolved_end"] == actual["resolved_delta"] == 0
    assert actual["status_counts"] == {"candidate_ready": 43, "dependency_blocked": 20}
    assert len(actual["occurrences"]) == 63
    assert not any(item["resolved"] for item in actual["occurrences"])
    assert actual["program_goal_state"] == "open_needs_targeted_backflow"
    supplied = actual.pop("stable_receipt_sha256")
    assert supplied == sha256_bytes(canonical_json_bytes(actual))


def test_night04_blocker_ledger_recomputes_exact_zero_resolution_truth() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    expected = build_night04_blocker_ledger(repo_root)
    actual = json.loads(
        (repo_root / NIGHT04_OUTPUT_ROOT / "progress/blocker_ledger.json").read_text(
            encoding="utf-8"
        )
    )
    assert actual == expected
    assert actual["blocker_occurrences_total"] == 63
    assert actual["blocker_occurrences_resolved_end"] == actual["resolved_delta"] == 0
    assert actual["status_counts"] == {"candidate_ready": 43, "dependency_blocked": 20}
    assert actual["parent_work_orders_resolved"] == 0
