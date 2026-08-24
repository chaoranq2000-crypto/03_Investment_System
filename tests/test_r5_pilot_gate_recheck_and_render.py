from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/render_r5_reviewed_input_output.py"
HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def load_renderer():
    spec = importlib.util.spec_from_file_location("render_r5_reviewed_input_output", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _render_inputs(historical_blob_file) -> dict[str, Path]:
    return {
        "gate_path": historical_blob_file(
            "reports/p1_6/r5_reviewed_input_pilot_gate_result.json",
            "render/gate.json",
        ),
        "pack_path": historical_blob_file(
            f"{HISTORICAL_RUN}/R5_stock_research_pack_source_gapped.yaml",
            "render/pack.yaml",
        ),
        "staging_path": historical_blob_file(
            f"{HISTORICAL_RUN}/R5_reviewed_input_staging_result.yaml",
            "render/staging.yaml",
        ),
        "promotion_path": historical_blob_file(
            f"{HISTORICAL_RUN}/R5_reviewed_input_registry_promotion_result.yaml",
            "render/promotion.yaml",
        ),
    }


def test_gate_input_is_explicit_and_has_no_legacy_default() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'parser.add_argument("--gate", type=Path, required=True' in source
    assert "reports/p1_6/" not in source


def test_blocked_gate_renders_source_gapped_draft(tmp_path: Path, historical_blob_file):
    renderer = load_renderer()
    output = tmp_path / "draft.md"
    result_path = tmp_path / "render_result.yaml"

    result = renderer.render_output(
        repo_root=REPO_ROOT,
        workflow_id="fixture_stock_first_002837",
        result_path=result_path,
        output_path=output,
        **_render_inputs(historical_blob_file),
    )
    text = output.read_text(encoding="utf-8")

    assert result["rendered_output_type"] == "source_gapped_research_draft"
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False
    assert "Source Gap Appendix" in text
    assert "Open Questions" in text
    assert "TODO_MARKET_DATA" in text


def test_render_result_preserves_required_markers(tmp_path: Path, historical_blob_file):
    renderer = load_renderer()
    output = tmp_path / "draft.md"
    result_path = tmp_path / "render_result.yaml"

    result = renderer.render_output(
        repo_root=REPO_ROOT,
        workflow_id="fixture_stock_first_002837",
        result_path=result_path,
        output_path=output,
        **_render_inputs(historical_blob_file),
    )

    assert result["forbidden_language_check"]["status"] == "pass"
    assert result["required_markers"]["source_gap_appendix"] is True
    assert result["required_markers"]["open_questions"] is True
    assert result["required_markers"]["no_advice_boundary"] is True
    assert result["required_markers"]["remaining_todos"] is True
