from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.maintenance.night_shift.models import ContractError, QueueDocument
from src.maintenance.night_shift.queue import load_queue, queue_bytes


def task(task_id: str, *, depends_on: list[str] | None = None, status: str = "pending") -> dict:
    return {
        "id": task_id,
        "title": task_id,
        "priority": 50,
        "status": status,
        "depends_on": depends_on or [],
        "work_type": "test",
        "goal": "exercise the contract",
        "allowed_paths": ["tests/**"],
        "forbidden_paths": ["data/raw/**"],
        "acceptance_commands": ["python -m pytest -q"],
        "required_artifacts": [],
        "retry_limit": 1,
        "on_success": {},
        "on_failure": {},
        "human_gate": False,
        "notes": [],
    }


def queue(tasks: list[dict]) -> dict:
    return {
        "schema_version": "r5_night_shift_queue_v1",
        "mission_id": "test_mission",
        "baseline": {"source_commit": "0" * 40},
        "run_window": {
            "timezone": "Europe/London",
            "start_at": "23:00",
            "stop_claiming_at": "06:15",
        },
        "task_selection": {"order": ["priority_desc", "task_id_asc"]},
        "tasks": tasks,
    }


def test_valid_queue_round_trips_to_stable_bytes(tmp_path: Path) -> None:
    value = queue(
        [
            task("ns01_t00_first", status="ready"),
            task("ns01_t10_second", depends_on=["ns01_t00_first"]),
        ]
    )
    document = QueueDocument.from_mapping(value)
    first = queue_bytes(document)
    path = tmp_path / "queue.yaml"
    path.write_bytes(first)
    second = queue_bytes(load_queue(path))
    assert first == second
    assert yaml.safe_load(first)["tasks"][1]["depends_on"] == ["ns01_t00_first"]


@pytest.mark.parametrize(
    ("tasks", "needle"),
    [
        (
            [task("ns01_t00_same"), task("ns01_t00_same")],
            "duplicate task ID",
        ),
        (
            [task("ns01_t00_first", depends_on=["ns01_t99_missing"])],
            "unknown dependency",
        ),
        (
            [
                task("ns01_t00_first", depends_on=["ns01_t10_second"]),
                task("ns01_t10_second", depends_on=["ns01_t00_first"]),
            ],
            "dependency cycle",
        ),
    ],
)
def test_graph_errors_fail_closed_and_name_the_problem(tasks: list[dict], needle: str) -> None:
    with pytest.raises(ContractError, match=needle):
        QueueDocument.from_mapping(queue(tasks))


def test_invalid_status_error_names_task_and_field() -> None:
    value = task("ns01_t00_bad", status="finished")
    with pytest.raises(ContractError) as caught:
        QueueDocument.from_mapping(queue([value]))
    message = str(caught.value)
    assert "ns01_t00_bad" in message
    assert ".status" in message
    assert "finished" in message
