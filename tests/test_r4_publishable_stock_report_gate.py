from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "qa"))

from check_no_unsupported_advice import find_unsupported_advice  # noqa: E402
from r4_publishable_stock_report_gate import evaluate_r4_gate  # noqa: E402


STOCK_RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def test_r4_publishable_gate_documents_bridge_only_boundary() -> None:
    gate_doc = ROOT / ".agents/skills/stock-deep-dive/references/publishable_stock_report_gate.md"
    stock_skill = (ROOT / ".agents/skills/stock-deep-dive/SKILL.md").read_text(encoding="utf-8")
    quality_skill = (ROOT / ".agents/skills/quality-review/SKILL.md").read_text(encoding="utf-8")

    assert gate_doc.exists()
    text = gate_doc.read_text(encoding="utf-8")
    assert "bridge_only" in text
    assert "publishable_ready" in text
    assert "No-advice gate" in text
    assert "references/publishable_stock_report_gate.md" in stock_skill
    assert "G7-R4 R4 Publishable Stock Report Check" in quality_skill
    assert "parent_gate_id: G7" in quality_skill


def test_r4_gate_status_is_bridge_only_with_visible_todos() -> None:
    result = evaluate_r4_gate(repo_root=ROOT)
    assert result["status"] == "bridge_only"
    assert result["high_issues"] == 0
    assert result["medium_issues"] >= 1
    assert result["mismatch_count"] >= 1
    assert result["liquid_missing_count"] >= 1


def test_r4_outputs_exist_and_keep_source_gaps_visible() -> None:
    report = (STOCK_RUN / "R4_stock_deep_dive_v0_1.md").read_text(encoding="utf-8")
    gate = (STOCK_RUN / "R4_quality_gate_report.md").read_text(encoding="utf-8")
    gaps = (STOCK_RUN / "R4_source_gap_report.md").read_text(encoding="utf-8")

    assert "## 1. Metadata" in report
    assert "## 3. 公司财务质量" in report
    assert "## 7. 技术/市场状态观察" in report
    assert "r4_publishable_gate_status: bridge_only" in gate
    assert "DLBR-001" in gaps
    assert "DISCLOSURE-SEGMENT-002" in gaps
    assert "MISSING_DISCLOSURE" in report
    assert "MISSING_DISCLOSURE" in gaps


def test_r4_outputs_pass_no_advice_scan() -> None:
    for name in ["R4_stock_deep_dive_v0_1.md", "R4_quality_gate_report.md", "R4_source_gap_report.md"]:
        text = (STOCK_RUN / name).read_text(encoding="utf-8")
        assert find_unsupported_advice(text) == []
