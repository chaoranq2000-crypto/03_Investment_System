from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from src.research.r5_bundle17r_backflow_execution import run_execution
from tests.r5_bundle17r_bf2_test_support import add_passed_result, build_fixture, write_yaml


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
