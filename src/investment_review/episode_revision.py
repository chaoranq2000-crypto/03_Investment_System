"""Append-only human review revisions for P2F episode-review artifacts.

The module accepts a closed human-review request, derives a new immutable
episode-review artifact, and validates the complete supersedes chain.  It has
no database dependency and never overwrites an existing artifact path.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from .artifact_io import (
    ArtifactIOError,
    atomic_create_bytes,
    canonical_json_bytes,
    load_json_object,
    pretty_json_bytes,
)
from .episode_interpretation import finding_content_id, option_content_id
from .episode_review import (
    FACT_SECTION_NAMES,
    validate_episode_review,
)


REQUEST_SCHEMA_VERSION = "p2f.human_review_request.v1"
REQUEST_VALIDATION_SCHEMA_VERSION = "p2f.human_review_request.validation.v1"
CHAIN_VALIDATION_SCHEMA_VERSION = "p2f.episode_revision_chain.validation.v1"
DIFF_SCHEMA_VERSION = "p2f.episode_review_diff.v1"

FINDING_SECTION_NAMES = (
    "main_tensions",
    "hypotheses",
    "alternative_explanations",
)

_REQUEST_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "contracts"
    / "P2F_HUMAN_REVIEW_REQUEST.schema.json"
)
_CONTENT_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_FINDING_ID_RE = re.compile(r"^finding:[0-9a-f]{32}$")
_OPTION_ID_RE = re.compile(r"^option:[0-9a-f]{32}$")
_REVIEW_EVENT_ID_RE = re.compile(r"^review-event:[0-9a-f]{32}$")


class EpisodeRevisionError(ValueError):
    """Raised when a human review or revision chain is unsafe."""


def _stable_id(prefix: str, value: object) -> str:
    digest = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    return f"{prefix}:{digest[:32]}"


def _content_id(value: Mapping[str, Any]) -> str:
    material = deepcopy(dict(value))
    material.pop("content_id", None)
    return "sha256:" + hashlib.sha256(canonical_json_bytes(material)).hexdigest()


def _finding(code: str, message: str) -> dict[str, str]:
    return {"severity": "blocker", "code": code, "message": message}


def _validation(
    findings: Iterable[Mapping[str, Any]], *, schema_version: str
) -> dict[str, Any]:
    values = sorted(
        [dict(item) for item in findings],
        key=lambda item: (str(item.get("code") or ""), str(item.get("message") or "")),
    )
    return {
        "schema_version": schema_version,
        "validation_status": "blocked" if values else "accepted",
        "findings": values,
    }


def _canonical_timestamp(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise EpisodeRevisionError(f"{field} must be a timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EpisodeRevisionError(f"invalid {field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.microsecond:
        raise EpisodeRevisionError(f"{field} must use timezone-aware whole seconds")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


@lru_cache(maxsize=1)
def _request_validator() -> Draft202012Validator:
    schema = json.loads(_REQUEST_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_human_review_request(request: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the closed P2F-4 request contract without raising."""

    findings: list[dict[str, str]] = []
    if not isinstance(request, Mapping):
        return _validation(
            [_finding("MALFORMED_HUMAN_REVIEW_REQUEST", "request must be an object")],
            schema_version=REQUEST_VALIDATION_SCHEMA_VERSION,
        )
    try:
        canonical_json_bytes(request)
    except ArtifactIOError as exc:
        findings.append(_finding("NON_CANONICAL_JSON", str(exc)))
    try:
        errors = sorted(
            _request_validator().iter_errors(request),
            key=lambda item: (list(item.absolute_path), item.message),
        )
    except Exception as exc:
        errors = []
        findings.append(_finding("REQUEST_SCHEMA_FAILURE", str(exc)))
    for error in errors:
        path = "$" + "".join(
            f"[{item}]" if isinstance(item, int) else f".{item}"
            for item in error.absolute_path
        )
        findings.append(_finding("REQUEST_SCHEMA_VIOLATION", f"{path}: {error.message}"))
    try:
        canonical = _canonical_timestamp(request.get("reviewed_at"), "reviewed_at")
    except EpisodeRevisionError as exc:
        findings.append(_finding("REVIEWED_AT_INVALID", str(exc)))
    else:
        if canonical != request.get("reviewed_at"):
            findings.append(
                _finding("REVIEWED_AT_INVALID", "reviewed_at must be canonical UTC Z")
            )
    for field in ("actor_ref", "reason"):
        value = request.get(field)
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            findings.append(
                _finding(
                    f"{field.upper()}_INVALID",
                    f"{field} must be a non-empty canonical string",
                )
            )
    target_ids = request.get("target_ids")
    corrections = request.get("corrections")
    if request.get("action") == "correct" and isinstance(target_ids, list) and isinstance(
        corrections, list
    ):
        correction_targets = [
            item.get("target_id")
            for item in corrections
            if isinstance(item, Mapping)
        ]
        if len(set(correction_targets)) != len(correction_targets):
            findings.append(
                _finding("CORRECTION_TARGET_DUPLICATE", "each target may be corrected once")
            )
        if set(correction_targets) != set(target_ids):
            findings.append(
                _finding(
                    "CORRECTION_TARGET_MISMATCH",
                    "correction targets must exactly match target_ids",
                )
            )
    return _validation(findings, schema_version=REQUEST_VALIDATION_SCHEMA_VERSION)


