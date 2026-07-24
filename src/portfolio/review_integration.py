"""Failure-isolated bridge and in-process investment-review automation.

The portfolio database remains the authoritative source.  This module only
selects an explicitly configured review sidecar and invokes the review sync
service after the portfolio transaction has already committed.  It never
creates or initializes a sidecar and it never lets review failures escape back
into the portfolio import path.  P5 automation reuses the existing append-only
``review_runs`` ledger and the frozen facts-only runner; it does not install an
operating-system scheduler.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import threading
import time
from typing import Any


REVIEW_DATABASE_ENV = "INVESTMENT_REVIEW_DB"
REVIEW_AUTOMATION_ENV = "INVESTMENT_REVIEW_AUTOMATION"
REVIEW_AUTOMATION_INTERVAL_ENV = "INVESTMENT_REVIEW_AUTOMATION_INTERVAL_SECONDS"
REVIEW_AUTOMATION_VERSION = "investment_review.catch_up.v1"
REVIEW_AUTOMATION_SCOPES = ("single", "weekly", "monthly")
DEFAULT_AUTOMATION_INTERVAL_SECONDS = 900.0
AUTOMATION_LEASE_TIMEOUT_SECONDS = 120.0

SyncHook = Callable[..., Mapping[str, Any]]
AutomationHook = Callable[..., Mapping[str, Any]]
RunnerFactory = Callable[[], Any]
Clock = Callable[[], datetime]

# Deliberately replaceable in tests.  Production leaves this as ``None`` so the
# review service is imported lazily only after a successful portfolio commit.
POST_COMMIT_SYNC_HOOK: SyncHook | None = None
POST_COMMIT_AUTOMATION_HOOK: AutomationHook | None = None

_LEASES_GUARD = threading.Lock()
_LOCAL_LEASES: dict[str, threading.Lock] = {}


def _local_lease(path: Path) -> threading.Lock:
    key = str(path.resolve(strict=False)).casefold()
    with _LEASES_GUARD:
        return _LOCAL_LEASES.setdefault(key, threading.Lock())


class _AutomationLease:
    """One-byte cross-process lease backed by an ignored checkout-local file."""

    def __init__(
        self,
        *,
        repo_root: Path,
        review_db: Path,
        timeout_seconds: float = AUTOMATION_LEASE_TIMEOUT_SECONDS,
    ) -> None:
        identity = hashlib.sha256(
            str(review_db.resolve(strict=False)).casefold().encode("utf-8")
        ).hexdigest()[:32]
        self.path = (
            repo_root
            / ".codex_tmp"
            / "investment_review_product_completion_v2"
            / "automation_locks"
            / f"{identity}.lock"
        ).resolve(strict=False)
        try:
            self.path.relative_to(repo_root)
        except ValueError as exc:
            raise ValueError(
                "automation lease must remain inside the selected checkout"
            ) from exc
        self._local = _local_lease(self.path)
        self.timeout_seconds = max(0.0, float(timeout_seconds))
        self._stream: Any | None = None
        self._locked = False

    def _try_os_lock(self) -> bool:
        assert self._stream is not None
        self._stream.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(
                    self._stream.fileno(),
                    msvcrt.LK_NBLCK,
                    1,
                )
            except OSError:
                return False
            return True

        import fcntl

        try:
            fcntl.flock(
                self._stream.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except OSError:
            return False
        return True

    def _unlock_os(self) -> None:
        assert self._stream is not None
        self._stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(
                self._stream.fileno(),
                msvcrt.LK_UNLCK,
                1,
            )
            return

        import fcntl

        fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)

    def __enter__(self) -> "_AutomationLease":
        deadline = time.monotonic() + self.timeout_seconds
        if not self._local.acquire(
            timeout=self.timeout_seconds
        ):
            raise TimeoutError("automation lease acquisition timed out")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._stream = self.path.open("a+b")
            self._stream.seek(0, os.SEEK_END)
            if self._stream.tell() == 0:
                self._stream.write(b"\0")
                self._stream.flush()
            while not self._try_os_lock():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        "automation cross-process lease acquisition timed out"
                    )
                threading.Event().wait(min(0.05, remaining))
            self._locked = True
            return self
        except Exception:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
            self._local.release()
            raise

    def __exit__(self, *_exc: object) -> None:
        try:
            if self._locked:
                self._unlock_os()
        finally:
            self._locked = False
            if self._stream is not None:
                self._stream.close()
                self._stream = None
            self._local.release()


@dataclass(frozen=True)
class ReviewAutomationConfig:
    """Bounded configuration for the optional in-process coordinator."""

    enabled: bool = True
    interval_seconds: float = DEFAULT_AUTOMATION_INTERVAL_SECONDS
    startup_catch_up: bool = True


@dataclass(frozen=True)
class _AutomationPlan:
    run_id: str
    run_key: str
    source_cutoff_id: str
    source_sha256: str
    artifact_namespace: str
    projection_sha256: str
    as_of: str | None
    knowledge_cutoff: str | None
    source_cutoff: str | None
    sync_action: str
    source_seen: int
    sidecar_seen: int
    unsynced: int


def _parse_bool(value: object, *, field: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on", "enabled"}:
        return True
    if normalized in {"0", "false", "no", "off", "disabled"}:
        return False
    raise ValueError(f"{field} must be a boolean value")


def review_automation_config(
    *,
    environ: Mapping[str, str] | None = None,
    enabled_override: bool | None = None,
) -> ReviewAutomationConfig:
    """Resolve automation settings without consulting the current directory."""

    values = os.environ if environ is None else environ
    raw_enabled = values.get(REVIEW_AUTOMATION_ENV)
    enabled = (
        bool(enabled_override)
        if enabled_override is not None
        else (
            True
            if raw_enabled is None or not str(raw_enabled).strip()
            else _parse_bool(raw_enabled, field=REVIEW_AUTOMATION_ENV)
        )
    )
    if not enabled:
        return ReviewAutomationConfig(
            enabled=False,
            interval_seconds=DEFAULT_AUTOMATION_INTERVAL_SECONDS,
            startup_catch_up=True,
        )
    raw_interval = values.get(REVIEW_AUTOMATION_INTERVAL_ENV)
    if raw_interval is None or not str(raw_interval).strip():
        interval = DEFAULT_AUTOMATION_INTERVAL_SECONDS
    else:
        try:
            interval = float(str(raw_interval).strip())
        except ValueError as exc:
            raise ValueError(
                f"{REVIEW_AUTOMATION_INTERVAL_ENV} must be numeric"
            ) from exc
        if not 30.0 <= interval <= 86400.0:
            raise ValueError(
                f"{REVIEW_AUTOMATION_INTERVAL_ENV} must be between 30 and 86400"
            )
    return ReviewAutomationConfig(
        enabled=enabled,
        interval_seconds=interval,
        startup_catch_up=True,
    )


def _containing_checkout(path: Path) -> Path | None:
    for parent in (path.parent, *path.parents):
        if (parent / ".git").exists():
            return parent.resolve(strict=False)
    return None


def configured_review_database(
    explicit_path: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path | None:
    """Return the explicitly selected absolute sidecar path, if any.

    There is intentionally no current-working-directory or linked-worktree
    fallback.  In particular, running a command from another checkout must not
    make that checkout's existing sidecar an implicit write target.
    """

    raw_value: str | Path | None = explicit_path
    if raw_value is None:
        raw_value = (os.environ if environ is None else environ).get(REVIEW_DATABASE_ENV)
    if raw_value is None or not str(raw_value).strip():
        return None
    candidate = Path(str(raw_value).strip()).expanduser()
    if not candidate.is_absolute():
        raise ValueError(f"{REVIEW_DATABASE_ENV} must be an absolute path")
    resolved = candidate.resolve(strict=False)
    current_checkout = Path(__file__).resolve().parents[2]
    candidate_checkout = _containing_checkout(resolved)
    if candidate_checkout is not None and candidate_checkout != current_checkout:
        raise ValueError(
            f"{REVIEW_DATABASE_ENV} belongs to a different checkout: "
            f"{candidate_checkout}"
        )
    return resolved


def _utc_now(clock: Clock) -> str:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("automation clock must return an aware datetime")
    return value.astimezone(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _public_run_projection(value: object) -> dict[str, Any] | None:
    """Project one catch-up ledger row without paths or raw error text."""

    if not isinstance(value, Mapping):
        return None
    run = value.get("run")
    event = value.get("status_event")
    if not isinstance(run, Mapping):
        return None
    parameters = run.get("parameters")
    parameters = parameters if isinstance(parameters, Mapping) else {}
    details = (
        event.get("details")
        if isinstance(event, Mapping)
        and isinstance(event.get("details"), Mapping)
        else {}
    )
    scope_runs = details.get("scope_runs")
    projected_scopes: list[dict[str, Any]] = []
    if isinstance(scope_runs, list):
        for item in scope_runs:
            if not isinstance(item, Mapping):
                continue
            projected_scopes.append(
                {
                    "scope": item.get("scope"),
                    "run_id": item.get("run_id"),
                    "run_key": item.get("run_key"),
                    "status": item.get("status"),
                    "content_id": item.get("content_id"),
                }
            )
    return {
        "run_id": run.get("run_id"),
        "run_key": run.get("run_key"),
        "status": value.get("status"),
        "requested_at": run.get("requested_at"),
        "source_cutoff": run.get("source_cutoff"),
        "status_occurred_at": (
            event.get("occurred_at") if isinstance(event, Mapping) else None
        ),
        "source_cutoff_id": parameters.get("source_cutoff_id"),
        "projection_sha256": parameters.get("projection_sha256"),
        "attempt": details.get("attempt"),
        "retryable": details.get("retryable"),
        "scope_runs": projected_scopes,
    }


def review_automation_health(
    store: Any,
    *,
    enabled: bool,
    worker_alive: bool = False,
    queue_depth: int = 0,
    local_state: str | None = None,
    local_failure: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a bounded, path-free projection of the persistent catch-up queue."""

    health_unavailable = False
    try:
        runs = store.list_review_runs(scope="catch_up")
    except Exception:
        health_unavailable = True
        runs = []
        local_failure = {
            "error_type": "AutomationHealthUnavailable",
            "occurred_at": None,
        }

    def run_sort_key(item: object) -> tuple[str, str, str]:
        if not isinstance(item, Mapping):
            return ("", "", "")
        run = item.get("run")
        run = run if isinstance(run, Mapping) else {}
        event = item.get("status_event")
        event = event if isinstance(event, Mapping) else {}
        return (
            str(event.get("occurred_at") or ""),
            str(run.get("requested_at") or ""),
            str(run.get("run_id") or ""),
        )

    runs.sort(key=run_sort_key)
    latest = runs[-1] if runs else None
    success_events: list[dict[str, Any]] = []
    completed_events: list[dict[str, Any]] = []
    failure_events: list[dict[str, Any]] = []
    for item in runs:
        run = item.get("run")
        if not isinstance(run, Mapping):
            continue
        for event in item.get("history", []):
            if not isinstance(event, Mapping):
                continue
            projection = {
                "run": run,
                "status": event.get("status"),
                "status_event": event,
            }
            if event.get("status") in {"succeeded", "partial"}:
                completed_events.append(projection)
            if event.get("status") == "succeeded":
                success_events.append(projection)
            if event.get("status") in {"failed", "blocked"}:
                failure_events.append(projection)
    success_events.sort(
        key=lambda item: str(
            (item.get("status_event") or {}).get("occurred_at") or ""
        )
    )
    completed_events.sort(
        key=lambda item: str(
            (item.get("status_event") or {}).get("occurred_at") or ""
        )
    )
    failure_events.sort(
        key=lambda item: str(
            (item.get("status_event") or {}).get("occurred_at") or ""
        )
    )
    pending = [
        item
        for item in runs
        if item.get("status") in {"queued", "running", "failed"}
    ]
    latest_event = (
        latest.get("status_event")
        if isinstance(latest, Mapping)
        and isinstance(latest.get("status_event"), Mapping)
        else {}
    )
    latest_occurred_at = str(latest_event.get("occurred_at") or "")
    local_failure_occurred_at = (
        str(local_failure.get("occurred_at") or "")
        if isinstance(local_failure, Mapping)
        else ""
    )
    local_failure_is_current = bool(
        isinstance(local_failure, Mapping)
        and (
            latest is None
            or (
                local_failure_occurred_at
                and local_failure_occurred_at > latest_occurred_at
            )
        )
    )
    if not enabled:
        state = "disabled"
    elif health_unavailable:
        state = "failed"
    elif local_state == "queued" and int(queue_depth) > 0:
        state = "queued"
    elif local_state in {"running", "stopping"} and worker_alive:
        state = str(local_state)
    elif local_state == "failed" and local_failure_is_current:
        state = "failed"
    elif latest is None:
        state = "idle"
    else:
        state = str(latest.get("status") or "unknown")
    persistent_failure = (
        _public_run_projection(failure_events[-1])
        if failure_events
        else None
    )
    local_failure_projection = (
        {
            "status": "failed",
            "error_type": local_failure.get("error_type"),
            "status_occurred_at": local_failure.get("occurred_at"),
        }
        if isinstance(local_failure, Mapping)
        else None
    )
    persistent_failure_occurred_at = (
        str(persistent_failure.get("status_occurred_at") or "")
        if isinstance(persistent_failure, Mapping)
        else ""
    )
    if (
        local_failure_projection is not None
        and (
            persistent_failure is None
            or (
                local_failure_occurred_at
                and local_failure_occurred_at
                > persistent_failure_occurred_at
            )
        )
    ):
        last_failure: dict[str, Any] | None = local_failure_projection
    else:
        last_failure = persistent_failure
    return {
        "enabled": bool(enabled),
        "state": state,
        "worker_alive": bool(worker_alive),
        "queue_depth": max(int(queue_depth), len(pending)),
        "run_count": len(runs),
        "latest": _public_run_projection(latest),
        "last_success": _public_run_projection(success_events[-1])
        if success_events
        else None,
        "last_completed": _public_run_projection(completed_events[-1])
        if completed_events
        else None,
        "last_failure": last_failure,
    }


