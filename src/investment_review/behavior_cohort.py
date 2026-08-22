"""Deterministic, cutoff-aware P2G-1 cross-episode fact cohorts.

The cohort is a frozen facts-only boundary.  It selects one authoritative P2F
review revision per logical chain, preserves its complete P2F facts projection,
and never consumes interpretation text, a database, the network, or wall-clock
metadata.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime
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
from .episode_interpretation import facts_only_projection
from .episode_review import (
    FACT_SECTION_NAMES,
    SCHEMA_VERSION as EPISODE_REVIEW_SCHEMA_VERSION,
    validate_episode_review,
    replay_validate_episode_review,
)
from .episode_revision import validate_revision_chain
from .review_input_bundle import validate_review_input_bundle
from .time_utils import TimestampError, parse_datetime, utc_iso


SCHEMA_VERSION = "p2g.behavior_cohort.v1"
VALIDATION_SCHEMA_VERSION = "p2g.behavior_cohort.validation.v1"
BUILDER_VERSION = "p2g.behavior_cohort.builder.v1"
EXCLUSION_REGISTRY_VERSION = "p2g.behavior_cohort.exclusions.v1"

EFFECTIVE_ANCHORS = ("episode_opened_at", "episode_closed_at")
EXCLUSION_REASON_REGISTRY: dict[str, bool] = {
    "outside_effective_window": False,
    "knowledge_after_cutoff": False,
    "missing_effective_anchor": False,
    "missing_knowledge_time": True,
    "schema_invalid": True,
    "release_not_ready": True,
    "source_not_verified": True,
    "source_replay_mismatch": True,
    "revision_chain_invalid": True,
    "ambiguous_current_revision": True,
    "human_rejected": False,
    "missing_required_fact_section": True,
    "duplicate_logical_episode": True,
    "content_id_mismatch": True,
    "filter_mismatch": False,
    "missing_source": True,
    "extra_source": True,
    "interpretation_contamination": True,
}

_CONTRACT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "contracts"
    / "P2G_BEHAVIOR_COHORT_DRAFT.schema.json"
)
_CONTENT_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_COHORT_ID_RE = re.compile(r"^cohort:[0-9a-f]{32}$")
_CANONICALIZATION = {
    "json_profile": "utf8-json-sorted-keys-no-float",
    "sort_version": "p2g.behavior_cohort.sort.v1",
    "hash_algorithm": "sha256",
    "excluded_fields": ["content_id"],
    "exclusion_registry_version": EXCLUSION_REGISTRY_VERSION,
    "builder_version": BUILDER_VERSION,
    "array_order": {
        "selection_spec.filters.account_ids": "lexical",
        "selection_spec.filters.instrument_ids": "lexical",
        "source_inventory": "source_kind,review_id,revision_no,content_id",
        "included_reviews": "effective_at,episode_id,review_id,revision_no,selected_review_content_id",
        "excluded_candidates": "candidate_id,reason_codes,candidate_content_ids",
    },
}


class BehaviorCohortError(ValueError):
    """Raised when a P2G-1 cohort cannot be built or verified safely."""


def _value_content_id(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _content_id(value: Mapping[str, Any]) -> str:
    material = deepcopy(dict(value))
    material.pop("content_id", None)
    return _value_content_id(material)


def _cohort_id(selection_spec: Mapping[str, Any]) -> str:
    return "cohort:" + hashlib.sha256(
        canonical_json_bytes(selection_spec)
    ).hexdigest()[:32]


def _normalize_timestamp(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BehaviorCohortError(f"{field} must be a timezone-aware timestamp")
    text = value.strip()
    try:
        parsed = parse_datetime(text, "UTC")
    except TimestampError as exc:
        raise BehaviorCohortError(f"invalid {field}: {value!r}") from exc
    normalized_probe = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        original = datetime.fromisoformat(normalized_probe)
    except ValueError as exc:
        raise BehaviorCohortError(f"invalid {field}: {value!r}") from exc
    if original.tzinfo is None or original.utcoffset() is None:
        raise BehaviorCohortError(f"{field} must include a timezone")
    if original.microsecond:
        raise BehaviorCohortError(f"{field} must use whole seconds")
    return utc_iso(parsed, "UTC")


def _canonical_timestamp(value: object, field: str) -> str:
    normalized = _normalize_timestamp(value, field)
    if value != normalized:
        raise BehaviorCohortError(f"{field} must use canonical UTC seconds")
    return normalized


def _timestamp_key(value: str) -> object:
    return parse_datetime(value, "UTC")


def _finding(severity: str, code: str, message: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message}


def _validation(
    findings: Iterable[Mapping[str, Any]], *, mode: str = "offline_structural"
) -> dict[str, Any]:
    values = sorted(
        [dict(item) for item in findings],
        key=lambda item: (
            0 if item.get("severity") == "blocker" else 1,
            str(item.get("code") or ""),
            str(item.get("message") or ""),
        ),
    )
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "validation_mode": mode,
        "validation_status": (
            "blocked"
            if any(item.get("severity") == "blocker" for item in values)
            else "accepted_with_warnings"
            if values
            else "accepted"
        ),
        "findings": values,
    }


@lru_cache(maxsize=1)
def _contract_validator() -> Draft202012Validator:
    schema = json.loads(_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _schema_findings(artifact: Mapping[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for error in sorted(
        _contract_validator().iter_errors(artifact),
        key=lambda item: (list(item.absolute_path), item.message),
    ):
        path = "$" + "".join(
            f"[{item}]" if isinstance(item, int) else f".{item}"
            for item in error.absolute_path
        )
        findings.append(
            _finding("blocker", "SCHEMA_VIOLATION", f"{path}: {error.message}")
        )
    return findings


def _normalize_filters(filters: Mapping[str, Any] | None) -> dict[str, list[str]]:
    values = dict(filters or {})
    unknown = sorted(set(values) - {"account_ids", "instrument_ids"})
    if unknown:
        raise BehaviorCohortError("unsupported filters: " + ", ".join(unknown))

    def normalized(name: str, *, uppercase: bool) -> list[str]:
        raw = values.get(name, [])
        if not isinstance(raw, (list, tuple, set)):
            raise BehaviorCohortError(f"filters.{name} must be an array")
        result = {
            str(item).strip().upper() if uppercase else str(item).strip()
            for item in raw
            if str(item).strip()
        }
        return sorted(result)

    return {
        "account_ids": normalized("account_ids", uppercase=False),
        "instrument_ids": normalized("instrument_ids", uppercase=True),
    }


def _observed_content_id(value: Mapping[str, Any]) -> str:
    return _content_id(value)


def _evidence_ref(source_kind: str, content_id: str, role: str) -> dict[str, str]:
    return {"source_kind": source_kind, "content_id": content_id, "role": role}


def _exclusion(
    *,
    candidate_id: str,
    episode_id: str | None,
    review_id: str | None,
    candidate_content_ids: Iterable[str],
    reason_codes: Iterable[str],
    evidence_refs: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    reasons = sorted(set(reason_codes))
    unknown = sorted(set(reasons) - set(EXCLUSION_REASON_REGISTRY))
    if unknown:
        raise BehaviorCohortError("unknown exclusion reasons: " + ", ".join(unknown))
    unique_refs = {
        canonical_json_bytes(item): dict(item) for item in evidence_refs
    }
    refs = sorted(
        unique_refs.values(),
        key=lambda item: (
            str(item.get("source_kind") or ""),
            str(item.get("content_id") or ""),
            str(item.get("role") or ""),
        ),
    )
    return {
        "candidate_id": candidate_id,
        "episode_id": episode_id,
        "review_id": review_id,
        "candidate_content_ids": sorted(
            {value for value in candidate_content_ids if _CONTENT_ID_RE.fullmatch(value)}
        ),
        "reason_codes": reasons,
        "evidence_refs": refs,
        "blocking": any(EXCLUSION_REASON_REGISTRY[reason] for reason in reasons),
    }


def _review_identity(review: Mapping[str, Any]) -> tuple[str, str, str]:
    input_ref = review.get("input_bundle_ref")
    if not isinstance(input_ref, Mapping):
        input_ref = {}
    return (
        str(review.get("review_id") or ""),
        str(input_ref.get("episode_id") or ""),
        str(input_ref.get("content_id") or ""),
    )


def _bundle_review_cutoff(bundle: Mapping[str, Any]) -> str:
    request = bundle.get("build_request")
    if not isinstance(request, Mapping):
        raise BehaviorCohortError("P2F input bundle has no build_request")
    return _canonical_timestamp(
        request.get("review_cutoff"), "input_bundle.build_request.review_cutoff"
    )


def _review_knowledge_at(
    review: Mapping[str, Any], bundle: Mapping[str, Any]
) -> str:
    times = [_bundle_review_cutoff(bundle)]
    governance = review.get("governance")
    if not isinstance(governance, Mapping):
        raise BehaviorCohortError("review governance is missing")
    mode = str(governance.get("generation_mode") or "")
    if mode == "model_assisted":
        model = governance.get("model_generation")
        if not isinstance(model, Mapping):
            raise BehaviorCohortError("model-assisted review has no model provenance")
        times.append(
            _canonical_timestamp(
                model.get("generated_at"), "review.governance.model_generation.generated_at"
            )
        )
    elif mode == "human_authored":
        events = governance.get("human_reviews")
        if not isinstance(events, list) or not events:
            raise BehaviorCohortError("human-authored review has no review events")
        for index, event in enumerate(events):
            if not isinstance(event, Mapping):
                raise BehaviorCohortError("human review event must be an object")
            times.append(
                _canonical_timestamp(
                    event.get("reviewed_at"),
                    f"review.governance.human_reviews[{index}].reviewed_at",
                )
            )
    elif mode != "facts_only":
        raise BehaviorCohortError("unsupported review generation mode")
    return max(times, key=_timestamp_key)


def _validation_reason_codes(validation: Mapping[str, Any]) -> list[str]:
    codes = {
        str(item.get("code") or "")
        for item in validation.get("findings", [])
        if isinstance(item, Mapping)
    }
    reasons: set[str] = set()
    if "CONTENT_ID_MISMATCH" in codes:
        reasons.add("content_id_mismatch")
    if {"FACT_SECTION_INVALID", "FACT_SECTION_KIND_MISMATCH"} & codes:
        reasons.add("missing_required_fact_section")
    if validation.get("validation_status") == "blocked" and not reasons:
        reasons.add("schema_invalid")
    return sorted(reasons)


def _lifecycle_fact(projection: Mapping[str, Any]) -> Mapping[str, Any] | None:
    sections = projection.get("fact_sections")
    if not isinstance(sections, Mapping):
        return None
    timeline = sections.get("timeline")
    if not isinstance(timeline, Mapping):
        return None
    values = [
        item
        for item in timeline.get("facts", [])
        if isinstance(item, Mapping) and item.get("kind") == "episode_lifecycle"
    ]
    return values[0] if len(values) == 1 else None


def _effective_at(projection: Mapping[str, Any], anchor: str) -> str | None:
    lifecycle = _lifecycle_fact(projection)
    data = lifecycle.get("data") if isinstance(lifecycle, Mapping) else None
    if not isinstance(data, Mapping):
        return None
    field = "opened_at" if anchor == "episode_opened_at" else "closed_at"
    value = data.get(field)
    if value is None:
        return None
    return _canonical_timestamp(value, f"lifecycle.{field}")


def _security_identity_values(
    projection: Mapping[str, Any]
) -> tuple[set[str], set[str]]:
    accounts: set[str] = set()
    instruments: set[str] = set()
    sections = projection.get("fact_sections")
    if not isinstance(sections, Mapping):
        return accounts, instruments
    section = sections.get("security_context")
    if not isinstance(section, Mapping):
        return accounts, instruments
    for fact in section.get("facts", []):
        if not isinstance(fact, Mapping) or fact.get("kind") != "security_identity":
            continue
        data = fact.get("data")
        if not isinstance(data, Mapping):
            continue
        if str(data.get("account_id") or ""):
            accounts.add(str(data["account_id"]))
        if str(data.get("instrument_id") or ""):
            instruments.add(str(data["instrument_id"]).upper())
    return accounts, instruments


def _matches_filters(
    projection: Mapping[str, Any], filters: Mapping[str, Sequence[str]]
) -> bool:
    accounts, instruments = _security_identity_values(projection)
    account_filter = set(filters.get("account_ids", []))
    instrument_filter = set(filters.get("instrument_ids", []))
    return (not account_filter or bool(accounts & account_filter)) and (
        not instrument_filter or bool(instruments & instrument_filter)
    )


def _fact_section_refs(projection: Mapping[str, Any]) -> list[dict[str, Any]]:
    sections = projection.get("fact_sections")
    if not isinstance(sections, Mapping):
        raise BehaviorCohortError("facts projection has no fact_sections")
    result: list[dict[str, Any]] = []
    for name in FACT_SECTION_NAMES:
        section = sections.get(name)
        if not isinstance(section, Mapping):
            raise BehaviorCohortError(f"facts projection is missing {name}")
        result.append(
            {
                "section": name,
                "status": str(section.get("status") or ""),
                "fact_ids": sorted(
                    str(item.get("fact_id"))
                    for item in section.get("facts", [])
                    if isinstance(item, Mapping) and item.get("fact_id")
                ),
                "source_ids": sorted(
                    {str(item) for item in section.get("source_ids", [])}
                ),
                "warning_codes": sorted(
                    {str(item) for item in section.get("warning_codes", [])}
                ),
                "gap_codes": sorted(
                    {str(item) for item in section.get("gap_codes", [])}
                ),
            }
        )
    return result


def _projection_source_refs(projection: Mapping[str, Any]) -> list[dict[str, str]]:
    unique: dict[bytes, dict[str, str]] = {}
    sections = projection.get("fact_sections")
    if not isinstance(sections, Mapping):
        raise BehaviorCohortError("facts projection has no fact_sections")
    for name in FACT_SECTION_NAMES:
        section = sections.get(name)
        if not isinstance(section, Mapping):
            continue
        for fact in section.get("facts", []):
            if not isinstance(fact, Mapping):
                continue
            for ref in fact.get("source_refs", []):
                if not isinstance(ref, Mapping):
                    continue
                value = {
                    "source_id": str(ref.get("source_id") or ""),
                    "source_kind": str(ref.get("source_kind") or ""),
                    "content_id": str(ref.get("content_id") or ""),
                    "locator": str(ref.get("locator") or ""),
                    "frozen_pointer": str(ref.get("frozen_pointer") or ""),
                }
                unique[canonical_json_bytes(value)] = value
    return sorted(
        unique.values(),
        key=lambda item: (
            item["source_kind"],
            item["source_id"],
            item["content_id"],
            item["frozen_pointer"],
            item["locator"],
        ),
    )


def _included_sort_key(item: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(item.get("effective_at") or ""),
        str(item.get("episode_id") or ""),
        str(item.get("review_id") or ""),
        int(item.get("revision_no") or 0),
        str(item.get("selected_review_content_id") or ""),
    )


def _excluded_sort_key(item: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(item.get("candidate_id") or ""),
        tuple(item.get("reason_codes") or []),
        tuple(item.get("candidate_content_ids") or []),
    )


def _source_inventory_from_included(
    included: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for item in included:
        lineage = [
            dict(value)
            for value in item.get("revision_chain", [])
            if isinstance(value, Mapping)
        ]
        selected_id = str(item.get("selected_review_content_id") or "")
        for value in lineage:
            content_id = str(value.get("content_id") or "")
            values.append(
                {
                    "source_kind": "episode_review",
                    "role": (
                        "selected_review"
                        if content_id == selected_id
                        else "revision_predecessor"
                    ),
                    "episode_id": str(item.get("episode_id") or ""),
                    "review_id": str(item.get("review_id") or ""),
                    "revision_no": int(value.get("revision_no") or 0),
                    "content_id": content_id,
                    "knowledge_at": str(value.get("knowledge_at") or ""),
                }
            )
        values.append(
            {
                "source_kind": "review_input_bundle",
                "role": "input_bundle",
                "episode_id": str(item.get("episode_id") or ""),
                "review_id": str(item.get("review_id") or ""),
                "revision_no": None,
                "content_id": str(item.get("input_bundle_content_id") or ""),
                "knowledge_at": str(item.get("input_bundle_knowledge_at") or ""),
            }
        )
    unique = {canonical_json_bytes(value): value for value in values}
    return sorted(
        unique.values(),
        key=lambda value: (
            value["source_kind"],
            value["review_id"],
            -1 if value["revision_no"] is None else value["revision_no"],
            value["content_id"],
        ),
    )


def _counts(
    candidate_chain_count: int,
    included: Sequence[Mapping[str, Any]],
    excluded: Sequence[Mapping[str, Any]],
    inventory: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    fact_count = sum(
        len(section.get("facts", []))
        for item in included
        for section in (
            item.get("facts_projection", {}).get("fact_sections", {}).values()
            if isinstance(item.get("facts_projection"), Mapping)
            and isinstance(item.get("facts_projection", {}).get("fact_sections"), Mapping)
            else []
        )
        if isinstance(section, Mapping)
    )
    return {
        "candidate_chain_count": candidate_chain_count,
        "included_review_count": len(included),
        "excluded_candidate_count": len(excluded),
        "blocking_exclusion_count": sum(
            1 for item in excluded if item.get("blocking") is True
        ),
        "source_count": len(inventory),
        "fact_count": fact_count,
    }


def _release_status(excluded: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    blocker_codes = sorted(
        {
            reason
            for item in excluded
            if item.get("blocking") is True
            for reason in item.get("reason_codes", [])
            if EXCLUSION_REASON_REGISTRY.get(str(reason), True)
        }
    )
    return {
        "status": "blocked" if blocker_codes else "ready",
        "blocker_codes": blocker_codes,
    }


def _source_status(
    included: Sequence[Mapping[str, Any]],
    excluded: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    release = _release_status(excluded)
    review_ids = sorted(
        {
            str(lineage.get("content_id") or "")
            for item in included
            for lineage in item.get("revision_chain", [])
            if isinstance(lineage, Mapping)
        }
    )
    bundle_ids = sorted(
        {str(item.get("input_bundle_content_id") or "") for item in included}
    )
    return {
        "status": "verified" if release["status"] == "ready" else "blocked",
        "validation_mode": "p2f_source_replay",
        "verified_review_content_ids": review_ids,
        "verified_input_bundle_content_ids": bundle_ids,
    }


def build_behavior_cohort(
    episode_reviews: Iterable[Mapping[str, Any]],
    input_bundles: Iterable[Mapping[str, Any]],
    *,
    effective_from: str,
    effective_to: str,
    knowledge_cutoff: str,
    effective_anchor: str,
    filters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one deterministic facts-only cohort from explicit P2F sources."""

    if effective_anchor not in EFFECTIVE_ANCHORS:
        raise BehaviorCohortError(
            "effective_anchor must be one of: " + ", ".join(EFFECTIVE_ANCHORS)
        )
    start = _normalize_timestamp(effective_from, "effective_from")
    end = _normalize_timestamp(effective_to, "effective_to")
    cutoff = _normalize_timestamp(knowledge_cutoff, "knowledge_cutoff")
    if _timestamp_key(start) >= _timestamp_key(end):
        raise BehaviorCohortError("effective_from must precede effective_to")
    selection_spec = {
        "effective_from": start,
        "effective_to": end,
        "effective_anchor": effective_anchor,
        "knowledge_cutoff": cutoff,
        "filters": _normalize_filters(filters),
    }

    review_values = list(episode_reviews)
    bundle_values = list(input_bundles)
    if not all(isinstance(item, Mapping) for item in review_values):
        raise BehaviorCohortError("every episode review must be an object")
    if not all(isinstance(item, Mapping) for item in bundle_values):
        raise BehaviorCohortError("every input bundle must be an object")
    raw_reviews = [dict(item) for item in review_values]
    raw_bundles = [dict(item) for item in bundle_values]
    if not raw_reviews:
        raise BehaviorCohortError("at least one episode review is required")

    review_by_document: dict[str, dict[str, Any]] = {}
    for review in raw_reviews:
        document_id = _value_content_id(review)
        review_by_document.setdefault(document_id, review)
    bundle_by_document: dict[str, dict[str, Any]] = {}
    for bundle in raw_bundles:
        document_id = _value_content_id(bundle)
        bundle_by_document.setdefault(document_id, bundle)

    bundles_by_claimed: dict[str, list[dict[str, Any]]] = {}
    for bundle in bundle_by_document.values():
        bundles_by_claimed.setdefault(str(bundle.get("content_id") or ""), []).append(bundle)

    groups: dict[str, list[dict[str, Any]]] = {}
    referenced_bundle_ids: set[str] = set()
    for review in review_by_document.values():
        review_id, _episode_id, bundle_id = _review_identity(review)
        observed = _observed_content_id(review)
        key = review_id if review_id else f"invalid-review-chain:{observed[7:39]}"
        groups.setdefault(key, []).append(review)
        if bundle_id:
            referenced_bundle_ids.add(bundle_id)

    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for candidate_id in sorted(groups):
        group = groups[candidate_id]
        identities = [_review_identity(review) for review in group]
        review_ids = {value[0] for value in identities if value[0]}
        episode_ids = {value[1] for value in identities if value[1]}
        bundle_ids = {value[2] for value in identities if value[2]}
        review_id = next(iter(review_ids), None)
        episode_id = next(iter(episode_ids), None)
        observed_ids = sorted({_observed_content_id(review) for review in group})
        review_refs = [
            _evidence_ref("episode_review", value, "candidate_revision")
            for value in observed_ids
        ]
        if len(review_ids) != 1 or len(episode_ids) != 1 or len(bundle_ids) != 1:
            excluded.append(
                _exclusion(
                    candidate_id=candidate_id,
                    episode_id=episode_id,
                    review_id=review_id,
                    candidate_content_ids=observed_ids,
                    reason_codes=["revision_chain_invalid"],
                    evidence_refs=review_refs,
                )
            )
            continue
        bundle_id = next(iter(bundle_ids))
        bundle_candidates = bundles_by_claimed.get(bundle_id, [])
        if len(bundle_candidates) != 1:
            reasons = ["missing_source"] if not bundle_candidates else ["content_id_mismatch"]
            excluded.append(
                _exclusion(
                    candidate_id=candidate_id,
                    episode_id=episode_id,
                    review_id=review_id,
                    candidate_content_ids=observed_ids,
                    reason_codes=reasons,
                    evidence_refs=review_refs,
                )
            )
            continue
        bundle = bundle_candidates[0]
        bundle_observed = _observed_content_id(bundle)
        knowledge_by_observed: dict[str, str] = {}
        missing_knowledge = False
        for review in group:
            observed = _observed_content_id(review)
            try:
                knowledge_by_observed[observed] = _review_knowledge_at(review, bundle)
            except BehaviorCohortError:
                missing_knowledge = True
        if missing_knowledge:
            excluded.append(
                _exclusion(
                    candidate_id=candidate_id,
                    episode_id=episode_id,
                    review_id=review_id,
                    candidate_content_ids=observed_ids,
                    reason_codes=["missing_knowledge_time"],
                    evidence_refs=[
                        *review_refs,
                        _evidence_ref("review_input_bundle", bundle_observed, "input_bundle"),
                    ],
                )
            )
            continue
        eligible = [
            review
            for review in group
            if _timestamp_key(knowledge_by_observed[_observed_content_id(review)])
            <= _timestamp_key(cutoff)
        ]
        if not eligible:
            excluded.append(
                _exclusion(
                    candidate_id=candidate_id,
                    episode_id=episode_id,
                    review_id=review_id,
                    candidate_content_ids=observed_ids,
                    reason_codes=["knowledge_after_cutoff"],
                    evidence_refs=review_refs,
                )
            )
            continue

        review_reasons: set[str] = set()
        for review in eligible:
            validation = validate_episode_review(review)
            review_reasons.update(_validation_reason_codes(validation))
        if review_reasons:
            excluded.append(
                _exclusion(
                    candidate_id=candidate_id,
                    episode_id=episode_id,
                    review_id=review_id,
                    candidate_content_ids=[_observed_content_id(value) for value in eligible],
                    reason_codes=review_reasons,
                    evidence_refs=review_refs,
                )
            )
            continue

        revisions = [
            int((review.get("revision") or {}).get("revision_no") or 0)
            for review in eligible
        ]
        if len(revisions) != len(set(revisions)):
            excluded.append(
                _exclusion(
                    candidate_id=candidate_id,
                    episode_id=episode_id,
                    review_id=review_id,
                    candidate_content_ids=[str(value.get("content_id") or "") for value in eligible],
                    reason_codes=["ambiguous_current_revision"],
                    evidence_refs=review_refs,
                )
            )
            continue
        chain_validation = validate_revision_chain(eligible)
        content_ids = {str(review.get("content_id") or "") for review in eligible}
        superseded_ids = {
            str((review.get("revision") or {}).get("supersedes_content_id") or "")
            for review in eligible
            if (review.get("revision") or {}).get("supersedes_content_id")
        }
        leaves = sorted(content_ids - superseded_ids)
        chain_reasons: list[str] = []
        if chain_validation.get("validation_status") == "blocked":
            chain_reasons.append("revision_chain_invalid")
        if len(leaves) != 1:
            chain_reasons.append("ambiguous_current_revision")
        if chain_reasons:
            excluded.append(
                _exclusion(
                    candidate_id=candidate_id,
                    episode_id=episode_id,
                    review_id=review_id,
                    candidate_content_ids=content_ids,
                    reason_codes=chain_reasons,
                    evidence_refs=review_refs,
                )
            )
            continue
        selected = next(review for review in eligible if review.get("content_id") == leaves[0])
        projection = facts_only_projection(selected)
        projection_validation = validate_episode_review(projection)
        if projection_validation.get("validation_status") == "blocked":
            excluded.append(
                _exclusion(
                    candidate_id=candidate_id,
                    episode_id=episode_id,
                    review_id=review_id,
                    candidate_content_ids=content_ids,
                    reason_codes=["interpretation_contamination"],
                    evidence_refs=review_refs,
                )
            )
            continue
        try:
            effective_at = _effective_at(projection, effective_anchor)
        except BehaviorCohortError:
            effective_at = None
        if effective_at is None:
            excluded.append(
                _exclusion(
                    candidate_id=candidate_id,
                    episode_id=episode_id,
                    review_id=review_id,
                    candidate_content_ids=content_ids,
                    reason_codes=["missing_effective_anchor"],
                    evidence_refs=review_refs,
                )
            )
            continue
        if not (
            _timestamp_key(start)
            <= _timestamp_key(effective_at)
            < _timestamp_key(end)
        ):
            excluded.append(
                _exclusion(
                    candidate_id=candidate_id,
                    episode_id=episode_id,
                    review_id=review_id,
                    candidate_content_ids=content_ids,
                    reason_codes=["outside_effective_window"],
                    evidence_refs=review_refs,
                )
            )
            continue
        if not _matches_filters(projection, selection_spec["filters"]):
            excluded.append(
                _exclusion(
                    candidate_id=candidate_id,
                    episode_id=episode_id,
                    review_id=review_id,
                    candidate_content_ids=content_ids,
                    reason_codes=["filter_mismatch"],
                    evidence_refs=review_refs,
                )
            )
            continue

        bundle_validation = validate_review_input_bundle(bundle)
        bundle_reasons = set(_validation_reason_codes(bundle_validation))
        if bundle.get("content_id") != bundle_observed:
            bundle_reasons.add("content_id_mismatch")
        release = bundle.get("release_readiness")
        if not isinstance(release, Mapping) or release.get("status") != "ready":
            bundle_reasons.add("release_not_ready")
        verification = bundle.get("source_verification")
        if not isinstance(verification, Mapping) or verification.get("status") != "verified":
            bundle_reasons.add("source_not_verified")
        if bundle_reasons:
            excluded.append(
                _exclusion(
                    candidate_id=candidate_id,
                    episode_id=episode_id,
                    review_id=review_id,
                    candidate_content_ids=[*content_ids, bundle_observed],
                    reason_codes=bundle_reasons,
                    evidence_refs=[
                        *review_refs,
                        _evidence_ref("review_input_bundle", bundle_observed, "input_bundle"),
                    ],
                )
            )
            continue
        replay = replay_validate_episode_review(selected, input_bundle=bundle)
        if (
            replay.get("validation_status") == "blocked"
            or (replay.get("source_verification") or {}).get("status") != "verified"
        ):
            excluded.append(
                _exclusion(
                    candidate_id=candidate_id,
                    episode_id=episode_id,
                    review_id=review_id,
                    candidate_content_ids=[*content_ids, bundle_observed],
                    reason_codes=["source_replay_mismatch"],
                    evidence_refs=[
                        *review_refs,
                        _evidence_ref("review_input_bundle", bundle_observed, "input_bundle"),
                    ],
                )
            )
            continue

        ordered_chain = sorted(
            eligible,
            key=lambda value: int((value.get("revision") or {}).get("revision_no") or 0),
        )
        lineage = [
            {
                "revision_no": int(review["revision"]["revision_no"]),
                "status": str(review["revision"]["status"]),
                "content_id": str(review["content_id"]),
                "knowledge_at": knowledge_by_observed[_observed_content_id(review)],
            }
            for review in ordered_chain
        ]
        included.append(
            {
                "episode_id": str(episode_id),
                "review_id": str(review_id),
                "revision_no": int(selected["revision"]["revision_no"]),
                "selected_review_content_id": str(selected["content_id"]),
                "input_bundle_content_id": str(bundle["content_id"]),
                "input_bundle_knowledge_at": _bundle_review_cutoff(bundle),
                "effective_at": effective_at,
                "knowledge_at": knowledge_by_observed[_observed_content_id(selected)],
                "revision_chain": lineage,
                "facts_content_id": str(projection["content_id"]),
                "fact_section_refs": _fact_section_refs(projection),
                "source_refs": _projection_source_refs(projection),
                "facts_projection": projection,
            }
        )

    for claimed_id, candidates in sorted(bundles_by_claimed.items()):
        if claimed_id in referenced_bundle_ids:
            continue
        for bundle in candidates:
            observed = _observed_content_id(bundle)
            excluded.append(
                _exclusion(
                    candidate_id=f"input-bundle:{observed[7:39]}",
                    episode_id=None,
                    review_id=None,
                    candidate_content_ids=[observed],
                    reason_codes=["extra_source"],
                    evidence_refs=[
                        _evidence_ref("review_input_bundle", observed, "unreferenced_input")
                    ],
                )
            )

    included.sort(key=_included_sort_key)
    duplicate_episode_ids = {
        episode
        for episode in {item["episode_id"] for item in included}
        if sum(1 for item in included if item["episode_id"] == episode) > 1
    }
    if duplicate_episode_ids:
        retained: list[dict[str, Any]] = []
        for item in included:
            if item["episode_id"] not in duplicate_episode_ids:
                retained.append(item)
                continue
            excluded.append(
                _exclusion(
                    candidate_id=str(item["review_id"]),
                    episode_id=str(item["episode_id"]),
                    review_id=str(item["review_id"]),
                    candidate_content_ids=[str(item["selected_review_content_id"])],
                    reason_codes=["duplicate_logical_episode"],
                    evidence_refs=[
                        _evidence_ref(
                            "episode_review",
                            str(item["selected_review_content_id"]),
                            "duplicate_candidate",
                        )
                    ],
                )
            )
        included = retained
    excluded = list(
        {
            canonical_json_bytes(item): item
            for item in excluded
        }.values()
    )
    excluded.sort(key=_excluded_sort_key)
    inventory = _source_inventory_from_included(included)
    release_readiness = _release_status(excluded)
    source_verification = _source_status(included, excluded)
    artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "content_id": "",
        "cohort_id": _cohort_id(selection_spec),
        "selection_spec": selection_spec,
        "source_inventory": inventory,
        "included_reviews": included,
        "excluded_candidates": excluded,
        "counts": _counts(len(groups), included, excluded, inventory),
        "release_readiness": release_readiness,
        "source_verification": source_verification,
        "canonicalization": deepcopy(_CANONICALIZATION),
    }
    artifact["content_id"] = _content_id(artifact)
    validation = validate_behavior_cohort(artifact)
    if validation["validation_status"] == "blocked":
        raise BehaviorCohortError(
            "built behavior cohort failed validation: "
            + "; ".join(item["message"] for item in validation["findings"])
        )
    return artifact


