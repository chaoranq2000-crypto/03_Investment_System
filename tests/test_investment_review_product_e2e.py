from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

import src.portfolio.web as web_module
from src.investment_review.ingest import reviewed_mapping_content_sha256
from src.investment_review.review_runner import ReviewRunner
from src.portfolio.investment_review_service import InvestmentReviewWebService
from src.portfolio.store import PortfolioStore
from src.portfolio.web import create_dashboard_server
from tests.test_investment_review_review_runner import (
    RunnerFixture,
    _fixture as build_runner_fixture,
    _run as run_review,
)
from tests.test_portfolio_web import _build_store as build_portfolio_store


@dataclass(frozen=True)
class ProductE2E:
    base_url: str
    runner: RunnerFixture
    receipt: dict[str, Any]
    run_id: str
    review_id: str
    event: dict[str, Any]
    source_sha256: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _json_request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: Mapping[str, Any] | list[Any] | None = None,
    raw: bytes | None = None,
    headers: Mapping[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    body = raw
    request_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = Request(
        base_url + path,
        data=body,
        headers=request_headers,
        method=method,
    )
    try:
        response = urlopen(request, timeout=10)
    except HTTPError as exc:
        response = exc
    with response:
        status = response.status
        response_body = response.read()
    try:
        decoded = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        decoded = {"raw": response_body.decode("utf-8", errors="replace")}
    assert isinstance(decoded, dict)
    return status, decoded


def _review_query(context: ProductE2E) -> str:
    return urlencode(
        {
            "run_id": context.run_id,
            "review_id": context.review_id,
        }
    )


def _data(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    assert isinstance(data, dict)
    return data


@contextmanager
def _running_server(
    store: PortfolioStore,
    *,
    env_file: Path,
    investment_review_service: InvestmentReviewWebService | None = None,
) -> Iterator[str]:
    server = create_dashboard_server(
        store,
        port=0,
        env_file=env_file,
        investment_review_service=investment_review_service,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def _decision_payload(
    context: ProductE2E,
    *,
    request_id: str = "request_e2e_decision_001",
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "run_id": context.run_id,
        "review_id": context.review_id,
        "event_id": context.event["event_id"],
        "occurred_at": "2026-01-06T01:59:00Z",
        "known_at": "2026-07-14T00:00:00Z",
        "thesis": "Synthetic decision note for the local product E2E.",
        "status": "OPEN",
        "raw_note": "Synthetic note; not a reconstructed historical decision.",
    }


@pytest.fixture
def product_e2e(tmp_path: Path) -> ProductE2E:
    runner = build_runner_fixture(tmp_path / "review")
    receipt = run_review(runner)
    assert receipt["status"] == "partial"
    assert len(receipt["episodes"]) == 1
    episode = receipt["episodes"][0]
    event = runner.store.list_events(limit=1)[0]
    source_sha256 = _sha256(runner.source)

    dashboard_root = tmp_path / "dashboard"
    dashboard_root.mkdir()
    portfolio_store = build_portfolio_store(dashboard_root)
    review_service = InvestmentReviewWebService(
        review_db=runner.review_db,
        portfolio_db=runner.source,
        mapping_path=runner.mapping,
        artifact_root=runner.artifacts,
        repo_root=runner.root,
    )
    server = create_dashboard_server(
        portfolio_store,
        port=0,
        investment_review_service=review_service,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    context = ProductE2E(
        base_url=f"http://{host}:{port}",
        runner=runner,
        receipt=receipt,
        run_id=receipt["run_id"],
        review_id=episode["review_id"],
        event=event,
        source_sha256=source_sha256,
    )
    try:
        yield context
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def test_product_get_surfaces_and_legacy_portfolio_endpoint(
    product_e2e: ProductE2E,
) -> None:
    context = product_e2e
    query = _review_query(context)

    status, reviews = _json_request(
        context.base_url, "/api/investment-review/reviews"
    )
    assert status == 200
    review_list = _data(reviews)
    assert review_list["count"] == 1
    assert review_list["reviews"][0]["run_id"] == context.run_id
    assert review_list["reviews"][0]["review_id"] == context.review_id
    assert review_list["reviews"][0]["status"] == "partial"

    payloads: dict[str, dict[str, Any]] = {}
    for surface in ("review", "timeline", "context", "evidence"):
        status, payload = _json_request(
            context.base_url,
            f"/api/investment-review/{surface}?{query}",
        )
        assert status == 200
        assert payload["ref"]["run_id"] == context.run_id
        assert payload["ref"]["review_id"] == context.review_id
        data = _data(payload)
        payloads[surface] = data

    detail = payloads["review"]
    assert detail["summary"]["generation_mode"] == "facts_only"
    assert detail["correction_capability"]["correctable"] is False
    assert detail["revision"]["revision_no"] == 1
    assert payloads["timeline"]["events"]
    assert "snapshot_links" in payloads["timeline"]
    assert payloads["context"]["status"] == "missing"
    assert isinstance(payloads["context"]["contexts"], list)
    assert payloads["evidence"]["sections"]
    assert isinstance(payloads["evidence"]["source_inventory"], list)

    status, health = _json_request(
        context.base_url, "/api/investment-review/health"
    )
    assert status == 200
    health_data = _data(health)
    assert health_data["status"] == "healthy"
    assert health_data["counts"]["unsynced"] == 0
    assert health_data["lag"]["unsynced"] == 0
    assert health_data["reviews"]["count"] == 1

    status, portfolio = _json_request(context.base_url, "/api/portfolio")
    assert status == 200
    assert portfolio["positions"][0]["ts_code"] == "600000.SH"
    assert portfolio["summary"]["market_value"] == "1200"
    assert _sha256(context.runner.source) == context.source_sha256


def test_unexpected_review_errors_are_bounded_and_server_survives(
    product_e2e: ProductE2E,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leaked_path = r"C:\secret\protected_review.sqlite3"

    def fail_health(_self: InvestmentReviewWebService) -> dict[str, Any]:
        raise RuntimeError(leaked_path)

    monkeypatch.setattr(InvestmentReviewWebService, "get_health", fail_health)
    status, failed_get = _json_request(
        product_e2e.base_url,
        "/api/investment-review/health",
    )
    assert status == 503
    assert failed_get["code"] == "investment_review_internal_error"
    assert leaked_path not in json.dumps(failed_get, ensure_ascii=False)

    def fail_decision(
        _self: InvestmentReviewWebService,
        _payload: object,
    ) -> dict[str, Any]:
        raise OSError(leaked_path)

    monkeypatch.setattr(
        InvestmentReviewWebService,
        "create_decision",
        fail_decision,
    )
    status, failed_post = _json_request(
        product_e2e.base_url,
        "/api/investment-review/decision",
        method="POST",
        payload=_decision_payload(
            product_e2e,
            request_id="request_e2e_internal_error",
        ),
        headers={"X-Investment-Review-Action": "decision"},
    )
    assert status == 503
    assert failed_post["code"] == "investment_review_internal_error"
    assert leaked_path not in json.dumps(failed_post, ensure_ascii=False)

    status, portfolio = _json_request(
        product_e2e.base_url,
        "/api/portfolio",
    )
    assert status == 200
    assert portfolio["positions"][0]["ts_code"] == "600000.SH"


def test_standard_web_auto_wires_explicit_existing_sidecar_and_canonical_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = build_runner_fixture(tmp_path / "auto-wired-review")
    canonical_artifacts = (
        fixture.root / ".codex_tmp" / "investment_review_runs"
    )
    runner = ReviewRunner(
        review_db=fixture.review_db,
        portfolio_db=fixture.source,
        mapping_path=fixture.mapping,
        artifact_root=canonical_artifacts,
        repo_root=fixture.root,
    )
    receipt = runner.run(
        scope="single",
        as_of="2026-02-02T23:59:59Z",
        knowledge_cutoff="2026-07-14T00:00:00Z",
        dry_run=False,
        trigger="pytest_auto_wire",
    )
    assert receipt["status"] == "partial"
    assert (canonical_artifacts / receipt["run_id"] / "receipt.json").is_file()

    env_file = tmp_path / "auto-wire.env"
    env_file.write_text(
        f"INVESTMENT_REVIEW_DB={fixture.review_db}\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("INVESTMENT_REVIEW_DB", raising=False)
    monkeypatch.setattr(web_module, "repository_root", lambda: fixture.root)
    source_before = _sha256(fixture.source)
    sidecar_before = _sha256(fixture.review_db)
    portfolio_store = PortfolioStore(fixture.source)

    with _running_server(
        portfolio_store,
        env_file=env_file,
    ) as base_url:
        status, reviews = _json_request(
            base_url,
            "/api/investment-review/reviews",
        )
        assert status == 200
        review_list = _data(reviews)
        assert review_list["count"] == 1
        assert review_list["reviews"][0]["run_id"] == receipt["run_id"]
        assert review_list["reviews"][0]["review_id"] == (
            receipt["episodes"][0]["review_id"]
        )

    assert _sha256(fixture.source) == source_before
    assert _sha256(fixture.review_db) == sidecar_before


def test_standard_web_without_review_configuration_is_failure_isolated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dashboard_root = tmp_path / "unconfigured-dashboard"
    dashboard_root.mkdir()
    portfolio_store = build_portfolio_store(dashboard_root)
    env_file = dashboard_root / "absent.env"
    implicit_sidecar = dashboard_root / "data" / "db" / "investment_review.sqlite3"
    monkeypatch.delenv("INVESTMENT_REVIEW_DB", raising=False)
    assert not env_file.exists()
    assert not implicit_sidecar.exists()

    with _running_server(portfolio_store, env_file=env_file) as base_url:
        status, unavailable = _json_request(
            base_url,
            "/api/investment-review/reviews",
        )
        assert status == 503
        assert unavailable["code"] == "investment_review_unavailable"

        status, portfolio = _json_request(base_url, "/api/portfolio")
        assert status == 200
        assert portfolio["positions"][0]["ts_code"] == "600000.SH"

    assert not implicit_sidecar.exists()


@pytest.mark.parametrize("configuration_kind", ["relative", "missing_absolute"])
def test_invalid_review_configuration_is_bounded_and_portfolio_remains_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configuration_kind: str,
) -> None:
    dashboard_root = tmp_path / configuration_kind
    dashboard_root.mkdir()
    portfolio_store = build_portfolio_store(dashboard_root)
    configured_path = (
        "relative-review.sqlite3"
        if configuration_kind == "relative"
        else str((dashboard_root / "missing-review.sqlite3").resolve())
    )
    env_file = dashboard_root / "review.env"
    env_file.write_text(
        f"INVESTMENT_REVIEW_DB={configured_path}\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("INVESTMENT_REVIEW_DB", raising=False)

    with _running_server(portfolio_store, env_file=env_file) as base_url:
        status, unavailable = _json_request(
            base_url,
            "/api/investment-review/reviews",
        )
        assert status == 503
        assert unavailable == {
            "error": "本地投资复盘配置无效",
            "code": "investment_review_configuration_invalid",
        }
        serialized = json.dumps(unavailable, ensure_ascii=False)
        assert configured_path not in serialized
        assert str(dashboard_root) not in serialized

        status, portfolio = _json_request(base_url, "/api/portfolio")
        assert status == 200
        assert portfolio["positions"][0]["ts_code"] == "600000.SH"


def test_explicit_review_service_takes_priority_over_invalid_environment(
    product_e2e: ProductE2E,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = product_e2e
    invalid_path = (tmp_path / "missing-sidecar.sqlite3").resolve()
    env_file = tmp_path / "invalid-explicit-priority.env"
    env_file.write_text(
        f"INVESTMENT_REVIEW_DB={invalid_path}\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("INVESTMENT_REVIEW_DB", raising=False)
    explicit_service = InvestmentReviewWebService(
        review_db=context.runner.review_db,
        portfolio_db=context.runner.source,
        mapping_path=context.runner.mapping,
        artifact_root=context.runner.artifacts,
        repo_root=context.runner.root,
    )

    with _running_server(
        PortfolioStore(context.runner.source),
        env_file=env_file,
        investment_review_service=explicit_service,
    ) as base_url:
        status, reviews = _json_request(
            base_url,
            "/api/investment-review/reviews",
        )
        assert status == 200
        assert _data(reviews)["reviews"][0]["run_id"] == context.run_id

    assert not invalid_path.exists()


@pytest.mark.parametrize("mapping_state", ["missing", "unreviewed", "stale"])
def test_all_review_endpoints_close_when_mapping_is_unavailable(
    tmp_path: Path,
    mapping_state: str,
) -> None:
    fixture = build_runner_fixture(tmp_path / mapping_state)
    receipt = run_review(fixture)
    assert receipt["episodes"]
    mapping_path = fixture.mapping
    if mapping_state == "missing":
        mapping_path = fixture.root / "config" / "missing-reviewed-mapping.json"
        assert not mapping_path.exists()
    else:
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        if mapping_state == "unreviewed":
            mapping["review"]["status"] = "unreviewed"
        else:
            mapping["generated_from"]["table_schema_sha256"] = "0" * 64
            mapping["review"]["mapping_content_sha256"] = (
                reviewed_mapping_content_sha256(mapping)
            )
        mapping_path.write_text(
            json.dumps(mapping, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    service = InvestmentReviewWebService(
        review_db=fixture.review_db,
        portfolio_db=fixture.source,
        mapping_path=mapping_path,
        artifact_root=fixture.artifacts,
        repo_root=fixture.root,
    )
    env_file = fixture.root / "empty.env"
    env_file.write_text("", encoding="utf-8")
    get_routes = (
        "/api/investment-review/health",
        "/api/investment-review/reviews",
        "/api/investment-review/review",
        "/api/investment-review/timeline",
        "/api/investment-review/context",
        "/api/investment-review/evidence",
        "/api/investment-review/periodic-reports",
        "/api/investment-review/periodic-report",
    )
    post_routes = {
        "/api/investment-review/decision": "decision",
        "/api/investment-review/link": "link",
        "/api/investment-review/fee-correction": "fee-correction",
        "/api/investment-review/review-correction": "review-correction",
    }
    source_before = _sha256(fixture.source)
    sidecar_before = _sha256(fixture.review_db)

    with _running_server(
        PortfolioStore(fixture.source),
        env_file=env_file,
        investment_review_service=service,
    ) as base_url:
        for route in get_routes:
            status, payload = _json_request(base_url, route)
            assert status == 503
            assert payload == {
                "error": "本地投资复盘映射缺失、未审核或来源绑定已失效",
                "code": "investment_review_unavailable",
            }
        for route, action in post_routes.items():
            status, payload = _json_request(
                base_url,
                route,
                method="POST",
                payload={},
                headers={"X-Investment-Review-Action": action},
            )
            assert status == 503
            assert payload == {
                "error": "本地投资复盘映射缺失、未审核或来源绑定已失效",
                "code": "investment_review_unavailable",
            }
    assert _sha256(fixture.source) == source_before
    assert _sha256(fixture.review_db) == sidecar_before


def test_missing_receipt_is_path_free_and_does_not_break_portfolio_api(
    product_e2e: ProductE2E,
) -> None:
    context = product_e2e
    run = context.runner.store.get_review_run(context.run_id)
    receipt_path = Path(run["status_event"]["details"]["receipt_path"])
    assert receipt_path.is_file()
    receipt_path.unlink()

    status, reviews = _json_request(
        context.base_url,
        "/api/investment-review/reviews",
    )
    assert status == 200
    review_list = _data(reviews)
    assert review_list["count"] == 1
    assert review_list["reviews"][0]["run_id"] == context.run_id
    assert review_list["reviews"][0]["status"] == "failed"
    assert "RUN_RECEIPT_INVALID" in review_list["reviews"][0]["gap_codes"]
    serialized = json.dumps(reviews, ensure_ascii=False)
    assert str(receipt_path) not in serialized
    assert str(context.runner.root) not in serialized

    status, portfolio = _json_request(context.base_url, "/api/portfolio")
    assert status == 200
    assert portfolio["positions"][0]["ts_code"] == "600000.SH"


def test_product_decision_link_fee_correction_persist_and_source_is_read_only(
    product_e2e: ProductE2E,
) -> None:
    context = product_e2e
    xss_text = (
        '<img src=x onerror="globalThis.__investmentReviewXss=1">'
        "<script>globalThis.__investmentReviewXss=2</script>"
    )
    decision_payload = {
        **_decision_payload(context),
        "thesis": xss_text,
        "raw_note": xss_text,
    }
    status, decision_result = _json_request(
        context.base_url,
        "/api/investment-review/decision",
        method="POST",
        payload=decision_payload,
        headers={"X-Investment-Review-Action": "decision"},
    )
    assert status == 200
    decision_data = _data(decision_result)
    assert decision_data["status"] == "INSERTED"
    decision_id = decision_data["decision_id"]
    stored_decision = context.runner.store.get_decision(decision_id)
    assert stored_decision["thesis"] == xss_text
    assert stored_decision["raw_note"] == xss_text

    status, link_result = _json_request(
        context.base_url,
        "/api/investment-review/link",
        method="POST",
        payload={
            "run_id": context.run_id,
            "review_id": context.review_id,
            "event_id": context.event["event_id"],
            "decision_id": decision_id,
            "relation": "retrospective_context",
        },
        headers={"X-Investment-Review-Action": "link"},
    )
    assert status == 200
    link_data = _data(link_result)
    assert link_data["decision_id"] == decision_id
    assert link_data["event_id"] == context.event["event_id"]
    assert link_data["status"] == "LINKED"
    assert link_data["link_id"].startswith("retrolink_")
    assert link_data["link_content_id"].startswith("sha256:")
    projection = next(
        item
        for item in context.runner.store.list_episode_projection_inputs()
        if item["event_id"] == context.event["event_id"]
    )
    assert projection["decision_refs"] == []
    link_files = list(
        (context.runner.artifacts / "human_revisions" / "retrospective_links").rglob(
            "retrolink_*.json"
        )
    )
    assert len(link_files) == 1
    assert json.loads(link_files[0].read_text(encoding="utf-8"))["content_id"] == (
        link_data["link_content_id"]
    )
    status, refreshed_detail = _json_request(
        context.base_url,
        f"/api/investment-review/review?{_review_query(context)}",
    )
    assert status == 200
    current_decisions = _data(refreshed_detail)["current_decisions"]
    assert current_decisions[0]["decision_id"] == decision_id
    assert current_decisions[0]["relation"] == "retrospective_context"
    assert current_decisions[0]["thesis"] == xss_text
    assert current_decisions[0]["raw_note"] == xss_text
    assert current_decisions[0]["link"]["link_id"] == link_data["link_id"]

    correction_payload = {
        "request_id": "request_e2e_fee_001",
        "run_id": context.run_id,
        "review_id": context.review_id,
        "event_id": context.event["event_id"],
        "status": "actual",
        "amount": "1.23",
        "currency": "CNY",
        "effective_at": "2026-07-15T00:00:00Z",
        "known_at": "2026-07-15T00:00:00Z",
        "reviewer_ref": "reviewer:e2e",
        "reason": "Synthetic settlement confirmation for product E2E.",
        "supersedes_correction_id": None,
    }
    status, correction_result = _json_request(
        context.base_url,
        "/api/investment-review/fee-correction",
        method="POST",
        payload=correction_payload,
        headers={"X-Investment-Review-Action": "fee-correction"},
    )
    assert status == 200
    correction_data = _data(correction_result)
    assert correction_data["status"] == "INSERTED"
    correction_id = correction_data["correction_id"]
    assert context.runner.store.list_fee_corrections(
        event_id=context.event["event_id"]
    ) == [
        {
            "correction_id": correction_id,
            "event_id": context.event["event_id"],
            "status": "actual",
            "amount": "1.23",
            "currency": "CNY",
            "effective_at": "2026-07-15T00:00:00Z",
            "known_at": "2026-07-15T00:00:00Z",
            "reviewer_ref": "reviewer:e2e",
            "reason": "Synthetic settlement confirmation for product E2E.",
            "supersedes_correction_id": None,
            "provenance": {
                "request_id": correction_payload["request_id"],
                "run_id": context.run_id,
                "review_id": context.review_id,
                "source": "investment_review_web",
            },
        }
    ]
    status, refreshed_timeline = _json_request(
        context.base_url,
        f"/api/investment-review/timeline?{_review_query(context)}",
    )
    assert status == 200
    corrected_event = next(
        item
        for item in _data(refreshed_timeline)["events"]
        if item["event_id"] == context.event["event_id"]
    )
    assert corrected_event["fee"]["correction_id"] == correction_id
    assert corrected_event["fee"]["status"] == "actual"
    assert corrected_event["fee"]["amount"] == "1.23"

    stale_payload = {
        **correction_payload,
        "request_id": "request_e2e_fee_stale",
        "status": "unknown",
        "amount": None,
        "effective_at": "2026-07-15T00:01:00Z",
        "known_at": "2026-07-15T00:01:00Z",
        "reason": "Synthetic stale-parent request.",
        "supersedes_correction_id": "fee_correction_missing_parent",
    }
    status, stale = _json_request(
        context.base_url,
        "/api/investment-review/fee-correction",
        method="POST",
        payload=stale_payload,
        headers={"X-Investment-Review-Action": "fee-correction"},
    )
    assert status == 409
    assert stale["code"] == "stale_fee_correction_parent"
    assert len(
        context.runner.store.list_fee_corrections(
            event_id=context.event["event_id"]
        )
    ) == 1
    assert _sha256(context.runner.source) == context.source_sha256


def test_product_rejects_facts_only_revision_and_unsafe_http_inputs(
    product_e2e: ProductE2E,
) -> None:
    context = product_e2e
    detail_status, detail = _json_request(
        context.base_url,
        f"/api/investment-review/review?{_review_query(context)}",
    )
    assert detail_status == 200
    parent_content_id = _data(detail)["revision"]["content_id"]
    artifacts_before = _artifact_hashes(context.runner.artifacts)
    fake_finding = "finding:" + "0" * 32
    correction = {
        "run_id": context.run_id,
        "review_id": context.review_id,
        "expected_parent_content_id": parent_content_id,
        "request": {
            "schema_version": "p2f.human_review_request.v1",
            "action": "correct",
            "reviewed_at": "2026-07-15T00:00:00Z",
            "actor_ref": "reviewer:e2e",
            "reason": "Synthetic correction request against a facts-only review.",
            "target_ids": [fake_finding],
            "corrections": [
                {
                    "operation": "replace_fact_refs",
                    "target_id": fake_finding,
                    "fact_refs": ["fact:" + "0" * 32],
                }
            ],
        },
    }
    status, blocked = _json_request(
        context.base_url,
        "/api/investment-review/review-correction",
        method="POST",
        payload=correction,
        headers={"X-Investment-Review-Action": "review-correction"},
    )
    assert status == 409
    assert "facts_only" in blocked["error"]
    assert _artifact_hashes(context.runner.artifacts) == artifacts_before

    valid_decision = _decision_payload(
        context, request_id="request_e2e_validation_base"
    )
    status, rejected_host = _json_request(
        context.base_url,
        "/api/investment-review/health",
        headers={"Host": "attacker.example"},
    )
    assert status == 403
    assert rejected_host["code"] == "host_not_allowed"

    status, rejected_rebinding = _json_request(
        context.base_url,
        "/api/investment-review/decision",
        method="POST",
        payload=valid_decision,
        headers={
            "Host": "attacker.example",
            "Origin": "http://attacker.example",
            "X-Investment-Review-Action": "decision",
        },
    )
    assert status == 403
    assert rejected_rebinding["code"] == "host_not_allowed"

    status, _ = _json_request(
        context.base_url,
        "/api/investment-review/decision",
        method="POST",
        payload=valid_decision,
    )
    assert status == 403

    status, _ = _json_request(
        context.base_url,
        "/api/investment-review/decision",
        method="POST",
        raw=json.dumps(valid_decision).encode("utf-8"),
        headers={
            "Content-Type": "text/plain",
            "X-Investment-Review-Action": "decision",
        },
    )
    assert status == 415

    malformed_cases = [
        b"[]",
        b"{",
        (
            b'{"request_id":"duplicate-a","request_id":"duplicate-b",'
            b'"run_id":"reviewrun_00000000000000000000000000000000"}'
        ),
    ]
    for raw in malformed_cases:
        status, _ = _json_request(
            context.base_url,
            "/api/investment-review/decision",
            method="POST",
            raw=raw,
            headers={
                "Content-Type": "application/json",
                "X-Investment-Review-Action": "decision",
            },
        )
        assert status in {400, 422}

    status, _ = _json_request(
        context.base_url,
        "/api/investment-review/decision",
        method="POST",
        payload={**valid_decision, "source_path": "../../portfolio.sqlite3"},
        headers={"X-Investment-Review-Action": "decision"},
    )
    assert status in {400, 422}

    status, _ = _json_request(
        context.base_url,
        "/api/investment-review/decision",
        method="POST",
        payload={
            **valid_decision,
            "request_id": "request_e2e_oversize",
            "thesis": "x" * 70000,
        },
        headers={"X-Investment-Review-Action": "decision"},
    )
    assert status == 413

    invalid_queries = [
        urlencode(
            {
                "run_id": "../../outside",
                "review_id": context.review_id,
            }
        ),
        urlencode(
            {
                "run_id": context.run_id,
                "review_id": "..\\..\\outside",
            }
        ),
        (
            f"run_id={context.run_id}&run_id=reviewrun_{'0' * 32}"
            f"&review_id={context.review_id}"
        ),
    ]
    for query in invalid_queries:
        status, _ = _json_request(
            context.base_url,
            f"/api/investment-review/review?{query}",
        )
        assert status in {400, 404}

    status, _ = _json_request(
        context.base_url,
        "/api/investment-review/%2e%2e/%2e%2e/portfolio.sqlite3",
    )
    assert status == 404
    assert _artifact_hashes(context.runner.artifacts) == artifacts_before
    assert _sha256(context.runner.source) == context.source_sha256
