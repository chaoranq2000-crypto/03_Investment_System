from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "src/qa/r4_publishable_stock_report_gate.py"
sys.path.insert(0, str(ROOT / "src" / "qa"))

from check_no_unsupported_advice import find_unsupported_advice  # noqa: E402
from r4_publishable_stock_report_gate import evaluate_r4_gate  # noqa: E402


HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
DATA_LAYER_RUN = ROOT / "reports/workflow_runs/wf_20260703_data_layer_002837_invic"


def _historical_file(historical_blob_file, name: str) -> Path:
    return historical_blob_file(f"{HISTORICAL_RUN}/{name}", f"r4_gate_stock_run/{name}")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _minimal_stock_run(historical_blob_file) -> Path:
    files = [
        _historical_file(historical_blob_file, name)
        for name in (
            "business_segment_metric_pack.csv",
            "R4_stock_deep_dive_v0_1.md",
            "R4_quality_gate_report.md",
            "R4_source_gap_report.md",
        )
    ]
    assert len({path.parent for path in files}) == 1
    return files[0].parent


def test_stage_readout_outputs_are_explicit_and_not_repo_level_defaults() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    assert 'parser.add_argument("--gate-readout-output", type=Path, required=True)' in source
    assert 'parser.add_argument("--draft-readout-output", type=Path, required=True)' in source
    assert "reports/p1_6/" not in source


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
    assert "### QR-R4 Publishable Stock Report Subchecks" in quality_skill
    assert "`QR-R4-1`" in quality_skill
    assert "`QR-R4-5`" in quality_skill


def test_r4_gate_status_is_bridge_only_with_visible_todos(historical_blob_file) -> None:
    result = evaluate_r4_gate(
        data_layer_run=DATA_LAYER_RUN,
        stock_run=_minimal_stock_run(historical_blob_file),
    )
    assert result["status"] == "bridge_only"
    assert result["high_issues"] == 0
    assert result["medium_issues"] >= 1
    assert result["mismatch_count"] >= 1
    assert result["liquid_missing_count"] >= 1


def test_r4_outputs_exist_and_keep_source_gaps_visible(historical_blob_file) -> None:
    report = _read_text(
        _historical_file(historical_blob_file, "R4_stock_deep_dive_v0_1.md")
    )
    gate = _read_text(
        _historical_file(historical_blob_file, "R4_quality_gate_report.md")
    )
    gaps = _read_text(
        _historical_file(historical_blob_file, "R4_source_gap_report.md")
    )

    assert "## 1. Metadata" in report
    assert "## 3. 公司财务质量" in report
    assert "## 7. 技术/市场状态观察" in report
    assert "r4_publishable_gate_status: bridge_only" in gate
    assert "DLBR-001" in gaps
    assert "DISCLOSURE-SEGMENT-002" in gaps
    assert "MISSING_DISCLOSURE" in report
    assert "MISSING_DISCLOSURE" in gaps


def test_r4_outputs_pass_no_advice_scan(historical_blob_file) -> None:
    for name in ["R4_stock_deep_dive_v0_1.md", "R4_quality_gate_report.md", "R4_source_gap_report.md"]:
        text = _read_text(_historical_file(historical_blob_file, name))
        assert find_unsupported_advice(text) == []
