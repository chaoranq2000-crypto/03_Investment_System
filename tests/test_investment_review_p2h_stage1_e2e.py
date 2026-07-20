from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from src.investment_review.artifact_io import canonical_json_bytes
from src.investment_review.behavior_hypothesis_candidates import (
    build_behavior_hypothesis_candidate,
    replay_validate_behavior_hypothesis_candidate,
)
from src.investment_review.cli import build_parser, main as review_main


FIXTURE_ROOT = Path("tests/fixtures/investment_review_p2h_stage1")


def _json_output(capsys) -> dict[str, object]:
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def _load_real_synthetic_p2g_observation() -> dict[str, object]:
    """Reuse the accepted synthetic P2G-2 fixture without introducing real data."""

    path = Path(__file__).with_name("test_investment_review_behavior_hypotheses.py")
    spec = importlib.util.spec_from_file_location("p2g_fixture_for_p2h", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.observation_artifact.__wrapped__()


def _p2g_candidate_draft(source: dict[str, object]) -> dict[str, object]:
    supporting = next(
        item for item in source["evaluations"] if item["status"] == "observed"
    )
    counterevidence = next(
        item for item in source["evaluations"] if item["status"] == "not_observed"
    )

    def evidence_ref(evaluation: dict[str, object]) -> dict[str, object]:
        return {
            "artifact_type": source["schema_version"],
            "artifact_id": evaluation["evaluation_id"],
            "canonical_hash": source["content_id"],
            "source_locator": "synthetic/generated/p2g_observation.json",
            "effective_at": "2026-07-01T00:00:00Z",
            "knowledge_at": "2026-07-01T08:00:00Z",
        }

    return {
        "created_at": "2026-07-01T09:00:00Z",
        "effective_at": "2026-07-01T08:00:00Z",
        "knowledge_at": "2026-07-01T09:00:00Z",
        "subject_scope": {
            "kind": "cohort",
            "refs": [source["source_cohort"]["cohort_id"]],
        },
        "pattern_family": "sequence",
        "hypothesis_statement": (
            "The observed synthetic sequence may persist in comparable episodes."
        ),
        "supporting_evidence": [evidence_ref(supporting)],
        "counterevidence": [evidence_ref(counterevidence)],
        "source_gaps": [],
        "alternative_explanations": [
            "The synthetic opportunity set may differ between episodes."
        ],
        "applicability_conditions": [
            "Only the frozen synthetic P2G cohort and cutoff are covered."
        ],
        "disconfirming_observations": [
            "Comparable synthetic episodes do not reproduce the sequence."
        ],
        "observation_plan": {
            "question": "Does the sequence persist in comparable synthetic episodes?",
            "required_facts": ["reviewed synthetic decision intent"],
        },
        "provenance": {
            "submitter_kind": "human_reviewed_sidecar",
            "source_locator": "synthetic/generated/p2h_candidate.json",
            "tool_version": "p2h.behavior_hypothesis_candidate.builder.v1",
        },
    }


def _review_event(candidate_id: str, event_type: str, hour: int) -> dict[str, object]:
    timestamp = f"2026-07-01T{hour:02d}:00:00Z"
    rationale = (
        "The candidate is submitted for bounded human review."
        if event_type == "submitted"
        else "Evidence supports continued observation only; causality remains unproven."
    )
    return {
        "candidate_id": candidate_id,
        "event_type": event_type,
        "reviewed_at": timestamp,
        "effective_at": timestamp,
        "knowledge_at": timestamp,
        "reviewer_ref": "synthetic-human-reviewer",
        "rationale": rationale,
        "evidence_cutoff": "2026-07-01T09:00:00Z",
        "supersedes_event_id": None,
        "supersedes_candidate_id": None,
        "provenance": {
            "submitter_kind": "human",
            "source_locator": f"synthetic/generated/{event_type}.json",
            "tool_version": "p2h.behavior_hypothesis_review_event.builder.v1",
        },
    }


def test_checked_in_fixtures_are_synthetic_and_source_replay_valid() -> None:
    source = json.loads(
        (FIXTURE_ROOT / "synthetic_observation_source.json").read_text(
            encoding="utf-8"
        )
    )
    material = dict(source)
    declared = material.pop("content_id")
    actual = "sha256:" + hashlib.sha256(canonical_json_bytes(material)).hexdigest()
    assert declared == actual

    draft = json.loads(
        (FIXTURE_ROOT / "candidate_draft.json").read_text(encoding="utf-8")
    )
    candidate = build_behavior_hypothesis_candidate(draft)
    assert replay_validate_behavior_hypothesis_candidate(
        candidate, source_artifacts=[source]
    )["validation_status"] == "accepted"
    combined = json.dumps({"source": source, "draft": draft}, ensure_ascii=False)
    assert "synthetic" in combined
    assert "600000" not in combined
    assert "000001" not in combined


def test_cli_exposes_the_complete_p2h_stage1_surface() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    for command in (
        "behavior-candidate-build",
        "behavior-candidate-validate",
        "behavior-candidate-ingest",
        "behavior-candidate-list",
        "behavior-candidate-show",
        "behavior-review-event-record",
        "behavior-candidate-status",
        "behavior-candidate-replay",
    ):
        assert command in help_text


def test_synthetic_p2g_to_human_review_projection_and_replay_e2e(
    tmp_path: Path, capsys
) -> None:
    source = _load_real_synthetic_p2g_observation()
    source_path = tmp_path / "synthetic-p2g-observation.json"
    source_path.write_text(
        json.dumps(source, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    source_before = hashlib.sha256(source_path.read_bytes()).hexdigest()
    draft_path = tmp_path / "candidate-draft.json"
    draft_path.write_text(
        json.dumps(
            _p2g_candidate_draft(source),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    candidate_path = tmp_path / "candidate.json"
    database = tmp_path / "review.sqlite3"

    assert review_main(
        [
            "behavior-candidate-build",
            "--input",
            str(draft_path),
            "--output",
            str(candidate_path),
        ]
    ) == 0
    build_result = _json_output(capsys)
    candidate_id = str(build_result["candidate_id"])

    assert review_main(
        [
            "behavior-candidate-validate",
            str(candidate_path),
            "--source-replay",
            "--source-artifact",
            str(source_path),
        ]
    ) == 0
    assert _json_output(capsys)["source_verification"] == {"status": "verified"}

    assert review_main(["--db", str(database), "init"]) == 0
    _json_output(capsys)
    ingest_args = [
        "--db",
        str(database),
        "behavior-candidate-ingest",
        str(candidate_path),
        "--source-artifact",
        str(source_path),
    ]
    assert review_main(ingest_args) == 0
    assert _json_output(capsys)["status"] == "INSERTED"
    assert review_main(ingest_args) == 0
    assert _json_output(capsys)["status"] == "SKIPPED"

    for event_type, hour in (("submitted", 10), ("accepted_for_observation", 11)):
        event_path = tmp_path / f"{event_type}.json"
        event_path.write_text(
            json.dumps(
                _review_event(candidate_id, event_type, hour),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        event_args = [
            "--db",
            str(database),
            "behavior-review-event-record",
            "--input",
            str(event_path),
        ]
        assert review_main(event_args) == 0
        assert _json_output(capsys)["status"] == "INSERTED"
        assert review_main(event_args) == 0
        assert _json_output(capsys)["status"] == "SKIPPED"

    status_args = [
        "--db",
        str(database),
        "behavior-candidate-status",
        candidate_id,
        "--as-of",
        "2026-07-01T11:00:00Z",
        "--knowledge-cutoff",
        "2026-07-01T11:00:00Z",
    ]
    assert review_main(status_args) == 0
    first_projection = _json_output(capsys)
    assert first_projection["status"] == "accepted_for_observation"
    assert "not proven" in first_projection["state_semantics"]
    assert review_main(status_args) == 0
    assert _json_output(capsys) == first_projection

    assert review_main(
        [
            "--db",
            str(database),
            "behavior-candidate-list",
            "--status",
            "accepted_for_observation",
            "--scope-kind",
            "cohort",
        ]
    ) == 0
    listed = _json_output(capsys)
    assert listed["count"] == 1
    assert listed["items"][0]["candidate"]["candidate_id"] == candidate_id

    assert review_main(
        ["--db", str(database), "behavior-candidate-show", candidate_id]
    ) == 0
    assert _json_output(capsys)["candidate_id"] == candidate_id

    assert review_main(
        [
            "--db",
            str(database),
            "behavior-candidate-replay",
            candidate_id,
            "--source-artifact",
            str(source_path),
        ]
    ) == 0
    replay = _json_output(capsys)
    assert replay["validation_status"] == "accepted"
    assert replay["source_verification"] == {"status": "verified"}
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == source_before
