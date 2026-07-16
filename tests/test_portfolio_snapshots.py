from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from src.portfolio.models import ClosePrice, Instrument, LedgerEntry
from src.portfolio.store import PortfolioStore, SNAPSHOT_ENGINE_VERSION


KNOWN_EARLY = "2026-07-10T08:00:00+00:00"


def _build_store(
    tmp_path,
    *,
    include_price: bool = True,
    two_positions: bool = False,
) -> PortfolioStore:
    store = PortfolioStore(tmp_path / "portfolio.sqlite3")
    store.initialize()
    instruments = [Instrument("600000.SH", "浦发银行", "equity")]
    entries = [
        LedgerEntry(
            account_id="default",
            event_date=date(2026, 7, 10),
            event_type="OPENING",
            ts_code="600000.SH",
            quantity=Decimal("100"),
            total_cost=Decimal("1000"),
            dedupe_key="opening-600000",
        )
    ]
    prices = (
        [
            ClosePrice(
                "600000.SH",
                date(2026, 7, 10),
                Decimal("12"),
                "opening_snapshot",
                fetched_at=KNOWN_EARLY,
            )
        ]
        if include_price
        else []
    )
    if two_positions:
        instruments.append(Instrument("000001.SZ", "平安银行", "equity"))
        entries.append(
            LedgerEntry(
                account_id="default",
                event_date=date(2026, 7, 10),
                event_type="OPENING",
                ts_code="000001.SZ",
                quantity=Decimal("50"),
                total_cost=Decimal("500"),
                dedupe_key="opening-000001",
            )
        )
        prices.append(
            ClosePrice(
                "000001.SZ",
                date(2026, 7, 10),
                Decimal("8"),
                "opening_snapshot",
                fetched_at=KNOWN_EARLY,
            )
        )
    store.apply_opening_snapshot(
        account_id="default",
        instruments=instruments,
        entries=entries,
        prices=prices,
        source_name="opening.csv",
        source_sha256="a" * 64,
        total_rows=len(entries),
    )
    with store.connect() as connection:
        connection.execute("UPDATE ledger_entries SET created_at = ?", (KNOWN_EARLY,))
        connection.commit()
    return store


def _add_trade(
    store: PortfolioStore,
    *,
    event_date: date,
    quantity: str,
    price: str,
    dedupe_key: str,
    known_at: str,
) -> None:
    quantity_value = Decimal(quantity)
    price_value = Decimal(price)
    entry = LedgerEntry(
        account_id="default",
        event_date=event_date,
        event_type="BUY",
        ts_code="600000.SH",
        quantity=quantity_value,
        price=price_value,
        gross_amount=quantity_value * price_value,
        dedupe_key=dedupe_key,
    )
    store.apply_statement(
        account_id="default",
        instruments=[Instrument("600000.SH", "浦发银行", "equity")],
        entries=[entry],
        broker="test",
        source_name=f"{dedupe_key}.csv",
        source_sha256=dedupe_key.ljust(64, "0")[:64],
        total_rows=1,
        skipped_rows=0,
    )
    with store.connect() as connection:
        connection.execute(
            "UPDATE ledger_entries SET created_at = ? WHERE dedupe_key = ?",
            (known_at, dedupe_key),
        )
        connection.commit()


def test_snapshot_filters_future_effective_and_future_known_trades(tmp_path):
    store = _build_store(tmp_path)
    _add_trade(
        store,
        event_date=date(2026, 7, 11),
        quantity="10",
        price="11",
        dedupe_key="late-known-buy",
        known_at="2026-07-13T00:00:00+00:00",
    )
    _add_trade(
        store,
        event_date=date(2026, 7, 13),
        quantity="20",
        price="11",
        dedupe_key="future-effective-buy",
        known_at="2026-07-11T00:00:00+00:00",
    )

    early = store.build_snapshot(
        "default",
        date(2026, 7, 12),
        knowledge_cutoff_at=datetime(2026, 7, 12, 23, tzinfo=timezone.utc),
    )
    later = store.build_snapshot(
        "default",
        date(2026, 7, 12),
        knowledge_cutoff_at=datetime(2026, 7, 14, tzinfo=timezone.utc),
    )

    assert early["positions"][0]["quantity"] == Decimal("100")
    assert later["positions"][0]["quantity"] == Decimal("110")
    assert later["positions"][0]["cost_basis"] == Decimal("1110")
    assert later["revision"] == 2
    assert later["positions"][0]["lineage"]["transaction_cutoff"] == "2026-07-12"
    assert all(
        item["dedupe_key"] != "future-effective-buy"
        for item in later["positions"][0]["lineage"]["transactions"]
    )


