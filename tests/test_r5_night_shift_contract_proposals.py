from __future__ import annotations

from src.maintenance.night_shift.contracts import (
    generate_contract_proposal,
    validate_review_packet,
)


def test_generator_emits_hash_locked_proposal_not_approval() -> None:
    proposal = generate_contract_proposal(
        task_id="ns02_t35_pointer_contract_proposals",
        source_artifact="reports/legacy/generation_lock.json",
        owner_skill="quality-review",
        requested_action="emit generation_id in a new generation",
        candidate_paths=["src/research/generator.py", "tests/test_generator.py"],
        acceptance_commands=["python -m pytest -q tests/test_generator.py"],
        generator_version="night02-v1",
    )
    assert proposal["review_state"] == "proposed"
    assert proposal["review_sha"] is None
    assert proposal["resolution_claim_allowed"] is False
    assert validate_review_packet(proposal, require_approved=False) == proposal[
        "proposal_sha256"
    ]
