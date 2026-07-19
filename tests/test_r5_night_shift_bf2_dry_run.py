from __future__ import annotations

from pathlib import Path

from src.maintenance.night_shift.validation import build_bf2_dry_run_receipt


SOURCE_SHA = "4340945457d661ed62967e949f862ccf2214aff2"


def test_real_bf2_dry_run_preserves_63_plus_6_and_zero_resolved(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    receipt = build_bf2_dry_run_receipt(
        repo_root=repo_root,
        source_commit=SOURCE_SHA,
        output_path=tmp_path / "bf2_dry_run_receipt.json",
    )
    assert receipt["occurrence_count"] == 63
    assert receipt["parent_work_order_count"] == 6
    assert receipt["seeded_task_count"] == 69
    assert receipt["classification_counts"] == {
        "analysis_required": 24,
        "dependency_blocked": 20,
        "engineering_local": 8,
        "evidence_required": 8,
        "human_gate": 3,
    }
    assert receipt["blocker_occurrences_resolved"] == 0
    assert receipt["historical_inputs_unchanged"] is True
    assert receipt["pointer_proposal_count"] == 8
