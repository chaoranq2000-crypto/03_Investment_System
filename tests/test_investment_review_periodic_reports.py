from __future__ import annotations

import sqlite3
from pathlib import Path

from src.investment_review.periodic_reports import (
    PeriodicReportStore,
    build_daily_report,
    render_periodic_report_markdown,
    validate_periodic_report,
)
from src.portfolio.store import PortfolioStore


def _formal_portfolio_db(tmp_path: Path) -> Path:
    path = tmp_path / "portfolio.sqlite3"
    store = PortfolioStore(path)
    store.initialize()
    with store.connect() as connection:
        connection.executemany(
            """
            INSERT INTO instruments(
                ts_code, name, asset_type, exchange, currency,
                industry_name, industry_source, industry_updated_at, updated_at
            ) VALUES (?, ?, 'equity', 'SZ', 'CNY', '', '', '', ?)
            """,
            [
                ("000001.SZ", "样本一号", "2026-07-15T12:00:00Z"),
                ("000002.SZ", "样本二号", "2026-07-15T12:00:00Z"),
            ],
        )
        connection.execute(
            """
            INSERT INTO import_batches(
                batch_id, account_id, import_kind, broker, source_name,
                source_sha256, total_rows, accepted_rows, duplicate_rows,
                skipped_rows, imported_at
            ) VALUES (
                'batch-periodic', 'default', 'statement', 'fixture',
                'fixture.csv', ?, 5, 5, 0, 0, '2026-07-15T12:00:00Z'
            )
            """,
            ("a" * 64,),
        )
        rows = [
            (
                "2026-07-10",
                "10:00:00",
                "BUY",
                "000001.SZ",
                "100",
                "10",
                "1000",
                "fixture-1",
                "ledger-1",
            ),
            (
                "2026-07-10",
                "10:05:00",
                "BUY",
                "000002.SZ",
                "100",
                "20",
                "2000",
                "fixture-2",
                "ledger-2",
            ),
            (
                "2026-07-15",
                "09:35:00",
                "BUY",
                "000001.SZ",
                "20",
                "11",
                "220",
                "fixture-3",
                "ledger-3",
            ),
            (
                "2026-07-15",
                "10:10:00",
                "SELL",
                "000001.SZ",
                "20",
                "11.1",
                "222",
                "fixture-4",
                "ledger-4",
            ),
        ]
        connection.executemany(
            """
            INSERT INTO ledger_entries(
                account_id, event_date, event_time, event_type, ts_code,
                quantity, price, gross_amount, fees, total_cost, cash_amount,
                external_id, dedupe_key, import_batch_id, source_row, note,
                created_at
            ) VALUES (
                'default', ?, ?, ?, ?, ?, ?, ?, '0', '0', '0',
                ?, ?, 'batch-periodic', 1,
                'broker=fixture; fees_missing=true',
                '2026-07-15T12:00:00Z'
            )
            """,
            rows,
        )
        prices = [
            ("000001.SZ", "2026-07-11", "10.2", "10", "2", 1),
            ("000001.SZ", "2026-07-14", "10.8", "10.2", "5.88", 2),
            ("000001.SZ", "2026-07-15", "11", "10.8", "1.85", 3),
            ("000002.SZ", "2026-07-11", "20", "20", "0", 4),
            ("000002.SZ", "2026-07-14", "20.5", "20", "2.5", 5),
            ("000002.SZ", "2026-07-15", "20.2", "20.5", "-1.46", 6),
        ]
        connection.executemany(
            """
            INSERT INTO close_prices(
                ts_code, trade_date, close, pre_close, pct_chg, source,
                fetched_at
            ) VALUES (?, ?, ?, ?, ?, 'fixture.daily', ?)
            """,
            [
                (*row[:5], f"2026-07-15T12:00:0{row[5]}Z")
                for row in prices
            ],
        )
        connection.executemany(
            """
            INSERT INTO cash_balance_snapshots(
                snapshot_id, account_id, as_of_date, amount, source, note,
                recorded_at
            ) VALUES (?, 'default', ?, ?, 'statement_calculated', ?, ?)
            """,
            [
                (
                    "cash-previous",
                    "2026-07-14",
                    "1000",
                    "fixture",
                    "2026-07-14T12:00:00Z",
                ),
                (
                    "cash-report",
                    "2026-07-15",
                    "1002",
                    "fee_pending",
                    "2026-07-15T12:00:00Z",
                ),
            ],
        )
        connection.commit()
    return path


