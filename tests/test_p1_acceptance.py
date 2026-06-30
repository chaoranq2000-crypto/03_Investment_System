import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEGMENT_ID = "ai_server_liquid_cooling"
REPORT_DATE = "2026-07-01"


REQUIRED_P1_FILES = [
    "reports/p1/00_p0_readiness_check.md",
    "reports/p1/01_pilot_segment_selection.md",
    f"reports/p1/quality_review_{SEGMENT_ID}.md",
    "reports/p1/quality_issues.csv",
    "reports/p1/fix_log.md",
    "reports/p1/template_change_log.md",
    f"reports/p1/p1_readout_{SEGMENT_ID}.md",
    "reports/p1/p1_lessons_learned.md",
    "reports/p1/p2_entry_checklist.md",
    "reports/p1/p1_watchlist.md",
    f"reports/segments/{SEGMENT_ID}/segment_definition.yaml",
    f"reports/segments/{SEGMENT_ID}/segment_boundary.md",
    f"reports/segments/{SEGMENT_ID}/evidence_inventory.md",
    f"reports/segments/{SEGMENT_ID}/claims_review.md",
    f"reports/segments/{SEGMENT_ID}/{REPORT_DATE}_segment_report.md",
    f"reports/segments/{SEGMENT_ID}/company_universe.csv",
    f"reports/segments/{SEGMENT_ID}/company_universe_notes.md",
    f"reports/segments/{SEGMENT_ID}/scorecard.yaml",
    f"reports/segments/{SEGMENT_ID}/evidence_map.md",
    f"reports/segments/{SEGMENT_ID}/followup_questions.md",
    f"reports/segments/{SEGMENT_ID}/segment_company_exposure_review.md",
    f"reports/segments/{SEGMENT_ID}/stock_deep_dive_selection.md",
    f"reports/segments/{SEGMENT_ID}/refresh_tasks.yaml",
    "reports/stocks/002837_invic/2026-07-01_stock_deep_dive.md",
    "reports/stocks/002837_invic/segment_exposure.yaml",
    "reports/stocks/002837_invic/stock_scorecard.yaml",
    "reports/stocks/002837_invic/evidence_map.md",
    "reports/stocks/002837_invic/open_questions.md",
    "reports/stocks/002837_invic/valuation_scenarios.md",
    "reports/stocks/300731_cotran/2026-07-01_stock_deep_dive.md",
    "reports/stocks/300731_cotran/segment_exposure.yaml",
    "reports/stocks/300731_cotran/stock_scorecard.yaml",
    "reports/stocks/300731_cotran/evidence_map.md",
    "reports/stocks/300731_cotran/open_questions.md",
    "reports/stocks/300731_cotran/valuation_scenarios.md",
    "data/manifests/evidence_manifest.csv",
    "data/manifests/claims_draft.csv",
    "data/manifests/metrics_draft.csv",
    "data/processed/normalized/segment_company_exposure.csv",
    "data/raw/market_data/tushare_stock_basic_ai_server_liquid_cooling_2026-07-01.csv",
    "data/processed/tables/tushare_stock_basic_ai_server_liquid_cooling_2026-07-01.csv",
    "data/raw/market_data/tushare_income_selected_stocks_2026-07-01.csv",
    "data/raw/market_data/tushare_fina_indicator_selected_stocks_2026-07-01.csv",
    "data/raw/market_data/tushare_cashflow_selected_stocks_2026-07-01.csv",
    "data/raw/market_data/tushare_balancesheet_selected_stocks_2026-07-01.csv",
    "data/processed/tables/tushare_income_selected_stocks_2026-07-01.csv",
    "data/processed/tables/tushare_fina_indicator_selected_stocks_2026-07-01.csv",
    "data/processed/tables/tushare_cashflow_selected_stocks_2026-07-01.csv",
    "data/processed/tables/tushare_balancesheet_selected_stocks_2026-07-01.csv",
    "config/watchlist.yaml",
]


