from __future__ import annotations

import argparse
import json
import socket
import sqlite3
import urllib.request
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import pytest
from jsonschema import Draft202012Validator

from src.investment_review.artifact_io import canonical_json_bytes, pretty_json_bytes
from src.investment_review.behavior_cohort import (
    build_behavior_cohort,
    replay_validate_behavior_cohort,
    validate_behavior_cohort,
)
from src.investment_review.behavior_hypotheses import (
    build_behavior_hypothesis_set,
    replay_validate_behavior_hypothesis_set,
    validate_behavior_hypothesis_set,
)
from src.investment_review.behavior_hypothesis_audit import (
    diff_behavior_hypothesis_revisions,
    list_behavior_hypothesis_revisions,
    render_behavior_hypothesis_revision_markdown,
)
from src.investment_review.behavior_hypothesis_ledger import (
    build_behavior_hypothesis_ledger,
    query_behavior_hypothesis_ledger,
    render_behavior_hypothesis_ledger_markdown,
    replay_validate_behavior_hypothesis_ledger,
    save_behavior_hypothesis_ledger,
    validate_behavior_hypothesis_ledger,
)
from src.investment_review.behavior_hypothesis_review import (
    BehaviorHypothesisReviewError,
    apply_behavior_hypothesis_review,
    behavior_hypothesis_review_request_id,
    replay_validate_behavior_hypothesis_revision,
    save_behavior_hypothesis_revision,
    validate_behavior_hypothesis_review_request,
    validate_behavior_hypothesis_revision,
    validate_behavior_hypothesis_revision_chain,
)
from src.investment_review.behavior_observations import (
    BehaviorObservationError,
    build_behavior_observation_set,
    replay_validate_behavior_observation_set,
    validate_behavior_observation_set,
)
from src.investment_review.cli import build_parser, main as review_main
from tests import test_investment_review_behavior_hypotheses as p2g3_tests
from tests import test_investment_review_behavior_hypothesis_review as review_tests
from tests import test_investment_review_behavior_observations as observation_tests


UTC = timezone.utc
EFFECTIVE_FROM = "2026-07-01T00:00:00Z"
EFFECTIVE_TO = "2026-07-01T09:00:00Z"
KNOWLEDGE_CUTOFF = "2026-07-01T10:00:00Z"