def load_human_review_request(path: str | Path) -> dict[str, Any]:
    try:
        return load_json_object(path)
    except ArtifactIOError as exc:
        raise EpisodeRevisionError(str(exc)) from exc


def _fact_ids(artifact: Mapping[str, Any]) -> set[str]:
    sections = artifact.get("fact_sections")
    if not isinstance(sections, Mapping):
        return set()
    return {
        str(fact.get("fact_id"))
        for section_name in FACT_SECTION_NAMES
        for fact in (
            sections.get(section_name, {}).get("facts", [])
            if isinstance(sections.get(section_name), Mapping)
            else []
        )
        if isinstance(fact, Mapping) and fact.get("fact_id")
    }


def _interpretation_index(
    artifact: Mapping[str, Any],
) -> dict[str, tuple[str, dict[str, Any]]]:
    sections = artifact.get("interpretation_sections")
    if not isinstance(sections, Mapping):
        return {}
    result: dict[str, tuple[str, dict[str, Any]]] = {}
    for section_name in FINDING_SECTION_NAMES:
        for item in sections.get(section_name, []):
            if isinstance(item, Mapping):
                result[str(item.get("finding_id") or "")] = (
                    section_name,
                    dict(item),
                )
    for item in sections.get("counterfactual_options", []):
        if isinstance(item, Mapping):
            result[str(item.get("option_id") or "")] = (
                "counterfactual_options",
                dict(item),
            )
    return result


def _interpretation_ids(artifact: Mapping[str, Any]) -> set[str]:
    return {value for value in _interpretation_index(artifact) if value}


def _event_id(event: Mapping[str, Any]) -> str:
    material = deepcopy(dict(event))
    material.pop("review_event_id", None)
    return _stable_id("review-event", material)


def _request_or_raise(request: Mapping[str, Any]) -> None:
    validation = validate_human_review_request(request)
    if validation["validation_status"] == "blocked":
        codes = ", ".join(item["code"] for item in validation["findings"])
        raise EpisodeRevisionError(f"invalid human review request: {codes}")


def _source_or_raise(artifact: Mapping[str, Any]) -> None:
    validation = validate_episode_review(artifact)
    if validation["validation_status"] == "blocked":
        raise EpisodeRevisionError("source episode review is invalid")
    governance = artifact.get("governance")
    mode = governance.get("generation_mode") if isinstance(governance, Mapping) else None
    if mode not in {"model_assisted", "human_authored"}:
        raise EpisodeRevisionError(
            "human review requires a model-assisted or human-authored interpretation"
        )


def _latest_provenance_time(artifact: Mapping[str, Any]) -> str | None:
    governance = artifact.get("governance")
    if not isinstance(governance, Mapping):
        return None
    events = governance.get("human_reviews")
    if isinstance(events, list) and events:
        latest = events[-1]
        return str(latest.get("reviewed_at")) if isinstance(latest, Mapping) else None
    model = governance.get("model_generation")
    return str(model.get("generated_at")) if isinstance(model, Mapping) else None


