from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".agents" / "skills"
SDD = SKILLS / "stock-deep-dive"
OLD_SKILL_NAMES = ["stock-" + "research-analyst", "stock-" + "report-writer", "stock-" + "report-write"]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_legacy_skill_directories_removed():
    for name in OLD_SKILL_NAMES:
        assert not (SKILLS / name).exists()


def test_merged_references_and_assets_exist():
    required = [
        SDD / "references" / "analysis_pack_contract.md",
        SDD / "references" / "business_breakdown_contract.md",
        SDD / "references" / "forecast_valuation_contract.md",
        SDD / "references" / "market_sentiment_event_contract.md",
        SDD / "references" / "report_style_guide.md",
        SDD / "references" / "legacy_stock_skill_rules.md",
        SDD / "assets" / "stock_analysis_pack_template.yaml",
        SDD / "assets" / "stock_deep_dive_report_template.md",
    ]
    for path in required:
        assert path.exists(), path


def test_config_uses_only_stock_deep_dive_for_stock_skill():
    config = read(ROOT / ".codex" / "config.toml")
    assert ".agents/skills/stock-deep-dive" in config
    for name in OLD_SKILL_NAMES:
        assert name not in config


def test_stock_report_quality_upgrade_snippet_is_retired():
    snippet = read(ROOT / ".codex" / "config.stock_report_quality_upgrade.snippet.toml")
    assert "Deprecated" in snippet
    assert "[[skills.config]]" not in snippet


def test_active_routing_docs_do_not_reference_legacy_stock_skills():
    docs = [
        ROOT / "README.md",
        ROOT / "docs" / "workflows" / "RESEARCH_WORKFLOW.md",
        ROOT / "docs" / "workflows" / "WORKFLOW_ORCHESTRATION_SPEC.md",
        ROOT / ".agents" / "skills" / "research-orchestrator" / "references" / "skill_routing_matrix.md",
        ROOT / ".agents" / "skills" / "research-orchestrator" / "SKILL.md",
    ]
    for path in docs:
        if not path.exists():
            continue
        text = read(path)
        for name in OLD_SKILL_NAMES:
            assert name not in text, f"{name} remains in {path}"


def test_stock_deep_dive_keeps_no_advice_boundary():
    text = read(SDD / "SKILL.md")
    assert "no buy/sell/hold" in text
    assert "position sizing" in text
    assert "direct trading instruction" in text
    assert "legacy_stock_skill_rules.md" in text


def test_legacy_stock_skill_rules_are_migrated_not_routed():
    text = read(SDD / "references" / "legacy_stock_skill_rules.md")
    assert "Report drafting translates" in text
    assert "not_needed" in text
    assert "Separate active routing" in text
    assert "quality-review" in text


def test_revenue_and_profit_exposure_require_missing_disclosure_without_source():
    text = read(SDD / "SKILL.md")
    assert "revenue_pct" in text
    assert "profit_pct" in text
    assert "MISSING_DISCLOSURE" in text
    assert "directly" in text and "disclosed" in text


def test_product_line_clue_is_not_promoted_to_financial_exposure():
    text = read(SDD / "SKILL.md")
    assert "product_line_clue" in text
    assert "must not be promoted" in text
    assert "revenue exposure" in text
    assert "profit" in text
