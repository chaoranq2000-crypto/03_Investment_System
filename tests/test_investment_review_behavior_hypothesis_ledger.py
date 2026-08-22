from __future__ import annotations

import json
import socket
import sqlite3
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import pytest
from jsonschema import Draft202012Validator

from src.investment_review.artifact_io import canonical_json_bytes, pretty_json_bytes
from src.investment_review.behavior_hypotheses import build_behavior_hypothesis_set
from src.investment_review.behavior_hypothesis_ledger import (
    BehaviorHypothesisLedgerError,
    build_behavior_hypothesis_ledger,
    query_behavior_hypothesis_ledger,
    render_behavior_hypothesis_ledger_markdown,
    replay_validate_behavior_hypothesis_ledger,
    save_behavior_hypothesis_ledger,
    save_behavior_hypothesis_ledger_markdown,
    validate_behavior_hypothesis_ledger,
)
from src.investment_review.behavior_hypothesis_review import (
    apply_behavior_hypothesis_review,
    behavior_hypothesis_review_request_id,
)
from src.investment_review.cli import main as review_main
from tests import test_investment_review_behavior_hypothesis_audit as audit_tests
from tests import test_investment_review_behavior_hypothesis_review as review_tests


def _accepted_duplicate_chain(
    observations: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    result = build_behavior_hypothesis_set(
        observations,
        response_text=json.dumps(
            review_tests._recorded_response(observations),
            ensure_ascii=False,
            sort_keys=True,
        ),
        model_id=review_tests.MODEL_ID,
        generated_at="2026-07-18T12:00:01Z",
    )
    source = result.artifact
    target = source["hypotheses"][0]
    revision = apply_behavior_hypothesis_review(
        source,
        review_tests._request(
            source,
            [review_tests._action(target, "accept")],
            reviewed_at="2026-07-19T13:00:00Z",
        ),
        observation_artifact=observations,
    )
    return source, revision


def _ledger_context() -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, Any],
]:
    observations, _source, revision_1, revision_2, revision_3 = audit_tests._chain()
    _source_2, duplicate_revision = _accepted_duplicate_chain(observations)
    revisions = [revision_3, duplicate_revision, revision_1, revision_2]
    ledger = build_behavior_hypothesis_ledger(revisions, [observations])
    return observations, revisions, ledger


def _entry_with_status(
    ledger: Mapping[str, Any], status: str
) -> dict[str, Any]:
    return next(
        entry
        for entry in ledger["entries"]
        if any(item["status"] == status for item in entry["occurrences"])
    )


def _codes(validation: Mapping[str, Any]) -> set[str]:
    return {str(item["code"]) for item in validation["findings"]}


