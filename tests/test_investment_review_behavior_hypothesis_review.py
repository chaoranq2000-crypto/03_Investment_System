from __future__ import annotations

import json
import socket
import sqlite3
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import pytest

from src.investment_review.artifact_io import canonical_json_bytes, pretty_json_bytes
from src.investment_review.behavior_hypotheses import build_behavior_hypothesis_set
from src.investment_review.behavior_hypothesis_review import (
    REVISION_SCHEMA_VERSION,
    BehaviorHypothesisReviewError,
    apply_behavior_hypothesis_review,
    behavior_hypothesis_review_request_id,
    load_behavior_hypothesis_artifact,
    replay_validate_behavior_hypothesis_revision,
    save_behavior_hypothesis_revision,
    validate_behavior_hypothesis_review_request,
    validate_behavior_hypothesis_revision,
    validate_behavior_hypothesis_revision_chain,
)
from src.investment_review.cli import main as review_main
from tests import test_investment_review_behavior_hypotheses as p2g3_tests


GENERATED_AT = "2026-07-18T12:00:00Z"
MODEL_ID = "recorded-model-v1"
PROPOSAL_FIELDS = (
    "statement",
    "scope",
    "evaluation_refs",
    "supporting_reasons",
    "counterevidence_evaluation_refs",
    "counterevidence_search",
    "alternative_explanations",
    "assumptions",
    "uncertainty_notes",
    "falsification_conditions",
    "next_observations_needed",
    "temporal_perspective",
)


@pytest.fixture()
def observation_artifact() -> dict[str, Any]:
    return p2g3_tests.observation_artifact.__wrapped__()


def _recorded_response(observation_artifact: Mapping[str, Any]) -> dict[str, Any]:
    response = p2g3_tests._response(observation_artifact)
    base = response["hypotheses"][0]
    observed = [
        item
        for item in observation_artifact["evaluations"]
        if item["status"] == "observed"
    ]
    used = set(base["evaluation_refs"])
    pair = next(
        item
        for item in observed
        if len(item["subject"]["episode_ids"]) == 2
        and item["evaluation_id"] not in used
    )
    single = next(
        item for item in observed if len(item["subject"]["episode_ids"]) == 1
    )
    second = deepcopy(base)
    second["statement"] = (
        "A separate referenced cadence may be a bounded candidate that needs testing."
    )
    second["scope"]["episode_ids"] = list(pair["subject"]["episode_ids"])
    second["evaluation_refs"] = [pair["evaluation_id"]]
    third = deepcopy(base)
    third["statement"] = (
        "One episode is insufficient to establish a repeated behavior pattern."
    )
    third["scope"]["episode_ids"] = list(single["subject"]["episode_ids"])
    third["evaluation_refs"] = [single["evaluation_id"]]
    response["hypotheses"] = [base, second, third]
    return response


@pytest.fixture()
def p2g3_source(observation_artifact: dict[str, Any]) -> dict[str, Any]:
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=json.dumps(
            _recorded_response(observation_artifact),
            ensure_ascii=False,
            sort_keys=True,
        ),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert result.used_fallback is False
    return result.artifact


def _proposal(item: Mapping[str, Any]) -> dict[str, Any]:
    return {field: deepcopy(item[field]) for field in PROPOSAL_FIELDS}


def _request(
    parent: Mapping[str, Any],
    actions: list[dict[str, Any]],
    *,
    reviewed_at: str = "2026-07-19T12:00:00Z",
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "schema_version": "p2g.behavior_hypothesis_review_request.v1",
        "request_id": "review-request:" + "0" * 32,
        "expected_parent_content_id": parent["content_id"],
        "actor": "reviewer:test",
        "reviewed_at": reviewed_at,
        "actions": actions,
    }
    request["request_id"] = behavior_hypothesis_review_request_id(request)
    assert validate_behavior_hypothesis_review_request(request)["validation_status"] == "accepted"
    return request


