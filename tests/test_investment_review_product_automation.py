from __future__ import annotations

import hashlib
import json
import socket
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
import src.investment_review.market_context_adapter as market_adapter_module
import src.investment_review.periodic_runner as periodic_runner_module
import src.portfolio.web as web_module
from src.investment_review.periodic_runner import (
    PeriodicAutomationConfig,
    PeriodicReportAutomationCoordinator,
    PeriodicReportRunner,
    periodic_automation_config,
)
from tests.test_investment_review_review_runner import (
    RunnerFixture,
    _closed_episode_rows,
    _fixture as build_runner_fixture,
    _local_satisfied_checkpoint_market_resolver,
    _reviewability_fixture as build_reviewability_runner_fixture,
    _trade_row,
)
from tests.test_investment_review_sync_service import _insert_ledger_row
from tests.test_investment_review_periodic_reports import (
    _empty_sidecar as _periodic_sidecar,
    _formal_portfolio_db as _periodic_portfolio_db,
)
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


def test_periodic_report_runner_catches_up_and_exposes_replayable_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    source = _periodic_portfolio_db(tmp_path)
    sidecar = _periodic_sidecar(tmp_path)
    source_before = _sha256(source)
    runner = PeriodicReportRunner(
        portfolio_db=source,
        review_db=sidecar,
        repo_root=tmp_path,
    )
    now = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)

    first = runner.run_once(
        trigger="test_catch_up",
        now=now,
        start_date="2026-07-14",
    )
    replay = runner.run_once(trigger="test_replay", now=now)

    assert first["state"] == "succeeded"
    assert first["latest"]["daily"]["period"]["trading_day_count"] == 3
    assert first["latest"]["summaries"][0]["period_type"] == "weekly"
    assert replay["state"] == "succeeded"
    assert replay["latest"]["daily"]["status"] == "up_to_date"
    assert runner.status()["last_success"]["trigger"] == "test_replay"
    assert _sha256(source) == source_before

    monkeypatch.setattr(
        periodic_runner_module,
        "generate_daily_range",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("bounded failure")),
    )
    failed = runner.run_once(
        trigger="test_failure",
        now=now,
        start_date="2026-07-14",
    )
    assert failed["state"] == "failed"
    assert failed["last_failure"]["error_type"] == "RuntimeError"
    assert "bounded failure" in failed["last_failure"]["error"]
    assert runner.status()["last_success"]["trigger"] == "test_replay"


def test_periodic_automation_is_process_local_and_disableable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    source = _periodic_portfolio_db(tmp_path)
    sidecar = _periodic_sidecar(tmp_path)
    disabled = periodic_automation_config(
        environ={
            periodic_runner_module.PERIODIC_AUTOMATION_ENV: "0",
            periodic_runner_module.PERIODIC_AUTOMATION_INTERVAL_ENV: "invalid-unused",
        }
    )
    assert disabled == PeriodicAutomationConfig(enabled=False)
    with pytest.raises(ValueError, match="between 30 and 86400"):
        periodic_automation_config(
            environ={
                periodic_runner_module.PERIODIC_AUTOMATION_INTERVAL_ENV: "1"
            }
        )
    coordinator = PeriodicReportAutomationCoordinator(
        portfolio_db=source,
        review_db=sidecar,
        repo_root=tmp_path,
        config=disabled,
    )
    assert coordinator.start()["enabled"] is False
    assert coordinator.run_once()["enabled"] is False
    assert coordinator.stop()["worker_alive"] is False
    assert coordinator.status()["os_scheduler_installed"] is False


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