def apply_human_review(
    artifact: Mapping[str, Any], request: Mapping[str, Any]
) -> dict[str, Any]:
    """Return one validated append-only revision without mutating the source."""

    _request_or_raise(request)
    _source_or_raise(artifact)
    source_bytes = canonical_json_bytes(artifact)
    source_content_id = str(artifact.get("content_id") or "")
    reviewed_at = str(request["reviewed_at"])
    latest_time = _latest_provenance_time(artifact)
    if latest_time is not None and reviewed_at < _canonical_timestamp(
        latest_time, "prior provenance time"
    ):
        raise EpisodeRevisionError("reviewed_at cannot precede prior provenance")

    target_ids = sorted(set(str(value) for value in request["target_ids"]))
    source_index = _interpretation_index(artifact)
    unknown_targets = sorted(set(target_ids) - set(source_index))
    if unknown_targets:
        raise EpisodeRevisionError(
            "human review targets unknown interpretation IDs: " + ", ".join(unknown_targets)
        )
    action = str(request["action"])
    if action in {"accept", "reject"} and any(
        not _FINDING_ID_RE.fullmatch(target_id) for target_id in target_ids
    ):
        raise EpisodeRevisionError("accept/reject actions may target findings only")

    corrections = {
        str(item["target_id"]): dict(item)
        for item in request["corrections"]
        if isinstance(item, Mapping)
    }
    fact_ids = _fact_ids(artifact)
    for correction in corrections.values():
        refs = {
            str(value)
            for value in correction.get("fact_refs", [])
        } | {
            str(value)
            for value in correction.get("counterevidence_fact_refs", [])
        }
        unknown_facts = sorted(refs - fact_ids)
        if unknown_facts:
            raise EpisodeRevisionError(
                "correction references unknown facts: " + ", ".join(unknown_facts)
            )

    candidate = deepcopy(dict(artifact))
    sections = candidate["interpretation_sections"]
    result_ids: dict[str, str] = {}
    for section_name in FINDING_SECTION_NAMES:
        revised_items: list[dict[str, Any]] = []
        for raw in sections[section_name]:
            item = deepcopy(dict(raw))
            old_id = str(item["finding_id"])
            if old_id in target_ids:
                if action == "accept":
                    item["review_status"] = "accepted"
                elif action == "reject":
                    item["review_status"] = "rejected"
                else:
                    correction = corrections[old_id]
                    item["fact_refs"] = sorted(
                        set(str(value) for value in correction["fact_refs"])
                    )
                    if "counterevidence_status" in correction:
                        item["counterevidence_status"] = correction[
                            "counterevidence_status"
                        ]
                    if "counterevidence_fact_refs" in correction:
                        item["counterevidence_fact_refs"] = sorted(
                            set(
                                str(value)
                                for value in correction["counterevidence_fact_refs"]
                            )
                        )
                    item["review_status"] = "revised"
                item["finding_id"] = finding_content_id(section_name, item)
                result_ids[old_id] = str(item["finding_id"])
            revised_items.append(item)
        sections[section_name] = sorted(
            revised_items, key=lambda value: str(value["finding_id"])
        )

    revised_options: list[dict[str, Any]] = []
    for raw in sections["counterfactual_options"]:
        item = deepcopy(dict(raw))
        old_id = str(item["option_id"])
        if old_id in target_ids:
            if action != "correct":
                raise EpisodeRevisionError("counterfactual options may only be corrected")
            correction = corrections[old_id]
            if {
                "counterevidence_status",
                "counterevidence_fact_refs",
            } & set(correction):
                raise EpisodeRevisionError(
                    "counterevidence fields are not valid for counterfactual options"
                )
            item["fact_refs"] = sorted(
                set(str(value) for value in correction["fact_refs"])
            )
            item["option_id"] = option_content_id(item)
            result_ids[old_id] = str(item["option_id"])
        revised_options.append(item)
    sections["counterfactual_options"] = sorted(
        revised_options, key=lambda value: str(value["option_id"])
    )
    if set(result_ids) != set(target_ids):
        raise EpisodeRevisionError("not every requested target produced a revised result")
    if any(source_id == result_ids[source_id] for source_id in target_ids):
        raise EpisodeRevisionError("human review must produce a material interpretation change")

    event: dict[str, Any] = {
        "review_event_id": "",
        "action": action,
        "reviewed_at": reviewed_at,
        "actor_ref": str(request["actor_ref"]),
        "reason": str(request["reason"]),
        "source_content_id": source_content_id,
        "target_ids": target_ids,
        "result_target_ids": sorted(result_ids.values()),
    }
    event["review_event_id"] = _event_id(event)

    prior_governance = artifact["governance"]
    human_reviews = deepcopy(list(prior_governance["human_reviews"]))
    human_reviews.append(event)
    human_reviews.sort(
        key=lambda value: (str(value["reviewed_at"]), str(value["review_event_id"]))
    )
    if human_reviews[-1] != event:
        raise EpisodeRevisionError("review event chronology must be append-only")
    candidate["governance"] = {
        "facts_interpretation_separated": True,
        "no_advice": True,
        "no_mechanical_score": True,
        "generation_mode": "human_authored",
        "model_generation": None,
        "human_reviews": human_reviews,
    }
    prior_revision = artifact["revision"]
    candidate["revision"] = {
        "revision_no": int(prior_revision["revision_no"]) + 1,
        "status": "corrected" if action == "correct" else "reviewed",
        "supersedes_content_id": source_content_id,
        "correction_reason": str(request["reason"]) if action == "correct" else None,
    }
    candidate["content_id"] = _content_id(candidate)
    validation = validate_episode_review(candidate)
    if validation["validation_status"] == "blocked":
        codes = ", ".join(item["code"] for item in validation["findings"])
        raise EpisodeRevisionError(f"human revision failed validation: {codes}")
    if canonical_json_bytes(artifact) != source_bytes:
        raise EpisodeRevisionError("source artifact was mutated")
    return candidate


