"""Queue loading, deterministic serialization, and ready-task selection."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from .models import ContractError, QueueDocument, Task


def load_queue(path: Path) -> QueueDocument:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ContractError(f"queue[{path}]: cannot read YAML: {exc}") from exc
    if not isinstance(payload, dict):
        raise ContractError(f"queue[{path}]: YAML root must be an object")
    return QueueDocument.from_mapping(payload, path=f"queue[{path.as_posix()}]")


def queue_bytes(queue: QueueDocument) -> bytes:
    text = yaml.safe_dump(
        queue.to_mapping(),
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=1000,
        line_break="\n",
    )
    if not text.endswith("\n"):
        text += "\n"
    return text.encode("utf-8")


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()


def save_queue(path: Path, queue: QueueDocument) -> None:
    atomic_write(path, queue_bytes(queue))


def _clock(value: Any, field: str) -> time:
    if isinstance(value, int) and not isinstance(value, bool):
        if not 0 <= value < 24 * 60:
            raise ContractError(f"run_window.{field}: integer minute value is out of range")
        return time(hour=value // 60, minute=value % 60)
    text = str(value or "").strip()
    try:
        hour_text, minute_text = text.split(":", 1)
        parsed = time(hour=int(hour_text), minute=int(minute_text))
    except (TypeError, ValueError) as exc:
        raise ContractError(f"run_window.{field}: expected HH:MM, got {value!r}") from exc
    return parsed


def _zone(run_window: dict[str, Any]) -> ZoneInfo:
    name = str(run_window.get("timezone") or "").strip()
    if not name:
        raise ContractError("run_window.timezone: must not be empty")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ContractError(f"run_window.timezone: unknown timezone {name!r}") from exc


def claiming_open(run_window: dict[str, Any], now: datetime | None = None) -> bool:
    zone = _zone(run_window)
    current = now or datetime.now(tz=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    local = current.astimezone(zone).timetz().replace(tzinfo=None)
    start = _clock(run_window.get("start_at", "00:00"), "start_at")
    stop = _clock(run_window.get("stop_claiming_at"), "stop_claiming_at")
    if start == stop:
        return False
    if start < stop:
        return start <= local < stop
    return local >= start or local < stop


def dependencies_passed(task: Task, queue: QueueDocument) -> bool:
    by_id = queue.task_map
    return all(by_id[dependency].status == "passed" for dependency in task.depends_on)


def ready_tasks(queue: QueueDocument, now: datetime | None = None) -> tuple[Task, ...]:
    if not claiming_open(queue.run_window, now):
        return ()
    candidates = [
        task
        for task in queue.tasks
        if task.status in {"pending", "ready"}
        and not task.human_gate
        and dependencies_passed(task, queue)
    ]
    return tuple(sorted(candidates, key=lambda task: (-task.priority, task.id)))