def test_v2_automation_binds_perspective_anchor_and_carries_system_limitation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = build_reviewability_runner_fixture(
        tmp_path,
        rows=[
            *_closed_episode_rows(
                "2026-01-01",
                "2026-01-02",
                "v2-flat-a",
                symbol="000001.SZ",
            ),
            *_closed_episode_rows(
                "2026-01-01",
                "2026-01-02",
                "v2-flat-b",
                symbol="000002.SZ",
            ),
            _trade_row(
                event_date="2026-01-05",
                event_type="BUY",
                external_id="v2-open-a",
                symbol="000001.SZ",
            ),
            _trade_row(
                event_date="2026-01-05",
                event_type="BUY",
                external_id="v2-open-b",
                symbol="000002.SZ",
            ),
        ],
        automatic_market_context=True,
    )
    fixture.store.upgrade_reviewability_candidate_v2()
    audit_now = datetime(2026, 8, 1, 8, 1, tzinfo=timezone.utc)
    adapter = market_adapter_module.MarketContextAdapter(
        cache_root=(
            fixture.root
            / ".codex_tmp"
            / "investment_review_product_completion_v3"
            / "market_cache"
        ),
        clock=lambda: audit_now,
    )
    observed_budget_ids: dict[str, list[int]] = {"user": [], "system": []}

    def resolve_v2(**kwargs: Any) -> dict[str, Any]:
        observed_budget_ids[str(kwargs["perspective"])].append(
            id(kwargs["request_budget"])
        )
        return adapter(**kwargs)

    user = _coordinator(
        fixture,
        config=ReviewAutomationConfig(
            enabled=True,
            interval_seconds=900,
            startup_catch_up=True,
            perspective="user",
        ),
        clock=lambda: audit_now,
        checkpoint_market_resolver=resolve_v2,
    )
    system = _coordinator(
        fixture,
        config=ReviewAutomationConfig(
            enabled=True,
            interval_seconds=900,
            startup_catch_up=True,
            perspective="system",
        ),
        clock=lambda: audit_now,
        checkpoint_market_resolver=resolve_v2,
    )

    user_plan = user._prepare_plan(trigger="v2_user")
    user_repeat = user._prepare_plan(trigger="v2_user_repeat")
    system_plan = system._prepare_plan(trigger="v2_system")

    assert user_repeat.run_key == user_plan.run_key
    assert user_repeat.market_input_sha256 == user_plan.market_input_sha256
    assert user_plan.run_key != system_plan.run_key
    assert user_plan.projection_sha256 != system_plan.projection_sha256
    assert user_plan.market_input_sha256 != system_plan.market_input_sha256
    assert len(observed_budget_ids["user"]) == 8
    assert len(set(observed_budget_ids["user"][:4])) == 1
    assert len(set(observed_budget_ids["user"][4:])) == 1
    assert len(observed_budget_ids["system"]) == 4
    assert len(set(observed_budget_ids["system"])) == 1
    assert "investment_review_product_completion_v4" in (
        user._lease.path.as_posix()
    )
    for plan, perspective, limitation in (
        (user_plan, "user", "provider_unavailable"),
        (system_plan, "system", "withheld_by_cutoff"),
    ):
        manifest = plan.market_input_manifest
        checkpoint_plan = plan.checkpoint_plan
        assert manifest is not None
        assert checkpoint_plan is not None
        assert manifest["schema_version"] == (
            integration_module.REVIEW_AUTOMATION_MARKET_INPUT_MANIFEST_VERSION_V2
        )
        assert manifest["perspective"] == perspective
        assert plan.perspective == perspective
        assert len(manifest["items"]) == 4
        assert len(checkpoint_plan["identities"]) == 2
        identities = {
            identity["episode_id"]: identity
            for identity in checkpoint_plan["identities"]
        }
        for item in manifest["items"]:
            projection = item["projection"]
            fallback = projection["market_fallback"]
            assert item["projection_kind"] == "full"
            assert item["perspective"] == perspective
            assert projection["perspective"] == perspective
            assert fallback["status"] == limitation
            assert fallback["request_count"] == 0
            assert fallback["request_count_status"] == "verified"
            assert fallback["unverified_attempt_upper_bound"] == 0
            assert len(fallback["fetch_receipts"]) == 1
            guard_receipt = fallback["fetch_receipts"][0]
            assert guard_receipt["attempt_count"] == 0
            assert guard_receipt["attempt_count_status"] == "verified"
            assert guard_receipt["budget_charged_attempts"] == 0
            assert guard_receipt["started_at"] == fallback["guard_audit_at"]
            assert guard_receipt["completed_at"] == fallback["guard_audit_at"]
            identity = identities.get(item["episode_id"])
            if identity is not None:
                for field in (
                    "operation_anchor_event_id",
                    "operation_anchor_at",
                    "operation_anchor_ordering_key",
                    "information_time_policy_version",
                ):
                    assert item[field] == identity[field]

    socket_calls: list[tuple[object, ...]] = []

    def forbidden_connect(*args: object, **_kwargs: object) -> None:
        socket_calls.append(args)
        raise AssertionError("v2 automation replay must remain offline")

    monkeypatch.setattr(socket, "create_connection", forbidden_connect)
    result = system.run_once(trigger="v2_system_carry")
    assert result["status"] in {"partial", "succeeded"}, json.dumps(
        result, ensure_ascii=False, indent=2
    )
    scope_runs = {item["scope"]: item for item in result["scope_runs"]}
    assert scope_runs["single"]["checkpoint_count"] == 1
    assert scope_runs["weekly"]["checkpoint_count"] == 2
    assert scope_runs["monthly"]["checkpoint_count"] == 2
    open_episode_ids = {
        identity["episode_id"]
        for identity in system_plan.checkpoint_plan["identities"]
    }
    planned_open_market_ids = sorted(
        item["market_input_content_id"]
        for item in system_plan.market_input_manifest["items"]
        if item["episode_id"] in open_episode_ids
    )
    assert scope_runs["weekly"]["market_input_content_ids"] == (
        planned_open_market_ids
    )
    assert scope_runs["monthly"]["market_input_content_ids"] == (
        planned_open_market_ids
    )
    assert set(scope_runs["single"]["market_input_content_ids"]).issubset(
        planned_open_market_ids
    )
    checkpoints = fixture.store.list_operation_checkpoints()
    assert len(checkpoints) == 2
    assert {item["perspective"] for item in checkpoints} == {"system"}
    assert {item["market_fallback"]["status"] for item in checkpoints} == {
        "withheld_by_cutoff"
    }
    assert socket_calls == []


