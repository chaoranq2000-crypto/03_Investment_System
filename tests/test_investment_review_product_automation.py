from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.investment_review.models import DecisionRecord
from src.portfolio.cli import build_parser, command_import_statement
from src.portfolio.investment_review_service import InvestmentReviewWebService
from src.portfolio.review_integration import (
    REVIEW_AUTOMATION_ENV,
    REVIEW_AUTOMATION_INTERVAL_ENV,
    ReviewAutomationConfig,
    ReviewAutomationCoordinator,
    review_automation_config,
    trigger_post_commit_review_sync,
)
import src.portfolio.review_integration as integration_module
import src.portfolio.web as web_module
from tests.test_investment_review_review_runner import (
    RunnerFixture,
    _fixture as build_runner_fixture,
    _reviewability_fixture as build_reviewability_runner_fixture,
    _trade_row,
)
from tests.test_investment_review_sync_service import _insert_ledger_row
from tests.test_portfolio_tracker import _portfolio_store_with_opening


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_hashes(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _coordinator(
    fixture: RunnerFixture,
    *,
    config: ReviewAutomationConfig | None = None,
    runner_factory=None,
    artifact_root: Path | None = None,
    clock=None,
    checkpoint_market_resolver=None,
) -> ReviewAutomationCoordinator:
    return ReviewAutomationCoordinator(
        portfolio_db=fixture.source,
        review_db=fixture.review_db,
        mapping_path=fixture.mapping,
        artifact_root=artifact_root or fixture.artifacts,
        repo_root=fixture.root,
        config=config,
        runner_factory=runner_factory,
        clock=clock,
        checkpoint_market_resolver=checkpoint_market_resolver,
    )


def test_automation_configuration_is_strict_and_disableable(
    tmp_path: Path,
) -> None:
    assert review_automation_config(environ={}).enabled is True
    disabled = review_automation_config(
        environ={
            REVIEW_AUTOMATION_ENV: "0",
            REVIEW_AUTOMATION_INTERVAL_ENV: "60",
        }
    )
    assert disabled == ReviewAutomationConfig(
        enabled=False,
        interval_seconds=900.0,
        startup_catch_up=True,
    )
    assert review_automation_config(
        environ={
            REVIEW_AUTOMATION_ENV: "0",
            REVIEW_AUTOMATION_INTERVAL_ENV: "invalid-but-unused",
        }
    ).enabled is False
    assert review_automation_config(
        environ={REVIEW_AUTOMATION_INTERVAL_ENV: "invalid-but-unused"},
        enabled_override=False,
    ).enabled is False
    with pytest.raises(ValueError, match="boolean"):
        review_automation_config(
            environ={REVIEW_AUTOMATION_ENV: "sometimes"}
        )
    with pytest.raises(ValueError, match="between 30 and 86400"):
        review_automation_config(
            environ={REVIEW_AUTOMATION_INTERVAL_ENV: "1"}
        )

    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(FileNotFoundError, match="will not create"):
        ReviewAutomationCoordinator(
            portfolio_db=tmp_path / "portfolio.sqlite3",
            review_db=missing,
            repo_root=tmp_path,
        )
    assert not missing.exists()


def test_catch_up_runs_three_scopes_and_replays_without_drift(
    tmp_path: Path,
) -> None:
    fixture = build_runner_fixture(tmp_path)
    coordinator = _coordinator(fixture)
    source_before = _sha256(fixture.source)

    first = coordinator.run_once(trigger="startup_catch_up")
    assert first["status"] == "partial"
    assert [item["scope"] for item in first["scope_runs"]] == [
        "single",
        "weekly",
        "monthly",
    ]
    assert {item["status"] for item in first["scope_runs"]} == {"partial"}
    sidecar_after_first = _sha256(fixture.review_db)
    artifacts_after_first = _tree_hashes(fixture.artifacts)

    replay = coordinator.run_once(trigger="periodic_catch_up")
    assert replay["status"] == "deduplicated"
    assert replay["run_key"] == first["run_key"]
    assert replay["scope_runs"] == first["scope_runs"]
    assert _sha256(fixture.review_db) == sidecar_after_first
    assert _tree_hashes(fixture.artifacts) == artifacts_after_first
    assert _sha256(fixture.source) == source_before

    catch_up = fixture.store.list_review_runs(scope="catch_up")
    assert len(catch_up) == 1
    assert catch_up[0]["status"] == "partial"
    assert [item["status"] for item in catch_up[0]["history"]] == [
        "queued",
        "running",
        "partial",
    ]


def test_disabled_coordinator_is_inert(
    tmp_path: Path,
) -> None:
    fixture = build_runner_fixture(tmp_path)
    coordinator = _coordinator(
        fixture,
        config=ReviewAutomationConfig(
            enabled=False,
            interval_seconds=60,
            startup_catch_up=True,
        ),
    )
    sidecar_before = _sha256(fixture.review_db)
    started = coordinator.start()
    assert started["enabled"] is False
    assert started["state"] == "disabled"
    assert started["worker_alive"] is False
    assert coordinator.request(trigger="startup")["status"] == "disabled"
    assert coordinator.run_once(trigger="startup")["status"] == "disabled"
    assert fixture.store.list_review_runs(scope="catch_up") == []
    assert _sha256(fixture.review_db) == sidecar_before


def test_catch_up_key_binds_artifact_namespace(
    tmp_path: Path,
) -> None:
    fixture = build_runner_fixture(tmp_path)
    calls: list[tuple[str, str]] = []

    class FakeRunner:
        def __init__(self, namespace: str) -> None:
            self.namespace = namespace

        def run(self, *, scope: str, **_kwargs: Any) -> dict[str, Any]:
            calls.append((self.namespace, scope))
            return {
                "run_id": f"reviewrun_{scope:0<32}"[:42],
                "run_key": f"review:{self.namespace}:{scope}",
                "status": "ready",
                "content_id": "sha256:" + ("5" * 64),
            }

    first = _coordinator(
        fixture,
        artifact_root=fixture.root / "artifacts-a",
        runner_factory=lambda: FakeRunner("a"),
    ).run_once(trigger="namespace_a")
    second = _coordinator(
        fixture,
        artifact_root=fixture.root / "artifacts-b",
        runner_factory=lambda: FakeRunner("b"),
    ).run_once(trigger="namespace_b")

    assert first["status"] == "succeeded"
    assert second["status"] == "succeeded"
    assert first["run_key"] != second["run_key"]
    assert calls == [
        ("a", "single"),
        ("a", "weekly"),
        ("a", "monthly"),
        ("b", "single"),
        ("b", "weekly"),
        ("b", "monthly"),
    ]


def test_reviewability_open_episode_uses_same_slot_idempotency_and_new_slot_key(
    tmp_path: Path,
) -> None:
    fixture = build_reviewability_runner_fixture(tmp_path)
    current = [datetime(2026, 7, 26, 8, 1, tzinfo=timezone.utc)]
    coordinator = _coordinator(
        fixture,
        config=ReviewAutomationConfig(
            enabled=True,
            interval_seconds=900,
            startup_catch_up=True,
        ),
        clock=lambda: current[0],
    )

    first = coordinator._prepare_plan(trigger="first")
    repeated = coordinator._prepare_plan(trigger="same_slot")

    assert repeated.run_key == first.run_key
    assert first.checkpoint_slot == "2026-07-26T08:00:00Z"
    assert first.as_of == first.checkpoint_slot
    assert first.knowledge_cutoff == first.checkpoint_slot
    assert first.checkpoint_plan_sha256 is not None
    assert first.checkpoint_plan == {
        "schema_version": (
            integration_module.REVIEW_CHECKPOINT_PLAN_SCHEMA_VERSION
        ),
        "automation_version": (
            integration_module.REVIEW_CHECKPOINT_AUTOMATION_VERSION
        ),
        "checkpoint_slot_seconds": 900,
        "checkpoint_slot": "2026-07-26T08:00:00Z",
        "as_of": "2026-07-26T08:00:00Z",
        "knowledge_cutoff": "2026-07-26T08:00:00Z",
        "identities": [
            {
                "episode_id": first.checkpoint_plan["identities"][0][
                    "episode_id"
                ],
                "review_kind": "active_checkpoint",
                "checkpoint_type": "active_checkpoint",
                "perspective": "user",
                "as_of": "2026-07-26T08:00:00Z",
                "knowledge_cutoff": "2026-07-26T08:00:00Z",
                "checkpoint_key": first.checkpoint_plan["identities"][0][
                    "checkpoint_key"
                ],
                "checkpoint_id": first.checkpoint_plan["identities"][0][
                    "checkpoint_id"
                ],
            }
        ],
        "content_id": first.checkpoint_plan["content_id"],
    }

    current[0] = datetime(2026, 7, 26, 8, 16, tzinfo=timezone.utc)
    later = coordinator._prepare_plan(trigger="next_slot")

    assert later.run_key != first.run_key
    assert later.checkpoint_slot == "2026-07-26T08:15:00Z"
    assert later.checkpoint_plan_sha256 != first.checkpoint_plan_sha256
    assert later.checkpoint_plan["identities"][0]["episode_id"] == (
        first.checkpoint_plan["identities"][0]["episode_id"]
    )


def test_serve_dashboard_explicit_automation_owns_start_and_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    class FakeService:
        def __init__(self) -> None:
            self.store = SimpleNamespace(path=tmp_path / "review.sqlite3")
            self.sync_service = SimpleNamespace(
                mapping_path=tmp_path / "mapping.json"
            )
            self.catalog = SimpleNamespace(
                runner=SimpleNamespace(
                    artifact_root=tmp_path / "artifacts"
                )
            )
            self.provider = None

        def set_automation_status_provider(self, provider) -> None:
            self.provider = provider

    class FakeCoordinator:
        def __init__(self, **kwargs: Any) -> None:
            calls.append(("init", kwargs["config"].enabled))

        def status(self) -> dict[str, Any]:
            return {
                "enabled": True,
                "state": "idle",
                "worker_alive": False,
            }

        def start(self) -> dict[str, Any]:
            calls.append("start")
            return self.status()

        def stop(self, *, timeout: float) -> dict[str, Any]:
            calls.append(("stop", timeout))
            return self.status()

    class FakeServer:
        def __init__(self, service: FakeService) -> None:
            self.dashboard_app = SimpleNamespace(
                investment_review_service=service
            )
            self.server_address = ("127.0.0.1", 54321)

        def serve_forever(self, *, poll_interval: float) -> None:
            assert poll_interval == 0.2
            raise KeyboardInterrupt

        def server_close(self) -> None:
            calls.append("server_close")

    service = FakeService()
    monkeypatch.setattr(
        web_module,
        "create_dashboard_server",
        lambda *_args, **_kwargs: FakeServer(service),
    )
    monkeypatch.setattr(
        web_module,
        "ReviewAutomationCoordinator",
        FakeCoordinator,
    )
    monkeypatch.setattr(web_module, "load_env_file", lambda _path: {})
    monkeypatch.setattr(
        web_module,
        "repository_root",
        lambda: tmp_path,
    )
    store = SimpleNamespace(path=tmp_path / "portfolio.sqlite3")

    web_module.serve_dashboard(
        store,
        open_browser=False,
        investment_review_service=service,
        review_automation=True,
    )
    assert calls == [
        ("init", True),
        "start",
        ("stop", 30.0),
        "server_close",
    ]
    assert service.provider is not None

    calls.clear()
    web_module.serve_dashboard(
        store,
        open_browser=False,
        investment_review_service=service,
    )
    assert calls == ["server_close"]


def test_concurrent_requests_consume_one_deterministic_cycle(
    tmp_path: Path,
) -> None:
    fixture = build_runner_fixture(tmp_path)
    calls: list[str] = []
    calls_lock = threading.Lock()

    class FakeRunner:
        def run(self, *, scope: str, **_kwargs: Any) -> dict[str, Any]:
            with calls_lock:
                calls.append(scope)
            return {
                "run_id": f"reviewrun_{scope:0<32}"[:42],
                "run_key": f"review:{scope}",
                "status": "ready",
                "content_id": "sha256:" + ("1" * 64),
            }

    coordinator_a = _coordinator(
        fixture,
        runner_factory=lambda: FakeRunner(),
    )
    coordinator_b = _coordinator(
        fixture,
        runner_factory=lambda: FakeRunner(),
    )
    coordinators = (coordinator_a, coordinator_b)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda index: coordinators[index % 2].run_once(
                    trigger=f"concurrent_{index}"
                ),
                range(8),
            )
        )

    assert calls == ["single", "weekly", "monthly"]
    assert sum(item["status"] == "succeeded" for item in results) == 1
    assert sum(item["status"] == "deduplicated" for item in results) == 7
    assert len({item["run_key"] for item in results}) == 1
    assert len(fixture.store.list_review_runs(scope="catch_up")) == 1


