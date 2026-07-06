from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_stock_deep_dive_references_data_layer_pack_consumption() -> None:
    skill = (ROOT / ".agents/skills/stock-deep-dive/SKILL.md").read_text(encoding="utf-8")
    reference = ROOT / ".agents/skills/stock-deep-dive/references/data_layer_pack_consumption.md"
    text = reference.read_text(encoding="utf-8")
    assert "references/data_layer_pack_consumption.md" in skill
    assert "TODO_MARKET_DATA" in text
    assert "TODO_PEER_DATA" in text
    assert "MISSING_DISCLOSURE" in text
    assert "Tushare/Baostock data cannot prove" in text


def test_quality_review_has_data_layer_pack_gate() -> None:
    quality = (ROOT / ".agents/skills/quality-review/SKILL.md").read_text(encoding="utf-8")
    assert "### G7-DL Data Layer Pack Check" in quality
    assert "parent_gate_id: G7" in quality
    assert "valuation_snapshot.yaml" in quality
    assert "TODO_STRUCTURED_FINANCIAL_DATA" in quality
    assert "MISSING_DISCLOSURE" in quality