def test_reviewability_automation_task_key_binds_frozen_market_input_only(
    tmp_path: Path,
) -> None:
    fixture = build_reviewability_runner_fixture(tmp_path)
    current = [datetime(2026, 7, 26, 8, 1, tzinfo=timezone.utc)]
    market_revision = ["first"]
    calls: list[tuple[str, str, str]] = []

    def resolver(**kwargs: Any) -> dict[str, Any]:
        result = _local_satisfied_checkpoint_market_resolver(**kwargs)
        result["market_axis"]["summary"] = market_revision[0]
        calls.append(
            (
                str(kwargs["episode"]["episode_id"]),
                str(kwargs["as_of"]),
                str(kwargs["knowledge_cutoff"]),
            )
        )
        return result

    coordinator = _coordinator(
        fixture,
        config=ReviewAutomationConfig(
            enabled=True,
            interval_seconds=900,
            startup_catch_up=True,
        ),
        checkpoint_market_resolver=resolver,
        clock=lambda: current[0],
    )

    first = coordinator._prepare_plan(trigger="market_first")
    repeated = coordinator._prepare_plan(trigger="market_repeat")
    first_checkpoint_key = first.checkpoint_plan["identities"][0][
        "checkpoint_key"
    ]

    assert repeated.run_key == first.run_key
    assert repeated.market_input_sha256 == first.market_input_sha256
    assert first.market_input_manifest["schema_version"] == (
        integration_module.REVIEW_AUTOMATION_MARKET_INPUT_MANIFEST_VERSION
    )
    assert first.market_input_manifest["items"][0][
        "market_input_content_id"
    ].startswith("sha256:")
    assert first.market_input_sha256 is not None
    assert "investment_review_product_completion_v3" in (
        coordinator._lease.path.as_posix()
    )

    market_revision[0] = "second"
    changed_market = coordinator._prepare_plan(trigger="market_changed")

    assert changed_market.run_key != first.run_key
    assert changed_market.market_input_sha256 != first.market_input_sha256
    assert (
        changed_market.checkpoint_plan_sha256
        == first.checkpoint_plan_sha256
    )
    assert changed_market.checkpoint_plan["identities"][0][
        "checkpoint_key"
    ] == first_checkpoint_key

    current[0] = datetime(2026, 7, 26, 8, 16, tzinfo=timezone.utc)
    later = coordinator._prepare_plan(trigger="market_next_slot")

    assert later.run_key != changed_market.run_key
    assert later.checkpoint_plan["identities"][0][
        "checkpoint_key"
    ] != first_checkpoint_key
    assert len(calls) == 4


