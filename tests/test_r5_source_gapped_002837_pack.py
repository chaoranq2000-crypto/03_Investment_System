from __future__ import annotations

import yaml
import pytest

# Published historical results; current algorithms are covered in the default suite.
pytestmark = pytest.mark.legacy_compatibility

HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
PACK_SOURCE = f"{HISTORICAL_RUN}/R5_stock_research_pack_source_gapped.yaml"
PLAN_SOURCE = f"{HISTORICAL_RUN}/R5_evidence_plan_from_gaps.yaml"
GAP_REPORT_SOURCE = f"{HISTORICAL_RUN}/R5_source_gap_report.md"
OPEN_QUESTIONS_SOURCE = f"{HISTORICAL_RUN}/R5_open_questions.md"


def load_historical_yaml(historical_blob_bytes, source_path: str) -> dict:
    data = yaml.safe_load(historical_blob_bytes(source_path).decode("utf-8"))
    assert isinstance(data, dict)
    return data


def test_002837_source_gapped_pack_keeps_research_draft_boundary(
    historical_blob_bytes,
):
    pack = load_historical_yaml(historical_blob_bytes, PACK_SOURCE)

    assert pack["pack_status"] == "research_draft"
    assert pack["quality_status"]["allowed_report_level"] == "research_draft"
    assert pack["quality_status"]["no_advice_gate_passed"] is True
    assert pack["forecast_model_pack"]["status"] == "TODO"
    assert pack["valuation_pack"]["status"] == "TODO"
    assert pack["technical_market_pack"]["status"] == "TODO"
    assert pack["sentiment_event_pack"]["status"] == "TODO"


def test_002837_source_gap_register_covers_required_sections(
    historical_blob_bytes,
):
    pack = load_historical_yaml(historical_blob_bytes, PACK_SOURCE)
    sections = {item["section"] for item in pack["source_gap_register"]}

    assert {
        "business_breakdown",
        "forecast",
        "valuation",
        "technical_market",
        "sentiment_event",
        "segment_exposure",
    }.issubset(sections)


def test_002837_gap_artifacts_are_multiline_and_parseable(
    historical_blob_bytes,
):
    load_historical_yaml(historical_blob_bytes, PACK_SOURCE)
    load_historical_yaml(historical_blob_bytes, PLAN_SOURCE)
    gap_report = historical_blob_bytes(GAP_REPORT_SOURCE).decode("utf-8")
    open_questions = historical_blob_bytes(OPEN_QUESTIONS_SOURCE).decode("utf-8")
    assert len(gap_report.splitlines()) > 8
    assert len(open_questions.splitlines()) > 8
