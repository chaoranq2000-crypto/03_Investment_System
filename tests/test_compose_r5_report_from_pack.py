from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/compose_r5_report_from_pack.py"
PACK_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml"


def load_composer():
    spec = importlib.util.spec_from_file_location("compose_r5_report_from_pack", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_composes_fixture_note(tmp_path: Path):
    composer = load_composer()
    output = tmp_path / "R5_stock_research_note.fixture.md"
    assert composer.main([str(PACK_PATH), str(output)]) == 0
    text = output.read_text(encoding="utf-8")
    assert "pack_status: research_draft" in text
    assert "Source Gap Appendix" in text


def test_required_sections_are_present():
    composer = load_composer()
    pack = composer.load_pack(PACK_PATH)
    text = composer.compose_note(pack)
    for section in ["前言", "财务概览", "业务拆分", "行业分析", "盈利预测", "估值分析", "技术分析", "情绪分析", "事件驱动", "研究结论", "Source Gap Appendix"]:
        assert section in text


def test_todo_missing_tokens_are_preserved():
    composer = load_composer()
    pack = composer.load_pack(PACK_PATH)
    text = composer.compose_note(pack)
    assert "TODO_SOURCE_REQUIRED" in text
    assert "MISSING_DISCLOSURE" in text
    assert "TODO_MODEL_INPUT" in text


def test_composer_does_not_introduce_new_numbers():
    composer = load_composer()
    pack_text = PACK_PATH.read_text(encoding="utf-8")
    note = composer.compose_note(composer.load_pack(PACK_PATH))
    assert composer.numeric_tokens(note) - composer.numeric_tokens(pack_text) == set()


def test_no_trading_action_language():
    composer = load_composer()
    text = composer.compose_note(composer.load_pack(PACK_PATH))
    for phrase in ["建议买入", "建议卖出", "仓位建议", "保证收益"]:
        assert phrase not in text
