from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = REPO_ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
PACK_PATH = RUN_DIR / "R5_stock_research_pack_source_gapped.yaml"
PLAN_PATH = RUN_DIR / "R5_evidence_plan_from_gaps.yaml"
GAP_REPORT_PATH = RUN_DIR / "R5_source_gap_report.md"
OPEN_QUESTIONS_PATH = RUN_DIR / "R5_open_questions.md"


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_002837_source_gapped_pack_keeps_research_draft_boundary():
    pack = load_yaml(PACK_PATH)

    assert pack["pack_status"] == "research_draft"
    assert pack["quality_status"]["allowed_report_level"] == "research_draft"
    assert pack["quality_status"]["no_advice_gate_passed"] is True
    assert pack["forecast_model_pack"]["status"] == "TODO"
    assert pack["valuation_pack"]["status"] == "TODO"
    assert pack["technical_market_pack"]["status"] == "TODO"
    assert pack["sentiment_event_pack"]["status"] == "TODO"


def test_002837_source_gap_register_covers_required_sections():
    pack = load_yaml(PACK_PATH)
    sections = {item["section"] for item in pack["source_gap_register"]}

    assert {
        "business_breakdown",
        "forecast",
        "valuation",
        "technical_market",
        "sentiment_event",
        "segment_exposure",
    }.issubset(sections)


def test_002837_gap_artifacts_are_multiline_and_parseable():
    load_yaml(PACK_PATH)
    load_yaml(PLAN_PATH)
    assert len(GAP_REPORT_PATH.read_text(encoding="utf-8").splitlines()) > 8
    assert len(OPEN_QUESTIONS_PATH.read_text(encoding="utf-8").splitlines()) > 8