def test_snapshot_selects_latest_non_future_price_and_records_staleness(tmp_path):
    store = _build_store(tmp_path)
    store.add_close_prices(
        [
            ClosePrice(
                "600000.SH",
                date(2026, 7, 11),
                Decimal("13"),
                "test.close",
                fetched_at="2026-07-11T09:00:00+00:00",
            ),
            ClosePrice(
                "600000.SH",
                date(2026, 7, 12),
                Decimal("14"),
                "late.close",
                fetched_at="2026-07-13T09:00:00+00:00",
            ),
            ClosePrice(
                "600000.SH",
                date(2026, 7, 13),
                Decimal("99"),
                "future.close",
                fetched_at="2026-07-11T09:00:00+00:00",
            ),
        ]
    )

    snapshot = store.build_snapshot(
        "default",
        date(2026, 7, 12),
        knowledge_cutoff_at=datetime(2026, 7, 12, 23, tzinfo=timezone.utc),
    )
    position = snapshot["positions"][0]
    assert position["price"] == Decimal("13")
    assert position["price_date"] == "2026-07-11"
    assert position["price_source"] == "test.close"
    assert position["staleness_days"] == 1
    assert position["valuation_status"] == "stale"


def test_snapshot_compares_known_times_as_instants_across_offsets(tmp_path):
    store = _build_store(tmp_path)
    store.add_close_prices(
        [
            ClosePrice(
                "600000.SH",
                date(2026, 7, 11),
                Decimal("13"),
                "offset.close",
                fetched_at="2026-07-12T08:00:00+08:00",
            )
        ]
    )

    snapshot = store.build_snapshot(
        "default",
        date(2026, 7, 12),
        knowledge_cutoff_at=datetime(2026, 7, 12, 0, 30, tzinfo=timezone.utc),
    )

    assert snapshot["positions"][0]["price"] == Decimal("13")
    assert snapshot["positions"][0]["price_source"] == "offset.close"


def test_snapshot_preserves_unpriced_position_without_fake_zero_value(tmp_path):
    store = _build_store(tmp_path, include_price=False)

    snapshot = store.build_snapshot("default", date(2026, 7, 12))
    position = snapshot["positions"][0]
    assert position["quantity"] == Decimal("100")
    assert position["cost_basis"] == Decimal("1000")
    assert position["price"] is None
    assert position["market_value"] is None
    assert position["unrealized_pnl"] is None
    assert position["valuation_status"] == "unpriced"
    assert snapshot["market_value"] == Decimal("0")
    assert snapshot["unpriced_position_count"] == 1
    assert snapshot["valuation_complete"] is False


def test_snapshot_is_idempotent_and_input_change_creates_queryable_revision(tmp_path):
    store = _build_store(tmp_path)

    first = store.build_snapshot("default", date(2026, 7, 12))
    repeated = store.build_snapshot("default", date(2026, 7, 12))
    assert repeated["snapshot_id"] == first["snapshot_id"]
    assert repeated["revision"] == 1

    store.add_close_prices(
        [
            ClosePrice(
                "600000.SH",
                date(2026, 7, 12),
                Decimal("15"),
                "corrected.close",
                fetched_at="2026-07-14T00:00:00+00:00",
            )
        ]
    )
    revised = store.build_snapshot("default", date(2026, 7, 12))

    assert revised["revision"] == 2
    assert revised["snapshot_id"] != first["snapshot_id"]
    assert revised["source_state_hash"] != first["source_state_hash"]
    assert store.get_snapshot("default", date(2026, 7, 12), revision=1)["positions"][0][
        "price"
    ] == Decimal("12")
    assert store.get_snapshot("default", date(2026, 7, 12))["revision"] == 2
    assert [row["revision"] for row in store.list_snapshots("default")] == [2, 1]


def test_snapshot_summary_reconciles_to_position_rows(tmp_path):
    store = _build_store(tmp_path, two_positions=True)

    snapshot = store.build_snapshot("default", date(2026, 7, 12))
    positions = snapshot["positions"]
    assert snapshot["cost_basis"] == sum((row["cost_basis"] for row in positions), Decimal("0"))
    assert snapshot["market_value"] == sum((row["market_value"] for row in positions), Decimal("0"))
    assert snapshot["unrealized_pnl"] == sum(
        (row["unrealized_pnl"] for row in positions), Decimal("0")
    )
    assert snapshot["cost_basis"] == Decimal("1500")
    assert snapshot["market_value"] == Decimal("1600")
    assert snapshot["unrealized_pnl"] == Decimal("100")
    assert sum((row["portfolio_weight"] for row in positions), Decimal("0")) == Decimal("1")


