from __future__ import annotations

import sqlite3
from copy import deepcopy
from pathlib import Path

from src.investment_review.periodic_reports import (
    PeriodicReportStore,
    _fee_provenance,
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
    assert instrument["safety"] == {
        "orders_executed": False,
        "broker_accessed": False,
        "guaranteed_return_claims": False,
        "recommendation_is_not_an_order": True,
    }
    markdown = render_periodic_report_markdown(instrument)
    assert "system_inference" in markdown
    assert "样本一号（000001.SZ）" in markdown
    assert "四层决策上下文" in markdown
    assert "个性化交易建议与建议仓位" in markdown
    assert "本报告不会执行订单" in markdown


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
        {"fees": "6.2", "note": "broker_statement=true"}
    )["status"] == "reported_actual"
    backfilled = _fee_provenance(
        {
            "fees": "5.06",
            "note": (
                "fees_missing=true; fee_rule=historical_fee_rule_v1; "
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
