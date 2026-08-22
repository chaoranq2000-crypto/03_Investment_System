from __future__ import annotations

import hashlib
import json
import sqlite3
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

import src.investment_review.review_runner as runner_module
import src.investment_review.sync_service as sync_module
from src.investment_review.artifact_io import canonical_json_bytes
from src.investment_review.cli import main as review_cli_main
from src.investment_review.episode_review import (
    build_facts_only_episode_review,
)
from src.investment_review.models import (
    MARKET_FALLBACK_POLICY_VERSION,
    MARKET_PROVIDER_ALLOWLIST,
    MARKET_PROVIDER_ALLOWLIST_SHA256,
    MARKET_PROVIDER_ALLOWLIST_VERSION,
    OPERATION_CHECKPOINT_SCHEMA_VERSION_V2,
    PUBLIC_INFORMATION_POLICY_VERSION,
    DecisionRecord,
)
from src.investment_review.market_context_adapter import (
    MARKET_GATEWAY_CONTRACT_VERSION,
    MARKET_RATE_LIMIT_POLICY_VERSION,
    MarketContextAdapter,
    MarketRequestBudget,
    _provider_information_candidate_v2,
    _provider_publication_source_ref_v2,
    market_context_resolution_path,
    market_row_content_sha256_v2,
    resolve_market_context,
)
from src.investment_review.review_input_bundle import (
    build_review_input_bundle,
    validate_review_input_bundle,
)
from src.investment_review.review_checkpoint import (
    derive_review_checkpoint_operation_anchor,
)
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
LATER_AS_OF = "2026-02-03T23:59:59Z"


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


def _reviewability_fixture(
    tmp_path: Path,
    *,
    rows: list[dict[str, str]] | None = None,
    checkpoint_market_resolver: Any | None = None,
    automatic_market_context: bool = False,
) -> RunnerFixture:
    root = tmp_path / "repo"
    source, mapping, review_db = _write_fixture(
        root,
        rows=rows
        or [
            _trade_row(
                event_date="2026-01-05",
                event_type="BUY",
                external_id="open-one",
            ),
            _trade_row(
                event_date="2026-01-06",
                event_type="BUY",
                external_id="increase-one",
            ),
        ],
    )
    if automatic_market_context:
        review_db = (
            root
            / "data"
            / "db"
            / "investment_review_reviewability_v3.sqlite3"
        )
    PortfolioStore(source).initialize()
    store = ReviewStore(review_db)
    store.initialize_reviewability_candidate()
    sync_review_events(
        source,
        review_db=review_db,
        mapping_path=mapping,
        repo_root=root,
    )
    artifacts = root / "run-artifacts"
    runner_kwargs: dict[str, Any] = {
        "review_db": review_db,
        "portfolio_db": source,
        "mapping_path": mapping,
        "artifact_root": artifacts,
        "repo_root": root,
    }
    if not automatic_market_context:
        runner_kwargs["checkpoint_market_resolver"] = (
            checkpoint_market_resolver
        )
    runner = ReviewRunner(**runner_kwargs)
    return RunnerFixture(
        root=root,
        source=source,
        mapping=mapping,
        review_db=review_db,
        artifacts=artifacts,
        store=store,
        runner=runner,
    )


