"""Safe rendering and deterministic audit tools for P2G-4 revisions."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from textwrap import wrap
from typing import Any, Mapping, Sequence

from .artifact_io import ArtifactIOError, atomic_create_bytes, canonical_json_bytes
from .behavior_hypothesis_review import (
    BehaviorHypothesisReviewError,
    validate_behavior_hypothesis_revision,
    validate_behavior_hypothesis_revision_chain,
)
from .episode_review import _markdown_code, _markdown_escape


DIFF_SCHEMA_VERSION = "p2g.behavior_hypothesis_revision_diff.v1"

_BUSINESS_FIELDS = (
    "status",
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
    "warning_codes",
    "guardrail_flags",
    "lineage_root_hypothesis_id",
    "supersedes_hypothesis_id",
)


def _valid_or_raise(artifact: Mapping[str, Any], label: str) -> None:
    validation = validate_behavior_hypothesis_revision(artifact)
    if validation["validation_status"] == "blocked":
        codes = sorted({item["code"] for item in validation["findings"]})
        raise BehaviorHypothesisReviewError(
            f"{label} revision is invalid: {', '.join(codes)}"
        )


def _wrapped(value: object, *, prefix: str = "") -> list[str]:
    escaped = _markdown_escape(value)
    width = max(20, 88 - len(prefix))
    pieces = wrap(
        escaped,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
        replace_whitespace=False,
        drop_whitespace=True,
    ) or [""]
    return [prefix + pieces[0], *[(" " * len(prefix)) + item for item in pieces[1:]]]


def _string_list(lines: list[str], label: str, values: Sequence[object]) -> None:
    lines.append(f"- {label}:")
    if not values:
        lines.append("  - `none`")
        return
    for value in values:
        lines.extend(_wrapped(value, prefix="  - "))


def render_behavior_hypothesis_revision_markdown(
    artifact: Mapping[str, Any],
) -> str:
    """Render one validated P2G-4 revision as escaped, stable Markdown."""

    _valid_or_raise(artifact, "input")
    revision = artifact["revision"]
    source = artifact["source_observation_set"]
    model = artifact["model_provenance"]
    lines = [
        "# P2G-4 行为假设人工审核修订",
        "",
        f"- schema_version: {_markdown_code(artifact['schema_version'])}",
        f"- content_id: {_markdown_code(artifact['content_id'])}",
        f"- revision_chain_id: {_markdown_code(artifact['revision_chain_id'])}",
        f"- revision_no: {_markdown_code(revision['revision_no'])}",
        f"- parent_content_id: {_markdown_code(revision['parent_content_id'])}",
        "- root_hypothesis_set_content_id: "
        + _markdown_code(revision["root_hypothesis_set_content_id"]),
        f"- request_id: {_markdown_code(revision['request_id'])}",
        "",
        "> accepted 仅表示人工确认保留为工作假设，不是事实证明、心理诊断或交易建议。",
        "",
        "## 冻结来源与验证",
        "",
        f"- source_observation_content_id: {_markdown_code(source['content_id'])}",
        f"- source_observation_set_id: {_markdown_code(source['observation_set_id'])}",
        f"- model_id: {_markdown_code(model['model_id'])}",
        f"- model_generated_at: {_markdown_code(model['generated_at'])}",
        f"- model_response_sha256: {_markdown_code(model['response_sha256'])}",
        "- source_replay_status: "
        + _markdown_code(artifact["source_verification"]["status"]),
        "- source_replay_content_id: "
        + _markdown_code(artifact["source_verification"]["verified_content_id"]),
        "- release_readiness: "
        + _markdown_code(artifact["release_readiness"]["status"]),
    ]
    _string_list(lines, "warnings", artifact["warnings"])

    lines.extend(["", "## 人工审核事件"])
    for event in artifact["review_events"]:
        lines.extend(
            [
                "",
                f"### {_markdown_code(event['review_event_id'])}",
                "",
                f"- request_id: {_markdown_code(event['request_id'])}",
                f"- action: {_markdown_code(event['action'])}",
                f"- reviewed_at: {_markdown_code(event['reviewed_at'])}",
                f"- actor: {_markdown_escape(event['actor'])}",
            ]
        )
        lines.extend(_wrapped(event["reason"], prefix="- reason: "))
        lines.extend(
            [
                "- target_hypothesis_id: "
                + _markdown_code(event["target_hypothesis_id"]),
                "- result_hypothesis_id: "
                + _markdown_code(event["result_hypothesis_id"]),
                "- status_transition: "
                + _markdown_code(event["target_status_before"])
                + " -> "
                + _markdown_code(event["target_status_after"]),
                f"- result_status: {_markdown_code(event['result_status'])}",
            ]
        )

    lines.extend(["", "## 当前与历史行为假设"])
    for hypothesis in artifact["hypotheses"]:
        lines.extend(
            [
                "",
                f"### {_markdown_code(hypothesis['hypothesis_id'])}",
                "",
                f"- status: {_markdown_code(hypothesis['status'])}",
                "- lineage_root_hypothesis_id: "
                + _markdown_code(hypothesis["lineage_root_hypothesis_id"]),
                "- supersedes_hypothesis_id: "
                + _markdown_code(hypothesis["supersedes_hypothesis_id"] or "none"),
            ]
        )
        lines.extend(_wrapped(hypothesis["statement"], prefix="- statement: "))
        scope = hypothesis["scope"]
        _string_list(lines, "scope.episode_ids", scope["episode_ids"])
        lines.extend(
            [
                f"- scope.start_at: {_markdown_code(scope['start_at'] or 'none')}",
                f"- scope.end_at: {_markdown_code(scope['end_at'] or 'none')}",
            ]
        )
        _string_list(lines, "scope.market_contexts", scope["market_contexts"])
        _string_list(lines, "evaluation_refs", hypothesis["evaluation_refs"])
        _string_list(lines, "supporting_reasons", hypothesis["supporting_reasons"])
        _string_list(
            lines,
            "counterevidence_evaluation_refs",
            hypothesis["counterevidence_evaluation_refs"],
        )
        lines.extend(
            _wrapped(
                hypothesis["counterevidence_search"] or "none",
                prefix="- counterevidence_search: ",
            )
        )
        _string_list(
            lines, "alternative_explanations", hypothesis["alternative_explanations"]
        )
        _string_list(lines, "assumptions", hypothesis["assumptions"])
        _string_list(lines, "uncertainty_notes", hypothesis["uncertainty_notes"])
        _string_list(
            lines, "falsification_conditions", hypothesis["falsification_conditions"]
        )
        _string_list(
            lines, "next_observations_needed", hypothesis["next_observations_needed"]
        )
        lines.append(
            "- temporal_perspective: "
            + _markdown_code(hypothesis["temporal_perspective"])
        )
        _string_list(lines, "warning_codes", hypothesis["warning_codes"])
        _string_list(lines, "guardrail_flags", hypothesis["guardrail_flags"])
    return "\n".join(lines) + "\n"


def save_behavior_hypothesis_markdown(path: str | Path, rendered: str) -> Path:
    output = Path(path)
    if output.exists():
        raise BehaviorHypothesisReviewError("Markdown output already exists")
    try:
        return atomic_create_bytes(output, rendered.encode("utf-8"))
    except (ArtifactIOError, OSError) as exc:
        raise BehaviorHypothesisReviewError("failed to create Markdown output") from exc


def _hypothesis_index(
    artifact: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    return {
        str(item["hypothesis_id"]): item
        for item in artifact["hypotheses"]
        if isinstance(item, Mapping)
    }


def diff_behavior_hypothesis_revisions(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, Any]:
    """Report only real field changes between two validated revisions."""

    _valid_or_raise(before, "before")
    _valid_or_raise(after, "after")
    if before["revision_chain_id"] != after["revision_chain_id"]:
        raise BehaviorHypothesisReviewError("cannot diff different revision chains")
    before_no = before["revision"]["revision_no"]
    after_no = after["revision"]["revision_no"]
    if before_no > after_no:
        raise BehaviorHypothesisReviewError("diff requires chronological revision order")
    if before_no == after_no and before["content_id"] != after["content_id"]:
        raise BehaviorHypothesisReviewError("same revision number has different content")
    before_events = before["review_events"]
    after_events = after["review_events"]
    if after_events[: len(before_events)] != before_events:
        raise BehaviorHypothesisReviewError("review event history is not an append-only prefix")
    before_index = _hypothesis_index(before)
    after_index = _hypothesis_index(after)
    changes: list[dict[str, Any]] = []
    for hypothesis_id in sorted(set(before_index) & set(after_index)):
        fields: dict[str, Any] = {}
        for field in _BUSINESS_FIELDS:
            previous = before_index[hypothesis_id].get(field)
            current = after_index[hypothesis_id].get(field)
            if canonical_json_bytes(previous) != canonical_json_bytes(current):
                fields[field] = {"before": deepcopy(previous), "after": deepcopy(current)}
        if fields:
            changes.append({"hypothesis_id": hypothesis_id, "fields": fields})
    return {
        "schema_version": DIFF_SCHEMA_VERSION,
        "revision_chain_id": before["revision_chain_id"],
        "from_revision_no": before_no,
        "to_revision_no": after_no,
        "from_content_id": before["content_id"],
        "to_content_id": after["content_id"],
        "root_binding_unchanged": canonical_json_bytes(
            before["source_hypothesis_set"]
        )
        == canonical_json_bytes(after["source_hypothesis_set"]),
        "observation_binding_unchanged": canonical_json_bytes(
            before["source_observation_set"]
        )
        == canonical_json_bytes(after["source_observation_set"]),
        "model_provenance_unchanged": canonical_json_bytes(
            before["model_provenance"]
        )
        == canonical_json_bytes(after["model_provenance"]),
        "added_hypothesis_ids": sorted(set(after_index) - set(before_index)),
        "removed_hypothesis_ids": sorted(set(before_index) - set(after_index)),
        "changed_hypotheses": changes,
        "review_events_added": deepcopy(after_events[len(before_events) :]),
    }


def list_behavior_hypothesis_revisions(
    artifacts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """List a complete non-forking chain with stored and effective states."""

    validation = validate_behavior_hypothesis_revision_chain(artifacts)
    if validation["validation_status"] == "blocked":
        codes = sorted({item["code"] for item in validation["findings"]})
        raise BehaviorHypothesisReviewError(
            "refusing to list an invalid revision chain: " + ", ".join(codes)
        )
    ordered = sorted(artifacts, key=lambda item: item["revision"]["revision_no"])
    latest = ordered[-1]["revision"]["revision_no"]
    rows: list[dict[str, Any]] = []
    for artifact in ordered:
        counts = {status: 0 for status in ("proposed", "accepted", "rejected", "superseded")}
        for item in artifact["hypotheses"]:
            counts[str(item["status"])] += 1
        rows.append(
            {
                "revision_chain_id": artifact["revision_chain_id"],
                "revision_no": artifact["revision"]["revision_no"],
                "effective_status": (
                    "current"
                    if artifact["revision"]["revision_no"] == latest
                    else "superseded"
                ),
                "content_id": artifact["content_id"],
                "parent_content_id": artifact["revision"]["parent_content_id"],
                "root_hypothesis_set_content_id": artifact["revision"][
                    "root_hypothesis_set_content_id"
                ],
                "request_id": artifact["revision"]["request_id"],
                "review_event_count": len(artifact["review_events"]),
                "hypothesis_status_counts": counts,
            }
        )
    return rows


__all__ = [
    "DIFF_SCHEMA_VERSION",
    "diff_behavior_hypothesis_revisions",
    "list_behavior_hypothesis_revisions",
    "render_behavior_hypothesis_revision_markdown",
    "save_behavior_hypothesis_markdown",
]
