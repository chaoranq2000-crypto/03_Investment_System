from __future__ import annotations

from dataclasses import replace

import pytest

from src.maintenance.night_shift.backflow import spawn_retry_task
from src.maintenance.night_shift.contracts import authorize_packaged_task
from src.maintenance.night_shift.models import ContractError, Task

from tests.test_r5_night_shift_contract import task


def approved_task() -> Task:
    return authorize_packaged_task(
        Task.from_mapping(task("ns02_t37_failure_spawn_retry"), path="task"),
        package_digest_sha256="a" * 64,
    )


def test_retry_inherits_scope_and_has_bounded_parent_link() -> None:
    original = approved_task()
    retry = spawn_retry_task(original, failure_type="acceptance_failure")
    assert retry.parent_task_id == original.id
    assert retry.spawn_depth == 1
    assert retry.allowed_paths == original.allowed_paths
    assert retry.acceptance_commands == original.acceptance_commands
    second = spawn_retry_task(retry, failure_type="acceptance_failure")
    assert second.spawn_depth == 2
    with pytest.raises(ContractError, match="depth limit"):
        spawn_retry_task(second, failure_type="acceptance_failure")


def test_safety_failures_do_not_spawn_retries() -> None:
    with pytest.raises(ContractError, match="terminal"):
        spawn_retry_task(approved_task(), failure_type="scope_violation")