def test_enqueue_does_not_wait_behind_active_consumer(
    tmp_path: Path,
) -> None:
    fixture = build_runner_fixture(tmp_path)
    entered = threading.Event()
    release = threading.Event()

    class BlockingRunner:
        def run(self, *, scope: str, **_kwargs: Any) -> dict[str, Any]:
            if scope == "single":
                entered.set()
                assert release.wait(timeout=10)
            return {
                "run_id": f"reviewrun_{scope:0<32}"[:42],
                "run_key": f"review:{scope}",
                "status": "ready",
                "content_id": "sha256:" + ("4" * 64),
            }

    consumer = _coordinator(
        fixture,
        runner_factory=lambda: BlockingRunner(),
    )
    producer = _coordinator(
        fixture,
        runner_factory=lambda: BlockingRunner(),
    )
    result_holder: list[dict[str, Any]] = []
    thread = threading.Thread(
        target=lambda: result_holder.append(
            consumer.run_once(trigger="active_consumer")
        )
    )
    thread.start()
    assert entered.wait(timeout=10)
    started = time.monotonic()
    queued = producer.enqueue(trigger="portfolio_statement_post_commit")
    elapsed = time.monotonic() - started
    assert queued["status"] == "deferred"
    assert queued["trigger"] == "portfolio_statement_post_commit"
    assert queued["reason"] == "automation_consumer_active"
    assert queued["retryable"] is True
    assert queued["current_status"] == "running"
    assert elapsed < 1.0
    release.set()
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert result_holder[0]["status"] == "succeeded"


