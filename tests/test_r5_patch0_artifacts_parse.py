from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

YAML_FILES = [
    REPO_ROOT / "templates/r5_stock_research_pack.yaml",
    REPO_ROOT / "benchmarks/r5_report_quality_rubric.yaml",
]

MULTILINE_FILES = [
    REPO_ROOT / "docs/workflows/R5_SAMPLE_QUALITY_STOCK_REPORT_SPEC.md",
    REPO_ROOT / "docs/workflows/R5_MVP_RESTRUCTURE_PLAN.md",
    REPO_ROOT / "templates/r5_stock_research_pack.yaml",
    REPO_ROOT / "templates/r5_stock_research_note.md",
    REPO_ROOT / "benchmarks/r5_report_quality_rubric.yaml",
    REPO_ROOT / "reports/p1_6/R5_MVP_PATCH_0_PLAN.md",
    REPO_ROOT / "codex_tasks/R5_PATCH_0_TASK_CARD.md",
]

SPEC_PATH = REPO_ROOT / "docs/workflows/R5_SAMPLE_QUALITY_STOCK_REPORT_SPEC.md"
NOTE_TEMPLATE_PATH = REPO_ROOT / "templates/r5_stock_research_note.md"


def test_r5_yaml_artifacts_parse():
    for path in YAML_FILES:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data is not None, path


def test_r5_patch0_artifacts_are_not_single_line_blobs():
    for path in MULTILINE_FILES:
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) >= 8, path


def test_r5_note_template_has_enough_report_sections():
    text = NOTE_TEMPLATE_PATH.read_text(encoding="utf-8")
    headings = re.findall(r"^#{1,2}\s+", text, flags=re.MULTILINE)
    assert len(headings) >= 8


def test_r5_spec_keeps_core_semantic_boundaries():
    text = SPEC_PATH.read_text(encoding="utf-8")
    required_needles = [
        "R4",
        "R5",
        "R5_stock_research_pack.yaml",
        "事实源",
        "company_identity_pack",
        "evidence_snapshot_pack",
        "financial_history_pack",
        "business_breakdown_pack",
        "segment_exposure_pack",
        "industry_context_pack",
        "peer_comparison_pack",
        "forecast_model_pack",
        "valuation_pack",
        "technical_market_pack",
        "sentiment_event_pack",
        "risk_counterevidence_pack",
        "前言",
        "财务概览",
        "业务拆分",
        "行业分析",
        "盈利预测",
        "估值分析",
        "技术分析",
        "情绪分析",
        "事件驱动",
        "研究结论",
        "降级",
    ]
    missing = [needle for needle in required_needles if needle not in text]
    assert not missing
    assert "no-advice" in text.lower()
