from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py"
VALID_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_stock_research_pack.valid.example.yaml"
INVALID_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_stock_research_pack.invalid.example.yaml"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_stock_research_pack", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def issue_paths(issues: list[dict[str, str]]) -> set[str]:
    return {issue["path"] for issue in issues}


def test_valid_fixture_returns_json_decision(capsys):
    validator = load_validator()
    assert validator.main(["--pack", str(VALID_PATH)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"] == "accepted_with_todos"
    assert payload["issues"] == []


def test_invalid_fixture_has_high_issues_and_not_accepted(capsys):
    validator = load_validator()
    assert validator.main(["--pack", str(INVALID_PATH)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"] in {"blocked", "needs_fix"}
    assert any(issue["severity"] == "high" for issue in payload["issues"])


def test_missing_company_or_evidence_blocks():
    validator = load_validator()
    data = load_yaml(VALID_PATH)
    data.pop("company_identity_pack")
    data.pop("evidence_snapshot_pack")
    issues = validator.validate_pack_issues(data)
    assert {"company_identity_pack", "evidence_snapshot_pack"}.issubset(issue_paths(issues))
    assert validator.derive_decision(data, issues) == "blocked"


def test_material_value_requires_source_reference():
    validator = load_validator()
    data = load_yaml(VALID_PATH)
    revenue = data["business_breakdown_pack"]["business_lines"][0]["revenue"]
    revenue["value"] = 100
    revenue.pop("missing_reason", None)
    issues = validator.validate_pack_issues(data)
    assert any("non-null value requires evidence_id or metric_id" in issue["description"] for issue in issues)


def test_material_null_requires_missing_reason():
    validator = load_validator()
    data = load_yaml(VALID_PATH)
    gross_margin = data["business_breakdown_pack"]["business_lines"][0]["gross_margin"]
    gross_margin.pop("missing_reason", None)
    issues = validator.validate_pack_issues(data)
    assert any("value is null" in issue["description"] for issue in issues)


def test_technical_and_sentiment_require_as_of_date_for_strong_judgement():
    validator = load_validator()
    data = load_yaml(VALID_PATH)
    data["technical_market_pack"]["status"] = "ready"
    data["technical_market_pack"]["trend_judgement"] = "strong trend"
    data["sentiment_event_pack"]["status"] = "ready"
    data["sentiment_event_pack"]["company_sentiment"] = {"summary": "strong sentiment"}
    issues = validator.validate_pack_issues(data)
    paths = issue_paths(issues)
    assert "technical_market_pack.as_of_date" in paths
    assert "sentiment_event_pack.as_of_date" in paths


def test_forecast_years_and_metrics_are_required():
    validator = load_validator()
    data = load_yaml(VALID_PATH)
    data["forecast_model_pack"]["forecast_years"] = ["2026E"]
    data["forecast_model_pack"]["required_metrics"] = ["revenue"]
    issues = validator.validate_pack_issues(data)
    paths = issue_paths(issues)
    assert "forecast_model_pack.forecast_years" in paths
    assert "forecast_model_pack.required_metrics" in paths


def test_sample_quality_requires_market_snapshot_and_no_advice_gate():
    validator = load_validator()
    data = load_yaml(VALID_PATH)
    data["quality_status"]["allowed_report_level"] = "sample_quality_ready"
    data["quality_status"]["no_advice_gate_passed"] = False
    issues = validator.validate_pack_issues(data)
    paths = issue_paths(issues)
    assert "quality_status.no_advice_gate_passed" in paths
    assert "valuation_pack.market_snapshot.current_price" in paths


def test_todo_tokens_must_be_visible_in_source_gap_register():
    validator = load_validator()
    data = copy.deepcopy(load_yaml(VALID_PATH))
    data["source_gap_register"] = []
    issues = validator.validate_pack_issues(data)
    assert any(issue["path"] == "source_gap_register" for issue in issues)
