from __future__ import annotations

from pathlib import Path

from src.maintenance.night_shift.night03_validation import build_ci_contract


def test_night03_ci_covers_contract_adversarial_full_and_history_guard() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    contract = build_ci_contract(repo_root)
    assert contract["passed"] is True
    assert all(contract["checks"].values())
    assert contract["checks"]["no_publication_mutation"] is True