def _p2f_sources(
    root: Path,
    *,
    offset_timezone: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if offset_timezone:
        offset = timezone(timedelta(hours=8))
        specs = [
            {
                "opened_at": datetime(2026, 7, 1, 9, 0, tzinfo=offset),
                "closed_at": datetime(2026, 7, 1, 9, 30, tzinfo=offset),
                "quantity": "100",
            },
            {
                "opened_at": datetime(2026, 7, 1, 10, 0, tzinfo=offset),
                "closed_at": datetime(2026, 7, 1, 10, 30, tzinfo=offset),
                "quantity": "110",
            },
        ]
    else:
        specs = [
            observation_tests._spec(1, quantity="100"),
            observation_tests._spec(2, quantity="110"),
        ]
    reviews: list[dict[str, Any]] = []
    bundles: list[dict[str, Any]] = []
    for index, spec in enumerate(specs):
        review, bundle = observation_tests._episode_artifacts(
            root,
            f"stage3-{index}",
            **spec,
        )
        reviews.append(review)
        bundles.append(bundle)
    return reviews, bundles


def _build_cohort(
    reviews: list[dict[str, Any]], bundles: list[dict[str, Any]]
) -> dict[str, Any]:
    return build_behavior_cohort(
        reviews,
        bundles,
        effective_from=EFFECTIVE_FROM,
        effective_to=EFFECTIVE_TO,
        knowledge_cutoff=KNOWLEDGE_CUTOFF,
        effective_anchor="episode_opened_at",
    )


def _recorded_response(observations: Mapping[str, Any]) -> dict[str, Any]:
    response = p2g3_tests._response(observations)
    first = response["hypotheses"][0]
    first["scope"]["start_at"] = observations["scope"]["effective_from"]
    first["scope"]["end_at"] = observations["scope"]["effective_to"]
    second = deepcopy(first)
    second["statement"] = (
        "The same bounded evidence may support a separate cadence candidate for testing."
    )
    third = deepcopy(first)
    third["statement"] = (
        "A competing bounded explanation may fit the cited episodes and needs testing."
    )
    response["hypotheses"] = [first, second, third]
    return response


def _build_p2g3(observations: Mapping[str, Any]) -> dict[str, Any]:
    result = build_behavior_hypothesis_set(
        observations,
        response_text=json.dumps(
            _recorded_response(observations),
            ensure_ascii=False,
            sort_keys=True,
        ),
        model_id=review_tests.MODEL_ID,
        generated_at=review_tests.GENERATED_AT,
    )
    assert result.used_fallback is False
    return result.artifact


def _review_chain(
    source: Mapping[str, Any], observations: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    first, second, third = source["hypotheses"]
    replacement = review_tests._proposal(third)
    replacement["statement"] = (
        "The corrected bounded candidate narrows the explanation and needs retesting."
    )
    revision_1 = apply_behavior_hypothesis_review(
        source,
        review_tests._request(
            source,
            [
                review_tests._action(first, "accept"),
                review_tests._action(second, "reject"),
                review_tests._action(
                    third, "correct", replacement=replacement
                ),
            ],
        ),
        observation_artifact=observations,
    )
    corrected = next(
        item
        for item in revision_1["hypotheses"]
        if item["supersedes_hypothesis_id"] == third["hypothesis_id"]
    )
    revision_2 = apply_behavior_hypothesis_review(
        revision_1,
        review_tests._request(
            revision_1,
            [review_tests._action(corrected, "accept")],
            reviewed_at="2026-07-19T12:00:01Z",
        ),
        observation_artifact=observations,
    )
    return revision_1, revision_2


def _pipeline(root: Path) -> dict[str, Any]:
    reviews, bundles = _p2f_sources(root)
    cohort = _build_cohort(reviews, bundles)
    observations = build_behavior_observation_set(cohort)
    hypotheses = _build_p2g3(observations)
    revision_1, revision_2 = _review_chain(hypotheses, observations)
    revisions = [revision_1, revision_2]
    ledger = build_behavior_hypothesis_ledger(revisions, [observations])
    return {
        "reviews": reviews,
        "bundles": bundles,
        "cohort": cohort,
        "observations": observations,
        "hypotheses": hypotheses,
        "revision_1": revision_1,
        "revision_2": revision_2,
        "revisions": revisions,
        "ledger": ledger,
    }


@pytest.fixture(scope="module")
def stage3(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    return _pipeline(tmp_path_factory.mktemp("p2g-stage3-e2e"))


def _attempt_codes(result: Any) -> set[str]:
    return set(result.attempt.get("failure_codes", []))


def _validation_codes(result: Mapping[str, Any]) -> set[str]:
    return {str(item["code"]) for item in result["findings"]}


def test_true_p2g1_to_ledger_path_replays_renders_and_is_byte_stable(
    stage3: dict[str, Any],
    tmp_path: Path,
) -> None:
    assert replay_validate_behavior_cohort(
        stage3["cohort"],
        episode_reviews=stage3["reviews"],
        input_bundles=stage3["bundles"],
    )["validation_status"] == "accepted"
    assert replay_validate_behavior_observation_set(
        stage3["observations"], cohort=stage3["cohort"]
    )["validation_status"] == "accepted"
    assert replay_validate_behavior_hypothesis_set(
        stage3["hypotheses"],
        observation_artifact=stage3["observations"],
    )["validation_status"] == "accepted"
    for revision in stage3["revisions"]:
        assert validate_behavior_hypothesis_revision(revision)[
            "validation_status"
        ] == "accepted"
        assert replay_validate_behavior_hypothesis_revision(
            revision,
            observation_artifact=stage3["observations"],
        )["validation_status"] == "accepted"
    assert validate_behavior_hypothesis_revision_chain(
        list(reversed(stage3["revisions"]))
    )["validation_status"] == "accepted"

    rendered = render_behavior_hypothesis_revision_markdown(stage3["revision_2"])
    assert "accepted 仅表示人工确认保留为工作假设" in rendered
    diff = diff_behavior_hypothesis_revisions(
        stage3["revision_1"], stage3["revision_2"]
    )
    assert len(diff["changed_hypotheses"]) == 1
    assert set(diff["changed_hypotheses"][0]["fields"]) == {"status"}
    assert [
        item["revision_no"]
        for item in list_behavior_hypothesis_revisions(stage3["revisions"])
    ] == [1, 2]

    ledger = stage3["ledger"]
    assert validate_behavior_hypothesis_ledger(ledger)[
        "validation_status"
    ] == "accepted"
    assert replay_validate_behavior_hypothesis_ledger(
        ledger,
        revisions=list(reversed(stage3["revisions"])),
        observation_artifacts=[stage3["observations"]],
    )["validation_status"] == "accepted"
    assert ledger["counts"]["active_fingerprint_count"] == 2
    accepted = query_behavior_hypothesis_ledger(
        ledger, view="active", status="accepted", actor="reviewer:test"
    )
    assert accepted["match_count"] == 2
    assert "不是心理画像、评分器或交易建议" in (
        render_behavior_hypothesis_ledger_markdown(ledger)
    )

    repeated = _pipeline(tmp_path / "repeat")
    for name in (
        "cohort",
        "observations",
        "hypotheses",
        "revision_1",
        "revision_2",
        "ledger",
    ):
        assert canonical_json_bytes(repeated[name]) == canonical_json_bytes(
            stage3[name]
        )


def test_upstream_and_evaluation_tamper_are_blocked(
    stage3: dict[str, Any],
) -> None:
    cohort = deepcopy(stage3["cohort"])
    cohort["content_id"] = "sha256:" + "f" * 64
    assert validate_behavior_cohort(cohort)["validation_status"] == "blocked"
    with pytest.raises(BehaviorObservationError):
        build_behavior_observation_set(cohort)

    observations = deepcopy(stage3["observations"])
    observations["evaluations"][0]["facts"]["observed_relation"] = "tampered"
    assert validate_behavior_observation_set(observations)[
        "validation_status"
    ] == "blocked"
    result = build_behavior_hypothesis_set(
        observations,
        response_text=json.dumps(_recorded_response(stage3["observations"])),
        model_id=review_tests.MODEL_ID,
        generated_at=review_tests.GENERATED_AT,
    )
    assert result.used_fallback is True
    assert "SOURCE_OBSERVATION_SET_INVALID" in _attempt_codes(result)


@pytest.mark.parametrize(
    "mutation,expected_code",
    [
        ("support_not_observed", "SUPPORT_EVALUATION_NOT_OBSERVED"),
        ("counter_unresolved", "COUNTEREVIDENCE_REF_UNKNOWN"),
        ("counter_missing", "COUNTEREVIDENCE_REQUIRED"),
        ("scope_mismatch", "SCOPE_EPISODE_MISMATCH"),
    ],
)
def test_p2g3_semantic_failure_matrix_is_all_or_nothing(
    stage3: dict[str, Any], mutation: str, expected_code: str
) -> None:
    response = _recorded_response(stage3["observations"])
    candidate = response["hypotheses"][0]
    if mutation == "support_not_observed":
        evaluation = next(
            item
            for item in stage3["observations"]["evaluations"]
            if item["status"] == "not_observed"
        )
        candidate["evaluation_refs"] = [evaluation["evaluation_id"]]
        candidate["scope"]["episode_ids"] = list(
            evaluation["subject"]["episode_ids"]
        )
    elif mutation == "counter_unresolved":
        candidate["counterevidence_evaluation_refs"] = [
            "evaluation:" + "f" * 32
        ]
        candidate["counterevidence_search"] = None
    elif mutation == "counter_missing":
        candidate["counterevidence_evaluation_refs"] = []
        candidate["counterevidence_search"] = None
    else:
        candidate["scope"]["episode_ids"] = ["episode:outside-source"]
    result = build_behavior_hypothesis_set(
        stage3["observations"],
        response_text=json.dumps(response, ensure_ascii=False, sort_keys=True),
        model_id=review_tests.MODEL_ID,
        generated_at=review_tests.GENERATED_AT,
    )
    assert result.used_fallback is True
    assert expected_code in _attempt_codes(result)
    assert canonical_json_bytes(result.artifact) == canonical_json_bytes(
        stage3["observations"]
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("statement", "你是冲动型和报复型交易人格。"),
        ("uncertainty_notes", ["纪律得分 80/100。"]),
        ("next_observations_needed", ["下次应减仓 50%。"]),
        ("next_observations_needed", ["应当卖在最高点。"]),
    ],
)
def test_stale_parent_and_unsafe_corrections_never_create_a_revision(
    stage3: dict[str, Any], field: str, value: Any
) -> None:
    source = stage3["hypotheses"]
    target = source["hypotheses"][0]
    stale = review_tests._request(
        source, [review_tests._action(target, "accept")]
    )
    stale["expected_parent_content_id"] = "sha256:" + "f" * 64
    stale["request_id"] = behavior_hypothesis_review_request_id(stale)
    with pytest.raises(BehaviorHypothesisReviewError, match="stale"):
        apply_behavior_hypothesis_review(
            source,
            stale,
            observation_artifact=stage3["observations"],
        )

    replacement = review_tests._proposal(target)
    replacement[field] = value
    with pytest.raises(BehaviorHypothesisReviewError):
        apply_behavior_hypothesis_review(
            source,
            review_tests._request(
                source,
                [
                    review_tests._action(
                        target, "correct", replacement=replacement
                    )
                ],
            ),
            observation_artifact=stage3["observations"],
        )


def test_revision_break_fork_cycle_and_duplicate_are_blocked(
    stage3: dict[str, Any],
) -> None:
    revision_1 = stage3["revision_1"]
    revision_2 = stage3["revision_2"]
    broken = deepcopy(revision_2)
    broken["revision"]["parent_content_id"] = "sha256:" + "f" * 64
    assert "REVISION_PARENT_MISMATCH" in _validation_codes(
        validate_behavior_hypothesis_revision_chain([revision_1, broken])
    )
    fork = deepcopy(revision_2)
    fork["content_id"] = "sha256:" + "e" * 64
    assert "REVISION_CHAIN_FORK" in _validation_codes(
        validate_behavior_hypothesis_revision_chain(
            [revision_1, revision_2, fork]
        )
    )
    cycle_1 = deepcopy(revision_1)
    cycle_2 = deepcopy(revision_2)
    cycle_1["revision"]["parent_content_id"] = cycle_2["content_id"]
    cycle_2["revision"]["parent_content_id"] = cycle_1["content_id"]
    assert "REVISION_CHAIN_CYCLE" in _validation_codes(
        validate_behavior_hypothesis_revision_chain([cycle_1, cycle_2])
    )
    assert "REVISION_CONTENT_ID_DUPLICATE" in _validation_codes(
        validate_behavior_hypothesis_revision_chain([revision_1, revision_1])
    )


def test_in_memory_stage3_runtime_does_not_access_source_files_db_or_network(
    stage3: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("external source access is forbidden")

    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    observations = build_behavior_observation_set(stage3["cohort"])
    hypotheses = _build_p2g3(observations)
    revision_1, revision_2 = _review_chain(hypotheses, observations)
    ledger = build_behavior_hypothesis_ledger(
        [revision_2, revision_1], [observations]
    )
    assert query_behavior_hypothesis_ledger(ledger, view="active")[
        "match_count"
    ] == 2


def test_requests_are_strict_atomic_and_action_order_is_deterministic(
    stage3: dict[str, Any],
) -> None:
    source = stage3["hypotheses"]
    first, second, _third = source["hypotheses"]
    actions = [
        review_tests._action(first, "accept"),
        review_tests._action(second, "reject"),
    ]
    request_a = review_tests._request(source, deepcopy(actions))
    request_b = review_tests._request(source, list(reversed(deepcopy(actions))))
    assert request_a["request_id"] == request_b["request_id"]
    revision_a = apply_behavior_hypothesis_review(
        source, request_a, observation_artifact=stage3["observations"]
    )
    revision_b = apply_behavior_hypothesis_review(
        source, request_b, observation_artifact=stage3["observations"]
    )
    assert canonical_json_bytes(revision_a) == canonical_json_bytes(revision_b)

    extra = deepcopy(request_a)
    extra["unexpected"] = True
    assert validate_behavior_hypothesis_review_request(extra)[
        "validation_status"
    ] == "blocked"
    wrong_time = deepcopy(request_a)
    wrong_time["reviewed_at"] = "2026-07-19T20:00:00+08:00"
    wrong_time["request_id"] = behavior_hypothesis_review_request_id(wrong_time)
    assert validate_behavior_hypothesis_review_request(wrong_time)[
        "validation_status"
    ] == "blocked"
    duplicate = deepcopy(request_a)
    duplicate["actions"] = [deepcopy(actions[0]), deepcopy(actions[0])]
    duplicate["request_id"] = behavior_hypothesis_review_request_id(duplicate)
    assert validate_behavior_hypothesis_review_request(duplicate)[
        "validation_status"
    ] == "blocked"


def test_create_only_and_cli_error_leave_no_partial_artifact(
    stage3: dict[str, Any],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    revision_path = tmp_path / "revision.json"
    ledger_path = tmp_path / "ledger.json"
    save_behavior_hypothesis_revision(revision_path, stage3["revision_2"])
    save_behavior_hypothesis_ledger(ledger_path, stage3["ledger"])
    with pytest.raises(BehaviorHypothesisReviewError, match="exists"):
        save_behavior_hypothesis_revision(revision_path, stage3["revision_2"])
    with pytest.raises(Exception, match="exists"):
        save_behavior_hypothesis_ledger(ledger_path, stage3["ledger"])

    source_path = tmp_path / "source.json"
    observations_path = tmp_path / "observations.json"
    request_path = tmp_path / "invalid-request.json"
    output_path = tmp_path / "must-not-exist.json"
    source_path.write_bytes(pretty_json_bytes(stage3["hypotheses"]))
    observations_path.write_bytes(pretty_json_bytes(stage3["observations"]))
    invalid = review_tests._request(
        stage3["hypotheses"],
        [
            review_tests._action(
                stage3["hypotheses"]["hypotheses"][0], "accept"
            )
        ],
    )
    invalid["unexpected"] = True
    request_path.write_bytes(pretty_json_bytes(invalid))
    assert review_main(
        [
            "behavior-hypothesis-review",
            "--artifact",
            str(source_path),
            "--request",
            str(request_path),
            "--observation-artifact",
            str(observations_path),
            "--output",
            str(output_path),
        ]
    ) == 2
    capsys.readouterr()
    assert not output_path.exists()


def test_path_style_and_equivalent_timezones_do_not_change_p2g1_identity(
    tmp_path: Path,
) -> None:
    utc_reviews, utc_bundles = _p2f_sources(tmp_path / "windows" / "style")
    same_reviews, same_bundles = _p2f_sources(tmp_path / "posix" / "style")
    offset_reviews, offset_bundles = _p2f_sources(
        tmp_path / "offset" / "style", offset_timezone=True
    )
    utc_cohort = _build_cohort(utc_reviews, utc_bundles)
    same_cohort = _build_cohort(same_reviews, same_bundles)
    offset_cohort = _build_cohort(offset_reviews, offset_bundles)
    assert canonical_json_bytes(utc_cohort) == canonical_json_bytes(same_cohort)
    assert utc_cohort["content_id"] == same_cohort["content_id"]
    utc_opened = [
        item["effective_at"] for item in utc_cohort["included_reviews"]
    ]
    offset_opened = [
        item["effective_at"]
        for item in offset_cohort["included_reviews"]
    ]
    assert utc_opened == offset_opened == sorted(offset_opened)


def test_stage3_close_readout_contract_matches_schemas_docs_and_cli(
    stage3: dict[str, Any],
) -> None:
    for schema_path in sorted(Path("docs/contracts").glob("*.schema.json")):
        Draft202012Validator.check_schema(
            json.loads(schema_path.read_text(encoding="utf-8"))
        )
    assert validate_behavior_cohort(stage3["cohort"])[
        "validation_status"
    ] == "accepted"
    assert validate_behavior_observation_set(stage3["observations"])[
        "validation_status"
    ] == "accepted"
    assert validate_behavior_hypothesis_set(stage3["hypotheses"])[
        "validation_status"
    ] == "accepted"

    parser = build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    expected_commands = {
        "behavior-hypothesis-interpret",
        "behavior-hypothesis-review",
        "behavior-hypothesis-validate",
        "behavior-hypothesis-render",
        "behavior-hypothesis-diff",
        "behavior-hypothesis-revision-list",
        "behavior-hypothesis-ledger-build",
        "behavior-hypothesis-ledger-validate",
        "behavior-hypothesis-ledger-query",
        "behavior-hypothesis-ledger-render",
    }
    assert expected_commands <= set(subparsers.choices)

    p2g3_playbook = Path(
        "docs/playbooks/INVESTMENT_REVIEW_P2G_3.md"
    ).read_text(encoding="utf-8")
    p2g4_playbook = Path(
        "docs/playbooks/INVESTMENT_REVIEW_P2G_4.md"
    ).read_text(encoding="utf-8")
    ledger_playbook = Path(
        "docs/playbooks/INVESTMENT_REVIEW_BEHAVIOR_HYPOTHESIS_LEDGER.md"
    ).read_text(encoding="utf-8")
    close_readout = Path(
        "reports/investment_review/p2g_stage3/P2G_STAGE3_CLOSE_READOUT.md"
    ).read_text(encoding="utf-8")
    assert "proposed" in p2g3_playbook and "交易建议" in p2g3_playbook
    for status in ("accepted", "rejected", "superseded"):
        assert status in p2g4_playbook and status in ledger_playbook
    assert "心理画像" in ledger_playbook and "P2G-5" in ledger_playbook
    for command in expected_commands - {"behavior-hypothesis-interpret"}:
        assert command in close_readout
    for marker in (
        "functional_close_status: `accepted`",
        "accepted 只是人工确认的工作假设",
        "active 只含 accepted occurrence",
        "不把 Behavior Hypothesis Ledger 命名为 `P2G-5`",
        "当前功能关闭无 blocker",
    ):
        assert marker in close_readout
