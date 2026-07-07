from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
RUBRIC_PATH = REPO_ROOT / "benchmarks/r5_report_quality_rubric.yaml"
DENSITY_PATH = REPO_ROOT / "benchmarks/r5_section_density_targets.yaml"
README_PATH = REPO_ROOT / "benchmarks/sample_reports/README.md"
NOTE_FIXTURE_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_stock_research_note.fixture.md"


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_density_targets_yaml_parses_and_covers_sections():
    data = load_yaml(DENSITY_PATH)
    sections = data["sections"]
    for section in ["financial_overview", "business_breakdown", "industry_analysis", "forecast", "valuation", "technical", "sentiment", "catalyst", "conclusion"]:
        assert section in sections
        assert sections[section]["required"]
        assert sections[section]["optional"] is not None
        assert sections[section]["blocked"]


def test_rubric_blocks_missing_forecast_and_valuation_inputs():
    rubric = load_yaml(RUBRIC_PATH)
    blocking = rubric["blocking_rules"]
    assert blocking["forecast_missing"]["decision"] == "research_draft_only"
    assert blocking["valuation_market_snapshot_missing"]["decision"] == "research_draft_only"
    assert blocking["peer_context_missing"]["decision"] == "research_draft_only"
    thresholds = rubric["sample_quality_thresholds"]
    assert thresholds["forecast_base_case_required"] is True
    assert thresholds["valuation_market_snapshot_required"] is True
    assert thresholds["valuation_peer_context_required"] is True


def test_source_gap_and_no_advice_rules_are_explicit():
    rubric = load_yaml(RUBRIC_PATH)
    assert rubric["sample_quality_thresholds"]["source_gap_must_be_visible"] is True
    assert rubric["sample_quality_thresholds"]["hidden_todo_allowed"] is False
    gates = {gate["gate_id"]: gate for gate in rubric["quality_gates"]}
    assert gates["R5-G10"]["name"] == "No-Advice Gate"
    assert rubric["blocking_rules"]["direct_trading_instruction"]["decision"] == "blocked"


def test_fixture_note_keeps_todos_and_avoids_trading_advice():
    text = NOTE_FIXTURE_PATH.read_text(encoding="utf-8")
    for token in ["TODO_SOURCE_REQUIRED", "MISSING_DISCLOSURE", "TODO_MODEL_INPUT"]:
        assert token in text
    for phrase in ["建议买入", "建议卖出", "仓位建议", "买入评级", "卖出评级"]:
        assert phrase not in text


def test_sample_report_policy_does_not_contain_external_report_body():
    text = README_PATH.read_text(encoding="utf-8")
    assert "Do not paste full external" in text
    assert "full report text" in text
