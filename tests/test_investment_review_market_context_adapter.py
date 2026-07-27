from __future__ import annotations

from datetime import datetime, timezone
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any

import pytest

from src.investment_review.artifact_io import canonical_json_bytes
from src.investment_review.market_context_adapter import (
    MARKET_CONTEXT_MANIFEST_VERSION,
    MARKET_GATEWAY_CONTRACT_VERSION,
    MARKET_LIMITS,
    MARKET_RATE_LIMIT_POLICY_VERSION,
    MarketContextAdapter,
    MarketContextCutoffUnavailableError,
    MarketContextError,
    MarketRequestBudget,
    MarketRequestBudgetExhaustedError,
    MARKET_CONTEXT_RESOLUTION_VERSION_V2,
    MARKET_CONTEXT_SOURCE_VERSION_V2,
    MARKET_EXCHANGE_PUBLICATION_RULE_VERSION,
    MARKET_FALLBACK_POLICY_VERSION_V2,
    PUBLIC_INFORMATION_POLICY_VERSION,
    _canonical_component_source_v2,
    _canonical_fallback_v2,
    _canonical_receipt_v2,
    _assemble_resolution_v2,
    _coverage_v2,
    _frozen_source_refs_v2,
    _market_axis_v2,
    _market_gaps_v2,
    _not_needed_fallback_v2,
    _perspective_eligibility_v2,
    _provider_information_candidate_v2,
    _provider_publication_source_ref_v2,
    _resolve_external_revision_conflicts_v2,
    build_market_cache_requirement_v2,
    canonical_provider_request,
    market_row_content_sha256_v2,
    load_market_context_resolution,
    market_context_resolution_path,
    offline_market_context_for_consumer,
    replay_validate_market_context_resolution,
    resolve_market_context,
    resolve_market_context_v2,
    validate_market_context_resolution,
    validate_market_context_resolution_v2,
    validate_market_context_supplemental_sources,
)
from src.investment_review.models import (
    ModelValidationError,
    _canonical_market_axis_v2,
    _canonical_market_fallback_v2,
)
from src.investment_review.store import ReviewStore


AS_OF = "2026-07-17T05:55:28Z"
CUTOFF = "2026-07-18T00:00:00Z"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _portfolio_db(
    tmp_path: Path,
    *,
    with_close: bool = True,
    close_date: str = "2026-07-16",
    close_value: str = "3.929",
    with_instrument: bool = True,
    with_industry: bool = True,
    with_optional_rows: bool = False,
    close_fetched_at: str = "2026-07-17T07:36:48Z",
    instrument_updated_at: str = "2026-07-17T07:34:46Z",
) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "portfolio.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE instruments (
            ts_code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            exchange TEXT NOT NULL,
            currency TEXT NOT NULL,
            industry_name TEXT NOT NULL DEFAULT '',
            industry_source TEXT NOT NULL DEFAULT '',
            industry_updated_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );
        CREATE TABLE close_prices (
            observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            close TEXT NOT NULL,
            pre_close TEXT NOT NULL DEFAULT '',
            pct_chg TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );
        CREATE TABLE daily_bar_observations (
            observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_code TEXT NOT NULL, trade_date TEXT NOT NULL,
            open_price TEXT NOT NULL, high_price TEXT NOT NULL,
            low_price TEXT NOT NULL, close_price TEXT NOT NULL,
            volume_lots TEXT NOT NULL, amount_k_cny TEXT NOT NULL,
            source TEXT NOT NULL, refresh_batch_id TEXT NOT NULL,
            dedupe_key TEXT NOT NULL, fetched_at TEXT NOT NULL
        );
        CREATE TABLE adjustment_factor_observations (
            observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_code TEXT NOT NULL, trade_date TEXT NOT NULL,
            adj_factor TEXT NOT NULL, source TEXT NOT NULL,
            refresh_batch_id TEXT NOT NULL, dedupe_key TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );
        CREATE TABLE minute_bar_observations (
            observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_code TEXT NOT NULL, bar_time TEXT NOT NULL,
            frequency_minutes INTEGER NOT NULL, open_price TEXT NOT NULL,
            high_price TEXT NOT NULL, low_price TEXT NOT NULL,
            close_price TEXT NOT NULL, volume_shares TEXT NOT NULL,
            amount_cny TEXT NOT NULL, source TEXT NOT NULL,
            refresh_batch_id TEXT NOT NULL, dedupe_key TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );
        """
    )
    if with_instrument:
        connection.execute(
            """INSERT INTO instruments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "588200.SH",
                "科创芯片ETF",
                "etf",
                "SH",
                "CNY",
                "电子" if with_industry else "",
                "reviewed.current" if with_industry else "",
                "2026-07-17T07:51:58Z" if with_industry else "",
                instrument_updated_at,
            ),
        )
    if with_close:
        connection.execute(
            """INSERT INTO close_prices(
                ts_code, trade_date, close, pre_close, pct_chg, source, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                "588200.SH",
                close_date,
                close_value,
                "4.14",
                "-5.1",
                "tushare.fund_daily",
                close_fetched_at,
            ),
        )
    if with_optional_rows:
        connection.execute(
            """
            INSERT INTO daily_bar_observations(
                ts_code, trade_date, open_price, high_price, low_price,
                close_price, volume_lots, amount_k_cny, source,
                refresh_batch_id, dedupe_key, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "588200.SH",
                "2026-07-16",
                "4.10",
                "4.12",
                "3.90",
                "3.929",
                "100",
                "200",
                "tushare.fund_daily",
                "fixture",
                "daily-fixture",
                "2026-07-17T07:40:00Z",
            ),
        )
        connection.execute(
            """
            INSERT INTO minute_bar_observations(
                ts_code, bar_time, frequency_minutes, open_price,
                high_price, low_price, close_price, volume_shares,
                amount_cny, source, refresh_batch_id, dedupe_key,
                fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "588200.SH",
                "2026-07-17 13:30:00",
                1,
                "4.01",
                "4.02",
                "4.00",
                "4.01",
                "1000",
                "4010",
                "tushare.etf_mins",
                "fixture",
                "minute-fixture",
                "2026-07-17T05:35:00Z",
            ),
        )
        connection.execute(
            """
            INSERT INTO adjustment_factor_observations(
                ts_code, trade_date, adj_factor, source,
                refresh_batch_id, dedupe_key, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "588200.SH",
                "2026-07-16",
                "1.0",
                "tushare.fund_adj",
                "fixture",
                "factor-fixture",
                "2026-07-17T07:41:00Z",
            ),
        )
    connection.commit()
    assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    connection.close()
    return path


