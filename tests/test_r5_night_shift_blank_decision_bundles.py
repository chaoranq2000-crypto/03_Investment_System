from __future__ import annotations

import hashlib

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT

from tests.night04_test_support import REPO_ROOT


def test_blank_bundle_index_binds_43_empty_forms() -> None:
    index = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "review_control/blank_decision_bundles/index.yaml").read_text(encoding="utf-8"))
    assert index["bundle_count"] == 43
    for entry in index["bundles"]:
        path = REPO_ROOT / entry["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
        record = yaml.safe_load(path.read_text(encoding="utf-8"))["records"][0]
        assert all(record[field] is None for field in ("reviewer", "reviewer_authority", "reviewed_at", "decision"))