def test_failed_scope_is_visible_and_same_task_recovers(
    tmp_path: Path,
) -> None:
    fixture = build_runner_fixture(tmp_path)
    real_runner = fixture.runner
    fail_weekly_once = True

    class FlakyRunner:
        def run(self, *, scope: str, **kwargs: Any) -> dict[str, Any]:
            nonlocal fail_weekly_once
            if scope == "weekly" and fail_weekly_once:
                fail_weekly_once = False
                raise RuntimeError("synthetic weekly failure")
            return real_runner.run(scope=scope, **kwargs)

    coordinator = _coordinator(
        fixture,
        runner_factory=lambda: FlakyRunner(),
    )
    source_before = _sha256(fixture.source)
    first = coordinator.run_once(trigger="startup_catch_up")
    assert first["status"] == "failed"
    assert first["retryable"] is True
    first_artifacts = _tree_hashes(fixture.artifacts)

    recovering_coordinator = _coordinator(
        fixture,
        runner_factory=lambda: FlakyRunner(),
    )
    recovered = recovering_coordinator.run_once(trigger="startup_retry")
    assert recovered["status"] == "partial"
    assert recovered["run_key"] == first["run_key"]
    assert recovered["retryable"] is False
    assert all(item["status"] == "partial" for item in recovered["scope_runs"])
    for path, digest in first_artifacts.items():
        assert _tree_hashes(fixture.artifacts)[path] == digest

    run = fixture.store.get_review_run(first["run_key"])
    statuses = [item["status"] for item in run["history"]]
    assert statuses == [
        "queued",
        "running",
        "failed",
        "queued",
        "running",
        "partial",
    ]
    health = coordinator.status()
    recovering_health = recovering_coordinator.status()
    assert health["state"] == "partial"
    assert recovering_health["state"] == "partial"
    assert health["last_failure"]["status"] == "failed"
    assert health["last_success"] is None
    assert health["last_completed"]["status"] == "partial"
    assert _sha256(fixture.source) == source_before

    class BrokenSync:
        def status(self) -> dict[str, Any]:
            raise RuntimeError("synthetic status failure after recovery")

    original_sync_service = coordinator.sync_service
    coordinator.sync_service = BrokenSync()
    latest_failure = coordinator.run_once(trigger="pre_plan_failure")
    assert latest_failure["status"] == "failed"
    latest_health = coordinator.status()
    assert latest_health["state"] == "failed"
    assert latest_health["last_failure"]["error_type"] == "RuntimeError"

    coordinator.sync_service = original_sync_service
    deduplicated_recovery = coordinator.run_once(
        trigger="pre_plan_failure_retry"
    )
    assert deduplicated_recovery["status"] == "deduplicated"
    final_health = coordinator.status()
    assert final_health["state"] == "partial"
    assert final_health["latest"]["status"] == "partial"
    assert final_health["last_failure"]["error_type"] == "RuntimeError"

    coordinator.sync_service = BrokenSync()
    assert coordinator.enqueue(trigger="enqueue_failure")["status"] == "failed"
    assert coordinator.status()["state"] == "failed"
    coordinator.sync_service = original_sync_service
    enqueue_recovery = coordinator.enqueue(trigger="enqueue_failure_retry")
    assert enqueue_recovery["status"] == "deduplicated"
    assert coordinator.status()["state"] == "partial"


