from __future__ import annotations

import hashlib
import sqlite3
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

import src.investment_review.portfolio_snapshot_adapter as adapter_module
from src.investment_review.models import canonical_json, sha256_text
from src.investment_review.portfolio_snapshot_adapter import (
    PortfolioSnapshotAdapter,
    PortfolioSnapshotAdapterError,
    inspect_portfolio_snapshots,
    load_cash_baseline_proof,
)
from src.portfolio.models import ClosePrice, Instrument, LedgerEntry
from src.portfolio.store import PortfolioStore


EARLY = "2026-07-10T08:00:00+00:00"


def _file_sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _store(tmp_path, *, include_price: bool = True) -> PortfolioStore:
    store = PortfolioStore(tmp_path / "portfolio.sqlite3")
    store.initialize()
    prices = (
        [
            ClosePrice(
                "600000.SH",
                date(2026, 7, 10),
                Decimal("12"),
                "reviewed.close",
                fetched_at=EARLY,
            )
        ]
        if include_price
        else []
    )
    store.apply_opening_snapshot(
        account_id="default",
        instruments=[Instrument("600000.SH", "浦发银行", "equity")],
        entries=[
            LedgerEntry(
                account_id="default",
                event_date=date(2026, 7, 10),
                event_type="OPENING",
                ts_code="600000.SH",
                quantity=Decimal("100"),
                total_cost=Decimal("1000"),
                external_id="opening-1",
                dedupe_key="opening-1",
            )
        ],
        prices=prices,
        source_name="opening.csv",
        source_sha256="a" * 64,
        total_rows=1,
    )
    with store.connect() as connection:
        connection.execute(
            "UPDATE ledger_entries SET created_at = ?",
            (EARLY,),
        )
        connection.commit()
    return store


def _build(
    store: PortfolioStore,
    as_of: date,
    knowledge_cutoff: datetime,
) -> dict:
    return store.build_snapshot(
        "default",
        as_of,
        knowledge_cutoff_at=knowledge_cutoff,
    )


def _warning_codes(payload: dict) -> set[str]:
    return {
        str(item["code"])
        for item in payload["quality"]["warnings"]
    }


