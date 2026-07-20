from __future__ import annotations

from copy import deepcopy

from src.maintenance.night_shift.night04_review import validate_decision_batch

from tests.night04_test_support import FIXTURE_NOW, REPO_ROOT, valid_manifest


def test_conflicting_duplicate_decisions_reject_both_records() -> None:
    manifest, authorities = valid_manifest()
    conflict = deepcopy(manifest["records"][0])
    conflict["decision"] = "reject"
    manifest["records"].append(conflict)
    result = validate_decision_batch(REPO_ROOT, manifest, authority_registry=authorities, now=FIXTURE_NOW)
    assert result["accepted_count"] == 0
    assert result["invalid_count"] == 2
    assert {item["reason"] for item in result["invalid_records"]} == {"conflicting_duplicate"}
