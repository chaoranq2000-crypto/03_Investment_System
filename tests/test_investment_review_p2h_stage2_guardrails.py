from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from src.investment_review.behavior_hypothesis_candidates import (
    build_behavior_hypothesis_candidate,
    build_behavior_hypothesis_review_event,
)
from src.investment_review.behavior_observation_protocols import (
    ObservationProtocolError,
    build_observation_protocol,
    build_observation_protocol_review_event,
    validate_observation_protocol,
)
from src.investment_review.cli import build_parser, main as review_main
from src.investment_review.store import ReviewStore


STAGE1_FIXTURES = Path("tests/fixtures/investment_review_p2h_stage1")
STAGE2_FIXTURES = Path("tests/fixtures/investment_review_p2h_stage2")


def _inputs() -> tuple[dict[str, object], dict[str, object], list[dict[str, object]], dict[str, object]]:
    source = json.loads(
        (STAGE1_FIXTURES / "synthetic_observation_source.json").read_text(
            encoding="utf-8"
        )
    )
    candidate = build_behavior_hypothesis_candidate(
        json.loads(
            (STAGE1_FIXTURES / "candidate_draft.json").read_text(encoding="utf-8")
        )
    )

    def event(event_type: str, hour: int) -> dict[str, object]:
        timestamp = f"2026-07-20T{hour:02d}:00:00Z"
        return build_behavior_hypothesis_review_event(
            {
                "candidate_id": candidate["candidate_id"],
                "event_type": event_type,
                "reviewed_at": timestamp,
                "effective_at": timestamp,
                "knowledge_at": timestamp,
                "reviewer_ref": "synthetic-human-reviewer",
                "rationale": f"The human reviewer records {event_type}.",
                "evidence_cutoff": "2026-07-20T12:00:00Z",
                "supersedes_event_id": None,
                "supersedes_candidate_id": None,
                "provenance": {
                    "submitter_kind": "human",
                    "source_locator": f"synthetic/{event_type}.json",
                    "tool_version": "p2h.behavior_hypothesis_review_event.builder.v1",
                },
            }
        )

    events = [event("submitted", 13), event("accepted_for_observation", 14)]
    draft = json.loads(
        (STAGE2_FIXTURES / "protocol_draft.json").read_text(encoding="utf-8")
    )
    return source, candidate, events, draft


def _protocol() -> dict[str, object]:
    source, candidate, events, draft = _inputs()
    return build_observation_protocol(
        draft,
        candidate=candidate,
        review_events=events,
        candidate_source_artifacts=[source],
    )


@pytest.mark.parametrize(
    "field",
    [
        "trade_action",
        "position_size",
        "expected_return",
        "order_execution",
        "score",
        "numeric_confidence",
        "personal_profile",
        "personal_playbook",
        "intervention_action",
        "experiment_action",
        "attempt_outcome",
        "ui_config",
        "web_api",
    ],
)
def test_prohibited_advice_score_profile_intervention_and_ui_fields_are_rejected(
    field: str,
) -> None:
    source, candidate, events, draft = _inputs()
    draft[field] = "prohibited"
    with pytest.raises(ObservationProtocolError, match="unsupported fields"):
        build_observation_protocol(
            draft,
            candidate=candidate,
            review_events=events,
            candidate_source_artifacts=[source],
        )


@pytest.mark.parametrize(
    ("question", "expected_code"),
    [
        ("You should buy immediately.", "POLICY_DIRECT_ADVICE"),
        ("Give this behavior a score of 9.", "POLICY_MECHANICAL_SCORE"),
        ("This pattern persists with 95% confidence.", "POLICY_NUMERIC_CONFIDENCE"),
        ("Greed caused this behavior.", "POLICY_PSYCHOLOGY_DIAGNOSIS"),
        ("Update the personal profile.", "POLICY_PROFILE_WRITE"),
        ("Create an intervention for the next episode.", "POLICY_INTERVENTION_ACTION"),
    ],
)
def test_authored_policy_violations_are_blockers(
    question: str, expected_code: str
) -> None:
    protocol = _protocol()
    protocol["question"] = question
    result = validate_observation_protocol(protocol)
    assert result["validation_status"] == "blocked"
    assert expected_code in result["finding_codes"]


