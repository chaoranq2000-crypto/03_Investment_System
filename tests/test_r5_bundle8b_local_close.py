from __future__ import annotations

import csv
import io
from pathlib import Path

import yaml
import pytest

# Published historical results; current algorithms are covered in the default suite.
pytestmark = pytest.mark.legacy_compatibility


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def historical_yaml(historical_blob_bytes, name: str):
    return yaml.safe_load(historical_blob_bytes(f"{HISTORICAL_RUN}/{name}").decode("utf-8"))


def historical_csv(historical_blob_bytes, name: str) -> list[dict[str, str]]:
    text = historical_blob_bytes(f"{HISTORICAL_RUN}/{name}").decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def test_bundle8b_local_close_state_is_synchronized(historical_blob_bytes) -> None:
    state = historical_yaml(historical_blob_bytes, "workflow_state.yaml")
    assert state["status"] in {"accepted_with_todos", "needs_fix", "in_progress"}
    assert "R5_bundle8_research_depth_close" in state["completed_stages"]
    assert state["current_stage"] in {
        "R5_bundle8_closed",
        "R5_bundle9_closed",
        "R5_bundle10_external_human_review_pending",
        "T10_close_readout",
        "R5_bundle9r_closed",
        "T9_quality_review",
        "R5_bundle13r_t1_t2_evidence_backflow",
    }
    if state["current_stage"] == "R5_bundle13r_t1_t2_evidence_backflow":
        assert state["bundle13r_backflow_execution"]["status"] == "backflow_execution_in_progress"
    assert state["bundle8_close"]["bundle_closed"] is True
    assert state["bundle8_close"]["reader_regenerated"] is False
    assert state["bundle8_close"]["reader_decision"] == "rejected"
    assert state["bundle8_close"]["reader_score"] == 59
    assert state["bundle9_close"]["sample_quality_allowed"] is False
    assert state["bundle9_close"]["p2_allowed"] is False
    assert state["bundle10_close"]["sample_quality_allowed"] is True
    assert state["bundle10_close"]["p2_allowed"] is False


def test_bundle8b_close_artifacts_and_todos_are_registered(historical_blob_bytes) -> None:
    artifacts = historical_csv(historical_blob_bytes, "artifact_manifest.csv")
    paths = {row["path"] for row in artifacts}
    assert f"{HISTORICAL_RUN}/bundle8_close_readout.md" in paths
    assert f"{HISTORICAL_RUN}/R5_bundle8b_close_input_validation.json" in paths
    assert len({row["artifact_id"] for row in artifacts}) == len(artifacts)
    bundle8b_rows = [
        row
        for row in artifacts
        if 91 <= int(row["artifact_id"].split("_")[-1]) <= 111
    ]
    assert len(bundle8b_rows) == 21
    assert all(historical_blob_bytes(row["path"]) for row in bundle8b_rows)
    todos = {
        row["issue_id"]: row
        for row in historical_csv(historical_blob_bytes, "open_todos.csv")
    }
    assert todos["P2-BLOCK-004"]["status"] == "resolved_live_smoke_completed"
    assert todos["R5Q-B7-E54AC257"]["status"] == "resolved_bundle8_peer_inputs"
    assert todos["R5B8B-G3-001"]["status"] == "accepted_todo"
    assert todos["R5B8B-QR-CI-001"]["status"] == "accepted_todo"
