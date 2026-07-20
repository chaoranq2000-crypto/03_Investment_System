from __future__ import annotations

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT

from tests.night04_test_support import REPO_ROOT


def test_inbox_contract_continues_when_no_external_decision_exists() -> None:
    contract = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "review_control/inbox_polling_contract.yaml").read_text(encoding="utf-8"))
    assert contract["missing_external_decisions"] == "continue_bounded_work"
    assert contract["manufacture_decisions"] is False
    assert contract["idempotency_key"] == "decision_digest_sha256"
