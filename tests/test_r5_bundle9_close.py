import importlib.util
import csv
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/validate_r5_bundle9_close.py"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_r5_bundle9_close", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_bundle9_close_inputs_pass_deterministic_validation() -> None:
    result = load_module().validate_bundle9(
        REPO_ROOT,
        "wf_20260703_stock_first_002837_invic",
    )
    assert result["decision"] == "pass", result["errors"]
    assert result["checks"]["forecast_assumptions"]["rows"] == 42
    assert result["checks"]["forecast_model"]["profit_bridge_max_abs_difference"] == 0.0
    assert result["checks"]["valuation_math"]["scenario_checks"] == 6
    assert result["checks"]["valuation_math"]["reverse_checks"] == 5
    assert result["checks"]["valuation_boundary"]["sample_quality_allowed"] is False


def test_bundle9_canonical_state_is_closed_but_reader_remains_fail_closed() -> None:
    run = REPO_ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
    state = yaml.safe_load((run / "workflow_state.yaml").read_text(encoding="utf-8"))
    scorecard = yaml.safe_load(
        (run / "R5_stock_research_report_reader_v2_quality_scorecard.yaml").read_text(encoding="utf-8")
    )
    assert "R5_bundle9_forecast_valuation_close" in state["completed_stages"]
    assert state["current_stage"] in {
        "R5_bundle9_closed",
        "R5_bundle10_external_human_review_pending",
        "T10_close_readout",
        "R5_bundle9r_closed",
    }
    assert state["bundle9_close"]["bundle_closed"] is True
    assert state["bundle9_close"]["sample_quality_allowed"] is False
    assert state["bundle9_close"]["p2_allowed"] is False
    assert scorecard["score"] == 59
    assert scorecard["decision"] == "rejected"


def test_bundle9_close_artifacts_are_registered_once() -> None:
    run = REPO_ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
    with (run / "artifact_manifest.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        paths = [row["path"] for row in csv.DictReader(handle)]
    expected = {
        f"reports/workflow_runs/wf_20260703_stock_first_002837_invic/{name}"
        for name in (
            "R5_bundle9_forecast_assumption_registry.yaml",
            "segment_forecast_model.yaml",
            "R5_bundle9_valuation_pack.yaml",
            "reverse_valuation.yaml",
            "scenario_valuation.yaml",
            "bundle9_quality_report.md",
            "bundle9_close_readout.md",
        )
    }
    assert all(paths.count(path) == 1 for path in expected)
    readout = (run / "bundle9_close_readout.md").read_text(encoding="utf-8")
    assert "617 passed, 2 skipped" in readout
    assert "sample_quality_allowed: `false`" in readout
    assert "PENDING_PRE_CLOSE" not in readout