def _validate_behavior_cohort_impl(artifact: Mapping[str, Any]) -> dict[str, Any]:
    findings = _schema_findings(artifact)
    try:
        canonical_json_bytes(artifact)
    except ArtifactIOError as exc:
        findings.append(_finding("blocker", "NON_CANONICAL_JSON", str(exc)))
    if artifact.get("schema_version") != SCHEMA_VERSION:
        findings.append(_finding("blocker", "UNSUPPORTED_SCHEMA", "unsupported schema"))
    if artifact.get("canonicalization") != _CANONICALIZATION:
        findings.append(
            _finding(
                "blocker",
                "CANONICALIZATION_PROFILE_MISMATCH",
                "canonicalization profile does not match P2G-1",
            )
        )
    try:
        expected_content_id = _content_id(artifact)
        if (
            not _CONTENT_ID_RE.fullmatch(str(artifact.get("content_id") or ""))
            or artifact.get("content_id") != expected_content_id
        ):
            findings.append(
                _finding("blocker", "CONTENT_ID_MISMATCH", "content_id is not canonical")
            )
    except ArtifactIOError as exc:
        findings.append(_finding("blocker", "CONTENT_ID_ERROR", str(exc)))

    selection = artifact.get("selection_spec")
    if not isinstance(selection, Mapping):
        selection = {}
    start = end = cutoff = None
    for field in ("effective_from", "effective_to", "knowledge_cutoff"):
        try:
            value = _canonical_timestamp(selection.get(field), f"selection_spec.{field}")
        except BehaviorCohortError as exc:
            findings.append(_finding("blocker", "INVALID_SELECTION_TIME", str(exc)))
            continue
        if field == "effective_from":
            start = value
        elif field == "effective_to":
            end = value
        else:
            cutoff = value
    if start and end and _timestamp_key(start) >= _timestamp_key(end):
        findings.append(
            _finding("blocker", "INVALID_EFFECTIVE_WINDOW", "effective_from must precede effective_to")
        )
    if selection.get("effective_anchor") not in EFFECTIVE_ANCHORS:
        findings.append(
            _finding("blocker", "INVALID_EFFECTIVE_ANCHOR", "unsupported effective anchor")
        )
    try:
        normalized_filters = _normalize_filters(selection.get("filters"))
        if selection.get("filters") != normalized_filters:
            findings.append(
                _finding("blocker", "FILTERS_NOT_CANONICAL", "filters are not canonical")
            )
    except BehaviorCohortError as exc:
        findings.append(_finding("blocker", "FILTERS_INVALID", str(exc)))
    if isinstance(selection, Mapping):
        expected_cohort_id = _cohort_id(selection)
        if (
            not _COHORT_ID_RE.fullmatch(str(artifact.get("cohort_id") or ""))
            or artifact.get("cohort_id") != expected_cohort_id
        ):
            findings.append(
                _finding("blocker", "COHORT_ID_MISMATCH", "cohort_id is not deterministic")
            )

    included = [
        item for item in artifact.get("included_reviews", []) if isinstance(item, Mapping)
    ]
    if included != sorted(included, key=_included_sort_key):
        findings.append(
            _finding("blocker", "INCLUDED_ORDER_MISMATCH", "included reviews are not canonical")
        )
    seen_episodes: set[str] = set()
    seen_reviews: set[str] = set()
    for item in included:
        episode_id = str(item.get("episode_id") or "")
        review_id = str(item.get("review_id") or "")
        if episode_id in seen_episodes or review_id in seen_reviews:
            findings.append(
                _finding("blocker", "DUPLICATE_LOGICAL_EPISODE", "included review identity is duplicated")
            )
        seen_episodes.add(episode_id)
        seen_reviews.add(review_id)
        projection = item.get("facts_projection")
        if not isinstance(projection, Mapping):
            findings.append(
                _finding("blocker", "FACTS_PROJECTION_INVALID", f"{review_id} has no facts projection")
            )
            continue
        projection_validation = validate_episode_review(projection)
        if projection_validation.get("validation_status") == "blocked":
            findings.append(
                _finding("blocker", "FACTS_PROJECTION_INVALID", f"{review_id} P2F facts projection is invalid")
            )
        governance = projection.get("governance")
        interpretations = projection.get("interpretation_sections")
        if (
            not isinstance(governance, Mapping)
            or governance.get("generation_mode") != "facts_only"
            or not isinstance(interpretations, Mapping)
            or any(interpretations.get(name) != [] for name in interpretations)
        ):
            findings.append(
                _finding("blocker", "INTERPRETATION_CONTAMINATION", f"{review_id} is not facts-only")
            )
        input_ref = projection.get("input_bundle_ref")
        if not isinstance(input_ref, Mapping):
            input_ref = {}
        if (
            projection.get("schema_version") != EPISODE_REVIEW_SCHEMA_VERSION
            or projection.get("review_id") != review_id
            or input_ref.get("episode_id") != episode_id
            or input_ref.get("content_id") != item.get("input_bundle_content_id")
            or projection.get("content_id") != item.get("facts_content_id")
        ):
            findings.append(
                _finding("blocker", "FACTS_BINDING_MISMATCH", f"{review_id} facts binding drifted")
            )
        try:
            expected_sections = _fact_section_refs(projection)
            expected_refs = _projection_source_refs(projection)
            if item.get("fact_section_refs") != expected_sections:
                findings.append(
                    _finding("blocker", "FACT_SECTION_REFS_MISMATCH", f"{review_id} section refs drifted")
                )
            if item.get("source_refs") != expected_refs:
                findings.append(
                    _finding("blocker", "SOURCE_REFS_MISMATCH", f"{review_id} source refs drifted")
                )
        except BehaviorCohortError as exc:
            findings.append(_finding("blocker", "FACT_REFS_INVALID", str(exc)))
        lineage = [
            value for value in item.get("revision_chain", []) if isinstance(value, Mapping)
        ]
        numbers = [value.get("revision_no") for value in lineage]
        if numbers != list(range(1, len(lineage) + 1)):
            findings.append(
                _finding("blocker", "REVISION_LINEAGE_INVALID", f"{review_id} lineage is not sequential")
            )
        if (
            not lineage
            or lineage[-1].get("content_id") != item.get("selected_review_content_id")
            or lineage[-1].get("revision_no") != item.get("revision_no")
        ):
            findings.append(
                _finding("blocker", "SELECTED_REVISION_MISMATCH", f"{review_id} selected leaf is inconsistent")
            )
        try:
            knowledge = _canonical_timestamp(item.get("knowledge_at"), f"{review_id}.knowledge_at")
            bundle_knowledge = _canonical_timestamp(
                item.get("input_bundle_knowledge_at"), f"{review_id}.input_bundle_knowledge_at"
            )
            effective = _canonical_timestamp(item.get("effective_at"), f"{review_id}.effective_at")
            if cutoff and (
                _timestamp_key(knowledge) > _timestamp_key(cutoff)
                or _timestamp_key(bundle_knowledge) > _timestamp_key(cutoff)
            ):
                findings.append(
                    _finding("blocker", "KNOWLEDGE_CUTOFF_LEAK", f"{review_id} exceeds the cutoff")
                )
            if start and end and not (
                _timestamp_key(start) <= _timestamp_key(effective) < _timestamp_key(end)
            ):
                findings.append(
                    _finding("blocker", "EFFECTIVE_WINDOW_MISMATCH", f"{review_id} is outside the window")
                )
            expected_effective = _effective_at(projection, str(selection.get("effective_anchor") or ""))
            if effective != expected_effective:
                findings.append(
                    _finding("blocker", "EFFECTIVE_ANCHOR_MISMATCH", f"{review_id} anchor drifted")
                )
            if not _matches_filters(projection, selection.get("filters") or {}):
                findings.append(
                    _finding("blocker", "FILTER_MISMATCH", f"{review_id} violates frozen filters")
                )
        except BehaviorCohortError as exc:
            findings.append(_finding("blocker", "INCLUDED_TIME_INVALID", str(exc)))

    excluded = [
        item for item in artifact.get("excluded_candidates", []) if isinstance(item, Mapping)
    ]
    if excluded != sorted(excluded, key=_excluded_sort_key):
        findings.append(
            _finding("blocker", "EXCLUDED_ORDER_MISMATCH", "excluded candidates are not canonical")
        )
    for item in excluded:
        reasons = item.get("reason_codes")
        if not isinstance(reasons, list) or reasons != sorted(set(reasons)):
            findings.append(
                _finding("blocker", "EXCLUSION_REASONS_INVALID", "reason codes are not canonical")
            )
            continue
        if set(reasons) - set(EXCLUSION_REASON_REGISTRY):
            findings.append(
                _finding("blocker", "EXCLUSION_REASON_UNKNOWN", "unknown exclusion reason")
            )
            continue
        expected_blocking = any(EXCLUSION_REASON_REGISTRY[value] for value in reasons)
        if item.get("blocking") is not expected_blocking:
            findings.append(
                _finding("blocker", "EXCLUSION_BLOCKING_MISMATCH", "blocking flag is not registry-derived")
            )

    expected_inventory = _source_inventory_from_included(included)
    if artifact.get("source_inventory") != expected_inventory:
        findings.append(
            _finding("blocker", "SOURCE_INVENTORY_MISMATCH", "source inventory is not the included-source closure")
        )
    derived_candidate_ids = {
        str(item.get("review_id") or item.get("candidate_id") or "")
        for item in [*included, *excluded]
        if str(item.get("review_id") or item.get("candidate_id") or "")
        and not str(item.get("candidate_id") or "").startswith("input-bundle:")
    }
    expected_counts = _counts(
        len(derived_candidate_ids), included, excluded, expected_inventory
    )
    if artifact.get("counts") != expected_counts:
        findings.append(
            _finding("blocker", "COUNTS_MISMATCH", "counts do not match cohort arrays")
        )
    expected_release = _release_status(excluded)
    if artifact.get("release_readiness") != expected_release:
        findings.append(
            _finding("blocker", "RELEASE_READINESS_MISMATCH", "release readiness is not exclusion-derived")
        )
    expected_source = _source_status(included, excluded)
    if artifact.get("source_verification") != expected_source:
        findings.append(
            _finding("blocker", "SOURCE_VERIFICATION_MISMATCH", "source verification is not source-derived")
        )
    return _validation(findings)


