from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.maintenance.night_shift.night03 import Night03Error
from src.maintenance.night_shift.night03_decisions import validate_decision_manifest


PACKET = {
    "evidence_id": "ev_002",
    "source_hash": "c" * 64,
    "source_class": "regulatory_source",
    "claim_boundary": "Cited regulatory fact.",
    "counter_evidence": [],
}


def test_authority_guard_rejects_machine_identity_wrong_owner_and_future_time(
    night03_decision_factory,
) -> None:
    now = datetime(2026, 7, 20, tzinfo=timezone.utc)
    root, manifest, _, _ = night03_decision_factory(
        "evidence_acceptance", PACKET, reviewer="codex-agent"
    )
    with pytest.raises(Night03Error, match="machine-generated"):
        validate_decision_manifest(root, manifest, now=now)
    manifest["decisions"][0]["reviewer"] = "Q Reviewer"
    manifest["decisions"][0]["reviewer_authority"] = "research_reviewer"
    with pytest.raises(Night03Error, match="does not match"):
        validate_decision_manifest(root, manifest, now=now)
    manifest["decisions"][0]["reviewer_authority"] = "evidence_reviewer"
    manifest["decisions"][0]["reviewed_at"] = "2026-07-21T00:00:00+00:00"
    with pytest.raises(Night03Error, match="future"):
        validate_decision_manifest(root, manifest, now=now)
