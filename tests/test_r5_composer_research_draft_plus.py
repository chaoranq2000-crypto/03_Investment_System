from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WRITER_PATH = REPO_ROOT / "src/report/stock_report_writer.py"
PACK_PATH = REPO_ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_pack_source_gapped.yaml"


def load_writer():
    spec = importlib.util.spec_from_file_location("stock_report_writer", WRITER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_scorecard(path: Path) -> None:
    data = {
        "artifact_type": "R5_quality_scorecard_v2",
        "allowed_report_level": "reviewed_input_research_draft",
        "sections": [
            {
                "section_id": "financial",
                "readiness": "ready_with_limitations",
                "evidence_ids": ["ev_financial"],
                "issues": [],
                "limitations": ["company-level metrics only"],
                "fix_owner_skill": "stock-deep-dive",
            },
            {
                "section_id": "valuation",
                "readiness": "source_gapped",
                "evidence_ids": [],
                "issues": ["TODO_MARKET_DATA", "TODO_PEER_DATA"],
                "limitations": ["reviewed valuation inputs absent"],
                "fix_owner_skill": "stock-deep-dive",
            },
        ],
        "sample_quality_blockers": ["valuation reviewed inputs absent"],
        "next_actions": ["register reviewed valuation inputs"],
    }
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_reviewed_input_mode_renders_mixed_readiness_sections(tmp_path: Path):
    writer = load_writer()
    scorecard = tmp_path / "scorecard.yaml"
    output = tmp_path / "draft_plus.md"
    write_scorecard(scorecard)

    result = writer.render_reviewed_input_research_draft(pack_path=PACK_PATH, scorecard_path=scorecard, output_path=output)
    text = output.read_text(encoding="utf-8")

    assert result["output_type"] == "reviewed_input_research_draft"
    assert result["reviewed_sections"] == 1
    assert "financial" in text
    assert "TODO_MARKET_DATA" in text
    assert "Source Gap Appendix" in text


def test_reviewed_input_mode_has_no_direct_trading_language(tmp_path: Path):
    writer = load_writer()
    scorecard = tmp_path / "scorecard.yaml"
    output = tmp_path / "draft_plus.md"
    write_scorecard(scorecard)

    writer.render_reviewed_input_research_draft(pack_path=PACK_PATH, scorecard_path=scorecard, output_path=output)
    text = output.read_text(encoding="utf-8")

    for phrase in ["买入", "卖出", "持有", "仓位", "buy rating", "sell rating", "hold rating"]:
        assert phrase.lower() not in text.lower()