def validate_behavior_cohort(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Validate arbitrary JSON-like P2G-1 input without raising."""

    if not isinstance(artifact, Mapping):
        return _validation(
            [_finding("blocker", "MALFORMED_BEHAVIOR_COHORT", "cohort must be an object")]
        )
    try:
        return _validate_behavior_cohort_impl(artifact)
    except Exception as exc:
        return _validation(
            [_finding("blocker", "MALFORMED_BEHAVIOR_COHORT", str(exc))]
        )


def replay_validate_behavior_cohort(
    artifact: Mapping[str, Any],
    *,
    episode_reviews: Iterable[Mapping[str, Any]],
    input_bundles: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Rebuild from explicit P2F sources and compare exact canonical bytes."""

    offline = validate_behavior_cohort(artifact)
    findings = list(offline.get("findings", []))
    rebuilt_content_id: str | None = None
    if offline.get("validation_status") != "blocked":
        selection = artifact.get("selection_spec") or {}
        try:
            rebuilt = build_behavior_cohort(
                episode_reviews,
                input_bundles,
                effective_from=str(selection.get("effective_from") or ""),
                effective_to=str(selection.get("effective_to") or ""),
                knowledge_cutoff=str(selection.get("knowledge_cutoff") or ""),
                effective_anchor=str(selection.get("effective_anchor") or ""),
                filters=(selection.get("filters") if isinstance(selection.get("filters"), Mapping) else None),
            )
            rebuilt_content_id = str(rebuilt.get("content_id") or "")
            if canonical_json_bytes(rebuilt) != canonical_json_bytes(artifact):
                findings.append(
                    _finding(
                        "blocker",
                        "SOURCE_REPLAY_MISMATCH",
                        "cohort bytes differ from deterministic P2F source replay",
                    )
                )
        except Exception as exc:
            findings.append(_finding("blocker", "SOURCE_REPLAY_ERROR", str(exc)))
    result = _validation(findings, mode="source_replay")
    result["release_readiness"] = str(
        (artifact.get("release_readiness") or {}).get("status") or "blocked"
    )
    result["source_verification"] = {
        "status": (
            "verified"
            if result["validation_status"] != "blocked"
            and result["release_readiness"] == "ready"
            else "blocked"
        ),
        "verified_content_id": str(artifact.get("content_id") or ""),
        "rebuilt_content_id": rebuilt_content_id,
    }
    return result


def save_behavior_cohort(path: str | Path, artifact: Mapping[str, Any]) -> Path:
    validation = validate_behavior_cohort(artifact)
    if validation["validation_status"] == "blocked":
        raise BehaviorCohortError("refusing to save an invalid behavior cohort")
    try:
        return atomic_create_bytes(path, pretty_json_bytes(artifact))
    except (ArtifactIOError, FileExistsError) as exc:
        raise BehaviorCohortError(str(exc)) from exc


def load_behavior_cohort(path: str | Path) -> dict[str, Any]:
    try:
        return load_json_object(path)
    except ArtifactIOError as exc:
        raise BehaviorCohortError(str(exc)) from exc


def query_behavior_cohort(
    artifact: Mapping[str, Any],
    *,
    episode_id: str | None = None,
    review_id: str | None = None,
    reason_code: str | None = None,
    content_id: str | None = None,
) -> list[Any]:
    validation = validate_behavior_cohort(artifact)
    if validation["validation_status"] == "blocked":
        raise BehaviorCohortError("refusing to query an invalid behavior cohort")
    if content_id is not None and artifact.get("content_id") != content_id:
        return []
    selected = sum(value is not None for value in (episode_id, review_id, reason_code))
    if selected > 1:
        raise BehaviorCohortError(
            "episode_id, review_id and reason_code filters are mutually exclusive"
        )
    if episode_id is not None:
        return [
            deepcopy(dict(item))
            for item in artifact.get("included_reviews", [])
            if isinstance(item, Mapping) and item.get("episode_id") == episode_id
        ]
    if review_id is not None:
        return [
            deepcopy(dict(item))
            for item in artifact.get("included_reviews", [])
            if isinstance(item, Mapping) and item.get("review_id") == review_id
        ]
    if reason_code is not None:
        if reason_code not in EXCLUSION_REASON_REGISTRY:
            raise BehaviorCohortError(f"unknown exclusion reason: {reason_code}")
        return [
            deepcopy(dict(item))
            for item in artifact.get("excluded_candidates", [])
            if isinstance(item, Mapping) and reason_code in item.get("reason_codes", [])
        ]
    return [deepcopy(dict(artifact))]


__all__ = [
    "BUILDER_VERSION",
    "EFFECTIVE_ANCHORS",
    "EXCLUSION_REASON_REGISTRY",
    "EXCLUSION_REGISTRY_VERSION",
    "SCHEMA_VERSION",
    "VALIDATION_SCHEMA_VERSION",
    "BehaviorCohortError",
    "build_behavior_cohort",
    "load_behavior_cohort",
    "query_behavior_cohort",
    "replay_validate_behavior_cohort",
    "save_behavior_cohort",
    "validate_behavior_cohort",
]