@pytest.mark.parametrize("persisted_status", ["queued", "running"])
def test_existing_pending_enqueue_recovers_local_failure(
    tmp_path: Path,
    persisted_status: str,
) -> None:
    fixture = build_runner_fixture(tmp_path)
    coordinator = _coordinator(fixture)
    original_sync_service = coordinator.sync_service

    queued = coordinator.enqueue(trigger="initial")
    assert queued["current_status"] == "queued"
    if persisted_status == "running":
        coordinator._append_status(
            run_id=queued["run_id"],
            status="running",
            details={"attempt": 1, "retryable": True},
        )

    class BrokenSync:
        def status(self) -> dict[str, Any]:
            raise RuntimeError("synthetic pending pre-plan failure")

    coordinator.sync_service = BrokenSync()
    assert coordinator.enqueue(trigger="failure")["status"] == "failed"
    assert coordinator.status()["state"] == "failed"

    coordinator.sync_service = original_sync_service
    recovered = coordinator.enqueue(trigger="recovery")
    assert recovered["status"] == "queued"
    assert recovered["current_status"] == persisted_status
    assert coordinator.status()["state"] == persisted_status


def test_startup_recovers_a_persisted_running_task_and_stops_worker(
    tmp_path: Path,
) -> None:
    fixture = build_runner_fixture(tmp_path)
    calls: list[str] = []
    finished = threading.Event()

    class FakeRunner:
        def run(self, *, scope: str, **_kwargs: Any) -> dict[str, Any]:
            calls.append(scope)
            if len(calls) == 3:
                finished.set()
            return {
                "run_id": f"reviewrun_{scope:0<32}"[:42],
                "run_key": f"review:{scope}",
                "status": "ready",
                "content_id": "sha256:" + ("2" * 64),
            }

    crashed = _coordinator(
        fixture,
        runner_factory=lambda: FakeRunner(),
    )
    queued = crashed.enqueue(trigger="pre_crash")
    assert queued["status"] == "queued"
    crashed._append_status(  # Simulate a process dying after dequeue.
        run_id=queued["run_id"],
        status="running",
        details={"attempt": 1, "retryable": True},
    )

    recovered = _coordinator(
        fixture,
        config=ReviewAutomationConfig(
            enabled=True,
            interval_seconds=3600,
            startup_catch_up=True,
        ),
        runner_factory=lambda: FakeRunner(),
    )
    started = recovered.start()
    assert started["enabled"] is True
    assert finished.wait(timeout=10)
    stopped = recovered.stop(timeout=5)
    assert stopped["worker_alive"] is False
    assert calls == ["single", "weekly", "monthly"]
    run = fixture.store.get_review_run(queued["run_key"])
    assert run["status"] == "succeeded"
    assert [item["status"] for item in run["history"]] == [
        "queued",
        "running",
        "running",
        "succeeded",
    ]


