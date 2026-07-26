from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
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
from src.investment_review.models import DecisionRecord
from src.investment_review.review_input_bundle import (
    build_review_input_bundle,
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
