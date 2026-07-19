from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.maintenance.night_shift.night03 import Night03Error
from src.maintenance.night_shift.night03_decisions import validate_decision_manifest


def packet() -> dict:
    return {
        "evidence_id": "ev_001",
        "source_hash": "b" * 64,
        "source_class": "official_report",
        "claim_boundary": "Bounded fact only.",
        "counter_evidence": [],
    }


def test_exact_hash_validator_rejects_candidate_and_queue_tampering(
    night03_decision_factory,
) -> None:
    now = datetime(2026, 7, 20, tzinfo=timezone.utc)
    root, manifest, candidate_path, _ = night03_decision_factory(
        "evidence_acceptance", packet()
    )
    assert validate_decision_manifest(root, manifest, now=now)["valid"] is True
    candidate_path.write_text("tampered: true\n", encoding="utf-8")
    with pytest.raises(Night03Error, match="exact-hash mismatch"):
        validate_decision_manifest(root, manifest, now=now)
    manifest["source_queue_sha256"] = "0" * 64
    with pytest.raises(Night03Error, match="source_queue_sha256 mismatch"):
        validate_decision_manifest(root, manifest, now=now)
