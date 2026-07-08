from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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


def test_source_gapped_pack_renders_only_degraded_draft(tmp_path: Path):
    writer = load_writer()
    out = tmp_path / "R5_stock_research_note_source_gapped.md"

    result = writer.render_source_gapped_research_draft(pack_path=PACK_PATH, output_path=out)
    text = out.read_text(encoding="utf-8")

    assert result["output_type"] == "source_gapped_research_draft"
    assert "source_gapped_research_draft" in text
    assert "TODO_MODEL_INPUT" in text
    assert "TODO_MARKET_DATA" in text
    assert "TODO_SOURCE_REQUIRED" in text
    assert "sample_quality" not in text.lower()
    assert "sample-quality" not in text.lower()


def test_source_gapped_draft_contains_all_pack_gaps(tmp_path: Path):
    writer = load_writer()
    out = tmp_path / "draft.md"

    writer.render_source_gapped_research_draft(pack_path=PACK_PATH, output_path=out)
    text = out.read_text(encoding="utf-8")

    for gap_id in [
        "R5_002837_GAP_BUSINESS_001",
        "R5_002837_GAP_FORECAST_001",
        "R5_002837_GAP_VALUATION_001",
        "R5_002837_GAP_MARKET_001",
        "R5_002837_GAP_SENTIMENT_001",
        "R5_002837_GAP_EXPOSURE_001",
    ]:
        assert gap_id in text


def test_source_gapped_draft_has_no_direct_trading_language(tmp_path: Path):
    writer = load_writer()
    out = tmp_path / "draft.md"

    writer.render_source_gapped_research_draft(pack_path=PACK_PATH, output_path=out)
    text = out.read_text(encoding="utf-8")

    for phrase in ["买入", "卖出", "持有", "仓位", "buy rating", "sell rating", "hold rating"]:
        assert phrase.lower() not in text.lower()