class ReviewAutomationCoordinator:
    """Single-worker, retry-safe coordinator for facts-only catch-up runs."""

    def __init__(
        self,
        *,
        portfolio_db: str | Path,
        review_db: str | Path,
        mapping_path: str | Path | None = None,
        artifact_root: str | Path | None = None,
        repo_root: str | Path | None = None,
        config: ReviewAutomationConfig | None = None,
        sync_service: Any | None = None,
        store: Any | None = None,
        runner_factory: RunnerFactory | None = None,
        clock: Clock | None = None,
    ) -> None:
        from src.investment_review.review_runner import ReviewRunner
        from src.investment_review.store import ReviewStore
        from src.investment_review.sync_service import ReviewSyncService

        self.repo_root = (
            Path(repo_root).expanduser().resolve()
            if repo_root is not None
            else Path(__file__).resolve().parents[2]
        )
        self.portfolio_db = Path(portfolio_db).expanduser().resolve(
            strict=False
        )
        self.review_db = Path(review_db).expanduser().resolve(strict=False)
        self.mapping_path = (
            Path(mapping_path).expanduser().resolve(strict=False)
            if mapping_path is not None
            else (
                self.repo_root
                / "config"
                / "investment_review.portfolio.reviewed.json"
            ).resolve(strict=False)
        )
        self.artifact_root = (
            Path(artifact_root).expanduser().resolve(strict=False)
            if artifact_root is not None
            else (
                self.repo_root / ".codex_tmp" / "investment_review_runs"
            ).resolve(strict=False)
        )
        try:
            self.artifact_namespace = self.artifact_root.relative_to(
                self.repo_root
            ).as_posix()
        except ValueError as exc:
            raise ValueError(
                "review automation artifacts must remain inside the selected checkout"
            ) from exc
        if not self.review_db.is_file():
            raise FileNotFoundError(
                "configured review sidecar does not exist; automation will not create it"
            )
        if self.portfolio_db == self.review_db:
            raise ValueError(
                "portfolio source and review sidecar must be different files"
            )
        try:
            self.review_db.relative_to(self.repo_root)
        except ValueError as exc:
            raise ValueError(
                "review automation sidecar must remain inside the selected checkout"
            ) from exc

        self.config = config or ReviewAutomationConfig()
        self.sync_service = sync_service or ReviewSyncService(
            self.portfolio_db,
            review_db=self.review_db,
            mapping_path=self.mapping_path,
            repo_root=self.repo_root,
        )
        self.store = store or ReviewStore(self.review_db)
        self.store.status()
        self._runner_factory = runner_factory or (
            lambda: ReviewRunner(
                review_db=self.review_db,
                portfolio_db=self.portfolio_db,
                mapping_path=self.mapping_path,
                artifact_root=self.artifact_root,
                repo_root=self.repo_root,
            )
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._cycle_lock = threading.Lock()
        self._lease = _AutomationLease(
            repo_root=self.repo_root,
            review_db=self.review_db,
        )
        self._enqueue_lease = _AutomationLease(
            repo_root=self.repo_root,
            review_db=self.review_db,
            timeout_seconds=0.05,
        )
        self._state_lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._pending_triggers: set[str] = set()
        self._thread: threading.Thread | None = None
        self._local_state = "idle" if self.config.enabled else "disabled"
        self._local_failure: dict[str, Any] | None = None

    @staticmethod
    def _projection_state(store: Any) -> tuple[list[dict[str, Any]], str]:
        from src.investment_review.models import canonical_json, sha256_text

        events = store.list_episode_projection_inputs()
        decision_ids = sorted(
            {
                str(ref.get("decision_id") or "")
                for event in events
                for ref in event.get("decision_refs", [])
                if isinstance(ref, Mapping) and ref.get("decision_id")
            }
        )
        decisions = [
            store.get_decision(decision_id)
            for decision_id in decision_ids
        ]
        digest = sha256_text(
            canonical_json(
                {
                    "events": events,
                    "linked_decisions": decisions,
                }
            )
        )
        return events, digest

    @staticmethod
    def _max_timestamp(values: list[object]) -> str | None:
        from src.investment_review.time_utils import parse_datetime, utc_iso

        parsed = [
            parse_datetime(value, "UTC")
            for value in values
            if value is not None and str(value).strip()
        ]
        return utc_iso(max(parsed), "UTC") if parsed else None

    def _prepare_plan(self, *, trigger: str) -> _AutomationPlan:
        from src.investment_review.models import canonical_json, sha256_text

        health = self.sync_service.status()
        counts = (
            health.get("counts")
            if isinstance(health.get("counts"), Mapping)
            else {}
        )
        unsynced = int(counts.get("unsynced", 0) or 0)
        if health.get("status") == "healthy" and unsynced == 0:
            sync_payload = health
            sync_action = "already_reconciled"
        else:
            sync_payload = self.sync_service.sync(
                dry_run=False,
                trigger=f"review_automation_{trigger}",
            )
            sync_action = "reconciled"
        source = (
            sync_payload.get("source")
            if isinstance(sync_payload.get("source"), Mapping)
            else {}
        )
        cutoff = (
            source.get("cutoff")
            if isinstance(source.get("cutoff"), Mapping)
            else {}
        )
        final_counts = (
            sync_payload.get("counts")
            if isinstance(sync_payload.get("counts"), Mapping)
            else {}
        )
        source_seen = int(final_counts.get("source_seen", 0) or 0)
        sidecar_seen = int(final_counts.get("sidecar_seen", 0) or 0)
        final_unsynced = int(final_counts.get("unsynced", 0) or 0)
        cutoff_id = str(cutoff.get("cutoff_id") or "")
        source_sha256 = str(source.get("sha256") or "")
        if (
            not cutoff_id
            or len(source_sha256) != 64
            or final_unsynced != 0
            or source_seen != sidecar_seen
        ):
            raise RuntimeError(
                "automation requires one exactly reconciled source cutoff"
            )

        events, projection_sha256 = self._projection_state(self.store)
        occurred_values = [event.get("occurred_at") for event in events]
        known_values = [event.get("known_at") for event in events]
        for event in events:
            for decision in event.get("decision_refs", []):
                if isinstance(decision, Mapping):
                    known_values.append(decision.get("known_at"))
        as_of = self._max_timestamp(occurred_values)
        knowledge_cutoff = self._max_timestamp(known_values)
        if as_of is not None and knowledge_cutoff is None:
            knowledge_cutoff = as_of
        material = {
            "automation_version": REVIEW_AUTOMATION_VERSION,
            "source_cutoff_id": cutoff_id,
            "source_sha256": source_sha256,
            "artifact_namespace": self.artifact_namespace,
            "projection_sha256": projection_sha256,
            "as_of": as_of,
            "knowledge_cutoff": knowledge_cutoff,
            "scopes": list(REVIEW_AUTOMATION_SCOPES),
        }
        digest = sha256_text(canonical_json(material))
        return _AutomationPlan(
            run_id=f"reviewrun_{digest[:32]}",
            run_key=f"catch_up:{digest}",
            source_cutoff_id=cutoff_id,
            source_sha256=source_sha256,
            artifact_namespace=self.artifact_namespace,
            projection_sha256=projection_sha256,
            as_of=as_of,
            knowledge_cutoff=knowledge_cutoff,
            source_cutoff=knowledge_cutoff or cutoff.get("max_known_at"),
            sync_action=sync_action,
            source_seen=source_seen,
            sidecar_seen=sidecar_seen,
            unsynced=final_unsynced,
        )

    def _ensure_run(
        self,
        plan: _AutomationPlan,
        *,
        trigger: str,
    ) -> tuple[dict[str, Any], bool]:
        from src.investment_review.store import (
            DataConflictError,
            ReviewStoreError,
        )

        try:
            return self.store.get_review_run(plan.run_key), False
        except ReviewStoreError:
            pass
        try:
            self.store.save_review_run(
                {
                    "run_id": plan.run_id,
                    "run_key": plan.run_key,
                    "scope": "catch_up",
                    "requested_at": _utc_now(self._clock),
                    "source_cutoff": plan.source_cutoff,
                    "trigger": trigger,
                    "parameters": {
                        "automation_version": REVIEW_AUTOMATION_VERSION,
                        "source_cutoff_id": plan.source_cutoff_id,
                        "source_sha256": plan.source_sha256,
                        "artifact_namespace": plan.artifact_namespace,
                        "projection_sha256": plan.projection_sha256,
                        "as_of": plan.as_of,
                        "knowledge_cutoff": plan.knowledge_cutoff,
                        "scopes": list(REVIEW_AUTOMATION_SCOPES),
                    },
                }
            )
            return self.store.get_review_run(plan.run_key), True
        except DataConflictError:
            return self.store.get_review_run(plan.run_key), False

    def _supersede_stale_pending(
        self,
        plan: _AutomationPlan,
    ) -> None:
        """Close crash leftovers whose immutable input has been superseded."""

        for item in self.store.list_review_runs(scope="catch_up"):
            run = item.get("run")
            if not isinstance(run, Mapping):
                continue
            if run.get("run_key") == plan.run_key:
                continue
            if item.get("status") not in {"queued", "running", "failed"}:
                continue
            self._append_status(
                run_id=str(run["run_id"]),
                status="blocked",
                details={
                    "gap_codes": ["CATCH_UP_INPUT_SUPERSEDED"],
                    "superseded_by_run_key": plan.run_key,
                    "superseded_by_source_cutoff_id": (
                        plan.source_cutoff_id
                    ),
                    "retryable": False,
                },
            )

    def _append_status(
        self,
        *,
        run_id: str,
        status: str,
        details: Mapping[str, Any],
    ) -> dict[str, Any]:
        from src.investment_review.models import canonical_json, sha256_text
        from src.investment_review.time_utils import parse_datetime, utc_iso

        run = self.store.get_review_run(run_id)
        now = parse_datetime(_utc_now(self._clock), "UTC")
        prior_times = [
            parse_datetime(event["occurred_at"], "UTC")
            for item in self.store.list_review_runs(scope="catch_up")
            for event in item.get("history", [])
            if isinstance(event, Mapping) and event.get("occurred_at")
        ]
        if prior_times:
            previous = max(prior_times)
            if now <= previous:
                now = previous + timedelta(seconds=1)
        timestamp = utc_iso(now, "UTC")
        material = {
            "run_id": run_id,
            "status": status,
            "occurred_at": timestamp,
            "details": dict(details),
        }
        event_id = "runstatus_" + sha256_text(canonical_json(material))[:32]
        self.store.append_review_run_status(
            {
                "run_event_id": event_id,
                "run_id": run_id,
                "status": status,
                "occurred_at": timestamp,
                "known_at": timestamp,
                "details": dict(details),
            }
        )
        return self.store.get_review_run(run_id)

    def _failure_receipt(
        self,
        *,
        trigger: str,
        exc: Exception,
        run_key: str | None = None,
    ) -> dict[str, Any]:
        occurred_at = _utc_now(self._clock)
        try:
            from src.investment_review.time_utils import (
                parse_datetime,
                utc_iso,
            )

            occurred = parse_datetime(occurred_at, "UTC")
            prior_times = [
                parse_datetime(event["occurred_at"], "UTC")
                for item in self.store.list_review_runs(scope="catch_up")
                for event in item.get("history", [])
                if isinstance(event, Mapping) and event.get("occurred_at")
            ]
            if prior_times:
                previous = max(prior_times)
                if occurred <= previous:
                    occurred = previous + timedelta(seconds=1)
                    occurred_at = utc_iso(occurred, "UTC")
        except Exception:
            # The receipt must remain available when persistence itself fails.
            pass
        with self._state_lock:
            self._local_state = "failed"
            self._local_failure = {
                "error_type": type(exc).__name__,
                "occurred_at": occurred_at,
            }
        return {
            "schema_version": "investment_review.automation_cycle.v1",
            "status": "failed",
            "trigger": trigger,
            "run_key": run_key,
            "retryable": True,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    def enqueue(self, *, trigger: str) -> dict[str, Any]:
        if not self.config.enabled:
            return {
                "status": "disabled",
                "trigger": trigger,
                "reason": f"{REVIEW_AUTOMATION_ENV}=0",
            }
        try:
            with self._enqueue_lease:
                return self._enqueue_local(trigger=trigger)
        except TimeoutError:
            try:
                result = self._enqueue_local(
                    trigger=trigger,
                    supersede_stale=False,
                )
                if result.get("current_status") == "running":
                    return {
                        **result,
                        "status": "deferred",
                        "reason": "automation_consumer_active",
                        "retryable": True,
                    }
                return result
            except Exception as exc:
                return {
                    "status": "deferred",
                    "trigger": trigger,
                    "reason": "automation_lease_busy",
                    "retryable": True,
                    "error_type": type(exc).__name__,
                }
        except Exception as exc:
            return self._failure_receipt(trigger=trigger, exc=exc)

    def _enqueue_local(
        self,
        *,
        trigger: str,
        supersede_stale: bool = True,
    ) -> dict[str, Any]:
        """Persist one deterministic catch-up request without consuming it."""

        if not self.config.enabled:
            return {
                "status": "disabled",
                "trigger": trigger,
                "reason": f"{REVIEW_AUTOMATION_ENV}=0",
            }
        try:
            plan = self._prepare_plan(trigger=trigger)
            if supersede_stale:
                self._supersede_stale_pending(plan)
            existing, created = self._ensure_run(plan, trigger=trigger)
            if existing["status"] in {"succeeded", "partial", "blocked"}:
                with self._state_lock:
                    self._local_state = str(existing["status"])
                return {
                    "status": "deduplicated",
                    "trigger": trigger,
                    "run_id": plan.run_id,
                    "run_key": plan.run_key,
                    "current_status": existing["status"],
                }
            if created or existing["status"] not in {"queued", "running"}:
                existing = self._append_status(
                    run_id=plan.run_id,
                    status="queued",
                    details={
                        "trigger": trigger,
                        "source_cutoff_id": plan.source_cutoff_id,
                        "retryable": True,
                    },
                )
            with self._state_lock:
                self._local_state = str(existing["status"])
            return {
                "status": "queued",
                "trigger": trigger,
                "run_id": plan.run_id,
                "run_key": plan.run_key,
                "current_status": existing["status"],
            }
        except Exception as exc:
            return self._failure_receipt(trigger=trigger, exc=exc)

    def run_once(self, *, trigger: str) -> dict[str, Any]:
        if not self.config.enabled:
            return {
                "status": "disabled",
                "trigger": trigger,
                "reason": f"{REVIEW_AUTOMATION_ENV}=0",
            }
        try:
            with self._lease:
                return self._run_once_local(trigger=trigger)
        except Exception as exc:
            return self._failure_receipt(trigger=trigger, exc=exc)

    def _run_once_local(self, *, trigger: str) -> dict[str, Any]:
        """Synchronously consume the current deterministic catch-up task."""

        if not self.config.enabled:
            return {
                "status": "disabled",
                "trigger": trigger,
                "reason": f"{REVIEW_AUTOMATION_ENV}=0",
            }
        with self._cycle_lock:
            try:
                plan = self._prepare_plan(trigger=trigger)
                self._supersede_stale_pending(plan)
                existing, created = self._ensure_run(plan, trigger=trigger)
                if existing["status"] in {"succeeded", "partial", "blocked"}:
                    with self._state_lock:
                        self._local_state = str(existing["status"])
                    return {
                        "schema_version": "investment_review.automation_cycle.v1",
                        "status": "deduplicated",
                        "trigger": trigger,
                        "run_id": plan.run_id,
                        "run_key": plan.run_key,
                        "current_status": existing["status"],
                        "source_cutoff_id": plan.source_cutoff_id,
                        "scope_runs": (
                            existing.get("status_event") or {}
                        ).get("details", {}).get("scope_runs", []),
                    }
                if created or existing["status"] not in {"queued", "running"}:
                    existing = self._append_status(
                        run_id=plan.run_id,
                        status="queued",
                        details={
                            "trigger": trigger,
                            "source_cutoff_id": plan.source_cutoff_id,
                            "retryable": True,
                        },
                    )
                attempt = 1 + sum(
                    1
                    for item in existing["history"]
                    if item.get("status") == "running"
                )
                self._append_status(
                    run_id=plan.run_id,
                    status="running",
                    details={
                        "attempt": attempt,
                        "trigger": trigger,
                        "source_cutoff_id": plan.source_cutoff_id,
                        "sync_action": plan.sync_action,
                        "retryable": True,
                    },
                )
                with self._state_lock:
                    self._local_state = "running"

                if plan.as_of is None or plan.knowledge_cutoff is None:
                    terminal = self._append_status(
                        run_id=plan.run_id,
                        status="blocked",
                        details={
                            "attempt": attempt,
                            "trigger": trigger,
                            "source_cutoff_id": plan.source_cutoff_id,
                            "scope_runs": [],
                            "gap_codes": ["NO_SOURCE_EVENTS"],
                            "retryable": False,
                        },
                    )
                    with self._state_lock:
                        self._local_state = "blocked"
                    return {
                        "schema_version": "investment_review.automation_cycle.v1",
                        "status": terminal["status"],
                        "trigger": trigger,
                        "run_id": plan.run_id,
                        "run_key": plan.run_key,
                        "source_cutoff_id": plan.source_cutoff_id,
                        "scope_runs": [],
                        "gap_codes": ["NO_SOURCE_EVENTS"],
                        "retryable": False,
                    }

                runner = self._runner_factory()
                scope_runs: list[dict[str, Any]] = []
                failures: list[dict[str, str]] = []
                for scope in REVIEW_AUTOMATION_SCOPES:
                    if (
                        self._stop.is_set()
                        and threading.current_thread() is self._thread
                    ):
                        failures.append(
                            {
                                "scope": scope,
                                "error_type": "AutomationStopRequested",
                                "error": "automation worker stop requested",
                            }
                        )
                        scope_runs.append(
                            {
                                "scope": scope,
                                "run_id": None,
                                "run_key": None,
                                "status": "failed",
                                "content_id": None,
                            }
                        )
                        continue
                    try:
                        receipt = runner.run(
                            scope=scope,
                            as_of=plan.as_of,
                            knowledge_cutoff=plan.knowledge_cutoff,
                            dry_run=False,
                            trigger=f"automation_{trigger}",
                        )
                        scope_runs.append(
                            {
                                "scope": scope,
                                "run_id": receipt.get("run_id"),
                                "run_key": receipt.get("run_key"),
                                "status": receipt.get("status"),
                                "content_id": receipt.get("content_id"),
                            }
                        )
                    except Exception as exc:
                        failures.append(
                            {
                                "scope": scope,
                                "error_type": type(exc).__name__,
                                "error": str(exc),
                            }
                        )
                        scope_runs.append(
                            {
                                "scope": scope,
                                "run_id": None,
                                "run_key": None,
                                "status": "failed",
                                "content_id": None,
                            }
                        )

                verified_run_key: str | None = None
                try:
                    verified_plan = self._prepare_plan(
                        trigger=f"{trigger}_post_cycle_verify"
                    )
                    verified_run_key = verified_plan.run_key
                    if verified_plan.run_key != plan.run_key:
                        failures.append(
                            {
                                "scope": "cycle",
                                "error_type": "AutomationInputDrift",
                                "error": (
                                    "source or canonical sidecar input changed "
                                    "during the automation cycle"
                                ),
                            }
                        )
                except Exception as exc:
                    failures.append(
                        {
                            "scope": "cycle",
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        }
                    )

                statuses = {str(item.get("status") or "") for item in scope_runs}
                if failures or "failed" in statuses:
                    final_status = "failed"
                elif "blocked" in statuses:
                    final_status = "blocked"
                elif "partial" in statuses:
                    final_status = "partial"
                else:
                    final_status = "succeeded"
                retryable = final_status == "failed"
                details = {
                    "attempt": attempt,
                    "trigger": trigger,
                    "source_cutoff_id": plan.source_cutoff_id,
                    "projection_sha256": plan.projection_sha256,
                    "sync_action": plan.sync_action,
                    "counts": {
                        "source_seen": plan.source_seen,
                        "sidecar_seen": plan.sidecar_seen,
                        "unsynced": plan.unsynced,
                    },
                    "scope_runs": scope_runs,
                    "failures": failures,
                    "post_cycle_run_key": verified_run_key,
                    "retryable": retryable,
                }
                self._append_status(
                    run_id=plan.run_id,
                    status=final_status,
                    details=details,
                )
                with self._state_lock:
                    self._local_state = final_status
                    if final_status != "failed":
                        self._local_failure = None
                return {
                    "schema_version": "investment_review.automation_cycle.v1",
                    "status": final_status,
                    "trigger": trigger,
                    "run_id": plan.run_id,
                    "run_key": plan.run_key,
                    "source_cutoff_id": plan.source_cutoff_id,
                    "projection_sha256": plan.projection_sha256,
                    "as_of": plan.as_of,
                    "knowledge_cutoff": plan.knowledge_cutoff,
                    "sync_action": plan.sync_action,
                    "counts": details["counts"],
                    "scope_runs": scope_runs,
                    "failures": failures,
                    "retryable": retryable,
                }
            except Exception as exc:
                return self._failure_receipt(
                    trigger=trigger,
                    exc=exc,
                    run_key=locals().get("plan").run_key
                    if isinstance(locals().get("plan"), _AutomationPlan)
                    else None,
                )

    def request(self, *, trigger: str) -> dict[str, Any]:
        """Coalesce a background request; the persistent key handles replay."""

        if not self.config.enabled:
            return {
                "status": "disabled",
                "trigger": trigger,
                "reason": f"{REVIEW_AUTOMATION_ENV}=0",
            }
        with self._state_lock:
            before = len(self._pending_triggers)
            self._pending_triggers.add(str(trigger or "manual"))
            self._local_state = "queued"
            depth = len(self._pending_triggers)
        self._wake.set()
        return {
            "status": "deduplicated" if depth == before else "queued",
            "trigger": trigger,
            "queue_depth": depth,
        }

    def _block_continuous_drift(
        self,
        result: Mapping[str, Any],
    ) -> None:
        run_id = str(result.get("run_id") or "")
        if not run_id:
            return
        try:
            with self._lease:
                current = self.store.get_review_run(run_id)
                if current.get("status") != "failed":
                    return
                self._append_status(
                    run_id=run_id,
                    status="blocked",
                    details={
                        "gap_codes": [
                            "SOURCE_CONTINUED_CHANGING_DURING_AUTOMATION"
                        ],
                        "retryable": False,
                    },
                )
            with self._state_lock:
                self._local_state = "blocked"
        except Exception as exc:
            self._failure_receipt(
                trigger="continuous_drift_block",
                exc=exc,
                run_key=str(result.get("run_key") or "") or None,
            )

    def _worker(self) -> None:
        immediate_drift_retry_used = False
        while not self._stop.is_set():
            self._wake.wait(self.config.interval_seconds)
            self._wake.clear()
            if self._stop.is_set():
                break
            with self._state_lock:
                triggers = sorted(self._pending_triggers)
                self._pending_triggers.clear()
            trigger = (
                "+".join(triggers)
                if triggers
                else "periodic_catch_up"
            )
            result = self.run_once(trigger=trigger)
            failures = result.get("failures")
            input_drift = (
                isinstance(failures, list)
                and any(
                    isinstance(item, Mapping)
                    and item.get("error_type") == "AutomationInputDrift"
                    for item in failures
                )
            )
            if input_drift and not self._stop.is_set():
                if not immediate_drift_retry_used:
                    immediate_drift_retry_used = True
                    self.request(trigger="input_drift_retry")
                else:
                    self._block_continuous_drift(result)
                    immediate_drift_retry_used = False
            else:
                immediate_drift_retry_used = False
        with self._state_lock:
            if self._local_state not in {"failed", "blocked"}:
                self._local_state = "stopped"

    def start(self) -> dict[str, Any]:
        if not self.config.enabled:
            return self.status()
        already_running = False
        with self._state_lock:
            if self._thread is not None and self._thread.is_alive():
                already_running = True
            else:
                self._stop.clear()
                self._thread = threading.Thread(
                    target=self._worker,
                    name="investment-review-automation",
                    daemon=True,
                )
                self._thread.start()
        if already_running:
            return self.status()
        if self.config.startup_catch_up:
            self.request(trigger="startup_catch_up")
        return self.status()

    def stop(self, *, timeout: float = 5.0) -> dict[str, Any]:
        with self._state_lock:
            thread = self._thread
            if thread is not None:
                self._local_state = "stopping"
        if thread is None:
            return self.status()
        self._stop.set()
        self._wake.set()
        thread.join(timeout=max(0.0, float(timeout)))
        return self.status()

    def status(self) -> dict[str, Any]:
        with self._state_lock:
            thread = self._thread
            pending = len(self._pending_triggers)
            local_state = self._local_state
            local_failure = (
                dict(self._local_failure)
                if self._local_failure is not None
                else None
            )
        return review_automation_health(
            self.store,
            enabled=self.config.enabled,
            worker_alive=bool(thread is not None and thread.is_alive()),
            queue_depth=pending,
            local_state=local_state,
            local_failure=local_failure,
        )


def _default_post_commit_sync(
    *,
    portfolio_db: Path,
    review_db: Path,
    trigger: str,
) -> Mapping[str, Any]:
    """Synchronize and enqueue one non-blocking transaction-external catch-up."""

    from src.investment_review.sync_service import sync_after_portfolio_commit

    result = dict(
        sync_after_portfolio_commit(
            portfolio_db,
            explicit_review_db=review_db,
        )
    )
    try:
        config = review_automation_config()
    except Exception as exc:
        result["automation"] = {
            "status": "failed",
            "trigger": trigger,
            "reason": "invalid_review_automation_configuration",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "retryable": True,
        }
        return result
    if not config.enabled:
        result["automation"] = {
            "status": "disabled",
            "trigger": trigger,
            "reason": f"{REVIEW_AUTOMATION_ENV}=0",
        }
        return result
    try:
        if POST_COMMIT_AUTOMATION_HOOK is not None:
            automation = dict(
                POST_COMMIT_AUTOMATION_HOOK(
                    portfolio_db=portfolio_db,
                    review_db=review_db,
                    trigger=trigger,
                )
            )
        else:
            automation = ReviewAutomationCoordinator(
                portfolio_db=portfolio_db,
                review_db=review_db,
                config=config,
            ).enqueue(trigger=trigger)
    except Exception as exc:
        automation = {
            "status": "failed",
            "trigger": trigger,
            "reason": "review_automation_failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "retryable": True,
        }
    result["automation"] = automation
    return result


def trigger_post_commit_review_sync(
    portfolio_db: str | Path,
    *,
    review_db: str | Path | None = None,
) -> dict[str, Any]:
    """Run one best-effort catch-up after a committed statement import.

    Every return value is suitable for inclusion in the existing JSON summary.
    Configuration and review-side failures are visible but never raised.
    """

    try:
        selected_review_db = configured_review_database(review_db)
    except Exception as exc:
        return {
            "status": "failed",
            "trigger": "portfolio_statement_post_commit",
            "reason": "invalid_review_database_configuration",
            "error": str(exc),
        }

    if selected_review_db is None:
        return {
            "status": "disabled",
            "trigger": "portfolio_statement_post_commit",
            "reason": f"{REVIEW_DATABASE_ENV} is not configured",
        }
    try:
        review_db_exists = selected_review_db.is_file()
        source = Path(portfolio_db).resolve(strict=False)
    except Exception as exc:
        return {
            "status": "failed",
            "trigger": "portfolio_statement_post_commit",
            "review_db": str(selected_review_db),
            "reason": "review_sync_path_check_failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    if not review_db_exists:
        return {
            "status": "not_initialized",
            "trigger": "portfolio_statement_post_commit",
            "review_db": str(selected_review_db),
            "reason": "configured review sidecar does not exist",
        }

    if source == selected_review_db:
        return {
            "status": "failed",
            "trigger": "portfolio_statement_post_commit",
            "review_db": str(selected_review_db),
            "reason": "portfolio_and_review_database_must_be_separate",
        }

    hook = POST_COMMIT_SYNC_HOOK or _default_post_commit_sync
    try:
        result = dict(
            hook(
                portfolio_db=source,
                review_db=selected_review_db,
                trigger="portfolio_statement_post_commit",
            )
        )
    except Exception as exc:  # review failures must not roll back portfolio state
        return {
            "status": "failed",
            "trigger": "portfolio_statement_post_commit",
            "review_db": str(selected_review_db),
            "reason": "review_sync_failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    result.setdefault("status", "succeeded")
    result.setdefault("trigger", "portfolio_statement_post_commit")
    result.setdefault("review_db", str(selected_review_db))
    return result
