from __future__ import annotations

import json
import socket
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

import pytest

import src.portfolio.investment_review_service as review_service_module
from src.investment_review.market_context_adapter import MarketContextAdapter
from src.investment_review.models import DecisionRecord
from src.investment_review.periodic_reports import PeriodicReportStore
from src.investment_review.review_runner import (
    ReviewRunCatalog,
    ReviewRunnerError,
)
from src.investment_review.store import ReviewStore, ReviewStoreError
from src.portfolio.investment_review_service import (
    InvestmentReviewServiceError,
    InvestmentReviewWebService,
)
from tests.test_investment_review_episode_interpretation import _build
from tests.test_investment_review_review_runner import (
    AS_OF,
    RunnerFixture,
    _closed_episode_rows,
    _fixture,
    _reviewability_fixture,
    _run,
    _trade_row,
)


@dataclass(frozen=True)
class ProductApiFixture:
    runner: RunnerFixture
    receipt: dict[str, Any]
    catalog: Any
    service: InvestmentReviewWebService
    run_id: str
    review_id: str
    episode_id: str
    event_id: str


class _PathBearingSyncStatus:
    """A deliberately path-bearing dependency used to prove sanitization."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def status(self) -> dict[str, Any]:
        return {
            "schema_version": "fixture",
            "status": "healthy",
            "source": {"path": str(self.root / "portfolio.sqlite3")},
            "sidecar": {"path": str(self.root / "review.sqlite3")},
            "counts": {
                "source_seen": 2,
                "sidecar_seen": 2,
                "unsynced": 0,
            },
            "lag": {"unsynced": 0, "source_cutoff_id": "cutoff_fixture"},
            "fees": {"actual": 2, "estimated": 0, "unknown": 0},
            "last_success": {
                "run": {
                    "run_id": "reviewrun_" + "a" * 32,
                    "scope": "sync",
                    "requested_at": "2026-07-24T00:00:00Z",
                    "parameters": {
                        "source_path": str(self.root / "portfolio.sqlite3")
                    },
                },
                "status": "succeeded",
                "status_event": {
                    "occurred_at": "2026-07-24T00:00:01Z",
                    "details": {
                        "receipt_path": str(self.root / "receipt.json")
                    },
                },
            },
            "last_failure": None,
        }


@pytest.fixture
def product_api(tmp_path: Path) -> ProductApiFixture:
    runner = _fixture(tmp_path)
    receipt = _run(runner)
    episode = receipt["episodes"][0]
    catalog = ReviewRunCatalog(
        review_db=runner.review_db,
        portfolio_db=runner.source,
        artifact_root=runner.artifacts,
        repo_root=runner.root,
    )
    service = InvestmentReviewWebService(
        catalog=catalog,
        store=runner.store,
        sync_service=_PathBearingSyncStatus(runner.root),
        revision_root=runner.artifacts / "human_revisions",
        repo_root=runner.root,
    )
    bundle = service.catalog.get_episode_bundle(
        str(receipt["run_id"]),
        str(episode["review_id"]),
        episode_id=str(episode["episode_id"]),
    )
    event_id = str(bundle["episode"]["event_refs"][0]["event_id"])
    return ProductApiFixture(
        runner=runner,
        receipt=receipt,
        catalog=service.catalog,
        service=service,
        run_id=str(receipt["run_id"]),
        review_id=str(episode["review_id"]),
        episode_id=str(episode["episode_id"]),
        event_id=event_id,
    )


def _periodic_api_report() -> dict[str, Any]:
    return {
        "schema_version": "investment_review.periodic_report.v1",
        "report_id": "periodic_" + "a" * 32,
        "status": "ready",
        "subject": {
            "type": "portfolio",
            "id": "default",
            "name": "组合账户",
        },
        "period": {
            "type": "daily",
            "start": "2026-07-15",
            "end": "2026-07-15",
            "report_cutoff_at": "2026-07-15T15:00:00+08:00",
        },
        "generated_at": "2026-07-15T12:00:00Z",
        "headline": "组合日报：因此现有 hold 建议不变。",
        "sections": {
            "performance_and_positions": {
                "performance": {"asset_change_pct": "1"},
                "cash": {"amount_cny": "100"},
                "positions": [],
                "risk_change": {"cash_weight_pct": "10"},
            },
            "decision_context": {
                "framework": "four_layer_periodic_review_v1",
                "report_depth": "daily_delta_only",
                "fundamental_and_valuation": {
                    "status": "missing",
                    "summary": "本期无基本面与估值增量。",
                },
                "market_and_sector": {
                    "status": "missing",
                    "summary": "本期无大盘与板块增量。",
                },
                "technical_and_trend": {
                    "status": "missing",
                    "summary": "本期无技术与趋势增量。",
                },
                "position_and_execution": {
                    "status": "available",
                    "summary": "本期无持仓变动。",
                },
            },
            "operations_and_motives": {
                "operation_count": 0,
                "operations": [],
                "episode_summaries": [],
            },
            "review_judgments": [],
            "recommendation": {
                "type": "analyst_view",
                "action": "hold",
                "target_position": {
                    "target_cash_range_pct": ["5", "10"],
                    "target_position_note": "保持现金缓冲。",
                },
                "time_horizon": "下一交易周",
                "confidence": "low",
                "rationale": [],
                "major_downside_risks": ["样本风险"],
                "invalidation_conditions": ["账本变化"],
                "data_timestamp": "2026-07-15T15:00:00+08:00",
                "report_cutoff_at": "2026-07-15T15:00:00+08:00",
                "important_missing_inputs": ["MISSING_VALUATION"],
                "orders_executed": False,
                "guaranteed_return": False,
            },
            "risks_invalidation_and_missing": {
                "major_risks": ["样本风险"],
                "invalidation_conditions": ["账本变化"],
                "missing_inputs": ["MISSING_VALUATION"],
                "data_limitations": [],
            },
        },
        "source": {
            "source_path": "portfolio.sqlite3",
            "source_sha256": "b" * 64,
            "source_observed_through": "2026-07-15T12:00:00Z",
            "review_sidecar": "investment_review.sqlite3",
            "source_refs": ["portfolio.sqlite3#ledger_entries"],
        },
        "safety": {
            "orders_executed": False,
            "broker_accessed": False,
            "guaranteed_return_claims": False,
            "recommendation_is_not_an_order": True,
        },
        "content_id": "sha256:" + "c" * 64,
    }


def test_periodic_report_api_lists_and_reads_from_the_selected_sidecar(
    product_api: ProductApiFixture,
) -> None:
    store = PeriodicReportStore(product_api.runner.review_db)
    store.initialize()
    report = _periodic_api_report()
    assert store.save(report)["status"] == "inserted"
    weekly_report = deepcopy(report)
    weekly_report["report_id"] = "periodic_" + "d" * 32
    weekly_report["period"] = {
        "type": "weekly",
        "start": "2026-07-13",
        "end": "2026-07-17",
        "report_cutoff_at": "2026-07-17T15:00:00+08:00",
    }
    weekly_report["sections"]["decision_context"]["report_depth"] = (
        "weekly_synthesis"
    )
    weekly_report["sections"]["recommendation"]["data_timestamp"] = (
        "2026-07-17T15:00:00+08:00"
    )
    weekly_report["sections"]["recommendation"]["report_cutoff_at"] = (
        "2026-07-17T15:00:00+08:00"
    )
    weekly_report["content_id"] = "sha256:" + "e" * 64
    assert store.save(weekly_report)["status"] == "inserted"

    listing = product_api.service.list_periodic_reports(
        subject_type="portfolio",
        period_type="daily",
    )
    weekly_listing = product_api.service.list_periodic_reports(
        subject_type="portfolio",
        period_type="weekly",
    )
    full_listing = product_api.service.list_periodic_reports(limit=1000)
    detail = product_api.service.get_periodic_report(report["report_id"])

    assert listing["status"] == "ready"
    assert listing["data"]["total_count"] == 1
    assert listing["data"]["reports"][0]["report_id"] == report["report_id"]
    assert weekly_listing["data"]["reports"][0]["report_id"] == (
        weekly_report["report_id"]
    )
    assert full_listing["data"]["total_count"] == 2
    assert listing["data"]["reports"][0]["recommendation"]["mode"] == (
        "historical_snapshot"
    )
    projected_report = listing["data"]["reports"][0]
    assert projected_report["headline"].startswith(
        "历史建议快照，非当前有效建议。"
    )
    assert "现有 hold 建议不变" not in projected_report["headline"]
    assert projected_report["historical_snapshot"] == {
        "label": "历史建议快照，非当前有效建议",
        "original_headline": "组合日报：因此现有 hold 建议不变。",
        "original_central_judgment": None,
        "stored_report_unchanged": True,
    }
    with pytest.raises(InvestmentReviewServiceError) as captured:
        product_api.service.list_periodic_reports(limit=1001)
    assert captured.value.code == "invalid_limit"
    assert listing["data"]["supported_period_types"] == [
        "daily",
        "weekly",
        "monthly",
    ]
    assert detail["data"]["report"]["sections"]["recommendation"]["mode"] == (
        "historical_snapshot"
    )
    assert "现有 hold 建议不变" not in detail["data"]["report"]["headline"]
    assert store.get(report["report_id"]) == report
    health = product_api.service.get_health()
    assert health["data"]["periodic_reports"]["count"] == 2
    assert health["data"]["periodic_reports"]["supported_period_types"] == [
        "daily",
        "weekly",
        "monthly",
    ]
    assert health["data"]["periodic_reports"]["automation"]["state"] == (
        "never_run"
    )
    assert health["data"]["periodic_reports"]["automation"][
        "os_scheduler_installed"
    ] is False


def _all_strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _all_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _all_strings(item)


def _event_row(fixture: ProductApiFixture, event_id: str | None = None) -> dict[str, Any]:
    selected = event_id or fixture.event_id
    return next(
        item
        for item in fixture.runner.store.list_events(limit=100)
        if item["event_id"] == selected
    )


def _decision_payload(
    fixture: ProductApiFixture,
    *,
    request_id: str = "decision.request.001",
    thesis: str = "Explicit reviewer note.",
    known_at: str | None = None,
) -> dict[str, Any]:
    event = _event_row(fixture)
    return {
        "request_id": request_id,
        "run_id": fixture.run_id,
        "review_id": fixture.review_id,
        "event_id": fixture.event_id,
        "occurred_at": event["occurred_at"],
        "known_at": known_at or event["occurred_at"],
        "thesis": thesis,
        "status": "OPEN",
        "trigger_text": None,
        "invalidation_text": None,
        "expected_horizon": None,
        "portfolio_role": None,
        "direct_reason": None,
        "risk_notes": None,
        "raw_note": None,
    }


def _fee_payload(
    fixture: ProductApiFixture,
    *,
    request_id: str = "fee.request.001",
    amount: object = "2.50",
    supersedes: str | None = None,
    effective_at: str = "2026-07-24T00:00:00Z",
    known_at: str = "2026-07-24T00:00:00Z",
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "run_id": fixture.run_id,
        "review_id": fixture.review_id,
        "event_id": fixture.event_id,
        "status": "actual",
        "amount": amount,
        "currency": "CNY",
        "effective_at": effective_at,
        "known_at": known_at,
        "reviewer_ref": "reviewer:pytest",
        "reason": "Confirmed against a synthetic test statement.",
        "supersedes_correction_id": supersedes,
    }


def test_catalog_get_episode_bundle_is_exactly_run_qualified(
    product_api: ProductApiFixture,
) -> None:
    first = product_api.catalog.get_episode_bundle(
        product_api.run_id,
        product_api.review_id,
        episode_id=product_api.episode_id,
    )
    event = _event_row(product_api)
    decision = replace(
        DecisionRecord.build(
            symbol=event["symbol"],
            market=event["market"],
            occurred_at=event["occurred_at"],
            known_at=event["occurred_at"],
            thesis="A second run must not make the first run ambiguous.",
            timezone="UTC",
        ),
        decision_id="dec_" + "b" * 32,
    )
    product_api.runner.store.add_decision(decision)
    product_api.runner.store.link_decision_event(
        decision.decision_id,
        product_api.event_id,
        "execution",
    )
    second_receipt = _run(product_api.runner)
    second_episode = second_receipt["episodes"][0]

    assert second_episode["review_id"] == product_api.review_id
    assert second_receipt["run_id"] != product_api.run_id
    second = product_api.catalog.get_episode_bundle(
        str(second_receipt["run_id"]),
        product_api.review_id,
        episode_id=product_api.episode_id,
    )
    assert first["receipt"]["run_id"] == product_api.run_id
    assert second["receipt"]["run_id"] == second_receipt["run_id"]
    assert first["review"]["content_id"] != second["review"]["content_id"]

    with pytest.raises(ReviewRunnerError, match="not found"):
        product_api.catalog.get_episode_bundle(
            product_api.run_id,
            "review:" + "f" * 32,
        )


def test_v2_operation_checkpoint_projects_six_axes_and_paired_perspectives(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        *_closed_episode_rows(
            "2026-02-01",
            "2026-02-02",
            "api-v2-flat-baseline",
        ),
        _trade_row(
            event_date="2026-02-02",
            event_type="BUY",
            external_id="api-v2-open",
            event_time="12:00:00",
        ),
    ]
    fixture = _reviewability_fixture(
        tmp_path,
        rows=rows,
        automatic_market_context=True,
    )
    fixture.store.upgrade_reviewability_candidate_v2()
    latest_first_ingest = max(
        datetime.fromisoformat(
            str(item["first_ingest"]["observed_at"]).replace("Z", "+00:00")
        )
        for item in fixture.store.list_event_observation_evidence()
    )
    knowledge_cutoff = (
        latest_first_ingest + timedelta(seconds=1)
    ).isoformat().replace("+00:00", "Z")
    fixture.runner.checkpoint_market_resolver = MarketContextAdapter(
        cache_root=fixture.runner.market_cache_root,
        provider_gateway=None,
        clock=lambda: datetime(2026, 7, 29, 8, 0, tzinfo=timezone.utc),
    )
    source_before = fixture.source.read_bytes()
    user_receipt = fixture.runner.run(
        scope="single",
        as_of=AS_OF,
        knowledge_cutoff=knowledge_cutoff,
        perspective="user",
        dry_run=False,
        trigger="pytest-v2-api",
    )
    system_receipt = fixture.runner.run(
        scope="single",
        as_of=AS_OF,
        knowledge_cutoff=knowledge_cutoff,
        perspective="system",
        dry_run=False,
        trigger="pytest-v2-api",
    )
    assert fixture.source.read_bytes() == source_before

    catalog = ReviewRunCatalog(
        review_db=fixture.review_db,
        portfolio_db=fixture.source,
        artifact_root=fixture.artifacts,
        repo_root=fixture.root,
    )
    service = InvestmentReviewWebService(
        catalog=catalog,
        store=fixture.store,
        revision_root=fixture.artifacts / "human_revisions",
        repo_root=fixture.root,
    )
    socket_calls: list[str] = []

    def forbidden_network(*args: Any, **kwargs: Any) -> None:
        socket_calls.append(repr((args, kwargs)))
        raise AssertionError("validated API projections must remain offline")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(socket.socket, "connect", forbidden_network)
    projections: dict[str, dict[str, Any]] = {}
    for perspective, receipt in (
        ("user", user_receipt),
        ("system", system_receipt),
    ):
        episode = receipt["episodes"][0]
        detail = service.get_review_detail(
            receipt["run_id"],
            episode["review_id"],
        )
        operation_review = detail["data"]["operation_review"]
        projections[perspective] = operation_review
        assert operation_review["available"] is True
        assert operation_review["schema_version"] == (
            "investment_review.operation_checkpoint.v2"
        )
        assert operation_review["perspective"] == perspective
        assert operation_review["actual_user_observation_proven"] is False
        assert set(operation_review["axes"]) == {
            "operation",
            "decision",
            "snapshot_cash_valuation",
            "market",
            "lifecycle",
            "outcome",
        }
        assert operation_review["axes"]["operation"]["status"] == "ready"
        assert operation_review["axes"]["decision"]["status"] == "not_recorded"
        assert operation_review["axes"]["lifecycle"]["status"] == "open"
        assert operation_review["axes"]["outcome"]["status"] == "interim"
        fields = operation_review["axes"]["snapshot_cash_valuation"]["fields"]
        assert fields["position_quantity"]["value"] not in {None, "0"}
        for field in ("industry", "nav", "price", "weight"):
            assert fields[field]["value"] is None
        assert all(
            {
                "code",
                "severity",
                "owner",
                "next_step",
                "source_refs",
            }.issubset(gap)
            for gap in operation_review["gaps"]
        )

        evidence = service.get_evidence(
            receipt["run_id"],
            episode["review_id"],
        )
        assert evidence["data"]["operation_checkpoint"] == operation_review
        listing = service.list_reviews(scope="single")
        listed = next(
            item
            for item in listing["data"]["reviews"]
            if item["run_id"] == receipt["run_id"]
        )
        assert listed["operation_review"]["perspective"] == perspective
        assert listed["operation_review"]["axis_statuses"] == {
            name: operation_review["axes"][name]["status"]
            for name in (
                "operation",
                "decision",
                "snapshot_cash_valuation",
                "market",
                "lifecycle",
                "outcome",
            )
        }
        serialized = json.dumps(
            [detail, evidence, listed],
            ensure_ascii=False,
        )
        assert str(fixture.root) not in serialized

    assert projections["user"]["checkpoint_id"] != (
        projections["system"]["checkpoint_id"]
    )
    forbidden_keys = {
        "motive",
        "psychology",
        "diagnosis",
        "score",
        "recommendation",
        "actually_read",
    }

    def keys(value: object) -> set[str]:
        if isinstance(value, Mapping):
            return {
                str(key).lower()
                for key in value
            } | {
                nested
                for item in value.values()
                for nested in keys(item)
            }
        if isinstance(value, (list, tuple)):
            return {nested for item in value for nested in keys(item)}
        return set()

    assert forbidden_keys.isdisjoint(keys(projections))
    assert socket_calls == []


def test_catalog_rejects_receipt_paths_outside_trusted_root(
    product_api: ProductApiFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = deepcopy(product_api.receipt)
    receipt["episodes"][0]["artifacts"]["context"]["path"] = str(
        tmp_path / "outside.json"
    )
    monkeypatch.setattr(
        product_api.catalog,
        "get_receipt",
        lambda run_id: receipt,
    )

    with pytest.raises(ReviewRunnerError, match="outside the trusted root"):
        product_api.catalog.get_episode_bundle(
            product_api.run_id,
            product_api.review_id,
        )


def test_catalog_rejects_hash_drift(
    product_api: ProductApiFixture,
) -> None:
    review_path = Path(
        product_api.receipt["episodes"][0]["artifacts"]["review"]["path"]
    )
    review_path.write_text('{"tampered":true}\n', encoding="utf-8")

    with pytest.raises(ReviewRunnerError, match="HASH|hash|validation blocked"):
        product_api.catalog.get_episode_bundle(
            product_api.run_id,
            product_api.review_id,
        )


def test_missing_receipt_is_visible_as_a_path_free_failed_run(
    product_api: ProductApiFixture,
) -> None:
    receipt_path = (
        product_api.runner.artifacts
        / product_api.run_id
        / "receipt.json"
    )
    receipt_path.unlink()

    listing = product_api.service.list_reviews()
    assert listing["status"] == "failed"
    assert listing["data"]["count"] == 1
    assert listing["data"]["reviews"][0]["status"] == "failed"
    assert listing["data"]["reviews"][0]["gap_codes"] == [
        "RUN_RECEIPT_INVALID"
    ]
    assert not any(
        str(product_api.runner.root) in value
        for value in _all_strings(listing)
    )

    with pytest.raises(InvestmentReviewServiceError) as captured:
        product_api.service.get_review_detail(
            product_api.run_id,
            product_api.review_id,
        )
    assert captured.value.status == 409
    assert captured.value.code == "review_artifact_invalid"
    assert str(product_api.runner.root) not in str(captured.value)


def test_listing_reuses_validated_receipt_without_second_read(
    product_api: ProductApiFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = product_api.catalog.get_receipt
    calls = 0

    def disappear_after_catalog(run_id: str) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ReviewRunnerError("receipt artifact is missing")
        return original(run_id)

    monkeypatch.setattr(
        product_api.catalog,
        "get_receipt",
        disappear_after_catalog,
    )
    listing = product_api.service.list_reviews()

    assert calls == 1
    assert listing["status"] == "partial"
    assert listing["data"]["count"] == 1


def test_read_models_are_curated_and_health_does_not_leak_paths(
    product_api: ProductApiFixture,
) -> None:
    listing = product_api.service.list_reviews()
    detail = product_api.service.get_review_detail(
        product_api.run_id, product_api.review_id
    )
    timeline = product_api.service.get_timeline(
        product_api.run_id, product_api.review_id
    )
    context = product_api.service.get_context(
        product_api.run_id, product_api.review_id
    )
    evidence = product_api.service.get_evidence(
        product_api.run_id, product_api.review_id
    )
    health = product_api.service.get_health()

    item = next(
        item
        for item in listing["data"]["reviews"]
        if item["review_id"] == product_api.review_id
    )
    assert item["run_id"] == product_api.run_id
    assert item["status"] == "partial"
    assert detail["ref"]["run_id"] == product_api.run_id
    assert detail["ref"]["review_id"] == product_api.review_id
    assert detail["data"]["correction_capability"] == {
        "correctable": False,
        "reason": "facts_only_has_no_interpretation_to_correct",
    }
    assert len(timeline["data"]["events"]) == 2
    assert all("source_refs" not in event for event in timeline["data"]["events"])
    assert context["status"] == "missing"
    assert context["data"]["contexts"]
    assert evidence["data"]["sections"]
    assert evidence["data"]["source_inventory"]
    assert health["status"] == "healthy"
    assert health["data"]["counts"]["unsynced"] == 0
    assert health["data"]["fees"]["actual"] == 2
    assert health["boundary"]["advice"] is True
    assert health["boundary"]["motive_inference"] is True
    assert health["boundary"]["order_execution"] is False
    assert health["boundary"]["broker_write"] is False
    assert health["boundary"]["guaranteed_returns"] is False

    values = list(
        _all_strings(
            [listing, detail, timeline, context, evidence, health]
        )
    )
    protected = {
        str(product_api.runner.root),
        str(product_api.runner.source),
        str(product_api.runner.review_db),
        str(product_api.runner.artifacts),
    }
    assert not any(
        secret in value
        for secret in protected
        for value in values
    )


def test_context_projection_removes_snapshot_local_paths(
    product_api: ProductApiFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = product_api.catalog.get_episode_bundle(
        product_api.run_id,
        product_api.review_id,
    )
    bundle = deepcopy(bundle)
    secret = str(product_api.runner.root / "private" / "snapshot.sqlite3")
    bundle["context"]["contexts"][0]["portfolio_snapshot"]["source_refs"] = [
        {
            "source_id": "snapshot:fixture",
            "content_id": "sha256:" + "1" * 64,
            "path": secret,
            "source_path": secret,
        }
    ]
    bundle["context"]["source_binding"]["database_path"] = secret
    monkeypatch.setattr(
        product_api.catalog,
        "get_episode_bundle",
        lambda run_id, review_id: deepcopy(bundle),
    )

    projected = product_api.service.get_context(
        product_api.run_id,
        product_api.review_id,
    )
    serialized = json.dumps(projected, ensure_ascii=False)
    assert secret not in serialized
    assert '"path"' not in serialized
    assert '"source_path"' not in serialized
    assert '"database_path"' not in serialized
    assert "snapshot:fixture" in serialized


def test_failed_run_is_visible_without_an_episode_or_path_details(
    product_api: ProductApiFixture,
) -> None:
    failed_run_id = "reviewrun_" + "c" * 32
    product_api.runner.store.save_review_run(
        {
            "run_id": failed_run_id,
            "run_key": "review:failed:pytest",
            "scope": "single",
            "requested_at": "2026-07-24T00:00:00Z",
            "source_cutoff": "2026-07-24T00:00:00Z",
            "trigger": "pytest",
            "parameters": {
                "artifact_root": str(product_api.runner.artifacts),
                "portfolio_db": str(product_api.runner.source),
            },
        }
    )
    product_api.runner.store.append_review_run_status(
        {
            "run_event_id": "runstatus_" + "d" * 32,
            "run_id": failed_run_id,
            "status": "failed",
            "occurred_at": "2026-07-24T00:00:01Z",
            "known_at": "2026-07-24T00:00:01Z",
            "details": {
                "receipt_path": str(product_api.runner.root / "secret.json"),
                "error": "synthetic",
            },
        }
    )

    listing = product_api.service.list_reviews()
    failed = next(
        item
        for item in listing["data"]["reviews"]
        if item["run_id"] == failed_run_id
    )
    health = product_api.service.get_health()

    assert failed["review_id"] is None
    assert failed["episode_id"] is None
    assert failed["status"] == "failed"
    assert failed["gap_codes"] == ["RUN_FAILED"]
    assert listing["status"] == "failed"
    # A historical failed attempt stays visible without poisoning current
    # health after a later successful/partial run has completed.
    assert health["status"] == "healthy"
    assert health["data"]["reviews"]["by_status"]["failed"] == 1
    assert (
        health["data"]["reviews"]["last_failure"]["run_id"]
        == failed_run_id
    )
    assert str(product_api.runner.root) not in json.dumps(
        [listing, health], ensure_ascii=False
    )


@pytest.mark.parametrize(
    "status",
    ["lagging", "missing_sidecar", "schema_not_initialized", "invalid_sidecar"],
)
def test_health_preserves_explicit_degraded_status(
    product_api: ProductApiFixture,
    status: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        product_api.service.sync_service,
        "status",
        lambda: {
            "status": status,
            "counts": {"source_seen": 2, "sidecar_seen": 1, "unsynced": 1},
            "lag": {"unsynced": 1},
            "fees": {"actual": 0, "estimated": 0, "unknown": 1},
        },
    )
    health = product_api.service.get_health()
    assert health["status"] == status
    assert health["data"]["status"] == status
    assert health["data"]["lag"]["unsynced"] == 1


def test_create_decision_is_request_idempotent_and_preserves_xss_as_text(
    product_api: ProductApiFixture,
) -> None:
    thesis = '<script>alert("stored-text-only")</script>'
    payload = _decision_payload(product_api, thesis=thesis)

    first = product_api.service.create_decision(payload)
    second = product_api.service.create_decision(payload)

    assert first["data"]["status"] == "INSERTED"
    assert second["data"]["status"] == "SKIPPED"
    assert first["data"]["decision_id"] == second["data"]["decision_id"]
    with product_api.runner.store.connection(read_only=True) as connection:
        rows = connection.execute(
            "SELECT decision_id, thesis FROM decisions ORDER BY decision_id"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["decision_id"] == first["data"]["decision_id"]
    assert rows[0]["thesis"] == thesis

    changed = {**payload, "thesis": "Different content for same request."}
    with pytest.raises(InvestmentReviewServiceError) as captured:
        product_api.service.create_decision(changed)
    assert captured.value.status == 409
    assert captured.value.code == "decision_idempotency_conflict"


def test_create_decision_is_idempotent_under_concurrent_requests(
    product_api: ProductApiFixture,
) -> None:
    payload = _decision_payload(
        product_api,
        request_id="decision.request.concurrent",
    )
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _: product_api.service.create_decision(payload),
                range(8),
            )
        )

    statuses = [item["data"]["status"] for item in results]
    assert statuses.count("INSERTED") == 1
    assert statuses.count("SKIPPED") == 7
    assert len({item["data"]["decision_id"] for item in results}) == 1


def test_retrospective_link_is_explicit_and_execution_backdating_is_rejected(
    product_api: ProductApiFixture,
) -> None:
    event = _event_row(product_api)
    decision = replace(
        DecisionRecord.build(
            symbol=event["symbol"],
            market=event["market"],
            occurred_at=event["occurred_at"],
            known_at="2026-07-24T00:00:00Z",
            thesis="Captured after execution and never presented as prior knowledge.",
            timezone="UTC",
        ),
        decision_id="dec_" + "e" * 32,
    )
    product_api.runner.store.add_decision(decision)
    base = {
        "run_id": product_api.run_id,
        "review_id": product_api.review_id,
        "event_id": product_api.event_id,
        "decision_id": decision.decision_id,
    }

    with pytest.raises(InvestmentReviewServiceError) as captured:
        product_api.service.link_decision({**base, "relation": "execution"})
    assert captured.value.status == 422
    assert captured.value.code == "execution_link_backdating_forbidden"

    linked = product_api.service.link_decision(
        {**base, "relation": "retrospective_context"}
    )
    replay = product_api.service.link_decision(
        {**base, "relation": "retrospective_context"}
    )
    assert linked["data"]["relation"] == "retrospective_context"
    assert replay["data"]["relation"] == "retrospective_context"
    assert linked["data"]["status"] == "LINKED"
    assert replay["data"]["status"] == "SKIPPED"
    assert replay["data"]["link_id"] == linked["data"]["link_id"]
    assert replay["data"]["link_content_id"] == linked["data"]["link_content_id"]
    current = linked["data"]["current_decisions"]
    assert any(
        item["decision_id"] == decision.decision_id
        and item["temporal_role"] == "retrospective_context"
        and item["link"]["link_id"] == linked["data"]["link_id"]
        for item in current
    )
    with product_api.runner.store.connection(read_only=True) as connection:
        count = connection.execute(
            """
            SELECT COUNT(*) FROM decision_event_links
            WHERE decision_id = ? AND event_id = ? AND relation = ?
            """,
            (
                decision.decision_id,
                product_api.event_id,
                "retrospective_context",
            ),
        ).fetchone()[0]
    assert count == 0
    directory = product_api.service._retrospective_directory(  # noqa: SLF001
        product_api.run_id,
        product_api.review_id,
    )
    link_files = list(directory.glob("retrolink_*.json"))
    assert len(link_files) == 1
    link_artifact = json.loads(link_files[0].read_text(encoding="utf-8"))
    assert link_artifact["content_id"] == linked["data"]["link_content_id"]
    assert link_artifact["relation"] == "retrospective_context"

    rerun = _run(product_api.runner)
    assert rerun["status"] == "partial"
    assert rerun["run_key"] == product_api.receipt["run_key"]
    assert rerun["content_id"] == product_api.receipt["content_id"]
    assert not any(
        stage["status"] == "blocked"
        for stage in rerun["stages"]
    )


def test_retrospective_link_rejects_future_known_time(
    product_api: ProductApiFixture,
) -> None:
    event = _event_row(product_api)
    decision = replace(
        DecisionRecord.build(
            symbol=event["symbol"],
            market=event["market"],
            occurred_at=event["occurred_at"],
            known_at="2099-01-01T00:00:00Z",
            thesis="A future-known decision cannot be linked retrospectively.",
            timezone="UTC",
        ),
        decision_id="dec_" + "9" * 32,
    )
    product_api.runner.store.add_decision(decision)

    with pytest.raises(InvestmentReviewServiceError) as captured:
        product_api.service.link_decision(
            {
                "run_id": product_api.run_id,
                "review_id": product_api.review_id,
                "event_id": product_api.event_id,
                "decision_id": decision.decision_id,
                "relation": "retrospective_context",
            }
        )
    assert captured.value.status == 422
    assert captured.value.code == "retrospective_decision_time_invalid"


def test_fee_correction_requires_current_parent_and_replays_idempotently(
    product_api: ProductApiFixture,
) -> None:
    first_payload = _fee_payload(product_api)
    first = product_api.service.correct_fee(first_payload)
    replay = product_api.service.correct_fee(first_payload)

    assert first["data"]["status"] == "INSERTED"
    assert replay["data"]["status"] == "SKIPPED"
    assert replay["data"]["correction_id"] == first["data"]["correction_id"]

    stale = _fee_payload(
        product_api,
        request_id="fee.request.stale",
        effective_at="2026-07-24T00:00:01Z",
        known_at="2026-07-24T00:00:01Z",
    )
    with pytest.raises(InvestmentReviewServiceError) as captured:
        product_api.service.correct_fee(stale)
    assert captured.value.status == 409
    assert captured.value.code == "stale_fee_correction_parent"

    second = product_api.service.correct_fee(
        _fee_payload(
            product_api,
            request_id="fee.request.002",
            amount="3.25",
            supersedes=first["data"]["correction_id"],
            effective_at="2026-07-24T00:00:02Z",
            known_at="2026-07-24T00:00:02Z",
        )
    )
    assert second["data"]["status"] == "INSERTED"
    assert (
        second["data"]["effective_fee"]["supersedes_correction_id"]
        == first["data"]["correction_id"]
    )


def test_facts_only_review_correction_is_an_explicit_conflict(
    product_api: ProductApiFixture,
) -> None:
    detail = product_api.service.get_review_detail(
        product_api.run_id, product_api.review_id
    )
    with pytest.raises(InvestmentReviewServiceError) as captured:
        product_api.service.correct_review(
            {
                "run_id": product_api.run_id,
                "review_id": product_api.review_id,
                "expected_parent_content_id": detail["ref"]["content_id"],
                "request": {},
            }
        )
    assert captured.value.status == 409
    assert captured.value.code == "facts_only_not_correctable"
    assert not (product_api.runner.artifacts / "human_revisions").exists()


def test_interpreted_review_correction_is_append_only_and_windows_path_safe(
    product_api: ProductApiFixture,
) -> None:
    event = _event_row(product_api)
    decision = replace(
        DecisionRecord.build(
            symbol=event["symbol"],
            market=event["market"],
            occurred_at=event["occurred_at"],
            known_at=event["occurred_at"],
            thesis="Synthetic decision for interpreted-review API verification.",
            timezone="UTC",
        ),
        decision_id="dec_" + "6" * 32,
    )
    product_api.runner.store.add_decision(decision)
    product_api.runner.store.link_decision_event(
        decision.decision_id,
        event["event_id"],
        "execution",
    )
    interpreted_receipt = _run(product_api.runner)
    interpreted_episode = interpreted_receipt["episodes"][0]
    run_id = str(interpreted_receipt["run_id"])
    review_id = str(interpreted_episode["review_id"])
    base_bundle = product_api.catalog.get_episode_bundle(
        run_id,
        review_id,
    )
    interpreted_review = _build(base_bundle["review"]).artifact

    class InterpretedCatalog:
        def __init__(self) -> None:
            self.store = product_api.catalog.store
            self.runner = product_api.catalog.runner

        def transform_episode_bundle(
            self,
            bundle: Mapping[str, Any],
        ) -> dict[str, Any]:
            bundle = deepcopy(bundle)
            bundle["review"] = deepcopy(interpreted_review)
            return bundle

    service = InvestmentReviewWebService(
        catalog=InterpretedCatalog(),  # type: ignore[arg-type]
        store=product_api.runner.store,
        revision_root=product_api.runner.artifacts / "human_revisions",
        repo_root=product_api.runner.root,
    )
    target = interpreted_review["interpretation_sections"]["main_tensions"][0]
    replacement_fact = next(
        fact["fact_id"]
        for section in interpreted_review["fact_sections"].values()
        for fact in section["facts"]
        if fact["fact_id"] not in target["fact_refs"]
    )
    parent_content_id = interpreted_review["content_id"]
    result = service.correct_review(
        {
            "run_id": run_id,
            "review_id": review_id,
            "expected_parent_content_id": parent_content_id,
            "request": {
                "schema_version": "p2f.human_review_request.v1",
                "action": "correct",
                "reviewed_at": "2026-07-24T00:00:00Z",
                "actor_ref": "workspace_user",
                "reason": "Synthetic correction for API verification.",
                "target_ids": [target["finding_id"]],
                "corrections": [
                    {
                        "operation": "replace_fact_refs",
                        "target_id": target["finding_id"],
                        "fact_refs": [replacement_fact],
                    }
                ],
            },
        }
    )

    assert result["data"]["status"] == "INSERTED"
    assert result["data"]["revision_no"] == 2
    assert result["data"]["supersedes_content_id"] == parent_content_id
    revision_directory = service._revision_directory(  # noqa: SLF001
        run_id,
        review_id,
    )
    revision_files = list(revision_directory.glob("*.json"))
    assert len(revision_files) == 1
    assert revision_files[0].name == (
        f"r0002_{result['data']['content_id'].removeprefix('sha256:')[:32]}.json"
    )
    detail = service.get_review_detail(
        run_id,
        review_id,
    )
    assert detail["data"]["revision"]["revision_no"] == 2
    assert detail["data"]["revision"]["generation_mode"] == "human_authored"

    with pytest.raises(InvestmentReviewServiceError) as captured:
        service.correct_review(
            {
                "run_id": run_id,
                "review_id": review_id,
                "expected_parent_content_id": parent_content_id,
                "request": {
                    "schema_version": "p2f.human_review_request.v1",
                    "action": "accept",
                    "reviewed_at": "2026-07-24T00:00:01Z",
                    "actor_ref": "workspace_user",
                    "reason": "This request is intentionally stale.",
                    "target_ids": [target["finding_id"]],
                    "corrections": [],
                },
            }
        )
    assert captured.value.status == 409
    assert captured.value.code == "stale_review_parent"


def test_unregistered_revision_json_is_not_silently_ignored(
    product_api: ProductApiFixture,
) -> None:
    directory = product_api.service._revision_directory(  # noqa: SLF001
        product_api.run_id,
        product_api.review_id,
    )
    directory.mkdir(parents=True)
    (directory / "unexpected.json").write_text(
        '{"untrusted":true}\n',
        encoding="utf-8",
    )

    with pytest.raises(InvestmentReviewServiceError) as captured:
        product_api.service.get_review_detail(
            product_api.run_id,
            product_api.review_id,
        )
    assert captured.value.status == 409
    assert captured.value.code == "revision_artifact_invalid"


def test_revision_directory_file_is_not_silently_ignored(
    product_api: ProductApiFixture,
) -> None:
    directory = product_api.service._revision_directory(  # noqa: SLF001
        product_api.run_id,
        product_api.review_id,
    )
    directory.parent.mkdir(parents=True, exist_ok=True)
    directory.write_text("not a directory\n", encoding="utf-8")

    with pytest.raises(InvestmentReviewServiceError) as captured:
        product_api.service.get_review_detail(
            product_api.run_id,
            product_api.review_id,
        )
    assert captured.value.status == 409
    assert captured.value.code == "revision_artifact_invalid"
    assert str(product_api.runner.root) not in str(captured.value)


def test_service_rejects_store_from_a_different_sidecar(
    product_api: ProductApiFixture,
) -> None:
    other_store = ReviewStore(
        product_api.runner.root / "protected_other_sidecar.sqlite3"
    )
    with pytest.raises(InvestmentReviewServiceError) as captured:
        InvestmentReviewWebService(
            catalog=product_api.catalog,
            store=other_store,
            revision_root=product_api.runner.artifacts / "human_revisions",
            repo_root=product_api.runner.root,
        )
    assert captured.value.status == 503
    assert captured.value.code == "review_store_identity_mismatch"
    assert str(product_api.runner.root) not in str(captured.value)


def test_service_identity_gate_preserves_repo_relative_paths(
    product_api: ProductApiFixture,
) -> None:
    root = product_api.runner.root
    service = InvestmentReviewWebService(
        review_db=product_api.runner.review_db.relative_to(root),
        portfolio_db=product_api.runner.source.relative_to(root),
        artifact_root=product_api.runner.artifacts.relative_to(root),
        repo_root=root,
    )
    assert Path(service.store.path).resolve() == (
        product_api.runner.review_db.resolve()
    )
    listing = service.list_reviews()
    assert listing["data"]["count"] == 1


def test_list_reviews_pushes_scope_into_trusted_catalog(
    product_api: ProductApiFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_scopes: list[str | None] = []
    status_scopes: list[str | None] = []

    def list_receipts(
        *,
        scope: str | None = None,
        include_validated_receipt: bool = False,
    ) -> dict[str, object]:
        receipt_scopes.append(scope)
        assert include_validated_receipt is True
        return {"runs": [], "invalid_runs": []}

    def list_run_statuses(*, scope: str | None = None) -> dict[str, object]:
        status_scopes.append(scope)
        return {"runs": []}

    monkeypatch.setattr(product_api.service.catalog, "list_receipts", list_receipts)
    monkeypatch.setattr(
        product_api.service.catalog,
        "list_run_statuses",
        list_run_statuses,
    )

    listing = product_api.service.list_reviews(scope="single")

    assert listing["data"]["count"] == 0
    assert receipt_scopes == ["single"]
    assert status_scopes == ["single"]


def test_revision_path_rejects_link_like_leaf(
    product_api: ProductApiFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = product_api.service._revision_directory(  # noqa: SLF001
        product_api.run_id,
        product_api.review_id,
    )
    real_is_link_like = review_service_module._is_link_like  # noqa: SLF001

    def emulate_junction(path: Path) -> bool:
        return path == directory or real_is_link_like(path)

    monkeypatch.setattr(
        review_service_module,
        "_is_link_like",
        emulate_junction,
    )
    with pytest.raises(InvestmentReviewServiceError) as captured:
        product_api.service.get_review_detail(
            product_api.run_id,
            product_api.review_id,
        )
    assert captured.value.status == 409
    assert captured.value.code == "revision_path_invalid"


@pytest.mark.parametrize(
    ("operation", "expected_code"),
    [
        ("traversal_run", "invalid_run_id"),
        ("traversal_review", "invalid_review_id"),
        ("unexpected_field", "unexpected_field"),
        ("naive_timestamp", "invalid_known_at"),
        ("numeric_fee", "fee_amount_invalid"),
    ],
)
def test_service_rejects_untrusted_ids_unknown_fields_and_noncanonical_values(
    product_api: ProductApiFixture,
    operation: str,
    expected_code: str,
) -> None:
    with pytest.raises(InvestmentReviewServiceError) as captured:
        if operation == "traversal_run":
            product_api.service.get_review_detail(
                "../receipt.json", product_api.review_id
            )
        elif operation == "traversal_review":
            product_api.service.get_review_detail(
                product_api.run_id, "../../review.json"
            )
        elif operation == "unexpected_field":
            product_api.service.create_decision(
                {
                    **_decision_payload(product_api),
                    "artifact_path": "C:\\secret\\review.json",
                }
            )
        elif operation == "naive_timestamp":
            product_api.service.create_decision(
                {
                    **_decision_payload(product_api),
                    "known_at": "2026-07-24 00:00:00",
                }
            )
        else:
            product_api.service.correct_fee(
                _fee_payload(product_api, amount=2.5)
            )
    assert captured.value.status in {400, 422}
    assert captured.value.code == expected_code
