from __future__ import annotations

import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DECISION_PATH = REPO_ROOT / "reports/p1_6/r5_after_patch55_decision.json"
EXPECTED_PATH = REPO_ROOT / "config/r5_patch_49_55_expected_artifacts.yaml"
NOTE_PATH = REPO_ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_note_reviewed_input_draft.md"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_after_patch55_decision_keeps_source_gapped_state():
    decision = load_json(DECISION_PATH)

    assert decision["current_r5_state"] == "R5_REVIEWED_INPUT_PILOT_BLOCKED_SOURCE_GAPPED"
    assert decision["reviewed_input_pilot_allowed"] is False
    assert decision["sample_quality_report_allowed"] is False
    assert decision["p2_allowed"] is False
    assert decision["strict_smoke_status"] == "pass"
    assert decision["pack_promotion_level"] == "source_gapped_research_draft"
    assert decision["rendered_output_type"] == "source_gapped_research_draft"
    assert decision["blockers"]
    for token in ["TODO_MARKET_DATA", "TODO_PEER_DATA", "TODO_MODEL_INPUT", "MISSING_DISCLOSURE"]:
        assert token in decision["known_todos"]


def test_patch49_55_expected_artifacts_exist():
    expected = load_yaml(EXPECTED_PATH)
    missing = [
        item["path"]
        for item in expected["required_artifacts"]
        if not (REPO_ROOT / item["path"]).exists()
    ]

    assert not missing


def test_rendered_reviewed_input_draft_has_no_direct_trading_language():
    text = NOTE_PATH.read_text(encoding="utf-8")

    for phrase in ["买入", "卖出", "持有", "仓位", "目标价", "保证收益", "buy rating", "sell rating", "hold rating"]:
        assert phrase.lower() not in text.lower()
