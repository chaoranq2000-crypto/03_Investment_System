"""Immutable, deterministic P2G-4 behavior-hypothesis adjudication.

The module consumes explicit P2G-3/P2G-4 JSON artifacts, one closed human
request, and the exact P2G-2 observation artifact.  It does not access a
database, network, model provider, current time, or mutable alias.
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

from . import behavior_hypotheses as p2g3
from .artifact_io import (
    ArtifactIOError,
    atomic_create_bytes,
    canonical_json_bytes,
    load_json_object,
    pretty_json_bytes,
)
from .behavior_observations import validate_behavior_observation_set


REQUEST_SCHEMA_VERSION = "p2g.behavior_hypothesis_review_request.v1"
REVISION_SCHEMA_VERSION = "p2g.behavior_hypothesis_revision.v1"
REQUEST_VALIDATION_SCHEMA_VERSION = (
    "p2g.behavior_hypothesis_review_request.validation.v1"
)
REVISION_VALIDATION_SCHEMA_VERSION = (
    "p2g.behavior_hypothesis_revision.validation.v1"
)
CHAIN_VALIDATION_SCHEMA_VERSION = (
    "p2g.behavior_hypothesis_revision_chain.validation.v1"
)
BUILDER_VERSION = "p2g.behavior_hypothesis_revision.builder.v1"
CANONICAL_SORT_VERSION = "p2g.behavior_hypothesis_revision_sort.v1"

_ROOT = Path(__file__).resolve().parents[2]
_REQUEST_SCHEMA_PATH = (
    _ROOT
    / "docs"
    / "contracts"
    / "P2G_4_BEHAVIOR_HYPOTHESIS_REVIEW_REQUEST.schema.json"
)
_REVISION_SCHEMA_PATH = (
    _ROOT
    / "docs"
    / "contracts"
    / "P2G_4_BEHAVIOR_HYPOTHESIS_REVISION.schema.json"
)

_CONTENT_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_REQUEST_ID_RE = re.compile(r"^review-request:[0-9a-f]{32}$")
_HYPOTHESIS_ID_RE = re.compile(r"^hypothesis:[0-9a-f]{32}$")
_EVENT_ID_RE = re.compile(r"^hypothesis-review-event:[0-9a-f]{32}$")

_PROPOSAL_FIELDS = (
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


class BehaviorHypothesisReviewError(ValueError):
    """Raised when P2G-4 input, transition, replay, or create-only I/O fails."""


def _value_content_id(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _content_id(value: Mapping[str, Any]) -> str:
    material = deepcopy(dict(value))
    material.pop("content_id", None)
    return _value_content_id(material)


def _stable_id(prefix: str, value: object) -> str:
    return f"{prefix}:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()[:32]


def _canonical_timestamp(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise BehaviorHypothesisReviewError(f"{field} must be a timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BehaviorHypothesisReviewError(f"invalid {field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.microsecond:
        raise BehaviorHypothesisReviewError(
            f"{field} must use timezone-aware whole seconds"
        )
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _canonical_text(value: object, field: str) -> str:
    try:
        normalized = p2g3._normalize_text(value, field)  # noqa: SLF001
    except Exception as exc:
        raise BehaviorHypothesisReviewError(str(exc)) from exc
    if normalized != value:
        raise BehaviorHypothesisReviewError(f"{field} must be canonical text")
    return normalized


@lru_cache(maxsize=2)
def _validator(path: str) -> Draft202012Validator:
    schema = json.loads(Path(path).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _request_validator() -> Draft202012Validator:
    return _validator(str(_REQUEST_SCHEMA_PATH))


def _revision_validator() -> Draft202012Validator:
    return _validator(str(_REVISION_SCHEMA_PATH))


def _json_path(parts: Iterable[object]) -> str:
    value = "$"
    for part in parts:
        value += f"[{part}]" if isinstance(part, int) else f".{part}"
    return value


def _finding(code: str, message: str) -> dict[str, str]:
    return {"severity": "blocker", "code": code, "message": message}


def _validation(
    findings: Iterable[Mapping[str, str]],
    *,
    schema_version: str,
    mode: str = "offline",
) -> dict[str, Any]:
    unique: dict[tuple[str, str, str], dict[str, str]] = {}
    for item in findings:
        row = {
            "severity": str(item.get("severity") or "blocker"),
            "code": str(item.get("code") or "UNKNOWN"),
            "message": str(item.get("message") or ""),
        }
        unique[(row["severity"], row["code"], row["message"])] = row
    rows = sorted(
        unique.values(),
        key=lambda item: (item["severity"], item["code"], item["message"]),
    )
    blockers = [item for item in rows if item["severity"] == "blocker"]
    return {
        "schema_version": schema_version,
        "validation_mode": mode,
        "validation_status": "blocked" if blockers else "accepted",
        "blocker_count": len(blockers),
        "finding_count": len(rows),
        "findings": rows,
    }


def _proposal(item: Mapping[str, Any]) -> dict[str, Any]:
    return {field: deepcopy(item.get(field)) for field in _PROPOSAL_FIELDS}


def _normalize_request(
    request: Mapping[str, Any], *, verify_request_id: bool
) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        raise BehaviorHypothesisReviewError("review request must be an object")
    canonical_json_bytes(request)
    schema_errors = sorted(
        _request_validator().iter_errors(request),
        key=lambda error: (_json_path(error.absolute_path), error.message),
    )
    if schema_errors:
        first = schema_errors[0]
        raise BehaviorHypothesisReviewError(
            f"request schema violation at {_json_path(first.absolute_path)}: {first.message}"
        )
    reviewed_at = _canonical_timestamp(request.get("reviewed_at"), "reviewed_at")
    if reviewed_at != request.get("reviewed_at"):
        raise BehaviorHypothesisReviewError("reviewed_at must use canonical UTC Z seconds")
    actor = _canonical_text(request.get("actor"), "actor")
    actions: list[dict[str, Any]] = []
    for index, raw in enumerate(request.get("actions", [])):
        if not isinstance(raw, Mapping):
            raise BehaviorHypothesisReviewError(f"actions[{index}] must be an object")
        action = str(raw.get("action") or "")
        replacement = raw.get("replacement")
        normalized_replacement = None
        if action == "correct":
            if not isinstance(replacement, Mapping):
                raise BehaviorHypothesisReviewError("correct requires a full replacement")
            try:
                normalized_replacement = p2g3._normalize_proposal(  # noqa: SLF001
                    replacement
                )
            except Exception as exc:
                raise BehaviorHypothesisReviewError(str(exc)) from exc
            if normalized_replacement != replacement:
                raise BehaviorHypothesisReviewError(
                    "correction replacement must already be canonical"
                )
        elif replacement is not None:
            raise BehaviorHypothesisReviewError("accept/reject replacement must be null")
        target = str(raw.get("target_hypothesis_id") or "")
        if not _HYPOTHESIS_ID_RE.fullmatch(target):
            raise BehaviorHypothesisReviewError("target_hypothesis_id is invalid")
        actions.append(
            {
                "target_hypothesis_id": target,
                "action": action,
                "reason": _canonical_text(raw.get("reason"), f"actions[{index}].reason"),
                "replacement": normalized_replacement,
            }
        )
    actions.sort(key=lambda item: item["target_hypothesis_id"])
    targets = [item["target_hypothesis_id"] for item in actions]
    if len(targets) != len(set(targets)):
        raise BehaviorHypothesisReviewError(
            "each target_hypothesis_id may appear only once per request"
        )
    normalized = {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "request_id": str(request.get("request_id") or ""),
        "expected_parent_content_id": str(
            request.get("expected_parent_content_id") or ""
        ),
        "actor": actor,
        "reviewed_at": reviewed_at,
        "actions": actions,
    }
    expected_id = behavior_hypothesis_review_request_id(normalized)
    if verify_request_id and normalized["request_id"] != expected_id:
        raise BehaviorHypothesisReviewError("request_id is not content-derived")
    return normalized


def behavior_hypothesis_review_request_id(request: Mapping[str, Any]) -> str:
    """Derive the request ID from a request whose fields are already canonical."""

    material = deepcopy(dict(request))
    material.pop("request_id", None)
    actions = material.get("actions")
    if isinstance(actions, list):
        material["actions"] = sorted(
            actions,
            key=lambda item: (
                str(item.get("target_hypothesis_id") or "")
                if isinstance(item, Mapping)
                else ""
            ),
        )
    return _stable_id("review-request", material)


def validate_behavior_hypothesis_review_request(
    request: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the closed request contract without raising."""

    findings: list[dict[str, str]] = []
    if not isinstance(request, Mapping):
        return _validation(
            [_finding("MALFORMED_REVIEW_REQUEST", "request must be an object")],
            schema_version=REQUEST_VALIDATION_SCHEMA_VERSION,
        )
    try:
        canonical_json_bytes(request)
    except Exception as exc:
        findings.append(_finding("NON_CANONICAL_REVIEW_REQUEST", str(exc)))
    try:
        for error in sorted(
            _request_validator().iter_errors(request),
            key=lambda item: (_json_path(item.absolute_path), item.message),
        ):
            findings.append(
                _finding(
                    "REVIEW_REQUEST_SCHEMA_INVALID",
                    f"{_json_path(error.absolute_path)}: {error.message}",
                )
            )
    except Exception as exc:
        findings.append(_finding("REVIEW_REQUEST_SCHEMA_FAILURE", str(exc)))
    try:
        _normalize_request(request, verify_request_id=True)
    except Exception as exc:
        findings.append(_finding("REVIEW_REQUEST_SEMANTIC_INVALID", str(exc)))
    return _validation(
        findings, schema_version=REQUEST_VALIDATION_SCHEMA_VERSION
    )


