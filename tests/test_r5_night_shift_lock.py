from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.maintenance.night_shift.lock import LockError, RunLock
from src.maintenance.night_shift.queue import atomic_write


def test_double_acquire_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "run.lock"
    lock = RunLock(path, pid=101, host="host-a", pid_exists=lambda _: True)
    lock.acquire(run_id="run-a", branch="branch-a")
    with pytest.raises(LockError, match="already held"):
        lock.acquire(run_id="run-b", branch="branch-b")
    lock.release("run-a")


def test_stale_lock_is_archived_only_when_process_is_gone(tmp_path: Path) -> None:
    path = tmp_path / "run.lock"
    old = datetime(2026, 7, 18, 23, 0, tzinfo=timezone.utc)
    path.write_text(
        json.dumps(
            {
                "run_id": "old-run",
                "pid": 999,
                "host": "host-a",
                "branch": "old-branch",
                "started_at": old.isoformat(),
                "heartbeat_at": old.isoformat(),
            }
        ),
        encoding="utf-8",
    )
    current = old + timedelta(hours=1)
    lock = RunLock(
        path,
        stale_after=timedelta(minutes=15),
        now=lambda: current,
        pid_exists=lambda _: False,
        pid=101,
        host="host-a",
    )
    record, archived = lock.acquire(
        run_id="new-run", branch="new-branch", recover_stale=True
    )
    assert record.run_id == "new-run"
    assert archived is not None and archived.is_file()
    assert json.loads(archived.read_text(encoding="utf-8"))["run_id"] == "old-run"
    lock.release("new-run")


def test_atomic_write_failure_preserves_original(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "state.yaml"
    path.write_bytes(b"original\n")

    def fail_replace(source, destination):  # noqa: ANN001
        raise OSError("simulated replace interruption")

    monkeypatch.setattr("src.maintenance.night_shift.queue.os.replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        atomic_write(path, b"replacement\n")
    assert path.read_bytes() == b"original\n"
