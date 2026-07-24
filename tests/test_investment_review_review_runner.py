from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import src.investment_review.review_runner as runner_module
import src.investment_review.sync_service as sync_module
from src.investment_review.cli import main as review_cli_main
from src.investment_review.models import DecisionRecord
from src.investment_review.review_runner import (
    ReviewRunCatalog,
    ReviewRunner,
    ReviewRunnerError,
)
from src.investment_review.store import ReviewStore
from src.investment_review.sync_service import sync_review_events
from src.portfolio.store import PortfolioStore
from tests.test_investment_review_sync_service import (
    _initialize_product_sidecar,
    _write_fixture,
)


AS_OF = "2026-02-02T23:59:59Z"
KNOWLEDGE_CUTOFF = "2026-07-14T00:00:00Z"


@dataclass(frozen=True)
class RunnerFixture:
    root: Path
    source: Path
    mapping: Path
    review_db: Path
    artifacts: Path
    store: ReviewStore
    runner: ReviewRunner


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


def _trade_row(
    *,
    event_date: str,
    event_type: str,
    external_id: str,
    symbol: str = "000001.SZ",
    quantity: str = "10",
    event_time: str = "10:00:00",
) -> dict[str, str]:
    is_buy = event_type == "BUY"
    return {
        "account_id": "acct",
        "event_date": event_date,
        "event_time": event_time,
        "event_type": event_type,
        "ts_code": symbol,
        "quantity": quantity,
        "price": "100",
        "gross_amount": "1000",
        "fees": "1",
        "cash_amount": "-1001" if is_buy else "999",
        "external_id": external_id,
        "dedupe_key": external_id,
        # This field is deliberately not treated as historical known_at.
        "created_at": "2026-07-14T00:00:00Z",
    }


def _closed_episode_rows(
    opened_on: str,
    closed_on: str,
    suffix: str,
    *,
    symbol: str = "000001.SZ",
) -> list[dict[str, str]]:
    return [
        _trade_row(
            event_date=opened_on,
            event_type="BUY",
            external_id=f"buy-{suffix}",
            symbol=symbol,
        ),
        _trade_row(
            event_date=closed_on,
            event_type="SELL",
            external_id=f"sell-{suffix}",
            symbol=symbol,
        ),
    ]


def _fixture(
    tmp_path: Path,
    *,
    rows: list[dict[str, str]] | None = None,
    reconcile: bool = True,
) -> RunnerFixture:
    root = tmp_path / "repo"
    source, mapping, review_db = _write_fixture(
        root,
        rows=rows
        or _closed_episode_rows("2026-01-05", "2026-01-06", "one"),
    )
    # The runner consumes the existing P2B tables in read-only mode.  Initializing
    # their empty schema here gives the fixture the same contract as the formal DB.
    PortfolioStore(source).initialize()
    store = _initialize_product_sidecar(review_db)
    if reconcile:
        sync_review_events(
            source,
            review_db=review_db,
            mapping_path=mapping,
            repo_root=root,
        )
    artifacts = root / "run-artifacts"
    runner = ReviewRunner(
        review_db=review_db,
        portfolio_db=source,
        mapping_path=mapping,
        artifact_root=artifacts,
        repo_root=root,
    )
    return RunnerFixture(
        root=root,
        source=source,
        mapping=mapping,
        review_db=review_db,
        artifacts=artifacts,
        store=store,
        runner=runner,
    )


def _run(
    fixture: RunnerFixture,
    *,
    scope: str = "single",
    dry_run: bool = False,
    as_of: str = AS_OF,
) -> dict[str, Any]:
    return fixture.runner.run(
        scope=scope,
        as_of=as_of,
        knowledge_cutoff=KNOWLEDGE_CUTOFF,
        dry_run=dry_run,
        trigger="pytest",
    )


def _stage(receipt: dict[str, Any], name: str) -> dict[str, Any]:
    return next(stage for stage in receipt["stages"] if stage["name"] == name)


