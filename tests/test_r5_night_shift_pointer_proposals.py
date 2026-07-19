from __future__ import annotations

from pathlib import Path

from src.maintenance.night_shift.backflow import build_pointer_proposals
from src.maintenance.night_shift.contracts import validate_review_packet


def test_eight_pointer_issues_route_to_new_upstream_contracts() -> None:
    proposals = build_pointer_proposals(Path(__file__).resolve().parents[1])
    assert proposals["proposal_count"] == 8
    assert proposals["resolved_blocker_count"] == 0
    routes = {item["semantic_route"] for item in proposals["proposals"]}
    assert routes == {"upstream_generation_contract", "upstream_quality_contract"}
    for item in proposals["proposals"]:
        assert item["review_state"] == "proposed"
        assert item["review_sha"] is None
        assert item["historical_artifact_read_only"] is True
        assert item["legacy_pointer_substitution_allowed"] is False
        assert validate_review_packet(item, require_approved=False) == item[
            "proposal_sha256"
        ]