def test_automation_market_budget_is_one_cap_across_all_episodes(
    tmp_path: Path,
) -> None:
    rows = [
        _trade_row(
            event_date="2026-01-05",
            event_type="BUY",
            external_id=f"open-{index}",
            symbol=f"{index:06d}.SZ",
        )
        for index in range(1, 9)
    ]
    fixture = build_reviewability_runner_fixture(tmp_path, rows=rows)
    budget_ids: set[int] = set()
    allocations: list[int] = []

    def resolver(**kwargs: Any) -> dict[str, Any]:
        budget = kwargs["request_budget"]
        budget_ids.add(id(budget))
        reserved = budget.reserve(3)
        budget.settle(reserved, reserved)
        allocations.append(reserved)
        return _local_satisfied_checkpoint_market_resolver(**kwargs)

    coordinator = _coordinator(
        fixture,
        checkpoint_market_resolver=resolver,
        clock=lambda: datetime(2026, 7, 26, 8, 1, tzinfo=timezone.utc),
    )
    plan = coordinator._prepare_plan(trigger="shared_market_budget")

    assert len(plan.market_input_manifest["items"]) == 8
    assert len(budget_ids) == 1
    assert sum(allocations) == 20
    assert allocations[-2:] == [2, 0]
    budget_snapshot = plan.market_input_manifest["request_budget"]
    assert budget_snapshot["max_requests"] == 20
    assert budget_snapshot["used_requests"] == 20
    assert budget_snapshot["reserved_requests"] == 0
    assert budget_snapshot["remaining_requests"] == 0
    assert budget_snapshot.get("active_requests", 0) == 0


def test_market_task_identity_ignores_first_fetch_vs_exact_cache_hit_budget(
    tmp_path: Path,
) -> None:
    fixture = build_reviewability_runner_fixture(tmp_path)
    first_resolution = [True]

    def resolver(**kwargs: Any) -> dict[str, Any]:
        if first_resolution[0]:
            budget = kwargs["request_budget"]
            reserved = budget.reserve(3)
            budget.settle(reserved, reserved)
        return _local_satisfied_checkpoint_market_resolver(**kwargs)

    coordinator = _coordinator(
        fixture,
        checkpoint_market_resolver=resolver,
        clock=lambda: datetime(2026, 7, 26, 8, 1, tzinfo=timezone.utc),
    )
    fetched = coordinator._prepare_plan(trigger="first_provider_fetch")
    first_resolution[0] = False
    cached = coordinator._prepare_plan(trigger="exact_cache_hit")

    assert fetched.market_input_manifest["request_budget"][
        "used_requests"
    ] == 3
    assert cached.market_input_manifest["request_budget"][
        "used_requests"
    ] == 0
    assert cached.market_input_sha256 == fetched.market_input_sha256
    assert cached.run_key == fetched.run_key


def test_closed_only_automation_still_binds_market_manifest(
    tmp_path: Path,
) -> None:
    fixture = build_reviewability_runner_fixture(
        tmp_path,
        rows=[
            _trade_row(
                event_date="2026-01-05",
                event_type="BUY",
                external_id="closed-buy",
            ),
            _trade_row(
                event_date="2026-01-06",
                event_type="SELL",
                external_id="closed-sell",
            ),
        ],
    )
    revision = ["closed-a"]

    def resolver(**kwargs: Any) -> dict[str, Any]:
        result = _local_satisfied_checkpoint_market_resolver(**kwargs)
        result["market_axis"]["summary"] = revision[0]
        return result

    coordinator = _coordinator(
        fixture,
        checkpoint_market_resolver=resolver,
        clock=lambda: datetime(2026, 7, 26, 8, 1, tzinfo=timezone.utc),
    )
    first = coordinator._prepare_plan(trigger="closed_market_a")
    revision[0] = "closed-b"
    changed = coordinator._prepare_plan(trigger="closed_market_b")

    assert first.checkpoint_plan is None
    assert first.checkpoint_plan_sha256 is None
    assert first.market_input_sha256 is not None
    assert first.market_input_manifest["items"][0]["projection_kind"] == (
        "legacy"
    )
    assert first.market_input_manifest["items"][0]["as_of"].startswith(
        "2026-01-06T"
    )
    assert changed.run_key != first.run_key
    assert changed.market_input_sha256 != first.market_input_sha256


