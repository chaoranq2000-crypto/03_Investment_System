from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml
import pytest

from src.maintenance.night_shift.models import ContractError
from src.maintenance.night_shift.models import QueueDocument
from src.maintenance.night_shift.queue import ready_tasks
from src.maintenance.night_shift.runner import (
    initialize_state,
    main,
    transition_state,
)

from tests.test_r5_night_shift_contract import queue, task


def test_ready_selection_is_dependency_priority_and_cutoff_aware() -> None:
    first = task("ns01_t00_first", status="passed")
    lower = task("ns01_t10_lower", depends_on=["ns01_t00_first"])
    higher = task("ns01_t20_higher", depends_on=["ns01_t00_first"])
    higher["priority"] = 90
    document = QueueDocument.from_mapping(queue([first, lower, higher]))

    before_cutoff = datetime(2026, 7, 19, 4, 0, tzinfo=timezone.utc)
    assert [item.id for item in ready_tasks(document, before_cutoff)] == [
        "ns01_t20_higher",
        "ns01_t10_lower",
    ]

    after_cutoff = datetime(2026, 7, 19, 8, 0, tzinfo=timezone.utc)
    assert ready_tasks(document, after_cutoff) == ()


def test_cli_validate_show_and_canonicalize(tmp_path: Path, capsys) -> None:
    source = tmp_path / "queue.yaml"
    source.write_text(
        yaml.safe_dump(queue([task("ns01_t00_first", status="ready")]), sort_keys=False),
        encoding="utf-8",
    )
    assert main(["validate", "--queue", str(source)]) == 0
    assert "tasks=1" in capsys.readouterr().out

    assert main(["show", "--queue", str(source), "--task-id", "ns01_t00_first"]) == 0
    assert '"id": "ns01_t00_first"' in capsys.readouterr().out

    output = tmp_path / "canonical.yaml"
    assert main(
        ["canonicalize", "--queue", str(source), "--output", str(output)]
    ) == 0
    assert output.is_file()


def test_claim_start_complete_unlocks_next_task(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.yaml"
    source.write_text(
        yaml.safe_dump(
            queue(
                [
                    task("ns01_t00_first", status="ready"),
                    task("ns01_t10_second", depends_on=["ns01_t00_first"]),
                ]
            ),
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    state = tmp_path / "state.yaml"
    initialize_state(source, state, run_id="run-a")
    monkeypatch.setattr(
        "src.maintenance.night_shift.runner._git_branch", lambda _: "test-branch"
    )
    at = datetime(2026, 7, 19, 0, 30, tzinfo=timezone.utc)
    transition_state(
        state, task_id="ns01_t00_first", action="claim", run_id="run-a", actor="test", at=at
    )
    transition_state(
        state, task_id="ns01_t00_first", action="start", run_id="run-a", actor="test", at=at
    )
    queue_after, completed = transition_state(
        state,
        task_id="ns01_t00_first",
        action="complete",
        run_id="run-a",
        actor="test",
        at=at,
    )
    assert completed.status == "passed"
    assert queue_after.task_map["ns01_t10_second"].status == "ready"


def test_illegal_transition_and_cutoff_fail_without_mutation(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.yaml"
    source.write_text(
        yaml.safe_dump(queue([task("ns01_t00_first", status="ready")]), sort_keys=False),
        encoding="utf-8",
    )
    state = tmp_path / "state.yaml"
    initialize_state(source, state, run_id="run-a")
    before = state.read_bytes()
    monkeypatch.setattr(
        "src.maintenance.night_shift.runner._git_branch", lambda _: "test-branch"
    )

    with pytest.raises(ContractError, match="complete requires running"):
        transition_state(
            state,
            task_id="ns01_t00_first",
            action="complete",
            run_id="run-a",
            actor="test",
            at=datetime(2026, 7, 19, 0, 30, tzinfo=timezone.utc),
        )
    assert state.read_bytes() == before

    with pytest.raises(ContractError, match="cutoff"):
        transition_state(
            state,
            task_id="ns01_t00_first",
            action="claim",
            run_id="run-a",
            actor="test",
            at=datetime(2026, 7, 19, 8, 0, tzinfo=timezone.utc),
        )
    assert state.read_bytes() == before
