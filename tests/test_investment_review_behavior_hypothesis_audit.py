from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from src.investment_review.artifact_io import canonical_json_bytes, pretty_json_bytes
from src.investment_review.behavior_hypothesis_audit import (
    diff_behavior_hypothesis_revisions,
    list_behavior_hypothesis_revisions,
    render_behavior_hypothesis_revision_markdown,
    save_behavior_hypothesis_markdown,
)
from src.investment_review.behavior_hypothesis_review import (
    BehaviorHypothesisReviewError,
    apply_behavior_hypothesis_review,
    behavior_hypothesis_review_request_id,
    validate_behavior_hypothesis_revision_chain,
)
from src.investment_review.cli import main as review_main
from tests import test_investment_review_behavior_hypothesis_review as review_tests


GOLDEN_MARKDOWN_SHA256 = (
    "6e4484e7ae41be863595c1c7ad2f17a454eaa6010ce13b4fb0ad2ac40789be9f"
)


def _context() -> tuple[dict[str, Any], dict[str, Any]]:
    observations = review_tests.observation_artifact.__wrapped__()
    source = review_tests.p2g3_source.__wrapped__(observations)
    return observations, source


def _chain() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    observations, source = _context()
    first, second, third = source["hypotheses"]
    replacement = review_tests._proposal(third)
    replacement["statement"] = (
        "The one-episode candidate remains explicitly limited and needs more evidence."
    )
    revision_1 = apply_behavior_hypothesis_review(
        source,
        review_tests._request(
            source,
            [
                review_tests._action(
                    third, "correct", replacement=replacement
                )
            ],
        ),
        observation_artifact=observations,
    )
    revision_2 = apply_behavior_hypothesis_review(
        revision_1,
        review_tests._request(
            revision_1,
            [
                review_tests._action(first, "accept"),
                review_tests._action(second, "reject"),
            ],
            reviewed_at="2026-07-19T12:00:01Z",
        ),
        observation_artifact=observations,
    )
    accepted = review_tests._by_id(revision_2, first["hypothesis_id"])
    replacement_3 = review_tests._proposal(accepted)
    replacement_3["statement"] = (
        "The explicitly corrected candidate is narrower and returns to proposed."
    )
    revision_3 = apply_behavior_hypothesis_review(
        revision_2,
        review_tests._request(
            revision_2,
            [
                review_tests._action(
                    accepted, "correct", replacement=replacement_3
                )
            ],
            reviewed_at="2026-07-19T12:00:02Z",
        ),
        observation_artifact=observations,
    )
    return observations, source, revision_1, revision_2, revision_3


def _codes(validation: dict[str, Any]) -> set[str]:
    return {item["code"] for item in validation["findings"]}


def test_golden_markdown_is_stable_and_complete() -> None:
    _observations, _source, _revision_1, revision_2, _revision_3 = _chain()
    rendered = render_behavior_hypothesis_revision_markdown(revision_2)
    assert hashlib.sha256(rendered.encode("utf-8")).hexdigest() == GOLDEN_MARKDOWN_SHA256
    for marker in (
        "# P2G-4 行为假设人工审核修订",
        "accepted 仅表示人工确认保留为工作假设",
        "## 冻结来源与验证",
        "## 人工审核事件",
        "## 当前与历史行为假设",
        "- source_replay_status: `verified`",
        "- counterevidence_search:",
        "- falsification_conditions:",
        "- next_observations_needed:",
    ):
        assert marker in rendered


def test_markdown_escapes_html_tables_headings_newlines_and_controls() -> None:
    observations, source = _context()
    target = source["hypotheses"][0]
    replacement = review_tests._proposal(target)
    replacement["statement"] = "<b>bounded | candidate # heading</b>\nnext\x01line"
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
    rendered = render_behavior_hypothesis_revision_markdown(revision)
    assert "<b>" not in rendered
    assert "&lt;b&gt;bounded \\| candidate \\# heading&lt;/b&gt; next�line" in rendered
    assert "&lt;actor&gt;\\|\\#" in rendered
    assert "<reviewer>" not in rendered
    assert "\x01" not in rendered and "\x02" not in rendered


def test_diff_reports_no_change_accept_reject_and_correction_fields_only() -> None:
    _observations, _source, revision_1, revision_2, revision_3 = _chain()
    unchanged = diff_behavior_hypothesis_revisions(revision_1, revision_1)
    assert unchanged["added_hypothesis_ids"] == []
    assert unchanged["removed_hypothesis_ids"] == []
    assert unchanged["changed_hypotheses"] == []
    assert unchanged["review_events_added"] == []

    reviewed = diff_behavior_hypothesis_revisions(revision_1, revision_2)
    status_changes = {
        item["hypothesis_id"]: item["fields"]
        for item in reviewed["changed_hypotheses"]
    }
    assert len(status_changes) == 2
    assert all(set(fields) == {"status"} for fields in status_changes.values())
    assert {
        fields["status"]["after"] for fields in status_changes.values()
    } == {"accepted", "rejected"}

    corrected = diff_behavior_hypothesis_revisions(revision_2, revision_3)
    assert len(corrected["added_hypothesis_ids"]) == 1
    assert corrected["removed_hypothesis_ids"] == []
    assert len(corrected["changed_hypotheses"]) == 1
    assert corrected["changed_hypotheses"][0]["fields"] == {
        "status": {"before": "accepted", "after": "superseded"}
    }
    assert corrected["root_binding_unchanged"] is True
    assert corrected["observation_binding_unchanged"] is True
    assert corrected["model_provenance_unchanged"] is True