def test_snapshot_transaction_rolls_back_summary_and_details(tmp_path):
    store = _build_store(tmp_path)
    with store.connect() as connection:
        connection.executescript(
            """
            CREATE TRIGGER fail_position_snapshot_insert
            BEFORE INSERT ON position_snapshots
            BEGIN
                SELECT RAISE(ABORT, 'forced position failure');
            END;
            """
        )
        connection.commit()

    with pytest.raises(sqlite3.IntegrityError, match="forced position failure"):
        store.build_snapshot("default", date(2026, 7, 12))

    with store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM portfolio_snapshots").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM position_snapshots").fetchone()[0] == 0


def test_empty_account_snapshot_is_stable_and_queryable(tmp_path):
    store = PortfolioStore(tmp_path / "portfolio.sqlite3")
    store.initialize()

    first = store.build_snapshot("default", date(2026, 7, 12))
    second = store.build_snapshot("default", date(2026, 7, 12))

    assert first["snapshot_id"] == second["snapshot_id"]
    assert first["positions"] == []
    assert first["position_count"] == 0
    assert first["valuation_complete"] is True
    assert first["engine_version"] == SNAPSHOT_ENGINE_VERSION


def test_snapshot_cash_uses_as_of_and_known_time_lineage(tmp_path):
    store = _build_store(tmp_path)
    cash = store.set_cash_balance(
        "default",
        Decimal("1234.56"),
        date(2026, 7, 11),
        source="user_provided",
        note="confirmed",
    )
    with store.connect() as connection:
        connection.execute(
            "UPDATE cash_balance_snapshots SET recorded_at = ? WHERE snapshot_id = ?",
            ("2026-07-11T09:00:00+00:00", cash["snapshot_id"]),
        )
        connection.commit()

    visible = store.build_snapshot(
        "default",
        date(2026, 7, 12),
        knowledge_cutoff_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
    )
    hidden = store.build_snapshot(
        "default",
        date(2026, 7, 12),
        knowledge_cutoff_at=datetime(2026, 7, 11, 8, tzinfo=timezone.utc),
    )

    assert visible["cash_balance"] == Decimal("1234.56")
    assert visible["cash_status"] == "available"
    assert hidden["cash_balance"] is None
    assert hidden["cash_status"] == "unavailable"


def test_same_rank_cash_snapshots_are_unavailable_independent_of_insert_order(
    tmp_path,
):
    observed = []
    for name, amounts in (("forward", ("1000", "2000")), ("reverse", ("2000", "1000"))):
        case_path = tmp_path / name
        case_path.mkdir()
        store = _build_store(case_path)
        ids = []
        for amount in amounts:
            ids.append(
                store.set_cash_balance(
                    "default",
                    Decimal(amount),
                    date(2026, 7, 11),
                    source="reviewed_cash",
                )["snapshot_id"]
            )
        with store.connect() as connection:
            connection.executemany(
                "UPDATE cash_balance_snapshots SET recorded_at = ? WHERE snapshot_id = ?",
                [("2026-07-11T09:00:00+00:00", snapshot_id) for snapshot_id in ids],
            )
            connection.commit()
        observed.append(
            store.build_snapshot(
                "default",
                date(2026, 7, 12),
                knowledge_cutoff_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
            )
        )

    assert [item["cash_status"] for item in observed] == ["unavailable", "unavailable"]
    assert [item["cash_balance"] for item in observed] == [None, None]
    assert observed[0]["source_state_hash"] == observed[1]["source_state_hash"]


def test_snapshot_rejects_naive_knowledge_cutoff_and_bad_ranges(tmp_path):
    store = _build_store(tmp_path)
    with pytest.raises(ValueError, match="必须包含时区"):
        store.build_snapshot(
            "default",
            date(2026, 7, 12),
            knowledge_cutoff_at=datetime(2026, 7, 12),
        )
    with pytest.raises(ValueError, match="date_from"):
        store.list_snapshots(
            "default",
            date_from=date(2026, 7, 13),
            date_to=date(2026, 7, 12),
        )