def _action(
    hypothesis: Mapping[str, Any],
    action: str,
    *,
    replacement: Mapping[str, Any] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "target_hypothesis_id": hypothesis["hypothesis_id"],
        "action": action,
        "reason": reason or f"Human review recorded the explicit {action} rationale.",
        "replacement": deepcopy(replacement),
    }


def _by_id(artifact: Mapping[str, Any], hypothesis_id: str) -> dict[str, Any]:
    return next(
        item
        for item in artifact["hypotheses"]
        if item["hypothesis_id"] == hypothesis_id
    )


@pytest.mark.parametrize("action,expected", [("accept", "accepted"), ("reject", "rejected")])
def test_single_accept_or_reject_is_immutable_and_source_replayed(
    observation_artifact: dict[str, Any],
    p2g3_source: dict[str, Any],
    action: str,
    expected: str,
) -> None:
    source_before = canonical_json_bytes(p2g3_source)
    observation_before = canonical_json_bytes(observation_artifact)
    target = p2g3_source["hypotheses"][0]
    revision = apply_behavior_hypothesis_review(
        p2g3_source,
        _request(p2g3_source, [_action(target, action)]),
        observation_artifact=observation_artifact,
    )
    assert revision["schema_version"] == REVISION_SCHEMA_VERSION
    assert revision["revision"]["revision_no"] == 1
    assert revision["revision"]["parent_content_id"] == p2g3_source["content_id"]
    assert _by_id(revision, target["hypothesis_id"])["status"] == expected
    assert validate_behavior_hypothesis_revision(revision)["validation_status"] == "accepted"
    assert (
        replay_validate_behavior_hypothesis_revision(
            revision, observation_artifact=observation_artifact
        )["validation_status"]
        == "accepted"
    )
    assert canonical_json_bytes(p2g3_source) == source_before
    assert canonical_json_bytes(observation_artifact) == observation_before


def test_correct_supersedes_old_id_and_new_proposal_requires_second_review(
    observation_artifact: dict[str, Any],
    p2g3_source: dict[str, Any],
) -> None:
    target = p2g3_source["hypotheses"][0]
    replacement = _proposal(target)
    replacement["statement"] = (
        "Within the same frozen scope, the candidate remains narrower and testable."
    )
    revision_1 = apply_behavior_hypothesis_review(
        p2g3_source,
        _request(p2g3_source, [_action(target, "correct", replacement=replacement)]),
        observation_artifact=observation_artifact,
    )
    old = _by_id(revision_1, target["hypothesis_id"])
    new = next(
        item for item in revision_1["hypotheses"] if item["supersedes_hypothesis_id"]
    )
    assert old["status"] == "superseded"
    assert new["status"] == "proposed"
    assert new["hypothesis_id"] != target["hypothesis_id"]
    assert new["lineage_root_hypothesis_id"] == target["hypothesis_id"]

    revision_2 = apply_behavior_hypothesis_review(
        revision_1,
        _request(
            revision_1,
            [_action(new, "accept")],
            reviewed_at="2026-07-19T12:00:01Z",
        ),
        observation_artifact=observation_artifact,
    )
    assert _by_id(revision_2, new["hypothesis_id"])["status"] == "accepted"
    assert revision_2["revision"]["parent_content_id"] == revision_1["content_id"]
    assert (
        validate_behavior_hypothesis_revision_chain([revision_2, revision_1])[
            "validation_status"
        ]
        == "accepted"
    )


