import importlib.util
import csv
import io
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/validate_r5_bundle9_close.py"
HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
FIXTURE_WORKFLOW_ID = "wf_fixture_bundle9_close"
BUNDLE9_REQUIRED = (
    "R5_bundle9_forecast_assumption_registry.yaml",
    "segment_forecast_model.yaml",
    "forecast_bridge.yaml",
    "forecast_sensitivity.csv",
    "market_snapshot.csv",
    "peer_market_snapshot.csv",
    "valuation_input_readiness.yaml",
    "valuation_request.yaml",
    "R5_bundle9_valuation_input_registry.yaml",
    "R5_bundle9_peer_reconciliation.yaml",
    "R5_bundle9_valuation_pack.yaml",
    "reverse_valuation.yaml",
    "scenario_valuation.yaml",
    "analyst_forecast_comparison.csv",
    "valuation/valuation_model.yaml",
    "valuation/valuation_snapshot.yaml",
    "valuation/peer_comparison.csv",
    "valuation/sensitivity_table.csv",
    "valuation/valuation_section_draft.md",
    "valuation/valuation_gap_requests.yaml",
    "valuation/valuation_quality_handoff.yaml",
    "valuation/valuation_output.yaml",
    "valuation/R5_valuation_handoff.yaml",
)


def load_module():
    spec = importlib.util.spec_from_file_location("validate_r5_bundle9_close", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def historical_yaml(historical_blob_bytes, name: str):
    return yaml.safe_load(historical_blob_bytes(f"{HISTORICAL_RUN}/{name}").decode("utf-8"))


def historical_csv(historical_blob_bytes, name: str) -> list[dict[str, str]]:
    text = historical_blob_bytes(f"{HISTORICAL_RUN}/{name}").decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def materialize_bundle9(tmp_path: Path, historical_blob_bytes) -> Path:
    repo_root = tmp_path / "bundle9_validation_repo"
    run = repo_root / "reports/workflow_runs" / FIXTURE_WORKFLOW_ID
    for name in BUNDLE9_REQUIRED:
        target = run / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(historical_blob_bytes(f"{HISTORICAL_RUN}/{name}"))
    return repo_root


def test_bundle9_close_inputs_pass_deterministic_validation(
    tmp_path: Path,
    historical_blob_bytes,
) -> None:
    repo_root = materialize_bundle9(tmp_path, historical_blob_bytes)
    result = load_module().validate_bundle9(
        repo_root,
        FIXTURE_WORKFLOW_ID,
    )
    assert result["decision"] == "pass", result["errors"]
    assert result["checks"]["forecast_assumptions"]["rows"] == 42
    assert result["checks"]["forecast_model"]["profit_bridge_max_abs_difference"] == 0.0
    assert result["checks"]["valuation_math"]["scenario_checks"] == 6
    assert result["checks"]["valuation_math"]["reverse_checks"] == 5
    assert result["checks"]["valuation_boundary"]["sample_quality_allowed"] is False


def test_bundle9_canonical_state_is_closed_but_reader_remains_fail_closed(
    historical_blob_bytes,
) -> None:
    state = historical_yaml(historical_blob_bytes, "workflow_state.yaml")
    scorecard = historical_yaml(
        historical_blob_bytes, "R5_stock_research_report_reader_v2_quality_scorecard.yaml"
    )
    assert "R5_bundle9_forecast_valuation_close" in state["completed_stages"]
    assert state["current_stage"] in {
        "R5_bundle9_closed",
        "R5_bundle10_external_human_review_pending",
        "T10_close_readout",
        "R5_bundle9r_closed",
        "T9_quality_review",
        "R5_bundle13r_t1_t2_evidence_backflow",
    }
    if state["current_stage"] == "R5_bundle13r_t1_t2_evidence_backflow":
        assert state["bundle13r_backflow_execution"]["status"] == "backflow_execution_in_progress"
    assert state["bundle9_close"]["bundle_closed"] is True
    assert state["bundle9_close"]["sample_quality_allowed"] is False
    assert state["bundle9_close"]["p2_allowed"] is False
    assert scorecard["score"] == 59
    assert scorecard["decision"] == "rejected"


def test_bundle9_close_artifacts_are_registered_once(historical_blob_bytes) -> None:
    paths = [
        row["path"]
        for row in historical_csv(historical_blob_bytes, "artifact_manifest.csv")
    ]
    expected = {
        f"{HISTORICAL_RUN}/{name}"
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
    readout = historical_blob_bytes(
        f"{HISTORICAL_RUN}/bundle9_close_readout.md"
    ).decode("utf-8")
    assert "617 passed, 2 skipped" in readout
    assert "sample_quality_allowed: `false`" in readout
    assert "PENDING_PRE_CLOSE" not in readout
