from __future__ import annotations

import sqlite3
from copy import deepcopy
from pathlib import Path

from src.investment_review.periodic_narrative import (
    ANALYSIS_BRIEF_SCHEMA_VERSION,
    READER_REPORT_SCHEMA_VERSION,
    _risk_finding,
    render_reader_report_markdown,
)
from src.investment_review.periodic_reports import (
    LEGACY_REPORT_SCHEMA_VERSION,
    REPORT_SCHEMA_VERSION,
    PeriodicReportStore,
    build_aggregate_report,
    build_daily_report,
    render_periodic_report_markdown,
    upgrade_periodic_report_v2,
    validate_periodic_report,
)
from tests.test_investment_review_periodic_reports import (
    _empty_sidecar,
    _formal_portfolio_db,
    _point_in_time_context,
)


def test_v2_daily_report_has_reader_first_narrative_and_complete_appendix(
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

    assert report["schema_version"] == REPORT_SCHEMA_VERSION
    brief = report["analysis_brief"]
    reader = report["reader_report"]
    assert brief["schema_version"] == ANALYSIS_BRIEF_SCHEMA_VERSION
    assert reader["schema_version"] == READER_REPORT_SCHEMA_VERSION
    assert reader["central_judgment"] == brief["central_judgment"]["text"]
    assert report["headline"] == reader["central_judgment"]
    assert 1 <= len(brief["material_findings"]) <= 5
    assert all(item["source_refs"] for item in brief["material_findings"])
    assert all(
        section["source_refs"] for section in reader["narrative_sections"]
    )
    assert {
        section["title"] for section in reader["narrative_sections"]
    }.isdisjoint(
        {"基本面与估值", "大盘与板块", "技术与趋势", "仓位与执行"}
    )
    assert reader["action_plan"]["action"] == report["sections"][
        "recommendation"
    ]["action"]
    assert reader["action_plan"]["mode"] == "observation_only"
    assert reader["action_plan"]["target_position"] is None
    assert reader["orders_executed"] is False
    assert reader["guaranteed_return"] is False
    assert validate_periodic_report(report) == {
        "status": "accepted",
        "errors": [],
    }

    markdown = render_periodic_report_markdown(report)
    assert markdown.count("**中心判断：**") == 1
    assert "<details>" in markdown
    assert "<summary>结构化事实与来源</summary>" in markdown
    assert '"operations_and_motives"' in markdown
    assert '"decision_context"' in markdown
    assert "四层决策上下文" not in markdown
    assert "未生成交易动作或目标仓位" in markdown
    assert "`hold`" not in markdown
    assert "8%–12%" not in markdown


def test_v2_no_trade_and_missing_cash_degrade_without_inventing_facts(
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
        report_date="2026-07-14",
        subject_type="portfolio",
    )

    reader_text = " ".join(
        paragraph
        for section in report["reader_report"]["narrative_sections"]
        for paragraph in section["paragraphs"]
    )
    assert "没有持仓变动操作" in reader_text
    assert "不构造虚假动机或执行评价" in reader_text
    assert "现金权重尚无法可靠计算" in report["headline"]
    assert "MISSING等因素" not in report["headline"]
    assert report["sections"]["performance_and_positions"]["risk_change"][
        "cash_weight_pct"
    ] is None
    assert report["sections"]["performance_and_positions"]["cash"] is None
    assert validate_periodic_report(report)["status"] == "accepted"


def test_portfolio_structure_is_described_without_hidden_risk_thresholds() -> None:
    finding = _risk_finding(
        {
            "report_id": "fixture-neutral-structure",
            "subject": {"type": "portfolio"},
            "period": {"type": "daily"},
            "sections": {
                "performance_and_positions": {
                    "risk_change": {
                        "cash_weight_pct": "8",
                        "top_position_weight_pct": "18",
                        "top3_weight_pct": "45",
                        "source_refs": ["fixture:portfolio_structure"],
                    },
                    "positions": [],
                }
            },
        }
    )

    assert finding is not None
    assert finding["type"] == "fact"
    assert finding["text"] == (
        "当日期末组合结构：现金权重 8%、最大单一标的 18%、前三大合计 45%。"
        "是否需要调整取决于用户确认的风险预算与策略输入。"
    )
    assert "fixture:portfolio_structure" in finding["source_refs"]


def test_legacy_reader_action_is_labeled_as_historical_snapshot() -> None:
    markdown = render_reader_report_markdown(
        {
            "subject": {"type": "instrument", "id": "000001.SZ", "name": "样本"},
            "period": {"type": "daily", "end": "2026-07-15"},
            "reader_report": {
                "central_judgment": "历史报告。",
                "narrative_sections": [],
                "action_plan": {
                    "action": "reduce",
                    "target_position_note": "历史区间 8%–12%。",
                    "time_horizon": "下一交易周",
                },
                "major_risks": [],
                "invalidation_conditions": [],
                "missing_inputs": [],
            },
        }
    )

    assert "## 历史建议快照" in markdown
    assert "只用于复盘，不是当前有效建议" in markdown


def test_weekly_reader_report_contains_cross_day_synthesis_not_daily_copy(
    tmp_path: Path,
) -> None:
    source = _formal_portfolio_db(tmp_path)
    sidecar = _empty_sidecar(tmp_path)
    daily_reports = [
        build_daily_report(
            portfolio_db=source,
            review_db=sidecar,
            report_date=day,
            subject_type="portfolio",
        )
        for day in ("2026-07-14", "2026-07-15", "2026-07-16")
    ]

    weekly = build_aggregate_report(
        daily_reports=daily_reports,
        period_type="weekly",
        period_start="2026-07-14",
        period_end="2026-07-16",
    )

    cross_findings = [
        item
        for item in weekly["analysis_brief"]["material_findings"]
        if item["kind"] == "cross_period_synthesis"
    ]
    assert len(cross_findings) == 1
    cross_text = cross_findings[0]["text"]
    assert "覆盖 3 个交易日" in cross_text
    assert "操作发生在" in cross_text
    daily_paragraphs = {
        paragraph
        for report in daily_reports
        for section in report["reader_report"]["narrative_sections"]
        for paragraph in section["paragraphs"]
    }
    assert cross_text not in daily_paragraphs
    assert any(
        section["key"] == "cross_period_synthesis"
        for section in weekly["reader_report"]["narrative_sections"]
    )
    assert validate_periodic_report(weekly)["status"] == "accepted"


def test_v1_reports_remain_valid_readable_and_storable(
    tmp_path: Path,
) -> None:
    source = _formal_portfolio_db(tmp_path)
    sidecar = _empty_sidecar(tmp_path)
    current = build_daily_report(
        portfolio_db=source,
        review_db=sidecar,
        report_date="2026-07-15",
        subject_type="instrument",
        subject_id="000001.SZ",
    )
    legacy = deepcopy(current)
    legacy["schema_version"] = LEGACY_REPORT_SCHEMA_VERSION
    legacy["headline"] = "历史 V1 报告仍可读取。"
    legacy.pop("analysis_brief")
    legacy.pop("reader_report")

    assert validate_periodic_report(legacy) == {
        "status": "accepted",
        "errors": [],
    }
    legacy_markdown = render_periodic_report_markdown(legacy)
    assert "## 1. 本期结论摘要" in legacy_markdown
    assert "四层决策上下文" in legacy_markdown

    historical_advice = deepcopy(legacy)
    historical_recommendation = historical_advice["sections"]["recommendation"]
    historical_recommendation.pop("mode", None)
    historical_recommendation.pop("decision_basis", None)
    historical_recommendation["action"] = "reduce"
    historical_recommendation["target_position"] = {
        "target_position_range_pct": ["8", "12"],
        "target_position_note": "历史区间 8%–12%。",
    }
    historical_markdown = render_periodic_report_markdown(historical_advice)
    assert "历史建议快照（非当前有效建议）" in historical_markdown
    assert "该内容只用于复盘，不是当前有效建议" in historical_markdown

    store = PeriodicReportStore(sidecar)
    store.initialize()
    assert store.save(legacy)["status"] == "inserted"
    assert store.get(legacy["report_id"])["schema_version"] == (
        LEGACY_REPORT_SCHEMA_VERSION
    )

    upgraded = upgrade_periodic_report_v2(legacy)
    assert upgraded["schema_version"] == REPORT_SCHEMA_VERSION
    assert upgraded["source"]["upgraded_from"] == {
        "schema_version": LEGACY_REPORT_SCHEMA_VERSION,
        "report_id": legacy["report_id"],
        "structured_facts_changed": False,
    }
    assert upgraded["sections"] == legacy["sections"]
    assert validate_periodic_report(upgraded)["status"] == "accepted"


def test_v2_validator_rejects_untraceable_or_template_shaped_reader_text(
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

    untraceable = deepcopy(report)
    untraceable["analysis_brief"]["material_findings"][0]["source_refs"] = []
    validation = validate_periodic_report(untraceable)
    assert validation["status"] == "blocked"
    assert "material_finding_missing_source_refs" in validation["errors"]

    template_shaped = deepcopy(report)
    template_shaped["reader_report"]["narrative_sections"][0]["title"] = (
        "基本面与估值"
    )
    validation = validate_periodic_report(template_shaped)
    assert validation["status"] == "blocked"
    assert "reader_uses_mandatory_four_layer_heading" in validation["errors"]