def revision_layer_findings(artifact: Mapping[str, Any]) -> list[dict[str, str]]:
    """Return offline P2F-4 revision/event findings without recursive validation."""

    governance = artifact.get("governance")
    if not isinstance(governance, Mapping) or governance.get("generation_mode") != "human_authored":
        return []
    findings: list[dict[str, str]] = []
    revision = artifact.get("revision")
    if not isinstance(revision, Mapping):
        return [_finding("HUMAN_REVISION_INVALID", "revision must be an object")]
    revision_no = revision.get("revision_no")
    if not isinstance(revision_no, int) or isinstance(revision_no, bool) or revision_no < 2:
        findings.append(
            _finding("HUMAN_REVISION_INVALID", "human revision_no must be at least 2")
        )
    status = revision.get("status")
    if status not in {"reviewed", "corrected"}:
        findings.append(
            _finding(
                "HUMAN_REVISION_STATUS_INVALID",
                "stored human revisions must be reviewed or corrected",
            )
        )
    supersedes = str(revision.get("supersedes_content_id") or "")
    if not _CONTENT_ID_RE.fullmatch(supersedes):
        findings.append(
            _finding("SUPERSEDES_CONTENT_ID_INVALID", "human revision must supersede one artifact")
        )
    reason = revision.get("correction_reason")
    if status == "corrected" and (
        not isinstance(reason, str) or not reason.strip() or reason != reason.strip()
    ):
        findings.append(
            _finding("CORRECTION_REASON_INVALID", "corrected revision requires a reason")
        )
    if status == "reviewed" and reason is not None:
        findings.append(
            _finding("CORRECTION_REASON_INVALID", "reviewed revision cannot carry a correction reason")
        )
    if governance.get("model_generation") is not None:
        findings.append(
            _finding("HUMAN_MODEL_PROVENANCE_INVALID", "human revision model_generation must be null")
        )

    events = governance.get("human_reviews")
    if not isinstance(events, list) or not events:
        return findings + [
            _finding("HUMAN_REVIEW_EVENT_MISSING", "human revision requires review events")
        ]
    mapping_events = [event for event in events if isinstance(event, Mapping)]
    if len(mapping_events) != len(events):
        findings.append(
            _finding("HUMAN_REVIEW_EVENT_INVALID", "human review events must be objects")
        )
    canonical_events = sorted(
        mapping_events,
        key=lambda value: (
            str(value.get("reviewed_at") or ""),
            str(value.get("review_event_id") or ""),
        ),
    )
    if list(events) != canonical_events:
        findings.append(
            _finding("HUMAN_REVIEW_EVENT_ORDER_INVALID", "human review events are not canonical")
        )
    seen_events: set[str] = set()
    for event in mapping_events:
        event_id = str(event.get("review_event_id") or "")
        if not _REVIEW_EVENT_ID_RE.fullmatch(event_id) or event_id != _event_id(event):
            findings.append(
                _finding("HUMAN_REVIEW_EVENT_ID_MISMATCH", "review event ID is not content-derived")
            )
        if event_id in seen_events:
            findings.append(
                _finding("HUMAN_REVIEW_EVENT_DUPLICATE", f"duplicate event {event_id}")
            )
        seen_events.add(event_id)
        try:
            timestamp = _canonical_timestamp(event.get("reviewed_at"), "reviewed_at")
        except EpisodeRevisionError:
            findings.append(
                _finding("HUMAN_REVIEW_TIME_INVALID", f"{event_id} has an invalid time")
            )
        else:
            if timestamp != event.get("reviewed_at"):
                findings.append(
                    _finding("HUMAN_REVIEW_TIME_INVALID", f"{event_id} time is not canonical")
                )
        for field in ("actor_ref", "reason"):
            value = event.get(field)
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                findings.append(
                    _finding("HUMAN_REVIEW_EVENT_INVALID", f"{event_id} has invalid {field}")
                )
        for field in ("target_ids", "result_target_ids"):
            values = event.get(field)
            if (
                not isinstance(values, list)
                or not values
                or values != sorted(set(str(value) for value in values))
                or not all(
                    _FINDING_ID_RE.fullmatch(str(value))
                    or _OPTION_ID_RE.fullmatch(str(value))
                    for value in values
                )
            ):
                findings.append(
                    _finding("HUMAN_REVIEW_TARGET_INVALID", f"{event_id} has invalid {field}")
                )
        targets = event.get("target_ids")
        results = event.get("result_target_ids")
        if isinstance(targets, list) and isinstance(results, list):
            if len(targets) != len(results):
                findings.append(
                    _finding(
                        "HUMAN_REVIEW_RESULT_COUNT_MISMATCH",
                        f"{event_id} targets and results are not one-to-one",
                    )
                )
            if set(targets) & set(results):
                findings.append(
                    _finding(
                        "HUMAN_REVIEW_NOOP",
                        f"{event_id} contains an unchanged target ID",
                    )
                )
            if event.get("action") in {"accept", "reject"} and any(
                not _FINDING_ID_RE.fullmatch(str(value))
                for value in [*targets, *results]
            ):
                findings.append(
                    _finding(
                        "HUMAN_REVIEW_TARGET_INVALID",
                        f"{event_id} accept/reject action contains a non-finding ID",
                    )
                )
        if not _CONTENT_ID_RE.fullmatch(str(event.get("source_content_id") or "")):
            findings.append(
                _finding("HUMAN_REVIEW_SOURCE_INVALID", f"{event_id} source is invalid")
            )

    last = mapping_events[-1] if mapping_events else {}
    if last.get("source_content_id") != revision.get("supersedes_content_id"):
        findings.append(
            _finding("HUMAN_REVIEW_SOURCE_MISMATCH", "latest event must bind the superseded artifact")
        )
    expected_status = "corrected" if last.get("action") == "correct" else "reviewed"
    if last.get("action") not in {"accept", "reject", "correct"} or status != expected_status:
        findings.append(
            _finding("HUMAN_REVIEW_ACTION_MISMATCH", "latest action does not match revision status")
        )
    current_ids = _interpretation_ids(artifact)
    result_ids = last.get("result_target_ids")
    if isinstance(result_ids, list) and not set(result_ids).issubset(current_ids):
        findings.append(
            _finding("HUMAN_REVIEW_RESULT_MISSING", "latest result IDs are absent from the revision")
        )
    return findings