def _empty_sidecar(tmp_path: Path) -> Path:
    path = tmp_path / "investment_review.sqlite3"
    sqlite3.connect(path).close()
    return path


def test_real_contract_shape_builds_portfolio_and_no_decision_instrument_daily(
    tmp_path: Path,
) -> None:
    source = _formal_portfolio_db(tmp_path)
    sidecar = _empty_sidecar(tmp_path)
    before = source.read_bytes()

    portfolio = build_daily_report(
        portfolio_db=source,
        review_db=sidecar,
        report_date="2026-07-15",
        subject_type="portfolio",
    )
    instrument = build_daily_report(
        portfolio_db=source,
        review_db=sidecar,
        report_date="2026-07-15",
        subject_type="instrument",
        subject_id="000001.SZ",
    )

    assert source.read_bytes() == before
    assert portfolio["period"]["type"] == "daily"
    assert portfolio["subject"]["type"] == "portfolio"
    assert instrument["subject"]["id"] == "000001.SZ"
    assert validate_periodic_report(portfolio) == {
        "status": "accepted",
        "errors": [],
    }
    assert validate_periodic_report(instrument) == {
        "status": "accepted",
        "errors": [],
    }
    operations = instrument["sections"]["operations_and_motives"]["operations"]
    assert len(operations) == 2
    assert all(item["decision_status"] == "not_recorded" for item in operations)
    assert all(item["motive"]["label"] == "system_inference" for item in operations)
    assert all(item["motive"]["uses_later_information"] is False for item in operations)
    assert all(
        item["motive"]["input_cutoff_at"] == item["occurred_at"]
        for item in operations
    )
    assert all(item["fee_status"] == "MISSING" for item in operations)
    assert instrument["safety"] == {
        "orders_executed": False,
        "broker_accessed": False,
        "guaranteed_return_claims": False,
        "recommendation_is_not_an_order": True,
    }
    markdown = render_periodic_report_markdown(instrument)
    assert "system_inference" in markdown
    assert "个性化交易建议与建议仓位" in markdown
    assert "本报告不会执行订单" in markdown


def test_periodic_store_is_additive_and_idempotent(tmp_path: Path) -> None:
    source = _formal_portfolio_db(tmp_path)
    sidecar = _empty_sidecar(tmp_path)
    report = build_daily_report(
        portfolio_db=source,
        review_db=sidecar,
        report_date="2026-07-15",
        subject_type="instrument",
        subject_id="000001.SZ",
    )
    store = PeriodicReportStore(sidecar)
    store.initialize()

    first = store.save(report)
    second = store.save(report)

    assert first["status"] == "inserted"
    assert second["status"] == "skipped"
    assert store.count() == 1
    assert store.get(report["report_id"]) == report
    listing = store.list(subject_type="instrument", period_type="daily")
    assert [item["report_id"] for item in listing] == [report["report_id"]]


def test_daily_report_still_exists_without_trades(tmp_path: Path) -> None:
    source = _formal_portfolio_db(tmp_path)
    sidecar = _empty_sidecar(tmp_path)

    report = build_daily_report(
        portfolio_db=source,
        review_db=sidecar,
        report_date="2026-07-14",
        subject_type="portfolio",
    )

    operations = report["sections"]["operations_and_motives"]
    assert operations["operation_count"] == 0
    assert report["sections"]["recommendation"]["action"] in {
        "hold",
        "reduce",
    }
    assert validate_periodic_report(report)["status"] == "accepted"
