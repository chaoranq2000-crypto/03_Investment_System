from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from src.maintenance.night_shift.contracts import (
    authorize_packaged_queue,
    authorize_packaged_task,
    lint_executable_contract,
    lint_queue_contracts,
)
from src.maintenance.night_shift.models import ContractError, QueueDocument, Task
from src.maintenance.night_shift.queue import load_queue

from tests.test_r5_night_shift_contract import queue, task


def test_proposed_night02_package_loads_without_becoming_approved() -> None:
    package_queue = (
        Path(__file__).resolve().parents[1]
        / "codex_tasks/night_shift/r5_overnight_02_20260720/task_queue.yaml"
    )
    document = load_queue(package_queue)
    assert document.schema_version == "r5_night_shift_queue_v2_proposed"
    assert len(document.tasks) == 40
    assert max(item.priority for item in document.tasks) == 300
    assert document.tasks[0].review_state == "legacy"


def test_v2_final_schema_fails_closed_without_authority_fields() -> None:
    value = queue([task("ns02_t00_missing_authority")])
    value["schema_version"] = "r5_night_shift_queue_v2"
    with pytest.raises(ContractError, match="authority field"):
        QueueDocument.from_mapping(value)


def test_human_reviewed_package_authority_makes_task_lintable() -> None:
    base = Task.from_mapping(task("ns02_t00_authorized"), path="task")
    extended = replace(
        base,
        phase="test",
        estimated_work_units=1,
        delivery_required=True,
    )
    authorized = authorize_packaged_task(extended, package_digest_sha256="a" * 64)
    result = lint_executable_contract(authorized)
    assert result["passed"] is True
    assert authorized.review_state == "approved"


def test_verified_package_digest_authorizes_all_40_packaged_tasks() -> None:
    package_queue = (
        Path(__file__).resolve().parents[1]
        / "codex_tasks/night_shift/r5_overnight_02_20260720/task_queue.yaml"
    )
    proposed = load_queue(package_queue)
    authorized = authorize_packaged_queue(
        proposed,
        package_digest_sha256="236de0bccd04b327f7056bcb79a3c6536c9d5f652d1944c346ceefc3b84420ad",
    )
    report = lint_queue_contracts(authorized)
    assert authorized.schema_version == "r5_night_shift_queue_v2"
    assert report["task_count"] == 40
    assert report["failed_task_count"] == 0
