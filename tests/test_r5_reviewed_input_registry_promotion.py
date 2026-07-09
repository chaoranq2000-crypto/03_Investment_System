from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/promote_r5_reviewed_inputs_to_registries.py"
FIXTURE_ROOT = REPO_ROOT / "tests/fixtures/r5_reviewed_inputs"


def load_promoter():
    spec = importlib.util.spec_from_file_location("promote_r5_reviewed_inputs_to_registries", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_no_accepted_inputs_do_not_change_registries(tmp_path: Path):
    promoter = load_promoter()
    dropzone_root = tmp_path / "empty_dropzone"
    dropzone_root.mkdir()

    result = promoter.build_promotion_result(
        repo_root=REPO_ROOT,
        workflow_id="wf_20260703_stock_first_002837_invic",
        dropzone_root=dropzone_root,
    )

    assert result["promotion_status"] == "no_accepted_inputs"
    assert result["registries_changed"] is False
    assert result["allowed_report_level"] == "source_gapped_research_draft"


def test_pending_rows_do_not_unblock_registry_promotion():
    promoter = load_promoter()
    result = promoter.build_promotion_result(
        repo_root=REPO_ROOT,
        workflow_id="wf_20260703_stock_first_002837_invic",
        dropzone_root=FIXTURE_ROOT / "valid_pending",
    )

    assert result["promotion_status"] == "no_accepted_inputs"
    assert result["accepted_count"] == 0
    assert result["registries_changed"] is False


def test_invalid_accepted_rows_block_promotion():
    promoter = load_promoter()
    result = promoter.build_promotion_result(
        repo_root=REPO_ROOT,
        workflow_id="wf_20260703_stock_first_002837_invic",
        dropzone_root=FIXTURE_ROOT / "invalid_missing_evidence",
    )

    assert result["promotion_status"] == "blocked_invalid_dropzone"
    assert result["registries_changed"] is False
    assert any(issue["issue_id"] == "R5DROP-EVIDENCE-001" for issue in result["validation_issues"])
