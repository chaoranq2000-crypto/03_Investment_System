from __future__ import annotations

import json
from pathlib import Path

from src.maintenance.night_shift.night03 import (
    EXPECTED_NIGHT02_FILE_COUNT,
    OUTPUT_ROOT,
    SOURCE_COMMIT,
    build_night02_input_manifest,
)
from src.maintenance.night_shift.receipts import canonical_json_bytes, sha256_bytes


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_night02_manifest_binds_every_physical_file_and_source_commit() -> None:
    expected = build_night02_input_manifest(REPO_ROOT)
    path = REPO_ROOT / OUTPUT_ROOT / "preflight/night02_input_manifest.json"
    actual = json.loads(path.read_text(encoding="utf-8"))
    assert actual == expected
    assert actual["source_commit"] == SOURCE_COMMIT
    assert actual["file_count"] == EXPECTED_NIGHT02_FILE_COUNT
    paths = {item["path"] for item in actual["files"]}
    assert any(path.endswith("mission_completion_receipt.json") for path in paths)
    assert any(path.endswith("next_night_queue.yaml") for path in paths)
    supplied = actual.pop("stable_receipt_sha256")
    assert supplied == sha256_bytes(canonical_json_bytes(actual))