def test_cli_dry_run_does_not_mutate_sidecar_source_or_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _fixture(tmp_path)
    source_before = _sha256(fixture.source)
    sidecar_before = _sha256(fixture.review_db)
    monkeypatch.setattr(runner_module, "_repo_root", lambda: fixture.root)
    monkeypatch.setattr(sync_module, "_default_repo_root", lambda: fixture.root)

    exit_code = review_cli_main(
        [
            "--db",
            str(fixture.review_db),
            "review-run",
            "--portfolio-db",
            str(fixture.source),
            "--mapping",
            str(fixture.mapping),
            "--artifact-root",
            str(fixture.artifacts),
            "--scope",
            "single",
            "--as-of",
            AS_OF,
            "--knowledge-cutoff",
            KNOWLEDGE_CUTOFF,
            "--dry-run",
        ]
    )
    receipt = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert receipt["mode"] == "dry_run"
    assert receipt["status"] == "partial"
    assert receipt["review_sidecar"]["mutated"] is False
    assert receipt["source_proof"]["unchanged"] is True
    assert _sha256(fixture.source) == source_before
    assert _sha256(fixture.review_db) == sidecar_before
    assert not fixture.artifacts.exists()
    assert (
        fixture.runner.validate_receipt(receipt)["validation_status"]
        == "accepted"
    )
    assert all(
        artifact["write_status"] == "dry_run"
        for stage in receipt["stages"]
        for artifact in stage["artifacts"]
    )


@pytest.mark.parametrize(
    "unsafe_cutoff",
    ["2026-02-02", "2026-02-02 23:59:59"],
)
def test_service_rejects_naive_or_date_only_cutoffs(
    tmp_path: Path,
    unsafe_cutoff: str,
) -> None:
    fixture = _fixture(tmp_path)
    sidecar_before = _sha256(fixture.review_db)

    with pytest.raises(
        ReviewRunnerError, match="explicit timezone or Z suffix"
    ):
        fixture.runner.run(
            scope="single",
            as_of=unsafe_cutoff,
            knowledge_cutoff=KNOWLEDGE_CUTOFF,
            dry_run=True,
        )

    assert _sha256(fixture.review_db) == sidecar_before
    assert not fixture.artifacts.exists()


def test_cli_rejects_naive_cutoff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _fixture(tmp_path)
    monkeypatch.setattr(runner_module, "_repo_root", lambda: fixture.root)
    monkeypatch.setattr(sync_module, "_default_repo_root", lambda: fixture.root)

    exit_code = review_cli_main(
        [
            "--db",
            str(fixture.review_db),
            "review-run",
            "--portfolio-db",
            str(fixture.source),
            "--mapping",
            str(fixture.mapping),
            "--artifact-root",
            str(fixture.artifacts),
            "--scope",
            "single",
            "--as-of",
            "2026-02-02 23:59:59",
            "--knowledge-cutoff",
            KNOWLEDGE_CUTOFF,
            "--dry-run",
        ]
    )
    error = json.loads(capsys.readouterr().err)

    assert exit_code == 2
    assert error["status"] == "ERROR"
    assert error["error_type"] == "ReviewRunnerError"
    assert "explicit timezone or Z suffix" in error["error"]
    assert not fixture.artifacts.exists()