def test_accepted_stage1_candidate_does_not_auto_create_or_activate_protocol(
    tmp_path: Path,
) -> None:
    source, candidate, events, _ = _inputs()
    store = ReviewStore(tmp_path / "review.sqlite3")
    store.initialize()
    store.save_behavior_hypothesis_candidate(candidate, source_artifacts=[source])
    for event in events:
        store.save_behavior_hypothesis_review_event(event)

    status = store.status()
    assert status["counts"]["behavior_observation_protocols"] == 0
    assert status["counts"]["behavior_observation_protocol_review_events"] == 0


def test_store_and_cli_expose_no_mutation_profile_intervention_or_execution_path(
    tmp_path: Path,
) -> None:
    store = ReviewStore(tmp_path / "review.sqlite3")
    store.initialize()
    for method in (
        "update_observation_protocol",
        "delete_observation_protocol",
        "update_observation_protocol_review_event",
        "delete_observation_protocol_review_event",
        "create_intervention",
        "record_experiment_attempt",
        "update_personal_profile",
        "update_personal_playbook",
        "execute_order",
    ):
        assert not hasattr(store, method)

    help_text = build_parser().format_help().lower()
    for forbidden_command in (
        "observation-protocol-update",
        "observation-protocol-delete",
        "intervention-create",
        "profile-update",
        "order-execute",
    ):
        assert forbidden_command not in help_text


def test_event_extra_action_field_and_nonhuman_event_are_rejected() -> None:
    protocol = _protocol()
    draft: dict[str, object] = {
        "protocol_id": protocol["protocol_id"],
        "event_type": "submitted",
        "reviewed_at": "2026-07-20T16:00:00Z",
        "effective_at": "2026-07-20T16:00:00Z",
        "knowledge_at": "2026-07-20T16:00:00Z",
        "reviewer_ref": "synthetic-human-reviewer",
        "rationale": "The protocol is submitted for human review.",
        "evidence_cutoff": "2026-07-20T15:00:00Z",
        "supersedes_event_id": None,
        "superseded_by_protocol_id": None,
        "provenance": {
            "submitter_kind": "human",
            "source_locator": "synthetic/submitted.json",
            "tool_version": "p2h.observation_protocol_review_event.builder.v1",
        },
    }
    with_action = deepcopy(draft)
    with_action["intervention_action"] = "prohibited"
    with pytest.raises(ObservationProtocolError, match="unsupported fields"):
        build_observation_protocol_review_event(with_action)

    nonhuman = deepcopy(draft)
    nonhuman["provenance"]["submitter_kind"] = "agent_assisted"
    with pytest.raises(ObservationProtocolError, match="human-authored"):
        build_observation_protocol_review_event(nonhuman)


def test_protocol_build_is_create_only_and_error_does_not_echo_private_payload(
    tmp_path: Path, capsys
) -> None:
    source, candidate, events, _ = _inputs()
    source_path = tmp_path / "source.json"
    candidate_path = tmp_path / "candidate.json"
    event_paths: list[Path] = []
    source_path.write_text(json.dumps(source), encoding="utf-8")
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
    for index, event in enumerate(events):
        path = tmp_path / f"event-{index}.json"
        path.write_text(json.dumps(event), encoding="utf-8")
        event_paths.append(path)
    output = tmp_path / "existing-protocol.json"
    output.write_text("sentinel", encoding="utf-8")

    args = [
        "observation-protocol-build",
        "--input",
        str(STAGE2_FIXTURES / "protocol_draft.json"),
        "--candidate-artifact",
        str(candidate_path),
    ]
    for path in event_paths:
        args.extend(["--review-event", str(path)])
    args.extend(
        [
            "--candidate-source-artifact",
            str(source_path),
            "--output",
            str(output),
        ]
    )
    assert review_main(args) == 2
    captured = capsys.readouterr()
    assert output.read_text(encoding="utf-8") == "sentinel"
    assert "Does the association persist" not in captured.err
    assert "FileExistsError" in captured.err


def test_canonical_protocol_contains_no_absolute_machine_or_direct_identifier_data() -> None:
    rendered = json.dumps(_protocol(), ensure_ascii=False).lower()
    for forbidden in (
        "c:\\users\\",
        "c:\\projects\\",
        "file://",
        "computername",
        "username",
        "broker_export.json",
        "portfolio.sqlite3",
    ):
        assert forbidden not in rendered
