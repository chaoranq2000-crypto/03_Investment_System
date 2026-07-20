from __future__ import annotations

from src.maintenance.night_shift.night04_review import validate_decision_batch

from tests.night04_test_support import FIXTURE_NOW, REPO_ROOT, valid_manifest


def test_stale_candidate_hash_rejects_entire_record() -> None:
    manifest, authorities = valid_manifest()
    manifest["records"][0]["candidate_sha256"] = "0" * 64
    result = validate_decision_batch(REPO_ROOT, manifest, authority_registry=authorities, now=FIXTURE_NOW)
    assert result["accepted_count"] == 0
    assert result["invalid_records"][0]["reason"] == "stale_candidate_hash"
