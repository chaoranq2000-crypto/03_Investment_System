from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.maintenance.night_shift.models import ContractError, QueueDocument
from src.maintenance.night_shift.queue import load_queue, save_queue
from src.maintenance.night_shift.runner import (
    STATE_METADATA_SCHEMA_VERSION,
    metadata_path_for,
    recover_interrupted_state,
    transition_state,
)

from tests.test_r5_night_shift_contract import queue, task


RUN_AT = datetime(2026, 7, 19, 22, 30, tzinfo=timezone.utc)
CUTOFF_AT = datetime(2026, 7, 20, 5, 16, tzinfo=timezone.utc)


def _state(tmp_path: Path, statuses: tuple[str, ...]) -> Path:
    state_path = tmp_path / "state.yaml"
    tasks = [task(f"ns02_t{i:02d}_recovery", status=status) for i, status in enumerate(statuses)]
    document = QueueDocument.from_mapping(queue(tasks))
    save_queue(state_path, document)
    metadata_path_for(state_path).write_text(
        json.dumps(
            {
                "schema_version": STATE_METADATA_SCHEMA_VERSION,
                "run_id": "run-recovery",
                "tasks": {
                    item.id: {"attempts": 1, "history": []} for item in document.tasks
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return state_path


def test_interrupted_claimed_and_running_tasks_recover_once(tmp_path: Path) -> None:
    state_path = _state(tmp_path, ("claimed", "running", "passed"))
    recovered_state, recovered = recover_interrupted_state(
        state_path,
        run_id="run-recovery",
        actor="restart",
        at=RUN_AT,
    )
    assert len(recovered) == 2
    assert [task.status for task in recovered_state.tasks] == [
        "failed_retryable",
        "failed_retryable",
        "passed",
    ]
    _, second = recover_interrupted_state(
        state_path,
        run_id="run-recovery",
        actor="restart",
        at=RUN_AT,
    )
    assert second == ()
    metadata = json.loads(metadata_path_for(state_path).read_text(encoding="utf-8"))
    for task_id in recovered:
        assert metadata["tasks"][task_id]["attempts"] == 1
        assert len(metadata["tasks"][task_id]["history"]) == 1


def test_cutoff_stops_new_claim_but_allows_inflight_completion(tmp_path: Path) -> None:
    state_path = _state(tmp_path, ("ready", "running"))
    with pytest.raises(ContractError, match="cutoff"):
        transition_state(
            state_path,
            task_id="ns02_t00_recovery",
            action="claim",
            run_id="run-recovery",
            actor="test",
            at=CUTOFF_AT,
        )
    state, completed = transition_state(
        state_path,
        task_id="ns02_t01_recovery",
        action="complete",
        run_id="run-recovery",
        actor="test",
        at=CUTOFF_AT,
    )
    assert completed.status == "passed"
    assert state.task_map["ns02_t00_recovery"].status == "ready"


def test_skipped_cutoff_can_resume_in_a_new_open_window(tmp_path: Path) -> None:
    state_path = _state(tmp_path, ("skipped_cutoff",))
    _, resumed = transition_state(
        state_path,
        task_id="ns02_t00_recovery",
        action="resume",
        run_id="run-recovery",
        actor="test",
        at=RUN_AT,
    )
    assert resumed.status == "ready"
    assert load_queue(state_path).task_map[resumed.id].status == "ready"