def _review_db(tmp_path: Path) -> Path:
    path = (
        tmp_path
        / "repo"
        / "data"
        / "db"
        / "investment_review_reviewability_v3.sqlite3"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        ReviewStore(path).initialize_reviewability_candidate()
    return path


def _cache_root(tmp_path: Path, *parts: str) -> Path:
    return (
        tmp_path
        / "repo"
        / ".codex_tmp"
        / "investment_review_product_completion_v3"
        / "market_cache"
        / Path(*parts)
    )


def _resolve(
    tmp_path: Path,
    source: Path,
    *,
    gateway: Any | None = None,
    clock=None,
    **kwargs: Any,
) -> dict[str, Any]:
    return resolve_market_context(
        portfolio_db=source,
        review_db=_review_db(tmp_path),
        instrument_id="588200.SH",
        as_of=AS_OF,
        knowledge_cutoff=CUTOFF,
        cache_root=_cache_root(tmp_path),
        provider_gateway=gateway,
        clock=clock,
        **kwargs,
    )


class FakeGateway:
    transport_scheme = "https"
    market_gateway_contract_version = MARKET_GATEWAY_CONTRACT_VERSION
    rate_limit_policy_version = MARKET_RATE_LIMIT_POLICY_VERSION
    enforces_provider_rate_limit = True
    enforces_timeout_cap = True
    enforces_retry_cap = True
    enforces_concurrency_cap = True

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def fetch(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return json.loads(json.dumps(self.response))


def _sequence_clock(*values: datetime):
    remaining = iter(values)
    last = values[-1]

    def read() -> datetime:
        nonlocal last
        try:
            last = next(remaining)
        except StopIteration:
            pass
        return last

    return read


def _success_response(close: str = "3.929") -> dict[str, Any]:
    return {
        "response_status": "succeeded",
        "attempt_count": 1,
        "started_at": "2026-07-17T08:00:00Z",
        "fetched_at": "2026-07-17T08:00:01Z",
        "completed_at": "2026-07-17T08:00:02Z",
        "raw_payload": "redacted-provider-response",
        "rows": [
            {
                "ts_code": "588200.SH",
                "trade_date": "2026-07-16",
                "close": close,
                "pre_close": "4.14",
                "pct_chg": "-5.1",
            }
        ],
    }


def _resolve_v2(
    tmp_path: Path,
    source: Path,
    *,
    perspective: str = "user",
    operation_anchor_at: str = AS_OF,
    gateway: Any | None = None,
    clock=None,
    request_budget: MarketRequestBudget | None = None,
    required_components: tuple[str, ...] = ("prior_close",),
    optional_components: tuple[str, ...] | None = None,
    provider_requests: tuple[dict[str, Any], ...] | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if optional_components is not None:
        kwargs["optional_components"] = optional_components
    if provider_requests is not None:
        kwargs["provider_requests"] = provider_requests
    return resolve_market_context_v2(
        portfolio_db=source,
        review_db=_review_db(tmp_path),
        instrument_id="588200.SH",
        perspective=perspective,
        operation_anchor_event_id="event-anchor",
        operation_anchor_at=operation_anchor_at,
        operation_anchor_ordering_key=[
            operation_anchor_at,
            0,
            "fixture-sequence",
            "event-anchor",
        ],
        as_of=AS_OF,
        knowledge_cutoff=CUTOFF,
        cache_root=_cache_root(tmp_path),
        provider_gateway=gateway,
        clock=clock,
        request_budget=request_budget,
        required_components=required_components,
        **kwargs,
    )


def _verified_v2_response(
    *,
    close: str = "3.929",
    publicly_available_at: str | None = "2026-07-16T07:00:00Z",
    publication_date: str | None = None,
    publication_timezone: str | None = None,
    publication_status: str = "verified",
    publication_basis: str = "official_release_metadata.v1",
    revision_ref: str | None = "provider-revision-20260716",
    public_time_source_ref: str | None = "AUTO",
    content_sha256: str | None = None,
    fetched_at: str = "2026-07-20T00:00:02Z",
    provider_id: str = "tushare",
    endpoint_id: str = "daily",
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "ts_code": "588200.SH",
        "trade_date": "2026-07-16",
        "close": close,
        "pre_close": "4.14",
        "pct_chg": "-5.1",
        "publication_status": publication_status,
        "publication_basis": publication_basis,
    }
    if publicly_available_at is not None:
        row["publicly_available_at"] = publicly_available_at
    if publication_date is not None:
        row["publication_date"] = publication_date
    if publication_timezone is not None:
        row["publication_timezone"] = publication_timezone
    if revision_ref is not None:
        row["revision_ref"] = revision_ref
    row["content_sha256"] = content_sha256 or market_row_content_sha256_v2(
        component="prior_close",
        instrument_id="588200.SH",
        row=row,
    )
    if public_time_source_ref == "AUTO" and revision_ref is not None:
        candidate_information = _provider_information_candidate_v2(
            normalized=row,
            revision_ref=revision_ref,
            fetched_at=fetched_at,
        )
        if candidate_information["status"] == "verified":
            row["public_time_source_ref"] = _provider_publication_source_ref_v2(
                provider_id=provider_id,
                endpoint_id=endpoint_id,
                publication_basis=publication_basis,
                revision_ref=revision_ref,
                content_sha256=row["content_sha256"],
                information_time=candidate_information,
            )
    elif public_time_source_ref not in {None, "AUTO"}:
        row["public_time_source_ref"] = public_time_source_ref
    return {
        "response_status": "succeeded",
        "attempt_count": 1,
        "fetched_at": fetched_at,
        "raw_payload": "redacted-provider-response-v2",
        "rows": [row],
    }


def _late_v2_clock():
    return _sequence_clock(
        datetime(2026, 7, 20, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 7, 20, 0, 0, 1, tzinfo=timezone.utc),
        datetime(2026, 7, 20, 0, 0, 3, tzinfo=timezone.utc),
    )


def _prior_close_provider_request(endpoint_id: str) -> dict[str, Any]:
    return {
        "component": "prior_close",
        "provider_id": "tushare",
        "endpoint_id": endpoint_id,
        "provider_version": "repository_configured_gateway.v1",
        "parameters": {
            "ts_code": "588200.SH",
            "start_date": "20260716",
            "end_date": "20260716",
            "fields": "ts_code,trade_date,close,pre_close,pct_chg",
        },
    }


def _instrument_provider_request() -> dict[str, Any]:
    return {
        "component": "instrument",
        "provider_id": "tushare",
        "endpoint_id": "etf_basic",
        "provider_version": "repository_configured_gateway.v1",
        "parameters": {
            "ts_code": "588200.SH",
            "fields": "ts_code,name,asset_type,exchange,currency",
        },
    }


def _instrument_v2_response(
    *,
    publicly_available_at: str | None = "2026-07-16T07:00:00Z",
    publication_date: str | None = None,
    publication_timezone: str | None = None,
    publication_status: str = "verified",
    publication_basis: str = "official_release_metadata.v1",
    revision_ref: str = "instrument-rev-1",
    fetched_at: str = "2026-07-20T00:00:02Z",
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "ts_code": "588200.SH",
        "name": "科创ETF",
        "asset_type": "etf",
        "exchange": "SSE",
        "currency": "CNY",
        "publication_status": publication_status,
        "publication_basis": publication_basis,
        "revision_ref": revision_ref,
    }
    if publicly_available_at is not None:
        row["publicly_available_at"] = publicly_available_at
    if publication_date is not None:
        row["publication_date"] = publication_date
    if publication_timezone is not None:
        row["publication_timezone"] = publication_timezone
    row["content_sha256"] = market_row_content_sha256_v2(
        component="instrument",
        instrument_id="588200.SH",
        row=row,
    )
    information = _provider_information_candidate_v2(
        normalized=row,
        revision_ref=revision_ref,
        fetched_at=fetched_at,
    )
    if information["status"] == "verified":
        row["public_time_source_ref"] = _provider_publication_source_ref_v2(
            provider_id="tushare",
            endpoint_id="etf_basic",
            publication_basis=publication_basis,
            revision_ref=revision_ref,
            content_sha256=row["content_sha256"],
            information_time=information,
        )
    return {
        "response_status": "succeeded",
        "attempt_count": 1,
        "fetched_at": fetched_at,
        "raw_payload": "redacted-instrument-response-v2",
        "rows": [row],
    }


def test_local_prior_close_and_identity_satisfy_without_gateway(tmp_path: Path) -> None:
    source = _portfolio_db(tmp_path)
    before = _sha256(source)
    gateway = FakeGateway(_success_response("9.999"))

    result = _resolve(tmp_path, source, gateway=gateway)

    assert gateway.calls == []
    assert _sha256(source) == before
    assert not Path(str(source) + "-wal").exists()
    assert not Path(str(source) + "-shm").exists()
    assert result["resolution"]["source_read"] == {
        **result["resolution"]["source_read"],
        "mode": "ro",
        "immutable": True,
        "query_only": True,
        "quick_check": "ok",
    }
    assert result["resolution"]["coverage_before"]["status"] == "satisfied"
    assert result["market_fallback"]["status"] == "not_needed"
    assert result["market_fallback"]["request_count"] == 0
    assert result["market_fallback"]["fetch_receipts"] == []
    assert result["market_axis"]["status"] == "available"
    assert result["market_axis"]["temporal_role"] == "reconstructed_public_context"
    close_sources = [
        source
        for source in result["supplemental_sources"]
        if source["payload"].get("component") == "prior_close"
    ]
    assert any(source["payload"]["values"]["close"] == "3.929" for source in close_sources)
    industry = next(
        source
        for source in result["supplemental_sources"]
        if source["payload"].get("component") == "current_industry"
    )
    assert industry["payload"]["point_in_time"] is False
    assert industry["payload"]["values"]["historical_use"] == "forbidden"
    assert "CURRENT_INDUSTRY_NOT_POINT_IN_TIME" in {
        gap["code"] for gap in result["market_gaps"]
    }
    assert validate_market_context_resolution(result["resolution"])["validation_status"] == "accepted"
    assert replay_validate_market_context_resolution(result["resolution"])["source_verification"] == "verified"


def test_local_daily_minute_and_factor_rows_enter_the_frozen_source_set(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path, with_optional_rows=True)

    result = _resolve(tmp_path, source)

    components = {
        source["payload"].get("component")
        for source in result["supplemental_sources"]
        if source.get("payload", {}).get("schema_version")
        != MARKET_CONTEXT_MANIFEST_VERSION
    }
    assert {
        "prior_close",
        "daily",
        "minute",
        "factor",
        "instrument",
        "current_industry",
    }.issubset(components)
    for component in ("daily", "minute", "factor"):
        assert result["resolution"]["coverage_after"]["components"][
            component
        ]["status"] == "satisfied"
    assert result["market_fallback"]["request_count"] == 0
    assert replay_validate_market_context_resolution(
        result["resolution"]
    )["source_verification"] == "verified"


def test_missing_local_coverage_calls_https_gateway_with_frozen_caps_once_and_reuses(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path, with_close=False, with_industry=False)
    gateway = FakeGateway(_success_response())
    clock = _sequence_clock(
        datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
        datetime(2026, 7, 17, 8, 0, 2, tzinfo=timezone.utc),
    )

    first = _resolve(tmp_path, source, gateway=gateway, clock=clock)

    assert len(gateway.calls) == 1
    call = gateway.calls[0]
    assert call["timeout_seconds"] == 20
    assert call["max_retries"] == 2
    assert call["max_concurrency"] == 2
    assert call["max_requests_per_run"] == 20
    assert first["resolution"]["coverage_before"]["status"] == "insufficient"
    assert first["resolution"]["coverage_after"]["status"] == "satisfied"
    assert first["market_fallback"]["status"] == "succeeded"
    assert first["market_fallback"]["request_count"] == 1
    assert first["market_axis"]["status"] == "available"
    receipt = first["market_fallback"]["fetch_receipts"][0]
    assert receipt["attempt_count"] == 1
    assert receipt["cache_entry_refs"]
    assert receipt["raw_content_sha256"].startswith("sha256:")
    assert receipt["normalized_content_sha256"].startswith("sha256:")
    assert receipt["cache_lineage"] == [first["market_requirement_id"]]

    second_gateway = FakeGateway(_success_response("8.888"))
    second = _resolve(tmp_path, source, gateway=second_gateway, clock=clock)
    assert second_gateway.calls == []
    assert second == first
    resolution_path = market_context_resolution_path(
        _cache_root(tmp_path), first["market_requirement_id"]
    )
    assert load_market_context_resolution(resolution_path) == first["resolution"]


def test_new_requirement_reuses_cutoff_safe_v3_entry_without_another_call(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(
        tmp_path, with_close=False, with_industry=False
    )
    first_gateway = FakeGateway(_success_response())
    first = _resolve(
        tmp_path,
        source,
        gateway=first_gateway,
        clock=_sequence_clock(
            datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 17, 8, 0, 2, tzinfo=timezone.utc),
        ),
    )
    second_gateway = FakeGateway(_success_response("8.888"))

    second = resolve_market_context(
        portfolio_db=source,
        review_db=_review_db(tmp_path),
        instrument_id="588200.SH",
        as_of="2026-07-17T06:00:00Z",
        knowledge_cutoff=CUTOFF,
        cache_root=_cache_root(tmp_path),
        provider_gateway=second_gateway,
        clock=_sequence_clock(
            datetime(2026, 7, 17, 8, 1, tzinfo=timezone.utc),
            datetime(2026, 7, 17, 8, 1, 2, tzinfo=timezone.utc),
        ),
    )

    assert len(first_gateway.calls) == 1
    assert second_gateway.calls == []
    assert first["market_requirement_id"] != second[
        "market_requirement_id"
    ]
    assert second["market_fallback"]["status"] == "not_needed"
    cached_price = next(
        item
        for item in second["supplemental_sources"]
        if item.get("payload", {}).get("component") == "prior_close"
    )
    assert cached_price["payload"]["origin"] == "external_provider_cache"
    assert cached_price["payload"]["cache_lineage"] == sorted(
        [
            first["market_requirement_id"],
            second["market_requirement_id"],
        ]
    )
    first_cached_price = next(
        item
        for item in first["supplemental_sources"]
        if item.get("payload", {}).get("component") == "prior_close"
    )
    assert cached_price["source_id"] != cached_price["payload"][
        "cache_entry_ref"
    ]
    assert cached_price["payload"]["cache_entry_ref"] == (
        first_cached_price["payload"]["cache_entry_ref"]
    )
    assert cached_price["payload"]["origin_fetch_receipt"] == (
        first["market_fallback"]["fetch_receipts"][0]
    )
    assert cached_price["payload"]["origin_requirement_id"] == first[
        "market_requirement_id"
    ]
    assert cached_price["payload"]["projection_requirement_id"] == second[
        "market_requirement_id"
    ]


def test_provider_failure_degrades_market_and_preserves_receipt(tmp_path: Path) -> None:
    source = _portfolio_db(tmp_path, with_close=False, with_industry=False)
    gateway = FakeGateway(
        {
            "response_status": "timeout",
            "attempt_count": 3,
            "started_at": "2026-07-17T08:00:00Z",
            "completed_at": "2026-07-17T08:00:10Z",
            "fetched_at": None,
            "rows": [],
        }
    )
    result = _resolve(
        tmp_path,
        source,
        gateway=gateway,
        clock=_sequence_clock(
            datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 17, 8, 0, 10, tzinfo=timezone.utc),
        ),
    )

    assert result["market_fallback"]["status"] == "failed"
    assert result["market_fallback"]["request_count"] == 3
    assert result["market_axis"]["status"] == "partial"
    assert result["resolution"]["coverage_after"]["status"] == "insufficient"
    assert validate_market_context_resolution(result["resolution"])["validation_status"] == "accepted"
    assert not list((_cache_root(tmp_path) / "e").glob("*.json"))


def test_fully_missing_and_stale_coverage_each_trigger_only_the_controlled_gateway(
    tmp_path: Path,
) -> None:
    missing_root = tmp_path / "missing"
    missing_root.mkdir()
    missing_source = _portfolio_db(
        missing_root, with_close=False, with_instrument=False
    )
    missing_gateway = FakeGateway(_success_response())
    missing = _resolve(
        missing_root,
        missing_source,
        gateway=missing_gateway,
        clock=_sequence_clock(
            datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 17, 8, 0, 2, tzinfo=timezone.utc),
        ),
    )
    assert missing["resolution"]["coverage_before"]["status"] == "missing"
    assert len(missing_gateway.calls) == 1
    assert missing["market_fallback"]["status"] == "succeeded"
    assert missing["resolution"]["coverage_after"]["status"] == "insufficient"

    stale_root = tmp_path / "stale"
    stale_root.mkdir()
    stale_source = _portfolio_db(
        stale_root, close_date="2026-06-01", with_industry=False
    )
    stale_gateway = FakeGateway(_success_response())
    stale = _resolve(
        stale_root,
        stale_source,
        gateway=stale_gateway,
        clock=_sequence_clock(
            datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 17, 8, 0, 2, tzinfo=timezone.utc),
        ),
    )
    assert stale["resolution"]["coverage_before"]["status"] == "stale"
    assert len(stale_gateway.calls) == 1
    assert stale["resolution"]["coverage_after"]["status"] == "satisfied"
    assert stale["market_fallback"]["status"] == "succeeded"


@pytest.mark.parametrize("bad_close", ["", "NaN", "abc", "0", "-1"])
def test_invalid_required_close_is_insufficient_and_triggers_controlled_gateway(
    tmp_path: Path,
    bad_close: str,
) -> None:
    source = _portfolio_db(
        tmp_path,
        close_value=bad_close,
        with_industry=False,
    )
    gateway = FakeGateway(_success_response())

    result = _resolve(
        tmp_path,
        source,
        gateway=gateway,
        clock=_sequence_clock(
            datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 17, 8, 0, 2, tzinfo=timezone.utc),
        ),
    )

    assert result["resolution"]["coverage_before"]["status"] == (
        "insufficient"
    )
    assert result["resolution"]["coverage_before"]["components"][
        "prior_close"
    ]["reason_codes"] == ["SOURCE_REQUIRED_VALUES_MISSING"]
    assert len(gateway.calls) == 1
    assert result["resolution"]["coverage_after"]["status"] == "satisfied"


def test_current_industry_never_claims_historical_system_known_role(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path)
    result = resolve_market_context(
        portfolio_db=source,
        review_db=_review_db(tmp_path),
        instrument_id="588200.SH",
        as_of="2026-07-18T00:00:00Z",
        knowledge_cutoff="2026-07-18T00:00:00Z",
        cache_root=_cache_root(tmp_path),
    )

    industry = next(
        source
        for source in result["supplemental_sources"]
        if source.get("payload", {}).get("component")
        == "current_industry"
    )
    assert industry["payload"]["system_observed_at"] < result["as_of"]
    assert industry["payload"]["temporal_role"] == (
        "reconstructed_public_context"
    )
    assert industry["payload"]["point_in_time"] is False
    assert result["market_axis"]["temporal_role"] == (
        "reconstructed_public_context"
    )


def test_late_fallback_clock_is_rejected_instead_of_backdating_receipt(tmp_path: Path) -> None:
    source = _portfolio_db(tmp_path, with_close=False)
    with pytest.raises(
        MarketContextCutoffUnavailableError, match="cannot be fabricated"
    ):
        _resolve(
            tmp_path,
            source,
            clock=lambda: datetime(2026, 7, 19, tzinfo=timezone.utc),
        )


def test_invalid_success_receipt_is_rejected_before_any_cache_entry_write(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path, with_close=False, with_industry=False)
    response = _success_response()
    response["fetched_at"] = "2026-07-17T09:00:00Z"
    gateway = FakeGateway(response)

    with pytest.raises(MarketContextError, match="outside receipt interval"):
        _resolve(
            tmp_path,
            source,
            gateway=gateway,
            clock=_sequence_clock(
                datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
                datetime(
                    2026, 7, 17, 8, 0, 2, tzinfo=timezone.utc
                ),
            ),
        )
    assert not list((_cache_root(tmp_path) / "e").glob("*.json"))