def _seed_cutoff_safe_market_rows(source: Path) -> None:
    connection = sqlite3.connect(source)
    columns = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(instruments)")
    }
    additions = {
        "name": "TEXT NOT NULL DEFAULT ''",
        "exchange": "TEXT NOT NULL DEFAULT ''",
        "currency": "TEXT NOT NULL DEFAULT ''",
        "industry_name": "TEXT NOT NULL DEFAULT ''",
        "industry_source": "TEXT NOT NULL DEFAULT ''",
        "industry_updated_at": "TEXT NOT NULL DEFAULT ''",
        "updated_at": "TEXT NOT NULL DEFAULT ''",
    }
    for name, declaration in additions.items():
        if name not in columns:
            connection.execute(
                f"ALTER TABLE instruments ADD COLUMN {name} {declaration}"
            )
    connection.execute(
        """
        UPDATE instruments
        SET name = ?, exchange = ?, currency = ?, updated_at = ?
        WHERE ts_code = ?
        """,
        (
            "fixture instrument",
            "SZ",
            "CNY",
            "2026-01-01T00:00:00Z",
            "000001.SZ",
        ),
    )
    connection.executemany(
        """
        INSERT INTO close_prices(
            ts_code, trade_date, close, pre_close, pct_chg, source,
            fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "000001.SZ",
                "2026-01-01",
                "99",
                "98",
                "1.02",
                "tushare.daily",
                "2026-01-03T00:00:00Z",
            ),
            (
                "000001.SZ",
                "2026-02-01",
                "101",
                "100",
                "1",
                "tushare.daily",
                "2026-02-02T00:00:00Z",
            ),
        ],
    )
    connection.commit()
    assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    connection.close()


def _local_satisfied_checkpoint_market_resolver(
    **kwargs: Any,
) -> dict[str, Any]:
    episode = kwargs["episode"]
    scope = episode["scope"]
    cache_ref = (
        "fixture_market_cache:"
        f"{scope['instrument_id']}:2026-01-07:local_close"
    )
    return {
        "market_axis": {
            "status": "available",
            "temporal_role": "system_known_at_decision",
            "effective_at": "2026-01-07T07:00:00Z",
            "publicly_available_at": "2026-01-07T07:01:00Z",
            "publicly_available_basis": "exchange_calendar",
            "fetched_at": "2026-01-07T07:02:00Z",
            "system_observed_at": "2026-01-07T07:02:00Z",
            "summary": "测试夹具中的本地收盘价覆盖已冻结。",
            "source_refs": [cache_ref],
        },
        "market_fallback": {
            "policy_version": MARKET_FALLBACK_POLICY_VERSION,
            "allowlist_version": MARKET_PROVIDER_ALLOWLIST_VERSION,
            "allowlist_sha256": MARKET_PROVIDER_ALLOWLIST_SHA256,
            "coverage_before": "satisfied",
            "coverage_after": "satisfied",
            "status": "not_needed",
            "request_count": 0,
            "limits": {
                "timeout_seconds": 20,
                "max_retries": 2,
                "max_concurrency": 2,
                "max_requests_per_run": 20,
            },
            "allowlist": sorted(MARKET_PROVIDER_ALLOWLIST),
            "cache_refs": [cache_ref],
            "fetch_receipt_refs": [],
            "fetch_receipts": [],
            "offline_consumers": {
                "renderer": False,
                "source_replay": False,
                "api": False,
                "ui": False,
            },
        },
        "market_gaps": [],
    }


def _run(
    fixture: RunnerFixture,
    *,
    scope: str = "single",
    dry_run: bool = False,
    as_of: str = AS_OF,
    perspective: str = "user",
) -> dict[str, Any]:
    return fixture.runner.run(
        scope=scope,
        as_of=as_of,
        knowledge_cutoff=KNOWLEDGE_CUTOFF,
        perspective=perspective,
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
    assert receipt["cutoffs"]["perspective"] == "user"
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


def test_cli_forwards_explicit_system_perspective(
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
            AS_OF,
            "--knowledge-cutoff",
            KNOWLEDGE_CUTOFF,
            "--perspective",
            "system",
            "--dry-run",
        ]
    )
    receipt = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert receipt["cutoffs"]["perspective"] == "system"
    assert not fixture.artifacts.exists()


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


def test_default_user_and_explicit_perspectives_are_bound_to_run_identity(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)

    default_user = fixture.runner.run(
        scope="single",
        as_of=AS_OF,
        knowledge_cutoff=KNOWLEDGE_CUTOFF,
        dry_run=True,
    )
    explicit_user = _run(fixture, dry_run=True, perspective="user")
    system = _run(fixture, dry_run=True, perspective="system")

    assert default_user == explicit_user
    assert default_user["cutoffs"]["perspective"] == "user"
    assert system["cutoffs"]["perspective"] == "system"
    assert system["run_key"] != default_user["run_key"]
    assert system["content_id"] != default_user["content_id"]
    assert len(default_user["episodes"]) == 1
    assert system["episodes"] == []
    assert system["selection"]["selected_episode_ids"] == []


def test_legacy_sidecar_does_not_enable_ledger_reconstruction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)

    def unexpected_reconstruction(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError(
            "legacy sidecars must preserve their canonical runner path"
        )

    monkeypatch.setattr(
        runner_module,
        "build_ledger_snapshot_reconstruction",
        unexpected_reconstruction,
    )

    receipt = _run(fixture, dry_run=True)

    assert receipt["status"] == "partial"
    assert "reviewability_schema_version" not in receipt["cutoffs"]
    assert (
        "ledger_snapshot_reconstruction_count"
        not in _stage(receipt, "snapshot")["details"]
    )
    assert "ledger_snapshot_reconstruction" not in receipt["episodes"][0]


def test_reviewability_runner_freezes_and_replays_ledger_reconstruction(
    tmp_path: Path,
) -> None:
    fixture = _reviewability_fixture(tmp_path)
    source_before = _sha256(fixture.source)

    receipt = _run(fixture)

    assert _sha256(fixture.source) == source_before
    assert receipt["cutoffs"]["reviewability_schema_version"] == 1
    assert (
        receipt["cutoffs"][
            "ledger_snapshot_reconstruction_schema_version"
        ]
        == runner_module.LEDGER_SNAPSHOT_RECONSTRUCTION_SCHEMA_VERSION
    )
    assert (
        receipt["cutoffs"][
            "ledger_snapshot_projection_manifest_version"
        ]
        == runner_module.LEDGER_RECONSTRUCTION_PROJECTION_MANIFEST_VERSION
    )
    assert len(
        receipt["cutoffs"][
            "ledger_snapshot_reconstruction_projection_sha256"
        ]
    ) == 64
    snapshot_stage = _stage(receipt, "snapshot")
    assert snapshot_stage["details"][
        "ledger_snapshot_reconstruction_count"
    ] == 1
    assert len(
        snapshot_stage["details"]["cash_baseline_proof_content_ids"]
    ) == 1
    episode = receipt["episodes"][0]
    projection = episode["ledger_snapshot_reconstruction"]
    assert projection["ending_quantity"] == "20"
    assert projection["status"] in {"available", "partial"}
    assert snapshot_stage["details"][
        "ledger_snapshot_reconstruction_content_ids"
    ] == [projection["content_id"]]
    descriptor = next(
        item
        for item in snapshot_stage["artifacts"]
        if item.get("content_id") == projection["content_id"]
    )
    artifact = json.loads(
        Path(descriptor["path"]).read_text(encoding="utf-8")
    )
    assert artifact["episode_id"] == episode["episode_id"]
    assert artifact["content_id"] == projection["content_id"]
    assert (
        runner_module.validate_ledger_snapshot_reconstruction(artifact)[
            "validation_status"
        ]
        == "accepted"
    )
    frozen_input = json.loads(
        Path(episode["artifacts"]["input"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    supplementals = frozen_input["frozen_sources"][
        "supplemental_sources"
    ]
    assert len(supplementals) == 1
    assert (
        supplementals[0]["payload"]["schema_version"]
        == runner_module.LEDGER_SNAPSHOT_RECONSTRUCTION_SCHEMA_VERSION
    )
    replay = _stage(receipt, "source_replay")["details"]["episodes"][0][
        "ledger_snapshot_reconstruction"
    ]
    assert replay == {
        **projection,
        "validation_status": "accepted",
        "source_verification": "verified",
    }
    assert (
        fixture.runner.validate_receipt(receipt)["validation_status"]
        == "accepted"
    )
    assert _run(fixture) == receipt


def test_reviewability_runner_appends_open_active_checkpoints_idempotently(
    tmp_path: Path,
) -> None:
    fixture = _reviewability_fixture(
        tmp_path,
        rows=[
            *_closed_episode_rows(
                "2026-01-01",
                "2026-01-02",
                "explicit-prior-flat-baseline",
            ),
            _trade_row(
                event_date="2026-01-05",
                event_type="BUY",
                external_id="open-one",
            ),
            _trade_row(
                event_date="2026-01-06",
                event_type="BUY",
                external_id="increase-one",
            ),
        ],
        checkpoint_market_resolver=(
            _local_satisfied_checkpoint_market_resolver
        ),
    )
    source_before = _sha256(fixture.source)
    sidecar_before = _sha256(fixture.review_db)

    dry_receipt = _run(fixture, dry_run=True)
    dry_episode = dry_receipt["episodes"][0]
    dry_projection = dry_episode["review_checkpoint"]

    assert _sha256(fixture.source) == source_before
    assert _sha256(fixture.review_db) == sidecar_before
    assert _tree_hashes(fixture.artifacts) == {}
    assert fixture.store.list_operation_checkpoints() == []
    assert dry_episode["operation_review_status"] == "ready"
    assert dry_episode["decision_context_status"] == "not_recorded"
    assert dry_projection["review_kind"] == "active_checkpoint"
    assert dry_projection["checkpoint_type"] == "active_checkpoint"
    assert dry_projection["review_readiness"] == "ready"
    assert dry_projection["decision_context_status"] == "not_recorded"
    assert dry_projection["episode_lifecycle"] == "open"
    assert dry_projection["outcome_maturity"] == "interim"
    assert dry_projection["market_status"] == "available"
    assert dry_projection["lifecycle_notices"] == [
        "OPEN_EPISODE_OUTCOME_NOT_FINAL"
    ]
    assert (
        "OPEN_EPISODE_OUTCOME_NOT_FINAL" not in dry_receipt["gaps"]
    )
    assert dry_episode["artifacts"]["review_checkpoint"][
        "write_status"
    ] == "dry_run"
    dry_replay = _stage(dry_receipt, "source_replay")["details"][
        "episodes"
    ][0]["review_checkpoint"]
    assert dry_replay["validation_status"] == "accepted"
    assert dry_replay["source_verification"] == "verified"
    assert {
        key: dry_replay[key] for key in dry_projection
    } == dry_projection
    assert (
        fixture.runner.validate_receipt(dry_receipt)[
            "validation_status"
        ]
        == "accepted"
    )

    applied = _run(fixture)
    applied_episode = applied["episodes"][0]
    applied_projection = applied_episode["review_checkpoint"]
    checkpoints = fixture.store.list_operation_checkpoints(
        episode_id=applied_episode["episode_id"]
    )

    assert len(checkpoints) == 1
    assert applied_projection == dry_projection
    assert _sha256(fixture.source) == source_before
    checkpoint_descriptor = applied_episode["artifacts"][
        "review_checkpoint"
    ]
    checkpoint_artifact = json.loads(
        Path(checkpoint_descriptor["path"]).read_text(encoding="utf-8")
    )
    assert checkpoint_descriptor["content_id"] == (
        applied_projection["content_id"]
    )
    assert checkpoint_artifact == checkpoints[0]
    assert (
        runner_module.validate_review_checkpoint(checkpoint_artifact)[
            "validation_status"
        ]
        == "accepted"
    )
    assert {
        gap["code"] for gap in checkpoint_artifact["gaps"]
    }.isdisjoint({"OPEN_EPISODE_OUTCOME_NOT_FINAL"})
    assert checkpoint_artifact["status_axes"]["operation"]["status"] == (
        "ready"
    )
    assert checkpoint_artifact["status_axes"]["decision"]["status"] == (
        "not_recorded"
    )
    assert checkpoint_artifact["status_axes"]["lifecycle"]["status"] == (
        "open"
    )
    assert checkpoint_artifact["status_axes"]["outcome"]["status"] == (
        "interim"
    )
    assert checkpoint_artifact["market_fallback"]["status"] == (
        "not_needed"
    )
    assert checkpoint_artifact["market_fallback"]["request_count"] == 0
    assert checkpoint_artifact["market_fallback"]["fetch_receipts"] == []
    assert (
        fixture.runner.validate_receipt(applied)["validation_status"]
        == "accepted"
    )

    sidecar_after_apply = _sha256(fixture.review_db)
    artifacts_after_apply = _tree_hashes(fixture.artifacts)
    repeated = _run(fixture)

    assert repeated == applied
    assert _sha256(fixture.review_db) == sidecar_after_apply
    assert _tree_hashes(fixture.artifacts) == artifacts_after_apply
    assert len(
        fixture.store.list_operation_checkpoints(
            episode_id=applied_episode["episode_id"]
        )
    ) == 1

    later = _run(fixture, as_of=LATER_AS_OF)
    later_episode = later["episodes"][0]
    later_projection = later_episode["review_checkpoint"]
    appended = fixture.store.list_operation_checkpoints(
        episode_id=applied_episode["episode_id"]
    )

    assert later["run_key"] != applied["run_key"]
    assert later_episode["episode_id"] == applied_episode["episode_id"]
    assert later_projection["position_case_id"] == (
        applied_projection["position_case_id"]
    )
    assert later_projection["as_of"] == LATER_AS_OF
    assert later_projection["checkpoint_key"] != (
        applied_projection["checkpoint_key"]
    )
    assert [item["as_of"] for item in appended] == [
        AS_OF,
        LATER_AS_OF,
    ]
    assert len(appended) == 2
    assert (
        fixture.runner.validate_receipt(later)["validation_status"]
        == "accepted"
    )


def test_reviewability_runner_rejects_an_unclosed_market_projection(
    tmp_path: Path,
) -> None:
    fixture = _reviewability_fixture(
        tmp_path,
        checkpoint_market_resolver=lambda **kwargs: {
            "unexpected_fixture_field": kwargs["as_of"]
        },
    )
    source_before = _sha256(fixture.source)
    sidecar_before = _sha256(fixture.review_db)

    receipt = _run(fixture, dry_run=True)

    assert receipt["status"] == "blocked"
    assert receipt["stages"][-1]["status"] == "blocked"
    assert receipt["stages"][-1]["details"]["error_type"] == (
        "CanonicalGateBlocked"
    )
    assert "unsupported fields" in (
        receipt["stages"][-1]["details"]["error"]
    )
    assert "CANONICAL_GATE_BLOCKED" in receipt["gaps"]
    assert _sha256(fixture.source) == source_before
    assert _sha256(fixture.review_db) == sidecar_before
    assert fixture.store.list_operation_checkpoints() == []
    assert not fixture.artifacts.exists()
    assert (
        fixture.runner.validate_receipt(receipt)["validation_status"]
        == "accepted"
    )


def test_p6_default_market_adapter_freezes_every_selected_episode(
    tmp_path: Path,
) -> None:
    fixture = _reviewability_fixture(
        tmp_path,
        rows=[
            *_closed_episode_rows(
                "2026-02-01",
                "2026-02-02",
                "closed-market-target",
            ),
            _trade_row(
                event_date="2026-02-02",
                event_type="BUY",
                external_id="open-market-target",
                event_time="12:00:00",
            ),
        ],
        automatic_market_context=True,
    )
    _seed_cutoff_safe_market_rows(fixture.source)
    source_before = _sha256(fixture.source)

    receipt = _run(fixture, scope="monthly")

    assert _sha256(fixture.source) == source_before
    assert len(receipt["episodes"]) == 2
    assert receipt["cutoffs"][
        "market_context_projection_manifest_version"
    ] == runner_module.MARKET_CONTEXT_PROJECTION_MANIFEST_VERSION
    assert len(
        receipt["cutoffs"]["market_context_projection_sha256"]
    ) == 64
    episode_stage = _stage(receipt, "episode")
    assert episode_stage["details"]["market_context_count"] == 2
    market_cache = (
        fixture.root
        / ".codex_tmp"
        / "investment_review_product_completion_v3"
        / "market_cache"
    )
    for item in receipt["episodes"]:
        assert market_context_resolution_path(
            market_cache,
            item["market_context"]["market_requirement_id"],
        ).is_file()

    open_episode = next(
        item for item in receipt["episodes"] if "review_checkpoint" in item
    )
    closed_episode = next(
        item for item in receipt["episodes"] if "review_checkpoint" not in item
    )
    for item in receipt["episodes"]:
        market = item["market_context"]
        assert market["as_of"] == item[
            "ledger_snapshot_reconstruction"
        ]["as_of"]
        assert market["knowledge_cutoff"] == KNOWLEDGE_CUTOFF
        assert market["market_fallback"]["status"] == "not_needed"
        assert market["market_fallback"]["request_count"] == 0
        assert market["market_fallback"]["fetch_receipts"] == []
        assert market["source_replay"]["source_verification"] == (
            "verified"
        )
        frozen_input = json.loads(
            Path(item["artifacts"]["input"]["path"]).read_text(
                encoding="utf-8"
            )
        )
        frozen_source_ids = {
            source["source_id"]
            for source in frozen_input["frozen_sources"][
                "supplemental_sources"
            ]
        }
        assert {
            source["source_id"]
            for source in market["supplemental_sources"]
        }.issubset(frozen_source_ids)

    assert closed_episode["market_context"]["as_of"] < receipt[
        "cutoffs"
    ]["as_of"]
    assert open_episode["market_context"]["as_of"] == receipt[
        "cutoffs"
    ]["as_of"]
    checkpoint = json.loads(
        Path(
            open_episode["artifacts"]["review_checkpoint"]["path"]
        ).read_text(encoding="utf-8")
    )
    assert checkpoint["status_axes"]["market"] == open_episode[
        "market_context"
    ]["market_axis"]
    assert (
        fixture.runner.validate_receipt(receipt)["validation_status"]
        == "accepted"
    )

    cache_before = _tree_hashes(market_cache)
    receipt_repeat = _run(fixture, scope="monthly")
    assert receipt_repeat == receipt
    assert _tree_hashes(market_cache) == cache_before


def test_p6_missing_market_only_degrades_market_axis(
    tmp_path: Path,
) -> None:
    fixture = _reviewability_fixture(
        tmp_path,
        rows=[
            *_closed_episode_rows(
                "2026-01-01",
                "2026-01-02",
                "explicit-prior-flat-baseline",
            ),
            _trade_row(
                event_date="2026-01-05",
                event_type="BUY",
                external_id="open-market-target",
            ),
        ],
        automatic_market_context=True,
    )
    fixture.runner.checkpoint_market_resolver = MarketContextAdapter(
        cache_root=fixture.runner.market_cache_root,
        clock=lambda: datetime(2026, 7, 13, tzinfo=timezone.utc),
    )

    receipt = _run(fixture)
    episode = receipt["episodes"][0]
    checkpoint = json.loads(
        Path(episode["artifacts"]["review_checkpoint"]["path"]).read_text(
            encoding="utf-8"
        )
    )

    assert episode["operation_review_status"] == "ready"
    assert checkpoint["status_axes"]["operation"]["status"] == "ready"
    assert episode["market_context"]["market_axis"]["status"] in {
        "missing",
        "failed",
        "insufficient",
        "partial",
    }
    assert episode["market_context"]["market_fallback"]["status"] == (
        "provider_unavailable"
    )
    assert episode["market_context"]["market_fallback"][
        "request_count"
    ] == 0
    assert (
        fixture.runner.validate_receipt(receipt)["validation_status"]
        == "accepted"
    )


def test_p6_late_provider_receipt_is_not_backdated_and_operation_continues(
    tmp_path: Path,
) -> None:
    fixture = _reviewability_fixture(
        tmp_path,
        rows=[
            *_closed_episode_rows(
                "2026-01-01",
                "2026-01-02",
                "explicit-prior-flat-baseline",
            ),
            _trade_row(
                event_date="2026-01-05",
                event_type="BUY",
                external_id="open-market-target",
            ),
        ],
        automatic_market_context=True,
    )

    receipt = _run(fixture)
    episode = receipt["episodes"][0]
    limitation = episode["market_context_limitation"]

    assert receipt["status"] == "partial"
    assert episode["operation_review_status"] == "ready"
    assert limitation == {
        "status": "withheld_by_cutoff",
        "code": "MARKET_CONTEXT_WITHHELD_BY_CUTOFF",
        "instrument_id": "000001.SZ",
        "as_of": AS_OF,
        "knowledge_cutoff": KNOWLEDGE_CUTOFF,
        "network_attempted": False,
        "receipt_backdated": False,
    }
    assert "market_context" not in episode
    assert "review_checkpoint" not in episode
    assert fixture.store.list_operation_checkpoints() == []
    assert (
        fixture.runner.validate_receipt(receipt)["validation_status"]
        == "accepted"
    )


def test_p6_v2_provider_limitation_is_frozen_and_keeps_active_checkpoint(
    tmp_path: Path,
) -> None:
    fixture = _reviewability_fixture(
        tmp_path,
        rows=[
            *_closed_episode_rows(
                "2026-02-01",
                "2026-02-02",
                "closed-v2-market-target",
            ),
            _trade_row(
                event_date="2026-02-02",
                event_type="BUY",
                external_id="open-v2-market-target",
                event_time="12:00:00",
            ),
        ],
        automatic_market_context=True,
    )
    fixture.store.upgrade_reviewability_candidate_v2()
    assert fixture.store.status()["reviewability_schema_version"] == 2
    audit_now = datetime(2026, 7, 27, 8, 0, tzinfo=timezone.utc)
    adapter = MarketContextAdapter(
        cache_root=fixture.runner.market_cache_root,
        clock=lambda: audit_now,
    )
    observed_anchors: list[dict[str, Any]] = []

    def resolve_v2(**kwargs: Any) -> dict[str, Any]:
        projection = adapter(**kwargs)
        checkpoint_type = (
            "active_checkpoint"
            if kwargs["episode"]["status"] == "open"
            else "exit"
        )
        expected = derive_review_checkpoint_operation_anchor(
            kwargs["episode"],
            operation_review=kwargs["operation_review"],
            checkpoint_type=checkpoint_type,
            checkpoint_as_of=kwargs["as_of"],
        )
        observed_anchors.append(
            {
                "episode_status": kwargs["episode"]["status"],
                "expected": expected,
                "actual": {
                    field: projection[field]
                    for field in (
                        "operation_anchor_event_id",
                        "operation_anchor_at",
                        "operation_anchor_ordering_key",
                    )
                },
            }
        )
        return projection

    fixture.runner.checkpoint_market_resolver = resolve_v2
    receipt = _run(fixture, scope="monthly")

    assert receipt["status"] in {"partial", "ready"}, json.dumps(
        {
            "stage": receipt["stages"][-1],
            "anchors": observed_anchors,
        },
        ensure_ascii=False,
        indent=2,
    )
    assert receipt["cutoffs"].get("reviewability_schema_version") == 2, (
        json.dumps(receipt["stages"], ensure_ascii=False, indent=2)
    )
    assert len(observed_anchors) == 2
    assert all(
        {
            field: item["expected"][field]
            for field in (
                "operation_anchor_event_id",
                "operation_anchor_at",
                "operation_anchor_ordering_key",
            )
        }
        == item["actual"]
        for item in observed_anchors
    )
    assert len(receipt["episodes"]) == 2
    episode_ids_by_status = {
        item["episode_status"]: item["expected"]["episode_id"]
        for item in observed_anchors
    }
    open_episode = next(
        item
        for item in receipt["episodes"]
        if item["episode_id"] == episode_ids_by_status["open"]
    )
    closed_episode = next(
        item
        for item in receipt["episodes"]
        if item["episode_id"] == episode_ids_by_status["closed"]
    )

    for episode in (open_episode, closed_episode):
        market = episode["market_context"]
        fallback = market["market_fallback"]
        assert market["perspective"] == "user"
        assert market["information_time_policy_version"] == (
            PUBLIC_INFORMATION_POLICY_VERSION
        )
        assert market["operation_anchor_at"] <= market["as_of"]
        assert fallback["status"] == "provider_unavailable"
        assert fallback["request_count"] == 0
        assert fallback["request_count_status"] == "verified"
        assert fallback["unverified_attempt_upper_bound"] == 0
        assert len(fallback["fetch_receipts"]) == 1
        guard_receipt = fallback["fetch_receipts"][0]
        assert guard_receipt["response_status"] == "provider_unavailable"
        assert guard_receipt["attempt_count"] == 0
        assert guard_receipt["attempt_count_status"] == "verified"
        assert guard_receipt["budget_charged_attempts"] == 0
        assert guard_receipt["started_at"] == fallback["guard_audit_at"]
        assert guard_receipt["completed_at"] == fallback["guard_audit_at"]
        assert guard_receipt["fetched_at"] is None
        assert guard_receipt["raw_content_sha256"] is None
        assert guard_receipt["normalized_content_sha256"] is None
        assert guard_receipt["cache_entry_refs"] == []
        # Audit time is a real post-cutoff fact, not a fabricated historical
        # timestamp.  The v2 input bundle must nevertheless freeze it intact.
        assert fallback["guard_audit_at"] == "2026-07-27T08:00:00Z"
        assert fallback["guard_audit_at"] > KNOWLEDGE_CUTOFF
        frozen_input = json.loads(
            Path(episode["artifacts"]["input"]["path"]).read_text(
                encoding="utf-8"
            )
        )
        assert validate_review_input_bundle(frozen_input)[
            "validation_status"
        ] in {"accepted", "accepted_with_warnings"}

    assert "review_checkpoint" not in closed_episode
    assert closed_episode["market_context"]["operation_anchor_at"].startswith(
        "2026-02-02T02:00:00"
    )
    assert open_episode["operation_review_status"] == "ready"
    assert open_episode["market_context"]["operation_anchor_at"].startswith(
        "2026-02-02T04:00:00"
    )
    checkpoint = json.loads(
        Path(open_episode["artifacts"]["review_checkpoint"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    assert checkpoint["schema_version"] == OPERATION_CHECKPOINT_SCHEMA_VERSION_V2
    assert checkpoint["status_axes"]["operation"]["status"] == "ready"
    open_market = open_episode["market_context"]
    market_axis = open_market["market_axis"]
    evidence_manifest = open_market["market_evidence_manifest"]
    assert checkpoint["status_axes"]["market"] == market_axis
    assert checkpoint["market_fallback"] == open_market["market_fallback"]
    assert market_axis["market_evidence_manifest_content_id"] == (
        evidence_manifest["content_id"]
    )
    assert (
        "market_evidence_manifest:" + evidence_manifest["content_id"]
        in checkpoint["source_refs"]
    )
    assert open_market["market_source_manifest"] == open_market["resolution"][
        "market_source_manifest"
    ]
    assert evidence_manifest == open_market["resolution"][
        "market_evidence_manifest"
    ]
    assert checkpoint["operation_anchor_event_id"] == open_episode[
        "market_context"
    ]["operation_anchor_event_id"]
    assert checkpoint["operation_anchor_at"] == open_episode["market_context"][
        "operation_anchor_at"
    ]
    assert checkpoint["operation_anchor_ordering_key"] == open_episode[
        "market_context"
    ]["operation_anchor_ordering_key"]
    assert fixture.runner.validate_receipt(receipt)["validation_status"] == (
        "accepted"
    )


def test_p6_v2_duplicate_provider_rows_keep_operation_ready_checkpoint(
    tmp_path: Path,
) -> None:
    class DuplicateGateway:
        transport_scheme = "https"
        market_gateway_contract_version = MARKET_GATEWAY_CONTRACT_VERSION
        rate_limit_policy_version = MARKET_RATE_LIMIT_POLICY_VERSION
        enforces_provider_rate_limit = True
        enforces_timeout_cap = True
        enforces_retry_cap = True
        enforces_concurrency_cap = True

        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def fetch(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(deepcopy(kwargs))
            request = kwargs["request"]
            row: dict[str, Any] = {
                "ts_code": "000001.SZ",
                "trade_date": "2026-02-01",
                "close": "101",
                "pre_close": "100",
                "pct_chg": "1",
                "publication_status": "verified",
                "publicly_available_at": "2026-02-01T07:00:00Z",
                "publication_basis": "official_release_metadata.v1",
                "revision_ref": "runner-duplicate-rev-1",
            }
            row["content_sha256"] = market_row_content_sha256_v2(
                component="prior_close",
                instrument_id="000001.SZ",
                row=row,
            )
            information = _provider_information_candidate_v2(
                normalized=row,
                revision_ref=row["revision_ref"],
                fetched_at="2026-07-27T08:00:00Z",
            )
            row["public_time_source_ref"] = (
                _provider_publication_source_ref_v2(
                    provider_id=str(request["provider_id"]),
                    endpoint_id=str(request["endpoint_id"]),
                    publication_basis=row["publication_basis"],
                    revision_ref=row["revision_ref"],
                    content_sha256=row["content_sha256"],
                    information_time=information,
                )
            )
            return {
                "response_status": "succeeded",
                "attempt_count": 1,
                "fetched_at": "2026-07-27T08:00:00Z",
                "raw_payload": "runner-duplicate-provider-response",
                "rows": [deepcopy(row), deepcopy(row)],
            }

    fixture = _reviewability_fixture(
        tmp_path,
        rows=[
            *_closed_episode_rows(
                "2026-01-01",
                "2026-01-02",
                "duplicate-provider-baseline",
            ),
            _trade_row(
                event_date="2026-02-02",
                event_type="BUY",
                external_id="open-v2-duplicate-provider",
                event_time="12:00:00",
            )
        ],
        automatic_market_context=True,
    )
    fixture.store.upgrade_reviewability_candidate_v2()
    gateway = DuplicateGateway()
    fixture.runner.checkpoint_market_resolver = MarketContextAdapter(
        cache_root=fixture.runner.market_cache_root,
        provider_gateway=gateway,
        clock=lambda: datetime(2026, 7, 27, 8, 0, tzinfo=timezone.utc),
    )

    receipt = _run(fixture)
    assert receipt["episodes"], json.dumps(receipt, ensure_ascii=False, indent=2)
    episode = receipt["episodes"][0]
    market = episode["market_context"]
    external = [
        item
        for item in market["supplemental_sources"]
        if item.get("payload", {}).get("origin") == "external_provider_cache"
    ]

    assert len(gateway.calls) == 1
    assert episode["operation_review_status"] == "ready"
    assert "review_checkpoint" in episode["artifacts"]
    assert market["market_fallback"]["status"] == "succeeded"
    assert market["market_fallback"]["request_count"] == 1
    assert len(external) == 1
    assert len(external[0]["payload"]["origin_cache_entry"]["rows"]) == 1
    checkpoint = json.loads(
        Path(episode["artifacts"]["review_checkpoint"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    assert checkpoint["checkpoint_type"] == "active_checkpoint"
    assert checkpoint["status_axes"]["operation"]["status"] == "ready"
    assert fixture.runner.validate_receipt(receipt)["validation_status"] == (
        "accepted"
    )


def test_p6_runner_shares_one_request_budget_across_selected_episodes(
    tmp_path: Path,
) -> None:
    budget_ids: list[int] = []

    def resolver(**kwargs: Any) -> dict[str, Any]:
        budget = kwargs["request_budget"]
        budget_ids.append(id(budget))
        reserved = budget.reserve(1)
        assert reserved == 1
        budget.settle(reserved, 1)
        return _local_satisfied_checkpoint_market_resolver(**kwargs)

    fixture = _reviewability_fixture(
        tmp_path,
        rows=[
            *_closed_episode_rows(
                "2026-01-05",
                "2026-01-06",
                "closed",
            ),
            _trade_row(
                event_date="2026-01-07",
                event_type="BUY",
                external_id="open",
            ),
        ],
        checkpoint_market_resolver=resolver,
    )
    budget = MarketRequestBudget()

    receipt = fixture.runner.run(
        scope="monthly",
        as_of=AS_OF,
        knowledge_cutoff=KNOWLEDGE_CUTOFF,
        dry_run=True,
        market_request_budget=budget,
    )

    assert len(receipt["episodes"]) == 2
    assert len(budget_ids) == 2
    assert len(set(budget_ids)) == 1
    assert budget_ids[0] == id(budget)
    assert budget.snapshot() == {
        "max_requests": 20,
        "used_requests": 2,
        "reserved_requests": 0,
        "active_requests": 0,
        "remaining_requests": 18,
    }
    assert _stage(receipt, "episode")["details"][
        "market_request_budget"
    ] == budget.snapshot()
    assert (
        fixture.runner.validate_receipt(receipt)["validation_status"]
        == "accepted"
    )


@pytest.mark.parametrize(
    "mismatch",
    ["instrument_id", "as_of", "knowledge_cutoff"],
)
def test_p6_full_market_projection_binds_requested_episode_and_cutoffs(
    tmp_path: Path,
    mismatch: str,
) -> None:
    fixture = _reviewability_fixture(
        tmp_path,
        automatic_market_context=True,
    )

    def resolver(**kwargs: Any) -> dict[str, Any]:
        episode_scope = kwargs["episode"]["scope"]
        instrument_id = str(episode_scope["instrument_id"])
        market_as_of = str(kwargs["as_of"])
        market_cutoff = str(kwargs["knowledge_cutoff"])
        if mismatch == "instrument_id":
            instrument_id = "999999.SZ"
        elif mismatch == "as_of":
            market_as_of = "2026-02-01T23:59:59Z"
        else:
            market_cutoff = "2026-07-13T23:59:59Z"
        return resolve_market_context(
            portfolio_db=kwargs["portfolio_db"],
            review_db=kwargs["review_db"],
            instrument_id=instrument_id,
            as_of=market_as_of,
            knowledge_cutoff=market_cutoff,
            cache_root=(
                fixture.runner.market_cache_root / mismatch
            ),
            clock=lambda: datetime(
                2026, 7, 13, tzinfo=timezone.utc
            ),
            request_budget=kwargs["request_budget"],
        )

    fixture.runner.checkpoint_market_resolver = resolver
    receipt = _run(fixture, dry_run=True)

    assert receipt["status"] == "blocked"
    assert receipt["stages"][-1]["details"]["error_type"] == (
        "CanonicalGateBlocked"
    )
    assert "does not bind the requested instrument and cutoffs" in (
        receipt["stages"][-1]["details"]["error"]
    )
    assert (
        fixture.runner.validate_receipt(receipt)["validation_status"]
        == "accepted"
    )


def test_p6_market_hash_changes_run_key_not_checkpoint_key(
    tmp_path: Path,
) -> None:
    fixture = _reviewability_fixture(
        tmp_path,
        rows=[
            *_closed_episode_rows(
                "2026-01-01",
                "2026-01-02",
                "explicit-prior-flat-baseline",
            ),
            _trade_row(
                event_date="2026-01-05",
                event_type="BUY",
                external_id="open-market-target",
            ),
        ],
        automatic_market_context=True,
    )
    _seed_cutoff_safe_market_rows(fixture.source)

    def resolver_with_threshold(seconds: int):
        def resolve(**kwargs: Any) -> dict[str, Any]:
            episode = kwargs["episode"]
            return resolve_market_context(
                portfolio_db=kwargs["portfolio_db"],
                review_db=kwargs["review_db"],
                instrument_id=episode["scope"]["instrument_id"],
                as_of=kwargs["as_of"],
                knowledge_cutoff=kwargs["knowledge_cutoff"],
                cache_root=(
                    fixture.root
                    / ".codex_tmp"
                    / "investment_review_product_completion_v3"
                    / "market_cache"
                    / str(seconds)
                ),
                staleness_seconds={"prior_close": seconds},
            )

        return resolve

    first_runner = ReviewRunner(
        review_db=fixture.review_db,
        portfolio_db=fixture.source,
        mapping_path=fixture.mapping,
        artifact_root=fixture.artifacts,
        repo_root=fixture.root,
        checkpoint_market_resolver=resolver_with_threshold(604800),
    )
    second_runner = ReviewRunner(
        review_db=fixture.review_db,
        portfolio_db=fixture.source,
        mapping_path=fixture.mapping,
        artifact_root=fixture.artifacts,
        repo_root=fixture.root,
        checkpoint_market_resolver=resolver_with_threshold(604801),
    )

    first = first_runner.run(
        scope="single",
        as_of=AS_OF,
        knowledge_cutoff=KNOWLEDGE_CUTOFF,
        dry_run=True,
    )
    second = second_runner.run(
        scope="single",
        as_of=AS_OF,
        knowledge_cutoff=KNOWLEDGE_CUTOFF,
        dry_run=True,
    )

    assert first["run_key"] != second["run_key"]
    assert first["episodes"][0]["market_context"][
        "market_input_content_id"
    ] != second["episodes"][0]["market_context"][
        "market_input_content_id"
    ]
    assert first["episodes"][0]["review_checkpoint"][
        "checkpoint_key"
    ] == second["episodes"][0]["review_checkpoint"]["checkpoint_key"]
    assert first_runner.validate_receipt(first)["validation_status"] == (
        "accepted"
    )
    assert second_runner.validate_receipt(second)[
        "validation_status"
    ] == "accepted"


def test_default_market_sentinel_preserves_legacy_receipt_bytes(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    default_receipt = _run(fixture, dry_run=True)
    disabled = ReviewRunner(
        review_db=fixture.review_db,
        portfolio_db=fixture.source,
        mapping_path=fixture.mapping,
        artifact_root=fixture.artifacts,
        repo_root=fixture.root,
        checkpoint_market_resolver=None,
    )
    disabled_receipt = disabled.run(
        scope="single",
        as_of=AS_OF,
        knowledge_cutoff=KNOWLEDGE_CUTOFF,
        dry_run=True,
        trigger="pytest",
    )

    assert disabled_receipt == default_receipt


def test_reviewability_runner_fails_closed_when_reconstruction_replay_blocks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _reviewability_fixture(tmp_path)

    monkeypatch.setattr(
        runner_module,
        "replay_validate_ledger_snapshot_reconstruction",
        lambda *args, **kwargs: {
            "validation_status": "blocked",
            "findings": [
                {
                    "severity": "blocker",
                    "code": "SYNTHETIC_REPLAY_DRIFT",
                }
            ],
            "source_verification": {"status": "failed"},
        },
    )

    receipt = _run(fixture, dry_run=True)

    assert receipt["status"] == "blocked"
    assert receipt["stages"][-1]["status"] == "blocked"
    assert (
        receipt["stages"][-1]["details"]["error_type"]
        == "CanonicalGateBlocked"
    )
    assert "CANONICAL_GATE_BLOCKED" in receipt["gaps"]


@pytest.mark.parametrize("dry_run", [True, False])
def test_receipt_validator_rejects_coordinated_reconstruction_quantity_tamper(
    tmp_path: Path,
    dry_run: bool,
) -> None:
    fixture = _reviewability_fixture(tmp_path)
    tampered = deepcopy(_run(fixture, dry_run=dry_run))
    tampered["episodes"][0]["ledger_snapshot_reconstruction"][
        "ending_quantity"
    ] = "999999"
    _stage(tampered, "source_replay")["details"]["episodes"][0][
        "ledger_snapshot_reconstruction"
    ]["ending_quantity"] = "999999"
    tampered["content_id"] = runner_module._receipt_content_id(tampered)

    validation = fixture.runner.validate_receipt(tampered)

    assert validation["validation_status"] == "blocked"
    assert (
        "LEDGER_RECONSTRUCTION_PROJECTION_BINDING_MISMATCH"
        in validation["findings"]
    )
    if not dry_run:
        assert (
            "LEDGER_RECONSTRUCTION_ARTIFACT_INVALID"
            in validation["findings"]
        )


def test_dry_receipt_validator_rejects_coordinated_reconstruction_id_tamper(
    tmp_path: Path,
) -> None:
    fixture = _reviewability_fixture(tmp_path)
    tampered = deepcopy(_run(fixture, dry_run=True))
    projection = tampered["episodes"][0][
        "ledger_snapshot_reconstruction"
    ]
    original_content_id = projection["content_id"]
    fake_content_id = "sha256:" + ("f" * 64)
    projection["content_id"] = fake_content_id
    _stage(tampered, "source_replay")["details"]["episodes"][0][
        "ledger_snapshot_reconstruction"
    ]["content_id"] = fake_content_id
    snapshot_stage = _stage(tampered, "snapshot")
    snapshot_stage["details"][
        "ledger_snapshot_reconstruction_content_ids"
    ] = [fake_content_id]
    for descriptor in snapshot_stage["artifacts"]:
        if descriptor.get("content_id") == original_content_id:
            descriptor["content_id"] = fake_content_id
    tampered["episodes"][0]["artifacts"]["snapshot_reconstruction"][
        "content_id"
    ] = fake_content_id
    tampered["content_id"] = runner_module._receipt_content_id(tampered)

    validation = fixture.runner.validate_receipt(tampered)

    assert validation["validation_status"] == "blocked"
    assert (
        "LEDGER_RECONSTRUCTION_PROJECTION_BINDING_MISMATCH"
        in validation["findings"]
    )


def test_service_rejects_unknown_perspective_before_any_write(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    sidecar_before = _sha256(fixture.review_db)

    with pytest.raises(
        ReviewRunnerError, match="unsupported review perspective"
    ):
        fixture.runner.run(
            scope="single",
            as_of=AS_OF,
            knowledge_cutoff=KNOWLEDGE_CUTOFF,
            perspective="omniscient",
            dry_run=True,
        )

    assert _sha256(fixture.review_db) == sidecar_before
    assert not fixture.artifacts.exists()


def test_service_rejects_as_of_after_knowledge_before_sync_or_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    sidecar_before = _sha256(fixture.review_db)
    sync_called = False

    def unexpected_sync(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal sync_called
        sync_called = True
        raise AssertionError("sync must not run for an invalid cutoff order")

    monkeypatch.setattr(
        runner_module,
        "sync_review_events",
        unexpected_sync,
    )

    with pytest.raises(
        ReviewRunnerError,
        match="as_of must not be later than knowledge_cutoff",
    ):
        fixture.runner.run(
            scope="single",
            as_of="2026-07-14T00:00:01Z",
            knowledge_cutoff="2026-07-14T00:00:00Z",
            dry_run=False,
        )

    assert sync_called is False
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
    recorded = fixture.store.get_review_run(str(first["run_key"]))
    parameters = recorded["run"]["parameters"]

    assert first == second
    assert first["status"] == "partial"
    assert first["run_id"] == second["run_id"]
    assert first["run_key"] == second["run_key"]
    assert first["content_id"] == second["content_id"]
    assert _sha256(fixture.source) == source_before
    assert _sha256(fixture.review_db) == sidecar_after_first
    assert _tree_hashes(fixture.artifacts) == artifacts_after_first
    assert artifacts_after_first
    assert parameters["perspective"] == "user"
    assert parameters["knowledge_provenance_schema_version"] == (
        runner_module.KNOWLEDGE_PROVENANCE_SCHEMA_VERSION
    )
    assert parameters["knowledge_provenance_method_version"] == (
        runner_module.KNOWLEDGE_PROVENANCE_METHOD_VERSION
    )
    assert parameters["knowledge_provenance_content_id"] == (
        first["cutoffs"]["knowledge_provenance_content_id"]
    )


def test_receipt_validation_requires_the_generation_artifact_namespace(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    receipt = _run(fixture, dry_run=True)
    mismatched_validator = ReviewRunner(
        review_db=fixture.review_db,
        portfolio_db=fixture.source,
        mapping_path=fixture.mapping,
        artifact_root=fixture.root / "different-artifact-namespace",
        repo_root=fixture.root,
    )

    validation = mismatched_validator.validate_receipt(receipt)

    assert validation["validation_status"] == "blocked"
    assert validation["findings"] == [
        "RUN_KEY_PERSPECTIVE_BINDING_MISMATCH"
    ]


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


@pytest.mark.parametrize("dry_run", [True, False])
def test_monthly_reentry_does_not_merge_into_prior_closed_episode(
    tmp_path: Path,
    dry_run: bool,
) -> None:
    rows = [
        *_closed_episode_rows("2026-01-05", "2026-01-06", "closed"),
        _trade_row(
            event_date="2026-01-31",
            event_type="BUY",
            external_id="reentry-open",
            quantity="20",
        ),
    ]
    fixture = _reviewability_fixture(tmp_path, rows=rows)

    receipt = _run(fixture, scope="monthly", dry_run=dry_run)

    assert receipt["status"] != "blocked"
    assert len(receipt["selection"]["selected_episode_ids"]) == 2
    projections = [
        item["ledger_snapshot_reconstruction"]
        for item in receipt["episodes"]
    ]
    assert sorted(item["ending_quantity"] for item in projections) == [
        "0",
        "20",
    ]
    assert sorted(item["as_of"] for item in projections) == [
        "2026-01-06T02:00:00Z",
        receipt["cutoffs"]["as_of"],
    ]
    assert (
        fixture.runner.validate_receipt(receipt)["validation_status"]
        == "accepted"
    )


def test_same_timestamp_reentry_uses_p2c_source_order_cursor(
    tmp_path: Path,
) -> None:
    rows = [
        _trade_row(
            event_date="2026-01-05",
            event_type="BUY",
            external_id="same-time-open",
        ),
        _trade_row(
            event_date="2026-01-06",
            event_time="10:00:00",
            event_type="SELL",
            external_id="same-time-close",
        ),
        _trade_row(
            event_date="2026-01-06",
            event_time="10:00:00",
            event_type="BUY",
            external_id="same-time-reentry",
            quantity="20",
        ),
    ]
    fixture = _reviewability_fixture(tmp_path, rows=rows)

    receipt = _run(fixture, scope="monthly")

    assert receipt["status"] != "blocked"
    assert len(receipt["selection"]["selected_episode_ids"]) == 2
    projections = [
        item["ledger_snapshot_reconstruction"]
        for item in receipt["episodes"]
    ]
    assert sorted(item["ending_quantity"] for item in projections) == [
        "0",
        "20",
    ]
    closed_episode = next(
        item
        for item in receipt["episodes"]
        if item["ledger_snapshot_reconstruction"]["ending_quantity"] == "0"
    )
    closed_artifact = json.loads(
        Path(
            closed_episode["artifacts"]["snapshot_reconstruction"]["path"]
        ).read_text(encoding="utf-8")
    )
    closing_event_id = closed_artifact["source_binding"][
        "episode_event_ids"
    ][-1]
    closing_anchors = [
        item
        for item in closed_artifact["anchors"]
        if item["event_id"] == closing_event_id
    ]
    assert len(closing_anchors) == 2
    assert {
        item["ordering_status"] for item in closing_anchors
    } == {"ambiguous"}
    assert all(
        len(item["same_time_event_ids"]) == 2
        for item in closing_anchors
    )
    assert any(
        closing_event_id in item["event_ids"]
        and len(item["event_ids"]) == 2
        and item["ordering_status"] == "ambiguous"
        for item in closed_artifact["event_cursor"]["same_time_groups"]
    )
    assert (
        fixture.runner.validate_receipt(receipt)["validation_status"]
        == "accepted"
    )


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
    parameters = recorded["run"]["parameters"]
    assert parameters["perspective"] == "user"
    assert parameters["knowledge_provenance_schema_version"] == (
        runner_module.KNOWLEDGE_PROVENANCE_SCHEMA_VERSION
    )
    assert parameters["knowledge_provenance_method_version"] == (
        runner_module.KNOWLEDGE_PROVENANCE_METHOD_VERSION
    )
    assert parameters[
        "knowledge_provenance_request_content_id"
    ].startswith("sha256:")


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
            episode["operation_review"],
            episode["knowledge_provenance"],
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


def test_no_decision_operation_review_is_ready_as_a_parallel_artifact(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)

    receipt = _run(fixture)

    episode_result = receipt["episodes"][0]
    assert episode_result["operation_review_status"] == "ready"
    assert episode_result["decision_context_status"] == "not_recorded"
    assert episode_result["operation_count"] == 2
    assert episode_result["decision_source_count"] == 0

    episode_stage = _stage(receipt, "episode")
    operation_content_id = episode_result["operation_review_content_id"]
    knowledge_content_id = episode_result[
        "knowledge_provenance_content_id"
    ]
    assert receipt["cutoffs"]["knowledge_provenance_content_id"] == (
        knowledge_content_id
    )
    assert episode_result["perspective"] == "user"
    assert (
        episode_stage["details"]["operation_review_content_id"]
        == operation_content_id
    )
    assert (
        episode_stage["details"]["operation_review_source_replay"]
        == "verified"
    )
    operation_descriptor = next(
        descriptor
        for descriptor in episode_stage["artifacts"]
        if descriptor["content_id"] == operation_content_id
    )
    operation_artifact = json.loads(
        Path(operation_descriptor["path"]).read_text(encoding="utf-8")
    )
    knowledge_descriptor = next(
        descriptor
        for descriptor in episode_stage["artifacts"]
        if descriptor["content_id"] == knowledge_content_id
    )
    knowledge_artifact = json.loads(
        Path(knowledge_descriptor["path"]).read_text(encoding="utf-8")
    )
    assert knowledge_artifact["perspective"] == "user"
    assert (
        runner_module.validate_knowledge_provenance(knowledge_artifact)[
            "validation_status"
        ]
        == "accepted"
    )
    assert (
        runner_module.validate_operation_review(operation_artifact)[
            "validation_status"
        ]
        == "accepted"
    )
    operation_episode = operation_artifact["episode_reviews"][0]
    assert operation_episode["operation_review_status"] == "ready"
    assert operation_episode["decision_context_status"] == "not_recorded"
    assert [
        operation["operation_type"]
        for operation in operation_episode["operations"]
    ] == ["position_open", "position_close"]

    replay_projection = _stage(receipt, "source_replay")["details"][
        "episodes"
    ][0]["operation_review"]
    assert replay_projection == {
        "validation_status": "accepted",
        "source_verification": "verified",
        "content_id": operation_content_id,
        "operation_review_status": "ready",
        "decision_context_status": "not_recorded",
    }

    # Rebuild the legacy P2F chain from the same frozen P2C/P2E-3 inputs.  The
    # parallel operation projection must not enter either canonical payload.
    collection_descriptor = next(
        descriptor
        for descriptor in episode_stage["artifacts"]
        if Path(descriptor["path"]).name == "episode_collection.json"
    )
    collection = json.loads(
        Path(collection_descriptor["path"]).read_text(encoding="utf-8")
    )
    direct_user_collection = runner_module.build_episode_collection(
        fixture.store.list_episode_projection_inputs(),
        cutoff_at=receipt["cutoffs"]["episode_cutoff"],
        snapshot_references=collection["snapshot_catalog"],
    )
    context = json.loads(
        Path(episode_result["artifacts"]["context"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    saved_input = json.loads(
        Path(episode_result["artifacts"]["input"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    saved_review = json.loads(
        Path(episode_result["artifacts"]["review"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    rebuilt_input = build_review_input_bundle(
        collection,
        context,
        portfolio_db=fixture.source,
        episode_id=episode_result["episode_id"],
        review_cutoff=receipt["cutoffs"]["review_cutoff"],
        decision_sources=[],
        supplemental_sources=[],
    )
    rebuilt_review = build_facts_only_episode_review(rebuilt_input)

    assert saved_input["schema_version"] == "p2f.review_input_bundle.v1"
    assert saved_review["schema_version"] == "p2f.episode_review.v1"
    assert canonical_json_bytes(collection) == canonical_json_bytes(
        direct_user_collection
    )
    assert canonical_json_bytes(saved_input) == canonical_json_bytes(
        rebuilt_input
    )
    assert canonical_json_bytes(saved_review) == canonical_json_bytes(
        rebuilt_review
    )


def test_receipt_validator_still_accepts_a_legacy_v1_receipt_projection(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    current = _run(fixture)
    legacy = deepcopy(current)
    legacy["cutoffs"].pop("perspective")
    knowledge_content_id = legacy["cutoffs"].pop(
        "knowledge_provenance_content_id"
    )

    episode_stage = _stage(legacy, "episode")
    operation_content_id = episode_stage["details"].pop(
        "operation_review_content_id"
    )
    episode_stage["details"].pop("operation_review_validation_status")
    episode_stage["details"].pop("operation_review_source_replay")
    episode_stage["details"].pop("operation_review_summary")
    episode_stage["details"].pop("perspective")
    episode_stage["details"].pop("knowledge_provenance_content_id")
    episode_stage["details"].pop(
        "knowledge_provenance_validation_status"
    )
    episode_stage["details"].pop("knowledge_provenance_source_replay")
    episode_stage["artifacts"] = [
        descriptor
        for descriptor in episode_stage["artifacts"]
        if descriptor.get("content_id")
        not in {operation_content_id, knowledge_content_id}
    ]
    for episode in legacy["episodes"]:
        episode.pop("operation_review_status")
        episode.pop("decision_context_status")
        episode.pop("operation_count")
        episode.pop("operation_review_content_id")
        episode.pop("perspective")
        episode.pop("knowledge_provenance_content_id")
    for replay in _stage(legacy, "source_replay")["details"]["episodes"]:
        replay.pop("operation_review")
        replay.pop("knowledge_provenance")
    legacy["content_id"] = runner_module._receipt_content_id(legacy)

    validation = fixture.runner.validate_receipt(legacy)

    assert validation == {
        "schema_version": (
            "investment_review.review_run_receipt.validation.v1"
        ),
        "validation_status": "accepted",
        "findings": [],
    }

    # Register the stripped shape as a distinct terminal ledger row and prove
    # that the public catalog can still replay an authentic stored v1 receipt.
    legacy["run_id"] = "reviewrun_legacy_v1"
    legacy["run_key"] = "review:legacy-v1"
    legacy["content_id"] = runner_module._receipt_content_id(legacy)
    legacy_path = fixture.artifacts / "legacy_v1_receipt.json"
    legacy_path.write_bytes(runner_module.pretty_json_bytes(legacy))
    fixture.store.save_review_run(
        {
            "run_id": legacy["run_id"],
            "run_key": legacy["run_key"],
            "scope": legacy["scope"],
            "requested_at": "2026-07-14T00:00:01Z",
            "source_cutoff": legacy["cutoffs"]["episode_cutoff"],
            "trigger": "legacy_fixture",
            "parameters": {
                "artifact_root": str(fixture.artifacts),
                "legacy_receipt_schema": (
                    "investment_review.review_run_receipt.v1"
                ),
            },
        }
    )
    fixture.store.append_review_run_status(
        {
            "run_event_id": "runstatus_legacy_v1_terminal",
            "run_id": legacy["run_id"],
            "status": legacy["status"],
            "occurred_at": "2026-07-14T00:00:02Z",
            "known_at": "2026-07-14T00:00:02Z",
            "details": {
                "receipt_path": str(legacy_path),
                "receipt_sha256": _sha256(legacy_path),
                "receipt_content_id": legacy["content_id"],
            },
        }
    )
    catalog = ReviewRunCatalog(
        review_db=fixture.review_db,
        portfolio_db=fixture.source,
        artifact_root=fixture.artifacts,
        repo_root=fixture.root,
    )

    assert catalog.get_receipt(legacy["run_id"]) == legacy
    catalog_items = {
        item["run_id"]: item
        for item in catalog.list_receipts()["runs"]
    }
    assert catalog_items[current["run_id"]]["perspective"] == "user"
    assert catalog_items[legacy["run_id"]]["perspective"] == "legacy"


def test_receipt_validator_rejects_an_unknown_perspective(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    receipt = _run(fixture, dry_run=True)
    tampered = deepcopy(receipt)
    tampered["cutoffs"]["perspective"] = "omniscient"
    tampered["content_id"] = runner_module._receipt_content_id(tampered)

    validation = fixture.runner.validate_receipt(tampered)

    assert validation["validation_status"] == "blocked"
    assert validation["findings"] == ["INVALID_PERSPECTIVE"]


def test_receipt_validator_rejects_rehashed_legal_perspective_swap(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    receipt = _run(fixture, dry_run=True, perspective="user")
    tampered = deepcopy(receipt)
    tampered["cutoffs"]["perspective"] = "system"
    tampered["content_id"] = runner_module._receipt_content_id(tampered)

    validation = fixture.runner.validate_receipt(tampered)

    assert validation["validation_status"] == "blocked"
    assert {
        "EPISODE_STAGE_PERSPECTIVE_BINDING_MISMATCH",
        "RUN_KEY_PERSPECTIVE_BINDING_MISMATCH",
    }.issubset(validation["findings"])


def test_receipt_validator_rejects_perspective_downgrade_with_v3_signals(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    tampered = deepcopy(_run(fixture, dry_run=True))
    tampered["cutoffs"].pop("perspective")
    tampered["content_id"] = runner_module._receipt_content_id(tampered)

    validation = fixture.runner.validate_receipt(tampered)

    assert validation["validation_status"] == "blocked"
    assert "MISSING_PERSPECTIVE" in validation["findings"]


@pytest.mark.parametrize(
    "field",
    ["scope", "mode", "status"],
)
def test_receipt_validator_blocks_unhashable_json_enum_values(
    tmp_path: Path,
    field: str,
) -> None:
    fixture = _fixture(tmp_path)
    tampered = deepcopy(_run(fixture, dry_run=True))
    tampered[field] = []
    tampered["content_id"] = runner_module._receipt_content_id(tampered)

    assert fixture.runner.validate_receipt(tampered)[
        "validation_status"
    ] == "blocked"