def test_scopes_consume_frozen_a_without_a_b_a_resolver_recall(
    tmp_path: Path,
) -> None:
    fixture = build_reviewability_runner_fixture(tmp_path)
    revisions = ["market-a", "market-b", "market-a"]
    calls = 0
    planned_episodes: list[dict[str, Any]] = []

    def resolver(**kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        result = _local_satisfied_checkpoint_market_resolver(**kwargs)
        result["market_axis"]["summary"] = revisions[calls]
        planned_episodes.append(dict(kwargs["episode"]))
        calls += 1
        return result

    coordinator = _coordinator(
        fixture,
        checkpoint_market_resolver=resolver,
        clock=lambda: datetime(2026, 7, 26, 8, 1, tzinfo=timezone.utc),
    )

    class ConsumingRunner:
        checkpoint_market_resolver = None

        def run(
            self,
            *,
            scope: str,
            as_of: str,
            knowledge_cutoff: str,
            **_kwargs: Any,
        ) -> dict[str, Any]:
            episode = planned_episodes[0]
            projection = self.checkpoint_market_resolver(
                episode=episode,
                operation_review={},
                knowledge_provenance={},
                ledger_snapshot_reconstruction={},
                perspective="user",
                as_of=as_of,
                knowledge_cutoff=knowledge_cutoff,
            )
            assert projection["market_axis"]["summary"] == "market-a"
            return {
                "run_id": f"reviewrun_{scope:0<32}"[:42],
                "run_key": f"review:frozen:{scope}",
                "status": "partial",
                "content_id": "sha256:" + ("7" * 64),
                "episodes": [
                    {"episode_id": episode["episode_id"]}
                ],
            }

    coordinator._runner_factory = ConsumingRunner
    result = coordinator.run_once(trigger="hostile_a_b_a")

    assert result["status"] == "partial"
    assert calls == 1
    persisted = fixture.store.get_review_run(result["run_key"])
    manifest = persisted["run"]["parameters"]["market_input_manifest"]
    planned_content_id = manifest["items"][0]["market_input_content_id"]
    assert manifest["items"][0]["projection"]["market_axis"][
        "summary"
    ] == "market-a"
    assert all(
        item["market_input_content_ids"] == [planned_content_id]
        for item in result["scope_runs"]
    )

    second = coordinator._prepare_plan(trigger="hostile_b")
    third = coordinator._prepare_plan(trigger="hostile_a_again")
    assert calls == 3
    assert second.run_key != result["run_key"]
    assert third.run_key == result["run_key"]


def test_cutoff_unavailable_type_survives_freeze_and_scopes_continue(
    tmp_path: Path,
) -> None:
    from src.investment_review.market_context_adapter import (
        MarketContextCutoffUnavailableError,
    )

    fixture = build_reviewability_runner_fixture(tmp_path)
    planned_episodes: list[dict[str, Any]] = []
    calls = 0

    def resolver(**kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        planned_episodes.append(dict(kwargs["episode"]))
        raise MarketContextCutoffUnavailableError(
            "real cache step is later than cutoff"
        )

    coordinator = _coordinator(
        fixture,
        checkpoint_market_resolver=resolver,
        clock=lambda: datetime(2026, 7, 26, 8, 1, tzinfo=timezone.utc),
    )

    class LimitationRunner:
        checkpoint_market_resolver = None

        def run(
            self,
            *,
            scope: str,
            as_of: str,
            knowledge_cutoff: str,
            **_kwargs: Any,
        ) -> dict[str, Any]:
            episode = planned_episodes[0]
            with pytest.raises(MarketContextCutoffUnavailableError):
                self.checkpoint_market_resolver(
                    episode=episode,
                    operation_review={},
                    knowledge_provenance={},
                    ledger_snapshot_reconstruction={},
                    perspective="user",
                    as_of=as_of,
                    knowledge_cutoff=knowledge_cutoff,
                )
            return {
                "run_id": f"reviewrun_{scope:0<32}"[:42],
                "run_key": f"review:cutoff-limitation:{scope}",
                "status": "partial",
                "content_id": "sha256:" + ("8" * 64),
                "episodes": [
                    {
                        "episode_id": episode["episode_id"],
                        "market_context_limitation": {
                            "code": "MARKET_CONTEXT_WITHHELD_BY_CUTOFF",
                            "receipt_backdated": False,
                        },
                    }
                ],
            }

    coordinator._runner_factory = LimitationRunner
    result = coordinator.run_once(trigger="historical_cutoff_missing")

    assert result["status"] == "partial"
    assert calls == 1
    run = fixture.store.get_review_run(result["run_key"])
    item = run["run"]["parameters"]["market_input_manifest"]["items"][0]
    assert item["projection"] is None
    assert item["error_code"] == "MARKET_CONTEXT_WITHHELD_BY_CUTOFF"
    assert "real cache step" not in json.dumps(item)
    assert all(
        scope_run["market_input_content_ids"] == []
        for scope_run in result["scope_runs"]
    )


def test_full_market_projection_must_bind_instrument_and_cutoffs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.investment_review.review_runner import (
        MARKET_CONTEXT_RUNNER_PROJECTION_FIELDS,
    )

    base = {
        "market_axis": {},
        "market_fallback": {"fetch_receipts": []},
        "market_gaps": [],
        "supplemental_sources": [],
        "market_input_content_id": "sha256:" + ("1" * 64),
        "market_requirement_id": "market_requirement_test",
        "market_resolution_id": "market_resolution_test",
        "as_of": "2026-07-26T08:00:00Z",
        "knowledge_cutoff": "2026-07-26T08:01:00Z",
        "market_source_manifest": {},
        "source_replay": {},
        "resolution": {
            "requirement": {"instrument_id": "000001.SZ"}
        },
    }
    assert frozenset(base) == MARKET_CONTEXT_RUNNER_PROJECTION_FIELDS
    monkeypatch.setattr(
        market_adapter_module,
        "market_context_runner_projection",
        lambda value: dict(value),
    )

    accepted = ReviewAutomationCoordinator._automation_market_projection(
        base,
        episode_id="episode-test",
        instrument_id="000001.SZ",
        as_of="2026-07-26T08:00:00Z",
        knowledge_cutoff="2026-07-26T08:01:00Z",
    )
    assert accepted["projection_kind"] == "full"

    mutations = [
        {"instrument_id": "000002.SZ"},
        {"as_of": "2026-07-26T08:00:01Z"},
        {"knowledge_cutoff": "2026-07-26T08:01:01Z"},
    ]
    for mutation in mutations:
        kwargs = {
            "episode_id": "episode-test",
            "instrument_id": "000001.SZ",
            "as_of": "2026-07-26T08:00:00Z",
            "knowledge_cutoff": "2026-07-26T08:01:00Z",
            **mutation,
        }
        with pytest.raises(RuntimeError, match="does not bind"):
            ReviewAutomationCoordinator._automation_market_projection(
                base,
                **kwargs,
            )


def test_default_market_adapter_receives_clock_and_custom_factory_is_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = build_reviewability_runner_fixture(tmp_path)
    frozen_now = datetime(2026, 7, 26, 8, 1, tzinfo=timezone.utc)
    captured: dict[str, Any] = {}

    class FakeDefaultAdapter:
        def __init__(self, *, cache_root: Path, clock) -> None:
            captured["cache_root"] = cache_root
            captured["clock"] = clock

        def __call__(self, **kwargs: Any) -> dict[str, Any]:
            return _local_satisfied_checkpoint_market_resolver(**kwargs)

    monkeypatch.setattr(
        market_adapter_module,
        "MarketContextAdapter",
        FakeDefaultAdapter,
    )
    coordinator = ReviewAutomationCoordinator(
        portfolio_db=fixture.source,
        review_db=fixture.review_db,
        mapping_path=fixture.mapping,
        artifact_root=fixture.artifacts,
        repo_root=fixture.root,
        clock=lambda: frozen_now,
    )
    plan = coordinator._prepare_plan(trigger="default_adapter")

    assert captured["clock"]() == frozen_now
    assert str(captured["cache_root"]).endswith(
        "investment_review_product_completion_v3\\market_cache"
    )
    assert plan.market_input_sha256 is not None
    with pytest.raises(ValueError, match="requires explicit"):
        ReviewAutomationCoordinator(
            portfolio_db=fixture.source,
            review_db=fixture.review_db,
            mapping_path=fixture.mapping,
            artifact_root=fixture.artifacts,
            repo_root=fixture.root,
            runner_factory=lambda: object(),
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
            self.periodic_provider = None

        def set_automation_status_provider(self, provider) -> None:
            self.provider = provider

        def set_periodic_automation_status_provider(self, provider) -> None:
            self.periodic_provider = provider

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

    class FakePeriodicCoordinator:
        def __init__(self, **kwargs: Any) -> None:
            calls.append(("periodic_init", kwargs["config"].enabled))

        def status(self) -> dict[str, Any]:
            return {
                "enabled": True,
                "state": "idle",
                "worker_alive": False,
                "os_scheduler_installed": False,
            }

        def start(self) -> dict[str, Any]:
            calls.append("periodic_start")
            return self.status()

        def stop(self, *, timeout: float) -> dict[str, Any]:
            calls.append(("periodic_stop", timeout))
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
    monkeypatch.setattr(
        web_module,
        "PeriodicReportAutomationCoordinator",
        FakePeriodicCoordinator,
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
        ("periodic_init", True),
        "periodic_start",
        ("stop", 30.0),
        ("periodic_stop", 30.0),
        "server_close",
    ]
    assert service.provider is not None
    assert service.periodic_provider is not None

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