def _assert_no_floats(value: object) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _assert_no_floats(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_floats(item)
    else:
        assert not isinstance(value, float)


def test_empty_p2b_inventory_is_explicit_missing_and_read_only(tmp_path):
    store = _store(tmp_path)
    source = store.path
    before = _file_sha256(source)

    first = inspect_portfolio_snapshots(
        source,
        account="default",
        as_of=date(2026, 7, 12),
        knowledge_cutoff="2026-07-12T23:59:59+08:00",
    )
    second = PortfolioSnapshotAdapter(source).load(
        account_id="default",
        as_of_date="2026-07-12",
        knowledge_cutoff_at="2026-07-12T15:59:59+00:00",
    )

    assert first == second
    assert _file_sha256(source) == before
    assert first["status"] == "missing"
    assert first["snapshot_references"] == []
    assert first["snapshot_quality"] == []
    assert first["quality"]["status"] == "missing"
    assert "SNAPSHOT_MISSING" in _warning_codes(first)
    assert first["cursor"] == {
        "cursor_scope": "partition",
        "included_event_set_complete": False,
        "account_global_cursor_status": "missing",
        "reason": (
            "The existing P2B reference contract contains no explicit "
            "account-wide cursor proof."
        ),
    }
    lineage = first["lineage"]
    assert lineage["sqlite_mode"] == "ro"
    assert lineage["query_only"] is True
    assert lineage["quick_check"] == "ok"
    assert lineage["source_sha256_before"] == before
    assert lineage["source_sha256_after"] == before
    assert lineage["selection"]["inventory_count"] == 0
    assert lineage["selection"]["selected_count"] == 0
    assert "decision" not in first
    assert "price" not in first
    assert "classification" not in first


def test_inventory_applies_both_cutoffs_and_never_promotes_cursor(tmp_path):
    store = _store(tmp_path)
    visible = _build(
        store,
        date(2026, 7, 10),
        datetime(2026, 7, 10, 23, tzinfo=timezone.utc),
    )
    future_known = _build(
        store,
        date(2026, 7, 11),
        datetime(2026, 7, 13, tzinfo=timezone.utc),
    )
    future_effective = _build(
        store,
        date(2026, 7, 13),
        datetime(2026, 7, 11, 23, tzinfo=timezone.utc),
    )

    result = inspect_portfolio_snapshots(
        store.path,
        account="default",
        as_of="2026-07-12",
        knowledge_cutoff="2026-07-12T23:59:59+00:00",
    )

    assert result["status"] == "partial"
    assert [item["snapshot_id"] for item in result["snapshot_references"]] == [
        visible["snapshot_id"]
    ]
    reference = result["snapshot_references"][0]
    assert reference["cursor_scope"] == "partition"
    assert reference["included_event_set_complete"] is False
    assert result["snapshot_quality"][0]["account_global_cursor_status"] == "missing"
    assert "PORTFOLIO_CURSOR_SCOPE_LIMITED" in _warning_codes(result)
    excluded = {
        item["snapshot_id"]: item["reasons"]
        for item in result["lineage"]["selection"]["excluded"]
    }
    assert excluded[future_known["snapshot_id"]] == ["future_known"]
    assert excluded[future_effective["snapshot_id"]] == ["future_effective"]
    assert result["lineage"]["selection"]["inventory_count"] == 3
    assert result["lineage"]["selection"]["selected_count"] == 1


def test_unpriced_and_non_point_in_time_classification_remain_partial(tmp_path):
    store = _store(tmp_path, include_price=False)
    snapshot = _build(
        store,
        date(2026, 7, 12),
        datetime(2026, 7, 12, 23, tzinfo=timezone.utc),
    )
    source_hash = _file_sha256(store.path)

    result = inspect_portfolio_snapshots(
        store.path,
        account="default",
        as_of="2026-07-12",
        knowledge_cutoff="2026-07-12T23:00:00+00:00",
    )

    assert _file_sha256(store.path) == source_hash
    assert result["status"] == "partial"
    quality = result["snapshot_quality"][0]
    assert quality["snapshot_id"] == snapshot["snapshot_id"]
    assert quality["cash_status"] == "missing"
    assert quality["valuation_status"] == "partial"
    assert quality["classification_status"] == "partial"
    assert quality["missing_price_count"] == 1
    assert quality["missing_classification_count"] == 1
    assert quality["positions"] == [
        {
            "symbol": "600000.SH",
            "price_status": "missing",
            "price_reason": "source_position_is_unpriced",
            "classification_status": "missing",
            "classification_reason": "point_in_time_classification_unavailable",
        }
    ]
    codes = _warning_codes(result)
    assert {"CASH_UNAVAILABLE", "MISSING_PRICE", "MISSING_CLASSIFICATION"} <= codes
    assert all(
        key not in quality["positions"][0]
        for key in ("price", "market_value", "industry")
    )


def test_future_known_position_lineage_is_not_treated_as_available(tmp_path):
    store = _store(tmp_path)
    snapshot = _build(
        store,
        date(2026, 7, 12),
        datetime(2026, 7, 12, 12, tzinfo=timezone.utc),
    )
    with store.connect() as connection:
        row = connection.execute(
            """
            SELECT lineage_json FROM position_snapshots
            WHERE snapshot_id = ? AND ts_code = ?
            """,
            (snapshot["snapshot_id"], "600000.SH"),
        ).fetchone()
        lineage = adapter_module.json.loads(row["lineage_json"])
        lineage["price"]["known_at"] = "2026-07-13T00:00:00+00:00"
        lineage["industry"] = {
            "name": "银行",
            "source": "test",
            "updated_at": "2026-07-13T00:00:00+00:00",
            "point_in_time": True,
        }
        connection.execute(
            """
            UPDATE position_snapshots
            SET industry_name = ?, industry_source = ?, lineage_json = ?
            WHERE snapshot_id = ? AND ts_code = ?
            """,
            (
                "银行",
                "test",
                canonical_json(lineage),
                snapshot["snapshot_id"],
                "600000.SH",
            ),
        )
        connection.commit()

    result = inspect_portfolio_snapshots(
        store.path,
        account="default",
        as_of="2026-07-12",
        knowledge_cutoff="2026-07-12T12:00:00+00:00",
    )

    position = result["snapshot_quality"][0]["positions"][0]
    assert position["price_status"] == "missing"
    assert position["price_reason"] == "dual_time_price_lineage_unproven"
    assert position["classification_status"] == "missing"
    assert (
        position["classification_reason"]
        == "point_in_time_classification_unavailable"
    )


def test_output_is_deterministic_machine_readable_and_has_content_identity(tmp_path):
    store = _store(tmp_path)
    _build(
        store,
        date(2026, 7, 12),
        datetime(2026, 7, 12, 23, tzinfo=timezone.utc),
    )

    first = inspect_portfolio_snapshots(
        store.path,
        as_of="2026-07-12",
        knowledge_cutoff="2026-07-12T23:00:00+00:00",
    )
    second = inspect_portfolio_snapshots(
        store.path,
        as_of="2026-07-12",
        knowledge_cutoff="2026-07-12T23:00:00+00:00",
    )

    assert canonical_json(first) == canonical_json(second)
    material = deepcopy(first)
    content_id = material.pop("content_id")
    content_sha256 = material.pop("content_sha256")
    assert sha256_text(canonical_json(material)) == content_sha256
    assert content_id == f"snapshot_inventory_{content_sha256[:32]}"
    assert first["account_id"] is None
    _assert_no_floats(first)


@pytest.mark.parametrize(
    "as_of,knowledge_cutoff,match",
    [
        (
            datetime(2026, 7, 12, tzinfo=timezone.utc),
            "2026-07-12T00:00:00+00:00",
            "must be a date",
        ),
        ("not-a-date", "2026-07-12T00:00:00+00:00", "ISO 8601 date"),
        ("2026-07-12", "2026-07-12T00:00:00", "include a timezone"),
    ],
)
def test_adapter_rejects_ambiguous_cutoffs(
    tmp_path,
    as_of,
    knowledge_cutoff,
    match,
):
    store = _store(tmp_path)

    with pytest.raises(PortfolioSnapshotAdapterError, match=match):
        inspect_portfolio_snapshots(
            store.path,
            account="default",
            as_of=as_of,
            knowledge_cutoff=knowledge_cutoff,
        )


def test_adapter_rejects_source_change_during_inventory(tmp_path, monkeypatch):
    store = _store(tmp_path)
    observed = iter(("a" * 64, "b" * 64))
    monkeypatch.setattr(
        adapter_module,
        "_sha256_file",
        lambda _path: next(observed),
    )

    with pytest.raises(
        PortfolioSnapshotAdapterError,
        match="changed while the read-only inventory",
    ):
        inspect_portfolio_snapshots(
            store.path,
            account="default",
            as_of="2026-07-12",
            knowledge_cutoff="2026-07-12T00:00:00+00:00",
        )


def test_cash_baseline_is_strictly_pre_event_and_same_day_is_reconciliation_only(
    tmp_path,
):
    store = _store(tmp_path)
    pre = store.set_cash_balance(
        "default",
        Decimal("2697"),
        date(2026, 7, 15),
        source="reviewed_statement",
    )
    checkpoint = store.set_cash_balance(
        "default",
        Decimal("961.4"),
        date(2026, 7, 17),
        source="statement_calculated",
        note="fee_pending_entries=7; calculation_status=fee_pending",
    )
    with store.connect() as connection:
        connection.execute(
            "UPDATE cash_balance_snapshots SET recorded_at = ? WHERE snapshot_id = ?",
            ("2026-07-16T02:00:00+00:00", pre["snapshot_id"]),
        )
        connection.execute(
            "UPDATE cash_balance_snapshots SET recorded_at = ? WHERE snapshot_id = ?",
            ("2026-07-17T10:00:00+00:00", checkpoint["snapshot_id"]),
        )
        connection.commit()
    before = _file_sha256(store.path)

    proof = load_cash_baseline_proof(
        store.path,
        account_id="default",
        pre_event_at="2026-07-17T05:40:00+00:00",
        as_of="2026-07-17T05:55:28+00:00",
        knowledge_cutoff_at="2026-07-18T00:00:00+00:00",
    )
    repeat = load_cash_baseline_proof(
        store.path,
        account_id="default",
        pre_event_at="2026-07-17T05:40:00+00:00",
        as_of="2026-07-17T05:55:28+00:00",
        knowledge_cutoff_at="2026-07-18T00:00:00+00:00",
    )

    assert _file_sha256(store.path) == before
    assert repeat == proof
    assert proof["pre_event_baseline"]["row"]["snapshot_id"] == pre["snapshot_id"]
    assert proof["pre_event_baseline"]["row"]["amount"] == "2697"
    assert (
        proof["checkpoint_reconciliation"]["row"]["snapshot_id"]
        == checkpoint["snapshot_id"]
    )
    assert proof["checkpoint_reconciliation"]["row"]["fee_pending"] is True
    baseline = proof["baseline_proof"]
    assert baseline["schema_version"] == "investment_review.ledger_snapshot_baseline.v1"
    assert baseline["position"]["status"] == "missing"
    assert baseline["cash"] == {
        "status": "available",
        "value": "2697",
        "currency": "CNY",
        "effective_at": "2026-07-16T02:00:00+00:00",
        "known_at": "2026-07-16T02:00:00+00:00",
        "recorded_at": "2026-07-16T02:00:00+00:00",
        "fee_pending": False,
        "method": "cash_balance_snapshot",
        "source_refs": [
            proof["pre_event_baseline"]["row"]["row_content_id"]
        ],
    }
    binding = proof["source_binding"]
    assert binding["sqlite_mode"] == "ro"
    assert binding["query_only"] is True
    assert binding["quick_check"] == "ok"
    assert binding["same_day_checkpoint_not_pre_baseline"] is True
    assert binding["source_sha256_before"] == before
    assert binding["source_sha256_after"] == before
    _assert_no_floats(proof)


def test_missing_cash_source_schema_degrades_cash_only(tmp_path):
    source = tmp_path / "portfolio_without_cash.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE placeholder (id INTEGER PRIMARY KEY)")
        connection.commit()
    before = _file_sha256(source)

    proof = load_cash_baseline_proof(
        source,
        account_id="default",
        pre_event_at="2026-07-17T05:40:00+00:00",
        as_of="2026-07-17T05:55:28+00:00",
        knowledge_cutoff_at="2026-07-18T00:00:00+00:00",
    )

    assert _file_sha256(source) == before
    assert proof["baseline_proof"]["cash"] == {
        "status": "missing",
        "value": None,
        "currency": "CNY",
        "effective_at": None,
        "known_at": None,
        "recorded_at": None,
        "fee_pending": False,
        "method": "missing",
        "source_refs": [],
    }
    assert proof["pre_event_baseline"]["status"] == "missing"
    assert proof["checkpoint_reconciliation"]["status"] == "missing"
    assert {
        item["code"] for item in proof["gaps"]
    } == {"CASH_BASELINE_MISSING", "CASH_SOURCE_SCHEMA_MISSING"}
    assert proof["source_binding"]["source_schema_status"] == "missing"
    assert proof["source_binding"]["quick_check"] == "ok"


