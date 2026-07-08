from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/r5_minimal_stock_run"
PACK_PATH = FIXTURE_DIR / "R5_stock_research_pack.yaml"
ISSUES_PATH = FIXTURE_DIR / "R5_quality_issues.csv"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_pack_validator():
    return load_module(
        "validate_r5_stock_research_pack",
        REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py",
    )


def test_valid_source_gapped_fixture_round_trip(tmp_path: Path):
    pack_validator = load_pack_validator()
    pack = pack_validator.load_yaml(PACK_PATH)
    issues = pack_validator.validate_pack_issues(pack)
    assert issues == []
    assert pack_validator.derive_decision(pack, issues) == "accepted_with_todos"

    for name, script, asset in [
        ("forecast", "validate_r5_forecast_model.py", "r5_forecast_model.example.yaml"),
        ("valuation", "validate_r5_valuation_pack.py", "r5_valuation_pack.example.yaml"),
    ]:
        validator = load_module(name, REPO_ROOT / f".agents/skills/stock-deep-dive/scripts/{script}")
        assert validator.main([str(REPO_ROOT / f".agents/skills/stock-deep-dive/assets/{asset}")]) == 0

    composer = load_module(
        "compose_r5_report_from_pack",
        REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/compose_r5_report_from_pack.py",
    )
    output = tmp_path / "R5_stock_research_note.md"
    assert composer.main([str(PACK_PATH), str(output)]) == 0
    note = output.read_text(encoding="utf-8")
    assert "Source Gap Appendix" in note
    assert "TODO_SOURCE_REQUIRED" in note
    assert "MISSING_DISCLOSURE" in note
    for phrase in ["建议买入", "建议卖出", "持有评级", "仓位建议"]:
        assert phrase not in note

    quality_validator = load_module(
        "validate_quality_issues",
        REPO_ROOT / ".agents/skills/quality-review/scripts/validate_quality_issues.py",
    )
    rows = quality_validator.load_issues(ISSUES_PATH)
    errors = quality_validator.validate_quality_issues(rows)
    assert errors == []
    assert quality_validator.derive_outcome(rows, errors) == "accepted_with_todos"


def test_invalid_missing_valuation_pack_is_blocked_or_downgraded():
    pack_validator = load_pack_validator()
    pack = pack_validator.load_yaml(PACK_PATH)
    pack.pop("valuation_pack")

    issues = pack_validator.validate_pack_issues(pack)

    assert any(issue["path"] == "valuation_pack" for issue in issues)
    assert pack_validator.derive_decision(pack, issues) in {"needs_fix", "blocked"}


def test_invalid_hidden_source_gap_is_blocked():
    pack_validator = load_pack_validator()
    pack = copy.deepcopy(pack_validator.load_yaml(PACK_PATH))
    pack["source_gap_register"] = []

    issues = pack_validator.validate_pack_issues(pack)

    assert any(issue["path"] == "source_gap_register" for issue in issues)
    assert pack_validator.derive_decision(pack, issues) in {"needs_fix", "blocked"}


def test_sample_quality_candidate_with_missing_valuation_is_downgraded():
    pack_validator = load_pack_validator()
    pack = copy.deepcopy(pack_validator.load_yaml(PACK_PATH))
    pack["pack_status"] = "sample_quality_candidate"
    pack["quality_status"]["allowed_report_level"] = "sample_quality_ready"
    pack["quality_status"]["no_advice_gate_passed"] = True
    pack["valuation_pack"]["status"] = "TODO"

    composer = load_module(
        "compose_r5_report_from_pack",
        REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/compose_r5_report_from_pack.py",
    )
    note = composer.compose_note(pack)

    assert "pack_status: research_draft" in note
    assert "valuation_pack" in note