def test_zero_attempt_success_is_rejected_before_any_entry_write(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(
        tmp_path, with_close=False, with_industry=False
    )
    response = _success_response()
    response["attempt_count"] = 0
    gateway = FakeGateway(response)

    with pytest.raises(MarketContextError, match="requires an HTTP attempt"):
        _resolve(
            tmp_path,
            source,
            gateway=gateway,
            clock=lambda: datetime(
                2026, 7, 17, 8, 0, 1, tzinfo=timezone.utc
            ),
        )

    assert len(gateway.calls) == 1
    assert not list((_cache_root(tmp_path) / "e").glob("*.json"))


def test_external_cache_entry_freezes_and_revalidates_original_receipt(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(
        tmp_path, with_close=False, with_industry=False
    )
    first = _resolve(
        tmp_path,
        source,
        gateway=FakeGateway(_success_response()),
        clock=lambda: datetime(
            2026, 7, 17, 8, 0, 1, tzinfo=timezone.utc
        ),
    )
    entry_path = next((_cache_root(tmp_path) / "e").glob("*.json"))
    entry = json.loads(entry_path.read_text(encoding="utf-8"))
    receipt = first["market_fallback"]["fetch_receipts"][0]

    assert entry["origin_fetch_receipt"] == receipt
    assert entry["provider_version"] == receipt["provider_version"]
    assert entry["redacted_parameters"] == receipt["redacted_parameters"]
    assert entry["request_fingerprint"] == receipt["request_fingerprint"]
    assert entry["started_at"] == receipt["started_at"]
    assert entry["completed_at"] == receipt["completed_at"]
    assert entry["fetched_at"] == receipt["fetched_at"]
    assert entry["attempt_count"] == receipt["attempt_count"]
    assert entry["origin_requirement"]["requirement_id"] == first[
        "market_requirement_id"
    ]

    entry["origin_fetch_receipt"]["provider_version"] = "tampered"
    entry_path.write_text(
        json.dumps(entry, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    with pytest.raises(
        MarketContextError, match="provenance|fingerprint|content|identity"
    ):
        resolve_market_context(
            portfolio_db=source,
            review_db=_review_db(tmp_path),
            instrument_id="588200.SH",
            as_of="2026-07-17T06:00:00Z",
            knowledge_cutoff=CUTOFF,
            cache_root=_cache_root(tmp_path),
            clock=lambda: datetime(
                2026, 7, 17, 8, 1, tzinfo=timezone.utc
            ),
        )


def test_cross_cutoff_projection_has_content_identity_and_immutable_cache_ref(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(
        tmp_path, with_close=False, with_industry=False
    )
    response = _success_response()
    response["rows"].append(
        {
            "ts_code": "588200.SH",
            "trade_date": "2026-07-15",
            "close": "4.100",
            "pre_close": "4.20",
            "pct_chg": "-2.38",
        }
    )
    first = _resolve(
        tmp_path,
        source,
        gateway=FakeGateway(response),
        clock=lambda: datetime(
            2026, 7, 17, 8, 0, 1, tzinfo=timezone.utc
        ),
    )
    second_gateway = FakeGateway(_success_response("8.888"))
    second = resolve_market_context(
        portfolio_db=source,
        review_db=_review_db(tmp_path),
        instrument_id="588200.SH",
        as_of="2026-07-16T05:55:28Z",
        knowledge_cutoff=CUTOFF,
        cache_root=_cache_root(tmp_path),
        provider_gateway=second_gateway,
        clock=lambda: datetime(
            2026, 7, 17, 8, 1, tzinfo=timezone.utc
        ),
    )

    first_source = next(
        item
        for item in first["supplemental_sources"]
        if item.get("payload", {}).get("origin")
        == "external_provider_cache"
    )
    second_source = next(
        item
        for item in second["supplemental_sources"]
        if item.get("payload", {}).get("origin")
        == "external_provider_cache"
    )
    assert second_gateway.calls == []
    assert first_source["payload"]["cache_entry_ref"] == second_source[
        "payload"
    ]["cache_entry_ref"]
    assert first_source["source_id"] != second_source["source_id"]
    assert len(first_source["payload"]["values"]["rows"]) == 2
    assert len(second_source["payload"]["values"]["rows"]) == 1
    assert first_source["payload"]["origin_fetch_receipt"] == second_source[
        "payload"
    ]["origin_fetch_receipt"]

    hostile = deepcopy(second["supplemental_sources"])
    hostile_source = next(
        item
        for item in hostile
        if item.get("payload", {}).get("origin")
        == "external_provider_cache"
    )
    hostile_source["payload"]["values"]["rows"][0]["close"] = "9.999"
    assert validate_market_context_supplemental_sources(hostile)[
        "validation_status"
    ] == "blocked"


@pytest.mark.parametrize("bad_kind", ["row_cap", "instrument"])
def test_provider_rows_are_bounded_and_exactly_instrument_scoped(
    tmp_path: Path, bad_kind: str
) -> None:
    source = _portfolio_db(
        tmp_path, with_close=False, with_industry=False
    )
    response = _success_response()
    if bad_kind == "row_cap":
        response["rows"] = response["rows"] * 513
        expected = "per-component cap"
    else:
        response["rows"][0]["ts_code"] = "000001.SZ"
        expected = "instrument"
    with pytest.raises(MarketContextError, match=expected):
        _resolve(
            tmp_path,
            source,
            gateway=FakeGateway(response),
            clock=lambda: datetime(
                2026, 7, 17, 8, 0, 1, tzinfo=timezone.utc
            ),
        )
    assert not list((_cache_root(tmp_path) / "e").glob("*.json"))


def test_measured_timeout_and_untrusted_gateway_fail_before_cache_write(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(
        tmp_path, with_close=False, with_industry=False
    )
    with pytest.raises(MarketContextError, match="fixed timeout"):
        _resolve(
            tmp_path,
            source,
            gateway=FakeGateway(_success_response()),
            clock=_sequence_clock(
                datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
                datetime(2026, 7, 17, 8, 0, 21, tzinfo=timezone.utc),
            ),
        )
    assert not list((_cache_root(tmp_path) / "e").glob("*.json"))

    class UntrustedGateway:
        transport_scheme = "https"

        def __init__(self) -> None:
            self.calls = 0

        def fetch(self, **kwargs: Any) -> dict[str, Any]:
            self.calls += 1
            return _success_response()

    untrusted = UntrustedGateway()
    with pytest.raises(MarketContextError, match="closed limits/rate-limit"):
        _resolve(
            tmp_path,
            source,
            gateway=untrusted,
            clock=lambda: datetime(
                2026, 7, 17, 8, 0, 1, tzinfo=timezone.utc
            ),
        )
    assert untrusted.calls == 0
    assert not list((_cache_root(tmp_path) / "e").glob("*.json"))


def test_budget_exhaustion_is_not_mislabeled_provider_unavailable(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(
        tmp_path, with_close=False, with_industry=False
    )
    gateway = FakeGateway(_success_response())
    with pytest.raises(
        MarketRequestBudgetExhaustedError, match="budget is exhausted"
    ):
        _resolve(
            tmp_path,
            source,
            gateway=gateway,
            request_budget=MarketRequestBudget(0),
            clock=lambda: datetime(
                2026, 7, 17, 8, 0, 1, tzinfo=timezone.utc
            ),
        )
    assert gateway.calls == []
    assert not list((_cache_root(tmp_path) / "e").glob("*.json"))


def test_local_row_observed_before_effective_is_withheld_not_promoted(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path, with_industry=False)
    connection = sqlite3.connect(source)
    connection.execute(
        "UPDATE close_prices SET fetched_at='2026-07-16T00:00:00Z'"
    )
    connection.commit()
    connection.close()

    result = _resolve(
        tmp_path,
        source,
        clock=lambda: datetime(
            2026, 7, 17, 8, 0, 1, tzinfo=timezone.utc
        ),
    )
    prior_close = result["resolution"]["coverage_before"]["components"][
        "prior_close"
    ]
    assert prior_close["status"] == "missing"
    assert "SOURCE_OBSERVED_BEFORE_EFFECTIVE" in prior_close[
        "reason_codes"
    ]
    assert result["market_fallback"]["status"] == "provider_unavailable"


def test_candidate_and_cache_authority_are_exact_and_marker_gated(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path)
    correct_review = _review_db(tmp_path)
    with pytest.raises(MarketContextError, match="outside the contract-owned"):
        resolve_market_context(
            portfolio_db=source,
            review_db=correct_review,
            instrument_id="588200.SH",
            as_of=AS_OF,
            knowledge_cutoff=CUTOFF,
            cache_root=tmp_path / "market_cache",
        )

    fake_root = tmp_path / "fake_repo"
    fake_review = (
        fake_root
        / "data"
        / "db"
        / "investment_review_reviewability_v3.sqlite3"
    )
    fake_review.parent.mkdir(parents=True)
    sqlite3.connect(fake_review).close()
    with pytest.raises(MarketContextError, match="exact marked v3 candidate"):
        resolve_market_context(
            portfolio_db=source,
            review_db=fake_review,
            instrument_id="588200.SH",
            as_of=AS_OF,
            knowledge_cutoff=CUTOFF,
            cache_root=(
                fake_root
                / ".codex_tmp"
                / "investment_review_product_completion_v3"
                / "market_cache"
            ),
        )


def test_same_requirement_concurrency_has_one_gateway_flight_and_exact_result(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(
        tmp_path, with_close=False, with_industry=False
    )
    review = _review_db(tmp_path)

    class BlockingGateway(FakeGateway):
        def __init__(self) -> None:
            super().__init__(_success_response())
            self.entered = threading.Event()
            self.release = threading.Event()

        def fetch(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(kwargs)
            self.entered.set()
            assert self.release.wait(5)
            return deepcopy(self.response)

    gateway = BlockingGateway()
    results: list[dict[str, Any]] = []
    failures: list[BaseException] = []

    def worker() -> None:
        try:
            results.append(
                resolve_market_context(
                    portfolio_db=source,
                    review_db=review,
                    instrument_id="588200.SH",
                    as_of=AS_OF,
                    knowledge_cutoff=CUTOFF,
                    cache_root=_cache_root(tmp_path),
                    provider_gateway=gateway,
                    clock=lambda: datetime(
                        2026, 7, 17, 8, 0, 1, tzinfo=timezone.utc
                    ),
                )
            )
        except BaseException as exc:  # pragma: no cover - reported below
            failures.append(exc)

    first_thread = threading.Thread(target=worker)
    second_thread = threading.Thread(target=worker)
    first_thread.start()
    assert gateway.entered.wait(5)
    second_thread.start()
    time.sleep(0.1)
    assert len(gateway.calls) == 1
    gateway.release.set()
    first_thread.join(10)
    second_thread.join(10)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert failures == []
    assert len(gateway.calls) == 1
    assert len(results) == 2
    assert results[0] == results[1]
    assert list((_cache_root(tmp_path) / "locks").glob("*.lock"))


def test_shared_budget_enforces_two_active_gateway_calls_across_requirements(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(
        tmp_path, with_close=False, with_industry=False
    )
    review = _review_db(tmp_path)
    budget = MarketRequestBudget()

    class ConcurrentGateway(FakeGateway):
        def __init__(self) -> None:
            super().__init__(_success_response())
            self.guard = threading.Lock()
            self.active = 0
            self.maximum_active = 0
            self.two_active = threading.Event()
            self.release = threading.Event()

        def fetch(self, **kwargs: Any) -> dict[str, Any]:
            with self.guard:
                self.calls.append(kwargs)
                self.active += 1
                self.maximum_active = max(self.maximum_active, self.active)
                if self.active == 2:
                    self.two_active.set()
            assert self.release.wait(5)
            with self.guard:
                self.active -= 1
            return deepcopy(self.response)

    gateway = ConcurrentGateway()
    failures: list[BaseException] = []

    def worker(second: int) -> None:
        try:
            resolve_market_context(
                portfolio_db=source,
                review_db=review,
                instrument_id="588200.SH",
                as_of=f"2026-07-17T05:55:{second:02d}Z",
                knowledge_cutoff=CUTOFF,
                cache_root=_cache_root(tmp_path),
                provider_gateway=gateway,
                request_budget=budget,
                clock=lambda: datetime(
                    2026, 7, 17, 8, 0, 1, tzinfo=timezone.utc
                ),
            )
        except BaseException as exc:  # pragma: no cover - reported below
            failures.append(exc)

    threads = [threading.Thread(target=worker, args=(second,)) for second in (28, 29, 30)]
    for thread in threads:
        thread.start()
    assert gateway.two_active.wait(5)
    time.sleep(0.1)
    assert gateway.maximum_active == 2
    gateway.release.set()
    for thread in threads:
        thread.join(10)

    assert all(not thread.is_alive() for thread in threads)
    assert failures == []
    assert len(gateway.calls) == 3
    assert gateway.maximum_active == 2
    assert budget.snapshot() == {
        "max_requests": 20,
        "used_requests": 3,
        "reserved_requests": 0,
        "active_requests": 0,
        "remaining_requests": 17,
    }


def test_allowlist_secret_caps_and_offline_consumer_are_closed(tmp_path: Path) -> None:
    with pytest.raises(MarketContextError, match="not code-allowlisted"):
        canonical_provider_request(
            {
                "component": "prior_close",
                "provider_id": "evil",
                "endpoint_id": "daily",
                "provider_version": "v1",
                "parameters": {},
            }
        )
    with pytest.raises(MarketContextError, match="sensitive"):
        canonical_provider_request(
            {
                "component": "prior_close",
                "provider_id": "tushare",
                "endpoint_id": "fund_daily",
                "provider_version": "v1",
                "parameters": {
                    "ts_code": "588200.SH",
                    "fields": "token_secret",
                },
            }
        )
    with pytest.raises(MarketContextError, match="bounded required parameters"):
        canonical_provider_request(
            {
                "component": "instrument",
                "provider_id": "tushare",
                "endpoint_id": "stock_basic",
                "provider_version": "v1",
                "parameters": {},
            }
        )
    with pytest.raises(MarketContextError, match="cannot follow"):
        canonical_provider_request(
            {
                "component": "prior_close",
                "provider_id": "tushare",
                "endpoint_id": "fund_daily",
                "provider_version": "v1",
                "parameters": {
                    "ts_code": "588200.SH",
                    "start_date": "20260717",
                    "end_date": "20260716",
                    "fields": "ts_code,trade_date,close",
                },
            }
        )
    assert MARKET_LIMITS == {
        "timeout_seconds": 20,
        "max_retries": 2,
        "max_concurrency": 2,
        "max_requests_per_run": 20,
    }

    source = _portfolio_db(tmp_path)
    result = _resolve(tmp_path, source)
    offline = offline_market_context_for_consumer(result, consumer="source_replay")
    assert offline["network_allowed"] is False
    assert offline["supplemental_sources"] == result["supplemental_sources"]
    assert validate_market_context_supplemental_sources(
        result["supplemental_sources"],
        expected_market_input_content_id=result["market_input_content_id"],
    )["validation_status"] == "accepted"
    with pytest.raises(MarketContextError, match="unsupported"):
        offline_market_context_for_consumer(result, consumer="provider")


def test_callable_adapter_infers_episode_instrument(tmp_path: Path) -> None:
    source = _portfolio_db(tmp_path)
    review = _review_db(tmp_path)
    adapter = MarketContextAdapter(cache_root=_cache_root(tmp_path, "adapter"))
    result = adapter(
        portfolio_db=source,
        review_db=review,
        episode={"scope": {"instrument_id": "588200.SH"}},
        operation_review={},
        knowledge_provenance={},
        ledger_snapshot_reconstruction={},
        perspective="user",
        as_of=AS_OF,
        knowledge_cutoff=CUTOFF,
    )
    assert result["market_axis"]["status"] == "available"


def test_v2_local_close_is_user_eligible_but_system_retrospective(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path)
    forbidden_gateway = FakeGateway(_verified_v2_response())
    user = _resolve_v2(
        tmp_path,
        source,
        perspective="user",
        gateway=forbidden_gateway,
        clock=_late_v2_clock(),
    )
    assert forbidden_gateway.calls == []
    assert user["resolution"]["schema_version"] == MARKET_CONTEXT_RESOLUTION_VERSION_V2
    assert user["market_fallback"]["policy_version"] == MARKET_FALLBACK_POLICY_VERSION_V2
    assert (
        user["information_time_policy_version"]
        == PUBLIC_INFORMATION_POLICY_VERSION
    )
    close_source = next(
        item
        for item in user["supplemental_sources"]
        if item.get("payload", {}).get("component") == "prior_close"
    )
    assert close_source["payload"]["information_time"] == {
        "status": "verified",
        "lower_bound": "2026-07-16T07:00:00Z",
        "upper_bound": "2026-07-16T07:00:00Z",
        "basis": "exchange_bar_publication_time.v1",
        "method_version": "public_information_time.v1",
        "revision_ref": close_source["payload"]["version_provenance"][
            "revision_ref"
        ],
    }
    assert close_source["payload"]["fetched_at"] == "2026-07-17T07:36:48Z"
    assert close_source["payload"]["system_observed_at"] == "2026-07-17T07:36:48Z"
    assert close_source["payload"]["perspective_eligibility"] == {
        "perspective": "user",
        "status": "eligible",
        "reason_code": "verified_publication_strictly_before_operation",
        "temporal_role": "user_known_at_operation_by_verified_publication",
        "operation_anchor_at": AS_OF,
        "projected_user_known_at": AS_OF,
        "projected_system_known_at": None,
        "actual_user_observation_proven": False,
    }
    assert user["market_axis"]["status"] == "available"
    assert user["market_axis"]["publicly_available_basis"] == "exchange_calendar"
    axis = user["market_axis"]
    assert axis["representative_source_id"] == close_source["source_id"]
    assert axis["representative_source_content_id"] == (
        "sha256:" + hashlib.sha256(canonical_json_bytes(close_source)).hexdigest()
    )
    assert axis["information_time"] == close_source["payload"]["information_time"]
    assert axis["version_provenance"] == close_source["payload"][
        "version_provenance"
    ]
    assert axis["perspective_eligibility"] == close_source["payload"][
        "perspective_eligibility"
    ]
    evidence_manifest = user["resolution"]["market_evidence_manifest"]
    assert axis["market_evidence_manifest_content_id"] == evidence_manifest[
        "content_id"
    ]
    assert (
        "market_evidence_manifest:" + evidence_manifest["content_id"]
        in axis["source_refs"]
    )
    representative_entry = next(
        entry
        for entry in evidence_manifest["sources"]
        if entry["source_id"] == close_source["source_id"]
    )
    assert representative_entry["envelope_content_id"] == axis[
        "representative_source_content_id"
    ]
    assert user["resolution"]["market_source_manifest"]["content_id"] != (
        evidence_manifest["content_id"]
    )

    system_gateway = FakeGateway(_verified_v2_response())
    system = _resolve_v2(
        tmp_path,
        source,
        perspective="system",
        gateway=system_gateway,
        clock=_late_v2_clock(),
    )
    assert system_gateway.calls == []
    system_close = next(
        item
        for item in system["supplemental_sources"]
        if item.get("payload", {}).get("component") == "prior_close"
    )
    assert system_close["payload"]["perspective_eligibility"]["status"] == "ineligible"
    assert (
        system_close["payload"]["perspective_eligibility"]["reason_code"]
        == "system_observed_after_operation"
    )
    assert system["market_axis"]["status"] == "missing"
    assert system["market_axis"]["temporal_role"] == "retrospective_context"
    assert system["market_fallback"]["status"] == "withheld_by_cutoff"
    receipt = system["market_fallback"]["fetch_receipts"][0]
    assert receipt["started_at"] == receipt["completed_at"] == receipt["guard_audit_at"]
    assert receipt["attempt_count"] == receipt["budget_charged_attempts"] == 0
    assert receipt["fetched_at"] is receipt["system_observed_at"] is None
    assert receipt["cache_entry_refs"] == []


def test_v2_user_late_acquisition_uses_verified_public_time_not_fetch_time(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path, with_close=False, with_instrument=False)
    gateway = FakeGateway(_verified_v2_response())
    result = _resolve_v2(
        tmp_path,
        source,
        gateway=gateway,
        clock=_late_v2_clock(),
    )
    assert len(gateway.calls) == 1
    assert result["market_fallback"]["status"] == "succeeded"
    assert result["market_fallback"]["coverage_after"] == "satisfied"
    assert result["market_axis"]["publicly_available_basis"] == "provider_declared"
    receipt = result["market_fallback"]["fetch_receipts"][0]
    assert receipt["started_at"] == "2026-07-20T00:00:01Z"
    assert receipt["fetched_at"] == "2026-07-20T00:00:02Z"
    assert receipt["system_observed_at"] == "2026-07-20T00:00:03Z"
    assert receipt["completed_at"] == "2026-07-20T00:00:03Z"
    assert receipt["fetched_at"] > CUTOFF
    source_row = next(
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("component") == "prior_close"
    )
    eligibility = source_row["payload"]["perspective_eligibility"]
    assert eligibility["status"] == "eligible"
    assert eligibility["projected_user_known_at"] == AS_OF
    assert eligibility["actual_user_observation_proven"] is False
    assert validate_market_context_resolution_v2(result["resolution"])[
        "validation_status"
    ] == "accepted"
    assert validate_market_context_resolution(result["resolution"])[
        "validation_status"
    ] == "accepted"
    assert result["source_replay"]["network_allowed"] is False


@pytest.mark.parametrize(
    ("public_at", "expected_status", "expected_reason"),
    [
        (
            "2026-07-17T05:55:27Z",
            "eligible",
            "verified_publication_strictly_before_operation",
        ),
        (
            AS_OF,
            "ambiguous",
            "publication_interval_touches_operation_anchor",
        ),
        (
            "2026-07-17T05:55:29Z",
            "ineligible",
            "post_operation_publication",
        ),
    ],
)
def test_v2_user_publication_boundary_is_strict(
    tmp_path: Path,
    public_at: str,
    expected_status: str,
    expected_reason: str,
) -> None:
    source = _portfolio_db(tmp_path, with_close=False, with_instrument=False)
    result = _resolve_v2(
        tmp_path,
        source,
        gateway=FakeGateway(_verified_v2_response(publicly_available_at=public_at)),
        clock=_late_v2_clock(),
    )
    component = next(
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("component") == "prior_close"
    )
    eligibility = component["payload"]["perspective_eligibility"]
    assert eligibility["status"] == expected_status
    assert eligibility["reason_code"] == expected_reason
    assert result["market_axis"]["temporal_role"] == {
        "eligible": "user_known_at_operation_by_verified_publication",
        "ambiguous": "ambiguous",
        "ineligible": "retrospective_context",
    }[expected_status]
    assert result["market_fallback"]["status"] == "succeeded"
    assert result["resolution"]["coverage_after"]["status"] == (
        "satisfied" if expected_status == "eligible" else "missing"
    )


@pytest.mark.parametrize(
    ("publication_date", "publication_timezone", "expected_info", "expected_eligibility"),
    [
        ("2026-07-16", "Asia/Shanghai", "verified", "eligible"),
        ("2026-07-17", "Asia/Shanghai", "verified", "ambiguous"),
        ("2026-07-16", "Unknown/Nowhere", "unknown", "unknown"),
        ("2026-07-16", None, "unknown", "unknown"),
    ],
)
def test_v2_date_only_publication_uses_source_timezone_closed_day(
    tmp_path: Path,
    publication_date: str,
    publication_timezone: str | None,
    expected_info: str,
    expected_eligibility: str,
) -> None:
    source = _portfolio_db(tmp_path, with_close=False, with_instrument=False)
    response = _verified_v2_response(
        publicly_available_at=None,
        publication_date=publication_date,
        publication_timezone=publication_timezone,
    )
    result = _resolve_v2(
        tmp_path,
        source,
        gateway=FakeGateway(response),
        clock=_late_v2_clock(),
    )
    component = next(
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("component") == "prior_close"
    )
    information = component["payload"]["information_time"]
    eligibility = component["payload"]["perspective_eligibility"]
    assert information["status"] == expected_info
    assert eligibility["status"] == expected_eligibility
    if publication_date == "2026-07-17" and publication_timezone == "Asia/Shanghai":
        assert information["lower_bound"] < AS_OF < information["upper_bound"]
        assert eligibility["reason_code"] == "publication_interval_touches_operation_anchor"
    if expected_info == "verified":
        assert result["market_axis"]["publicly_available_basis"] == (
            "verified_publication_interval"
        )


@pytest.mark.parametrize(
    ("overrides", "expected_info", "expected_eligibility"),
    [
        ({"revision_ref": None}, "unknown", "unknown"),
        ({"public_time_source_ref": None}, "unknown", "unknown"),
        ({"public_time_source_ref": "x"}, "conflicted", "ambiguous"),
        ({"content_sha256": "sha256:" + "0" * 64}, "conflicted", "ambiguous"),
        ({"publication_basis": "fetched_at"}, "conflicted", "ambiguous"),
        ({"publication_status": ""}, "unknown", "unknown"),
        ({"publication_basis": "caller_asserted.v1"}, "conflicted", "ambiguous"),
        (
            {
                "publication_date": "2026-07-17",
                "publication_timezone": "Asia/Shanghai",
            },
            "conflicted",
            "ambiguous",
        ),
        (
            {"publicly_available_at": "2026-07-16 07:00:00"},
            "unknown",
            "unknown",
        ),
    ],
)
def test_v2_unproven_or_forged_publication_fails_closed(
    tmp_path: Path,
    overrides: dict[str, Any],
    expected_info: str,
    expected_eligibility: str,
) -> None:
    source = _portfolio_db(tmp_path, with_close=False, with_instrument=False)
    response = _verified_v2_response(**overrides)
    result = _resolve_v2(
        tmp_path,
        source,
        gateway=FakeGateway(response),
        clock=_late_v2_clock(),
    )
    component = next(
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("component") == "prior_close"
    )
    assert component["payload"]["information_time"]["status"] == expected_info
    assert (
        component["payload"]["perspective_eligibility"]["status"]
        == expected_eligibility
    )
    assert result["market_axis"]["temporal_role"] == {
        "ambiguous": "ambiguous",
        "unknown": "unknown",
    }[expected_eligibility]
    assert result["market_fallback"]["status"] == "succeeded"
    assert result["resolution"]["coverage_after"]["status"] == "missing"


def test_v2_cached_late_external_version_is_user_eligible_system_ineligible(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path, with_close=False, with_instrument=False)
    user_gateway = FakeGateway(_verified_v2_response())
    user = _resolve_v2(
        tmp_path,
        source,
        perspective="user",
        gateway=user_gateway,
        clock=_late_v2_clock(),
    )
    assert user["resolution"]["coverage_after"]["status"] == "satisfied"
    system_gateway = FakeGateway(_verified_v2_response())
    system = _resolve_v2(
        tmp_path,
        source,
        perspective="system",
        gateway=system_gateway,
        clock=_late_v2_clock(),
    )
    assert system_gateway.calls == []
    cached = next(
        item
        for item in system["supplemental_sources"]
        if item.get("payload", {}).get("origin") == "external_provider_cache"
    )
    assert cached["payload"]["fetched_at"] == "2026-07-20T00:00:02Z"
    assert cached["payload"]["system_observed_at"] == "2026-07-20T00:00:03Z"
    assert cached["payload"]["perspective_eligibility"]["status"] == "ineligible"
    assert system["market_fallback"]["status"] == "withheld_by_cutoff"
    assert system["resolution"]["coverage_after"]["status"] == "missing"


def test_v2_user_provider_unavailable_and_budget_exhausted_are_complete_limitations(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path, with_close=False, with_instrument=False)
    unavailable = _resolve_v2(
        tmp_path,
        source,
        perspective="user",
        clock=_late_v2_clock(),
    )
    assert unavailable["market_fallback"]["status"] == "provider_unavailable"
    assert unavailable["market_fallback"]["request_count"] == 0
    assert unavailable["market_axis"]["status"] == "missing"
    assert unavailable["market_axis"]["publicly_available_basis"] == "not_applicable"
    for proof_field in (
        "representative_source_id",
        "representative_source_content_id",
        "information_time",
        "version_provenance",
        "perspective_eligibility",
    ):
        assert unavailable["market_axis"][proof_field] is None
    assert unavailable["market_axis"][
        "market_evidence_manifest_content_id"
    ] == unavailable["resolution"]["market_evidence_manifest"]["content_id"]
    assert unavailable["resolution"]["market_evidence_manifest"]["sources"] == []
    assert validate_market_context_resolution_v2(unavailable["resolution"])[
        "validation_status"
    ] == "accepted"

    other_root = _cache_root(tmp_path, "budget")
    gateway = FakeGateway(_verified_v2_response())
    exhausted = resolve_market_context_v2(
        portfolio_db=source,
        review_db=_review_db(tmp_path),
        instrument_id="588200.SH",
        perspective="user",
        operation_anchor_event_id="event-anchor",
        operation_anchor_at=AS_OF,
        operation_anchor_ordering_key=[AS_OF, 0, "fixture", "event-anchor"],
        as_of=AS_OF,
        knowledge_cutoff=CUTOFF,
        cache_root=other_root,
        provider_gateway=gateway,
        clock=_late_v2_clock(),
        request_budget=MarketRequestBudget(0),
        required_components=("prior_close",),
    )
    assert gateway.calls == []
    assert exhausted["market_fallback"]["status"] == "budget_exhausted"
    assert exhausted["market_fallback"]["request_count_status"] == "verified"
    assert exhausted["market_fallback"]["unverified_attempt_upper_bound"] == 0
    assert any(
        gap["code"] == "MARKET_REQUEST_BUDGET_EXHAUSTED"
        for gap in exhausted["market_gaps"]
    )


def test_v2_gateway_failure_preserves_verified_attempts_and_exception_keeps_unknown_bound(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path, with_close=False, with_instrument=False)
    failed_gateway = FakeGateway(
        {"response_status": "failed", "attempt_count": 1}
    )
    failed = _resolve_v2(
        tmp_path,
        source,
        gateway=failed_gateway,
        clock=_late_v2_clock(),
    )
    assert failed["market_fallback"]["status"] == "failed"
    assert failed["market_fallback"]["request_count"] == 1
    assert failed["market_fallback"]["request_count_status"] == "verified"

    class RaisingGateway(FakeGateway):
        def fetch(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(kwargs)
            raise RuntimeError("transport lost without attempt metadata")

    raising_gateway = RaisingGateway(_verified_v2_response())
    unknown = resolve_market_context_v2(
        portfolio_db=source,
        review_db=_review_db(tmp_path),
        instrument_id="588200.SH",
        perspective="user",
        operation_anchor_event_id="event-anchor",
        operation_anchor_at=AS_OF,
        operation_anchor_ordering_key=[AS_OF, 0, "fixture", "event-anchor"],
        as_of=AS_OF,
        knowledge_cutoff=CUTOFF,
        cache_root=_cache_root(tmp_path, "raising"),
        provider_gateway=raising_gateway,
        clock=_late_v2_clock(),
        required_components=("prior_close",),
    )
    fallback = unknown["market_fallback"]
    receipt = fallback["fetch_receipts"][0]
    assert fallback["status"] == "failed"
    assert fallback["limitation_code"] == "provider_attempt_count_unknown"
    assert fallback["request_count"] == 0
    assert fallback["request_count_status"] == "bounded_unknown"
    assert fallback["unverified_attempt_upper_bound"] == 3
    assert receipt["attempt_count"] == 0
    assert receipt["attempt_count_status"] == "unknown"
    assert receipt["budget_charged_attempts"] == 3
    assert receipt["fetched_at"] is None and receipt["cache_entry_refs"] == []
    assert any(
        gap["code"] == "PROVIDER_ATTEMPT_COUNT_UNKNOWN"
        for gap in unknown["market_gaps"]
    )


def _reidentify_v2_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(receipt)
    result["receipt_id"] = ""
    result["receipt_id"] = "market_fetch_receipt_v2_" + hashlib.sha256(
        canonical_json_bytes(result)
    ).hexdigest()
    return result


def _reidentify_v2_source(source: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(source)
    result["payload"]["source_id"] = None
    source_id = "market_source_v2_" + hashlib.sha256(
        canonical_json_bytes(result["payload"])
    ).hexdigest()
    result["source_id"] = source_id
    result["payload"]["source_id"] = source_id
    return result


def _reclose_local_projection_v2(
    source: dict[str, Any], requirement: dict[str, Any]
) -> dict[str, Any]:
    """Reclose every projection-derived field without changing raw origin proof."""
    result = deepcopy(source)
    payload = result["payload"]
    source_table = str(payload["source_table"])
    source_record_id = str(payload["source_record_id"])
    content_hash = "sha256:" + hashlib.sha256(
        canonical_json_bytes(
            {
                "component": payload["component"],
                "instrument_id": requirement["instrument_id"],
                "source_table": source_table,
                "source_record_id": source_record_id,
                "values": payload["values"],
            }
        )
    ).hexdigest()
    revision_ref = f"{source_table}:{source_record_id}:{content_hash}"
    payload["normalized_content_sha256"] = content_hash
    payload["version_provenance"]["content_sha256"] = content_hash
    payload["version_provenance"]["source_ref"] = (
        f"portfolio_cache:{source_table}:{source_record_id}"
    )
    payload["version_provenance"]["revision_ref"] = revision_ref
    payload["information_time"]["revision_ref"] = revision_ref
    eligibility = _perspective_eligibility_v2(
        requirement=requirement,
        component=str(payload["component"]),
        information_time=payload["information_time"],
        version_provenance=payload["version_provenance"],
        system_observed_at=str(payload["system_observed_at"]),
    )
    payload["perspective_eligibility"] = eligibility
    payload["temporal_role"] = eligibility["temporal_role"]
    result["effective_at"] = payload["effective_at"]
    result["knowledge_at"] = payload["system_observed_at"]
    result["locator"] = (
        f"portfolio_local_cache:{source_table}:{source_record_id}"
    )
    return _reidentify_v2_source(result)


def _reidentify_v2_resolution(resolution: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(resolution)
    result.pop("content_id", None)
    result["content_id"] = (
        "sha256:" + hashlib.sha256(canonical_json_bytes(result)).hexdigest()
    )
    return result


def test_v2_zero_limitation_status_and_acquisition_order_are_tamper_closed(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path)
    system = _resolve_v2(
        tmp_path,
        source,
        perspective="system",
        clock=_late_v2_clock(),
    )
    fallback = deepcopy(system["market_fallback"])
    fallback["fetch_receipts"][0]["response_status"] = "budget_exhausted"
    fallback["fetch_receipts"][0] = _reidentify_v2_receipt(
        fallback["fetch_receipts"][0]
    )
    fallback["fetch_receipt_refs"] = [
        fallback["fetch_receipts"][0]["receipt_id"]
    ]
    with pytest.raises(MarketContextError, match="guard receipt|limitation"):
        _canonical_fallback_v2(fallback)

    source2 = _portfolio_db(
        tmp_path / "other", with_close=False, with_instrument=False
    )
    success = _resolve_v2(
        tmp_path / "other",
        source2,
        gateway=FakeGateway(_verified_v2_response()),
        clock=_late_v2_clock(),
    )
    receipt = deepcopy(success["market_fallback"]["fetch_receipts"][0])
    receipt["guard_audit_at"] = "2026-07-20T00:00:02Z"
    receipt = _reidentify_v2_receipt(receipt)
    with pytest.raises(MarketContextError, match="order"):
        _canonical_receipt_v2(receipt)


def test_v2_axis_representative_does_not_leak_late_optional_observation(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(
        tmp_path,
        with_optional_rows=True,
        close_fetched_at="2026-07-17T05:00:00Z",
    )
    result = _resolve_v2(
        tmp_path,
        source,
        perspective="system",
        gateway=FakeGateway(_verified_v2_response()),
        clock=_late_v2_clock(),
    )
    assert result["market_fallback"]["status"] == "not_needed"
    assert result["market_axis"]["temporal_role"] == "system_known_at_operation"
    assert result["market_axis"]["system_observed_at"] == "2026-07-17T05:35:00Z"
    assert result["market_axis"]["system_observed_at"] <= AS_OF
    late_daily = next(
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("component") == "daily"
    )
    assert late_daily["payload"]["system_observed_at"] == "2026-07-17T07:40:00Z"
    assert late_daily["source_id"] in result["market_axis"][
        "retrospective_source_refs"
    ]


def test_v2_system_observation_equal_to_anchor_is_eligible(tmp_path: Path) -> None:
    source = _portfolio_db(tmp_path, close_fetched_at=AS_OF)
    result = _resolve_v2(
        tmp_path,
        source,
        perspective="system",
        gateway=FakeGateway(_verified_v2_response()),
        clock=_late_v2_clock(),
    )
    close_source = next(
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("component") == "prior_close"
    )
    eligibility = close_source["payload"]["perspective_eligibility"]
    assert eligibility["status"] == "eligible"
    assert eligibility["projected_system_known_at"] == AS_OF
    assert result["market_fallback"]["status"] == "not_needed"


def test_v2_system_rejects_local_row_acquired_before_effective_time(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(
        tmp_path,
        close_fetched_at="2026-07-16T06:00:00Z",
        with_instrument=False,
    )
    result = _resolve_v2(
        tmp_path,
        source,
        perspective="system",
        clock=_late_v2_clock(),
    )
    close_sources = [
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("component") == "prior_close"
    ]
    assert close_sources == []
    assert result["resolution"]["coverage_after"]["status"] == "missing"
    assert "SOURCE_ACQUISITION_PRECEDES_EFFECTIVE" in result["resolution"][
        "coverage_after"
    ]["components"]["prior_close"]["reason_codes"]
    assert result["market_axis"]["temporal_role"] == "missing"


def test_v2_system_instrument_revision_effective_time_never_uses_later_as_of(
    tmp_path: Path,
) -> None:
    anchor = "2026-07-17T05:40:00Z"
    observed = "2026-07-17T05:30:00Z"
    later_as_of = "2026-07-17T07:00:00Z"
    source = _portfolio_db(
        tmp_path,
        with_close=False,
        with_industry=False,
        instrument_updated_at=observed,
    )
    result = resolve_market_context_v2(
        portfolio_db=source,
        review_db=_review_db(tmp_path),
        instrument_id="588200.SH",
        perspective="system",
        operation_anchor_event_id="event-anchor",
        operation_anchor_at=anchor,
        operation_anchor_ordering_key=[anchor, 0, "fixture", "event-anchor"],
        as_of=later_as_of,
        knowledge_cutoff=CUTOFF,
        cache_root=_cache_root(tmp_path, "instrument-anchor"),
        required_components=("instrument",),
        optional_components=(),
    )
    instrument = next(
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("component") == "instrument"
    )
    assert instrument["effective_at"] == observed
    assert instrument["payload"]["effective_at"] == observed
    assert instrument["payload"]["coverage_effective_at"] == observed
    assert instrument["payload"]["perspective_eligibility"]["status"] == "eligible"
    assert result["market_axis"]["effective_at"] == observed
    assert result["market_axis"]["effective_at"] <= anchor < later_as_of


def test_v2_bar_scope_and_staleness_use_operation_anchor_not_later_as_of(
    tmp_path: Path,
) -> None:
    anchor = "2026-07-17T05:40:00Z"
    later_as_of = "2026-07-17T07:00:00Z"
    source = _portfolio_db(
        tmp_path,
        with_close=False,
        with_instrument=False,
        with_optional_rows=True,
    )
    connection = sqlite3.connect(source)
    connection.execute(
        """
        INSERT INTO minute_bar_observations(
            ts_code, bar_time, frequency_minutes, open_price,
            high_price, low_price, close_price, volume_shares,
            amount_cny, source, refresh_batch_id, dedupe_key, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "588200.SH",
            "2026-07-17 13:45:00",
            1,
            "4.02",
            "4.03",
            "4.01",
            "4.02",
            "1000",
            "4020",
            "tushare.etf_mins",
            "fixture",
            "post-anchor-minute",
            "2026-07-17T05:46:00Z",
        ),
    )
    connection.commit()
    connection.close()
    result = resolve_market_context_v2(
        portfolio_db=source,
        review_db=_review_db(tmp_path),
        instrument_id="588200.SH",
        perspective="system",
        operation_anchor_event_id="event-anchor",
        operation_anchor_at=anchor,
        operation_anchor_ordering_key=[anchor, 0, "fixture", "event-anchor"],
        as_of=later_as_of,
        knowledge_cutoff=CUTOFF,
        cache_root=_cache_root(tmp_path, "bar-anchor"),
        required_components=("minute",),
        optional_components=(),
        staleness_seconds={"minute": 15 * 60},
    )
    minute_sources = [
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("component") == "minute"
    ]
    assert len(minute_sources) == 1
    assert minute_sources[0]["payload"]["coverage_effective_at"] == (
        "2026-07-17T05:30:00Z"
    )
    assert minute_sources[0]["payload"]["coverage_effective_at"] <= anchor
    assert result["resolution"]["coverage_after"]["status"] == "satisfied"
    assert result["market_fallback"]["status"] == "not_needed"


def test_v2_missing_close_request_and_rows_are_anchor_scoped(tmp_path: Path) -> None:
    anchor = "2026-07-17T05:40:00Z"
    later_as_of = "2026-07-18T05:00:00Z"
    cutoff = "2026-07-21T00:00:00Z"
    source = _portfolio_db(tmp_path, with_close=False, with_instrument=False)
    response = _verified_v2_response()
    post_anchor = deepcopy(response["rows"][0])
    post_anchor["trade_date"] = "2026-07-17"
    post_anchor["publicly_available_at"] = "2026-07-17T07:00:00Z"
    post_anchor["revision_ref"] = "provider-revision-20260717"
    post_anchor["content_sha256"] = market_row_content_sha256_v2(
        component="prior_close",
        instrument_id="588200.SH",
        row=post_anchor,
    )
    post_information = _provider_information_candidate_v2(
        normalized=post_anchor,
        revision_ref="provider-revision-20260717",
        fetched_at=response["fetched_at"],
    )
    post_anchor["public_time_source_ref"] = _provider_publication_source_ref_v2(
        provider_id="tushare",
        endpoint_id="daily",
        publication_basis="official_release_metadata.v1",
        revision_ref="provider-revision-20260717",
        content_sha256=post_anchor["content_sha256"],
        information_time=post_information,
    )
    response["rows"].append(post_anchor)
    gateway = FakeGateway(response)
    result = resolve_market_context_v2(
        portfolio_db=source,
        review_db=_review_db(tmp_path),
        instrument_id="588200.SH",
        perspective="user",
        operation_anchor_event_id="event-anchor",
        operation_anchor_at=anchor,
        operation_anchor_ordering_key=[anchor, 0, "fixture", "event-anchor"],
        as_of=later_as_of,
        knowledge_cutoff=cutoff,
        cache_root=_cache_root(tmp_path, "provider-anchor"),
        provider_gateway=gateway,
        clock=_late_v2_clock(),
        required_components=("prior_close",),
        optional_components=(),
    )
    assert gateway.calls[0]["request"]["redacted_parameters"]["end_date"] == (
        "20260716"
    )
    close_sources = [
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("component") == "prior_close"
    ]
    assert len(close_sources) == 1
    assert close_sources[0]["payload"]["values"]["trade_date"] == "2026-07-16"
    assert close_sources[0]["payload"]["coverage_effective_at"] <= anchor


def test_v2_explicit_prior_close_request_cannot_exceed_operation_anchor() -> None:
    anchor = "2026-07-17T05:40:00Z"
    with pytest.raises(MarketContextError, match="operation anchor"):
        build_market_cache_requirement_v2(
            instrument_id="588200.SH",
            perspective="user",
            operation_anchor_event_id="event-anchor",
            operation_anchor_at=anchor,
            operation_anchor_ordering_key=[
                anchor,
                0,
                "fixture",
                "event-anchor",
            ],
            as_of="2026-07-18T05:00:00Z",
            knowledge_cutoff="2026-07-21T00:00:00Z",
            required_components=("prior_close",),
            optional_components=(),
            provider_requests=(
                {
                    "component": "prior_close",
                    "provider_id": "tushare",
                    "endpoint_id": "daily",
                    "provider_version": "repository_configured_gateway.v1",
                    "parameters": {
                        "ts_code": "588200.SH",
                        "start_date": "20260717",
                        "end_date": "20260717",
                        "fields": "ts_code,trade_date,close",
                    },
                },
            ),
        )


@pytest.mark.parametrize(
    "provider_request",
    [
        {
            "component": "daily",
            "provider_id": "tushare",
            "endpoint_id": "daily",
            "provider_version": "repository_configured_gateway.v1",
            "parameters": {
                "ts_code": "588200.SH",
                "start_date": "20260717",
                "end_date": "20260718",
                "fields": "ts_code,trade_date,close",
            },
        },
        {
            "component": "minute",
            "provider_id": "tushare",
            "endpoint_id": "etf_mins",
            "provider_version": "repository_configured_gateway.v1",
            "parameters": {
                "ts_code": "588200.SH",
                "freq": "1min",
                "start_date": "2026-07-17 13:30:00",
                "end_date": "2026-07-17 13:45:00",
                "fields": "ts_code,trade_time,close",
            },
        },
    ],
)
def test_v2_every_provider_window_is_bounded_by_operation_anchor(
    provider_request: dict[str, Any],
) -> None:
    anchor = "2026-07-17T05:40:00Z"
    with pytest.raises(MarketContextError, match="operation anchor"):
        build_market_cache_requirement_v2(
            instrument_id="588200.SH",
            perspective="user",
            operation_anchor_event_id="event-anchor",
            operation_anchor_at=anchor,
            operation_anchor_ordering_key=[anchor, 0, "fixture", "event-anchor"],
            as_of="2026-07-18T05:00:00Z",
            knowledge_cutoff="2026-07-21T00:00:00Z",
            required_components=(str(provider_request["component"]),),
            optional_components=(),
            provider_requests=(provider_request,),
        )


def test_v2_provider_endpoint_must_match_market_component() -> None:
    with pytest.raises(MarketContextError, match="market component"):
        build_market_cache_requirement_v2(
            instrument_id="588200.SH",
            perspective="user",
            operation_anchor_event_id="event-anchor",
            operation_anchor_at=AS_OF,
            operation_anchor_ordering_key=[AS_OF, 0, "fixture", "event-anchor"],
            as_of=AS_OF,
            knowledge_cutoff=CUTOFF,
            required_components=("factor",),
            optional_components=(),
            provider_requests=(
                {
                    **_prior_close_provider_request("daily"),
                    "component": "factor",
                },
            ),
        )


@pytest.mark.parametrize("naive_field", ["anchor", "as_of", "cutoff", "ordering"])
def test_v2_requirement_rejects_naive_boundary_times(naive_field: str) -> None:
    anchor = AS_OF
    as_of = AS_OF
    cutoff = CUTOFF
    ordering_at = AS_OF
    naive = "2026-07-17T05:55:28"
    if naive_field == "anchor":
        anchor = naive
        ordering_at = naive
    elif naive_field == "as_of":
        as_of = naive
    elif naive_field == "cutoff":
        cutoff = "2026-07-18T00:00:00"
    else:
        ordering_at = naive
    with pytest.raises(MarketContextError, match="explicit timezone"):
        build_market_cache_requirement_v2(
            instrument_id="588200.SH",
            perspective="user",
            operation_anchor_event_id="event-anchor",
            operation_anchor_at=anchor,
            operation_anchor_ordering_key=[
                ordering_at,
                0,
                "fixture",
                "event-anchor",
            ],
            as_of=as_of,
            knowledge_cutoff=cutoff,
            required_components=("prior_close",),
            optional_components=(),
        )


def test_v2_local_naive_observation_time_cannot_be_system_known(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(
        tmp_path,
        with_instrument=False,
        close_fetched_at="2026-07-17T05:00:00",
    )
    result = _resolve_v2(
        tmp_path,
        source,
        perspective="system",
        optional_components=(),
    )
    assert all(
        item.get("payload", {}).get("component") != "prior_close"
        for item in result["supplemental_sources"]
    )
    detail = result["resolution"]["coverage_after"]["components"]["prior_close"]
    assert detail["status"] == "missing"
    assert "SOURCE_TIME_INVALID" in detail["reason_codes"]


def test_v2_factor_has_no_exchange_bar_publication_inference(tmp_path: Path) -> None:
    source = _portfolio_db(
        tmp_path,
        with_close=False,
        with_instrument=False,
        with_optional_rows=True,
    )
    with sqlite3.connect(source) as connection:
        connection.execute("DELETE FROM daily_bar_observations")
        connection.execute("DELETE FROM minute_bar_observations")
        connection.commit()
    result = _resolve_v2(
        tmp_path,
        source,
        perspective="user",
        required_components=("factor",),
        optional_components=(),
    )
    factor = next(
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("component") == "factor"
    )
    assert factor["payload"]["information_time"]["status"] == "unknown"
    assert factor["payload"]["publicly_available_at"] is None
    assert factor["payload"]["perspective_eligibility"]["status"] == "unknown"
    assert result["resolution"]["coverage_after"]["status"] == "missing"
    assert result["market_axis"]["publicly_available_basis"] == "unknown"


def test_v2_system_rejects_factor_observed_before_its_effective_time(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(
        tmp_path,
        with_close=False,
        with_instrument=False,
        with_optional_rows=True,
    )
    with sqlite3.connect(source) as connection:
        connection.execute(
            "UPDATE adjustment_factor_observations "
            "SET fetched_at='2026-07-16T00:00:00Z'"
        )
        connection.commit()
    result = _resolve_v2(
        tmp_path,
        source,
        perspective="system",
        required_components=("factor",),
        optional_components=(),
    )
    factor_sources = [
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("component") == "factor"
    ]
    assert factor_sources == []
    assert result["resolution"]["coverage_after"]["status"] == "missing"
    assert "SOURCE_ACQUISITION_PRECEDES_EFFECTIVE" in result["resolution"][
        "coverage_after"
    ]["components"]["factor"]["reason_codes"]


def test_v2_validator_returns_blocked_for_non_mapping_payload_and_consumers_stay_offline(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path)
    result = _resolve_v2(tmp_path, source, perspective="user")
    for consumer in ("renderer", "source_replay", "api", "ui"):
        frozen = offline_market_context_for_consumer(result, consumer=consumer)
        assert frozen["network_allowed"] is False
    hostile = deepcopy(result["resolution"])
    hostile["supplemental_sources"][0]["payload"] = ["not", "an", "object"]
    validation = validate_market_context_resolution_v2(hostile)
    assert validation["validation_status"] == "blocked"
    assert validation["finding_count"] == 1


def test_v2_axis_unknown_basis_role_swap_is_tamper_closed(tmp_path: Path) -> None:
    source = _portfolio_db(tmp_path)
    result = _resolve_v2(tmp_path, source, perspective="user")
    hostile = deepcopy(result["resolution"])
    hostile["market_axis"]["publicly_available_basis"] = "unknown"
    hostile["market_axis"]["temporal_role"] = "unknown"
    hostile = _reidentify_v2_resolution(hostile)
    validation = validate_market_context_resolution_v2(hostile)
    assert validation["validation_status"] == "blocked"
    assert "axis projection drift" in validation["findings"][0]["message"]


def test_v2_component_validator_rejects_reidentified_post_anchor_eligible_source(
    tmp_path: Path,
) -> None:
    anchor = "2026-07-17T05:40:00Z"
    source = _portfolio_db(tmp_path)
    result = _resolve_v2(
        tmp_path,
        source,
        perspective="user",
        operation_anchor_at=anchor,
    )
    component = next(
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("component") == "prior_close"
    )
    hostile = deepcopy(component)
    hostile["effective_at"] = "2026-07-17T05:50:00Z"
    hostile["payload"]["effective_at"] = "2026-07-17T05:50:00Z"
    hostile["payload"]["coverage_effective_at"] = "2026-07-17T05:50:00Z"
    hostile = _reidentify_v2_source(hostile)
    with pytest.raises(MarketContextError, match="operation anchor"):
        _canonical_component_source_v2(
            hostile,
            result["resolution"]["requirement"],
        )


def test_v2_component_validator_rejects_reidentified_acquisition_reversal(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path)
    result = _resolve_v2(tmp_path, source, perspective="user")
    component = next(
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("component") == "prior_close"
    )
    hostile = deepcopy(component)
    hostile["knowledge_at"] = "2026-07-17T07:00:00Z"
    hostile["payload"]["system_observed_at"] = "2026-07-17T07:00:00Z"
    hostile = _reidentify_v2_source(hostile)
    with pytest.raises(MarketContextError, match="acquisition order"):
        _canonical_component_source_v2(
            hostile,
            result["resolution"]["requirement"],
        )


@pytest.mark.parametrize(
    "manifest_field",
    ["market_evidence_manifest", "market_source_manifest"],
)
def test_v2_manifest_hash_tamper_is_closed(
    tmp_path: Path,
    manifest_field: str,
) -> None:
    source = _portfolio_db(tmp_path)
    result = _resolve_v2(tmp_path, source, perspective="user")
    hostile = deepcopy(result["resolution"])
    hostile[manifest_field]["content_id"] = "sha256:" + "0" * 64
    hostile = _reidentify_v2_resolution(hostile)
    validation = validate_market_context_resolution_v2(hostile)
    assert validation["validation_status"] == "blocked"
    assert "manifest" in validation["findings"][0]["message"]


def test_v2_post_response_validation_failure_charges_reserved_budget(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path, with_close=False, with_instrument=False)
    budget = MarketRequestBudget(3)
    gateway = FakeGateway(
        {
            "response_status": "succeeded",
            "attempt_count": 1,
            "fetched_at": "2026-07-20T00:00:02Z",
            "raw_payload": "invalid-empty-provider-response",
            "rows": [],
        }
    )
    result = _resolve_v2(
        tmp_path,
        source,
        gateway=gateway,
        clock=_late_v2_clock(),
        request_budget=budget,
        optional_components=(),
    )
    receipt = result["market_fallback"]["fetch_receipts"][0]
    assert result["market_fallback"]["status"] == "failed"
    assert receipt["attempt_count_status"] == "unknown"
    assert receipt["budget_charged_attempts"] == 3
    assert budget.snapshot() == {
        "max_requests": 3,
        "used_requests": 3,
        "reserved_requests": 0,
        "active_requests": 0,
        "remaining_requests": 0,
    }


def test_v2_partial_success_preserves_budget_exhaustion_receipt_and_gap(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path, with_close=False, with_instrument=False)
    budget = MarketRequestBudget(1)

    class EndpointAwareGateway(FakeGateway):
        def fetch(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(kwargs)
            request = kwargs["request"]
            return _verified_v2_response(
                provider_id=str(request["provider_id"]),
                endpoint_id=str(request["endpoint_id"]),
            )

    gateway = EndpointAwareGateway(_verified_v2_response())
    result = _resolve_v2(
        tmp_path,
        source,
        gateway=gateway,
        clock=_late_v2_clock(),
        request_budget=budget,
        optional_components=(),
        provider_requests=(
            _prior_close_provider_request("daily"),
            _prior_close_provider_request("fund_daily"),
        ),
    )
    fallback = result["market_fallback"]
    assert len(gateway.calls) == 1
    assert fallback["status"] == "succeeded"
    assert fallback["request_count"] == 1
    assert {
        receipt["response_status"] for receipt in fallback["fetch_receipts"]
    } == {"succeeded", "budget_exhausted"}
    assert result["resolution"]["coverage_after"]["status"] == "satisfied"
    assert any(
        gap["code"] == "MARKET_REQUEST_BUDGET_EXHAUSTED"
        for gap in result["market_gaps"]
    )
    assert budget.snapshot()["used_requests"] == 1
    assert budget.snapshot()["remaining_requests"] == 0


def test_v2_partial_success_with_unknown_later_attempt_is_checkpoint_compatible(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path, with_close=False, with_instrument=False)
    budget = MarketRequestBudget(4)

    class SuccessThenUnknownGateway(FakeGateway):
        def fetch(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(kwargs)
            if len(self.calls) > 1:
                raise RuntimeError("transport lost without attempt metadata")
            request = kwargs["request"]
            return _verified_v2_response(
                provider_id=str(request["provider_id"]),
                endpoint_id=str(request["endpoint_id"]),
            )

    gateway = SuccessThenUnknownGateway(_verified_v2_response())
    result = _resolve_v2(
        tmp_path,
        source,
        gateway=gateway,
        clock=_sequence_clock(
            datetime(2026, 7, 20, 0, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 20, 0, 0, 1, tzinfo=timezone.utc),
            datetime(2026, 7, 20, 0, 0, 3, tzinfo=timezone.utc),
            datetime(2026, 7, 20, 0, 0, 4, tzinfo=timezone.utc),
            datetime(2026, 7, 20, 0, 0, 6, tzinfo=timezone.utc),
        ),
        request_budget=budget,
        optional_components=(),
        provider_requests=(
            _prior_close_provider_request("daily"),
            _prior_close_provider_request("fund_daily"),
        ),
    )
    fallback = result["market_fallback"]
    assert fallback["status"] == "succeeded"
    assert fallback["limitation_code"] == "provider_attempt_count_unknown"
    assert fallback["request_count_status"] == "bounded_unknown"
    assert fallback["request_count"] == 1
    assert fallback["unverified_attempt_upper_bound"] == 3
    assert _canonical_market_fallback_v2(
        fallback, perspective="user"
    ) == fallback
    assert _canonical_market_axis_v2(
        result["market_axis"],
        perspective="user",
        operation_anchor_at=AS_OF,
    ) == result["market_axis"]
    assert budget.snapshot()["used_requests"] == 4


def test_v2_checkpoint_model_rejects_unearned_fallback_coverage_change(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path, with_close=False, with_instrument=False)
    unavailable = _resolve_v2(
        tmp_path,
        source,
        clock=_late_v2_clock(),
        optional_components=(),
    )["market_fallback"]
    unavailable["coverage_after"] = "stale"
    with pytest.raises(ModelValidationError, match="cannot change coverage"):
        _canonical_market_fallback_v2(unavailable, perspective="user")

    failed = _resolve_v2(
        tmp_path / "failed",
        _portfolio_db(
            tmp_path / "failed", with_close=False, with_instrument=False
        ),
        gateway=FakeGateway({"response_status": "failed", "attempt_count": 1}),
        clock=_late_v2_clock(),
        optional_components=(),
    )["market_fallback"]
    failed["coverage_after"] = "stale"
    with pytest.raises(ModelValidationError, match="no success"):
        _canonical_market_fallback_v2(failed, perspective="user")


def test_v2_external_revision_conflict_uses_content_and_information_proof(
    tmp_path: Path,
) -> None:
    def resolved_external(
        name: str, response: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        case_root = tmp_path / name
        source = _portfolio_db(
            case_root, with_close=False, with_instrument=False
        )
        result = _resolve_v2(
            case_root,
            source,
            gateway=FakeGateway(response),
            clock=_late_v2_clock(),
            optional_components=(),
        )
        external = next(
            item
            for item in result["supplemental_sources"]
            if item.get("payload", {}).get("origin")
            == "external_provider_cache"
        )
        return external, result["resolution"]["requirement"]

    original, requirement = resolved_external(
        "original", _verified_v2_response()
    )
    other_basis, other_requirement = resolved_external(
        "other-basis",
        _verified_v2_response(
            publication_basis="provider_revision_publication_metadata.v1"
        ),
    )
    assert other_requirement == requirement
    provenance_conflict = _resolve_external_revision_conflicts_v2(
        [original, other_basis], requirement
    )
    assert all(
        item["payload"]["version_provenance"]["status"] == "conflicted"
        and item["payload"]["perspective_eligibility"]["status"] == "ambiguous"
        for item in provenance_conflict
    )
    conflicting_time, time_requirement = resolved_external(
        "time-conflict",
        _verified_v2_response(
            publicly_available_at="2026-07-16T08:00:00Z",
            publication_basis="provider_revision_publication_metadata.v1",
        ),
    )
    conflicting_content, content_requirement = resolved_external(
        "content-conflict", _verified_v2_response(close="9.999")
    )
    assert time_requirement == content_requirement == requirement
    _canonical_component_source_v2(conflicting_time, requirement)
    _canonical_component_source_v2(conflicting_content, requirement)

    conflicted = _resolve_external_revision_conflicts_v2(
        [original, conflicting_time, conflicting_content], requirement
    )
    assert len(conflicted) == 3
    assert all(
        item["payload"]["version_provenance"]["status"] == "conflicted"
        and item["payload"]["perspective_eligibility"]["status"] == "ambiguous"
        for item in conflicted
    )
    assert conflicted == _resolve_external_revision_conflicts_v2(
        conflicted, requirement
    )


def test_v2_external_source_content_lineage_and_publication_are_tamper_closed(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path, with_close=False, with_instrument=False)
    result = _resolve_v2(
        tmp_path,
        source,
        gateway=FakeGateway(_verified_v2_response()),
        clock=_late_v2_clock(),
        optional_components=(),
    )
    requirement = result["resolution"]["requirement"]
    external = next(
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("origin") == "external_provider_cache"
    )

    changed_value = deepcopy(external)
    changed_value["payload"]["values"]["close"] = "9.999"
    changed_value = _reidentify_v2_source(changed_value)
    with pytest.raises(MarketContextError, match="provenance/content"):
        _canonical_component_source_v2(changed_value, requirement)

    changed_lineage = deepcopy(external)
    changed_lineage["payload"]["cache_lineage"] = []
    changed_lineage = _reidentify_v2_source(changed_lineage)
    with pytest.raises(MarketContextError, match="provenance/content"):
        _canonical_component_source_v2(changed_lineage, requirement)

    changed_publication = deepcopy(external)
    information = changed_publication["payload"]["information_time"]
    information["lower_bound"] = information["upper_bound"] = (
        "2026-07-16T08:00:00Z"
    )
    changed_publication["payload"]["publicly_available_at"] = (
        information["upper_bound"]
    )
    changed_publication = _reidentify_v2_source(changed_publication)
    with pytest.raises(MarketContextError, match="provenance/content"):
        _canonical_component_source_v2(changed_publication, requirement)


def test_v2_external_projection_cannot_replace_complete_origin_cache_entry(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path, with_close=False, with_instrument=False)
    result = _resolve_v2(
        tmp_path,
        source,
        gateway=FakeGateway(_verified_v2_response()),
        clock=_late_v2_clock(),
        optional_components=(),
    )
    requirement = result["resolution"]["requirement"]
    external = next(
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("origin") == "external_provider_cache"
    )
    forged = deepcopy(external)
    payload = forged["payload"]
    payload["values"]["close"] = "9.999"
    content_hash = market_row_content_sha256_v2(
        component="prior_close",
        instrument_id=str(requirement["instrument_id"]),
        row=payload["values"],
    )
    payload["normalized_content_sha256"] = content_hash
    payload["version_provenance"]["content_sha256"] = content_hash
    receipt = payload["origin_fetch_receipt"]
    payload["version_provenance"]["source_ref"] = (
        _provider_publication_source_ref_v2(
            provider_id=str(receipt["provider_id"]),
            endpoint_id=str(receipt["endpoint_id"]),
            publication_basis="official_release_metadata.v1",
            revision_ref=str(payload["version_provenance"]["revision_ref"]),
            content_sha256=content_hash,
            information_time=payload["information_time"],
        )
    )
    forged = _reidentify_v2_source(forged)
    with pytest.raises(MarketContextError, match="origin proof"):
        _canonical_component_source_v2(forged, requirement)


def test_v2_identical_provider_rows_freeze_once_and_are_deterministic(
    tmp_path: Path,
) -> None:
    response = _verified_v2_response()
    response["rows"].append(deepcopy(response["rows"][0]))

    def resolve(case: str) -> tuple[dict[str, Any], FakeGateway]:
        case_root = tmp_path / case
        gateway = FakeGateway(response)
        result = _resolve_v2(
            case_root,
            _portfolio_db(
                case_root, with_close=False, with_instrument=False
            ),
            gateway=gateway,
            clock=_late_v2_clock(),
            optional_components=(),
        )
        return result, gateway

    first, first_gateway = resolve("first")
    second, second_gateway = resolve("second")
    for result, gateway in (
        (first, first_gateway),
        (second, second_gateway),
    ):
        assert len(gateway.calls) == 1
        assert result["market_fallback"]["status"] == "succeeded"
        assert result["market_fallback"]["request_count"] == 1
        external = [
            item
            for item in result["supplemental_sources"]
            if item.get("payload", {}).get("origin")
            == "external_provider_cache"
        ]
        assert len(external) == 1
        assert len(external[0]["payload"]["origin_cache_entry"]["rows"]) == 1
        assert validate_market_context_resolution_v2(result["resolution"])[
            "validation_status"
        ] == "accepted"
    assert first["market_fallback"]["fetch_receipts"] == second[
        "market_fallback"
    ]["fetch_receipts"]
    assert [
        item["source_id"]
        for item in first["supplemental_sources"]
        if item.get("payload", {}).get("origin")
        == "external_provider_cache"
    ] == [
        item["source_id"]
        for item in second["supplemental_sources"]
        if item.get("payload", {}).get("origin")
        == "external_provider_cache"
    ]


@pytest.mark.parametrize(
    ("case", "expected_eligibility", "expected_information"),
    (
        ("exact", "eligible", "verified"),
        ("date_only", "eligible", "verified"),
        ("post_operation", "ineligible", "verified"),
        ("unknown", "unknown", "unknown"),
        ("conflicted", "ambiguous", "conflicted"),
    ),
)
def test_v2_external_instrument_uses_version_boundary_not_operation_anchor(
    tmp_path: Path,
    case: str,
    expected_eligibility: str,
    expected_information: str,
) -> None:
    if case == "date_only":
        response = _instrument_v2_response(
            publicly_available_at=None,
            publication_date="2026-07-16",
            publication_timezone="Asia/Shanghai",
        )
    elif case == "post_operation":
        response = _instrument_v2_response(
            publicly_available_at="2026-07-17T06:00:00Z"
        )
    elif case == "unknown":
        response = _instrument_v2_response(
            publicly_available_at=None,
            publication_status="unknown",
        )
    elif case == "conflicted":
        response = _instrument_v2_response(
            publication_basis="fetch_time"
        )
    else:
        response = _instrument_v2_response()
    gateway = FakeGateway(response)
    result = _resolve_v2(
        tmp_path,
        _portfolio_db(
            tmp_path, with_close=False, with_instrument=False
        ),
        gateway=gateway,
        clock=_late_v2_clock(),
        required_components=("instrument",),
        optional_components=(),
        provider_requests=(_instrument_provider_request(),),
    )
    instrument = next(
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("component") == "instrument"
    )
    payload = instrument["payload"]
    assert len(gateway.calls) == 1
    assert result["market_fallback"]["status"] == "succeeded"
    assert payload["perspective_eligibility"]["status"] == expected_eligibility
    assert payload["information_time"]["status"] == expected_information
    if expected_information == "verified":
        assert payload["effective_at"] == payload["information_time"][
            "upper_bound"
        ]
        assert payload["effective_at"] == payload["publicly_available_at"]
    else:
        assert payload["effective_at"] == payload["fetched_at"]
        assert payload["publicly_available_at"] is None
    assert payload["coverage_effective_at"] == payload["effective_at"]
    assert payload["effective_at"] != AS_OF
    assert result["resolution"]["coverage_after"]["status"] == (
        "satisfied" if expected_eligibility == "eligible" else "missing"
    )
    assert validate_market_context_resolution_v2(result["resolution"])[
        "validation_status"
    ] == "accepted"

    if case == "exact":
        requirement = result["resolution"]["requirement"]
        forged = deepcopy(instrument)
        forged["payload"]["effective_at"] = "2026-07-16T06:59:59Z"
        forged["payload"]["coverage_effective_at"] = (
            "2026-07-16T06:59:59Z"
        )
        forged["effective_at"] = "2026-07-16T06:59:59Z"
        forged = _reidentify_v2_source(forged)
        with pytest.raises(MarketContextError, match="origin proof"):
            _canonical_component_source_v2(forged, requirement)


def test_v2_all_local_component_values_rebuild_from_origin_record(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(
        tmp_path,
        with_optional_rows=True,
        instrument_updated_at="2026-07-17T05:30:00Z",
    )
    result = _resolve_v2(
        tmp_path,
        source,
        optional_components=(
            "instrument",
            "daily",
            "minute",
            "factor",
            "current_industry",
        ),
    )
    requirement = result["resolution"]["requirement"]
    local_by_component = {
        str(item["payload"]["component"]): item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("origin") == "portfolio_local_cache"
    }
    value_mutations = {
        "prior_close": ("close", "9.999"),
        "daily": ("close_price", "9.999"),
        "minute": ("close_price", "9.999"),
        "factor": ("adj_factor", "9.999"),
        "instrument": ("name", "伪造标的"),
        "current_industry": ("industry_name", "伪造行业"),
    }
    assert set(local_by_component) == set(value_mutations)
    for component, (field, forged_value) in value_mutations.items():
        forged = deepcopy(local_by_component[component])
        forged["payload"]["values"][field] = forged_value
        forged = _reclose_local_projection_v2(forged, requirement)
        with pytest.raises(MarketContextError, match="canonical proof"):
            _canonical_component_source_v2(forged, requirement)


@pytest.mark.parametrize(
    "tamper",
    ("value", "source_provider", "source_record_id", "effective"),
)
def test_v2_reidentified_local_prior_close_full_resolution_tamper_is_closed(
    tmp_path: Path, tamper: str
) -> None:
    source = _portfolio_db(tmp_path)
    result = _resolve_v2(tmp_path, source, optional_components=())
    requirement = result["resolution"]["requirement"]
    row_sources = [
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("schema_version")
        == MARKET_CONTEXT_SOURCE_VERSION_V2
    ]
    prior_close = next(
        item
        for item in row_sources
        if item["payload"]["component"] == "prior_close"
    )
    forged = deepcopy(prior_close)
    if tamper == "value":
        assert forged["payload"]["values"]["close"] == "3.929"
        forged["payload"]["values"]["close"] = "9.999"
    elif tamper == "source_provider":
        forged["payload"]["source_provider"] = "forged.provider"
    elif tamper == "source_record_id":
        forged["payload"]["source_record_id"] = "forged-record"
    else:
        forged["payload"]["effective_at"] = "2026-07-16T06:59:59Z"
        forged["payload"]["coverage_effective_at"] = "2026-07-16T06:59:59Z"
    forged = _reclose_local_projection_v2(forged, requirement)
    forged_sources = [
        forged if item["source_id"] == prior_close["source_id"] else item
        for item in row_sources
    ]
    empty_schema_gaps = {
        component: []
        for component in (
            "prior_close",
            "instrument",
            "daily",
            "minute",
            "factor",
            "current_industry",
        )
    }
    coverage = _coverage_v2(requirement, forged_sources, empty_schema_gaps)
    fallback = _not_needed_fallback_v2(
        requirement, coverage, forged_sources
    )
    axis = _market_axis_v2(requirement, coverage, fallback, forged_sources)
    gaps = _market_gaps_v2(requirement, coverage, fallback, forged_sources)
    forged_resolution = _assemble_resolution_v2(
        requirement=requirement,
        coverage_before=coverage,
        coverage_after=coverage,
        fallback=fallback,
        market_axis=axis,
        market_gaps=gaps,
        row_sources=forged_sources,
        source_read=result["resolution"]["source_read"],
    )
    validation = validate_market_context_resolution_v2(forged_resolution)
    assert validation["validation_status"] == "blocked"
    assert "canonical proof" in validation["findings"][0]["message"]


@pytest.mark.parametrize(
    "tamper",
    (
        "source_sha256",
        "source_size",
        "auxiliary_extra",
        "nonempty_wal",
        "unpaired_shm",
    ),
)
def test_v2_source_read_proof_is_structurally_closed(
    tmp_path: Path, tamper: str
) -> None:
    result = _resolve_v2(tmp_path, _portfolio_db(tmp_path))
    hostile = deepcopy(result["resolution"])
    source_read = hostile["source_read"]
    path_state = {
        "size": 0,
        "mtime_ns": 1,
        "device": 1,
        "inode": 1,
        "sha256": "sha256:" + "0" * 64,
    }
    if tamper == "source_sha256":
        source_read["source_sha256"] = "not-a-hash"
    elif tamper == "source_size":
        source_read["source_size"] = -99
    elif tamper == "auxiliary_extra":
        source_read["auxiliary_state"] = {"arbitrary": "accepted"}
    elif tamper == "nonempty_wal":
        source_read["auxiliary_state"]["wal"] = {
            **path_state,
            "size": 1,
        }
    else:
        source_read["auxiliary_state"] = {
            "wal": None,
            "shm": path_state,
        }
    hostile = _reidentify_v2_resolution(hostile)
    validation = validate_market_context_resolution_v2(hostile)
    assert validation["validation_status"] == "blocked"
    assert "source" in validation["findings"][0]["message"].lower()


@pytest.mark.parametrize("tamper", ("locator", "fallback_guard"))
def test_v2_detached_manifest_rejects_derived_projection_drift(
    tmp_path: Path, tamper: str
) -> None:
    source = _portfolio_db(
        tmp_path, with_close=False, with_instrument=False
    )
    result = _resolve_v2(
        tmp_path,
        source,
        perspective="system",
        clock=_late_v2_clock(),
        optional_components=(),
    )
    hostile = deepcopy(result["supplemental_sources"])
    manifest = next(
        item
        for item in hostile
        if item.get("payload", {}).get("schema_version")
        == "investment_review.market_context_manifest.v2"
    )
    if tamper == "locator":
        manifest["locator"] = "forged:anything"
    else:
        guard = manifest["payload"]["market_fallback"]["guard_audit_at"]
        assert isinstance(guard, str) and guard.endswith("Z")
        manifest["payload"]["market_fallback"]["guard_audit_at"] = (
            guard[:-1] + "+00:00"
        )
    validation = validate_market_context_supplemental_sources(
        hostile,
        expected_market_input_content_id=result["market_input_content_id"],
    )
    assert validation["validation_status"] == "blocked"


def test_v2_reidentified_local_factor_cannot_invent_exchange_publication(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(
        tmp_path,
        with_close=False,
        with_instrument=False,
        with_optional_rows=True,
    )
    with sqlite3.connect(source) as connection:
        connection.execute("DELETE FROM daily_bar_observations")
        connection.execute("DELETE FROM minute_bar_observations")
        connection.commit()
    result = _resolve_v2(
        tmp_path,
        source,
        required_components=("factor",),
        optional_components=(),
    )
    requirement = result["resolution"]["requirement"]
    factor = next(
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("component") == "factor"
    )
    forged = deepcopy(factor)
    payload = forged["payload"]
    version = payload["version_provenance"]
    public_at = str(payload["coverage_effective_at"])
    information = {
        "status": "verified",
        "lower_bound": public_at,
        "upper_bound": public_at,
        "basis": MARKET_EXCHANGE_PUBLICATION_RULE_VERSION,
        "method_version": payload["information_time"]["method_version"],
        "revision_ref": version["revision_ref"],
    }
    payload["information_time"] = information
    payload["publicly_available_at"] = public_at
    payload["publicly_available_basis"] = MARKET_EXCHANGE_PUBLICATION_RULE_VERSION
    eligibility = _perspective_eligibility_v2(
        requirement=requirement,
        component="factor",
        information_time=information,
        version_provenance=version,
        system_observed_at=payload["system_observed_at"],
    )
    payload["perspective_eligibility"] = eligibility
    payload["temporal_role"] = eligibility["temporal_role"]
    forged = _reidentify_v2_source(forged)
    forged_sources = [forged]
    forged_coverage = _coverage_v2(
        requirement,
        forged_sources,
        {component: [] for component in (
            "prior_close",
            "instrument",
            "daily",
            "minute",
            "factor",
            "current_industry",
        )},
    )
    assert forged_coverage["status"] == "satisfied"
    fallback = _not_needed_fallback_v2(
        requirement, forged_coverage, forged_sources
    )
    axis = _market_axis_v2(
        requirement, forged_coverage, fallback, forged_sources
    )
    gaps = _market_gaps_v2(
        requirement, forged_coverage, fallback, forged_sources
    )
    forged_resolution = _assemble_resolution_v2(
        requirement=requirement,
        coverage_before=forged_coverage,
        coverage_after=forged_coverage,
        fallback=fallback,
        market_axis=axis,
        market_gaps=gaps,
        row_sources=forged_sources,
        source_read=result["resolution"]["source_read"],
    )
    validation = validate_market_context_resolution_v2(forged_resolution)
    assert validation["validation_status"] == "blocked"
    assert "local source canonical proof" in validation["findings"][0]["message"]


def test_v2_reidentified_external_unknown_row_cannot_invent_publication(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path, with_close=False, with_instrument=False)
    result = _resolve_v2(
        tmp_path,
        source,
        gateway=FakeGateway(
            _verified_v2_response(
                publication_status="unknown",
                public_time_source_ref=None,
            )
        ),
        clock=_late_v2_clock(),
        optional_components=(),
    )
    requirement = result["resolution"]["requirement"]
    external = next(
        item
        for item in result["supplemental_sources"]
        if item.get("payload", {}).get("origin") == "external_provider_cache"
    )
    forged = deepcopy(external)
    payload = forged["payload"]
    version = payload["version_provenance"]
    public_at = str(payload["coverage_effective_at"])
    information = {
        "status": "verified",
        "lower_bound": public_at,
        "upper_bound": public_at,
        "basis": "provider_exact_publication_time.v1",
        "method_version": payload["information_time"]["method_version"],
        "revision_ref": version["revision_ref"],
    }
    version["status"] = "verified"
    receipt = payload["origin_fetch_receipt"]
    version["source_ref"] = _provider_publication_source_ref_v2(
        provider_id=str(receipt["provider_id"]),
        endpoint_id=str(receipt["endpoint_id"]),
        publication_basis="official_release_metadata.v1",
        revision_ref=str(version["revision_ref"]),
        content_sha256=str(version["content_sha256"]),
        information_time=information,
    )
    payload["information_time"] = information
    payload["publicly_available_at"] = public_at
    payload["publicly_available_basis"] = information["basis"]
    eligibility = _perspective_eligibility_v2(
        requirement=requirement,
        component="prior_close",
        information_time=information,
        version_provenance=version,
        system_observed_at=payload["system_observed_at"],
    )
    payload["perspective_eligibility"] = eligibility
    payload["temporal_role"] = eligibility["temporal_role"]
    forged = _reidentify_v2_source(forged)
    forged_sources = [forged]
    empty_gaps = {
        component: []
        for component in (
            "prior_close",
            "instrument",
            "daily",
            "minute",
            "factor",
            "current_industry",
        )
    }
    coverage_after = _coverage_v2(requirement, forged_sources, empty_gaps)
    assert coverage_after["status"] == "satisfied"
    fallback = deepcopy(result["market_fallback"])
    fallback["coverage_after"] = "satisfied"
    fallback["cache_refs"] = _frozen_source_refs_v2(forged_sources)
    fallback = _canonical_fallback_v2(fallback)
    axis = _market_axis_v2(
        requirement, coverage_after, fallback, forged_sources
    )
    gaps = _market_gaps_v2(
        requirement, coverage_after, fallback, forged_sources
    )
    forged_resolution = _assemble_resolution_v2(
        requirement=requirement,
        coverage_before=result["resolution"]["coverage_before"],
        coverage_after=coverage_after,
        fallback=fallback,
        market_axis=axis,
        market_gaps=gaps,
        row_sources=forged_sources,
        source_read=result["resolution"]["source_read"],
    )
    validation = validate_market_context_resolution_v2(forged_resolution)
    assert validation["validation_status"] == "blocked"
    assert "origin proof" in validation["findings"][0]["message"]


def test_v2_validator_rebuilds_coverage_before_without_new_cache_rows(
    tmp_path: Path,
) -> None:
    source = _portfolio_db(tmp_path, with_close=False, with_instrument=False)
    result = _resolve_v2(
        tmp_path,
        source,
        gateway=FakeGateway(_verified_v2_response()),
        clock=_late_v2_clock(),
        optional_components=(),
    )
    assert result["resolution"]["coverage_before"]["status"] == "missing"
    assert result["resolution"]["coverage_after"]["status"] == "satisfied"
    hostile = deepcopy(result["resolution"])
    hostile["coverage_before"] = deepcopy(hostile["coverage_after"])
    hostile = _reidentify_v2_resolution(hostile)
    validation = validate_market_context_resolution_v2(hostile)
    assert validation["validation_status"] == "blocked"
    assert "before" in validation["findings"][0]["message"]
