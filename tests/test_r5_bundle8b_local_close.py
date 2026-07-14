from __future__ import annotations

import csv
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_bundle8b_local_close_state_is_synchronized() -> None:
    state = yaml.safe_load((RUN / "workflow_state.yaml").read_text(encoding="utf-8"))
    assert state["status"] in {"accepted_with_todos", "needs_fix"}
    assert "R5_bundle8_research_depth_close" in state["completed_stages"]
    assert state["current_stage"] in {
        "R5_bundle8_closed",
        "R5_bundle9_closed",
        "R5_bundle10_external_human_review_pending",
        "T10_close_readout",
        "R5_bundle9r_closed",
        "T9_quality_review",
    }
    assert state["bundle8_close"]["bundle_closed"] is True
    assert state["bundle8_close"]["reader_regenerated"] is False
    assert state["bundle8_close"]["reader_decision"] == "rejected"
    assert state["bundle8_close"]["reader_score"] == 59
    assert state["bundle9_close"]["sample_quality_allowed"] is False
    assert state["bundle9_close"]["p2_allowed"] is False
    assert state["bundle10_close"]["sample_quality_allowed"] is True
    assert state["bundle10_close"]["p2_allowed"] is False


def test_bundle8b_close_artifacts_and_todos_are_registered() -> None:
    artifacts = read_csv(RUN / "artifact_manifest.csv")
    paths = {row["path"] for row in artifacts}
    assert f"reports/workflow_runs/{RUN.name}/bundle8_close_readout.md" in paths
    assert f"reports/workflow_runs/{RUN.name}/R5_bundle8b_close_input_validation.json" in paths
    assert len({row["artifact_id"] for row in artifacts}) == len(artifacts)
    bundle8b_rows = [
        row
        for row in artifacts
        if 91 <= int(row["artifact_id"].split("_")[-1]) <= 111
    ]
    assert len(bundle8b_rows) == 21
    assert all((ROOT / row["path"]).exists() for row in bundle8b_rows)
    todos = {row["issue_id"]: row for row in read_csv(RUN / "open_todos.csv")}
    assert todos["P2-BLOCK-004"]["status"] == "resolved_live_smoke_completed"
    assert todos["R5Q-B7-E54AC257"]["status"] == "resolved_bundle8_peer_inputs"
    assert todos["R5B8B-G3-001"]["status"] == "accepted_todo"
    assert todos["R5B8B-QR-CI-001"]["status"] == "accepted_todo"
