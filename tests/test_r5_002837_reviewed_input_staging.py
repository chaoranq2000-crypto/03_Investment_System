from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/build_r5_reviewed_input_staging.py"
FIXTURE_ROOT = REPO_ROOT / "tests/fixtures/r5_reviewed_inputs"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_r5_reviewed_input_staging", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_empty_dropzone_keeps_002837_source_gapped(tmp_path: Path):
    builder = load_builder()
    dropzone_root = tmp_path / "empty_dropzone"
    dropzone_root.mkdir()

    result = builder.build_staging_result(
        repo_root=REPO_ROOT,
        workflow_id="wf_20260703_stock_first_002837_invic",
        dropzone_root=dropzone_root,
    )

    assert result["allowed_report_level"] == "source_gapped_research_draft"
    assert result["accepted_count"] == 0
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False
    assert "TODO_MARKET_DATA" in result["remaining_todos"]


def test_pending_rows_do_not_create_reviewed_flags():
    builder = load_builder()
    result = builder.build_staging_result(
        repo_root=REPO_ROOT,
        workflow_id="wf_20260703_stock_first_002837_invic",
        dropzone_root=FIXTURE_ROOT / "valid_pending",
    )

    assert result["pending_count"] == 1
    assert result["accepted_count"] == 0
    assert result["reviewed_market_inputs_available"] is False
    assert result["allowed_report_level"] == "source_gapped_research_draft"


def test_accepted_degraded_does_not_allow_sample_quality():
    builder = load_builder()
    result = builder.build_staging_result(
        repo_root=REPO_ROOT,
        workflow_id="wf_20260703_stock_first_002837_invic",
        dropzone_root=FIXTURE_ROOT / "valid_accepted_degraded",
    )

    assert result["accepted_degraded_count"] == 1
    assert result["sample_quality_report_allowed"] is False
    assert result["allowed_report_level"] == "source_gapped_research_draft"