def read_csv(relative_path: str) -> list[dict[str, str]]:
    with (ROOT / relative_path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def split_ids(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def test_p1_required_files_exist() -> None:
    missing = [path for path in REQUIRED_P1_FILES if not (ROOT / path).is_file()]
    assert not missing, "\n".join(missing)


def test_evidence_manifest_and_claims_are_linked() -> None:
    evidence = read_csv("data/manifests/evidence_manifest.csv")
    claims = read_csv("data/manifests/claims_draft.csv")
    evidence_ids = {row["evidence_id"] for row in evidence}

    assert len(evidence) >= 15
    assert len(claims) >= 22
    assert "market_data_tushare_probe_20260701_8bbf20" in evidence_ids
    assert "market_data_tushare_stock_basic_20260701_a6d9f2" in evidence_ids
    assert "market_data_tushare_income_selected_stocks_20260701_f1c8b2" in evidence_ids
    assert "market_data_tushare_fina_indicator_selected_stocks_20260701_c3e4a9" in evidence_ids
    assert "market_data_tushare_cashflow_selected_stocks_20260701_d5b6c1" in evidence_ids
    assert "market_data_tushare_balancesheet_selected_stocks_20260701_a8f0d7" in evidence_ids

    dangling = [row for row in claims if row["evidence_id"] not in evidence_ids]
    assert not dangling

    allowed_claim_types = {
        "fact",
        "estimate",
        "inference",
        "management_comment",
        "analyst_view",
        "opinion",
        "unknown",
        "risk",
    }
    invalid_types = [row for row in claims if row["claim_type"] not in allowed_claim_types]
    assert not invalid_types


def test_financial_metrics_are_traceable() -> None:
    metrics = read_csv("data/manifests/metrics_draft.csv")
    evidence_ids = {row["evidence_id"] for row in read_csv("data/manifests/evidence_manifest.csv")}

    assert len(metrics) >= 44
    companies = {row["entity_id"] for row in metrics}
    assert {"cn_002837_invic", "cn_300731_cotran"}.issubset(companies)

    for row in metrics:
        assert row["metric_id"].startswith("metric_company_")
        assert row["entity_type"] == "company"
        assert row["period"] in {"20251231", "20260331"}
        assert row["source_evidence_id"] in evidence_ids
        assert row["is_estimate"] == "false"
        assert "不能直接等同AI服务器液冷业务贡献" in row["notes"]


def test_company_universe_has_exposure_and_evidence() -> None:
    universe = read_csv(f"reports/segments/{SEGMENT_ID}/company_universe.csv")
    evidence_ids = {row["evidence_id"] for row in read_csv("data/manifests/evidence_manifest.csv")}

    assert len(universe) >= 5
    for row in universe:
        assert row["segment_id"] == SEGMENT_ID
        assert row["company_id"]
        assert row["stock_code"]
        assert row["stock_name"]
        assert row["exposure_type"] in {
            "revenue",
            "capacity",
            "product",
            "technology",
            "customer",
            "project",
            "narrative",
            "unknown",
        }
        assert 0 <= int(row["exposure_score"]) <= 5
        assert row["confidence"] in {"high", "medium", "low"}
        ids = split_ids(row["evidence_ids"])
        assert ids
        assert all(evidence_id in evidence_ids for evidence_id in ids)
        if row["stock_code"] in {"300731", "300602"}:
            assert int(row["exposure_score"]) <= 2


def test_segment_company_exposure_is_reusable_mapping() -> None:
    rows = read_csv("data/processed/normalized/segment_company_exposure.csv")
    evidence_ids = {row["evidence_id"] for row in read_csv("data/manifests/evidence_manifest.csv")}

    assert len(rows) >= 5
    for row in rows:
        assert row["segment_id"] == SEGMENT_ID
        assert row["company_id"].startswith("cn_")
        assert row["valid_from"] == REPORT_DATE
        ids = split_ids(row["evidence_ids"])
        assert ids
        assert all(evidence_id in evidence_ids for evidence_id in ids)


def test_quality_review_has_no_open_high_severity_issues() -> None:
    rows = read_csv("reports/p1/quality_issues.csv")
    open_high = [
        row
        for row in rows
        if row["severity"].lower() == "high" and row["status"].lower() not in {"fixed", "closed"}
    ]
    assert not open_high

    review = (ROOT / f"reports/p1/quality_review_{SEGMENT_ID}.md").read_text(encoding="utf-8")
    assert "status: PASS_WITH_MEDIUM_TODOS" in review
    assert "Tushare" in review
    assert "Case-study Calibration" in review


def test_stock_reports_follow_case_study_calibration() -> None:
    required_sections = [
        "## 1. 一页研究假设",
        "## 2. 财务质量：增长、利润率、现金流、资产负债",
        "## 3. 业务拆分：利润从哪里来",
        "## 4. 细分方向暴露：行业逻辑如何落到公司",
        "## 7. 盈利假设与敏感性",
        "## 8. 估值场景",
        "## 9. 催化剂与跟踪日历",
        "## 10. 风险、反证和可证伪条件",
    ]
    for path in [
        ROOT / "reports/stocks/002837_invic/2026-07-01_stock_deep_dive.md",
        ROOT / "reports/stocks/300731_cotran/2026-07-01_stock_deep_dive.md",
    ]:
        text = path.read_text(encoding="utf-8")
        for section in required_sections:
            assert section in text, f"{path.relative_to(ROOT)} missing {section}"
        assert "metric_company_" in text
        assert "不能把公司整体增长直接归因于AI服务器液冷" in text
        assert "MISSING: 暂无直接披露" in text


def test_no_direct_trading_instruction_phrases() -> None:
    forbidden = ["建议买入", "建议卖出", "强烈推荐", "买入评级", "卖出评级", "持有评级"]
    paths = [
        *Path(ROOT / "reports/p1").glob("*.md"),
        *Path(ROOT / "reports/segments" / SEGMENT_ID).glob("*.md"),
        *Path(ROOT / "reports/stocks").glob("*/*.md"),
    ]

    violations = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for phrase in forbidden:
            if phrase in text:
                violations.append(f"{path.relative_to(ROOT)} contains {phrase}")

    assert not violations, "\n".join(violations)
