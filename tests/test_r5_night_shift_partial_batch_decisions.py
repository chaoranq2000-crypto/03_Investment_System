from __future__ import annotations

from copy import deepcopy

from src.maintenance.night_shift.night04_review import validate_decision_batch

from tests.night04_test_support import FIXTURE_NOW, REPO_ROOT, valid_manifest


def test_partial_batch_accepts_only_individually_valid_records() -> None:
    first, first_authority = valid_manifest(0)
    second, second_authority = valid_manifest(1)
    bad = deepcopy(second["records"][0])
    bad["review_packet_sha256"] = "f" * 64
    first["records"].append(bad)
    result = validate_decision_batch(REPO_ROOT, first, authority_registry=first_authority | second_authority, now=FIXTURE_NOW)
    assert result["input_count"] == 2
    assert result["accepted_count"] == 1
    assert result["invalid_count"] == 1
    assert result["invalid_records"][0]["reason"] == "stale_review_packet_hash"
