from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.investment_review.behavior_hypothesis_candidates import (
    build_behavior_hypothesis_review_event,
)
from src.investment_review.cli import build_parser, main as review_main


STAGE1_FIXTURES = Path("tests/fixtures/investment_review_p2h_stage1")
STAGE2_FIXTURES = Path("tests/fixtures/investment_review_p2h_stage2")


def _json_output(capsys) -> dict[str, object]:
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _stage1_event(candidate_id: str, event_type: str, hour: int) -> dict[str, object]:
    timestamp = f"2026-07-20T{hour:02d}:00:00Z"
    return build_behavior_hypothesis_review_event(
        {
            "candidate_id": candidate_id,
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


def _protocol_event_draft(
    protocol_id: str, event_type: str, hour: int
) -> dict[str, object]:
    timestamp = f"2026-07-20T{hour:02d}:00:00Z"
    return {
        "protocol_id": protocol_id,
        "event_type": event_type,
        "reviewed_at": timestamp,
        "effective_at": timestamp,
        "knowledge_at": timestamp,
        "reviewer_ref": "synthetic-human-reviewer",
        "rationale": f"The human reviewer records {event_type}.",
        "evidence_cutoff": "2026-07-20T15:00:00Z",
        "supersedes_event_id": None,
        "superseded_by_protocol_id": None,
        "provenance": {
            "submitter_kind": "human",
            "source_locator": f"synthetic/protocol_{event_type}.json",
            "tool_version": "p2h.observation_protocol_review_event.builder.v1",
        },
    }


def test_cli_exposes_complete_slice_a_surface() -> None:
    help_text = build_parser().format_help()
    for command in (
        "observation-protocol-build",
        "observation-protocol-validate",
        "observation-protocol-ingest",
        "observation-protocol-event-record",
        "observation-protocol-list",
        "observation-protocol-show",
        "observation-protocol-status",
        "observation-protocol-replay",
    ):
        assert command in help_text


def test_checked_in_slice_a_fixture_is_synthetic_and_bounded() -> None:
    draft = json.loads(
        (STAGE2_FIXTURES / "protocol_draft.json").read_text(encoding="utf-8")
    )
    material = json.dumps(draft, ensure_ascii=False).lower()
    assert draft["privacy_scope"]["data_classification"] == "synthetic"
    assert draft["provenance"]["human_confirmed"] is True
    for forbidden in (
        "600000",
        "000001",
        "c:\\users",
        "portfolio.sqlite3",
        "buy now",
        "sell now",
    ):
        assert forbidden not in material


def test_stage1_accepted_candidate_to_protocol_lifecycle_and_replay_e2e(
    tmp_path: Path, capsys
) -> None:
    source_path = STAGE1_FIXTURES / "synthetic_observation_source.json"
    source_before = hashlib.sha256(source_path.read_bytes()).hexdigest()
    candidate_path = tmp_path / "candidate.json"
    database = tmp_path / "review.sqlite3"

    assert review_main(
        [
            "behavior-candidate-build",
            "--input",
            str(STAGE1_FIXTURES / "candidate_draft.json"),
            "--output",
            str(candidate_path),
        ]
    ) == 0
    candidate_result = _json_output(capsys)
    candidate_id = str(candidate_result["candidate_id"])

    assert review_main(["--db", str(database), "init"]) == 0
    _json_output(capsys)
    assert review_main(
        [
            "--db",
            str(database),
            "behavior-candidate-ingest",
            str(candidate_path),
            "--source-artifact",
            str(source_path),
        ]
    ) == 0
    assert _json_output(capsys)["status"] == "INSERTED"

    stage1_event_paths: list[Path] = []
    for event_type, hour in (("submitted", 13), ("accepted_for_observation", 14)):
        event_path = tmp_path / f"candidate-{event_type}.json"
        _write_json(event_path, _stage1_event(candidate_id, event_type, hour))
        stage1_event_paths.append(event_path)
        assert review_main(
            [
                "--db",
                str(database),
                "behavior-review-event-record",
                "--input",
                str(event_path),
            ]
        ) == 0
        assert _json_output(capsys)["status"] == "INSERTED"

    protocol_path = tmp_path / "protocol.json"
    build_args = [
        "observation-protocol-build",
        "--input",
        str(STAGE2_FIXTURES / "protocol_draft.json"),
        "--candidate-artifact",
        str(candidate_path),
    ]
    for event_path in stage1_event_paths:
        build_args.extend(["--review-event", str(event_path)])
    build_args.extend(
        [
            "--candidate-source-artifact",
            str(source_path),
            "--output",
            str(protocol_path),
        ]
    )
    assert review_main(build_args) == 0
    protocol_result = _json_output(capsys)
    protocol_id = str(protocol_result["protocol_id"])

    validate_args = [
        "observation-protocol-validate",
        str(protocol_path),
        "--source-replay",
        "--candidate-artifact",
        str(candidate_path),
    ]
    for event_path in reversed(stage1_event_paths):
        validate_args.extend(["--review-event", str(event_path)])
    validate_args.extend(["--candidate-source-artifact", str(source_path)])
    assert review_main(validate_args) == 0
    assert _json_output(capsys)["source_verification"] == {"status": "verified"}

    ingest_args = [
        "--db",
        str(database),
        "observation-protocol-ingest",
        str(protocol_path),
        "--candidate-source-artifact",
        str(source_path),
    ]
    assert review_main(ingest_args) == 0
    assert _json_output(capsys)["status"] == "INSERTED"
    assert review_main(ingest_args) == 0
    assert _json_output(capsys)["status"] == "SKIPPED"

    for event_type, hour in (
        ("submitted", 16),
        ("approved_for_observation", 17),
        ("activated", 18),
        ("note_added", 19),
        ("completed", 20),
    ):
        event_path = tmp_path / f"protocol-{event_type}.json"
        _write_json(event_path, _protocol_event_draft(protocol_id, event_type, hour))
        args = [
            "--db",
            str(database),
            "observation-protocol-event-record",
            "--input",
            str(event_path),
        ]
        assert review_main(args) == 0
        assert _json_output(capsys)["status"] == "INSERTED"
        assert review_main(args) == 0
        assert _json_output(capsys)["status"] == "SKIPPED"

    assert review_main(
        [
            "--db",
            str(database),
            "observation-protocol-status",
            protocol_id,
            "--as-of",
            "2026-07-20T17:00:00Z",
            "--knowledge-cutoff",
            "2026-07-20T17:00:00Z",
        ]
    ) == 0
    historical = _json_output(capsys)
    assert historical["status"] == "approved_for_observation"

    final_status_args = [
        "--db",
        str(database),
        "observation-protocol-status",
        protocol_id,
        "--as-of",
        "2026-07-20T20:00:00Z",
        "--knowledge-cutoff",
        "2026-07-20T20:00:00Z",
    ]
    assert review_main(final_status_args) == 0
    first_projection = _json_output(capsys)
    assert first_projection["status"] == "completed"
    assert "does not prove or disprove" in first_projection["state_semantics"]
    assert review_main(final_status_args) == 0
    assert _json_output(capsys) == first_projection

    assert review_main(
        [
            "--db",
            str(database),
            "observation-protocol-list",
            "--candidate-id",
            candidate_id,
            "--status",
            "completed",
            "--as-of",
            "2026-07-20T20:00:00Z",
            "--knowledge-cutoff",
            "2026-07-20T20:00:00Z",
        ]
    ) == 0
    listed = _json_output(capsys)
    assert listed["count"] == 1
    assert listed["items"][0]["protocol"]["protocol_id"] == protocol_id

    assert review_main(
        ["--db", str(database), "observation-protocol-show", protocol_id]
    ) == 0
    assert _json_output(capsys)["protocol_id"] == protocol_id

    assert review_main(
        [
            "--db",
            str(database),
            "observation-protocol-replay",
            protocol_id,
            "--candidate-source-artifact",
            str(source_path),
        ]
    ) == 0
    replay = _json_output(capsys)
    assert replay["validation_status"] == "accepted"
    assert replay["source_verification"] == {"status": "verified"}
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == source_before