def test_worker_performs_periodic_check_and_stops_cleanly(
    tmp_path: Path,
) -> None:
    fixture = build_runner_fixture(tmp_path)
    coordinator = _coordinator(
        fixture,
        config=ReviewAutomationConfig(
            enabled=True,
            interval_seconds=0.05,
            startup_catch_up=True,
        ),
    )
    triggers: list[str] = []
    periodic_seen = threading.Event()

    def record_cycle(*, trigger: str) -> dict[str, Any]:
        triggers.append(trigger)
        if trigger == "periodic_catch_up":
            periodic_seen.set()
        return {"status": "deduplicated"}

    coordinator.run_once = record_cycle  # type: ignore[method-assign]
    coordinator.start()
    assert periodic_seen.wait(timeout=5)
    stopped = coordinator.stop(timeout=5)
    assert stopped["worker_alive"] is False
    assert triggers[0] == "startup_catch_up"
    assert "periodic_catch_up" in triggers


def test_worker_bounds_immediate_retry_for_continuously_moving_source(
    tmp_path: Path,
) -> None:
    fixture = build_runner_fixture(tmp_path)
    calls: list[str] = []
    second_cycle_finished = threading.Event()

    class ContinuouslyMovingRunner:
        def run(self, *, scope: str, **_kwargs: Any) -> dict[str, Any]:
            calls.append(scope)
            if scope == "single":
                with sqlite3.connect(fixture.source) as connection:
                    current = int(
                        connection.execute("PRAGMA user_version").fetchone()[0]
                    )
                    connection.execute(
                        f"PRAGMA user_version = {current + 1}"
                    )
            if len(calls) == 6:
                second_cycle_finished.set()
            return {
                "run_id": f"reviewrun_{scope:0<32}"[:42],
                "run_key": f"review:{scope}:{len(calls)}",
                "status": "ready",
                "content_id": "sha256:" + ("6" * 64),
            }

    coordinator = _coordinator(
        fixture,
        config=ReviewAutomationConfig(
            enabled=True,
            interval_seconds=3600,
            startup_catch_up=True,
        ),
        runner_factory=lambda: ContinuouslyMovingRunner(),
    )
    coordinator.start()
    assert second_cycle_finished.wait(timeout=10)
    threading.Event().wait(0.25)
    assert calls == [
        "single",
        "weekly",
        "monthly",
        "single",
        "weekly",
        "monthly",
    ]
    deadline = time.monotonic() + 5
    status = coordinator.status()
    while status["state"] != "blocked" and time.monotonic() < deadline:
        threading.Event().wait(0.05)
        status = coordinator.status()
    assert status["state"] == "blocked"
    assert status["latest"]["status"] == "blocked"
    run = fixture.store.get_review_run(status["latest"]["run_id"])
    assert run["status_event"]["details"]["gap_codes"] == [
        "SOURCE_CONTINUED_CHANGING_DURING_AUTOMATION"
    ]
    stopped = coordinator.stop(timeout=5)
    assert stopped["worker_alive"] is False


