"""Mission outcome, long-term Goal policy, and resumability semantics."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from .models import ContractError, QueueDocument, Task


class MissionOutcome(str, Enum):
    DELIVERED = "delivered"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"
    CUTOFF = "cutoff"


PASSED_STATUS = "passed"
EXTERNAL_BLOCK_STATUSES = {
    "dependency_blocked",
    "evidence_required",
    "human_gate",
    "blocked_external",
}
OPEN_STATUSES = {
    "pending",
    "ready",
    "claimed",
    "running",
    "failed_retryable",
    "skipped_cutoff",
    *EXTERNAL_BLOCK_STATUSES,
}
FAILURE_STATUSES = {"failed_terminal"}


def _field(task: Task | Mapping[str, Any], name: str, default: Any = None) -> Any:
    if isinstance(task, Mapping):
        return task.get(name, default)
    return getattr(task, name, default)


def delivery_required(task: Task | Mapping[str, Any]) -> bool:
    value = _field(task, "delivery_required", True)
    return bool(value)


def evaluate_mission_outcome(
    tasks: Iterable[Task | Mapping[str, Any]],
    *,
    branch_pushed: bool,
    remote_sha_matches: bool,
    ci_verified: bool,
    cutoff_reached: bool = False,
    safety_failure: bool = False,
) -> MissionOutcome:
    """Evaluate Night02 without equating run termination with Goal closure."""

    task_list = list(tasks)
    required = [task for task in task_list if delivery_required(task)]
    statuses = [str(_field(task, "status", "")) for task in task_list]
    required_statuses = [str(_field(task, "status", "")) for task in required]

    if safety_failure or any(status in FAILURE_STATUSES for status in required_statuses):
        return MissionOutcome.FAILED
    publication_complete = branch_pushed and remote_sha_matches and ci_verified
    if required and all(status == PASSED_STATUS for status in required_statuses):
        return MissionOutcome.DELIVERED if publication_complete else MissionOutcome.PARTIAL
    if cutoff_reached:
        return MissionOutcome.CUTOFF

    passed_count = sum(status == PASSED_STATUS for status in statuses)
    remaining_required = [status for status in required_statuses if status != PASSED_STATUS]
    if remaining_required and all(status in EXTERNAL_BLOCK_STATUSES for status in remaining_required):
        return MissionOutcome.PARTIAL if passed_count else MissionOutcome.BLOCKED
    return MissionOutcome.PARTIAL if passed_count or task_list else MissionOutcome.BLOCKED


def outcome_for_pilot_evidence(
    pilot_outcome: str, *, delivery_work_already_passed: bool = False
) -> MissionOutcome:
    """`no_safe_pilot` is evidence of blocked/partial work, never success."""

    if pilot_outcome == "no_safe_pilot":
        return MissionOutcome.PARTIAL if delivery_work_already_passed else MissionOutcome.BLOCKED
    if pilot_outcome == "pilot_acceptance_executed":
        return MissionOutcome.PARTIAL
    raise ContractError(f"unsupported pilot outcome: {pilot_outcome!r}")


@dataclass(frozen=True)
class ProgramGoalPolicy:
    goal_id: str
    close_allowed: bool
    mission_may_close_goal: bool

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ProgramGoalPolicy":
        goal_id = str(value.get("id") or "").strip()
        if not goal_id:
            raise ContractError("program_goal.id: must not be empty")
        return cls(
            goal_id=goal_id,
            close_allowed=bool(value.get("close_allowed", False)),
            mission_may_close_goal=bool(value.get("this_mission_may_close_goal", False)),
        )

    def can_close(
        self,
        *,
        mission_outcome: MissionOutcome,
        explicit_human_authority: bool = False,
    ) -> bool:
        return bool(
            self.close_allowed
            and self.mission_may_close_goal
            and explicit_human_authority
            and mission_outcome is MissionOutcome.DELIVERED
        )


def resumable_task_ids(queue: QueueDocument) -> tuple[str, ...]:
    return tuple(task.id for task in queue.tasks if task.status in OPEN_STATUSES)


def queue_metrics(queue: QueueDocument) -> dict[str, Any]:
    status_counts = Counter(task.status for task in queue.tasks)
    blocked_by_type = Counter(
        task.status for task in queue.tasks if task.status in EXTERNAL_BLOCK_STATUSES
    )
    remaining = [task for task in queue.tasks if task.status != PASSED_STATUS]
    return {
        "total_count": len(queue.tasks),
        "ready_count": status_counts.get("ready", 0),
        "blocked_by_type": dict(sorted(blocked_by_type.items())),
        "remaining_work_units": sum(
            int(getattr(task, "estimated_work_units", 0) or 0) for task in remaining
        ),
        "delivery_required_remaining": sum(
            delivery_required(task) and task.status != PASSED_STATUS for task in queue.tasks
        ),
        "fallback_ready_count": sum(
            task.status == "ready"
            and str(getattr(task, "work_type", "")) in {"engineering", "analysis_automation"}
            and not delivery_required(task)
            for task in queue.tasks
        ),
        "status_counts": dict(sorted(status_counts.items())),
    }
