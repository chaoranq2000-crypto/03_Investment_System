from __future__ import annotations

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_diff_index_binds_evidence_claim_subject_and_exact_hashes() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "review_acceleration/evidence_claim_diff_index.yaml").read_text(encoding="utf-8"))
    assert payload["record_count"] == 43
    assert all(item["source_lineage"] and item["subject_summary"] for item in payload["records"])
    assert all(len(item["candidate_sha256"]) == 64 for item in payload["records"])