def test_startup_blocks_superseded_crash_leftover_before_new_cycle(
    tmp_path: Path,
) -> None:
    fixture = build_runner_fixture(tmp_path)

    class FakeRunner:
        def run(self, *, scope: str, **_kwargs: Any) -> dict[str, Any]:
            return {
                "run_id": f"reviewrun_{scope:0<32}"[:42],
                "run_key": f"review:{scope}",
                "status": "ready",
                "content_id": "sha256:" + ("3" * 64),
            }

    crashed = _coordinator(
        fixture,
        runner_factory=lambda: FakeRunner(),
    )
    queued = crashed.enqueue(trigger="pre_crash")
    crashed._append_status(
        run_id=queued["run_id"],
        status="running",
        details={"attempt": 1, "retryable": True},
    )

    event = next(
        item
        for item in fixture.store.list_events()
        if item["source_record_id"].endswith("buy-one")
    )
    decision = DecisionRecord.build(
        symbol=event["symbol"],
        occurred_at=event["occurred_at"],
        known_at=event["known_at"],
        thesis="Explicit synthetic input drift for crash recovery.",
        timezone="UTC",
    )
    decision_id = fixture.store.add_decision(decision)
    fixture.store.link_decision_event(decision_id, event["event_id"])

    recovered = _coordinator(
        fixture,
        runner_factory=lambda: FakeRunner(),
    )
    result = recovered.run_once(trigger="startup_after_input_change")
    assert result["status"] == "succeeded"
    assert result["run_key"] != queued["run_key"]
    old = fixture.store.get_review_run(queued["run_key"])
    assert old["status"] == "blocked"
    assert old["status_event"]["details"]["gap_codes"] == [
        "CATCH_UP_INPUT_SUPERSEDED"
    ]
    health = recovered.status()
    assert health["state"] == "succeeded"
    assert health["queue_depth"] == 0
    assert health["latest"]["run_key"] == result["run_key"]


