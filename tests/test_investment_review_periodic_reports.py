from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from datetime import date
from pathlib import Path

from src.investment_review.periodic_reports import (
    PeriodicReportStore,
    _fee_provenance,
    _natural_calendar_bounds,
    build_aggregate_report,
    build_daily_report,
    export_final_sample_matrix,
    generate_daily_range,
    generate_periodic_summaries,
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
            ("000001.SZ", "2026-07-16", "11.2", "11", "1.82", 7),
            ("000002.SZ", "2026-07-11", "20", "20", "0", 4),
            ("000002.SZ", "2026-07-14", "20.5", "20", "2.5", 5),
            ("000002.SZ", "2026-07-15", "20.2", "20.5", "-1.46", 6),
            ("000002.SZ", "2026-07-16", "20.1", "20.2", "-0.5", 8),
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
            ) VALUES (?, 'default', ?, ?, ?, ?, ?)
            """,
            [
                (
                    "cash-previous",
                    "2026-07-14",
                    "1000",
                    "user_provided",
                    "fixture",
                    "2026-07-14T12:00:00Z",
                ),
                (
                    "cash-report",
                    "2026-07-15",
                    "1002",
                    "statement_calculated",
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


def _point_in_time_context() -> dict[str, object]:
    return {
        "subject": {
            "ts_code": "000001.SZ",
            "name": "样本一号",
            "industry_name": "样本行业",
        },
        "fetched_at": "2026-07-15T12:30:00Z",
        "fundamental_and_valuation": {
            "status": "available",
            "summary": "最新公开财务与估值快照已核对。",
            "observations": [
                {
                    "type": "fact",
                    "text": "样本财务事实。",
                    "source_ref": "fixture:fundamental",
                }
            ],
            "source_refs": ["fixture:fundamental"],
        },
        "market_and_sector": {
            "status": "available",
            "summary": "指数与板块仅用于解释环境，不直接证明动机。",
            "observations": [],
            "source_refs": ["fixture:market"],
        },
        "technical_and_trend": {
            "status": "available",
            "summary": "短线趋势偏强，但只作概率性上下文。",
            "observations": [],
            "source_refs": ["fixture:technical"],
        },
        "intraday_bars": [
            {
                "bar_end_at": "2026-07-15T09:35:00+08:00",
                "high_cny": "11",
                "close_cny": "10.98",
                "source_ref": "fixture:09:35",
            },
            {
                "bar_end_at": "2026-07-15T10:05:00+08:00",
                "high_cny": "11.1",
                "close_cny": "11.08",
                "source_ref": "fixture:10:05",
            },
        ],
    }


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
    assert all(item["fee_status"] == "unknown" for item in operations)
    assert all(item["name"] == "样本一号" for item in operations)
    assert instrument["sections"]["decision_context"]["report_depth"] == (
        "daily_delta_only"
    )
    assert set(instrument["sections"]["decision_context"]) >= {
        "fundamental_and_valuation",
        "market_and_sector",
        "technical_and_trend",
        "position_and_execution",
    }
    assert instrument["sections"]["performance_and_positions"]["cash"][
        "consistency_status"
    ] == "replayed_from_anchor"
    portfolio_performance = portfolio["sections"]["performance_and_positions"][
        "performance"
    ]
    instrument_performance = instrument["sections"][
        "performance_and_positions"
    ]["performance"]
    assert portfolio_performance["performance_basis"] == "total_assets"
    assert instrument_performance["performance_basis"] == "instrument_close_price"
    assert instrument_performance["start_close_cny"] == "10.8"
    assert instrument_performance["end_close_cny"] == "11"
    assert instrument_performance["price_change_cny"] == "0.2"
    assert instrument_performance["price_change_pct"] == "1.85"
    assert instrument_performance["asset_change_cny"] is None
    assert instrument["safety"] == {
        "orders_executed": False,
        "broker_accessed": False,
        "guaranteed_return_claims": False,
        "recommendation_is_not_an_order": True,
    }
    assert instrument["schema_version"] == "investment_review.periodic_report.v2"
    assert instrument["headline"] == instrument["reader_report"]["central_judgment"]
    assert instrument["analysis_brief"]["material_findings"]
    markdown = render_periodic_report_markdown(instrument)
    assert "system_inference" in markdown
    assert "样本一号（000001.SZ）" in markdown
    assert "当日收盘价上涨 1.85%" in markdown
    assert "结构化事实与来源" in markdown
    assert "## 下一步行动" in markdown
    assert "四层决策上下文" not in markdown
    assert "报告不会连接券商或自动执行交易" in markdown


def test_available_four_layer_context_flows_into_motive_and_recommendation(
    tmp_path: Path,
) -> None:
    source = _formal_portfolio_db(tmp_path)
    sidecar = _empty_sidecar(tmp_path)
    report = build_daily_report(
        portfolio_db=source,
        review_db=sidecar,
        report_date="2026-07-15",
        subject_type="instrument",
        subject_id="000001.SZ",
        point_in_time_context=_point_in_time_context(),
    )

    context = report["sections"]["decision_context"]
    recommendation = report["sections"]["recommendation"]
    operations = report["sections"]["operations_and_motives"]["operations"]
    assert all(
        context[key]["status"] == "available"
        for key in (
            "fundamental_and_valuation",
            "market_and_sector",
            "technical_and_trend",
            "position_and_execution",
        )
    )
    assert recommendation["confidence"] == "medium"
    assert "MISSING_FUNDAMENTAL_AND_VALUATION_CONTEXT" not in (
        recommendation["important_missing_inputs"]
    )
    assert "MISSING_INTRADAY_MARKET_CONTEXT" not in operations[0]["motive"][
        "important_missing_information"
    ]


def test_fee_provenance_separates_actual_backfill_exemption_and_unknown() -> None:
    assert _fee_provenance(
        {
            "fees": "6.2",
            "note": "broker_statement=true; fee_source=broker_actual",
        }
    )["status"] == "reported_actual"
    legacy_actual = _fee_provenance(
        {
            "fees": "6.2",
            "note": "fee_backfilled_exact=historical_statement.csv:2",
        }
    )
    assert legacy_actual["status"] == "reported_actual"
    assert legacy_actual["fee_source"] == "broker_actual"
    assert _fee_provenance(
        {"fees": "6.2", "note": "broker_statement=true"}
    )["status"] == "unknown"
    backfilled = _fee_provenance(
        {
            "fees": "5.06",
            "note": (
                "fees_missing=true; fee_source=rule_derived; "
                "fee_rule=historical_fee_rule_v1; "
                "fee_backfilled_rule=true"
            ),
        }
    )
    assert backfilled["status"] == "rule_backfilled"
    assert backfilled["fee_rule"] == "historical_fee_rule_v1"
    assert _fee_provenance(
        {
            "fees": "0",
            "note": "fee_rule=online_primary_bond_subscription_fee_exempt_v1",
        }
    )["status"] == "formal_exemption"
    assert _fee_provenance(
        {"fees": "0", "note": "fees_missing=true"}
    )["status"] == "unknown"


def test_rule_backfilled_fees_replay_cash_without_missing_fee_warning(
    tmp_path: Path,
) -> None:
    source = _formal_portfolio_db(tmp_path)
    sidecar = _empty_sidecar(tmp_path)
    with sqlite3.connect(source) as connection:
        connection.execute(
            """
            UPDATE ledger_entries
            SET fees = '1',
                note = 'fee_rule=historical_fee_rule_v1; fee_backfilled_rule=true'
            WHERE event_date = '2026-07-15'
            """
        )
        connection.commit()

    report = build_daily_report(
        portfolio_db=source,
        review_db=sidecar,
        report_date="2026-07-15",
        subject_type="instrument",
        subject_id="000001.SZ",
    )

    cash = report["sections"]["performance_and_positions"]["cash"]
    operations = report["sections"]["operations_and_motives"]["operations"]
    assert cash["amount_cny"] == "1000"
    assert cash["fee_pending"] is False
    assert cash["fee_provenance_status"] == "complete"
    assert {item["fee_status"] for item in operations} == {"rule_backfilled"}
    assert "UNKNOWN_TRADE_FEE_PROVENANCE" not in report["sections"][
        "risks_invalidation_and_missing"
    ]["data_limitations"]


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

    refreshed = deepcopy(report)
    refreshed["report_id"] = "periodic_" + "b" * 32
    refreshed["headline"] = "同一报告期在来源修正后刷新。"
    receipt = store.save(refreshed)
    assert receipt["status"] == "updated"
    assert receipt["report_id"] == refreshed["report_id"]
    assert store.count() == 1
    assert store.get(refreshed["report_id"]) == refreshed


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


def test_missing_historical_cash_preserves_total_asset_gap_and_market_value_basis(
    tmp_path: Path,
) -> None:
    source = _formal_portfolio_db(tmp_path)
    sidecar = _empty_sidecar(tmp_path)
    with sqlite3.connect(source) as connection:
        connection.execute("DELETE FROM cash_balance_snapshots")
        connection.commit()

    report = build_daily_report(
        portfolio_db=source,
        review_db=sidecar,
        report_date="2026-07-15",
        subject_type="portfolio",
    )
    facts = report["sections"]["performance_and_positions"]
    performance = facts["performance"]

    assert facts["cash"] is None
    assert performance["start_total_assets_cny"] is None
    assert performance["end_total_assets_cny"] is None
    assert performance["performance_basis"] == "invested_market_value_ex_cash"
    assert performance["period_change_cny"] is not None
    assert performance["period_change_pct"] is not None
    assert "现金权重尚无法可靠计算" in report["headline"]
    assert "None" not in report["headline"]
    assert validate_periodic_report(report)["status"] == "accepted"


def test_daily_range_covers_held_traded_no_trade_exit_and_is_idempotent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    source = _formal_portfolio_db(tmp_path)
    sidecar = _empty_sidecar(tmp_path)
    output = tmp_path / "daily-range"
    with sqlite3.connect(source) as connection:
        connection.execute(
            """
            INSERT INTO ledger_entries(
                account_id, event_date, event_time, event_type, ts_code,
                quantity, price, gross_amount, fees, total_cost, cash_amount,
                external_id, dedupe_key, import_batch_id, source_row, note,
                created_at
            ) VALUES (
                'default', '2026-07-15', '14:20:00', 'SELL', '000002.SZ',
                '100', '20.2', '2020', '0', '0', '0',
                'fixture-5', 'ledger-5', 'batch-periodic', 5,
                'broker=fixture; fees_missing=true',
                '2026-07-15T12:00:00Z'
            )
            """
        )
        connection.commit()
    before = source.read_bytes()

    first = generate_daily_range(
        portfolio_db=source,
        review_db=sidecar,
        start_date="2026-07-14",
        end_date="2026-07-16",
        output_dir=output,
    )
    second = generate_daily_range(
        portfolio_db=source,
        review_db=sidecar,
        start_date="2026-07-14",
        end_date="2026-07-16",
        output_dir=output,
    )

    assert source.read_bytes() == before
    assert first["period"] == {
        "start": "2026-07-14",
        "end": "2026-07-16",
        "trading_day_count": 3,
    }
    assert [item["trade_date"] for item in first["coverage"]] == [
        "2026-07-14",
        "2026-07-15",
        "2026-07-16",
    ]
    assert [item["no_trade_day"] for item in first["coverage"]] == [
        True,
        False,
        True,
    ]
    assert first["coverage"][1]["traded_instruments"] == [
        "000001.SZ",
        "000002.SZ",
    ]
    assert first["coverage"][1]["instrument_reports"] == 2
    assert first["coverage"][2]["held_instruments"] == ["000001.SZ"]
    assert first["coverage"][2]["instrument_reports"] == 1
    assert first["report_count"] == 8
    assert {item["status"] for item in second["store_receipts"]} == {"skipped"}
    report_store = PeriodicReportStore(sidecar)
    assert report_store.count() == 8
    exited = report_store.get_by_identity(
        subject_type="instrument",
        subject_id="000002.SZ",
        period_type="daily",
        period_start="2026-07-15",
        period_end="2026-07-15",
    )
    assert exited is not None
    assert exited["subject"]["name"] == "样本二号"
    assert "期末已无该标的持仓" in exited["headline"]
    assert (output / "daily_range_validation.json").is_file()


def test_weekly_monthly_summaries_reconcile_daily_facts_and_are_idempotent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    source = _formal_portfolio_db(tmp_path)
    sidecar = _empty_sidecar(tmp_path)
    generate_daily_range(
        portfolio_db=source,
        review_db=sidecar,
        start_date="2026-07-14",
        end_date="2026-07-16",
    )

    weekly = generate_periodic_summaries(
        review_db=sidecar,
        period_type="weekly",
        start_date="2026-07-13",
        end_date="2026-07-19",
        output_dir=tmp_path / "weekly",
        subject_type="portfolio",
    )
    weekly_replay = generate_periodic_summaries(
        review_db=sidecar,
        period_type="weekly",
        start_date="2026-07-13",
        end_date="2026-07-19",
        output_dir=tmp_path / "weekly",
        subject_type="portfolio",
    )
    monthly = generate_periodic_summaries(
        review_db=sidecar,
        period_type="monthly",
        start_date="2026-07-01",
        end_date="2026-07-31",
        output_dir=tmp_path / "monthly",
        subject_type="instrument",
        subject_id="000001.SZ",
    )

    assert weekly["report_count"] == 1
    assert weekly["reports"][0]["daily_source_count"] == 3
    assert weekly["reports"][0]["operation_count"] == 2
    assert weekly["reports"][0]["validation"]["status"] == "accepted"
    assert {item["status"] for item in weekly_replay["store_receipts"]} == {
        "skipped"
    }
    assert monthly["report_count"] == 1
    stored_weekly = PeriodicReportStore(sidecar).get(
        weekly["reports"][0]["report_id"]
    )
    stored_monthly = PeriodicReportStore(sidecar).get(
        monthly["reports"][0]["report_id"]
    )
    assert stored_weekly["sections"]["decision_context"]["report_depth"] == (
        "weekly_synthesis"
    )
    assert stored_monthly["sections"]["decision_context"]["report_depth"] == (
        "monthly_synthesis"
    )
    monthly_performance = stored_monthly["sections"][
        "performance_and_positions"
    ]["performance"]
    assert monthly_performance["performance_basis"] == "instrument_close_price"
    assert monthly_performance["start_close_cny"] == "10.2"
    assert monthly_performance["end_close_cny"] == "11.2"
    assert monthly_performance["price_change_cny"] == "1"
    assert monthly_performance["price_change_pct"] == "9.8"
    assert monthly_performance["asset_change_cny"] is None
    assert "样本一号本月收盘价上涨 9.8%" in stored_monthly["headline"]
    assert stored_weekly["source"]["daily_report_ids"] == [
        item["source_report_id"]
        for item in stored_weekly["sections"]["performance_and_positions"][
            "period_attribution"
        ]["daily_changes"]
    ]
    assert "周报" in render_periodic_report_markdown(stored_weekly)
    assert "月报" in render_periodic_report_markdown(stored_monthly)


def test_aggregate_no_trade_period_and_cross_month_week_boundary(
    tmp_path: Path,
) -> None:
    source = _formal_portfolio_db(tmp_path)
    sidecar = _empty_sidecar(tmp_path)
    reports = [
        build_daily_report(
            portfolio_db=source,
            review_db=sidecar,
            report_date=day,
            subject_type="portfolio",
        )
        for day in ("2026-07-14", "2026-07-16")
    ]
    aggregate = build_aggregate_report(
        daily_reports=reports,
        period_type="weekly",
        period_start="2026-07-14",
        period_end="2026-07-16",
    )

    assert aggregate["sections"]["operations_and_motives"]["operation_count"] == 0
    assert aggregate["sections"]["review_judgments"][0]["status"] == "no_trade"
    assert validate_periodic_report(aggregate)["status"] == "accepted"
    assert _natural_calendar_bounds(date(2026, 7, 1), "weekly") == (
        date(2026, 6, 29),
        date(2026, 7, 5),
    )


def test_newly_opened_instrument_keeps_unavailable_return_explicit(
    tmp_path: Path,
) -> None:
    source = _formal_portfolio_db(tmp_path)
    sidecar = _empty_sidecar(tmp_path)
    reports = [
        build_daily_report(
            portfolio_db=source,
            review_db=sidecar,
            report_date=day,
            subject_type="instrument",
            subject_id="000001.SZ",
        )
        for day in ("2026-07-14", "2026-07-15", "2026-07-16")
    ]
    opening_performance = reports[0]["sections"][
        "performance_and_positions"
    ]["performance"]
    opening_performance["start_close_cny"] = None
    opening_performance["start_price_date"] = None
    opening_performance["start_invested_market_value_cny"] = "0"

    aggregate = build_aggregate_report(
        daily_reports=reports,
        period_type="monthly",
        period_start="2026-07-14",
        period_end="2026-07-16",
    )
    performance = aggregate["sections"]["performance_and_positions"][
        "performance"
    ]
    markdown = render_periodic_report_markdown(aggregate)

    assert performance["performance_basis"] == "instrument_position_market_value"
    assert performance["period_change_pct"] is None
    assert "收益率保持 MISSING" in aggregate["headline"]
    assert "缺少可比期初价格" in markdown
    assert "收益率保持 MISSING" in markdown
    assert "None" not in markdown


def test_final_export_contains_exact_six_report_types_and_safety_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    source = _formal_portfolio_db(tmp_path)
    sidecar = _empty_sidecar(tmp_path)
    generate_daily_range(
        portfolio_db=source,
        review_db=sidecar,
        start_date="2026-07-14",
        end_date="2026-07-16",
    )
    for period_type, period_start, period_end in (
        ("weekly", "2026-07-14", "2026-07-16"),
        ("monthly", "2026-07-14", "2026-07-16"),
    ):
        daily = [
            PeriodicReportStore(sidecar).get_by_identity(
                subject_type=subject_type,
                subject_id=subject_id,
                period_type="daily",
                period_start=day,
                period_end=day,
            )
            for subject_type, subject_id in (
                ("portfolio", "default"),
                ("instrument", "000001.SZ"),
            )
            for day in ("2026-07-14", "2026-07-15", "2026-07-16")
        ]
        for subject_type, subject_id in (
            ("portfolio", "default"),
            ("instrument", "000001.SZ"),
        ):
            selected = [
                item
                for item in daily
                if item is not None
                and item["subject"]["type"] == subject_type
                and item["subject"]["id"] == subject_id
            ]
            PeriodicReportStore(sidecar).save(
                build_aggregate_report(
                    daily_reports=selected,
                    period_type=period_type,
                    period_start=period_start,
                    period_end=period_end,
                )
            )
    output = tmp_path / "final"
    result = export_final_sample_matrix(
        portfolio_db=source,
        review_db=sidecar,
        output_dir=output,
        instrument="000001.SZ",
        daily_date="2026-07-15",
        weekly_start="2026-07-14",
        weekly_end="2026-07-16",
        monthly_start="2026-07-14",
        monthly_end="2026-07-16",
    )

    assert result["report_count"] == 6
    manifest = json.loads(
        (output / "validation_summary.json").read_text(encoding="utf-8")
    )
    assert {
        (item["subject"]["type"], item["period"]["type"])
        for item in manifest["sample_matrix"]
    } == {
        ("portfolio", "daily"),
        ("instrument", "daily"),
        ("portfolio", "weekly"),
        ("instrument", "weekly"),
        ("portfolio", "monthly"),
        ("instrument", "monthly"),
    }
    assert manifest["formal_portfolio_db"]["unchanged"] is True
    assert manifest["orders_executed"] is False
    assert manifest["production_released"] is False
    assert (output / "FINAL_READOUT.md").is_file()


def test_validator_rejects_post_operation_motive_observation(
    tmp_path: Path,
) -> None:
    source = _formal_portfolio_db(tmp_path)
    sidecar = _empty_sidecar(tmp_path)
    report = build_daily_report(
        portfolio_db=source,
        review_db=sidecar,
        report_date="2026-07-15",
        subject_type="instrument",
        subject_id="000001.SZ",
    )
    drifted = deepcopy(report)
    operation = drifted["sections"]["operations_and_motives"]["operations"][0]
    operation["motive"]["supporting_observations"][0]["observed_at"] = (
        "2026-07-15T15:00:00+08:00"
    )

    validation = validate_periodic_report(drifted)
    assert validation["status"] == "blocked"
    assert "motive_observation_after_operation" in validation["errors"]
