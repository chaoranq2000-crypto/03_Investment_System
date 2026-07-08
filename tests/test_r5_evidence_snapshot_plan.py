from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/evidence-ingest/scripts/validate_r5_evidence_plan.py"
TEMPLATE_PATH = REPO_ROOT / ".agents/skills/evidence-ingest/assets/r5_stock_evidence_plan_template.yaml"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_evidence_plan", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_template() -> dict:
    return yaml.safe_load(TEMPLATE_PATH.read_text(encoding="utf-8"))


def test_template_yaml_is_parseable_and_valid_enough(capsys):
    validator = load_validator()
    assert validator.main([str(TEMPLATE_PATH)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"] in {"accepted", "accepted_with_todos"}
    assert payload["issues"] == []


def test_missing_official_filing_request_is_high_issue():
    validator = load_validator()
    data = load_template()
    data["evidence_requests"].pop("official_filings")
    issues = validator.validate_plan(data)
    assert any(item["severity"] == "high" and "official" in item["path"] for item in issues)


def test_official_annual_request_is_required():
    validator = load_validator()
    data = load_template()
    data["evidence_requests"]["official_filings"] = [
        item for item in data["evidence_requests"]["official_filings"] if "annual" not in item["evidence_need"]
    ]
    issues = validator.validate_plan(data)
    assert any("annual report request" in item["message"] for item in issues)


def test_market_peer_and_news_cannot_prove_business_exposure():
    validator = load_validator()
    data = load_template()
    data["evidence_requests"]["market_snapshot"][0]["allowed_usage"].append("business_exposure")
    data["evidence_requests"]["peer_snapshot"][0]["allowed_usage"].append("profit_exposure")
    data["evidence_requests"]["news_event_clues"][0]["allowed_usage"].append("customer_exposure")
    issues = validator.validate_plan(data)
    paths = {item["path"] for item in issues}
    assert "evidence_requests.market_snapshot[0].allowed_usage" in paths
    assert "evidence_requests.peer_snapshot[0].allowed_usage" in paths
    assert "evidence_requests.news_event_clues[0].allowed_usage" in paths


def test_each_request_requires_source_rank_as_of_date_freshness_and_allowed_usage():
    validator = load_validator()
    data = load_template()
    broken = data["evidence_requests"]["structured_financial_metrics"][0]
    broken.pop("source_rank")
    broken.pop("as_of_date")
    broken["freshness_policy"] = ""
    broken["allowed_usage"] = []
    issues = validator.validate_plan(data)
    paths = {item["path"] for item in issues}
    assert "evidence_requests.structured_financial_metrics[0].source_rank" in paths
    assert "evidence_requests.structured_financial_metrics[0].as_of_date" in paths
    assert "evidence_requests.structured_financial_metrics[0].freshness_policy" in paths
    assert "evidence_requests.structured_financial_metrics[0].allowed_usage" in paths


def test_collected_request_requires_evidence_id_or_source_path():
    validator = load_validator()
    data = load_template()
    request = data["evidence_requests"]["official_filings"][0]
    request["status"] = "collected"
    request["evidence_id"] = None
    request.pop("source_path", None)
    issues = validator.validate_plan(data)
    assert any(item["path"].endswith(".evidence_id") for item in issues)


def test_handoff_fields_are_required_for_r5_pack_consumption():
    validator = load_validator()
    data = copy.deepcopy(load_template())
    data["handoff_to_stock_deep_dive"].pop("source_gap_register_path")
    issues = validator.validate_plan(data)
    assert any(item["path"] == "handoff_to_stock_deep_dive.source_gap_register_path" for item in issues)
