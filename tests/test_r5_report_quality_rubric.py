from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
RUBRIC_PATH = REPO_ROOT / "benchmarks/r5_report_quality_rubric.yaml"


def load_rubric() -> dict:
    with RUBRIC_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_r5_rubric_yaml_parses():
    data = load_rubric()
    assert data["artifact_type"] == "R5_report_quality_rubric"


def test_required_sections_cover_r5_report_shape():
    required_sections = set(load_rubric()["required_sections"])
    assert {
        "preface",
        "financial_overview",
        "business_breakdown",
        "industry_analysis",
        "forecast",
        "valuation",
        "technical_analysis",
        "sentiment_analysis",
        "catalyst_events",
        "research_conclusion",
    }.issubset(required_sections)


def test_each_r5_section_has_required_optional_and_blocked_conditions():
    sections = load_rubric()["required_sections"]
    for name, config in sections.items():
        assert config.get("required_conditions"), name
        assert "optional_conditions" in config, name
        assert config.get("blocked_conditions"), name


def test_blocking_rules_include_core_risks():
    blocking_rules = set(load_rubric()["blocking_rules"])
    assert {
        "unsupported_number",
        "hidden_todo_or_missing_disclosure",
        "direct_trading_instruction",
    }.issubset(blocking_rules)


def test_r5_gate_ids_are_complete():
    gate_ids = {gate["gate_id"] for gate in load_rubric()["quality_gates"]}
    assert {f"R5-G{i}" for i in range(1, 12)}.issubset(gate_ids)


def test_sample_quality_thresholds_block_high_issues_and_require_no_advice_gate():
    thresholds = load_rubric()["sample_quality_thresholds"]
    assert thresholds["high_issue_count_must_equal"] == 0
    assert thresholds["no_advice_gate_required"] is True
