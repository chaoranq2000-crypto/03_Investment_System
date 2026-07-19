from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest
import yaml

from src.maintenance.night_shift.night03 import Night03Error
from src.maintenance.night_shift.night03_decisions import validate_decision_manifest


def test_human_gate_review_is_invalidated_by_candidate_rerender(
    night03_decision_factory,
) -> None:
    packet = {
        "gate_id": "bundle17r_suite_hash_review",
        "candidate_artifact_sha256": "placeholder",
        "generation_lock_sha256": "e" * 64,
    }
    root, manifest, candidate_path, review_path = night03_decision_factory(
        "human_exact_hash", packet
    )
    candidate_hash = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    packet["candidate_artifact_sha256"] = candidate_hash
    review_path.write_text(yaml.safe_dump(packet, sort_keys=True), encoding="utf-8")
    manifest["decisions"][0]["review_packet_sha256"] = hashlib.sha256(
        review_path.read_bytes()
    ).hexdigest()
    now = datetime(2026, 7, 20, tzinfo=timezone.utc)
    assert validate_decision_manifest(root, manifest, now=now)["valid"] is True
    candidate_path.write_text("rerendered: true\n", encoding="utf-8")
    with pytest.raises(Night03Error, match="exact-hash mismatch"):
        validate_decision_manifest(root, manifest, now=now)
