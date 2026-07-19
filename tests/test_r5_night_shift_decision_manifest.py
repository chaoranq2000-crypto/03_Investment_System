from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.maintenance.night_shift.night03 import OUTPUT_ROOT
from src.maintenance.night_shift.night03_decisions import (
    DECISION_KINDS,
    decision_manifest_schema,
    validate_decision_manifest,
)


def evidence_packet() -> dict:
    return {
        "evidence_id": "ev_official_001",
        "source_hash": "a" * 64,
        "source_class": "official_disclosure",
        "claim_boundary": "Only the cited operating fact is accepted.",
        "counter_evidence": [],
    }


def test_decision_schema_covers_all_four_external_authority_kinds(
    night03_decision_factory,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    artifact = json.loads(
        (repo_root / OUTPUT_ROOT / "decisions/decision_manifest_schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifact == decision_manifest_schema()
    enum = artifact["properties"]["decisions"]["items"]["properties"]["decision_kind"]["enum"]
    assert enum == sorted(DECISION_KINDS)
    root, manifest, _, _ = night03_decision_factory(
        "evidence_acceptance", evidence_packet()
    )
    result = validate_decision_manifest(
        root, manifest, now=datetime(2026, 7, 20, tzinfo=timezone.utc)
    )
    assert result["valid"] is True
    assert result["decision_count"] == 1