def test_invalid_cash_row_is_excluded_without_hiding_schema_health(tmp_path):
    source = tmp_path / "portfolio_invalid_cash.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.executescript(
            """
            CREATE TABLE cash_balance_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                as_of_date TEXT NOT NULL,
                amount TEXT NOT NULL,
                source TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                recorded_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            """
            INSERT INTO cash_balance_snapshots
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "cash-invalid",
                "default",
                "2026-07-15",
                "not-a-decimal",
                "fixture",
                "",
                "2026-07-15T12:30:30+00:00",
            ),
        )
        connection.commit()
    before = _file_sha256(source)

    proof = load_cash_baseline_proof(
        source,
        account_id="default",
        pre_event_at="2026-07-17T05:40:00+00:00",
        as_of="2026-07-17T05:55:28+00:00",
        knowledge_cutoff_at="2026-07-18T00:00:00+00:00",
    )

    assert _file_sha256(source) == before
    assert proof["source_binding"]["source_schema_status"] == "available"
    assert proof["baseline_proof"]["cash"]["status"] == "missing"
    assert proof["invalid_rows"][0]["snapshot_id"] == "cash-invalid"
    assert {
        item["code"] for item in proof["gaps"]
    } == {"CASH_BASELINE_MISSING", "CASH_EVIDENCE_ROW_INVALID"}
