from __future__ import annotations

import hashlib

import pytest

from src.maintenance.night_shift.night03 import Night03Error
from src.maintenance.night_shift.night03_execution import execute_pointer_wave


def contract(index: int = 1) -> dict:
    command = "python -m pytest -q tests/test_r5_night_shift_pointer_executor.py"
    return {
        "occurrence_id": f"occ_{index}",
        "decision": "approved",
        "allowed_paths": ["src/maintenance/night_shift/night03.py"],
        "forbidden_paths": ["data/raw/**"],
        "acceptance_commands": [command],
        "acceptance_command_sha256": {
            command: hashlib.sha256(command.encode("utf-8")).hexdigest()
        },
    }


def test_pointer_executor_is_bounded_and_no_approval_never_resolves() -> None:
    empty = execute_pointer_wave([])
    assert empty["outcome"] == "blocked_external_no_approved_contracts"
    assert empty["resolved_count"] == 0
    with pytest.raises(Night03Error, match="two-task maximum"):
        execute_pointer_wave([contract(1), contract(2), contract(3)], executor=lambda _: {})
    result = execute_pointer_wave(
        [contract()],
        executor=lambda _: {
            "changed_paths": ["src/maintenance/night_shift/night03.py"],
            "acceptance_passed": True,
        },
    )
    assert result["executed_count"] == 1
    assert result["results"][0]["terminal_status"] == "passed"
    assert result["resolved_count"] == 0


def test_pointer_executor_rejects_child_diff_outside_approval() -> None:
    with pytest.raises(Night03Error, match="escaped approved scope"):
        execute_pointer_wave(
            [contract()],
            executor=lambda _: {
                "changed_paths": ["config/unapproved.yaml"],
                "acceptance_passed": True,
            },
        )