def test_source_change_during_scopes_fails_mixed_cutoff_cycle_and_retries(
    tmp_path: Path,
) -> None:
    fixture = build_runner_fixture(tmp_path)
    real_runner = fixture.runner
    changed = False

    class MovingSourceRunner:
        def run(self, *, scope: str, **kwargs: Any) -> dict[str, Any]:
            nonlocal changed
            receipt = real_runner.run(scope=scope, **kwargs)
            if scope == "single" and not changed:
                changed = True
                _insert_ledger_row(
                    fixture.source,
                    _trade_row(
                        event_date="2026-01-07",
                        event_type="BUY",
                        external_id="automation-source-drift",
                    ),
                )
            return receipt

    coordinator = _coordinator(
        fixture,
        runner_factory=lambda: MovingSourceRunner(),
    )
    first = coordinator.run_once(trigger="source_drift")
    assert first["status"] == "failed"
    assert first["retryable"] is True
    assert any(
        item["error_type"] == "AutomationInputDrift"
        for item in first["failures"]
    )

    recovered = coordinator.run_once(trigger="source_drift_retry")
    assert recovered["status"] == "partial"
    assert recovered["run_key"] != first["run_key"]
    old = fixture.store.get_review_run(first["run_key"])
    assert old["status"] == "blocked"
    assert old["status_event"]["details"]["gap_codes"] == [
        "CATCH_UP_INPUT_SUPERSEDED"
    ]
    assert recovered["counts"]["unsynced"] == 0


