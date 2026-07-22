from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Mapping

import yaml

from src.maintenance.night_shift.night05 import (
    EXPECTED_CANDIDATES,
    DELIVERY_COMMIT,
    EXPECTED_DEPENDENCIES,
    EXPECTED_OCCURRENCES,
    EXPECTED_PARENTS,
    EXPECTED_SOURCE_HASHES,
    EXPECTED_TOTAL_ITEMS,
    HISTORICAL_PATHS,
    MISSION_ID,
    OUTPUT_ROOT,
    SOURCE_COMMIT,
    SOURCE_ROOT,
    WAVE_A_IDS,
    WAVE_B_IDS,
    Night05Outcome,
    authoritative_queue,
    build_review_wave_plan,
    build_change_log,
    build_next_queue,
    build_recompute_summary,
    build_scope_audit,
    build_source_preflight,
    consume_external_decisions,
    evaluate_night05_outcome,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _notes(task: dict[str, object]) -> dict[str, str]:
    result: dict[str, str] = {}
    for note in task.get("notes") or []:
        text = str(note)
        if "=" in text:
            key, value = text.split("=", 1)
            result[key] = value
    return result


def _json_bytes(value: Mapping[str, object]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _yaml_bytes(value: Mapping[str, object]) -> bytes:
    return yaml.safe_dump(
        dict(value), allow_unicode=True, sort_keys=False, width=120
    ).encode("utf-8")


def test_night05_locks_exact_night04_delivery_and_truth() -> None:
    preflight = build_source_preflight(REPO_ROOT)
    assert preflight["passed"] is True
    assert preflight["source_commit"] == SOURCE_COMMIT
    assert preflight["source_delivery_receipt"]["ci_run_id"] == 29764207418
    assert preflight["source_delivery_receipt"]["ci_conclusion"] == "success"
    assert preflight["queue_task_count"] == EXPECTED_TOTAL_ITEMS
    assert preflight["candidate_count"] == EXPECTED_CANDIDATES
    assert preflight["source_hash_representation"] == "git_blob_bytes"
    morning = next(
        item
        for item in preflight["key_files"]
        if item["path"].endswith("/morning_readout.json")
    )
    assert morning["sha256"] == EXPECTED_SOURCE_HASHES["morning_readout.json"]
    assert morning["bytes"] == 2372
    assert preflight["starting_truth"] == {
        "resolved": 0,
        "total": EXPECTED_OCCURRENCES,
        "candidate_ready": EXPECTED_CANDIDATES,
        "dependency_blocked": EXPECTED_DEPENDENCIES,
        "dependency_unlocked": 0,
        "parents_resolved": 0,
        "program_goal": "open_needs_targeted_backflow",
        "sample_quality": False,
        "p2": False,
    }


def test_night05_review_waves_cover_all_43_candidates_without_unlock_claim() -> None:
    plan = build_review_wave_plan(REPO_ROOT)
    waves = plan["waves"]
    assert [item["candidate_count"] for item in waves] == [7, 6, 30]
    assert tuple(waves[0]["candidate_ids"]) == WAVE_A_IDS
    assert tuple(waves[1]["candidate_ids"]) == WAVE_B_IDS
    assert waves[0]["dependency_membership_coverage"] == EXPECTED_DEPENDENCIES
    assert waves[0]["actual_dependency_unlock"] == 0
    assert plan["machine_may_populate_decision_fields"] is False


def test_zero_external_input_closes_only_as_review_intake_ready() -> None:
    outcome = evaluate_night05_outcome(
        valid_external_decisions=0,
        independent_passed_receipts=0,
        resolved_delta=0,
    )
    assert outcome is Night05Outcome.REVIEW_INTAKE_READY
    intake = json.loads(
        (REPO_ROOT / OUTPUT_ROOT / "execution/decision_intake.json").read_text(
            encoding="utf-8"
        )
    )
    assert intake["scanned_manifest_count"] == 0
    assert intake["approved_decision_count"] == 0
    assert intake["machine_generated_decisions"] == 0
    assert intake["external_gate_state"] == "blocked_external"


def test_night05_carries_all_ids_and_source_hashes_verbatim() -> None:
    source = authoritative_queue(REPO_ROOT)
    carried = yaml.safe_load(
        (REPO_ROOT / OUTPUT_ROOT / "next_night_queue.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert carried["mission_id"] == MISSION_ID
    assert carried["source_commit"] == SOURCE_COMMIT
    assert len(carried["tasks"]) == EXPECTED_TOTAL_ITEMS
    assert [item["id"] for item in carried["tasks"]] == [
        item["id"] for item in source["tasks"]
    ]
    for before, after in zip(source["tasks"], carried["tasks"], strict=True):
        before_notes = _notes(before)
        after_notes = _notes(after)
        assert before_notes.get("source_artifact_path") == after_notes.get(
            "source_artifact_path"
        )
        assert before_notes.get("source_artifact_sha256") == after_notes.get(
            "source_artifact_sha256"
        )


def test_night05_readout_preserves_research_boundaries() -> None:
    readout = json.loads(
        (REPO_ROOT / OUTPUT_ROOT / "morning_readout.json").read_text(
            encoding="utf-8"
        )
    )
    truth = readout["research_truth"]
    assert readout["mission_outcome"] == "review_intake_ready"
    assert truth["blocker_occurrences_resolved"] == 0
    assert truth["dependency_unlocked"] == 0
    assert truth["work_orders_resolved"] == 0
    assert truth["program_goal"] == "open_needs_targeted_backflow"
    assert truth["sample_quality_allowed"] is False
    assert truth["p2_allowed"] is False


def test_night05_historical_roots_remain_unchanged() -> None:
    paths = [path.as_posix() for path in HISTORICAL_PATHS]
    committed = subprocess.check_output(
        [
            "git",
            "diff",
            "--name-only",
            f"{SOURCE_COMMIT}..HEAD",
            "--",
            *paths,
        ],
        cwd=REPO_ROOT,
        text=True,
    )
    working = subprocess.check_output(
        ["git", "diff", "--name-only", SOURCE_COMMIT, "--", *paths],
        cwd=REPO_ROOT,
        text=True,
    )
    assert not committed.strip()
    assert not working.strip()


def test_night05_scope_audit_covers_committed_and_working_changes() -> None:
    audit = build_scope_audit(REPO_ROOT)
    observed = set(audit["observed_changed_paths"])
    assert ".gitattributes" in observed
    assert "src/maintenance/night_shift/night05.py" in observed
    assert audit["scope_head"] == DELIVERY_COMMIT
    assert audit["scope_mode"] == "frozen_delivery_snapshot"
    assert not audit["historical_changed_paths"]
    assert not audit["out_of_scope_paths"]
    assert audit["passed"] is True


def test_night05_bootstrap_builders_match_frozen_bytes_without_writes() -> None:
    paths = [
        OUTPUT_ROOT / "preflight/source_preflight.json",
        OUTPUT_ROOT / "review/review_wave_plan.yaml",
        OUTPUT_ROOT / "execution/decision_intake.json",
        OUTPUT_ROOT / "execution/recompute_summary.json",
        OUTPUT_ROOT / "next_night_queue.yaml",
        OUTPUT_ROOT / "progress/change_log.json",
    ]
    before = {
        path.as_posix(): (REPO_ROOT / path).read_bytes() for path in paths
    }
    intake = consume_external_decisions(REPO_ROOT, persist=False)
    generated = {
        (OUTPUT_ROOT / "preflight/source_preflight.json").as_posix(): _json_bytes(
            build_source_preflight(REPO_ROOT)
        ),
        (OUTPUT_ROOT / "review/review_wave_plan.yaml").as_posix(): _yaml_bytes(
            build_review_wave_plan(REPO_ROOT)
        ),
        (OUTPUT_ROOT / "execution/decision_intake.json").as_posix(): _json_bytes(
            intake
        ),
        (OUTPUT_ROOT / "execution/recompute_summary.json").as_posix(): _json_bytes(
            build_recompute_summary(REPO_ROOT)
        ),
        (OUTPUT_ROOT / "next_night_queue.yaml").as_posix(): _yaml_bytes(
            build_next_queue(REPO_ROOT)
        ),
        (OUTPUT_ROOT / "progress/change_log.json").as_posix(): _json_bytes(
            build_change_log()
        ),
    }
    after = {
        path.as_posix(): (REPO_ROOT / path).read_bytes() for path in paths
    }
    assert before == generated
    assert before == after
    historical = REPO_ROOT / SOURCE_ROOT
    assert historical.is_dir()
