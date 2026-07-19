from __future__ import annotations

import copy

import pytest

from src.maintenance.night_shift.contracts import (
    generate_contract_proposal,
    validate_review_packet,
)
from src.maintenance.night_shift.models import ContractError


def proposal() -> dict:
    return generate_contract_proposal(
        task_id="ns02_t25_review_packet_hash_lock",
        source_artifact="reports/source.json",
        owner_skill="research-orchestrator",
        requested_action="review exact paths and commands",
        candidate_paths=["src/maintenance/night_shift/contracts.py"],
        acceptance_commands=["python -m pytest -q tests/test_r5_night_shift_review_handoff.py"],
        generator_version="night02-v1",
    )


def test_approved_review_binds_exact_proposal_hash() -> None:
    reviewed = proposal()
    reviewed.update(
        {
            "review_state": "approved",
            "review_sha": reviewed["proposal_sha256"],
            "reviewer": "human-reviewer",
            "reviewed_at": "2026-07-19T18:00:00+08:00",
            "decision": "approved",
        }
    )
    assert validate_review_packet(reviewed, require_approved=True) == reviewed[
        "review_sha"
    ]

    tampered = copy.deepcopy(reviewed)
    tampered["candidate_paths"].append("src/unreviewed.py")
    with pytest.raises(ContractError, match="hash mismatch"):
        validate_review_packet(tampered, require_approved=True)


def test_empty_reviewer_fields_cannot_be_auto_accepted() -> None:
    unreviewed = proposal()
    with pytest.raises(ContractError, match="not approved"):
        validate_review_packet(unreviewed, require_approved=True)