def test_health_projects_catch_up_without_paths_and_post_commit_failure_isolated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = build_runner_fixture(tmp_path)
    coordinator = _coordinator(fixture)
    result = coordinator.run_once(trigger="health_test")
    assert result["status"] == "partial"

    service = InvestmentReviewWebService(
        review_db=fixture.review_db,
        portfolio_db=fixture.source,
        mapping_path=fixture.mapping,
        artifact_root=fixture.artifacts,
        repo_root=fixture.root,
        automation_status_provider=coordinator.status,
    )
    health = service.get_health()
    automation = health["data"]["automation"]
    assert automation["enabled"] is True
    assert automation["state"] == "partial"
    assert automation["latest"]["source_cutoff_id"]
    serialized = json.dumps(automation, ensure_ascii=False)
    assert str(fixture.root) not in serialized
    assert "portfolio.sqlite3" not in serialized

    class FailedSync:
        def status(self) -> dict[str, Any]:
            return {
                "status": "failed",
                "counts": {
                    "source_seen": 2,
                    "sidecar_seen": 2,
                    "unsynced": 0,
                },
                "lag": {
                    "unsynced": 0,
                    "source_cutoff_id": "sync_cutoff_test",
                },
                "fees": {
                    "actual": 2,
                    "estimated": 0,
                    "unknown": 0,
                },
                "last_success": None,
                "last_failure": None,
            }

    service.sync_service = FailedSync()
    service.set_automation_status_provider(
        lambda: {
            "enabled": True,
            "state": "partial",
            "queue_depth": 0,
            "run_count": 1,
        }
    )
    assert service.get_health()["status"] == "failed"

    from src.investment_review import sync_service as sync_module

    monkeypatch.setattr(
        sync_module,
        "sync_after_portfolio_commit",
        lambda *_args, **_kwargs: {
            "status": "succeeded",
            "counts": {"inserted": 0, "skipped": 1},
        },
    )

    def fail_automation(**_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("synthetic post-commit automation failure")

    monkeypatch.setattr(
        integration_module,
        "POST_COMMIT_AUTOMATION_HOOK",
        fail_automation,
    )
    monkeypatch.delenv(REVIEW_AUTOMATION_ENV, raising=False)
    post_commit = trigger_post_commit_review_sync(
        fixture.source,
        review_db=fixture.review_db,
    )
    assert post_commit["status"] == "succeeded"
    assert post_commit["automation"]["status"] == "failed"
    assert post_commit["automation"]["retryable"] is True


def test_post_commit_automation_failure_cannot_rollback_portfolio_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store = _portfolio_store_with_opening(tmp_path)
    review_db = tmp_path / "candidate-review.sqlite3"
    review_db.touch()
    statement = tmp_path / "automation-failure.csv"
    statement.write_text(
        "成交日期,证券代码,证券名称,买卖标志,成交价格,成交数量,成交金额,手续费,资金流水号\n"
        "2026-07-13,600000,浦发银行,买入,13,10,130,1,automation-failure\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        integration_module.REVIEW_DATABASE_ENV,
        str(review_db.resolve()),
    )

    from src.investment_review import sync_service as sync_module

    monkeypatch.setattr(
        sync_module,
        "sync_after_portfolio_commit",
        lambda *_args, **_kwargs: {
            "status": "succeeded",
            "counts": {"inserted": 1, "skipped": 0},
        },
    )

    def fail_automation(**_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("synthetic automation failure after commit")

    monkeypatch.setattr(
        integration_module,
        "POST_COMMIT_AUTOMATION_HOOK",
        fail_automation,
    )
    args = build_parser().parse_args(
        [
            "import-statement",
            "--input",
            str(statement),
            "--apply",
        ]
    )
    assert command_import_statement(args, store) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["inserted_entries"] == 1
    assert payload["review_sync"]["status"] == "succeeded"
    assert payload["review_sync"]["automation"]["status"] == "failed"
    assert payload["review_sync"]["automation"]["retryable"] is True
    assert len(
        [
            item
            for item in store.ledger("default")
            if item["event_type"] == "BUY"
        ]
    ) == 1
