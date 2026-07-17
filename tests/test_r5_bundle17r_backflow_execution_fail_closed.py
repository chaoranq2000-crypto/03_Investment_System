from __future__ import annotations

from pathlib import Path

import pytest

from src.research.r5_bundle17r_backflow_execution import BackflowExecutionError, run_execution
from tests.r5_bundle17r_bf2_test_support import add_passed_result, build_fixture


def test_mismatched_work_order_hash_fails_receipt_and_preserves_blocker(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    add_passed_result(fixture, source_hash_override="0" * 64)

    result = run_execution(tmp_path, fixture["manifest_path"])
    proposal = result["status_proposal"]
    assert proposal["resolved_blocker_occurrence_count"] == 0
    assert proposal["unresolved_blocker_occurrence_count"] == 1
    assert proposal["decision"] == "needs_targeted_backflow"


def test_zip_cannot_be_declared_repo_candidate(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    add_passed_result(
        fixture,
        artifact_name="evidence.zip",
        declared_disposition="repo_candidate",
        promotion_target="reports/evidence.zip",
    )

    result = run_execution(tmp_path, fixture["manifest_path"])
    assert result["status_proposal"]["resolved_blocker_occurrence_count"] == 0
    rejected = tmp_path / "reports/bf2/R5_bundle17r_bf2_rejected_artifacts.csv"
    assert "binary_not_promotable" in rejected.read_text(encoding="utf-8")


def test_fail_on_manual_route_is_nonzero_semantics(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, route="manual")
    with pytest.raises(BackflowExecutionError, match="manual or pending"):
        run_execution(
            tmp_path,
            fixture["manifest_path"],
            fail_on_manual_route=True,
        )


def test_generation_lock_mismatch_stops_before_receipts(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    work_orders = tmp_path / "reports/bf1/work_orders.csv"
    work_orders.write_text(work_orders.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(BackflowExecutionError, match="hash mismatch"):
        run_execution(tmp_path, fixture["manifest_path"])
