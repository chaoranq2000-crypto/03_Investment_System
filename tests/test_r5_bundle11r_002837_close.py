from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "close_r5_bundle11r_002837.py"


def _load_close_module():
    spec = importlib.util.spec_from_file_location("close_r5_bundle11r_002837", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_quality_issue_rows_cover_every_r5_gate_and_keep_boundaries() -> None:
    module = _load_close_module()
    rows = module.quality_issue_rows()
    represented = {row["gate_id"] for row in rows}
    assert {f"R5-G{index}" for index in range(1, 12)}.issubset(represented)
    assert not [row for row in rows if row["severity"] in {"critical", "high"}]
    assert any(row["issue_id"] == "R5B11R-HUMAN-001" and row["status"] == "accepted_todo" for row in rows)


def test_close_inputs_are_hash_bound_and_fail_closed() -> None:
    module = _load_close_module()
    bundle_dir = ROOT / "reports" / "workflow_runs" / "wf_20260703_stock_first_002837_invic" / "bundle11r"
    result = module.validate_close_inputs(bundle_dir)
    assert all(result["checks"].values())
    assert result["handoff"]["status"] == "pending"
    assert result["lock"]["sample_quality_allowed"] is False
    assert result["lock"]["p2_allowed"] is False
