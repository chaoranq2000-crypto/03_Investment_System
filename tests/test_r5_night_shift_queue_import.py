from __future__ import annotations

import json
from pathlib import Path

from src.maintenance.night_shift.night03 import (
    EXPECTED_QUEUE_SHA256,
    EXPECTED_TOTAL_ITEMS,
    OUTPUT_ROOT,
    build_authoritative_queue_lock,
    source_queue_bytes,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_authoritative_queue_import_is_byte_exact_and_hash_locked() -> None:
    snapshot = REPO_ROOT / OUTPUT_ROOT / "queue/authoritative_queue_snapshot.yaml"
    assert snapshot.read_bytes() == source_queue_bytes(REPO_ROOT)
    lock_path = REPO_ROOT / OUTPUT_ROOT / "queue/authoritative_queue_lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    assert lock == build_authoritative_queue_lock(REPO_ROOT)
    assert lock["source_queue_sha256"] == EXPECTED_QUEUE_SHA256
    assert lock["task_count"] == EXPECTED_TOTAL_ITEMS
    assert lock["import_mode"] == "read_only_exact_hash"
