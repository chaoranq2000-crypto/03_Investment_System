from __future__ import annotations

import json
from pathlib import Path

from src.maintenance.night_shift.night04 import (
    EXPECTED_NIGHT03_FILE_COUNT,
    OUTPUT_ROOT,
    SOURCE_COMMIT,
    build_night03_input_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_night03_manifest_binds_exact_source_tree_blobs() -> None:
    expected = build_night03_input_manifest(REPO_ROOT)
    actual = json.loads((REPO_ROOT / OUTPUT_ROOT / "preflight/night03_input_manifest.json").read_text(encoding="utf-8"))
    assert actual == expected
    assert actual["source_commit"] == SOURCE_COMMIT
    assert actual["file_count"] == EXPECTED_NIGHT03_FILE_COUNT
    assert actual["hash_representation"] == "git_blob_bytes"
    assert all(len(item["git_blob_oid"]) == 40 for item in actual["files"])
