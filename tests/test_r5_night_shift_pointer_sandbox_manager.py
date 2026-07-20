from __future__ import annotations

import yaml

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from tests.night04_test_support import REPO_ROOT


def test_sandbox_manager_records_eight_detached_child_worktrees() -> None:
    payload = yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "pointer_prevalidation/sandbox_manager_contract.yaml").read_text(encoding="utf-8"))
    assert payload["sandbox_count"] == len(payload["sandboxes"]) == 8
    assert payload["mode"] == "detached_child_worktrees"
    assert len(payload["base_commit"]) == 40
    assert payload["target_branch_mutation_without_approval"] is False
