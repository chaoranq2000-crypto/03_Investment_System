from __future__ import annotations

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_pointer_execution_remains_closed_without_external_approval() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "pointer_prevalidation/conditional_execution_contract.yaml").read_text(encoding="utf-8"))
    assert "authentic_external_exact_hash_approval" in payload["required_gates"]
    assert payload["external_approvals_present"] == 0
    assert payload["target_branch_executions"] == 0
    assert payload["dry_run_is_resolution"] is False