def _chain_transition_findings(
    previous: Mapping[str, Any], current: Mapping[str, Any]
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    previous_events = previous["governance"]["human_reviews"]
    current_events = current["governance"]["human_reviews"]
    if current_events[:-1] != previous_events or len(current_events) != len(previous_events) + 1:
        findings.append(
            _finding(
                "HUMAN_REVIEW_HISTORY_MISMATCH",
                "each revision must append exactly one unchanged human review event",
            )
        )
        return findings
    event = current_events[-1]
    if event["source_content_id"] != previous["content_id"]:
        findings.append(
            _finding("HUMAN_REVIEW_SOURCE_MISMATCH", "event source must equal the prior content ID")
        )
    before = _interpretation_index(previous)
    after = _interpretation_index(current)
    targets = set(event["target_ids"])
    results = set(event["result_target_ids"])
    if not targets.issubset(before):
        findings.append(
            _finding("HUMAN_REVIEW_TARGET_MISSING", "event targets are absent from the prior revision")
        )
    if not results.issubset(after):
        findings.append(
            _finding("HUMAN_REVIEW_RESULT_MISSING", "event results are absent from the new revision")
        )
    if (set(before) - targets) != (set(after) - results):
        findings.append(
            _finding(
                "UNSCOPED_INTERPRETATION_CHANGE",
                "a revision changed interpretation IDs outside its declared targets",
            )
        )
    for unchanged_id in sorted((set(before) - targets) & (set(after) - results)):
        if canonical_json_bytes(before[unchanged_id][1]) != canonical_json_bytes(
            after[unchanged_id][1]
        ):
            findings.append(
                _finding(
                    "UNSCOPED_INTERPRETATION_CHANGE",
                    f"untargeted interpretation {unchanged_id} changed",
                )
            )
    if len(targets) != len(results):
        findings.append(
            _finding("HUMAN_REVIEW_RESULT_COUNT_MISMATCH", "targets and results must be one-to-one")
        )
    if targets & results:
        findings.append(
            _finding("HUMAN_REVIEW_NOOP", "target and result IDs must materially differ")
        )
    action = str(event.get("action") or "")
    if action in {"accept", "reject"}:
        if any(not _FINDING_ID_RE.fullmatch(value) for value in targets | results):
            findings.append(
                _finding(
                    "HUMAN_REVIEW_TARGET_INVALID",
                    "accept/reject transitions may contain finding IDs only",
                )
            )
        expected_results: set[str] = set()
        for target_id in sorted(targets & set(before)):
            section_name, original = before[target_id]
            if section_name not in FINDING_SECTION_NAMES:
                continue
            expected = deepcopy(original)
            expected["review_status"] = "accepted" if action == "accept" else "rejected"
            expected["finding_id"] = finding_content_id(section_name, expected)
            expected_results.add(str(expected["finding_id"]))
            actual = after.get(str(expected["finding_id"]))
            if actual is None or canonical_json_bytes(actual[1]) != canonical_json_bytes(expected):
                findings.append(
                    _finding(
                        "HUMAN_REVIEW_TRANSITION_MISMATCH",
                        f"{target_id} contains changes beyond review_status",
                    )
                )
        if expected_results != results:
            findings.append(
                _finding(
                    "HUMAN_REVIEW_TRANSITION_MISMATCH",
                    "accept/reject result IDs do not match the declared action",
                )
            )
    elif action == "correct":
        previous_signatures: list[bytes] = []
        current_signatures: list[bytes] = []
        for target_id in sorted(targets & set(before)):
            section_name, item = before[target_id]
            material = deepcopy(item)
            if section_name in FINDING_SECTION_NAMES:
                for field in (
                    "finding_id",
                    "fact_refs",
                    "counterevidence_status",
                    "counterevidence_fact_refs",
                    "review_status",
                ):
                    material.pop(field, None)
            else:
                material.pop("option_id", None)
                material.pop("fact_refs", None)
            previous_signatures.append(canonical_json_bytes({"section": section_name, "item": material}))
        for result_id in sorted(results & set(after)):
            section_name, item = after[result_id]
            material = deepcopy(item)
            if section_name in FINDING_SECTION_NAMES:
                if material.get("review_status") != "revised":
                    findings.append(
                        _finding(
                            "HUMAN_REVIEW_TRANSITION_MISMATCH",
                            f"corrected finding {result_id} must be revised",
                        )
                    )
                for field in (
                    "finding_id",
                    "fact_refs",
                    "counterevidence_status",
                    "counterevidence_fact_refs",
                    "review_status",
                ):
                    material.pop(field, None)
            else:
                material.pop("option_id", None)
                material.pop("fact_refs", None)
            current_signatures.append(canonical_json_bytes({"section": section_name, "item": material}))
        if sorted(previous_signatures) != sorted(current_signatures):
            findings.append(
                _finding(
                    "HUMAN_REVIEW_TRANSITION_MISMATCH",
                    "correction changed fields outside the closed fact-link operation",
                )
            )
    return findings


def _validate_revision_chain_impl(
    artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate an entire append-only chain, including transition scope."""

    findings: list[dict[str, str]] = []
    if not artifacts:
        return _validation(
            [_finding("REVISION_CHAIN_EMPTY", "at least one revision is required")],
            schema_version=CHAIN_VALIDATION_SCHEMA_VERSION,
        )
    mapping_artifacts = [artifact for artifact in artifacts if isinstance(artifact, Mapping)]
    if len(mapping_artifacts) != len(artifacts):
        findings.append(_finding("REVISION_ARTIFACT_INVALID", "all revisions must be objects"))
    for artifact in mapping_artifacts:
        validation = validate_episode_review(artifact)
        if validation["validation_status"] == "blocked":
            codes = sorted({item["code"] for item in validation["findings"]})
            findings.append(
                _finding(
                    "REVISION_ARTIFACT_INVALID",
                    f"{artifact.get('content_id', '<unknown>')}: {', '.join(codes)}",
                )
            )
    ordered = sorted(
        mapping_artifacts,
        key=lambda artifact: (
            artifact.get("revision", {}).get("revision_no", -1)
            if isinstance(artifact.get("revision"), Mapping)
            and isinstance(artifact.get("revision", {}).get("revision_no"), int)
            else -1
        ),
    )
    revision_numbers = [
        artifact.get("revision", {}).get("revision_no")
        if isinstance(artifact.get("revision"), Mapping)
        else None
        for artifact in ordered
    ]
    if revision_numbers != list(range(1, len(ordered) + 1)):
        findings.append(
            _finding(
                "REVISION_NUMBER_SEQUENCE_INVALID",
                "revision numbers must be unique, sequential, and start at 1",
            )
        )
    content_ids = [str(artifact.get("content_id") or "") for artifact in ordered]
    if len(set(content_ids)) != len(content_ids):
        findings.append(_finding("REVISION_CONTENT_ID_DUPLICATE", "content IDs must be unique"))

    by_id = {str(artifact.get("content_id") or ""): artifact for artifact in ordered}
    for artifact in ordered:
        seen: set[str] = set()
        cursor = str(artifact.get("content_id") or "")
        while cursor in by_id:
            if cursor in seen:
                findings.append(_finding("REVISION_CHAIN_CYCLE", "supersedes graph contains a cycle"))
                break
            seen.add(cursor)
            revision = by_id[cursor].get("revision")
            if not isinstance(revision, Mapping):
                break
            next_id = revision.get("supersedes_content_id")
            if not isinstance(next_id, str):
                break
            cursor = next_id

    if ordered:
        root_revision = ordered[0].get("revision")
        if not isinstance(root_revision, Mapping) or root_revision.get("supersedes_content_id") is not None:
            findings.append(_finding("REVISION_ROOT_INVALID", "revision 1 cannot supersede another artifact"))
        root_review_id = ordered[0].get("review_id")
        root_input = ordered[0].get("input_bundle_ref")
        root_facts = ordered[0].get("fact_sections")
        root_warnings = ordered[0].get("warnings")
        for index, artifact in enumerate(ordered[1:], start=1):
            previous = ordered[index - 1]
            revision = artifact.get("revision")
            if not isinstance(revision, Mapping) or revision.get("supersedes_content_id") != previous.get(
                "content_id"
            ):
                findings.append(
                    _finding(
                        "SUPERSEDES_CHAIN_MISMATCH",
                        "each revision must supersede the immediately preceding content ID",
                    )
                )
            if artifact.get("review_id") != root_review_id or canonical_json_bytes(
                artifact.get("input_bundle_ref")
            ) != canonical_json_bytes(root_input):
                findings.append(
                    _finding("REVISION_BINDING_MISMATCH", "review/input binding changed across revisions")
                )
            if canonical_json_bytes(artifact.get("fact_sections")) != canonical_json_bytes(
                root_facts
            ):
                findings.append(_finding("REVISION_FACTS_CHANGED", "fact sections changed across revisions"))
            if canonical_json_bytes(artifact.get("warnings")) != canonical_json_bytes(root_warnings):
                findings.append(_finding("REVISION_WARNINGS_CHANGED", "warnings changed across revisions"))
            try:
                findings.extend(_chain_transition_findings(previous, artifact))
            except (ArtifactIOError, KeyError, TypeError) as exc:
                findings.append(_finding("REVISION_TRANSITION_INVALID", str(exc)))
    return _validation(findings, schema_version=CHAIN_VALIDATION_SCHEMA_VERSION)


def validate_revision_chain(
    artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate arbitrary revision-chain input and return findings without raising."""

    try:
        return _validate_revision_chain_impl(artifacts)
    except Exception as exc:
        return _validation(
            [_finding("MALFORMED_REVISION_CHAIN", str(exc))],
            schema_version=CHAIN_VALIDATION_SCHEMA_VERSION,
        )


def diff_episode_reviews(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, Any]:
    """Return a deterministic, source-aware diff between two valid revisions."""

    for label, artifact in (("before", before), ("after", after)):
        if validate_episode_review(artifact)["validation_status"] == "blocked":
            raise EpisodeRevisionError(f"{label} revision is invalid")
    if before.get("review_id") != after.get("review_id"):
        raise EpisodeRevisionError("cannot diff revisions from different reviews")
    if before["revision"]["revision_no"] >= after["revision"]["revision_no"]:
        raise EpisodeRevisionError("diff requires an earlier and a later revision")
    before_index = _interpretation_index(before)
    after_index = _interpretation_index(after)
    before_events = before["governance"]["human_reviews"]
    after_events = after["governance"]["human_reviews"]
    if after_events[: len(before_events)] != before_events:
        raise EpisodeRevisionError("human review history is not an append-only prefix")
    added_events = deepcopy(after_events[len(before_events) :])
    latest = added_events[-1] if added_events else None
    return {
        "schema_version": DIFF_SCHEMA_VERSION,
        "review_id": before.get("review_id"),
        "from_revision": deepcopy(before.get("revision")),
        "to_revision": deepcopy(after.get("revision")),
        "from_content_id": before.get("content_id"),
        "to_content_id": after.get("content_id"),
        "input_binding_unchanged": canonical_json_bytes(before.get("input_bundle_ref"))
        == canonical_json_bytes(after.get("input_bundle_ref")),
        "facts_unchanged": canonical_json_bytes(before.get("fact_sections"))
        == canonical_json_bytes(after.get("fact_sections")),
        "warnings_unchanged": canonical_json_bytes(before.get("warnings"))
        == canonical_json_bytes(after.get("warnings")),
        "removed_interpretation_ids": sorted(set(before_index) - set(after_index)),
        "added_interpretation_ids": sorted(set(after_index) - set(before_index)),
        "declared_target_ids": deepcopy(latest.get("target_ids", [])) if latest else [],
        "declared_result_target_ids": deepcopy(latest.get("result_target_ids", []))
        if latest
        else [],
        "human_review_events_added": added_events,
    }


def list_episode_review_revisions(
    artifacts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """List canonical stored and effective revision states."""

    validation = validate_revision_chain(artifacts)
    if validation["validation_status"] == "blocked":
        raise EpisodeRevisionError("refusing to list an invalid revision chain")
    ordered = sorted(artifacts, key=lambda value: value["revision"]["revision_no"])
    latest_no = ordered[-1]["revision"]["revision_no"]
    return [
        {
            "review_id": artifact["review_id"],
            "revision_no": artifact["revision"]["revision_no"],
            "stored_status": artifact["revision"]["status"],
            "effective_status": (
                "superseded"
                if artifact["revision"]["revision_no"] != latest_no
                else artifact["revision"]["status"]
            ),
            "content_id": artifact["content_id"],
            "supersedes_content_id": artifact["revision"]["supersedes_content_id"],
            "generation_mode": artifact["governance"]["generation_mode"],
            "human_review_event_count": len(artifact["governance"]["human_reviews"]),
        }
        for artifact in ordered
    ]


def query_episode_review_revision(
    artifacts: Sequence[Mapping[str, Any]],
    *,
    revision_no: int | None = None,
    content_id: str | None = None,
) -> dict[str, Any]:
    """Return one exact old or current revision from a validated chain."""

    if revision_no is not None and content_id is not None:
        raise EpisodeRevisionError("revision_no and content_id are mutually exclusive")
    validation = validate_revision_chain(artifacts)
    if validation["validation_status"] == "blocked":
        raise EpisodeRevisionError("refusing to query an invalid revision chain")
    ordered = sorted(artifacts, key=lambda value: value["revision"]["revision_no"])
    for artifact in ordered:
        if revision_no is not None and artifact["revision"]["revision_no"] != revision_no:
            continue
        if content_id is not None and artifact["content_id"] != content_id:
            continue
        if revision_no is None and content_id is None and artifact is not ordered[-1]:
            continue
        return deepcopy(dict(artifact))
    raise EpisodeRevisionError("requested episode-review revision was not found")


def save_new_episode_review(path: str | Path, artifact: Mapping[str, Any]) -> Path:
    """Create one validated revision file and refuse all overwrite attempts."""

    if validate_episode_review(artifact)["validation_status"] == "blocked":
        raise EpisodeRevisionError("refusing to save an invalid episode-review revision")
    try:
        return atomic_create_bytes(path, pretty_json_bytes(artifact))
    except (ArtifactIOError, OSError) as exc:
        raise EpisodeRevisionError(str(exc)) from exc


__all__ = [
    "CHAIN_VALIDATION_SCHEMA_VERSION",
    "DIFF_SCHEMA_VERSION",
    "REQUEST_SCHEMA_VERSION",
    "REQUEST_VALIDATION_SCHEMA_VERSION",
    "EpisodeRevisionError",
    "apply_human_review",
    "diff_episode_reviews",
    "list_episode_review_revisions",
    "load_human_review_request",
    "query_episode_review_revision",
    "revision_layer_findings",
    "save_new_episode_review",
    "validate_human_review_request",
    "validate_revision_chain",
]
