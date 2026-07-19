"""Strict task and queue contracts for the local night-shift runtime."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence


QUEUE_SCHEMA_VERSION = "r5_night_shift_queue_v1"
TASK_ID_PATTERN = re.compile(r"^ns[0-9]{2}_t[0-9]{2}_[a-z0-9_]+$")
TASK_STATUSES = (
    "pending",
    "ready",
    "claimed",
    "running",
    "passed",
    "failed_retryable",
    "failed_terminal",
    "dependency_blocked",
    "evidence_required",
    "human_gate",
    "skipped_cutoff",
)

TASK_FIELDS = (
    "id",
    "title",
    "priority",
    "status",
    "depends_on",
    "work_type",
    "goal",
    "allowed_paths",
    "forbidden_paths",
    "acceptance_commands",
    "required_artifacts",
    "retry_limit",
    "on_success",
    "on_failure",
    "human_gate",
    "notes",
)

QUEUE_FIELDS = (
    "schema_version",
    "mission_id",
    "baseline",
    "run_window",
    "task_selection",
    "tasks",
)


class ContractError(ValueError):
    """Raised when a queue or task violates its declared contract."""


def _fail(path: str, message: str) -> ContractError:
    return ContractError(f"{path}: {message}")


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise _fail(path, "must be an object")
    return {str(key): child for key, child in value.items()}


def _text(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise _fail(path, "must be a string")
    if not allow_empty and not value.strip():
        raise _fail(path, "must not be empty")
    return value


def _integer(value: Any, path: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(path, "must be an integer")
    if not minimum <= value <= maximum:
        raise _fail(path, f"must be between {minimum} and {maximum}")
    return value


def _string_list(value: Any, path: str, *, unique: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise _fail(path, "must be an array")
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(_text(item, f"{path}[{index}]", allow_empty=False))
    if unique and len(set(result)) != len(result):
        raise _fail(path, "must not contain duplicate values")
    return tuple(result)


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    priority: int
    status: str
    depends_on: tuple[str, ...]
    work_type: str
    goal: str
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    acceptance_commands: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    retry_limit: int
    on_success: dict[str, Any]
    on_failure: dict[str, Any]
    human_gate: bool
    notes: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], *, path: str) -> "Task":
        payload = _mapping(value, path)
        missing = [name for name in TASK_FIELDS if name not in payload]
        if missing:
            raise _fail(path, f"missing required field(s): {', '.join(missing)}")
        unknown = sorted(set(payload) - set(TASK_FIELDS))
        if unknown:
            raise _fail(path, f"unknown field(s): {', '.join(unknown)}")

        task_id = _text(payload["id"], f"{path}.id")
        task_path = f"{path}[{task_id}]"
        if not TASK_ID_PATTERN.fullmatch(task_id):
            raise _fail(f"{task_path}.id", "does not match the night-shift task ID pattern")
        status = _text(payload["status"], f"{task_path}.status")
        if status not in TASK_STATUSES:
            raise _fail(
                f"{task_path}.status",
                f"unsupported status {status!r}; expected one of {', '.join(TASK_STATUSES)}",
            )
        human_gate = payload["human_gate"]
        if not isinstance(human_gate, bool):
            raise _fail(f"{task_path}.human_gate", "must be a boolean")

        return cls(
            id=task_id,
            title=_text(payload["title"], f"{task_path}.title"),
            priority=_integer(
                payload["priority"], f"{task_path}.priority", minimum=0, maximum=100
            ),
            status=status,
            depends_on=_string_list(
                payload["depends_on"], f"{task_path}.depends_on", unique=True
            ),
            work_type=_text(payload["work_type"], f"{task_path}.work_type"),
            goal=_text(payload["goal"], f"{task_path}.goal"),
            allowed_paths=_string_list(
                payload["allowed_paths"], f"{task_path}.allowed_paths"
            ),
            forbidden_paths=_string_list(
                payload["forbidden_paths"], f"{task_path}.forbidden_paths"
            ),
            acceptance_commands=_string_list(
                payload["acceptance_commands"], f"{task_path}.acceptance_commands"
            ),
            required_artifacts=_string_list(
                payload["required_artifacts"], f"{task_path}.required_artifacts"
            ),
            retry_limit=_integer(
                payload["retry_limit"], f"{task_path}.retry_limit", minimum=0, maximum=5
            ),
            on_success=_mapping(payload["on_success"], f"{task_path}.on_success"),
            on_failure=_mapping(payload["on_failure"], f"{task_path}.on_failure"),
            human_gate=human_gate,
            notes=_string_list(payload["notes"], f"{task_path}.notes"),
        )

    def with_status(self, status: str) -> "Task":
        if status not in TASK_STATUSES:
            raise ContractError(f"task[{self.id}].status: unsupported status {status!r}")
        return replace(self, status=status)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority,
            "status": self.status,
            "depends_on": list(self.depends_on),
            "work_type": self.work_type,
            "goal": self.goal,
            "allowed_paths": list(self.allowed_paths),
            "forbidden_paths": list(self.forbidden_paths),
            "acceptance_commands": list(self.acceptance_commands),
            "required_artifacts": list(self.required_artifacts),
            "retry_limit": self.retry_limit,
            "on_success": dict(self.on_success),
            "on_failure": dict(self.on_failure),
            "human_gate": self.human_gate,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class QueueDocument:
    schema_version: str
    mission_id: str
    baseline: dict[str, Any]
    run_window: dict[str, Any]
    task_selection: dict[str, Any]
    tasks: tuple[Task, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], *, path: str = "queue") -> "QueueDocument":
        payload = _mapping(value, path)
        required = {"schema_version", "mission_id", "baseline", "run_window", "tasks"}
        missing = sorted(required - set(payload))
        if missing:
            raise _fail(path, f"missing required field(s): {', '.join(missing)}")
        unknown = sorted(set(payload) - set(QUEUE_FIELDS))
        if unknown:
            raise _fail(path, f"unknown field(s): {', '.join(unknown)}")
        version = _text(payload["schema_version"], f"{path}.schema_version")
        if version != QUEUE_SCHEMA_VERSION:
            raise _fail(
                f"{path}.schema_version",
                f"expected {QUEUE_SCHEMA_VERSION!r}, got {version!r}",
            )
        raw_tasks = payload["tasks"]
        if not isinstance(raw_tasks, list):
            raise _fail(f"{path}.tasks", "must be an array")
        tasks = tuple(
            Task.from_mapping(item, path=f"{path}.tasks[{index}]")
            for index, item in enumerate(raw_tasks)
        )
        document = cls(
            schema_version=version,
            mission_id=_text(payload["mission_id"], f"{path}.mission_id"),
            baseline=_mapping(payload["baseline"], f"{path}.baseline"),
            run_window=_mapping(payload["run_window"], f"{path}.run_window"),
            task_selection=_mapping(
                payload.get("task_selection", {}), f"{path}.task_selection"
            ),
            tasks=tasks,
        )
        document.validate_graph(path=path)
        return document

    @property
    def task_map(self) -> dict[str, Task]:
        return {task.id: task for task in self.tasks}

    def validate_graph(self, *, path: str = "queue") -> None:
        ids = [task.id for task in self.tasks]
        if len(ids) != len(set(ids)):
            duplicates = sorted({item for item in ids if ids.count(item) > 1})
            raise _fail(f"{path}.tasks", f"duplicate task ID(s): {', '.join(duplicates)}")
        known = set(ids)
        for task in self.tasks:
            for dependency in task.depends_on:
                if dependency not in known:
                    raise _fail(
                        f"{path}.tasks[{task.id}].depends_on",
                        f"unknown dependency {dependency!r}",
                    )
                if dependency == task.id:
                    raise _fail(
                        f"{path}.tasks[{task.id}].depends_on",
                        "a task cannot depend on itself",
                    )

        visiting: list[str] = []
        visited: set[str] = set()
        task_map = self.task_map

        def visit(task_id: str) -> None:
            if task_id in visited:
                return
            if task_id in visiting:
                start = visiting.index(task_id)
                cycle = visiting[start:] + [task_id]
                raise _fail(f"{path}.tasks", f"dependency cycle: {' -> '.join(cycle)}")
            visiting.append(task_id)
            for dependency in task_map[task_id].depends_on:
                visit(dependency)
            visiting.pop()
            visited.add(task_id)

        for task_id in sorted(task_map):
            visit(task_id)

    def replace_task(self, replacement: Task) -> "QueueDocument":
        if replacement.id not in self.task_map:
            raise ContractError(f"queue.tasks[{replacement.id}]: task does not exist")
        updated = tuple(
            replacement if task.id == replacement.id else task for task in self.tasks
        )
        result = replace(self, tasks=updated)
        result.validate_graph()
        return result

    def to_mapping(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schema_version": self.schema_version,
            "mission_id": self.mission_id,
            "baseline": dict(self.baseline),
            "run_window": dict(self.run_window),
        }
        if self.task_selection:
            value["task_selection"] = dict(self.task_selection)
        value["tasks"] = [task.to_mapping() for task in self.tasks]
        return value


def task_ids(tasks: Sequence[Task]) -> tuple[str, ...]:
    """Return task IDs without exposing mutable task collections."""

    return tuple(task.id for task in tasks)