def test_revision_list_orders_multiple_revisions_and_derives_effective_state() -> None:
    _observations, _source, revision_1, revision_2, revision_3 = _chain()
    rows = list_behavior_hypothesis_revisions(
        [revision_3, revision_1, revision_2]
    )
    assert [item["revision_no"] for item in rows] == [1, 2, 3]
    assert [item["effective_status"] for item in rows] == [
        "superseded",
        "superseded",
        "current",
    ]
    assert rows[-1]["hypothesis_status_counts"]["proposed"] >= 1


def test_revision_chain_detects_break_fork_cycle_and_duplicate_content() -> None:
    _observations, _source, revision_1, revision_2, _revision_3 = _chain()

    broken = deepcopy(revision_2)
    broken["revision"]["parent_content_id"] = "sha256:" + "f" * 64
    validation = validate_behavior_hypothesis_revision_chain([revision_1, broken])
    assert validation["validation_status"] == "blocked"
    assert "REVISION_PARENT_MISMATCH" in _codes(validation)

    fork = deepcopy(revision_2)
    fork["content_id"] = "sha256:" + "e" * 64
    validation = validate_behavior_hypothesis_revision_chain(
        [revision_1, revision_2, fork]
    )
    assert validation["validation_status"] == "blocked"
    assert "REVISION_CHAIN_FORK" in _codes(validation)

    cycle_1 = deepcopy(revision_1)
    cycle_2 = deepcopy(revision_2)
    cycle_1["revision"]["parent_content_id"] = cycle_2["content_id"]
    cycle_2["revision"]["parent_content_id"] = cycle_1["content_id"]
    validation = validate_behavior_hypothesis_revision_chain([cycle_1, cycle_2])
    assert validation["validation_status"] == "blocked"
    assert "REVISION_CHAIN_CYCLE" in _codes(validation)

    validation = validate_behavior_hypothesis_revision_chain(
        [revision_1, revision_1]
    )
    assert validation["validation_status"] == "blocked"
    assert "REVISION_CONTENT_ID_DUPLICATE" in _codes(validation)
    with pytest.raises(BehaviorHypothesisReviewError):
        list_behavior_hypothesis_revisions([revision_1, broken])


def test_render_create_only_and_cli_audit_outputs_do_not_leak_local_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _observations, _source, revision_1, revision_2, revision_3 = _chain()
    paths = []
    for index, revision in enumerate((revision_1, revision_2, revision_3), start=1):
        path = tmp_path / f"revision-{index}.json"
        path.write_bytes(pretty_json_bytes(revision))
        paths.append(path)
    markdown = tmp_path / "revision.md"
    rendered = render_behavior_hypothesis_revision_markdown(revision_3)
    save_behavior_hypothesis_markdown(markdown, rendered)
    with pytest.raises(BehaviorHypothesisReviewError, match="exists"):
        save_behavior_hypothesis_markdown(markdown, rendered)

    assert review_main(
        [
            "behavior-hypothesis-render",
            "--artifact",
            str(paths[2]),
            "--output",
            str(tmp_path / "cli-render.md"),
        ]
    ) == 0
    render_stdout = capsys.readouterr().out
    assert str(tmp_path) not in render_stdout
    assert "output_created" in render_stdout

    assert review_main(
        ["behavior-hypothesis-diff", str(paths[0]), str(paths[2])]
    ) == 0
    diff_stdout = capsys.readouterr().out
    assert str(tmp_path) not in diff_stdout
    assert '"schema_version": "p2g.behavior_hypothesis_revision_diff.v1"' in diff_stdout

    assert review_main(
        [
            "behavior-hypothesis-revision-list",
            str(paths[2]),
            str(paths[0]),
            str(paths[1]),
        ]
    ) == 0
    list_stdout = capsys.readouterr().out
    assert str(tmp_path) not in list_stdout
    assert '"effective_status": "current"' in list_stdout

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}", encoding="utf-8")
    assert review_main(
        [
            "behavior-hypothesis-render",
            "--artifact",
            str(invalid),
            "--output",
            str(tmp_path / "invalid.md"),
        ]
    ) == 2
    stderr = capsys.readouterr().err
    assert str(tmp_path) not in stderr
    assert "REVISION_SCHEMA_INVALID" in stderr


def test_render_and_diff_are_deterministic_and_path_independent() -> None:
    _observations, _source, revision_1, revision_2, _revision_3 = _chain()
    assert (
        render_behavior_hypothesis_revision_markdown(revision_2)
        == render_behavior_hypothesis_revision_markdown(deepcopy(revision_2))
    )
    assert canonical_json_bytes(
        diff_behavior_hypothesis_revisions(revision_1, revision_2)
    ) == canonical_json_bytes(
        diff_behavior_hypothesis_revisions(deepcopy(revision_1), deepcopy(revision_2))
    )