@pytest.mark.parametrize("first_action", ["accept", "reject"])
def test_reviewed_hypothesis_can_only_be_reopened_by_explicit_correction(
    observation_artifact: dict[str, Any],
    p2g3_source: dict[str, Any],
    first_action: str,
) -> None:
    target = p2g3_source["hypotheses"][0]
    revision_1 = apply_behavior_hypothesis_review(
        p2g3_source,
        _request(p2g3_source, [_action(target, first_action)]),
        observation_artifact=observation_artifact,
    )
    reviewed_target = _by_id(revision_1, target["hypothesis_id"])
    replacement = _proposal(reviewed_target)
    replacement["statement"] = (
        "An explicit later correction creates a new bounded candidate for review."
    )
    revision_2 = apply_behavior_hypothesis_review(
        revision_1,
        _request(
            revision_1,
            [_action(reviewed_target, "correct", replacement=replacement)],
            reviewed_at="2026-07-19T12:00:01Z",
        ),
        observation_artifact=observation_artifact,
    )
    new = next(
        item for item in revision_2["hypotheses"] if item["supersedes_hypothesis_id"]
    )
    assert _by_id(revision_2, target["hypothesis_id"])["status"] == "superseded"
    assert new["status"] == "proposed"
    assert (
        validate_behavior_hypothesis_revision_chain([revision_1, revision_2])[
            "validation_status"
        ]
        == "accepted"
    )


def test_mixed_request_is_atomic_and_deterministic_under_action_permutation(
    observation_artifact: dict[str, Any],
    p2g3_source: dict[str, Any],
) -> None:
    first, second, third = p2g3_source["hypotheses"]
    replacement = _proposal(third)
    replacement["statement"] = (
        "The single referenced episode remains insufficient for a repeated-pattern claim."
    )
    actions = [
        _action(first, "accept"),
        _action(second, "reject"),
        _action(third, "correct", replacement=replacement),
    ]
    request_a = _request(p2g3_source, deepcopy(actions))
    request_b = _request(p2g3_source, list(reversed(deepcopy(actions))))
    assert request_a["request_id"] == request_b["request_id"]
    revision_a = apply_behavior_hypothesis_review(
        p2g3_source, request_a, observation_artifact=observation_artifact
    )
    revision_b = apply_behavior_hypothesis_review(
        p2g3_source, request_b, observation_artifact=observation_artifact
    )
    assert canonical_json_bytes(revision_a) == canonical_json_bytes(revision_b)
    assert len(
        [event for event in revision_a["review_events"] if event["action"] == "correct"]
    ) == 1


def test_stale_unknown_duplicate_and_invalid_transition_fail_before_output(
    observation_artifact: dict[str, Any],
    p2g3_source: dict[str, Any],
) -> None:
    target = p2g3_source["hypotheses"][0]
    stale = _request(p2g3_source, [_action(target, "accept")])
    stale["expected_parent_content_id"] = "sha256:" + "f" * 64
    stale["request_id"] = behavior_hypothesis_review_request_id(stale)
    with pytest.raises(BehaviorHypothesisReviewError, match="stale"):
        apply_behavior_hypothesis_review(
            p2g3_source, stale, observation_artifact=observation_artifact
        )

    unknown_item = deepcopy(target)
    unknown_item["hypothesis_id"] = "hypothesis:" + "f" * 32
    unknown = _request(p2g3_source, [_action(unknown_item, "accept")])
    with pytest.raises(BehaviorHypothesisReviewError, match="unknown"):
        apply_behavior_hypothesis_review(
            p2g3_source, unknown, observation_artifact=observation_artifact
        )

    duplicate_actions = [
        _action(target, "accept", reason="first explicit reason"),
        _action(target, "accept", reason="second explicit reason"),
    ]
    duplicate: dict[str, Any] = {
        "schema_version": "p2g.behavior_hypothesis_review_request.v1",
        "request_id": "review-request:" + "0" * 32,
        "expected_parent_content_id": p2g3_source["content_id"],
        "actor": "reviewer:test",
        "reviewed_at": "2026-07-19T12:00:00Z",
        "actions": duplicate_actions,
    }
    duplicate["request_id"] = behavior_hypothesis_review_request_id(duplicate)
    assert (
        validate_behavior_hypothesis_review_request(duplicate)["validation_status"]
        == "blocked"
    )

    accepted = apply_behavior_hypothesis_review(
        p2g3_source,
        _request(p2g3_source, [_action(target, "accept")]),
        observation_artifact=observation_artifact,
    )
    accepted_target = _by_id(accepted, target["hypothesis_id"])
    with pytest.raises(BehaviorHypothesisReviewError, match="proposed"):
        apply_behavior_hypothesis_review(
            accepted,
            _request(
                accepted,
                [_action(accepted_target, "reject")],
                reviewed_at="2026-07-19T12:00:01Z",
            ),
            observation_artifact=observation_artifact,
        )