def load_behavior_hypothesis_review_request(path: str | Path) -> dict[str, Any]:
    try:
        return load_json_object(path)
    except (ArtifactIOError, OSError, ValueError) as exc:
        raise BehaviorHypothesisReviewError(str(exc)) from exc


def _event_id(event: Mapping[str, Any]) -> str:
    material = deepcopy(dict(event))
    material.pop("review_event_id", None)
    return _stable_id("hypothesis-review-event", material)


def _corrected_hypothesis_id(
    *,
    source_observation_content_id: str,
    lineage_root_hypothesis_id: str,
    supersedes_hypothesis_id: str,
    proposal: Mapping[str, Any],
) -> str:
    return _stable_id(
        "hypothesis",
        {
            "source_observation_content_id": source_observation_content_id,
            "lineage_root_hypothesis_id": lineage_root_hypothesis_id,
            "supersedes_hypothesis_id": supersedes_hypothesis_id,
            "proposal": deepcopy(dict(proposal)),
        },
    )


def _revision_chain_id(root_content_id: str) -> str:
    return _stable_id(
        "hypothesis-revision-chain",
        {
            "schema_version": REVISION_SCHEMA_VERSION,
            "root_hypothesis_set_content_id": root_content_id,
        },
    )


def _root_hypotheses(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in artifact.get("hypotheses", []):
        if not isinstance(raw, Mapping) or raw.get("supersedes_hypothesis_id") is not None:
            continue
        item = {
            "hypothesis_id": str(raw.get("hypothesis_id") or ""),
            "status": "proposed",
            **_proposal(raw),
            "warning_codes": deepcopy(raw.get("warning_codes")),
            "guardrail_flags": deepcopy(raw.get("guardrail_flags")),
        }
        result.append(item)
    return sorted(result, key=lambda item: item["hypothesis_id"])


def _root_projection(artifact: Mapping[str, Any]) -> dict[str, Any]:
    roots = _root_hypotheses(artifact)
    referenced = {
        str(ref)
        for item in roots
        for ref in [
            *item.get("evaluation_refs", []),
            *item.get("counterevidence_evaluation_refs", []),
        ]
    }
    inventory = [
        deepcopy(dict(item))
        for item in artifact.get("evaluation_inventory", [])
        if isinstance(item, Mapping) and str(item.get("evaluation_id") or "") in referenced
    ]
    source = artifact.get("source_hypothesis_set")
    source = source if isinstance(source, Mapping) else {}
    source_observation = artifact.get("source_observation_set")
    source_observation = (
        deepcopy(dict(source_observation))
        if isinstance(source_observation, Mapping)
        else {}
    )
    root: dict[str, Any] = {
        "schema_version": p2g3.SCHEMA_VERSION,
        "artifact_type": "behavior_hypothesis_candidate_set",
        "content_id": str(source.get("content_id") or ""),
        "hypothesis_set_id": str(source.get("hypothesis_set_id") or ""),
        "source_observation_set": source_observation,
        "evaluation_inventory": sorted(
            inventory, key=lambda item: str(item.get("evaluation_id") or "")
        ),
        "model_provenance": deepcopy(artifact.get("model_provenance")),
        "hypotheses": roots,
        "warnings": sorted(
            {
                str(warning)
                for item in roots
                for warning in item.get("warning_codes", [])
            }
        ),
        "release_readiness": {"status": "ready", "blocker_codes": []},
        "source_verification": {
            "status": "verified",
            "validation_mode": "validated_p2g2_observation_set",
            "verified_content_id": str(source_observation.get("content_id") or ""),
        },
        "canonicalization": {
            "builder_version": p2g3.BUILDER_VERSION,
            "canonical_json": "utf8_nfc_sorted_keys_compact_no_float",
            "content_hash": "sha256",
            "sort_version": p2g3.CANONICAL_SORT_VERSION,
        },
    }
    return root


def _initial_state(source: Mapping[str, Any]) -> dict[str, Any]:
    roots = []
    for raw in source.get("hypotheses", []):
        if not isinstance(raw, Mapping):
            continue
        hypothesis_id = str(raw.get("hypothesis_id") or "")
        roots.append(
            {
                "hypothesis_id": hypothesis_id,
                "lineage_root_hypothesis_id": hypothesis_id,
                "supersedes_hypothesis_id": None,
                "status": "proposed",
                **_proposal(raw),
                "warning_codes": deepcopy(raw.get("warning_codes")),
                "guardrail_flags": deepcopy(raw.get("guardrail_flags")),
            }
        )
    source_content_id = str(source.get("content_id") or "")
    return {
        "root_content_id": source_content_id,
        "revision_no": 0,
        "source_hypothesis_set": {
            "schema_version": p2g3.SCHEMA_VERSION,
            "hypothesis_set_id": str(source.get("hypothesis_set_id") or ""),
            "content_id": source_content_id,
        },
        "source_observation_set": deepcopy(source.get("source_observation_set")),
        "evaluation_inventory": deepcopy(source.get("evaluation_inventory")),
        "model_provenance": deepcopy(source.get("model_provenance")),
        "hypotheses": sorted(roots, key=lambda item: item["hypothesis_id"]),
        "review_events": [],
    }


def _existing_state(source: Mapping[str, Any]) -> dict[str, Any]:
    revision = source.get("revision")
    if not isinstance(revision, Mapping):
        raise BehaviorHypothesisReviewError("revision metadata is missing")
    return {
        "root_content_id": str(revision.get("root_hypothesis_set_content_id") or ""),
        "revision_no": int(revision.get("revision_no") or 0),
        "source_hypothesis_set": deepcopy(source.get("source_hypothesis_set")),
        "source_observation_set": deepcopy(source.get("source_observation_set")),
        "evaluation_inventory": deepcopy(source.get("evaluation_inventory")),
        "model_provenance": deepcopy(source.get("model_provenance")),
        "hypotheses": deepcopy(source.get("hypotheses")),
        "review_events": deepcopy(source.get("review_events")),
    }


def _source_state_or_raise(
    source: Mapping[str, Any], observation_artifact: Mapping[str, Any]
) -> dict[str, Any]:
    schema_version = source.get("schema_version")
    if schema_version == p2g3.SCHEMA_VERSION:
        replay = p2g3.replay_validate_behavior_hypothesis_set(
            source, observation_artifact=observation_artifact
        )
        if replay.get("validation_status") != "accepted":
            raise BehaviorHypothesisReviewError(
                "P2G-3 source failed validation or source replay"
            )
        return _initial_state(source)
    if schema_version == REVISION_SCHEMA_VERSION:
        replay = replay_validate_behavior_hypothesis_revision(
            source, observation_artifact=observation_artifact
        )
        if replay.get("validation_status") != "accepted":
            raise BehaviorHypothesisReviewError(
                "P2G-4 source failed validation or source replay"
            )
        return _existing_state(source)
    raise BehaviorHypothesisReviewError("source must be a P2G-3 set or P2G-4 revision")


def _observation_index(
    observation_artifact: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    return {
        str(item.get("evaluation_id") or ""): item
        for item in observation_artifact.get("evaluations", [])
        if isinstance(item, Mapping) and str(item.get("evaluation_id") or "")
    }


def _compile_replacement(
    replacement: Mapping[str, Any],
    *,
    observation_artifact: Mapping[str, Any],
) -> dict[str, Any]:
    source_scope = p2g3._source_temporal_scope(  # noqa: SLF001
        observation_artifact.get("scope")
    )
    compiled = p2g3._compile_hypotheses(  # noqa: SLF001
        [replacement],
        source_content_id=str(observation_artifact.get("content_id") or ""),
        evaluation_index=_observation_index(observation_artifact),
        source_scope=source_scope,
    )
    if len(compiled) != 1:
        raise BehaviorHypothesisReviewError("correction did not produce one hypothesis")
    return compiled[0]


def _latest_provenance_time(state: Mapping[str, Any]) -> str:
    events = state.get("review_events")
    if isinstance(events, list) and events:
        last = max(
            (item for item in events if isinstance(item, Mapping)),
            key=lambda item: (
                str(item.get("reviewed_at") or ""),
                str(item.get("review_event_id") or ""),
            ),
        )
        return str(last.get("reviewed_at") or "")
    model = state.get("model_provenance")
    if isinstance(model, Mapping):
        return str(model.get("generated_at") or "")
    return ""


def _inventory_for_hypotheses(
    hypotheses: Sequence[Mapping[str, Any]],
    *,
    observation_artifact: Mapping[str, Any],
) -> list[dict[str, Any]]:
    referenced = sorted(
        {
            str(ref)
            for item in hypotheses
            for ref in [
                *item.get("evaluation_refs", []),
                *item.get("counterevidence_evaluation_refs", []),
            ]
        }
    )
    source_index = _observation_index(observation_artifact)
    missing = sorted(set(referenced) - set(source_index))
    if missing:
        raise BehaviorHypothesisReviewError(
            "revision references unknown evaluations: " + ", ".join(missing)
        )
    return [p2g3._inventory_item(source_index[item]) for item in referenced]  # noqa: SLF001


def apply_behavior_hypothesis_review(
    source: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    observation_artifact: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply one all-or-nothing review request and return an immutable revision."""

    if not isinstance(source, Mapping) or not isinstance(observation_artifact, Mapping):
        raise BehaviorHypothesisReviewError("source and observation artifact must be objects")
    source_bytes = canonical_json_bytes(source)
    observation_bytes = canonical_json_bytes(observation_artifact)
    normalized_request = _normalize_request(request, verify_request_id=True)
    parent_content_id = str(source.get("content_id") or "")
    if normalized_request["expected_parent_content_id"] != parent_content_id:
        raise BehaviorHypothesisReviewError("stale expected_parent_content_id")
    state = _source_state_or_raise(source, observation_artifact)
    reviewed_at = normalized_request["reviewed_at"]
    prior_time = _latest_provenance_time(state)
    if prior_time:
        canonical_prior = _canonical_timestamp(prior_time, "prior provenance time")
        if reviewed_at < canonical_prior:
            raise BehaviorHypothesisReviewError(
                "reviewed_at cannot precede model or review provenance"
            )
        if state["review_events"] and reviewed_at == canonical_prior:
            raise BehaviorHypothesisReviewError(
                "a later review request must use a later reviewed_at second"
            )

    hypotheses = [deepcopy(dict(item)) for item in state["hypotheses"]]
    by_id = {str(item.get("hypothesis_id") or ""): item for item in hypotheses}
    unknown = sorted(
        {
            action["target_hypothesis_id"]
            for action in normalized_request["actions"]
        }
        - set(by_id)
    )
    if unknown:
        raise BehaviorHypothesisReviewError(
            "review targets unknown hypotheses: " + ", ".join(unknown)
        )

    compiled_replacements: dict[str, dict[str, Any]] = {}
    for action in normalized_request["actions"]:
        target_id = action["target_hypothesis_id"]
        target = by_id[target_id]
        status = str(target.get("status") or "")
        if status == "superseded":
            raise BehaviorHypothesisReviewError("superseded hypotheses are terminal")
        if action["action"] in {"accept", "reject"} and status != "proposed":
            raise BehaviorHypothesisReviewError(
                "accept/reject may target proposed hypotheses only"
            )
        if action["action"] == "correct":
            compiled = _compile_replacement(
                action["replacement"], observation_artifact=observation_artifact
            )
            compiled_replacements[target_id] = compiled

    events = [deepcopy(dict(item)) for item in state["review_events"]]
    source_observation_id = str(observation_artifact.get("content_id") or "")
    for action in normalized_request["actions"]:
        target_id = action["target_hypothesis_id"]
        target = by_id[target_id]
        status_before = str(target["status"])
        action_name = action["action"]
        if action_name == "accept":
            target["status"] = "accepted"
            result_id = target_id
            target_after = "accepted"
            result_status = "accepted"
        elif action_name == "reject":
            target["status"] = "rejected"
            result_id = target_id
            target_after = "rejected"
            result_status = "rejected"
        else:
            compiled = compiled_replacements[target_id]
            lineage_root = str(target["lineage_root_hypothesis_id"])
            result_id = _corrected_hypothesis_id(
                source_observation_content_id=source_observation_id,
                lineage_root_hypothesis_id=lineage_root,
                supersedes_hypothesis_id=target_id,
                proposal=_proposal(compiled),
            )
            if result_id in by_id:
                raise BehaviorHypothesisReviewError(
                    "correction must produce a new hypothesis ID"
                )
            target["status"] = "superseded"
            revised = {
                "hypothesis_id": result_id,
                "lineage_root_hypothesis_id": lineage_root,
                "supersedes_hypothesis_id": target_id,
                "status": "proposed",
                **_proposal(compiled),
                "warning_codes": deepcopy(compiled["warning_codes"]),
                "guardrail_flags": [],
            }
            hypotheses.append(revised)
            by_id[result_id] = revised
            target_after = "superseded"
            result_status = "proposed"
        event: dict[str, Any] = {
            "review_event_id": "",
            "request_id": normalized_request["request_id"],
            "actor": normalized_request["actor"],
            "reviewed_at": reviewed_at,
            "action": action_name,
            "reason": action["reason"],
            "target_hypothesis_id": target_id,
            "result_hypothesis_id": result_id,
            "target_status_before": status_before,
            "target_status_after": target_after,
            "result_status": result_status,
        }
        event["review_event_id"] = _event_id(event)
        events.append(event)

    hypotheses.sort(key=lambda item: str(item["hypothesis_id"]))
    events.sort(
        key=lambda item: (str(item["reviewed_at"]), str(item["review_event_id"]))
    )
    inventory = _inventory_for_hypotheses(
        hypotheses, observation_artifact=observation_artifact
    )
    root_content_id = str(state["root_content_id"])
    candidate: dict[str, Any] = {
        "schema_version": REVISION_SCHEMA_VERSION,
        "artifact_type": "behavior_hypothesis_revision",
        "content_id": "",
        "revision_chain_id": _revision_chain_id(root_content_id),
        "revision": {
            "revision_no": int(state["revision_no"]) + 1,
            "parent_content_id": parent_content_id,
            "root_hypothesis_set_content_id": root_content_id,
            "request_id": normalized_request["request_id"],
        },
        "source_hypothesis_set": deepcopy(state["source_hypothesis_set"]),
        "source_observation_set": deepcopy(state["source_observation_set"]),
        "evaluation_inventory": inventory,
        "model_provenance": deepcopy(state["model_provenance"]),
        "hypotheses": hypotheses,
        "review_events": events,
        "warnings": sorted(
            {
                str(warning)
                for item in hypotheses
                for warning in item.get("warning_codes", [])
            }
        ),
        "release_readiness": {"status": "ready", "blocker_codes": []},
        "source_verification": {
            "status": "verified",
            "validation_mode": "p2g3_source_replay",
            "verified_content_id": source_observation_id,
        },
        "canonicalization": {
            "builder_version": BUILDER_VERSION,
            "canonical_json": "utf8_nfc_sorted_keys_compact_no_float",
            "content_hash": "sha256",
            "sort_version": CANONICAL_SORT_VERSION,
        },
    }
    candidate["content_id"] = _content_id(candidate)
    replay = replay_validate_behavior_hypothesis_revision(
        candidate, observation_artifact=observation_artifact
    )
    if replay["validation_status"] != "accepted":
        codes = sorted({item["code"] for item in replay["findings"]})
        raise BehaviorHypothesisReviewError(
            "built revision failed validation: " + ", ".join(codes)
        )
    if canonical_json_bytes(source) != source_bytes:
        raise BehaviorHypothesisReviewError("source artifact was mutated")
    if canonical_json_bytes(observation_artifact) != observation_bytes:
        raise BehaviorHypothesisReviewError("observation artifact was mutated")
    return candidate


def _latest_request_from_revision(artifact: Mapping[str, Any]) -> dict[str, Any]:
    revision = artifact.get("revision")
    if not isinstance(revision, Mapping):
        raise BehaviorHypothesisReviewError("revision metadata is missing")
    request_id = str(revision.get("request_id") or "")
    events = [
        item
        for item in artifact.get("review_events", [])
        if isinstance(item, Mapping) and item.get("request_id") == request_id
    ]
    if not events:
        raise BehaviorHypothesisReviewError("latest request has no review events")
    actors = {str(item.get("actor") or "") for item in events}
    times = {str(item.get("reviewed_at") or "") for item in events}
    if len(actors) != 1 or len(times) != 1:
        raise BehaviorHypothesisReviewError(
            "all events in one request must share actor and reviewed_at"
        )
    hypothesis_index = {
        str(item.get("hypothesis_id") or ""): item
        for item in artifact.get("hypotheses", [])
        if isinstance(item, Mapping)
    }
    actions = []
    for event in events:
        action = str(event.get("action") or "")
        replacement = None
        if action == "correct":
            result = hypothesis_index.get(str(event.get("result_hypothesis_id") or ""))
            if result is None:
                raise BehaviorHypothesisReviewError("correction result is missing")
            replacement = _proposal(result)
        actions.append(
            {
                "target_hypothesis_id": str(
                    event.get("target_hypothesis_id") or ""
                ),
                "action": action,
                "reason": str(event.get("reason") or ""),
                "replacement": replacement,
            }
        )
    actions.sort(key=lambda item: item["target_hypothesis_id"])
    return {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "request_id": request_id,
        "expected_parent_content_id": str(revision.get("parent_content_id") or ""),
        "actor": next(iter(actors)),
        "reviewed_at": next(iter(times)),
        "actions": actions,
    }


def _semantic_hypothesis_findings(
    artifact: Mapping[str, Any]
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    source_observation = artifact.get("source_observation_set")
    source_observation = source_observation if isinstance(source_observation, Mapping) else {}
    source_observation_id = str(source_observation.get("content_id") or "")
    try:
        source_scope = p2g3._source_temporal_scope(  # noqa: SLF001
            source_observation.get("temporal_scope")
        )
    except Exception as exc:
        source_scope = None
        findings.append(_finding("SOURCE_TEMPORAL_SCOPE_INVALID", str(exc)))
    inventory = artifact.get("evaluation_inventory")
    inventory = inventory if isinstance(inventory, list) else []
    inventory_index: dict[str, Mapping[str, Any]] = {}
    mapping_inventory = [item for item in inventory if isinstance(item, Mapping)]
    if mapping_inventory != sorted(
        mapping_inventory, key=lambda item: str(item.get("evaluation_id") or "")
    ):
        findings.append(_finding("EVALUATION_INVENTORY_ORDER_INVALID", "inventory is not sorted"))
    for item in mapping_inventory:
        evaluation_id = str(item.get("evaluation_id") or "")
        if evaluation_id in inventory_index:
            findings.append(_finding("EVALUATION_INVENTORY_DUPLICATE", evaluation_id))
        inventory_index[evaluation_id] = item

    hypotheses = artifact.get("hypotheses")
    hypotheses = hypotheses if isinstance(hypotheses, list) else []
    mapping_hypotheses = [item for item in hypotheses if isinstance(item, Mapping)]
    if mapping_hypotheses != sorted(
        mapping_hypotheses, key=lambda item: str(item.get("hypothesis_id") or "")
    ):
        findings.append(_finding("HYPOTHESIS_ORDER_INVALID", "hypotheses are not sorted"))
    by_id: dict[str, Mapping[str, Any]] = {}
    used_refs: set[str] = set()
    expected_warnings: set[str] = set()
    for item in mapping_hypotheses:
        hypothesis_id = str(item.get("hypothesis_id") or "")
        if hypothesis_id in by_id:
            findings.append(_finding("DUPLICATE_HYPOTHESIS_ID", hypothesis_id))
        by_id[hypothesis_id] = item
        if not _HYPOTHESIS_ID_RE.fullmatch(hypothesis_id):
            findings.append(_finding("HYPOTHESIS_ID_INVALID", hypothesis_id))
        try:
            normalized = p2g3._normalize_proposal(_proposal(item))  # noqa: SLF001
        except Exception as exc:
            findings.append(_finding("HYPOTHESIS_CANONICALIZATION_INVALID", str(exc)))
            normalized = None
        else:
            if normalized != _proposal(item):
                findings.append(_finding("HYPOTHESIS_CANONICALIZATION_INVALID", hypothesis_id))
        support = item.get("evaluation_refs")
        counter = item.get("counterevidence_evaluation_refs")
        support = support if isinstance(support, list) else []
        counter = counter if isinstance(counter, list) else []
        used_refs.update(str(ref) for ref in [*support, *counter])
        unknown = sorted(set([*support, *counter]) - set(inventory_index))
        if unknown:
            findings.append(_finding("EVALUATION_REF_UNKNOWN", f"{hypothesis_id}: {unknown}"))
        non_observed = [
            ref
            for ref in support
            if ref in inventory_index and inventory_index[ref].get("status") != "observed"
        ]
        if non_observed:
            findings.append(
                _finding("SUPPORT_EVALUATION_NOT_OBSERVED", f"{hypothesis_id}: {non_observed}")
            )
        if set(support) & set(counter):
            findings.append(_finding("SUPPORT_COUNTEREVIDENCE_OVERLAP", hypothesis_id))
        if not counter and not item.get("counterevidence_search"):
            findings.append(_finding("COUNTEREVIDENCE_REQUIRED", hypothesis_id))
        expected_episodes = sorted(
            {
                str(episode_id)
                for ref in support
                if ref in inventory_index
                for episode_id in inventory_index[ref].get("episode_ids", [])
            }
        )
        scope = item.get("scope")
        scope_episodes = scope.get("episode_ids") if isinstance(scope, Mapping) else []
        if scope_episodes != expected_episodes:
            findings.append(_finding("SCOPE_EPISODE_MISMATCH", hypothesis_id))
        if source_scope is not None and isinstance(scope, Mapping):
            try:
                if p2g3._scope_outside_source(scope, source_scope):  # noqa: SLF001
                    findings.append(_finding("TEMPORAL_SCOPE_OUTSIDE_SOURCE", hypothesis_id))
            except Exception as exc:
                findings.append(_finding("HYPOTHESIS_CANONICALIZATION_INVALID", str(exc)))
        warnings = ["insufficient_repeat_evidence"] if len(expected_episodes) < 2 else []
        if item.get("warning_codes") != warnings:
            findings.append(_finding("HYPOTHESIS_WARNING_MISMATCH", hypothesis_id))
        expected_warnings.update(warnings)
        if len(expected_episodes) < 2 and p2g3._claims_repeat_without_limit(  # noqa: SLF001
            str(item.get("statement") or "")
        ):
            findings.append(_finding("INSUFFICIENT_REPEAT_CLAIM", hypothesis_id))
        for code in sorted(p2g3._p2g_policy_codes(_proposal(item))):  # noqa: SLF001
            findings.append(_finding(code, hypothesis_id))
        supersedes = item.get("supersedes_hypothesis_id")
        lineage_root = str(item.get("lineage_root_hypothesis_id") or "")
        if supersedes is None:
            expected_id = p2g3._hypothesis_id(  # noqa: SLF001
                source_observation_id, {**_proposal(item), "status": "proposed"}
            )
            if hypothesis_id != expected_id or lineage_root != hypothesis_id:
                findings.append(_finding("ROOT_HYPOTHESIS_ID_MISMATCH", hypothesis_id))
        elif normalized is not None:
            expected_id = _corrected_hypothesis_id(
                source_observation_content_id=source_observation_id,
                lineage_root_hypothesis_id=lineage_root,
                supersedes_hypothesis_id=str(supersedes),
                proposal=normalized,
            )
            if hypothesis_id != expected_id:
                findings.append(_finding("CORRECTED_HYPOTHESIS_ID_MISMATCH", hypothesis_id))
    if set(inventory_index) != used_refs:
        findings.append(
            _finding(
                "EVALUATION_INVENTORY_SCOPE_MISMATCH",
                "inventory must equal all referenced evaluations",
            )
        )
    if artifact.get("warnings") != sorted(expected_warnings):
        findings.append(_finding("WARNINGS_MISMATCH", "top-level warnings are inconsistent"))

    child_by_parent: dict[str, list[str]] = {}
    for hypothesis_id, item in by_id.items():
        parent = item.get("supersedes_hypothesis_id")
        if parent is not None:
            child_by_parent.setdefault(str(parent), []).append(hypothesis_id)
            parent_item = by_id.get(str(parent))
            if parent_item is None:
                findings.append(_finding("HYPOTHESIS_LINEAGE_BROKEN", hypothesis_id))
            elif item.get("lineage_root_hypothesis_id") != parent_item.get(
                "lineage_root_hypothesis_id"
            ):
                findings.append(_finding("HYPOTHESIS_LINEAGE_ROOT_MISMATCH", hypothesis_id))
    for parent, children in child_by_parent.items():
        if len(children) != 1:
            findings.append(_finding("HYPOTHESIS_LINEAGE_FORK", parent))
        if parent in by_id and by_id[parent].get("status") != "superseded":
            findings.append(_finding("HYPOTHESIS_SUPERSEDED_STATUS_MISMATCH", parent))
    for hypothesis_id, item in by_id.items():
        if item.get("status") == "superseded" and hypothesis_id not in child_by_parent:
            findings.append(_finding("HYPOTHESIS_LINEAGE_BROKEN", hypothesis_id))
        seen: set[str] = set()
        cursor = hypothesis_id
        while cursor in by_id:
            if cursor in seen:
                findings.append(_finding("HYPOTHESIS_LINEAGE_CYCLE", hypothesis_id))
                break
            seen.add(cursor)
            parent = by_id[cursor].get("supersedes_hypothesis_id")
            if parent is None:
                break
            cursor = str(parent)
    return findings


def _event_history_findings(artifact: Mapping[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    hypotheses = {
        str(item.get("hypothesis_id") or ""): item
        for item in artifact.get("hypotheses", [])
        if isinstance(item, Mapping)
    }
    statuses = {
        hypothesis_id: "proposed"
        for hypothesis_id, item in hypotheses.items()
        if item.get("supersedes_hypothesis_id") is None
    }
    expected_ids = set(statuses)
    events = artifact.get("review_events")
    events = events if isinstance(events, list) else []
    mapping_events = [item for item in events if isinstance(item, Mapping)]
    canonical_events = sorted(
        mapping_events,
        key=lambda item: (
            str(item.get("reviewed_at") or ""),
            str(item.get("review_event_id") or ""),
        ),
    )
    if mapping_events != canonical_events:
        findings.append(_finding("REVIEW_EVENT_ORDER_INVALID", "events are not canonical"))
    seen_events: set[str] = set()
    seen_request_order: list[str] = []
    for event in mapping_events:
        event_id = str(event.get("review_event_id") or "")
        if (
            not _EVENT_ID_RE.fullmatch(event_id)
            or event_id != _event_id(event)
            or event_id in seen_events
        ):
            findings.append(_finding("REVIEW_EVENT_ID_MISMATCH", event_id))
        seen_events.add(event_id)
        request_id = str(event.get("request_id") or "")
        if request_id not in seen_request_order:
            seen_request_order.append(request_id)
        target = str(event.get("target_hypothesis_id") or "")
        result = str(event.get("result_hypothesis_id") or "")
        current = statuses.get(target)
        if current is None or current != event.get("target_status_before"):
            findings.append(_finding("REVIEW_EVENT_STATE_MISMATCH", event_id))
            continue
        action = event.get("action")
        if action in {"accept", "reject"}:
            expected_status = "accepted" if action == "accept" else "rejected"
            if (
                current != "proposed"
                or result != target
                or event.get("target_status_after") != expected_status
                or event.get("result_status") != expected_status
            ):
                findings.append(_finding("REVIEW_EVENT_TRANSITION_INVALID", event_id))
            statuses[target] = expected_status
        elif action == "correct":
            result_item = hypotheses.get(result)
            if (
                current == "superseded"
                or result == target
                or result_item is None
                or result_item.get("supersedes_hypothesis_id") != target
                or event.get("target_status_after") != "superseded"
                or event.get("result_status") != "proposed"
                or result in statuses
            ):
                findings.append(_finding("REVIEW_EVENT_TRANSITION_INVALID", event_id))
            statuses[target] = "superseded"
            statuses[result] = "proposed"
            expected_ids.add(result)
        else:
            findings.append(_finding("REVIEW_EVENT_ACTION_INVALID", event_id))
    if expected_ids != set(hypotheses):
        findings.append(
            _finding(
                "REVIEW_EVENT_HYPOTHESIS_SET_MISMATCH",
                "event results do not match hypotheses",
            )
        )
    for hypothesis_id, expected_status in statuses.items():
        if hypotheses.get(hypothesis_id, {}).get("status") != expected_status:
            findings.append(_finding("REVIEW_EVENT_FINAL_STATUS_MISMATCH", hypothesis_id))
    revision = artifact.get("revision")
    revision = revision if isinstance(revision, Mapping) else {}
    revision_no = revision.get("revision_no")
    if revision_no != len(seen_request_order):
        findings.append(
            _finding(
                "REVISION_REQUEST_COUNT_MISMATCH",
                "revision_no must equal request count",
            )
        )
    if seen_request_order and revision.get("request_id") != seen_request_order[-1]:
        findings.append(_finding("REVISION_REQUEST_ID_MISMATCH", "latest request ID mismatch"))
    try:
        latest_request = _latest_request_from_revision(artifact)
        request_validation = validate_behavior_hypothesis_review_request(latest_request)
        if request_validation["validation_status"] == "blocked":
            findings.append(
                _finding(
                    "LATEST_REVIEW_REQUEST_INVALID",
                    "latest request cannot be reconstructed",
                )
            )
    except Exception as exc:
        findings.append(_finding("LATEST_REVIEW_REQUEST_INVALID", str(exc)))
    return findings


def _validate_revision_impl(artifact: Mapping[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    try:
        canonical_json_bytes(artifact)
    except Exception as exc:
        return _validation(
            [_finding("NON_CANONICAL_REVISION", str(exc))],
            schema_version=REVISION_VALIDATION_SCHEMA_VERSION,
        )
    for error in sorted(
        _revision_validator().iter_errors(artifact),
        key=lambda item: (_json_path(item.absolute_path), item.message),
    ):
        findings.append(
            _finding(
                "REVISION_SCHEMA_INVALID",
                f"{_json_path(error.absolute_path)}: {error.message}",
            )
        )
    if artifact.get("schema_version") != REVISION_SCHEMA_VERSION:
        findings.append(_finding("REVISION_SCHEMA_VERSION_MISMATCH", "unsupported schema"))
    try:
        expected_content_id = _content_id(artifact)
    except Exception:
        expected_content_id = ""
    if artifact.get("content_id") != expected_content_id:
        findings.append(_finding("REVISION_CONTENT_ID_MISMATCH", "content_id is not canonical"))
    revision = artifact.get("revision")
    revision = revision if isinstance(revision, Mapping) else {}
    root_content_id = str(revision.get("root_hypothesis_set_content_id") or "")
    source = artifact.get("source_hypothesis_set")
    source = source if isinstance(source, Mapping) else {}
    if source.get("content_id") != root_content_id:
        findings.append(_finding("ROOT_SOURCE_BINDING_MISMATCH", "root content ID differs"))
    if artifact.get("revision_chain_id") != _revision_chain_id(root_content_id):
        findings.append(_finding("REVISION_CHAIN_ID_MISMATCH", "chain ID is not canonical"))
    if revision.get("revision_no") == 1 and revision.get("parent_content_id") != root_content_id:
        findings.append(
            _finding(
                "REVISION_PARENT_MISMATCH",
                "revision 1 must parent the P2G-3 root",
            )
        )
    try:
        root = _root_projection(artifact)
        root_validation = p2g3.validate_behavior_hypothesis_set(root)
        if root_validation["validation_status"] == "blocked":
            codes = sorted({item["code"] for item in root_validation["findings"]})
            findings.append(_finding("ROOT_HYPOTHESIS_SET_INVALID", ", ".join(codes)))
    except Exception as exc:
        findings.append(_finding("ROOT_HYPOTHESIS_SET_INVALID", str(exc)))
    findings.extend(_semantic_hypothesis_findings(artifact))
    findings.extend(_event_history_findings(artifact))
    source_observation = artifact.get("source_observation_set")
    source_observation = source_observation if isinstance(source_observation, Mapping) else {}
    source_observation_id = str(source_observation.get("content_id") or "")
    if artifact.get("source_verification") != {
        "status": "verified",
        "validation_mode": "p2g3_source_replay",
        "verified_content_id": source_observation_id,
    }:
        findings.append(_finding("SOURCE_VERIFICATION_MISMATCH", "source replay metadata differs"))
    if artifact.get("release_readiness") != {"status": "ready", "blocker_codes": []}:
        findings.append(_finding("RELEASE_READINESS_MISMATCH", "release must be ready"))
    if artifact.get("canonicalization") != {
        "builder_version": BUILDER_VERSION,
        "canonical_json": "utf8_nfc_sorted_keys_compact_no_float",
        "content_hash": "sha256",
        "sort_version": CANONICAL_SORT_VERSION,
    }:
        findings.append(_finding("CANONICALIZATION_MISMATCH", "metadata differs"))
    return _validation(
        findings, schema_version=REVISION_VALIDATION_SCHEMA_VERSION
    )


def validate_behavior_hypothesis_revision(
    artifact: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate arbitrary P2G-4 JSON-like input without raising."""

    if not isinstance(artifact, Mapping):
        return _validation(
            [_finding("MALFORMED_REVISION", "revision must be an object")],
            schema_version=REVISION_VALIDATION_SCHEMA_VERSION,
        )
    try:
        return _validate_revision_impl(artifact)
    except Exception as exc:
        return _validation(
            [_finding("MALFORMED_REVISION", str(exc))],
            schema_version=REVISION_VALIDATION_SCHEMA_VERSION,
        )


def replay_validate_behavior_hypothesis_revision(
    artifact: Mapping[str, Any],
    *,
    observation_artifact: Mapping[str, Any],
) -> dict[str, Any]:
    """Replay the root P2G-3 source and every evaluation/hypothesis binding."""

    offline = validate_behavior_hypothesis_revision(artifact)
    findings = list(offline["findings"])
    observation_validation = validate_behavior_observation_set(observation_artifact)
    source_observation = artifact.get("source_observation_set")
    source_observation = source_observation if isinstance(source_observation, Mapping) else {}
    expected_source_id = str(source_observation.get("content_id") or "")
    actual_source_id = str(observation_artifact.get("content_id") or "")
    if (
        observation_validation.get("validation_status") == "blocked"
        or (observation_artifact.get("release_readiness") or {}).get("status") != "ready"
        or (observation_artifact.get("source_verification") or {}).get("status") != "verified"
    ):
        findings.append(_finding("SOURCE_REPLAY_ERROR", "P2G-2 source is not valid/ready/verified"))
    if expected_source_id != actual_source_id:
        findings.append(_finding("SOURCE_REPLAY_MISMATCH", "observation content ID differs"))
    if source_observation.get("observation_set_id") != observation_artifact.get(
        "observation_set_id"
    ):
        findings.append(_finding("SOURCE_REPLAY_MISMATCH", "observation set ID differs"))
    if source_observation.get("temporal_scope") != observation_artifact.get("scope"):
        findings.append(_finding("SOURCE_REPLAY_MISMATCH", "observation scope differs"))
    try:
        root = _root_projection(artifact)
        root_replay = p2g3.replay_validate_behavior_hypothesis_set(
            root, observation_artifact=observation_artifact
        )
        if root_replay["validation_status"] == "blocked":
            codes = sorted({item["code"] for item in root_replay["findings"]})
            findings.append(_finding("ROOT_SOURCE_REPLAY_FAILED", ", ".join(codes)))
    except Exception as exc:
        findings.append(_finding("ROOT_SOURCE_REPLAY_FAILED", str(exc)))
    source_index = _observation_index(observation_artifact)
    for item in artifact.get("evaluation_inventory", []):
        if not isinstance(item, Mapping):
            continue
        evaluation_id = str(item.get("evaluation_id") or "")
        source_evaluation = source_index.get(evaluation_id)
        if source_evaluation is None:
            findings.append(_finding("SOURCE_REPLAY_MISMATCH", f"missing {evaluation_id}"))
        else:
            try:
                expected = p2g3._inventory_item(source_evaluation)  # noqa: SLF001
                if canonical_json_bytes(expected) != canonical_json_bytes(item):
                    findings.append(_finding("SOURCE_REPLAY_MISMATCH", f"changed {evaluation_id}"))
            except Exception as exc:
                findings.append(_finding("SOURCE_REPLAY_ERROR", str(exc)))
    try:
        source_scope = p2g3._source_temporal_scope(  # noqa: SLF001
            observation_artifact.get("scope")
        )
        for item in artifact.get("hypotheses", []):
            if not isinstance(item, Mapping):
                continue
            compiled = p2g3._compile_hypotheses(  # noqa: SLF001
                [_proposal(item)],
                source_content_id=actual_source_id,
                evaluation_index=source_index,
                source_scope=source_scope,
            )[0]
            for field in (*_PROPOSAL_FIELDS, "warning_codes", "guardrail_flags"):
                if canonical_json_bytes(compiled.get(field)) != canonical_json_bytes(
                    item.get(field)
                ):
                    findings.append(
                        _finding(
                            "HYPOTHESIS_SOURCE_REPLAY_MISMATCH",
                            f"{item.get('hypothesis_id')}: {field}",
                        )
                    )
    except Exception as exc:
        findings.append(_finding("HYPOTHESIS_SOURCE_REPLAY_FAILED", str(exc)))
    result = _validation(
        findings,
        schema_version=REVISION_VALIDATION_SCHEMA_VERSION,
        mode="source_replay",
    )
    result["release_readiness"] = str(
        (artifact.get("release_readiness") or {}).get("status") or "blocked"
    )
    result["source_verification"] = {
        "status": (
            "verified"
            if result["validation_status"] == "accepted"
            and result["release_readiness"] == "ready"
            else "blocked"
        ),
        "expected_source_content_id": expected_source_id,
        "actual_source_content_id": actual_source_id,
    }
    return result


def validate_behavior_hypothesis_revision_chain(
    artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate a complete, non-forking append-only P2G-4 revision chain."""

    findings: list[dict[str, str]] = []
    if not artifacts:
        return _validation(
            [_finding("REVISION_CHAIN_EMPTY", "at least one revision is required")],
            schema_version=CHAIN_VALIDATION_SCHEMA_VERSION,
        )
    mappings = [item for item in artifacts if isinstance(item, Mapping)]
    if len(mappings) != len(artifacts):
        findings.append(_finding("REVISION_ARTIFACT_INVALID", "all revisions must be objects"))
    for artifact in mappings:
        validation = validate_behavior_hypothesis_revision(artifact)
        if validation["validation_status"] == "blocked":
            codes = sorted({item["code"] for item in validation["findings"]})
            findings.append(_finding("REVISION_ARTIFACT_INVALID", ", ".join(codes)))
    ordered = sorted(
        mappings,
        key=lambda item: (
            item.get("revision", {}).get("revision_no", -1)
            if isinstance(item.get("revision"), Mapping)
            else -1
        ),
    )
    numbers = [item.get("revision", {}).get("revision_no") for item in ordered]
    if numbers != list(range(1, len(ordered) + 1)):
        findings.append(
            _finding(
                "REVISION_NUMBER_SEQUENCE_INVALID",
                "revision numbers must be 1..N",
            )
        )
    content_ids = [str(item.get("content_id") or "") for item in ordered]
    if len(content_ids) != len(set(content_ids)):
        findings.append(_finding("REVISION_CONTENT_ID_DUPLICATE", "content IDs must be unique"))
    parents = [
        str(item.get("revision", {}).get("parent_content_id") or "")
        for item in ordered
    ]
    if len(parents) != len(set(parents)):
        findings.append(_finding("REVISION_CHAIN_FORK", "multiple revisions share one parent"))
    if ordered:
        first_revision = ordered[0].get("revision")
        first_revision = first_revision if isinstance(first_revision, Mapping) else {}
        root_content_id = str(first_revision.get("root_hypothesis_set_content_id") or "")
        if first_revision.get("parent_content_id") != root_content_id:
            findings.append(_finding("REVISION_PARENT_MISMATCH", "revision 1 must parent the root"))
        root_chain_id = ordered[0].get("revision_chain_id")
        root_source = ordered[0].get("source_hypothesis_set")
        root_observation = ordered[0].get("source_observation_set")
        root_model = ordered[0].get("model_provenance")
        previous_events: list[Any] = []
        previous_inventory: dict[str, Any] = {}
        for index, artifact in enumerate(ordered):
            revision = artifact.get("revision")
            revision = revision if isinstance(revision, Mapping) else {}
            if revision.get("root_hypothesis_set_content_id") != root_content_id:
                findings.append(_finding("REVISION_ROOT_MISMATCH", "root changed across chain"))
            if artifact.get("revision_chain_id") != root_chain_id:
                findings.append(_finding("REVISION_CHAIN_ID_MISMATCH", "chain ID changed"))
            if (
                canonical_json_bytes(artifact.get("source_hypothesis_set"))
                != canonical_json_bytes(root_source)
                or canonical_json_bytes(artifact.get("source_observation_set"))
                != canonical_json_bytes(root_observation)
                or canonical_json_bytes(artifact.get("model_provenance"))
                != canonical_json_bytes(root_model)
            ):
                findings.append(_finding("REVISION_FROZEN_SOURCE_CHANGED", "frozen source changed"))
            expected_parent = (
                root_content_id
                if index == 0
                else ordered[index - 1].get("content_id")
            )
            if revision.get("parent_content_id") != expected_parent:
                findings.append(_finding("REVISION_PARENT_MISMATCH", f"revision {index + 1}"))
            events = artifact.get("review_events")
            events = events if isinstance(events, list) else []
            if index and events[: len(previous_events)] != previous_events:
                findings.append(_finding("REVIEW_EVENT_PREFIX_MISMATCH", f"revision {index + 1}"))
            if index and len(events) <= len(previous_events):
                findings.append(_finding("REVIEW_EVENT_APPEND_MISSING", f"revision {index + 1}"))
            previous_events = deepcopy(events)
            inventory = {
                str(item.get("evaluation_id") or ""): item
                for item in artifact.get("evaluation_inventory", [])
                if isinstance(item, Mapping)
            }
            for evaluation_id, prior in previous_inventory.items():
                if evaluation_id not in inventory or canonical_json_bytes(
                    inventory[evaluation_id]
                ) != canonical_json_bytes(prior):
                    findings.append(_finding("REVISION_EVALUATION_CHANGED", evaluation_id))
            previous_inventory = inventory
    by_id = {str(item.get("content_id") or ""): item for item in ordered}
    for artifact in ordered:
        seen: set[str] = set()
        cursor = str(artifact.get("content_id") or "")
        while cursor in by_id:
            if cursor in seen:
                findings.append(_finding("REVISION_CHAIN_CYCLE", "parent graph contains a cycle"))
                break
            seen.add(cursor)
            revision = by_id[cursor].get("revision")
            if not isinstance(revision, Mapping):
                break
            cursor = str(revision.get("parent_content_id") or "")
    return _validation(
        findings, schema_version=CHAIN_VALIDATION_SCHEMA_VERSION
    )


def save_behavior_hypothesis_revision(
    path: str | Path, artifact: Mapping[str, Any]
) -> Path:
    """Create one validated P2G-4 revision and refuse overwrite."""

    if validate_behavior_hypothesis_revision(artifact)["validation_status"] == "blocked":
        raise BehaviorHypothesisReviewError("refusing to save an invalid revision")
    output = Path(path)
    if output.exists():
        raise BehaviorHypothesisReviewError(f"output already exists: {output}")
    try:
        return atomic_create_bytes(output, pretty_json_bytes(artifact))
    except (ArtifactIOError, OSError) as exc:
        raise BehaviorHypothesisReviewError(str(exc)) from exc


def load_behavior_hypothesis_artifact(path: str | Path) -> dict[str, Any]:
    try:
        return load_json_object(path)
    except (ArtifactIOError, OSError, ValueError) as exc:
        raise BehaviorHypothesisReviewError(str(exc)) from exc


__all__ = [
    "BUILDER_VERSION",
    "CANONICAL_SORT_VERSION",
    "CHAIN_VALIDATION_SCHEMA_VERSION",
    "REQUEST_SCHEMA_VERSION",
    "REQUEST_VALIDATION_SCHEMA_VERSION",
    "REVISION_SCHEMA_VERSION",
    "REVISION_VALIDATION_SCHEMA_VERSION",
    "BehaviorHypothesisReviewError",
    "apply_behavior_hypothesis_review",
    "behavior_hypothesis_review_request_id",
    "load_behavior_hypothesis_artifact",
    "load_behavior_hypothesis_review_request",
    "replay_validate_behavior_hypothesis_revision",
    "save_behavior_hypothesis_revision",
    "validate_behavior_hypothesis_review_request",
    "validate_behavior_hypothesis_revision",
    "validate_behavior_hypothesis_revision_chain",
]
