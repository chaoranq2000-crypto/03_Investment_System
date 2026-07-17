from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from src.research.r5_bundle17r_backflow_execution import (
    GLOBAL_CASE_ID,
    row_sha256,
    run_execution,
)
from tests.r5_bundle17r_bf2_test_support import (
    add_passed_result,
    build_fixture,
    sha256_file,
    write_csv,
    write_yaml,
)


def test_passed_result_preserves_occurrence_and_emits_review_handoff(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    add_passed_result(fixture)

    result = run_execution(tmp_path, fixture["manifest_path"])
    proposal = result["status_proposal"]
    assert proposal["source_blocker_occurrence_count"] == 1
    assert proposal["resolved_blocker_occurrence_count"] == 1
    assert proposal["unresolved_blocker_occurrence_count"] == 0
    assert proposal["engineering_pass_count"] == 1
    assert proposal["decision"] == "ready_for_exact_hash_human_review"
    assert proposal["sample_quality_allowed"] is False
    assert proposal["p2_allowed"] is False

    issue_path = tmp_path / "reports/bf2/R5_bundle17r_bf2_issue_ledger.csv"
    with issue_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["bf2_source_occurrence_preserved"] == "true"
    assert rows[0]["bf2_resolution_status"] == "resolved"

    handoff_path = tmp_path / "reports/bf2/review_handoffs/CASE-A.yaml"
    handoff = yaml.safe_load(handoff_path.read_text(encoding="utf-8"))
    assert handoff["engineering_pass"] is True
    assert handoff["review_status"] == "pending"
    assert len(handoff["case_generation_sha256"]) == 64

    promotion = yaml.safe_load(
        (tmp_path / "reports/bf2/R5_bundle17r_bf2_promotion_manifest.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert promotion["mutation_authorized"] is False
    assert promotion["entries"][0]["promotion_target"] == "src/research/fix.py"


def test_exact_hash_review_can_promote_only_to_reviewed_candidate(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    add_passed_result(fixture)
    run_execution(tmp_path, fixture["manifest_path"])
    handoff = yaml.safe_load(
        (tmp_path / "reports/bf2/review_handoffs/CASE-A.yaml").read_text(encoding="utf-8")
    )
    review = {
        "schema_version": "r5_bundle17r_bf2_case_review_decision_v1",
        "case_id": "CASE-A",
        "decision": "accepted",
        "reviewer": "reviewer@example",
        "reviewed_at": "2026-07-17T12:00:00+01:00",
        "reviewed_case_generation_sha256": handoff["case_generation_sha256"],
        "notes": "accepted for research usefulness",
    }
    write_yaml(tmp_path / ".local/results/reviews/CASE-A.yaml", review)

    rerun = run_execution(tmp_path, fixture["manifest_path"])
    proposal = rerun["status_proposal"]
    assert proposal["decision"] == "reviewed_candidate_requires_separate_activation"
    assert proposal["next_stage"] == "R5_bundle17r_reviewed_candidate"
    assert proposal["sample_quality_allowed"] is False
    assert proposal["p2_allowed"] is False

    lock = json.loads(
        (tmp_path / "reports/bf2/R5_bundle17r_bf2_generation_lock.json").read_text(
            encoding="utf-8"
        )
    )
    assert lock["sample_quality_allowed"] is False
    assert lock["p2_allowed"] is False


def test_real_bf1_lock_shape_and_suite_work_orders_are_supported(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    work_orders = [
        {
            "work_order_id": "WO-SUITE",
            "case_id": "",
            "execution_route": "auto",
            "blocker_ids": "BLK-GLOBAL",
            "owner": "quality-review",
        },
        {
            "work_order_id": "WO-CASE",
            "case_id": "CASE-A",
            "execution_route": "auto",
            "blocker_ids": "BLK-CASE",
            "owner": "quality-review",
        },
        {
            "work_order_id": "WO-RERUN",
            "case_id": "",
            "execution_route": "auto",
            "blocker_ids": "",
            "owner": "research-orchestrator",
        },
    ]
    work_orders_path = tmp_path / "reports/bf1/work_orders.csv"
    write_csv(work_orders_path, list(work_orders[0]), work_orders)
    issues_path = tmp_path / "reports/bf1/issues.csv"
    write_csv(
        issues_path,
        ["blocker_id", "case_id", "work_order_id", "description"],
        [
            {
                "blocker_id": "BLK-GLOBAL",
                "case_id": "",
                "work_order_id": "WO-SUITE",
                "description": "suite gate failed",
            },
            {
                "blocker_id": "BLK-CASE",
                "case_id": "",
                "work_order_id": "WO-CASE",
                "description": "case gate failed",
            },
        ],
    )
    cases_path = tmp_path / "reports/bf1/cases.csv"
    write_csv(
        cases_path,
        ["case_id", "company_name", "engineering_pass"],
        [
            {"case_id": "CASE-A", "company_name": "Example", "engineering_pass": "false"},
            {"case_id": "suite", "company_name": "", "engineering_pass": "false"},
        ],
    )
    lock = {
        "schema_version": "r5_bundle17r_backflow_generation_lock_v1",
        "output_artifacts": {
            path.name: {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
            for path in (work_orders_path, issues_path, cases_path)
        },
    }
    (tmp_path / "reports/bf1/generation_lock.json").write_text(
        json.dumps(lock, sort_keys=True), encoding="utf-8"
    )

    def add_result(order: dict[str, str], blocker_ids: list[str]) -> None:
        result_dir = tmp_path / ".local/results" / order["work_order_id"]
        result_dir.mkdir(parents=True, exist_ok=True)
        write_yaml(
            result_dir / "result.yaml",
            {
                "schema_version": "r5_bundle17r_work_order_result_v1",
                "work_order_id": order["work_order_id"],
                "case_id": order["case_id"] or GLOBAL_CASE_ID,
                "source_work_order_sha256": row_sha256(order),
                "execution_status": "engineering_pass",
                "resolved_blocker_ids": blocker_ids,
                "checks": [{"id": "acceptance", "status": "passed"}],
                "produced_artifacts": [],
            },
        )

    add_result(work_orders[0], ["BLK-GLOBAL"])
    add_result(work_orders[1], ["BLK-CASE"])
    pending_terminal = run_execution(tmp_path, fixture["manifest_path"])
    assert pending_terminal["status_proposal"]["resolved_blocker_occurrence_count"] == 2
    assert pending_terminal["status_proposal"]["engineering_pass_count"] == 0
    assert pending_terminal["status_proposal"]["decision"] == "needs_targeted_backflow"
    assert pending_terminal["status_proposal"]["all_work_orders_engineering_pass"] is False
    with (pending_terminal["output_dir"] / "R5_bundle17r_bf2_case_matrix.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        case_row = next(csv.DictReader(handle))
    assert case_row["bf2_source_blocker_count"] == "1"
    assert case_row["bf2_global_source_blocker_count"] == "1"

    add_result(work_orders[2], [])
    complete = run_execution(tmp_path, fixture["manifest_path"])
    assert complete["status_proposal"]["engineering_pass_count"] == 1
    assert complete["status_proposal"]["decision"] == "ready_for_exact_hash_human_review"
    assert complete["status_proposal"]["all_work_orders_engineering_pass"] is True
