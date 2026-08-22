from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from src.investment_review.behavior_hypothesis_candidates import (
    BehaviorHypothesisCandidateError,
    BehaviorHypothesisProjectionError,
    build_behavior_hypothesis_candidate,
    build_behavior_hypothesis_review_event,
    project_behavior_hypothesis_state,
    replay_validate_behavior_hypothesis_candidate,
    validate_behavior_hypothesis_candidate,
)
from src.investment_review.cli import main as review_main
from src.investment_review.store import ReviewStore


FIXTURE_ROOT = Path("tests/fixtures/investment_review_p2h_stage1")


def _source() -> dict[str, object]:
    return json.loads(
        (FIXTURE_ROOT / "synthetic_observation_source.json").read_text(
            encoding="utf-8"
        )
    )


def _draft() -> dict[str, object]:
    return json.loads(
        (FIXTURE_ROOT / "candidate_draft.json").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize(
    "field",
    [
        "trade_action",
        "position_size",
        "expected_return",
        "execution_instruction",
        "score",
        "confidence_percentage",
        "personal_profile",
        "personal_playbook",
        "intervention",
    ],
)
def test_prohibited_advice_score_profile_and_execution_fields_are_rejected(
    field: str,
) -> None:
    draft = _draft()
    draft[field] = "prohibited"

    with pytest.raises(BehaviorHypothesisCandidateError, match="unsupported fields"):
        build_behavior_hypothesis_candidate(draft)


@pytest.mark.parametrize(
    ("statement", "expected_code"),
    [
        (
            "You should buy immediately because greed caused the loss.",
            "POLICY_DIRECT_ADVICE",
        ),
        (
            "The synthetic pattern may continue with 95% confidence.",
            "POLICY_NUMERIC_CONFIDENCE",
        ),
        (
            "The loss may prove that greed caused the decision.",
            "POLICY_PSYCHOLOGY_DIAGNOSIS",
        ),
    ],
)
def test_authored_diagnosis_advice_and_numeric_confidence_are_blocked(
    statement: str, expected_code: str
) -> None:
    draft = _draft()
    draft["hypothesis_statement"] = statement
    candidate = build_behavior_hypothesis_candidate(draft)

    validation = validate_behavior_hypothesis_candidate(candidate)

    assert validation["validation_status"] == "blocked"
    assert expected_code in validation["finding_codes"]


def test_alternatives_and_counterevidence_or_gap_are_mandatory() -> None:
    no_alternative = _draft()
    no_alternative["alternative_explanations"] = []
    with pytest.raises(BehaviorHypothesisCandidateError, match="must not be empty"):
        build_behavior_hypothesis_candidate(no_alternative)

    no_challenge = _draft()
    no_challenge["counterevidence"] = []
    no_challenge["source_gaps"] = []
    with pytest.raises(BehaviorHypothesisCandidateError, match="must be non-empty"):
        build_behavior_hypothesis_candidate(no_challenge)


def test_future_knowledge_and_hash_mismatch_are_not_downgraded_to_warnings() -> None:
    future = _draft()
    future["supporting_evidence"][0]["knowledge_at"] = "2026-07-20T12:00:01Z"
    with pytest.raises(BehaviorHypothesisCandidateError, match="after knowledge_at"):
        build_behavior_hypothesis_candidate(future)

    candidate = build_behavior_hypothesis_candidate(_draft())
    tampered = deepcopy(candidate)
    tampered["supporting_evidence"][0]["canonical_hash"] = "sha256:" + "f" * 64
    validation = replay_validate_behavior_hypothesis_candidate(
        tampered, source_artifacts=[_source()]
    )
    assert validation["validation_status"] == "blocked"
    assert "SOURCE_HASH_MISMATCH" in validation["finding_codes"]


def test_candidate_cannot_auto_enter_observing_or_proven_state() -> None:
    candidate = build_behavior_hypothesis_candidate(_draft())
    projection = project_behavior_hypothesis_state(
        candidate,
        [],
        as_of="2026-07-20T12:00:00Z",
        knowledge_cutoff="2026-07-20T12:00:00Z",
    )
    assert projection["status"] == "candidate"
    assert "proven" not in projection["status"]

    accepted = build_behavior_hypothesis_review_event(
        {
            "candidate_id": candidate["candidate_id"],
            "event_type": "accepted_for_observation",
            "reviewed_at": "2026-07-20T13:00:00Z",
            "effective_at": "2026-07-20T13:00:00Z",
            "knowledge_at": "2026-07-20T13:00:00Z",
            "reviewer_ref": "synthetic-human-reviewer",
            "rationale": "Evidence supports observation only; causality remains unproven.",
            "evidence_cutoff": "2026-07-20T12:00:00Z",
            "supersedes_event_id": None,
            "supersedes_candidate_id": None,
            "provenance": {
                "submitter_kind": "human",
                "source_locator": "synthetic/accepted.json",
                "tool_version": "p2h.behavior_hypothesis_review_event.builder.v1",
            },
        }
    )
    with pytest.raises(
        BehaviorHypothesisProjectionError, match="INVALID_REVIEW_TRANSITION"
    ):
        project_behavior_hypothesis_state(
            candidate,
            [accepted],
            as_of="2026-07-20T13:00:00Z",
            knowledge_cutoff="2026-07-20T13:00:00Z",
        )


def test_store_and_cli_expose_no_mutation_or_automatic_profile_path(
    tmp_path: Path, capsys
) -> None:
    store = ReviewStore(tmp_path / "review.sqlite3")
    store.initialize()
    for method in (
        "update_behavior_hypothesis_candidate",
        "delete_behavior_hypothesis_candidate",
        "update_behavior_hypothesis_review_event",
        "delete_behavior_hypothesis_review_event",
        "update_personal_profile",
        "update_personal_playbook",
        "create_intervention",
    ):
        assert not hasattr(store, method)

    output = tmp_path / "existing-candidate.json"
    output.write_text("sentinel", encoding="utf-8")
    exit_code = review_main(
        [
            "behavior-candidate-build",
            "--input",
            str(FIXTURE_ROOT / "candidate_draft.json"),
            "--output",
            str(output),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert output.read_text(encoding="utf-8") == "sentinel"
    assert "The observed association may persist" not in captured.err
    assert "FileExistsError" in captured.err
