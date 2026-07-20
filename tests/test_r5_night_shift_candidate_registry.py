from __future__ import annotations

import hashlib
from collections import Counter

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from src.maintenance.night_shift.night04_review import EXPECTED_KIND_COUNTS

from tests.night04_test_support import REPO_ROOT


def test_candidate_registry_contains_43_unique_exact_hash_records() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "review_control/candidate_registry.yaml").read_text(encoding="utf-8"))
    candidates = payload["candidates"]
    assert payload["candidate_count"] == len(candidates) == 43
    assert len({item["occurrence_id"] for item in candidates}) == 43
    assert dict(Counter(item["candidate_kind"] for item in candidates)) == EXPECTED_KIND_COUNTS
    for item in candidates:
        packet = REPO_ROOT / item["review_packet_path"]
        assert hashlib.sha256(packet.read_bytes()).hexdigest() == item["review_packet_sha256"]
        assert all(item[field] is None for field in ("reviewer", "reviewer_authority", "reviewed_at", "decision"))