def test_apply_then_identical_repeat_reuses_immutable_receipt(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    source_before = _sha256(fixture.source)

    first = _run(fixture)
    sidecar_after_first = _sha256(fixture.review_db)
    artifacts_after_first = _tree_hashes(fixture.artifacts)
    second = _run(fixture)

    assert first == second
    assert first["status"] == "partial"
    assert first["run_id"] == second["run_id"]
    assert first["run_key"] == second["run_key"]
    assert first["content_id"] == second["content_id"]
    assert _sha256(fixture.source) == source_before
    assert _sha256(fixture.review_db) == sidecar_after_first
    assert _tree_hashes(fixture.artifacts) == artifacts_after_first
    assert artifacts_after_first


def test_single_weekly_monthly_selection_is_deterministic(
    tmp_path: Path,
) -> None:
    rows = [
        *_closed_episode_rows("2026-01-05", "2026-01-06", "old"),
        *_closed_episode_rows("2026-01-28", "2026-01-29", "week-a"),
        *_closed_episode_rows("2026-01-31", "2026-02-01", "week-b"),
    ]
    fixture = _fixture(tmp_path, rows=rows)
    source_before = _sha256(fixture.source)
    expected_counts = {"single": 1, "weekly": 2, "monthly": 3}
    selections: dict[str, list[str]] = {}

    for scope, expected_count in expected_counts.items():
        first = _run(fixture, scope=scope, dry_run=True)
        second = _run(fixture, scope=scope, dry_run=True)
        assert first == second
        selected = first["selection"]["selected_episode_ids"]
        assert len(selected) == expected_count
        assert selected == sorted(selected)
        selections[scope] = selected

    assert set(selections["single"]) < set(selections["weekly"])
    assert set(selections["weekly"]) < set(selections["monthly"])
    assert _sha256(fixture.source) == source_before
    assert not fixture.artifacts.exists()


def test_immutable_artifact_collision_blocks_without_overwrite(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    preview = _run(fixture, dry_run=True)
    collision = (
        fixture.artifacts
        / str(preview["run_id"])
        / "snapshot_inventory.json"
    )
    collision.parent.mkdir(parents=True)
    collision.write_bytes(b"pre-existing-different-content")
    collision_before = _sha256(collision)
    source_before = _sha256(fixture.source)

    receipt = _run(fixture)

    assert receipt["status"] == "blocked"
    assert "CANONICAL_GATE_BLOCKED" in receipt["gaps"]
    blocked_stage = receipt["stages"][-1]
    assert blocked_stage["status"] == "blocked"
    assert (
        blocked_stage["details"]["error_type"]
        == "ImmutableArtifactConflict"
    )
    assert _sha256(collision) == collision_before
    assert _sha256(fixture.source) == source_before


def test_explicit_recorded_decision_is_consumed_without_inference(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    event = next(
        item
        for item in fixture.store.list_events()
        if item["source_record_id"].endswith("buy-one")
    )
    decision = DecisionRecord.build(
        symbol="000001.SZ",
        occurred_at="2026-01-05T00:00:00Z",
        known_at="2026-01-05T00:01:00Z",
        thesis="Only this explicitly recorded thesis may be used.",
        direct_reason="Explicit human-recorded reason.",
        risk_notes="Explicit human-recorded risk.",
        timezone="UTC",
    )
    decision_id = fixture.store.add_decision(decision)
    fixture.store.link_decision_event(decision_id, event["event_id"])

    receipt = _run(fixture)
    episode = receipt["episodes"][0]
    input_bundle = json.loads(
        Path(episode["artifacts"]["input"]["path"]).read_text(encoding="utf-8")
    )
    review = json.loads(
        Path(episode["artifacts"]["review"]["path"]).read_text(encoding="utf-8")
    )
    linked = input_bundle["frozen_sources"]["linked_decisions"]
    facts = [
        fact
        for section in review["fact_sections"].values()
        for fact in section["facts"]
    ]

    assert episode["decision_status"] == "linked"
    assert episode["decision_source_count"] == 1
    assert len(linked) == 1
    assert linked[0]["source_id"] == decision_id
    assert linked[0]["payload"]["thesis"] == decision.thesis
    assert linked[0]["payload"]["direct_reason"] == decision.direct_reason
    assert linked[0]["payload"]["risk_notes"] == decision.risk_notes
    assert any(
        fact["kind"] == "recorded_decision"
        and fact["data"]["decision_id"] == decision_id
        for fact in facts
    )
    assert receipt["governance"]["historical_decisions_inferred"] is False
    assert review["interpretation_sections"] == {
        "alternative_explanations": [],
        "counterfactual_options": [],
        "history_links": [],
        "hypotheses": [],
        "main_tensions": [],
    }


def test_new_explicit_decision_link_changes_run_identity(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    first = _run(fixture)
    event = next(
        item
        for item in fixture.store.list_events()
        if item["source_record_id"].endswith("buy-one")
    )
    decision = DecisionRecord.build(
        symbol="000001.SZ",
        occurred_at="2026-01-05T00:00:00Z",
        known_at="2026-01-05T00:01:00Z",
        thesis="New explicit evidence must produce a new review run.",
        timezone="UTC",
    )
    decision_id = fixture.store.add_decision(decision)
    fixture.store.link_decision_event(decision_id, event["event_id"])

    second = _run(fixture)

    assert first["run_key"] != second["run_key"]
    assert first["run_id"] != second["run_id"]
    assert first["episodes"][0]["decision_source_count"] == 0
    assert second["episodes"][0]["decision_source_count"] == 1
    assert second["episodes"][0]["decision_status"] == "linked"


def test_failed_stage_can_retry_same_run_key_to_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    original = runner_module.inspect_portfolio_snapshots
    calls = 0

    def fail_once(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("synthetic transient snapshot failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(
        runner_module,
        "inspect_portfolio_snapshots",
        fail_once,
    )
    first = _run(fixture)
    second = _run(fixture)
    run = fixture.store.get_review_run(str(second["run_key"]))
    statuses = [item["status"] for item in run["history"]]

    assert first["status"] == "failed"
    assert first["retry"]["retryable"] is True
    assert first["stages"][-1]["details"]["error_type"] == "RuntimeError"
    assert second["status"] == "partial"
    assert second["run_key"] == first["run_key"]
    assert calls == 2
    assert "failed" in statuses
    assert statuses[-1] == "partial"


def test_sync_preflight_failure_is_recorded_and_receipt_is_valid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)

    def fail_sync(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("synthetic sync preflight failure")

    monkeypatch.setattr(runner_module, "sync_review_events", fail_sync)
    receipt = _run(fixture)
    recorded = fixture.store.get_review_run(str(receipt["run_key"]))

    assert receipt["status"] == "failed"
    assert receipt["run_key"].startswith("review:preflight:")
    assert (
        fixture.runner.validate_receipt(receipt)["validation_status"]
        == "accepted"
    )
    assert recorded["status"] == "failed"
    assert recorded["status_event"]["details"]["failed_stage"] == "sync"
    assert recorded["status_event"]["details"]["retryable"] is True


def test_dry_run_with_lag_returns_valid_blocked_preflight_without_writes(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, reconcile=False)
    sidecar_before = _sha256(fixture.review_db)
    receipt = _run(fixture, dry_run=True)

    assert receipt["status"] == "blocked"
    assert receipt["run_key"].startswith("review:preflight:")
    assert (
        fixture.runner.validate_receipt(receipt)["validation_status"]
        == "accepted"
    )
    assert _sha256(fixture.review_db) == sidecar_before
    assert not fixture.artifacts.exists()


def test_retry_after_terminal_ledger_failure_reuses_same_receipt_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    original = fixture.runner._append_status
    calls = 0

    def fail_terminal_once(
        store: ReviewStore,
        *,
        run_id: str,
        status: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic terminal-ledger failure")
        return original(
            store,
            run_id=run_id,
            status=status,
            details=details,
        )

    monkeypatch.setattr(fixture.runner, "_append_status", fail_terminal_once)
    first = _run(fixture)
    receipt_path = (
        fixture.artifacts
        / str(first["run_id"])
        / "receipt.json"
    )
    receipt_hash = _sha256(receipt_path)
    monkeypatch.setattr(fixture.runner, "_append_status", original)

    second = fixture.runner.run(
        scope="single",
        as_of=AS_OF,
        knowledge_cutoff=KNOWLEDGE_CUTOFF,
        trigger="startup_retry",
    )

    assert first["status"] == "failed"
    assert second["status"] == "partial"
    assert second["run_key"] == first["run_key"]
    assert second["trigger"] == "pytest"
    assert _sha256(receipt_path) == receipt_hash
    assert json.loads(receipt_path.read_text(encoding="utf-8")) == second


def test_terminal_receipt_with_tampered_artifact_is_blocked_on_replay(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    first = _run(fixture)
    review_path = Path(
        first["episodes"][0]["artifacts"]["review"]["path"]
    )
    review_path.write_text('{"tampered":true}\n', encoding="utf-8")

    replay = _run(fixture)

    assert replay["status"] == "blocked"
    assert replay["stages"][-1]["status"] == "blocked"
    assert (
        replay["stages"][-1]["details"]["error_type"]
        == "CanonicalGateBlocked"
    )
    assert "CANONICAL_GATE_BLOCKED" in replay["gaps"]


def test_real_facts_only_artifacts_pass_source_replay_and_no_advice_governance(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    source_before = _sha256(fixture.source)
    receipt = _run(fixture)
    replay = _stage(receipt, "source_replay")
    facts_stage = _stage(receipt, "facts_only")
    catalog = ReviewRunCatalog(
        review_db=fixture.review_db,
        portfolio_db=fixture.source,
        artifact_root=fixture.artifacts,
        repo_root=fixture.root,
    )
    detail = catalog.get_review(receipt["episodes"][0]["review_id"])
    review = detail["review"]

    assert replay["status"] == "ready"
    assert replay["details"]["verified_episode_count"] == 1
    assert all(
        component["source_verification"] == "verified"
        for episode in replay["details"]["episodes"]
        for component in (
            episode["context"],
            episode["review_input"],
            episode["facts_only_review"],
        )
    )
    assert facts_stage["details"] == {
        "review_count": 1,
        "generation_mode": "facts_only",
        "model_called": False,
        "no_advice": True,
    }
    assert receipt["governance"] == {
        "facts_only": True,
        "model_called": False,
        "historical_decisions_inferred": False,
        "portfolio_source_written": False,
        "no_advice": True,
    }
    assert review["governance"]["generation_mode"] == "facts_only"
    assert review["governance"]["model_generation"] is None
    assert review["governance"]["no_advice"] is True
    assert review["governance"]["no_mechanical_score"] is True
    assert detail["validation"]["validation_status"] == "accepted"
    assert _sha256(fixture.source) == source_before
