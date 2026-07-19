from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.maintenance.night_shift.night03 import Night03Error
from src.maintenance.night_shift.night03_decisions import validate_decision_manifest


def test_evidence_adapter_requires_reviewed_identity_source_class_and_claim_boundary(
    night03_decision_factory,
) -> None:
    packet = {
        "evidence_id": "ev_official_003",
        "source_hash": "d" * 64,
        "source_class": "reviewed_dataset",
        "claim_boundary": "Metric period and unit only.",
        "counter_evidence": ["Conflicting management commentary remains open."],
    }
    root, manifest, _, review_path = night03_decision_factory(
        "evidence_acceptance", packet
    )
    now = datetime(2026, 7, 20, tzinfo=timezone.utc)
    assert validate_decision_manifest(root, manifest, now=now)["valid"] is True
    packet["source_class"] = "search_result"
    review_path.write_text(__import__("yaml").safe_dump(packet), encoding="utf-8")
    manifest["decisions"][0]["review_packet_sha256"] = __import__("hashlib").sha256(
        review_path.read_bytes()
    ).hexdigest()
    with pytest.raises(Night03Error, match="source_class"):
        validate_decision_manifest(root, manifest, now=now)
