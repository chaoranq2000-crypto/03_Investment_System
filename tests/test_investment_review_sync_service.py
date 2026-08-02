from __future__ import annotations

import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from src.investment_review import sync_service as sync_module
from src.investment_review.cli import main as review_cli_main
from src.investment_review.ingest import MappingError, reviewed_mapping_content_sha256
from src.investment_review.introspection import table_schema_sha256
from src.investment_review.store import DataConflictError, ReviewStore, ReviewStoreError
from src.investment_review.sync_service import (
    ReviewSyncService,
    SyncConflictError,
    SyncServiceError,
    project_review_fees,
    resolve_review_db,
    review_sync_status,
    sync_after_portfolio_commit,
    sync_review_events,
)


LEDGER_SQL = """
CREATE TABLE instruments (
    ts_code TEXT PRIMARY KEY,
    asset_type TEXT NOT NULL
);
CREATE TABLE ledger_entries (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    event_date TEXT NOT NULL,
    event_time TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    ts_code TEXT NOT NULL,
    quantity TEXT NOT NULL DEFAULT '0',
    price TEXT NOT NULL DEFAULT '0',
    gross_amount TEXT NOT NULL DEFAULT '0',
    fees TEXT NOT NULL DEFAULT '0',
    cash_amount TEXT NOT NULL DEFAULT '0',
    external_id TEXT NOT NULL DEFAULT '',
    dedupe_key TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""


def _default_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index in range(1, 6):
        rows.append(
            {
                "account_id": "acct",
                "event_date": f"2026-01-0{index}",
                "event_time": "10:00:00",
                "event_type": "BUY",
                "ts_code": "000001.SZ",
                "quantity": "10",
                "price": "100",
                "gross_amount": "1000",
                "fees": "1",
                "cash_amount": "-1001",
                "external_id": f"actual-{index}",
                "dedupe_key": f"actual-{index}",
                "note": "fee_source=broker_actual",
                "created_at": "2026-07-14T00:00:00Z",
            }
        )
    rows.extend(
        [
            {
                "account_id": "acct",
                "event_date": "2026-01-06",
                "event_time": "10:00:00",
                "event_type": "BUY",
                "ts_code": "000001.SZ",
                "quantity": "20",
                "price": "100",
                "gross_amount": "2000",
                "fees": "0",
                "cash_amount": "-2000",
                "external_id": "target",
                "dedupe_key": "target",
                "note": "",
                "created_at": "2026-07-14T00:00:00Z",
            },
            {
                "account_id": "acct",
                "event_date": "2026-01-07",
                "event_time": "10:00:00",
                "event_type": "SELL",
                "ts_code": "000002.SZ",
                "quantity": "10",
                "price": "100",
                "gross_amount": "1000",
                "fees": "0",
                "cash_amount": "1000",
                "external_id": "unknown-asset",
                "dedupe_key": "unknown-asset",
                "note": "",
                "created_at": "2026-07-14T00:00:00Z",
            },
        ]
    )
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fixture(
    root: Path,
    *,
    rows: list[dict[str, str]] | None = None,
) -> tuple[Path, Path, Path]:
    source = root / "source" / "portfolio.sqlite3"
    mapping_path = root / "config" / "investment_review.portfolio.reviewed.json"
    generated_path = root / "config" / "investment_review.portfolio.generated.json"
    schema_path = root / "reports" / "investment_review" / "phase1" / "schema_manifest.json"
    review_db = root / "candidate" / "investment_review.sqlite3"
    source.parent.mkdir(parents=True)
    mapping_path.parent.mkdir(parents=True)
    schema_path.parent.mkdir(parents=True)

    conn = sqlite3.connect(source)
    conn.row_factory = sqlite3.Row
    conn.executescript(LEDGER_SQL)
    conn.executemany(
        "INSERT INTO instruments(ts_code, asset_type) VALUES (?, ?)",
        [("000001.SZ", "equity"), ("000002.SZ", "unknown")],
    )
    payload_rows = [
        {**row, "note": str(row.get("note") or "")}
        for row in (rows if rows is not None else _default_rows())
    ]
    conn.executemany(
        """
        INSERT INTO ledger_entries(
            account_id, event_date, event_time, event_type, ts_code,
            quantity, price, gross_amount, fees, cash_amount, external_id,
            dedupe_key, note, created_at
        ) VALUES (
            :account_id, :event_date, :event_time, :event_type, :ts_code,
            :quantity, :price, :gross_amount, :fees, :cash_amount, :external_id,
            :dedupe_key, :note, :created_at
        )
        """,
        payload_rows,
    )
    schema_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='ledger_entries'"
    ).fetchone()
    columns = [dict(row) for row in conn.execute("PRAGMA table_info(ledger_entries)")]
    schema_sha = table_schema_sha256(columns, schema_row[0])
    conn.commit()
    conn.close()

    generated_path.write_text(
        json.dumps({"fixture": "generated"}, sort_keys=True), encoding="utf-8"
    )
    schema_path.write_text(
        json.dumps({"fixture": "schema", "table_schema_sha256": schema_sha}, sort_keys=True),
        encoding="utf-8",
    )
    mapping: dict[str, object] = {
        "mapping_version": 1,
        "source": {
            "name": "fixture-ledger",
            "kind": "portfolio_sqlite",
            "uri": str(source.resolve()),
            "timezone": "Asia/Shanghai",
            "read_only": True,
        },
        "sqlite": {"table": "ledger_entries"},
        "mapping": {
            "record_id": {"join": ["account_id", "external_id"], "separator": "::"},
            "occurred_at": {"join": ["event_date", "event_time"], "separator": " "},
            "known_at": None,
            "symbol": "ts_code",
            "side": "event_type",
            "quantity": "quantity",
            "price": "price",
            "gross_amount": "gross_amount",
            "cash_amount": "cash_amount",
            "fees": "fees",
            "account": "account_id",
            "market": None,
            "currency": {"constant": "CNY"},
            "event_type": "event_type",
        },
        "values": {
            "side": {
                "BUY": "BUY",
                "SELL": "SELL",
                "DIVIDEND": "OTHER",
                "CASH_FEE": "OTHER",
            }
        },
        "generated_from": {
            "database": str(source.resolve()),
            "table": "ledger_entries",
            "table_schema_sha256": schema_sha,
            "trade_score": 5,
            "review_required": True,
            "missing_required_fields": [],
        },
        "review": {
            "status": "reviewed",
            "reviewed_at": "2026-07-23T15:49:28+08:00",
            "reviewed_by": "workspace_user",
            "schema_manifest_path": str(schema_path.relative_to(root)),
            "schema_manifest_sha256": _sha256(schema_path),
            "generated_mapping_path": str(generated_path.relative_to(root)),
            "generated_mapping_sha256": _sha256(generated_path),
            "reason": "synthetic reviewed fixture",
        },
    }
    mapping["review"]["mapping_content_sha256"] = reviewed_mapping_content_sha256(mapping)  # type: ignore[index]
    mapping_path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return source, mapping_path, review_db


def _initialize_product_sidecar(path: Path) -> ReviewStore:
    path.parent.mkdir(parents=True, exist_ok=True)
    store = ReviewStore(path)
    store.initialize()
    store.initialize_product_completion()
    return store


def _insert_ledger_row(source: Path, row: dict[str, str]) -> None:
    conn = sqlite3.connect(source)
    try:
        conn.execute(
            """
            INSERT INTO ledger_entries(
                account_id, event_date, event_time, event_type, ts_code,
                quantity, price, gross_amount, fees, cash_amount, external_id,
                dedupe_key, created_at
            ) VALUES (
                :account_id, :event_date, :event_time, :event_type, :ts_code,
                :quantity, :price, :gross_amount, :fees, :cash_amount, :external_id,
                :dedupe_key, :created_at
            )
            """,
            row,
        )
        conn.commit()
    finally:
        conn.close()


def test_review_db_resolution_is_root_stable_and_has_fixed_precedence(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    assert resolve_review_db(
        explicit="explicit/review.sqlite3",
        repo_root=root,
        env={"INVESTMENT_REVIEW_DB": "env/review.sqlite3"},
    ) == (root / "explicit" / "review.sqlite3").resolve()
    assert resolve_review_db(
        repo_root=root,
        env={"INVESTMENT_REVIEW_DB": "env/review.sqlite3"},
    ) == (root / "env" / "review.sqlite3").resolve()
    assert resolve_review_db(repo_root=root, env={}) == (
        root / "data" / "db" / "investment_review.sqlite3"
    ).resolve()
    with pytest.raises(SyncServiceError, match="inside the selected repository"):
        resolve_review_db(
            explicit=tmp_path / "outside" / "investment_review.sqlite3",
            repo_root=root,
            env={},
        )


def test_legacy_doctor_failure_does_not_overwrite_its_output(tmp_path: Path) -> None:
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    output = tmp_path / "schema_manifest.json"
    output.write_text("preserve-existing-artifact", encoding="utf-8")

    result = review_cli_main(
        ["doctor", "--search-root", str(empty_root), "--out", str(output)]
    )

    assert result == 2
    assert output.read_text(encoding="utf-8") == "preserve-existing-artifact"


def test_dry_run_requires_review_lock_and_never_creates_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    source, mapping_path, review_db = _write_fixture(root)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    before = _sha256(source)
    receipt = sync_review_events(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        dry_run=True,
        repo_root=root,
    )
    assert receipt["status"] == "dry_run"
    assert receipt["source"]["mode"] == "ro"
    assert receipt["source"]["query_only"] is True
    assert receipt["source"]["quick_check"] == "ok"
    assert receipt["counts"]["source_seen"] == 7
    assert receipt["counts"]["sidecar_seen"] == 0
    assert receipt["counts"]["unsynced"] == 7
    assert receipt["fees"]["status_counts"] == {
        "actual": 5,
        "estimated": 1,
        "unknown": 1,
    }
    assert receipt["sidecar"]["mutated"] is False
    assert not review_db.exists()
    assert _sha256(source) == before

    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    mapping["review"]["status"] = "unreviewed"
    mapping["review"]["mapping_content_sha256"] = reviewed_mapping_content_sha256(mapping)
    mapping_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    with pytest.raises(MappingError, match="review.status='reviewed'"):
        sync_review_events(
            source,
            review_db=review_db,
            mapping_path=mapping_path,
            dry_run=True,
            repo_root=root,
        )
    assert not review_db.exists()


def test_fee_asset_type_dependency_changes_the_semantic_cutoff(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    source, mapping_path, review_db = _write_fixture(root)
    before = sync_review_events(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        dry_run=True,
        repo_root=root,
    )

    conn = sqlite3.connect(source)
    conn.execute(
        "UPDATE instruments SET asset_type='unknown' WHERE ts_code='000001.SZ'"
    )
    conn.commit()
    conn.close()
    after = sync_review_events(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        dry_run=True,
        repo_root=root,
    )

    assert before["source"]["cutoff"]["cutoff_id"] != after["source"]["cutoff"]["cutoff_id"]
    assert before["source"]["cutoff"]["asset_type_sha256"] != after["source"]["cutoff"]["asset_type_sha256"]
    assert before["fees"]["status_counts"] == {
        "actual": 5,
        "estimated": 1,
        "unknown": 1,
    }
    assert after["fees"]["status_counts"] == {
        "actual": 5,
        "estimated": 0,
        "unknown": 2,
    }


def test_apply_requires_explicit_product_schema(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    source, mapping_path, review_db = _write_fixture(root)
    review_db.parent.mkdir(parents=True)
    store = ReviewStore(review_db)
    store.initialize()

    with pytest.raises(ReviewStoreError, match="product-init"):
        sync_review_events(
            source,
            review_db=review_db,
            mapping_path=mapping_path,
            repo_root=root,
        )
    assert store.status()["counts"]["trade_events"] == 0
    assert store.status()["product_completion_schema_version"] is None


def test_apply_is_exactly_reconciled_idempotent_and_persists_fee_states(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    source, mapping_path, review_db = _write_fixture(root)
    store = _initialize_product_sidecar(review_db)
    before = _sha256(source)

    first = sync_review_events(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )
    second = sync_review_events(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )

    assert first["counts"]["source_seen"] == first["counts"]["sidecar_seen"] == 7
    assert first["counts"]["unsynced"] == 0
    assert first["counts"]["inserted"] == 7
    assert first["counts"]["skipped"] == 0
    assert second["counts"]["source_seen"] == second["counts"]["sidecar_seen"] == 7
    assert second["counts"]["unsynced"] == 0
    assert second["counts"]["inserted"] == 0
    assert second["counts"]["skipped"] == 7
    assert first["source"]["cutoff"] == second["source"]["cutoff"]
    assert first["fees"]["status_counts"] == {
        "actual": 5,
        "estimated": 1,
        "unknown": 1,
    }
    assert first["fees"]["profiles_inserted"] == 1
    assert first["fees"]["projections_inserted"] == 7
    assert second["fees"]["profiles_inserted"] == 0
    assert second["fees"]["profiles_skipped"] == 1
    assert second["fees"]["projections_inserted"] == 0
    assert second["fees"]["projections_skipped"] == 7

    projection_before = store.list_episode_projection_inputs()
    evidence_before = store.list_event_observation_evidence()
    evidence_after = store.list_event_observation_evidence(
        event_ids=[str(item["event_id"]) for item in projection_before]
    )
    projection_after = store.list_episode_projection_inputs()
    assert projection_after == projection_before
    assert evidence_after == evidence_before
    assert len(evidence_after) == 7
    assert all(item["first_ingest"]["outcome"] == "INSERTED" for item in evidence_after)
    assert all(item["first_ingest"]["status"] == "COMPLETED" for item in evidence_after)
    assert all(item["first_ingest"]["observed_at"] for item in evidence_after)
    assert all(item["ingested_at"] for item in evidence_after)
    assert all(
        item["first_ingest"]["observation_payload_sha256"] == item["payload_sha256"]
        for item in evidence_after
    )
    assert {
        item["raw_payload"]["source_row"]["created_at"] for item in evidence_after
    } == {"2026-07-14T00:00:00Z"}
    assert all(
        item["first_ingest"]["manifest"]["adapter"]
        == "investment_review_sync_service"
        for item in evidence_after
    )
    assert all(
        "first_ingest" not in item
        and "first_inserted_observed_at" not in item
        for item in projection_after
    )

    projections = store.list_fee_projections()
    assert len(projections) == 7
    target_id = next(
        event["event_id"]
        for event in store.list_events()
        if event["source_record_id"] == "acct::target"
    )
    target = next(item for item in projections if item["event_id"] == target_id)
    assert target["status"] == "estimated"
    assert target["amount"] == "2.00"
    assert target["source_fees"] == "0"
    assert target["method_version"] == "historical_median_rate_v1"
    assert target["sample_count"] == 5
    assert target["provenance"]["source_fee_preserved"] == "0"

    unknown_id = next(
        event["event_id"]
        for event in store.list_events()
        if event["source_record_id"] == "acct::unknown-asset"
    )
    unknown = next(item for item in projections if item["event_id"] == unknown_id)
    assert unknown["status"] == "unknown"
    assert unknown["amount"] is None
    assert unknown["source_fees"] == "0"
    assert unknown["reason_code"] == "UNRECOGNIZED_ASSET_TYPE"
    assert _sha256(source) == before

    status = review_sync_status(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )
    assert status["status"] == "healthy"
    assert status["lag"]["unsynced"] == 0
    assert status["fees"] == {"actual": 5, "estimated": 1, "unknown": 1}
    assert status["fee_details"]["base_projection_counts"] == status["fees"]
    assert status["last_success"]["status"] == "succeeded"

    store.append_fee_correction(
        {
            "correction_id": "fee_correction_target_actual",
            "event_id": target_id,
            "status": "actual",
            "amount": "2.10",
            "currency": "CNY",
            "effective_at": "2026-01-08T00:00:00Z",
            "known_at": "2026-01-08T00:00:00Z",
            "reviewer_ref": "synthetic-human",
            "reason": "Synthetic settlement confirmation.",
            "supersedes_correction_id": None,
            "provenance": {"source": "synthetic-fixture"},
        }
    )
    corrected_status = review_sync_status(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )
    assert corrected_status["fees"] == {
        "actual": 6,
        "estimated": 0,
        "unknown": 1,
    }
    assert corrected_status["fee_details"]["base_projection_counts"] == {
        "actual": 5,
        "estimated": 1,
        "unknown": 1,
    }
    assert corrected_status["fee_details"]["correction_count"] == 1


def test_rule_derived_positive_fee_is_not_an_actual_profile_sample(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    rows = _default_rows()
    rows[0]["note"] = (
        "fee_source=rule_derived; fee_rule=historical_fee_rule_v1"
    )
    source, mapping_path, review_db = _write_fixture(root, rows=rows)
    store = _initialize_product_sidecar(review_db)
    service = ReviewSyncService(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )
    observations, events_by_id = sync_module._fee_observations(service._snapshot())
    derived = next(
        item
        for item in observations
        if events_by_id[item.event_id].source_record_id == "acct::actual-1"
    )
    assert derived.source_fees == 1
    assert derived.source_fee_actual is False
    assert derived.source_fee_provenance["fee_source"] == "rule_derived"

    receipt = sync_review_events(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )
    assert receipt["fees"]["status_counts"] == {
        "actual": 4,
        "estimated": 0,
        "unknown": 3,
    }
    assert receipt["fees"]["profiles_inserted"] == 0
    assert {item["status"] for item in store.list_fee_projections()} == {
        "actual",
        "unknown",
    }


def test_exact_statement_fee_backfill_remains_an_actual_sample(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    rows = _default_rows()
    rows[0]["note"] = "fee_backfilled_exact=historical_statement.csv:2"
    source, mapping_path, review_db = _write_fixture(root, rows=rows)
    service = ReviewSyncService(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )

    observations, events_by_id = sync_module._fee_observations(service._snapshot())
    actual = next(
        item
        for item in observations
        if events_by_id[item.event_id].source_record_id == "acct::actual-1"
    )
    assert actual.source_fee_actual is True
    assert actual.source_fee_provenance["fee_source"] == "broker_actual"


def test_two_concurrent_syncs_converge_without_duplicate_fee_rows(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    source, mapping_path, review_db = _write_fixture(root)
    store = _initialize_product_sidecar(review_db)

    def run_sync() -> dict[str, object]:
        return sync_review_events(
            source,
            review_db=review_db,
            mapping_path=mapping_path,
            repo_root=root,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        receipts = list(executor.map(lambda _index: run_sync(), range(2)))

    assert [receipt["status"] for receipt in receipts] == ["succeeded", "succeeded"]
    assert sorted(int(receipt["counts"]["inserted"]) for receipt in receipts) == [0, 7]
    assert store.status()["counts"]["trade_events"] == 7
    assert len(store.list_fee_profiles()) == 1
    assert len(store.list_fee_projections()) == 7
    status = review_sync_status(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )
    assert status["status"] == "healthy"
    assert status["counts"]["unsynced"] == 0


def test_source_append_during_apply_retries_once_and_catches_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    source, mapping_path, review_db = _write_fixture(root)
    _initialize_product_sidecar(review_db)
    original_import = ReviewStore.import_events
    import_calls = 0

    def import_then_append(self, *args, **kwargs):
        nonlocal import_calls
        result = original_import(self, *args, **kwargs)
        import_calls += 1
        if import_calls == 1:
            row = _default_rows()[0].copy()
            row.update(
                event_date="2026-01-08",
                external_id="arrived-during-sync",
                dedupe_key="arrived-during-sync",
            )
            _insert_ledger_row(source, row)
        return result

    monkeypatch.setattr(ReviewStore, "import_events", import_then_append)
    receipt = sync_review_events(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )

    assert import_calls == 2
    assert receipt["counts"]["source_seen"] == 8
    assert receipt["counts"]["sidecar_seen"] == 8
    assert receipt["counts"]["unsynced"] == 0
    assert receipt["counts"]["inserted"] == 8
    assert receipt["run"]["attempt_count"] == 2
    assert [item["status"] for item in receipt["run"]["attempts"]] == [
        "partial",
        "succeeded",
    ]
    assert receipt["run"]["attempts"][0]["retry_required"] is True


def test_continuously_moving_source_records_blocker_after_one_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    source, mapping_path, review_db = _write_fixture(root)
    _initialize_product_sidecar(review_db)
    original_import = ReviewStore.import_events
    import_calls = 0

    def import_then_keep_moving(self, *args, **kwargs):
        nonlocal import_calls
        result = original_import(self, *args, **kwargs)
        import_calls += 1
        row = _default_rows()[0].copy()
        row.update(
            event_date=f"2026-01-{7 + import_calls:02d}",
            external_id=f"moving-{import_calls}",
            dedupe_key=f"moving-{import_calls}",
        )
        _insert_ledger_row(source, row)
        return result

    monkeypatch.setattr(ReviewStore, "import_events", import_then_keep_moving)
    with pytest.raises(SyncConflictError, match="continued to change"):
        sync_review_events(
            source,
            review_db=review_db,
            mapping_path=mapping_path,
            repo_root=root,
        )

    assert import_calls == 2
    status = review_sync_status(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )
    assert status["status"] == "failed"
    assert status["counts"]["unsynced"] == 1
    assert status["last_failure"]["status"] == "blocked"
    assert (
        status["last_failure"]["status_event"]["details"]["data_blocker"]
        == "SOURCE_CONTINUED_CHANGING_DURING_SYNC"
    )


def test_fee_projection_replay_is_deterministic_and_does_not_overwrite_source(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    source, mapping_path, review_db = _write_fixture(root)
    _initialize_product_sidecar(review_db)
    sync_review_events(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )
    before = _sha256(source)

    dry = project_review_fees(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        dry_run=True,
        repo_root=root,
    )
    replay = project_review_fees(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )
    assert dry["fees"]["projection_count"] == 7
    assert replay["fees"]["projections_inserted"] == 0
    assert replay["fees"]["projections_skipped"] == 7
    assert _sha256(source) == before


def test_fee_plan_batch_rolls_back_profiles_when_a_projection_fails(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    source, mapping_path, review_db = _write_fixture(root)
    store = _initialize_product_sidecar(review_db)
    service = ReviewSyncService(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )
    plan = sync_module._build_fee_plan(service._snapshot())
    assert plan.profiles

    with pytest.raises(ReviewStoreError, match="Trade event not found"):
        store.save_fee_plan(plan.profiles, plan.projections)

    assert store.list_fee_profiles() == []
    assert store.list_fee_projections() == []


@pytest.mark.parametrize("kind", ["blank", "duplicate"])
def test_composed_source_identity_must_be_complete_and_unique(
    tmp_path: Path, kind: str
) -> None:
    root = tmp_path / "repo"
    rows = _default_rows()
    if kind == "blank":
        rows[0]["external_id"] = ""
    else:
        rows[1]["external_id"] = rows[0]["external_id"]
    source, mapping_path, review_db = _write_fixture(root, rows=rows)

    with pytest.raises(SyncConflictError, match="identit"):
        sync_review_events(
            source,
            review_db=review_db,
            mapping_path=mapping_path,
            dry_run=True,
            repo_root=root,
        )
    assert not review_db.exists()


def test_source_content_drift_is_atomic_and_visible_as_failed_lag(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    source, mapping_path, review_db = _write_fixture(root)
    store = _initialize_product_sidecar(review_db)
    sync_review_events(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )

    conn = sqlite3.connect(source)
    conn.execute("UPDATE ledger_entries SET fees='2' WHERE external_id='target'")
    conn.commit()
    conn.close()
    with pytest.raises(DataConflictError, match="changed after an earlier import"):
        sync_review_events(
            source,
            review_db=review_db,
            mapping_path=mapping_path,
            repo_root=root,
        )

    stored = next(
        event
        for event in store.list_events()
        if event["source_record_id"] == "acct::target"
    )
    assert stored["fees"] == "0"
    assert store.status()["counts"]["trade_events"] == 7
    status = review_sync_status(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )
    assert status["status"] == "failed"
    assert status["counts"]["divergent_count"] == 1
    assert status["counts"]["unsynced"] == 1
    assert status["last_failure"]["status"] == "failed"


def test_same_timestamp_failure_then_success_reports_recovered_health(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    source, mapping_path, review_db = _write_fixture(root)
    _initialize_product_sidecar(review_db)
    monkeypatch.setattr(sync_module, "_utc_now", lambda: "2026-07-23T10:00:00Z")
    sync_review_events(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )

    conn = sqlite3.connect(source)
    conn.execute("UPDATE ledger_entries SET fees='2' WHERE external_id='target'")
    conn.commit()
    conn.close()
    with pytest.raises(DataConflictError):
        sync_review_events(
            source,
            review_db=review_db,
            mapping_path=mapping_path,
            repo_root=root,
        )

    conn = sqlite3.connect(source)
    conn.execute("UPDATE ledger_entries SET fees='0' WHERE external_id='target'")
    conn.commit()
    conn.close()
    recovered = sync_review_events(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )
    status = review_sync_status(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )

    assert recovered["status"] == "succeeded"
    assert status["status"] == "healthy"
    assert status["last_success"]["run"]["run_id"] == recovered["run"]["run_id"]
    assert status["last_failure"]["status"] == "failed"


def test_source_deletion_is_atomic_and_visible_as_failed_lag(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    source, mapping_path, review_db = _write_fixture(root)
    store = _initialize_product_sidecar(review_db)
    sync_review_events(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )

    conn = sqlite3.connect(source)
    conn.execute("DELETE FROM ledger_entries WHERE external_id='target'")
    conn.commit()
    conn.close()
    with pytest.raises(DataConflictError, match="removed or replaced"):
        sync_review_events(
            source,
            review_db=review_db,
            mapping_path=mapping_path,
            repo_root=root,
        )

    assert store.status()["counts"]["trade_events"] == 7
    status = review_sync_status(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )
    assert status["status"] == "failed"
    assert status["counts"]["unexpected_count"] == 1
    assert status["last_failure"]["status"] == "failed"


def test_source_delete_and_replace_same_count_cannot_hide_identity_drift(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    source, mapping_path, review_db = _write_fixture(root)
    store = _initialize_product_sidecar(review_db)
    sync_review_events(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )

    conn = sqlite3.connect(source)
    conn.execute("DELETE FROM ledger_entries WHERE external_id='target'")
    conn.commit()
    conn.close()
    replacement = _default_rows()[0].copy()
    replacement.update(
        event_date="2026-01-08",
        external_id="same-count-replacement",
        dedupe_key="same-count-replacement",
    )
    _insert_ledger_row(source, replacement)

    with pytest.raises(DataConflictError, match="removed or replaced"):
        sync_review_events(
            source,
            review_db=review_db,
            mapping_path=mapping_path,
            repo_root=root,
        )
    assert store.status()["counts"]["trade_events"] == 7
    status = review_sync_status(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )
    assert status["counts"]["source_seen"] == status["counts"]["sidecar_seen"] == 7
    assert status["counts"]["missing_count"] == 1
    assert status["counts"]["unexpected_count"] == 1
    assert status["counts"]["unsynced"] == 2


@pytest.mark.parametrize("drift_kind", ["schema", "provenance"])
def test_schema_and_provenance_drift_are_hard_stops_without_sidecar_creation(
    tmp_path: Path, drift_kind: str
) -> None:
    root = tmp_path / "repo"
    source, mapping_path, review_db = _write_fixture(root)
    if drift_kind == "schema":
        conn = sqlite3.connect(source)
        conn.execute("ALTER TABLE ledger_entries ADD COLUMN unexpected TEXT")
        conn.commit()
        conn.close()
        match = "table schema hash mismatch"
    else:
        generated_path = root / "config" / "investment_review.portfolio.generated.json"
        generated_path.write_text('{"fixture":"drifted"}', encoding="utf-8")
        match = "provenance hash mismatch"

    with pytest.raises(MappingError, match=match):
        sync_review_events(
            source,
            review_db=review_db,
            mapping_path=mapping_path,
            dry_run=True,
            repo_root=root,
        )
    assert not review_db.exists()


def test_source_and_sidecar_same_path_is_rejected_and_post_commit_isolated(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    source, mapping_path, review_db = _write_fixture(root)
    with pytest.raises(SyncServiceError, match="different files"):
        ReviewSyncService(
            source,
            review_db=source,
            mapping_path=mapping_path,
            repo_root=root,
        )

    result = sync_after_portfolio_commit(
        source,
        explicit_review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )
    assert result["status"] == "failed"
    assert result["error_type"] == "ReviewStoreError"
    assert not review_db.exists()


def test_status_is_read_only_when_sidecar_or_product_schema_is_missing(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    source, mapping_path, review_db = _write_fixture(root)
    missing = review_sync_status(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )
    assert missing["status"] == "missing_sidecar"
    assert not review_db.exists()

    review_db.parent.mkdir(parents=True)
    ReviewStore(review_db).initialize()
    before = _sha256(review_db)
    core_only = review_sync_status(
        source,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=root,
    )
    assert core_only["status"] == "schema_not_initialized"
    assert _sha256(review_db) == before