def test_schema_loads_and_multi_chain_ledger_has_exact_active_audit_views() -> None:
    schema = json.loads(
        Path(
            "docs/contracts/P2G_BEHAVIOR_HYPOTHESIS_LEDGER.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    _observations, _revisions, ledger = _ledger_context()

    assert validate_behavior_hypothesis_ledger(ledger)["validation_status"] == "accepted"
    assert ledger["counts"] == {
        "source_chain_count": 2,
        "source_revision_count": 4,
        "fingerprint_count": 5,
        "occurrence_count": 8,
        "active_fingerprint_count": 1,
        "proposed_occurrence_count": 4,
        "accepted_occurrence_count": 1,
        "rejected_occurrence_count": 1,
        "superseded_occurrence_count": 2,
    }
    assert query_behavior_hypothesis_ledger(ledger, view="active")["match_count"] == 1
    assert query_behavior_hypothesis_ledger(ledger, view="audit")["match_count"] == 5

    deduplicated = _entry_with_status(ledger, "accepted")
    assert {item["status"] for item in deduplicated["occurrences"]} == {
        "accepted",
        "superseded",
    }
    assert len({item["revision_chain_id"] for item in deduplicated["occurrences"]}) == 2
    active = query_behavior_hypothesis_ledger(ledger, view="active")
    assert [item["status"] for item in active["entries"][0]["occurrences"]] == [
        "accepted"
    ]


def test_same_statement_with_different_scope_is_not_merged() -> None:
    observations, _source, revision_1, revision_2, revision_3 = audit_tests._chain()
    response = review_tests._recorded_response(observations)
    first = deepcopy(response["hypotheses"][0])
    second = response["hypotheses"][1]
    first["scope"] = deepcopy(second["scope"])
    first["evaluation_refs"] = deepcopy(second["evaluation_refs"])
    response["hypotheses"] = [first]
    result = build_behavior_hypothesis_set(
        observations,
        response_text=json.dumps(response, ensure_ascii=False, sort_keys=True),
        model_id=review_tests.MODEL_ID,
        generated_at="2026-07-18T12:00:02Z",
    )
    target = result.artifact["hypotheses"][0]
    extra_revision = apply_behavior_hypothesis_review(
        result.artifact,
        review_tests._request(
            result.artifact,
            [review_tests._action(target, "accept")],
            reviewed_at="2026-07-19T14:00:00Z",
        ),
        observation_artifact=observations,
    )
    ledger = build_behavior_hypothesis_ledger(
        [revision_1, revision_2, revision_3, extra_revision],
        [observations],
    )
    matching = [
        entry
        for entry in ledger["entries"]
        if entry["hypothesis"]["statement"] == first["statement"]
    ]
    assert len(matching) == 2
    assert len({item["fingerprint_id"] for item in matching}) == 2
    assert len(
        {
            tuple(item["hypothesis"]["scope"]["episode_ids"])
            for item in matching
        }
    ) == 2


def test_revision_fork_break_and_source_tamper_fail_closed() -> None:
    observations, _source, revision_1, revision_2, _revision_3 = audit_tests._chain()
    broken = deepcopy(revision_2)
    broken["revision"]["parent_content_id"] = "sha256:" + "f" * 64
    with pytest.raises(BehaviorHypothesisLedgerError, match="invalid revision chain"):
        build_behavior_hypothesis_ledger([revision_1, broken], [observations])

    fork = deepcopy(revision_2)
    fork["content_id"] = "sha256:" + "e" * 64
    with pytest.raises(BehaviorHypothesisLedgerError, match="invalid revision chain"):
        build_behavior_hypothesis_ledger(
            [revision_1, revision_2, fork], [observations]
        )

    ledger = build_behavior_hypothesis_ledger(
        [revision_1, revision_2], [observations]
    )
    tampered = deepcopy(observations)
    tampered["evaluations"][0]["facts"]["observed_relation"] = "tampered"
    with pytest.raises(BehaviorHypothesisLedgerError):
        build_behavior_hypothesis_ledger([revision_1, revision_2], [tampered])
    replay = replay_validate_behavior_hypothesis_ledger(
        ledger,
        revisions=[revision_1, revision_2],
        observation_artifacts=[tampered],
    )
    assert replay["validation_status"] == "blocked"
    assert "LEDGER_SOURCE_REPLAY_FAILED" in _codes(replay)


def test_query_uses_and_semantics_and_canonical_half_open_time_window() -> None:
    observations, _revisions, ledger = _ledger_context()
    entry = _entry_with_status(ledger, "accepted")
    occurrence = next(
        item for item in entry["occurrences"] if item["status"] == "accepted"
    )
    payload = entry["hypothesis"]
    result = query_behavior_hypothesis_ledger(
        ledger,
        view="active",
        status="accepted",
        hypothesis_id=occurrence["hypothesis_id"],
        episode_id=payload["scope"]["episode_ids"][0],
        evaluation_id=payload["evaluation_refs"][0],
        source_observation_content_id=observations["content_id"],
        actor="reviewer:test",
        reviewed_from="2026-07-19T13:00:00Z",
        reviewed_to="2026-07-19T13:00:01Z",
    )
    assert result["match_count"] == 1
    assert query_behavior_hypothesis_ledger(
        ledger,
        view="active",
        status="accepted",
        hypothesis_id=occurrence["hypothesis_id"],
        market_context="not-present",
    )["match_count"] == 0
    assert query_behavior_hypothesis_ledger(
        ledger,
        view="active",
        actor="reviewer:test",
        reviewed_from="2026-07-19T13:00:01Z",
        reviewed_to="2026-07-19T13:00:02Z",
    )["match_count"] == 0
    with pytest.raises(BehaviorHypothesisLedgerError, match="canonical UTC Z"):
        query_behavior_hypothesis_ledger(
            ledger, reviewed_from="2026-07-19T21:00:00+08:00"
        )


def test_ordering_content_id_and_source_inputs_are_deterministic_and_immutable() -> None:
    observations, revisions, ledger = _ledger_context()
    revision_bytes = [canonical_json_bytes(item) for item in revisions]
    observation_bytes = canonical_json_bytes(observations)
    rebuilt = build_behavior_hypothesis_ledger(
        list(reversed(deepcopy(revisions))), [deepcopy(observations)]
    )
    assert canonical_json_bytes(rebuilt) == canonical_json_bytes(ledger)
    assert rebuilt["content_id"] == ledger["content_id"]
    assert [canonical_json_bytes(item) for item in revisions] == revision_bytes
    assert canonical_json_bytes(observations) == observation_bytes
    replay = replay_validate_behavior_hypothesis_ledger(
        ledger,
        revisions=list(reversed(revisions)),
        observation_artifacts=[observations],
    )
    assert replay["validation_status"] == "accepted"
    assert replay["source_verification"]["status"] == "verified"


def test_empty_active_view_with_audit_history_is_valid() -> None:
    observations, _source, revision_1, revision_2, revision_3 = audit_tests._chain()
    ledger = build_behavior_hypothesis_ledger(
        [revision_3, revision_1, revision_2], [observations]
    )
    assert ledger["active_fingerprint_ids"] == []
    assert ledger["counts"]["active_fingerprint_count"] == 0
    assert query_behavior_hypothesis_ledger(ledger, view="active")["entries"] == []
    assert query_behavior_hypothesis_ledger(ledger, view="audit")["match_count"] == 5
    assert validate_behavior_hypothesis_ledger(ledger)["validation_status"] == "accepted"


def test_ledger_build_query_and_render_do_not_use_db_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("external access is forbidden")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    observations, _source, revision_1, revision_2, revision_3 = audit_tests._chain()
    ledger = build_behavior_hypothesis_ledger(
        [revision_1, revision_2, revision_3], [observations]
    )
    query_behavior_hypothesis_ledger(ledger, view="audit")
    assert "# Behavior Hypothesis Ledger" in (
        render_behavior_hypothesis_ledger_markdown(ledger)
    )


def test_render_escapes_injection_and_output_is_create_only(tmp_path: Path) -> None:
    observations, source = audit_tests._context()
    target = source["hypotheses"][0]
    replacement = review_tests._proposal(target)
    replacement["statement"] = "<b>bounded | # candidate</b>\nnext\x01line"
    request = review_tests._request(
        source,
        [
            review_tests._action(
                target,
                "correct",
                replacement=replacement,
                reason="<reviewer> | # reason\nnext\x02line",
            )
        ],
    )
    request["actor"] = "<actor>|#"
    request["request_id"] = behavior_hypothesis_review_request_id(request)
    revision = apply_behavior_hypothesis_review(
        source, request, observation_artifact=observations
    )
    ledger = build_behavior_hypothesis_ledger([revision], [observations])
    rendered = render_behavior_hypothesis_ledger_markdown(ledger)
    assert "<b>" not in rendered and "<actor>" not in rendered
    assert "&lt;b&gt;bounded \\| \\# candidate&lt;/b&gt; next�line" in rendered
    assert "&lt;actor&gt;\\|\\#" in rendered
    assert "\x01" not in rendered and "\x02" not in rendered

    ledger_path = tmp_path / "ledger.json"
    markdown_path = tmp_path / "ledger.md"
    save_behavior_hypothesis_ledger(ledger_path, ledger)
    save_behavior_hypothesis_ledger_markdown(markdown_path, rendered)
    with pytest.raises(BehaviorHypothesisLedgerError, match="exists"):
        save_behavior_hypothesis_ledger(ledger_path, ledger)
    with pytest.raises(BehaviorHypothesisLedgerError, match="exists"):
        save_behavior_hypothesis_ledger_markdown(markdown_path, rendered)


def test_cli_build_validate_query_render_and_failure_do_not_leak_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    observations, revisions, ledger = _ledger_context()
    observation_path = tmp_path / "observations.json"
    revisions_path = tmp_path / "revisions.json"
    observation_path.write_bytes(pretty_json_bytes(observations))
    revisions_path.write_bytes(pretty_json_bytes(revisions))
    ledger_path = tmp_path / "ledger.json"
    assert review_main(
        [
            "behavior-hypothesis-ledger-build",
            "--revision",
            str(revisions_path),
            "--observation-artifact",
            str(observation_path),
            "--output",
            str(ledger_path),
        ]
    ) == 0
    stdout = capsys.readouterr().out
    assert str(tmp_path) not in stdout and "output_created" in stdout
    assert ledger_path.read_bytes() == pretty_json_bytes(ledger)

    assert review_main(
        [
            "behavior-hypothesis-ledger-validate",
            str(ledger_path),
            "--source-replay",
            "--revision",
            str(revisions_path),
            "--observation-artifact",
            str(observation_path),
        ]
    ) == 0
    stdout = capsys.readouterr().out
    assert str(tmp_path) not in stdout and '"validation_status": "accepted"' in stdout

    assert review_main(
        [
            "behavior-hypothesis-ledger-query",
            str(ledger_path),
            "--view",
            "active",
            "--status",
            "accepted",
            "--actor",
            "reviewer:test",
        ]
    ) == 0
    stdout = capsys.readouterr().out
    assert str(tmp_path) not in stdout and '"match_count": 1' in stdout

    markdown_path = tmp_path / "ledger.md"
    assert review_main(
        [
            "behavior-hypothesis-ledger-render",
            "--artifact",
            str(ledger_path),
            "--output",
            str(markdown_path),
        ]
    ) == 0
    stdout = capsys.readouterr().out
    assert str(tmp_path) not in stdout and "output_created" in stdout
    assert markdown_path.is_file()

    missing_output = tmp_path / "missing.md"
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}", encoding="utf-8")
    assert review_main(
        [
            "behavior-hypothesis-ledger-render",
            "--artifact",
            str(invalid),
            "--output",
            str(missing_output),
        ]
    ) == 2
    captured = capsys.readouterr()
    assert str(tmp_path) not in captured.err
    assert not missing_output.exists()
