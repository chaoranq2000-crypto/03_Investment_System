from __future__ import annotations

import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PATH = REPO_ROOT / "config/r5_bundle3_expected_artifacts.yaml"
PREFLIGHT_PATH = REPO_ROOT / "reports/p1_6/r5_core_asset_preflight_result.json"
CLOSE_READOUT = REPO_ROOT / "reports/p1_6/R5_BUNDLE_3_CORE_RESEARCH_ASSET_SUBPACKS_CLOSE_READOUT.md"


def test_bundle3_expected_artifacts_exist():
    expected = yaml.safe_load(EXPECTED_PATH.read_text(encoding="utf-8"))
    paths: list[str] = []
    for group in expected["artifacts"].values():
        for value in group.values():
            if isinstance(value, str):
                paths.append(value)
    missing = [path for path in paths if not (REPO_ROOT / path).exists()]

    assert not missing


def test_bundle3_preflight_fails_closed_with_todos():
    result = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))

    assert result["core_asset_state"] == "R5_CORE_ASSET_SCHEMAS_EXECUTABLE_WITH_TODOS"
    assert result["financial_history_status"] == "accepted_with_todos"
    assert result["business_breakdown_status"] == "accepted_with_todos"
    assert result["forecast_model_status"] == "accepted_with_todos"
    assert result["valuation_status"] == "accepted_with_todos"
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False
    assert result["blockers"] == []


def test_bundle3_close_readout_freezes_next_decision():
    text = CLOSE_READOUT.read_text(encoding="utf-8")

    assert "current_r5_state: `R5_CORE_ASSET_SCHEMAS_EXECUTABLE_WITH_TODOS`" in text
    assert "sample_quality_report_allowed: `false`" in text
    assert "p2_allowed: `false`" in text
    assert "R5 Bundle 4" in text
