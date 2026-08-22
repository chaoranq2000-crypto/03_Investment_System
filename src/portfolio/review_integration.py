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
from copy import deepcopy
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
REVIEW_CHECKPOINT_AUTOMATION_VERSION = (
    "investment_review.open_checkpoint_catch_up.v1"
)
REVIEW_CHECKPOINT_PLAN_SCHEMA_VERSION = (
    "investment_review.open_checkpoint_plan.v1"
)
REVIEW_CHECKPOINT_AUTOMATION_VERSION_V2 = (
    "investment_review.open_checkpoint_catch_up.v2"
)
REVIEW_CHECKPOINT_PLAN_SCHEMA_VERSION_V2 = (
    "investment_review.open_checkpoint_plan.v2"
)
REVIEW_AUTOMATION_MARKET_INPUT_MANIFEST_VERSION = (
    "investment_review.automation_market_input_manifest.v1"
)
REVIEW_AUTOMATION_MARKET_INPUT_MANIFEST_VERSION_V2 = (
    "investment_review.automation_market_input_manifest.v2"
)
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
_DEFAULT_CHECKPOINT_MARKET_RESOLVER = object()


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
        task_namespace: str = "investment_review_product_completion_v2",
        timeout_seconds: float = AUTOMATION_LEASE_TIMEOUT_SECONDS,
    ) -> None:
        if task_namespace not in {
            "investment_review_product_completion_v2",
            "investment_review_product_completion_v3",
            "investment_review_product_completion_v4",
        }:
            raise ValueError("unsupported automation lease task namespace")
        identity = hashlib.sha256(
            str(review_db.resolve(strict=False)).casefold().encode("utf-8")
        ).hexdigest()[:32]
        self.path = (
            repo_root
            / ".codex_tmp"
            / task_namespace
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
    perspective: str = "user"


@dataclass(frozen=True)
class _AutomationPlan:
    run_id: str
    run_key: str
    source_cutoff_id: str
    source_sha256: str
    artifact_namespace: str
    projection_sha256: str
    checkpoint_plan: dict[str, Any] | None
    checkpoint_plan_sha256: str | None
    market_input_manifest: dict[str, Any] | None
    market_input_sha256: str | None
    checkpoint_slot: str | None
    as_of: str | None
    knowledge_cutoff: str | None
    source_cutoff: str | None
    sync_action: str
    source_seen: int
    sidecar_seen: int
    unsynced: int
    perspective: str


class _FrozenAutomationMarketResolver:
    """Serve only the exact projections closed by one automation plan.

    The pre-bundle resolver is deliberately not retained here.  Runner scopes
    therefore cannot re-query a provider/cache and silently consume B after
    the task key was bound to A.
    """

    def __init__(self, manifest: Mapping[str, Any]) -> None:
        self._perspective = str(manifest.get("perspective") or "user")
        if self._perspective not in {"user", "system"}:
            raise RuntimeError(
                "frozen market manifest perspective is malformed"
            )
        self._items: dict[
            tuple[str, str, str, str, str], dict[str, Any]
        ] = {}
        raw_items = manifest.get("items")
        if not isinstance(raw_items, list):
            raise RuntimeError("frozen market manifest items are malformed")
        for raw in raw_items:
            if not isinstance(raw, Mapping):
                raise RuntimeError("frozen market manifest item is malformed")
            item = deepcopy(dict(raw))
            key = (
                str(item.get("episode_id") or ""),
                str(item.get("instrument_id") or ""),
                str(item.get("perspective") or self._perspective),
                str(item.get("as_of") or ""),
                str(item.get("knowledge_cutoff") or ""),
            )
            if not all(key) or key in self._items:
                raise RuntimeError(
                    "frozen market manifest identity is missing or duplicated"
                )
            self._items[key] = item
        self._lock = threading.Lock()
        self._consumed: list[dict[str, Any]] = []

    @staticmethod
    def _episode_instrument(episode: Mapping[str, Any]) -> str:
        scope = (
            episode.get("scope")
            if isinstance(episode.get("scope"), Mapping)
            else {}
        )
        return str(
            scope.get("instrument_id")
            or episode.get("instrument_id")
            or episode.get("symbol")
            or ""
        ).upper()

    def cursor(self) -> int:
        with self._lock:
            return len(self._consumed)

    def consumed_since(self, cursor: int) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self._consumed[cursor:])

    def __call__(
        self,
        *,
        episode: Mapping[str, Any],
        perspective: str = "user",
        as_of: str,
        knowledge_cutoff: str,
        request_budget: object | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        del request_budget
        episode_id = str(episode.get("episode_id") or "")
        instrument_id = self._episode_instrument(episode)
        key = (
            episode_id,
            instrument_id,
            str(perspective),
            str(as_of),
            str(knowledge_cutoff),
        )
        item = self._items.get(key)
        if item is None:
            raise RuntimeError(
                "runner requested market input outside the frozen automation plan"
            )
        consumed = {
            "episode_id": episode_id,
            "instrument_id": instrument_id,
            "as_of": str(as_of),
            "knowledge_cutoff": str(knowledge_cutoff),
            "market_input_content_id": item.get(
                "market_input_content_id"
            ),
            "market_requirement_id": item.get("market_requirement_id"),
            "market_resolution_id": item.get("market_resolution_id"),
            "fetch_receipt_ids": deepcopy(
                item.get("fetch_receipt_ids", [])
            ),
            "source_ids": deepcopy(item.get("source_ids", [])),
        }
        if "perspective" in item:
            consumed.update(
                {
                    "perspective": str(perspective),
                    "operation_anchor_event_id": item.get(
                        "operation_anchor_event_id"
                    ),
                    "operation_anchor_at": item.get(
                        "operation_anchor_at"
                    ),
                    "operation_anchor_ordering_key": deepcopy(
                        item.get("operation_anchor_ordering_key")
                    ),
                    "information_time_policy_version": item.get(
                        "information_time_policy_version"
                    ),
                }
            )
        with self._lock:
            self._consumed.append(consumed)
        projection = item.get("projection")
        if not isinstance(projection, Mapping):
            if item.get("error_code") == (
                "MARKET_CONTEXT_WITHHELD_BY_CUTOFF"
            ):
                from src.investment_review.market_context_adapter import (
                    MarketContextCutoffUnavailableError,
                )

                raise MarketContextCutoffUnavailableError(
                    "frozen market context is unavailable at the requested "
                    "knowledge cutoff"
                )
            raise RuntimeError("MARKET_CONTEXT_RESOLUTION_UNAVAILABLE")
        return deepcopy(dict(projection))


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
                    "checkpoint_ids": item.get("checkpoint_ids", []),
                    "checkpoint_count": item.get(
                        "checkpoint_count", 0
                    ),
                }
            )
    projection = {
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
        "checkpoint_plan_sha256": parameters.get(
            "checkpoint_plan_sha256"
        ),
        "market_input_sha256": parameters.get("market_input_sha256"),
        "checkpoint_slot": parameters.get("checkpoint_slot"),
        "attempt": details.get("attempt"),
        "retryable": details.get("retryable"),
        "scope_runs": projected_scopes,
    }
    if "perspective" in parameters:
        projection["perspective"] = parameters.get("perspective")
    return projection


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
        checkpoint_market_resolver: (
            Callable[..., Mapping[str, Any]] | None | object
        ) = _DEFAULT_CHECKPOINT_MARKET_RESOLVER,
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
        if self.config.perspective not in {"user", "system"}:
            raise ValueError(
                "review automation perspective must be user or system"
            )
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.sync_service = sync_service or ReviewSyncService(
            self.portfolio_db,
            review_db=self.review_db,
            mapping_path=self.mapping_path,
            repo_root=self.repo_root,
        )
        self.store = store or ReviewStore(self.review_db)
        store_status = self.store.status()
        self._reviewability_schema_version = int(
            store_status.get("reviewability_schema_version") or 0
        )
        if (
            self._reviewability_schema_version < 2
            and self.config.perspective != "user"
        ):
            raise ValueError(
                "system-perspective automation requires reviewability v2"
            )
        if (
            runner_factory is not None
            and checkpoint_market_resolver
            is _DEFAULT_CHECKPOINT_MARKET_RESOLVER
        ):
            raise ValueError(
                "runner_factory requires explicit "
                "checkpoint_market_resolver=None"
            )
        if (
            runner_factory is not None
            and checkpoint_market_resolver is not None
        ):
            raise ValueError(
                "runner_factory and checkpoint_market_resolver are "
                "mutually exclusive"
            )
        if checkpoint_market_resolver is _DEFAULT_CHECKPOINT_MARKET_RESOLVER:
            from src.investment_review.market_context_adapter import (
                MarketContextAdapter,
            )

            self._checkpoint_market_resolver: (
                Callable[..., Mapping[str, Any]] | None
            ) = MarketContextAdapter(
                cache_root=(
                    self.repo_root
                    / ".codex_tmp"
                    / "investment_review_product_completion_v3"
                    / "market_cache"
                ),
                clock=self._clock,
            )
        elif checkpoint_market_resolver is None or callable(
            checkpoint_market_resolver
        ):
            self._checkpoint_market_resolver = checkpoint_market_resolver
        else:
            raise ValueError(
                "checkpoint_market_resolver must be callable or None"
            )
        self._runner_factory = runner_factory or (
            lambda: ReviewRunner(
                review_db=self.review_db,
                portfolio_db=self.portfolio_db,
                mapping_path=self.mapping_path,
                artifact_root=self.artifact_root,
                repo_root=self.repo_root,
                checkpoint_market_resolver=(
                    self._checkpoint_market_resolver
                ),
            )
        )
        self._cycle_lock = threading.Lock()
        lease_namespace = (
            "investment_review_product_completion_v4"
            if self._reviewability_schema_version >= 2
            else "investment_review_product_completion_v3"
            if self._reviewability_schema_version == 1
            else "investment_review_product_completion_v2"
        )
        self._lease = _AutomationLease(
            repo_root=self.repo_root,
            review_db=self.review_db,
            task_namespace=lease_namespace,
        )
        self._enqueue_lease = _AutomationLease(
            repo_root=self.repo_root,
            review_db=self.review_db,
            task_namespace=lease_namespace,
            timeout_seconds=0.05,
        )
        self._state_lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._pending_triggers: set[str] = set()
        self._thread: threading.Thread | None = None
        self._local_state = "idle" if self.config.enabled else "disabled"
        self._local_failure: dict[str, Any] | None = None

    def _projection_state(
        self, store: Any
    ) -> tuple[list[dict[str, Any]], str]:
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
        material: dict[str, Any] = {
            "events": events,
            "linked_decisions": decisions,
        }
        if self._reviewability_schema_version >= 2:
            material["event_observation_evidence"] = (
                store.list_event_observation_evidence(
                    event_ids=[
                        str(event.get("event_id") or "")
                        for event in events
                        if event.get("event_id")
                    ]
                )
            )
            material["perspective"] = self.config.perspective
        digest = sha256_text(canonical_json(material))
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

    @staticmethod
    def _automation_market_projection(
        resolved: object,
        *,
        episode_id: str,
        instrument_id: str,
        as_of: str,
        knowledge_cutoff: str,
        perspective: str = "user",
    ) -> dict[str, Any]:
        """Validate and close one exact runner-consumable market projection."""

        from src.investment_review.artifact_io import canonical_json_bytes
        from src.investment_review.market_context_adapter import (
            market_context_runner_projection,
        )
        from src.investment_review.review_runner import (
            LEGACY_CHECKPOINT_MARKET_PROJECTION_VERSION,
            MARKET_CONTEXT_RUNNER_PROJECTION_FIELDS,
            MARKET_CONTEXT_RUNNER_PROJECTION_FIELDS_V2,
        )

        if not isinstance(resolved, Mapping):
            raise RuntimeError(
                "automation market resolver must return a mapping"
            )
        fields = frozenset(resolved)
        legacy_fields = frozenset(
            {"market_axis", "market_fallback", "market_gaps"}
        )
        if fields == legacy_fields:
            legacy_resolution = {
                "schema_version": (
                    LEGACY_CHECKPOINT_MARKET_PROJECTION_VERSION
                ),
                "as_of": as_of,
                "knowledge_cutoff": knowledge_cutoff,
                "market_axis": deepcopy(dict(resolved["market_axis"])),
                "market_fallback": deepcopy(
                    dict(resolved["market_fallback"])
                ),
                "market_gaps": deepcopy(list(resolved["market_gaps"])),
            }
            content_id = "sha256:" + hashlib.sha256(
                canonical_json_bytes(legacy_resolution)
            ).hexdigest()
            return {
                "episode_id": episode_id,
                "instrument_id": instrument_id,
                "as_of": as_of,
                "knowledge_cutoff": knowledge_cutoff,
                "projection_kind": "legacy",
                "market_input_content_id": content_id,
                "market_requirement_id": None,
                "market_resolution_id": None,
                "fetch_receipt_ids": [],
                "source_ids": [],
                "projection": deepcopy(dict(resolved)),
            }
        if fields not in {
            MARKET_CONTEXT_RUNNER_PROJECTION_FIELDS,
            MARKET_CONTEXT_RUNNER_PROJECTION_FIELDS_V2,
        }:
            raise RuntimeError(
                "automation market resolver returned unsupported fields"
            )
        projection = market_context_runner_projection(resolved)
        if dict(projection) != dict(resolved):
            raise RuntimeError(
                "automation market resolver projection drifted"
            )
        resolution = projection.get("resolution")
        requirement = (
            resolution.get("requirement")
            if isinstance(resolution, Mapping)
            and isinstance(resolution.get("requirement"), Mapping)
            else {}
        )
        if (
            projection.get("as_of") != as_of
            or projection.get("knowledge_cutoff") != knowledge_cutoff
            or str(requirement.get("instrument_id") or "").upper()
            != instrument_id
        ):
            raise RuntimeError(
                "automation market projection does not bind the requested "
                "instrument/as_of/knowledge_cutoff"
            )
        is_v2 = fields == MARKET_CONTEXT_RUNNER_PROJECTION_FIELDS_V2
        if is_v2 and (
            projection.get("perspective") != perspective
            or not projection.get("operation_anchor_event_id")
            or not projection.get("operation_anchor_at")
            or not isinstance(
                projection.get("operation_anchor_ordering_key"), list
            )
            or not projection.get("information_time_policy_version")
        ):
            raise RuntimeError(
                "automation v2 market projection does not bind perspective, "
                "operation anchor and information-time policy"
            )
        fallback = projection.get("market_fallback")
        receipts = (
            fallback.get("fetch_receipts", [])
            if isinstance(fallback, Mapping)
            else []
        )
        supplementals = projection.get("supplemental_sources", [])
        receipt_ids = sorted(
            str(item.get("receipt_id") or "")
            for item in receipts
            if isinstance(item, Mapping) and item.get("receipt_id")
        )
        source_ids = sorted(
            str(item.get("source_id") or "")
            for item in supplementals
            if isinstance(item, Mapping) and item.get("source_id")
        )
        item = {
            "episode_id": episode_id,
            "instrument_id": instrument_id,
            "as_of": as_of,
            "knowledge_cutoff": knowledge_cutoff,
            "projection_kind": "full",
            "market_input_content_id": str(
                projection["market_input_content_id"]
            ),
            "market_requirement_id": str(
                projection["market_requirement_id"]
            ),
            "market_resolution_id": str(
                projection["market_resolution_id"]
            ),
            "fetch_receipt_ids": receipt_ids,
            "source_ids": source_ids,
            "projection": deepcopy(dict(projection)),
        }
        if is_v2:
            item.update(
                {
                    "perspective": perspective,
                    "operation_anchor_event_id": str(
                        projection["operation_anchor_event_id"]
                    ),
                    "operation_anchor_at": str(
                        projection["operation_anchor_at"]
                    ),
                    "operation_anchor_ordering_key": deepcopy(
                        projection["operation_anchor_ordering_key"]
                    ),
                    "information_time_policy_version": str(
                        projection["information_time_policy_version"]
                    ),
                }
            )
        return item

    def _market_input_manifest(
        self,
        *,
        episodes: list[dict[str, Any]],
        operation_review: Mapping[str, Any],
        perspective: str,
        as_of: str,
        knowledge_cutoff: str,
        frozen_manifest: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Resolve/freeze market inputs once before runner scope execution."""

        from src.investment_review.models import canonical_json, sha256_text
        from src.investment_review.market_context_adapter import (
            MarketContextCutoffUnavailableError,
            MarketRequestBudget,
        )
        from src.investment_review.time_utils import utc_iso

        resolver = self._checkpoint_market_resolver
        if resolver is None:
            return None
        manifest_version = (
            REVIEW_AUTOMATION_MARKET_INPUT_MANIFEST_VERSION_V2
            if self._reviewability_schema_version >= 2
            else REVIEW_AUTOMATION_MARKET_INPUT_MANIFEST_VERSION
        )
        if frozen_manifest is not None:
            manifest = deepcopy(dict(frozen_manifest))
            content_id = str(manifest.get("content_id") or "")
            material = {
                key: value
                for key, value in manifest.items()
                if key not in {"content_id", "request_budget"}
            }
            expected = "sha256:" + sha256_text(canonical_json(material))
            if (
                manifest.get("schema_version") != manifest_version
                or content_id != expected
                or not isinstance(manifest.get("items"), list)
                or (
                    self._reviewability_schema_version >= 2
                    and manifest.get("perspective") != perspective
                )
            ):
                raise RuntimeError(
                    "frozen automation market manifest failed replay"
                )
            return manifest
        request_budget = MarketRequestBudget()
        items: list[dict[str, Any]] = []
        for episode in sorted(
            episodes, key=lambda item: str(item.get("episode_id") or "")
        ):
            episode_id = str(episode.get("episode_id") or "")
            if not episode_id:
                raise RuntimeError(
                    "automation market planning requires episode_id"
                )
            scope = (
                episode.get("scope")
                if isinstance(episode.get("scope"), Mapping)
                else {}
            )
            instrument_id = str(
                scope.get("instrument_id")
                or episode.get("instrument_id")
                or episode.get("symbol")
                or ""
            ).upper()
            if not instrument_id:
                raise RuntimeError(
                    "automation market planning requires instrument_id"
                )
            target_as_of = (
                str(episode.get("closed_at") or "")
                if episode.get("status") == "closed"
                else as_of
            )
            target_as_of = utc_iso(target_as_of, "UTC")
            try:
                resolver_kwargs: dict[str, Any] = {
                    "portfolio_db": self.portfolio_db,
                    "review_db": self.review_db,
                    "episode": deepcopy(episode),
                    "operation_review": deepcopy(dict(operation_review)),
                    "knowledge_provenance": {},
                    "ledger_snapshot_reconstruction": {},
                    "perspective": perspective,
                    "as_of": target_as_of,
                    "knowledge_cutoff": knowledge_cutoff,
                    "request_budget": request_budget,
                }
                if self._reviewability_schema_version >= 2:
                    resolver_kwargs["market_contract_version"] = "v2"
                resolved = resolver(**resolver_kwargs)
            except Exception as exc:
                if self._reviewability_schema_version >= 2:
                    raise RuntimeError(
                        "v2 market resolver must return a canonical limitation "
                        "projection instead of aborting automation"
                    ) from exc
                cutoff_unavailable = isinstance(
                    exc, MarketContextCutoffUnavailableError
                )
                items.append(
                    {
                        "episode_id": episode_id,
                        "instrument_id": instrument_id,
                        "as_of": target_as_of,
                        "knowledge_cutoff": knowledge_cutoff,
                        "projection_kind": "unavailable",
                        "market_input_content_id": None,
                        "market_requirement_id": None,
                        "market_resolution_id": None,
                        "fetch_receipt_ids": [],
                        "source_ids": [],
                        "projection": None,
                        "error_code": (
                            "MARKET_CONTEXT_WITHHELD_BY_CUTOFF"
                            if cutoff_unavailable
                            else "MARKET_CONTEXT_RESOLUTION_UNAVAILABLE"
                        ),
                        "error_type": type(exc).__name__,
                    }
                )
                continue
            planned_item = self._automation_market_projection(
                resolved,
                episode_id=episode_id,
                instrument_id=instrument_id,
                perspective=perspective,
                as_of=target_as_of,
                knowledge_cutoff=knowledge_cutoff,
            )
            if self._reviewability_schema_version >= 2:
                from src.investment_review.review_checkpoint import (
                    derive_review_checkpoint_operation_anchor,
                )

                anchor_checkpoint_type = {
                    "open": "active_checkpoint",
                    "closed": "exit",
                }.get(str(episode.get("status") or ""))
                if anchor_checkpoint_type is None:
                    raise RuntimeError(
                        "v2 automation market planning requires a proven "
                        "episode lifecycle"
                    )
                expected_anchor = derive_review_checkpoint_operation_anchor(
                    episode,
                    operation_review=operation_review,
                    checkpoint_type=anchor_checkpoint_type,
                    checkpoint_as_of=target_as_of,
                )
                if any(
                    planned_item.get(field) != expected_anchor.get(field)
                    for field in (
                        "operation_anchor_event_id",
                        "operation_anchor_at",
                        "operation_anchor_ordering_key",
                    )
                ):
                    raise RuntimeError(
                        "automation market projection drifted from the "
                        "canonical operation anchor"
                    )
            items.append(planned_item)
        budget = request_budget.snapshot()
        if (
            budget["used_requests"] > budget["max_requests"]
            or budget["reserved_requests"] != 0
        ):
            raise RuntimeError("automation market request budget did not settle")
        material = {
            "schema_version": manifest_version,
            "as_of": as_of,
            "knowledge_cutoff": knowledge_cutoff,
            "items": items,
        }
        if self._reviewability_schema_version >= 2:
            material["perspective"] = perspective
        return {
            **material,
            # Runtime evidence is persisted for audit, but is deliberately
            # outside semantic identity: a first provider fetch and a later
            # hit on its exact frozen cache must have the same task key.
            "request_budget": budget,
            "content_id": "sha256:"
            + sha256_text(canonical_json(material)),
        }

    def _open_checkpoint_plan(
        self,
        *,
        events: list[dict[str, Any]],
        latest_event_at: str | None,
        latest_known_at: str | None,
        frozen_market_manifest: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Plan one deterministic periodic cutoff for currently open episodes.

        This planner only binds semantic checkpoint identities.  It does not
        assemble market evidence or persist checkpoints; those remain runner
        responsibilities.  Legacy sidecars keep the v1 event-cutoff key.
        """

        from src.investment_review.episodes import (
            build_episode_collection,
            validate_episode_collection,
        )
        from src.investment_review.operation_review import (
            build_operation_review,
            replay_validate_operation_review,
            validate_operation_review,
        )
        from src.investment_review.models import canonical_json, sha256_text
        from src.investment_review.time_utils import parse_datetime, utc_iso

        status = self.store.status()
        reviewability_schema_version = int(
            status.get("reviewability_schema_version") or 0
        )
        if reviewability_schema_version not in {1, 2} or not events:
            return None, None

        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("review automation clock must be timezone-aware")
        now_utc = now.astimezone(timezone.utc)
        slot_seconds = max(1, int(round(self.config.interval_seconds)))
        slot_epoch = int(now_utc.timestamp()) // slot_seconds * slot_seconds
        slot_time = datetime.fromtimestamp(slot_epoch, tz=timezone.utc)
        if latest_event_at is not None:
            latest_event_time = parse_datetime(latest_event_at, "UTC")
            if slot_time < latest_event_time:
                slot_time = latest_event_time
        checkpoint_cutoff = utc_iso(slot_time, "UTC")

        known_candidates = [
            value
            for value in (latest_known_at, checkpoint_cutoff)
            if value is not None
        ]
        knowledge_cutoff = self._max_timestamp(known_candidates)
        if knowledge_cutoff is None:
            raise RuntimeError(
                "open checkpoint planning requires knowledge_cutoff"
            )
        perspective_events = events
        if reviewability_schema_version >= 2:
            from src.investment_review.knowledge_provenance import (
                build_knowledge_provenance,
                project_perspective_event_inputs,
                replay_validate_knowledge_provenance,
                validate_knowledge_provenance,
            )

            observation_evidence = self.store.list_event_observation_evidence(
                event_ids=[
                    str(event.get("event_id") or "")
                    for event in events
                    if event.get("event_id")
                ]
            )
            knowledge_provenance = build_knowledge_provenance(
                events,
                observation_evidence=observation_evidence,
                perspective=self.config.perspective,
                as_of=checkpoint_cutoff,
                knowledge_cutoff=knowledge_cutoff,
            )
            knowledge_validation = validate_knowledge_provenance(
                knowledge_provenance
            )
            knowledge_replay = replay_validate_knowledge_provenance(
                knowledge_provenance,
                event_inputs=events,
                observation_evidence=observation_evidence,
            )
            if (
                knowledge_validation.get("validation_status") == "blocked"
                or knowledge_replay.get("validation_status") == "blocked"
                or not isinstance(
                    knowledge_replay.get("source_verification"), Mapping
                )
                or knowledge_replay["source_verification"].get("status")
                != "verified"
            ):
                raise RuntimeError(
                    "automation perspective projection is not replayable"
                )
            perspective_events = project_perspective_event_inputs(
                knowledge_provenance,
                events,
            )

        collection = build_episode_collection(
            perspective_events,
            cutoff_at=checkpoint_cutoff,
            snapshot_references=[],
        )
        validation = validate_episode_collection(collection)
        if validation.get("validation_status") == "blocked":
            raise RuntimeError(
                "open checkpoint planning requires a validated episode "
                "collection"
            )
        operation_review = build_operation_review(
            collection,
            event_inputs=perspective_events,
        )
        operation_validation = validate_operation_review(operation_review)
        operation_replay = replay_validate_operation_review(
            operation_review,
            episode_collection=collection,
            event_inputs=perspective_events,
        )
        if (
            operation_validation.get("validation_status") == "blocked"
            or operation_replay.get("validation_status") == "blocked"
            or not isinstance(
                operation_replay.get("source_verification"), Mapping
            )
            or operation_replay["source_verification"].get("status")
            != "verified"
        ):
            raise RuntimeError(
                "open checkpoint planning requires a replayable operation "
                "review"
            )
        episodes = sorted(
            (
                deepcopy(dict(item))
                for item in collection.get("episodes", [])
                if isinstance(item, Mapping)
                and item.get("episode_id")
            ),
            key=lambda item: str(item.get("episode_id") or ""),
        )
        open_episodes = [
            item for item in episodes if item.get("status") == "open"
        ]
        open_episode_ids = [
            str(item.get("episode_id") or "")
            for item in open_episodes
        ]
        market_input_manifest = self._market_input_manifest(
            episodes=episodes,
            operation_review=operation_review,
            perspective=self.config.perspective,
            as_of=(
                checkpoint_cutoff
                if open_episode_ids
                else str(latest_event_at or checkpoint_cutoff)
            ),
            knowledge_cutoff=knowledge_cutoff,
            frozen_manifest=frozen_market_manifest,
        )
        if not open_episode_ids:
            return None, market_input_manifest
        identities: list[dict[str, Any]] = []
        episodes_by_id = {
            str(item.get("episode_id") or ""): item for item in open_episodes
        }
        for episode_id in open_episode_ids:
            identity = {
                "episode_id": episode_id,
                "review_kind": "active_checkpoint",
                "checkpoint_type": "active_checkpoint",
                "perspective": self.config.perspective,
                "as_of": checkpoint_cutoff,
                "knowledge_cutoff": knowledge_cutoff,
            }
            if reviewability_schema_version >= 2:
                from src.investment_review.models import (
                    PUBLIC_INFORMATION_POLICY_VERSION,
                )
                from src.investment_review.review_checkpoint import (
                    derive_review_checkpoint_operation_anchor,
                )

                anchor = derive_review_checkpoint_operation_anchor(
                    episodes_by_id[episode_id],
                    operation_review=operation_review,
                    checkpoint_type="active_checkpoint",
                    checkpoint_as_of=checkpoint_cutoff,
                )
                identity.update(
                    {
                        "operation_anchor_event_id": str(
                            anchor["operation_anchor_event_id"]
                        ),
                        "operation_anchor_at": str(
                            anchor["operation_anchor_at"]
                        ),
                        "operation_anchor_ordering_key": deepcopy(
                            anchor["operation_anchor_ordering_key"]
                        ),
                        "information_time_policy_version": (
                            PUBLIC_INFORMATION_POLICY_VERSION
                        ),
                    }
                )
            identity_digest = sha256_text(canonical_json(identity))
            identities.append(
                {
                    **identity,
                    "checkpoint_key": (
                        f"review_checkpoint_key_{identity_digest}"
                    ),
                    "checkpoint_id": (
                        f"review_checkpoint_{identity_digest[:32]}"
                    ),
                }
            )
        material = {
            "schema_version": (
                REVIEW_CHECKPOINT_PLAN_SCHEMA_VERSION_V2
                if reviewability_schema_version >= 2
                else REVIEW_CHECKPOINT_PLAN_SCHEMA_VERSION
            ),
            "automation_version": (
                REVIEW_CHECKPOINT_AUTOMATION_VERSION_V2
                if reviewability_schema_version >= 2
                else REVIEW_CHECKPOINT_AUTOMATION_VERSION
            ),
            "checkpoint_slot_seconds": slot_seconds,
            "checkpoint_slot": checkpoint_cutoff,
            "as_of": checkpoint_cutoff,
            "knowledge_cutoff": knowledge_cutoff,
            "identities": identities,
        }
        return (
            {
                **material,
                "content_id": (
                    "sha256:" + sha256_text(canonical_json(material))
                ),
            },
            market_input_manifest,
        )

    def _prepare_plan(
        self,
        *,
        trigger: str,
        frozen_market_manifest: Mapping[str, Any] | None = None,
    ) -> _AutomationPlan:
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
        checkpoint_plan, market_input_manifest = self._open_checkpoint_plan(
            events=events,
            latest_event_at=as_of,
            latest_known_at=knowledge_cutoff,
            frozen_market_manifest=frozen_market_manifest,
        )
        checkpoint_plan_sha256: str | None = None
        checkpoint_slot: str | None = None
        market_input_sha256: str | None = None
        automation_version = REVIEW_AUTOMATION_VERSION
        if checkpoint_plan is not None:
            automation_version = str(
                checkpoint_plan.get("automation_version")
                or REVIEW_CHECKPOINT_AUTOMATION_VERSION
            )
            checkpoint_plan_sha256 = str(
                checkpoint_plan["content_id"]
            ).removeprefix("sha256:")
            checkpoint_slot = str(checkpoint_plan["checkpoint_slot"])
            as_of = str(checkpoint_plan["as_of"])
            knowledge_cutoff = str(checkpoint_plan["knowledge_cutoff"])
        if market_input_manifest is not None:
            if self._reviewability_schema_version >= 2:
                automation_version = REVIEW_CHECKPOINT_AUTOMATION_VERSION_V2
            market_input_sha256 = str(
                market_input_manifest.get("content_id") or ""
            ).removeprefix("sha256:")
            if len(market_input_sha256) != 64:
                raise RuntimeError(
                    "automation market input manifest hash is invalid"
                )
            as_of = str(market_input_manifest.get("as_of") or as_of or "")
            knowledge_cutoff = str(
                market_input_manifest.get("knowledge_cutoff")
                or knowledge_cutoff
                or ""
            )
            if not as_of or not knowledge_cutoff:
                raise RuntimeError(
                    "automation market manifest cutoffs are invalid"
                )
        material = {
            "automation_version": automation_version,
            "source_cutoff_id": cutoff_id,
            "source_sha256": source_sha256,
            "artifact_namespace": self.artifact_namespace,
            "projection_sha256": projection_sha256,
            "checkpoint_plan_schema_version": (
                str(checkpoint_plan.get("schema_version"))
                if checkpoint_plan is not None
                else None
            ),
            "checkpoint_plan_sha256": checkpoint_plan_sha256,
            "market_input_sha256": market_input_sha256,
            "checkpoint_slot": checkpoint_slot,
            "as_of": as_of,
            "knowledge_cutoff": knowledge_cutoff,
            "scopes": list(REVIEW_AUTOMATION_SCOPES),
        }
        if self._reviewability_schema_version >= 2:
            material["perspective"] = self.config.perspective
        digest = sha256_text(canonical_json(material))
        return _AutomationPlan(
            run_id=f"reviewrun_{digest[:32]}",
            run_key=f"catch_up:{digest}",
            source_cutoff_id=cutoff_id,
            source_sha256=source_sha256,
            artifact_namespace=self.artifact_namespace,
            projection_sha256=projection_sha256,
            checkpoint_plan=checkpoint_plan,
            checkpoint_plan_sha256=checkpoint_plan_sha256,
            market_input_manifest=market_input_manifest,
            market_input_sha256=market_input_sha256,
            checkpoint_slot=checkpoint_slot,
            as_of=as_of,
            knowledge_cutoff=knowledge_cutoff,
            source_cutoff=knowledge_cutoff or cutoff.get("max_known_at"),
            sync_action=sync_action,
            source_seen=source_seen,
            sidecar_seen=sidecar_seen,
            unsynced=final_unsynced,
            perspective=self.config.perspective,
        )

    @staticmethod
    def _verify_scope_market_consumption(
        *,
        manifest: Mapping[str, Any],
        consumed: list[dict[str, Any]],
        receipt: Mapping[str, Any],
    ) -> dict[str, list[str]]:
        """Prove a scope consumed exactly its planned frozen projections."""

        from src.investment_review.artifact_io import canonical_json_bytes

        planned = {
            str(item.get("episode_id") or ""): item
            for item in manifest.get("items", [])
            if isinstance(item, Mapping) and item.get("episode_id")
        }
        receipt_episodes = {
            str(item.get("episode_id") or ""): item
            for item in receipt.get("episodes", [])
            if isinstance(item, Mapping) and item.get("episode_id")
        }
        consumed_by_episode: dict[str, dict[str, Any]] = {}
        for item in consumed:
            episode_id = str(item.get("episode_id") or "")
            if not episode_id or episode_id in consumed_by_episode:
                raise RuntimeError(
                    "scope consumed a frozen market projection more than once"
                )
            consumed_by_episode[episode_id] = item
        if set(consumed_by_episode) != set(receipt_episodes):
            raise RuntimeError(
                "scope market consumption does not match receipt episodes: "
                f"consumed={sorted(consumed_by_episode)}, "
                f"receipt={sorted(receipt_episodes)}, "
                f"status={receipt.get('status')}, gaps={receipt.get('gaps')}"
            )

        receipt_ids: set[str] = set()
        source_ids: set[str] = set()
        resolution_ids: set[str] = set()
        content_ids: set[str] = set()
        for episode_id, consumed_item in consumed_by_episode.items():
            planned_item = planned.get(episode_id)
            if planned_item is None:
                raise RuntimeError(
                    "scope consumed an episode outside the market plan"
                )
            for field in (
                "instrument_id",
                "perspective",
                "as_of",
                "knowledge_cutoff",
                "market_input_content_id",
                "market_requirement_id",
                "market_resolution_id",
                "fetch_receipt_ids",
                "source_ids",
                "operation_anchor_event_id",
                "operation_anchor_at",
                "operation_anchor_ordering_key",
                "information_time_policy_version",
            ):
                if (
                    field in consumed_item
                    or field in planned_item
                ) and consumed_item.get(field) != planned_item.get(field):
                    raise RuntimeError(
                        "scope market identifiers drifted from the plan"
                    )
            expected_projection = planned_item.get("projection")
            if isinstance(expected_projection, Mapping):
                received_projection = receipt_episodes[episode_id].get(
                    "market_context"
                )
                if planned_item.get("projection_kind") == "full":
                    if (
                        not isinstance(received_projection, Mapping)
                        or canonical_json_bytes(received_projection)
                        != canonical_json_bytes(expected_projection)
                    ):
                        raise RuntimeError(
                            "scope receipt market projection drifted from plan"
                        )
            receipt_ids.update(
                str(value)
                for value in planned_item.get("fetch_receipt_ids", [])
            )
            source_ids.update(
                str(value) for value in planned_item.get("source_ids", [])
            )
            if planned_item.get("market_resolution_id"):
                resolution_ids.add(
                    str(planned_item["market_resolution_id"])
                )
            if planned_item.get("market_input_content_id"):
                content_ids.add(
                    str(planned_item["market_input_content_id"])
                )
        return {
            "market_input_content_ids": sorted(content_ids),
            "market_resolution_ids": sorted(resolution_ids),
            "market_fetch_receipt_ids": sorted(receipt_ids),
            "market_source_ids": sorted(source_ids),
        }

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
                        "automation_version": (
                            str(
                                plan.checkpoint_plan.get(
                                    "automation_version"
                                )
                            )
                            if plan.checkpoint_plan is not None
                            else REVIEW_CHECKPOINT_AUTOMATION_VERSION_V2
                            if plan.market_input_manifest is not None
                            and plan.market_input_manifest.get(
                                "schema_version"
                            )
                            == REVIEW_AUTOMATION_MARKET_INPUT_MANIFEST_VERSION_V2
                            else REVIEW_AUTOMATION_VERSION
                        ),
                        "source_cutoff_id": plan.source_cutoff_id,
                        "source_sha256": plan.source_sha256,
                        "artifact_namespace": plan.artifact_namespace,
                        "projection_sha256": plan.projection_sha256,
                        "checkpoint_plan": plan.checkpoint_plan,
                        "checkpoint_plan_sha256": (
                            plan.checkpoint_plan_sha256
                        ),
                        "market_input_manifest": (
                            plan.market_input_manifest
                        ),
                        "market_input_sha256": plan.market_input_sha256,
                        "checkpoint_slot": plan.checkpoint_slot,
                        "as_of": plan.as_of,
                        "knowledge_cutoff": plan.knowledge_cutoff,
                        "scopes": list(REVIEW_AUTOMATION_SCOPES),
                        **(
                            {"perspective": plan.perspective}
                            if self._reviewability_schema_version >= 2
                            else {}
                        ),
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
                frozen_market_resolver: (
                    _FrozenAutomationMarketResolver | None
                ) = None
                if plan.market_input_manifest is not None:
                    frozen_market_resolver = _FrozenAutomationMarketResolver(
                        plan.market_input_manifest
                    )
                    if not hasattr(runner, "checkpoint_market_resolver"):
                        raise RuntimeError(
                            "market-planned automation runner cannot accept "
                            "the frozen resolver"
                        )
                    runner.checkpoint_market_resolver = (
                        frozen_market_resolver
                    )
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
                                "checkpoint_ids": [],
                                "checkpoint_count": 0,
                            }
                        )
                        continue
                    try:
                        market_cursor = (
                            frozen_market_resolver.cursor()
                            if frozen_market_resolver is not None
                            else 0
                        )
                        receipt = runner.run(
                            scope=scope,
                            as_of=plan.as_of,
                            knowledge_cutoff=plan.knowledge_cutoff,
                            perspective=plan.perspective,
                            dry_run=False,
                            trigger=f"automation_{trigger}",
                        )
                        market_identifiers: dict[str, list[str]] = {}
                        if (
                            frozen_market_resolver is not None
                            and plan.market_input_manifest is not None
                        ):
                            market_identifiers = (
                                self._verify_scope_market_consumption(
                                    manifest=plan.market_input_manifest,
                                    consumed=(
                                        frozen_market_resolver.consumed_since(
                                            market_cursor
                                        )
                                    ),
                                    receipt=receipt,
                                )
                            )
                        scope_runs.append(
                            {
                                "scope": scope,
                                "run_id": receipt.get("run_id"),
                                "run_key": receipt.get("run_key"),
                                "status": receipt.get("status"),
                                "content_id": receipt.get("content_id"),
                                "checkpoint_ids": sorted(
                                    str(
                                        (
                                            item.get(
                                                "review_checkpoint"
                                            )
                                            or {}
                                        ).get("checkpoint_id")
                                        or ""
                                    )
                                    for item in receipt.get(
                                        "episodes", []
                                    )
                                    if isinstance(item, Mapping)
                                    and isinstance(
                                        item.get("review_checkpoint"),
                                        Mapping,
                                    )
                                ),
                                "checkpoint_count": sum(
                                    1
                                    for item in receipt.get(
                                        "episodes", []
                                    )
                                    if isinstance(item, Mapping)
                                    and isinstance(
                                        item.get("review_checkpoint"),
                                        Mapping,
                                    )
                                ),
                                **market_identifiers,
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
                                "checkpoint_ids": [],
                                "checkpoint_count": 0,
                            }
                        )

                verified_run_key: str | None = None
                try:
                    verified_plan = self._prepare_plan(
                        trigger=f"{trigger}_post_cycle_verify",
                        frozen_market_manifest=plan.market_input_manifest,
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
                    "checkpoint_plan_sha256": (
                        plan.checkpoint_plan_sha256
                    ),
                    "market_input_sha256": plan.market_input_sha256,
                    "checkpoint_slot": plan.checkpoint_slot,
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
                    "checkpoint_plan_sha256": (
                        plan.checkpoint_plan_sha256
                    ),
                    "market_input_sha256": plan.market_input_sha256,
                    "checkpoint_slot": plan.checkpoint_slot,
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
