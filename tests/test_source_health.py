from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.ingest.source_health import (
    CIRCUIT_OPEN,
    DEGRADED,
    HEALTHY,
    empty_health_ledger,
    record_failure,
    record_success,
    should_attempt,
    source_state,
)


def test_403_opens_circuit_and_is_not_immediately_retried() -> None:
    now = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)
    ledger = record_failure(
        empty_health_ledger(),
        source_name="eastmoney_push2",
        capability="fund_flow_context",
        http_status=403,
        observed_at=now,
    )
    assert source_state(ledger, "eastmoney_push2", now=now) == CIRCUIT_OPEN
    assert not should_attempt(ledger, "eastmoney_push2", now=now + timedelta(hours=1))
    assert should_attempt(ledger, "eastmoney_push2", now=now + timedelta(hours=25))


def test_transient_failures_degrade_then_open_circuit() -> None:
    ledger = empty_health_ledger()
    for _ in range(2):
        ledger = record_failure(
            ledger,
            source_name="tencent_finance",
            capability="daily_price",
            http_status=503,
        )
    assert source_state(ledger, "tencent_finance") == DEGRADED
    ledger = record_failure(
        ledger,
        source_name="tencent_finance",
        capability="daily_price",
        http_status=503,
    )
    assert source_state(ledger, "tencent_finance") == CIRCUIT_OPEN


def test_success_resets_failure_state() -> None:
    ledger = record_failure(
        empty_health_ledger(),
        source_name="tushare",
        capability="financial_statements",
        error_class="timeout",
    )
    ledger = record_success(
        ledger,
        source_name="tushare",
        capability="financial_statements",
        fields=("ts_code", "ann_date", "end_date"),
    )
    assert source_state(ledger, "tushare") == HEALTHY
    assert ledger["sources"]["tushare"]["consecutive_failures"] == 0
