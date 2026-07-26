from __future__ import annotations

import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest

from src.investment_review.models import (
    CanonicalTradeEvent,
    ModelValidationError,
    SourceDefinition,
)
from src.investment_review.store import (
    APPLICATION_ID,
    PRODUCT_COMPLETION_SCHEMA_VERSION,
    DataConflictError,
    ReviewStore,
    ReviewStoreError,
)


def _seed_trade(store: ReviewStore) -> tuple[SourceDefinition, CanonicalTradeEvent]:
    source = SourceDefinition(
        name="synthetic-product-store",
        kind="sqlite",
        uri="synthetic://portfolio.sqlite3",
        identity_key="synthetic-product-store-v1",
        read_only=True,
    )
    event = CanonicalTradeEvent.build(
        source_id=source.source_id,
        source_record_id="account-1::trade-1",
        event_type="trade",
        occurred_at="2026-07-20T01:30:00Z",
        known_at="2026-07-20T01:30:00Z",
        symbol="600000.SH",
        timezone="UTC",
        account="account-1",
        market="SH",
        side="BUY",
        quantity="100",
        price="10",
        gross_amount="1000",
        cash_amount="-1000",
        fees="0",
        currency="CNY",
        raw_payload={"source_row": {"external_id": "trade-1", "fees": "0"}},
    )
    store.import_events(source, [event], manifest={"fixture": "product-store"})
    return source, event


def _initialized_store(path: Path) -> tuple[ReviewStore, CanonicalTradeEvent]:
    store = ReviewStore(path)
    store.initialize()
    store.initialize_product_completion()
    _, event = _seed_trade(store)
    return store, event


