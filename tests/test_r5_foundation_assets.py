from __future__ import annotations

import csv
import py_compile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

YAML_FILES = [
    REPO_ROOT / "templates/r5_stock_research_pack.yaml",
    REPO_ROOT / "benchmarks/r5_report_quality_rubric.yaml",
    REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml",
]

PYTHON_FILES = [
    REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py",
    REPO_ROOT / ".agents/skills/quality-review/scripts/validate_quality_issues.py",
    REPO_ROOT / "tests/test_validate_r5_stock_research_pack.py",
    REPO_ROOT / "tests/test_validate_quality_issues.py",
    REPO_ROOT / "tests/test_r5_foundation_assets.py",
]

CSV_FILES = [
    REPO_ROOT / ".agents/skills/quality-review/assets/r5_quality_issues.example.csv",
]

NON_COMPRESSED_FILES = [
    REPO_ROOT / "templates/r5_stock_research_pack.yaml",
    REPO_ROOT / "benchmarks/r5_report_quality_rubric.yaml",
    REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml",
    REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py",
    REPO_ROOT / "tests/test_validate_r5_stock_research_pack.py",
    REPO_ROOT / ".agents/skills/quality-review/assets/r5_quality_issues.example.csv",
    REPO_ROOT / ".agents/skills/quality-review/scripts/validate_quality_issues.py",
    REPO_ROOT / "tests/test_validate_quality_issues.py",
]

NO_ADVICE_SCAN_FILES = [
    REPO_ROOT / "templates/r5_stock_research_pack.yaml",
    REPO_ROOT / "templates/r5_stock_research_note.md",
    REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml",
    REPO_ROOT / ".agents/skills/quality-review/assets/r5_quality_issues.example.csv",
    REPO_ROOT / "reports/p1_6/R5_BUNDLE_2_RECOVERY_EXECUTABLE_GATES_READOUT.md",
]

QUALITY_ISSUE_FIELDS = {
    "issue_id",
    "severity",
    "gate_id",
    "section",
    "artifact",
    "description",
    "fix_owner_skill",
    "blocking_decision",
    "next_action",
    "status",
}

FORBIDDEN_ACTION_PHRASES = [
    "买入评级",
    "卖出评级",
    "持有评级",
    "建议买入",
    "建议卖出",
    "建议建仓",
    "仓位建议",
    "目标买点",
    "目标卖点",
]


def test_targeted_yaml_files_parse():
    for path in YAML_FILES:
        with path.open("r", encoding="utf-8") as handle:
            assert yaml.safe_load(handle) is not None, path


def test_targeted_python_files_compile():
    for path in PYTHON_FILES:
        py_compile.compile(str(path), doraise=True)


def test_quality_issue_csv_has_required_headers_and_rows():
    for path in CSV_FILES:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            assert reader.fieldnames is not None, path
            assert QUALITY_ISSUE_FIELDS.issubset(set(reader.fieldnames)), path
            assert list(reader), path


def test_targeted_files_are_not_single_physical_line_artifacts():
    for path in NON_COMPRESSED_FILES:
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) > 1, path


def test_r5_rubric_has_bundle_2_gate_coverage():
    with (REPO_ROOT / "benchmarks/r5_report_quality_rubric.yaml").open("r", encoding="utf-8") as handle:
        rubric = yaml.safe_load(handle)

    required_sections = set(rubric["required_sections"])
    gate_names = {gate["name"].lower() for gate in rubric["quality_gates"]}
    thresholds = rubric["sample_quality_thresholds"]

    assert "financial_overview" in required_sections
    assert "business_breakdown" in required_sections
    assert "industry_analysis" in required_sections
    assert "forecast" in required_sections
    assert "valuation" in required_sections
    assert "technical_analysis" in required_sections
    assert "sentiment_analysis" in required_sections
    assert "catalyst_events" in required_sections
    assert "research_conclusion" in required_sections
    assert any("no-advice" in name for name in gate_names)
    assert thresholds["source_gap_must_be_visible"] is True


def test_no_direct_trading_phrases_in_r5_templates_examples_or_readout():
    for path in NO_ADVICE_SCAN_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for phrase in FORBIDDEN_ACTION_PHRASES:
            assert phrase not in text, f"{phrase} found in {path}"
