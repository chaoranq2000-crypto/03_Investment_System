from __future__ import annotations

from src.maintenance.night_shift.night04_review import validate_decision_batch

from tests.night04_test_support import FIXTURE_NOW, REPO_ROOT, valid_manifest


def test_reviewer_authority_must_be_confirmed_by_external_registry() -> None:
    manifest, _ = valid_manifest()
    result = validate_decision_batch(REPO_ROOT, manifest, authority_registry=set(), now=FIXTURE_NOW)
    assert result["accepted_count"] == 0
    assert result["invalid_records"][0]["reason"] == "reviewer_authority_not_externally_verified"
