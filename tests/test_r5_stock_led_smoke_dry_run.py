from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/r5_minimal_stock_run"
PACK_PATH = FIXTURE_DIR / "R5_stock_research_pack.yaml"
ISSUES_PATH = FIXTURE_DIR / "R5_quality_issues.csv"
EXPECTED_NOTE_PATH = FIXTURE_DIR / "expected_R5_stock_research_note.md"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fixture_pack_passes_r5_pack_validator():
    validator = load_module(
        "validate_r5_stock_research_pack",
        REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py",
    )
    data = validator.load_yaml(PACK_PATH)
    issues = validator.validate_pack_issues(data)
    assert issues == []
    assert validator.derive_decision(data, issues) == "accepted_with_todos"


def test_subpack_validators_accept_fixture_examples():
    for name, script, asset in [
        ("forecast", "validate_r5_forecast_model.py", "r5_forecast_model.example.yaml"),
        ("valuation", "validate_r5_valuation_pack.py", "r5_valuation_pack.example.yaml"),
        ("technical", "validate_r5_technical_market_pack.py", "r5_technical_market_pack.example.yaml"),
        ("sentiment", "validate_r5_sentiment_event_pack.py", "r5_sentiment_event_pack.example.yaml"),
    ]:
        module = load_module(name, REPO_ROOT / f".agents/skills/stock-deep-dive/scripts/{script}")
        path = REPO_ROOT / f".agents/skills/stock-deep-dive/assets/{asset}"
        assert module.main([str(path)]) == 0


def test_quality_issue_validator_returns_accepted_with_todos():
    validator = load_module(
        "validate_quality_issues",
        REPO_ROOT / ".agents/skills/quality-review/scripts/validate_quality_issues.py",
    )
    rows = validator.load_issues(ISSUES_PATH)
    errors = validator.validate_quality_issues(rows)
    assert errors == []
    assert validator.derive_outcome(rows, errors) == "accepted_with_todos"


def test_composer_generates_expected_shape(tmp_path: Path):
    composer = load_module(
        "compose_r5_report_from_pack",
        REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/compose_r5_report_from_pack.py",
    )
    output = tmp_path / "R5_stock_research_note.md"
    assert composer.main([str(PACK_PATH), str(output)]) == 0
    text = output.read_text(encoding="utf-8")
    expected = EXPECTED_NOTE_PATH.read_text(encoding="utf-8")
    for needle in ["pack_status: research_draft", "Source Gap Appendix", "TODO_SOURCE_REQUIRED", "MISSING_DISCLOSURE"]:
        assert needle in text
        assert needle in expected


def test_fixture_is_not_real_stock_report():
    text = EXPECTED_NOTE_PATH.read_text(encoding="utf-8")
    assert "示例公司" in text
    assert "fixture_or_reviewed_pack_translation_only" in text
    for phrase in ["建议买入", "建议卖出", "仓位建议", "保证收益"]:
        assert phrase not in text