def test_correction_reuses_p2g3_guardrails_and_source_replay_detects_tamper(
    observation_artifact: dict[str, Any],
    p2g3_source: dict[str, Any],
) -> None:
    target = p2g3_source["hypotheses"][0]
    unsafe = _proposal(target)
    unsafe["statement"] = "Buy more now and set a guaranteed stop-loss at the best price."
    with pytest.raises(Exception):
        apply_behavior_hypothesis_review(
            p2g3_source,
            _request(p2g3_source, [_action(target, "correct", replacement=unsafe)]),
            observation_artifact=observation_artifact,
        )

    revision = apply_behavior_hypothesis_review(
        p2g3_source,
        _request(p2g3_source, [_action(target, "accept")]),
        observation_artifact=observation_artifact,
    )
    tampered = deepcopy(observation_artifact)
    tampered["evaluations"][0]["facts"]["anchor_gap_seconds"] = "999999"
    assert (
        replay_validate_behavior_hypothesis_revision(
            revision, observation_artifact=tampered
        )["validation_status"]
        == "blocked"
    )


def test_review_does_not_access_database_or_network(
    monkeypatch: pytest.MonkeyPatch,
    observation_artifact: dict[str, Any],
    p2g3_source: dict[str, Any],
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("database/network access is forbidden")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    target = p2g3_source["hypotheses"][0]
    revision = apply_behavior_hypothesis_review(
        p2g3_source,
        _request(p2g3_source, [_action(target, "accept")]),
        observation_artifact=observation_artifact,
    )
    assert revision["revision"]["revision_no"] == 1


def test_create_only_roundtrip_and_cli_review_validate(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    observation_artifact: dict[str, Any],
    p2g3_source: dict[str, Any],
) -> None:
    target = p2g3_source["hypotheses"][0]
    request = _request(p2g3_source, [_action(target, "accept")])
    revision = apply_behavior_hypothesis_review(
        p2g3_source, request, observation_artifact=observation_artifact
    )
    output = tmp_path / "direct-revision.json"
    save_behavior_hypothesis_revision(output, revision)
    assert load_behavior_hypothesis_artifact(output) == revision
    with pytest.raises(BehaviorHypothesisReviewError, match="exists"):
        save_behavior_hypothesis_revision(output, revision)

    source_path = tmp_path / "source.json"
    observation_path = tmp_path / "observations.json"
    request_path = tmp_path / "request.json"
    cli_output = tmp_path / "cli-revision.json"
    source_path.write_bytes(pretty_json_bytes(p2g3_source))
    observation_path.write_bytes(pretty_json_bytes(observation_artifact))
    request_path.write_bytes(pretty_json_bytes(request))
    assert review_main(
        [
            "behavior-hypothesis-review",
            "--artifact",
            str(source_path),
            "--request",
            str(request_path),
            "--observation-artifact",
            str(observation_path),
            "--output",
            str(cli_output),
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["revision_no"] == 1
    assert review_main(
        [
            "behavior-hypothesis-validate",
            str(cli_output),
            "--source-replay",
            "--observation-artifact",
            str(observation_path),
        ]
    ) == 0
    validation = json.loads(capsys.readouterr().out)
    assert validation["validation_status"] == "accepted"
    assert review_main(
        [
            "behavior-hypothesis-review",
            "--artifact",
            str(source_path),
            "--request",
            str(request_path),
            "--observation-artifact",
            str(observation_path),
            "--output",
            str(cli_output),
        ]
    ) == 2
    assert "exists" in capsys.readouterr().err
