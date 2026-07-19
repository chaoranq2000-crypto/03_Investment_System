from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.maintenance.night_shift.night03 import Night03Error
from src.maintenance.night_shift.night03_decisions import (
    pointer_proposal_hash,
    validate_decision_manifest,
)


def pointer_candidate() -> dict:
    packet = {
        "allowed_paths": ["src/maintenance/night_shift/night03.py"],
        "acceptance_commands": ["python -m pytest -q tests/test_pointer.py"],
        "scope_ceiling": {
            "allowed_paths": [
                "src/maintenance/night_shift/night03.py",
                "tests/test_pointer.py",
            ]
        },
    }
    packet["proposal_sha256"] = pointer_proposal_hash(packet)
    return packet


def test_pointer_approval_requires_exact_paths_commands_ceiling_and_review_hash(
    night03_decision_factory,
) -> None:
    candidate = pointer_candidate()
    review = {
        **candidate,
        "review_state": "approved",
        "review_sha": candidate["proposal_sha256"],
    }
    root, manifest, _, _ = night03_decision_factory(
        "pointer_contract_approval", review, candidate=candidate
    )
    now = datetime(2026, 7, 20, tzinfo=timezone.utc)
    assert validate_decision_manifest(root, manifest, now=now)["valid"] is True
    review["acceptance_commands"] = ["python -m pytest -q"]
    root, manifest, _, _ = night03_decision_factory(
        "pointer_contract_approval", review, candidate=candidate
    )
    with pytest.raises(Night03Error, match="commands"):
        validate_decision_manifest(root, manifest, now=now)
