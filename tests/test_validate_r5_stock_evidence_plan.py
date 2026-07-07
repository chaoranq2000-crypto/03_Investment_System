from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/evidence-ingest/scripts/validate_r5_stock_evidence_plan.py"
EXAMPLE_PATH = REPO_ROOT / ".agents/skills/evidence-ingest/assets/r5_stock_evidence_plan.example.yaml"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_stock_evidence_plan", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_example() -> dict:
    return yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))


def test_example_plan_validates(capsys):
    validator = load_validator()
    assert validator.main([str(EXAMPLE_PATH)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"] == "accepted"
    assert payload["issues"] == []


def test_required_families_are_present():
    validator = load_validator()
    data = load_example()
    data["evidence_plan"].pop("official_filings")
    issues = validator.validate_plan(data)
    assert any("official_filings" in item["path"] for item in issues)


def test_each_request_requires_priority_pack_freshness_and_fallback():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    request = data["evidence_plan"]["market_snapshot"]["requests"][0]
    request.pop("required_for_pack")
    request.pop("freshness_requirement")
    request.pop("fallback_if_missing")
    issues = validator.validate_plan(data)
    paths = {item["path"] for item in issues}
    assert "evidence_plan.market_snapshot.requests[0].required_for_pack" in paths
    assert "evidence_plan.market_snapshot.requests[0].freshness_requirement" in paths
    assert "evidence_plan.market_snapshot.requests[0].fallback_if_missing" in paths


def test_official_disclosures_outrank_context_sources():
    validator = load_validator()
    data = load_example()
    data["evidence_plan"]["news_event_clues"]["source_priority"] = 1
    issues = validator.validate_plan(data)
    assert any("official disclosures must outrank" in item["message"] for item in issues)


def test_missing_official_disclosure_uses_missing_disclosure():
    validator = load_validator()
    data = load_example()
    data["evidence_plan"]["official_filings"]["requests"][0]["fallback_if_missing"] = "TODO_SOURCE_REQUIRED"
    issues = validator.validate_plan(data)
    assert any("MISSING_DISCLOSURE" in item["message"] for item in issues)


def test_expected_artifacts_are_required():
    validator = load_validator()
    data = load_example()
    data["expected_artifacts"]["ingest_log"] = False
    issues = validator.validate_plan(data)
    assert any(item["path"] == "expected_artifacts.ingest_log" for item in issues)