def _tables(path: Path) -> set[str]:
    conn = sqlite3.connect(path)
    try:
        return {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
    finally:
        conn.close()


def test_product_schema_requires_explicit_opt_in_and_preserves_v2_boundary(
    tmp_path: Path,
) -> None:
    database = tmp_path / "review.sqlite3"
    store = ReviewStore(database)
    store.initialize()
    core_tables = _tables(database)

    assert "fee_profiles" not in core_tables
    assert store.status()["product_completion_schema_version"] is None
    store.initialize()
    assert _tables(database) == core_tables

    first = store.initialize_product_completion()
    second = store.initialize_product_completion()
    assert first["product_completion_schema_version"] == PRODUCT_COMPLETION_SCHEMA_VERSION
    assert second == first
    status = store.status()
    assert status["product_completion_schema_version"] == 1
    assert status["counts"]["fee_profiles"] == 0
    assert status["counts"]["fee_projections"] == 0
    assert status["counts"]["fee_corrections"] == 0
    assert status["counts"]["review_runs"] == 0
    assert status["counts"]["review_run_status_events"] == 0

    # An existing, fully initialized v2 sidecar remains core-only until a caller
    # explicitly selects it for the product feature.
    existing = tmp_path / "existing-v2.sqlite3"
    existing_store = ReviewStore(existing)
    existing_store.initialize()
    with existing_store.connection() as conn:
        with conn:
            conn.execute("CREATE TABLE legacy_marker(value TEXT NOT NULL)")
            conn.execute("INSERT INTO legacy_marker VALUES ('preserved')")
    existing_tables = _tables(existing)
    existing_bytes = existing.read_bytes()
    existing_store.initialize()
    assert _tables(existing) == existing_tables
    assert existing.read_bytes() == existing_bytes
    assert "fee_profiles" not in existing_tables
    with existing_store.connection(read_only=True) as conn:
        assert conn.execute("SELECT value FROM legacy_marker").fetchone()[0] == "preserved"

    legacy = tmp_path / "legacy-v1.sqlite3"
    conn = sqlite3.connect(legacy)
    conn.execute(f"PRAGMA application_id = {APPLICATION_ID}")
    conn.execute("PRAGMA user_version = 1")
    conn.execute("CREATE TABLE schema_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("INSERT INTO schema_meta VALUES ('schema_version', '1')")
    conn.commit()
    conn.close()
    with pytest.raises(ReviewStoreError, match="schema_version=1"):
        ReviewStore(legacy).initialize_product_completion()


def test_event_observation_evidence_is_read_only_and_keeps_p2c_shape(
    tmp_path: Path,
) -> None:
    database = tmp_path / "review.sqlite3"
    store, event = _initialized_store(database)
    projection_before = store.list_episode_projection_inputs()

    source = SourceDefinition(
        name="synthetic-product-store",
        kind="sqlite",
        uri="synthetic://portfolio.sqlite3",
        identity_key="synthetic-product-store-v1",
        read_only=True,
    )
    repeat = store.import_events(
        source,
        [event],
        manifest={"fixture": "product-store-repeat"},
    )
    assert repeat["inserted"] == 0
    assert repeat["skipped"] == 1
    database_before = database.read_bytes()

    evidence = store.list_event_observation_evidence(
        event_ids=[event.event_id],
        account="account-1",
        symbol="600000.sh",
    )
    projection_after = store.list_episode_projection_inputs()

    assert projection_after == projection_before
    assert set(projection_after[0]) == set(projection_before[0])
    assert database.read_bytes() == database_before
    assert len(evidence) == 1
    observed = evidence[0]
    assert observed["event_id"] == event.event_id
    assert observed["source_id"] == source.source_id
    assert observed["payload_sha256"] == event.payload_sha256
    assert observed["raw_payload"] == dict(event.raw_payload)
    assert observed["ingested_at"]
    assert observed["first_ingest"] == {
        "run_id": projection_before[0]["first_ingest_run_id"],
        "outcome": "INSERTED",
        "observed_at": observed["first_ingest"]["observed_at"],
        "observation_payload_sha256": event.payload_sha256,
        "source_id": source.source_id,
        "source_fingerprint": source.fingerprint,
        "started_at": observed["first_ingest"]["started_at"],
        "finished_at": observed["first_ingest"]["finished_at"],
        "status": "COMPLETED",
        "manifest": {"fixture": "product-store"},
    }
    assert observed["first_ingest"]["observed_at"]
    assert observed["first_ingest"]["started_at"]
    assert observed["first_ingest"]["finished_at"]
    assert store.list_event_observation_evidence(event_ids=[]) == []
    assert store.list_event_observation_evidence(symbol="000001.SZ") == []

    with store.connection(read_only=True) as conn:
        outcomes = conn.execute(
            """
            SELECT outcome, observed_at
            FROM ingest_run_events
            WHERE event_id = ?
            ORDER BY observed_at, run_id
            """,
            (event.event_id,),
        ).fetchall()
    assert {str(row["outcome"]) for row in outcomes} == {"INSERTED", "SKIPPED"}
    inserted_observation = next(
        row for row in outcomes if str(row["outcome"]) == "INSERTED"
    )
    assert (
        observed["first_ingest"]["observed_at"]
        == inserted_observation["observed_at"]
    )


def test_fee_projection_unknown_and_append_only_corrections_preserve_event(
    tmp_path: Path,
) -> None:
    store, event = _initialized_store(tmp_path / "review.sqlite3")
    event_before = store.list_events()[0]

    unknown = {
        "projection_id": "fee_projection_unknown",
        "event_id": event.event_id,
        "status": "unknown",
        "amount": None,
        "currency": "CNY",
        "source_fees": "0",
        "method": "historical_median_rate",
        "method_version": "v1",
        "sample_count": 0,
        "profile_id": None,
        "reason_code": "insufficient_samples",
        "projected_at": "2026-07-20T02:00:00Z",
        "provenance": {"source_fee_actual": False},
    }
    assert store.save_fee_projection(unknown)["status"] == "INSERTED"
    assert store.save_fee_projection(unknown)["status"] == "SKIPPED"
    current = store.get_effective_fee(event.event_id)
    assert current["status"] == "unknown"
    assert current["amount"] is None
    assert current["source"] == "projection"

    drifted = deepcopy(unknown)
    drifted["reason_code"] = "changed_after_creation"
    with pytest.raises(DataConflictError, match="changed after creation"):
        store.save_fee_projection(drifted)

    profile = {
        "profile_id": "fee_profile_account_asset_buy",
        "profile_key": "account-1|equity|BUY",
        "method": "historical_median_rate",
        "method_version": "historical_median_rate_v1",
        "sample_count": 5,
        "rate": "0.001",
        "currency": "CNY",
        "fallback_level": "account_asset_side",
        "computed_at": "2026-07-20T02:01:00Z",
        "provenance": {"sample_event_ids": [f"sample-{index}" for index in range(5)]},
    }
    assert store.save_fee_profile(profile)["status"] == "INSERTED"
    assert store.save_fee_profile(profile)["status"] == "SKIPPED"
    profile_drift = deepcopy(profile)
    profile_drift["rate"] = "0.002"
    with pytest.raises(DataConflictError, match="changed after creation"):
        store.save_fee_profile(profile_drift)

    too_small_profile = {
        **profile,
        "profile_id": "fee_profile_too_small",
        "sample_count": 4,
    }
    with pytest.raises(ModelValidationError, match="at least 5 samples"):
        store.save_fee_profile(too_small_profile)
    zero_rate_profile = {
        **profile,
        "profile_id": "fee_profile_zero_rate",
        "rate": "0",
    }
    with pytest.raises(ModelValidationError, match="positive rate"):
        store.save_fee_profile(zero_rate_profile)
    unsupported_profile = {
        **profile,
        "profile_id": "fee_profile_unsupported_method",
        "method_version": "v1",
    }
    with pytest.raises(ModelValidationError, match="historical_median_rate_v1"):
        store.save_fee_profile(unsupported_profile)

    estimated = {
        "projection_id": "fee_projection_estimated",
        "event_id": event.event_id,
        "status": "estimated",
        "amount": "1.00",
        "currency": "CNY",
        "source_fees": "0",
        "method": "historical_median_rate",
        "method_version": "historical_median_rate_v1",
        "sample_count": 5,
        "profile_id": profile["profile_id"],
        "reason_code": None,
        "projected_at": "2026-07-20T02:02:00Z",
        "provenance": {"rounding": "0.01"},
    }
    mismatched_projection = {
        **estimated,
        "projection_id": "fee_projection_profile_mismatch",
        "sample_count": 6,
    }
    with pytest.raises(ReviewStoreError, match="FEE_PROFILE_PROJECTION_MISMATCH"):
        store.save_fee_projection(mismatched_projection)
    store.save_fee_projection(estimated)
    before_correction = store.get_effective_fee(
        event.event_id,
        as_of="2026-07-20T02:02:00Z",
        knowledge_cutoff="2026-07-20T02:02:00Z",
    )
    assert before_correction["status"] == "estimated"
    assert before_correction["amount"] == "1.00"
    cutoff_limited = store.get_effective_fee(
        event.event_id,
        as_of="2026-07-20T02:02:00Z",
        knowledge_cutoff="2026-07-20T02:01:00Z",
    )
    assert cutoff_limited["projection_id"] == unknown["projection_id"]
    assert cutoff_limited["status"] == "unknown"

    correction = {
        "correction_id": "fee_correction_1",
        "event_id": event.event_id,
        "status": "actual",
        "amount": "1.23",
        "currency": "CNY",
        "effective_at": "2026-07-20T02:03:00Z",
        "known_at": "2026-07-20T02:03:00Z",
        "reviewer_ref": "synthetic-human",
        "reason": "Confirmed from a synthetic settlement fixture.",
        "supersedes_correction_id": None,
        "provenance": {"source": "synthetic-fixture"},
    }
    assert store.append_fee_correction(correction)["status"] == "INSERTED"
    assert store.append_fee_correction(correction)["status"] == "SKIPPED"

    replacement = {
        **correction,
        "correction_id": "fee_correction_2",
        "status": "unknown",
        "amount": None,
        "effective_at": "2026-07-20T02:04:00Z",
        "known_at": "2026-07-20T02:04:00Z",
        "reason": "The synthetic settlement fixture was withdrawn.",
        "supersedes_correction_id": correction["correction_id"],
    }
    store.append_fee_correction(replacement)
    corrections = store.list_fee_corrections(event_id=event.event_id)
    assert [item["correction_id"] for item in corrections] == [
        "fee_correction_1",
        "fee_correction_2",
    ]
    current = store.get_effective_fee(event.event_id)
    assert current["status"] == "unknown"
    assert current["amount"] is None
    assert current["source"] == "correction"
    assert current["base_projection_id"] == estimated["projection_id"]

    correction_drift = deepcopy(correction)
    correction_drift["amount"] = "9.99"
    with pytest.raises(DataConflictError, match="changed after creation"):
        store.append_fee_correction(correction_drift)

    invalid_actual = deepcopy(unknown)
    invalid_actual.update(
        projection_id="invalid_actual_zero",
        status="actual",
        amount="0",
    )
    with pytest.raises(ModelValidationError, match="positive amount"):
        store.save_fee_projection(invalid_actual)

    unproven_actual = {
        **unknown,
        "projection_id": "invalid_actual_provenance",
        "status": "actual",
        "amount": "1.23",
        "source_fees": "1.23",
        "method": "source_fee",
        "method_version": "source_fee_actual_v1",
        "reason_code": None,
        "projected_at": "2026-07-20T02:05:00Z",
        "provenance": {"source_fee_actual": False},
    }
    with pytest.raises(
        ModelValidationError, match="provenance.source_fee_actual=true"
    ):
        store.save_fee_projection(unproven_actual)
    wrong_actual_method = {
        **unproven_actual,
        "projection_id": "invalid_actual_method",
        "provenance": {"source_fee_actual": True},
        "method": "historical_median_rate",
        "method_version": "historical_median_rate_v1",
    }
    with pytest.raises(ModelValidationError, match="source_fee_actual_v1"):
        store.save_fee_projection(wrong_actual_method)

    assert store.list_events()[0] == event_before


def test_review_run_status_ledger_is_idempotent_unknown_safe_and_deterministic(
    tmp_path: Path,
) -> None:
    store, _ = _initialized_store(tmp_path / "review.sqlite3")
    run = {
        "run_id": "review_run_1",
        "run_key": "single:account-1:2026-07-20T02:00:00Z",
        "scope": "single",
        "requested_at": "2026-07-20T02:00:00Z",
        "source_cutoff": "2026-07-20T01:59:59Z",
        "trigger": "manual",
        "parameters": {"event_id": "synthetic-event"},
    }
    assert store.save_review_run(run)["status"] == "INSERTED"
    assert store.save_review_run(run)["status"] == "SKIPPED"
    assert store.get_review_run(run["run_key"])["status"] == "unknown"

    failed = {
        "run_event_id": "review_run_1_failed",
        "run_id": run["run_id"],
        "status": "failed",
        "occurred_at": "2026-07-20T02:02:00Z",
        "known_at": "2026-07-20T02:02:00Z",
        "details": {"error_code": "SYNTHETIC_FAILURE"},
    }
    running = {
        "run_event_id": "review_run_1_running",
        "run_id": run["run_id"],
        "status": "running",
        "occurred_at": "2026-07-20T02:01:00Z",
        "known_at": "2026-07-20T02:01:00Z",
        "details": {},
    }
    # Arrival order is not used as business order.
    store.append_review_run_status(failed)
    store.append_review_run_status(running)
    assert store.append_review_run_status(failed)["status"] == "SKIPPED"

    projection = store.get_review_run(run["run_id"])
    assert projection["status"] == "failed"
    assert [item["status"] for item in projection["history"]] == [
        "running",
        "failed",
    ]
    earlier = store.get_review_run(
        run["run_id"],
        as_of="2026-07-20T02:01:30Z",
        knowledge_cutoff="2026-07-20T02:01:30Z",
    )
    assert earlier["status"] == "running"

    event_drift = deepcopy(failed)
    event_drift["status"] = "blocked"
    with pytest.raises(DataConflictError, match="changed after creation"):
        store.append_review_run_status(event_drift)

    same_time = {
        **failed,
        "run_event_id": "review_run_1_same_time",
        "status": "blocked",
    }
    with pytest.raises(ReviewStoreError, match="AMBIGUOUS_REVIEW_RUN_STATUS_TIME"):
        store.append_review_run_status(same_time)

    run_drift = deepcopy(run)
    run_drift["trigger"] = "startup"
    with pytest.raises(DataConflictError, match="changed after creation"):
        store.save_review_run(run_drift)

    listed = store.list_review_runs(scope="single", status="failed")
    assert [item["run"]["run_id"] for item in listed] == [run["run_id"]]


def test_product_record_replay_is_independent_of_insert_order(tmp_path: Path) -> None:
    left, left_event = _initialized_store(tmp_path / "left.sqlite3")
    right, right_event = _initialized_store(tmp_path / "right.sqlite3")
    assert left_event.event_id == right_event.event_id

    profiles = [
        {
            "profile_id": f"profile_{suffix}",
            "profile_key": f"asset|{suffix}|BUY",
            "method": "historical_median_rate",
            "method_version": "historical_median_rate_v1",
            "sample_count": 5,
            "rate": rate,
            "currency": "CNY",
            "fallback_level": "asset_side",
            "computed_at": timestamp,
            "provenance": {"fixture": suffix},
        }
        for suffix, rate, timestamp in (
            ("a", "0.001", "2026-07-20T02:00:00Z"),
            ("b", "0.002", "2026-07-20T02:01:00Z"),
        )
    ]
    for profile in profiles:
        left.save_fee_profile(profile)
    for profile in reversed(profiles):
        right.save_fee_profile(profile)
    assert left.list_fee_profiles() == right.list_fee_profiles()

    run = {
        "run_id": "deterministic_run",
        "run_key": "weekly:2026-W30",
        "scope": "weekly",
        "requested_at": "2026-07-20T03:00:00Z",
        "source_cutoff": "2026-07-20T02:59:59Z",
        "trigger": "scheduled",
        "parameters": {},
    }
    events = [
        {
            "run_event_id": "deterministic_running",
            "run_id": run["run_id"],
            "status": "running",
            "occurred_at": "2026-07-20T03:01:00Z",
            "known_at": "2026-07-20T03:01:00Z",
            "details": {},
        },
        {
            "run_event_id": "deterministic_partial",
            "run_id": run["run_id"],
            "status": "partial",
            "occurred_at": "2026-07-20T03:02:00Z",
            "known_at": "2026-07-20T03:02:00Z",
            "details": {"gap": "synthetic snapshot missing"},
        },
    ]
    for store, ordered in ((left, events), (right, list(reversed(events)))):
        store.save_review_run(run)
        for event in ordered:
            store.append_review_run_status(event)
    assert left.get_review_run(run["run_id"]) == right.get_review_run(run["run_id"])
