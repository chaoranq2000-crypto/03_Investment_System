from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/render_r5_reviewed_input_output.py"


def load_renderer():
    spec = importlib.util.spec_from_file_location("render_r5_reviewed_input_output", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_blocked_gate_renders_source_gapped_draft(tmp_path: Path):
    renderer = load_renderer()
    output = tmp_path / "draft.md"
    result_path = tmp_path / "render_result.yaml"

    result = renderer.render_output(
        repo_root=REPO_ROOT,
        workflow_id="wf_20260703_stock_first_002837_invic",
        result_path=result_path,
        output_path=output,
    )
    text = output.read_text(encoding="utf-8")

    assert result["rendered_output_type"] == "source_gapped_research_draft"
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False
    assert "Source Gap Appendix" in text
    assert "Open Questions" in text
    assert "TODO_MARKET_DATA" in text


def test_render_result_preserves_required_markers(tmp_path: Path):
    renderer = load_renderer()
    output = tmp_path / "draft.md"
    result_path = tmp_path / "render_result.yaml"

    result = renderer.render_output(
        repo_root=REPO_ROOT,
        workflow_id="wf_20260703_stock_first_002837_invic",
        result_path=result_path,
        output_path=output,
    )

    assert result["forbidden_language_check"]["status"] == "pass"
    assert result["required_markers"]["source_gap_appendix"] is True
    assert result["required_markers"]["open_questions"] is True
    assert result["required_markers"]["no_advice_boundary"] is True
    assert result["required_markers"]["remaining_todos"] is True
