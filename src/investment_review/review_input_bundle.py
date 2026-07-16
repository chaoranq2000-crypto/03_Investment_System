"""Deterministic P2F review-input bundles for one TradeEpisode.

The bundle is a frozen, facts-only input boundary.  It embeds the selected P2C
episode and the exact single-episode P2E-3 slice, rejects look-ahead sources,
and records a source-aware P2E-3 replay before a production bundle can be
marked release-ready.
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
    atomic_write_bytes,
    canonical_json_bytes,
    load_json_object,
    pretty_json_bytes,
)
from .episode_portfolio_context import (
    SCHEMA_VERSION as P2E3_SCHEMA_VERSION,
    VALIDATION_SCHEMA_VERSION as P2E3_VALIDATION_SCHEMA_VERSION,
    replay_validate_episode_portfolio_context,
    validate_episode_portfolio_context,
)
from .episodes import (
    COLLECTION_SCHEMA_VERSION,
    DECISION_LINKAGE_CONTRACT_VERSION,
    EPISODE_SCHEMA_VERSION,
    PROJECTION_VERSION,
    query_episode_collection,
    snapshot_catalog_sort_key,
    validate_episode,
    validate_episode_collection,
)


SCHEMA_VERSION = "p2f.review_input_bundle.v1"
VALIDATION_SCHEMA_VERSION = "p2f.review_input_bundle.validation.v1"

_CONTRACT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "contracts"
    / "P2F_REVIEW_INPUT_BUNDLE_DRAFT.schema.json"
)
_P2E3_CONTRACT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "contracts"
    / "P2E_3_TRADE_EPISODE_PORTFOLIO_CONTEXT_DRAFT.schema.json"
)
_CONTENT_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_WARNING_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_AVAILABILITY = {
    "available",
    "missing",
    "unlinked",
    "ambiguous",
    "stale",
    "unpriced",
    "invalid",
    "not_applicable",
    "withheld_by_cutoff",
}
_AVAILABILITY_PRIORITY = (
    "invalid",
    "ambiguous",
    "withheld_by_cutoff",
    "unlinked",
    "unpriced",
    "stale",
    "missing",
    "not_applicable",
    "available",
)
_SUPPLEMENTAL_KINDS = {
    "note",
    "market_context",
    "outcome",
    "price",
    "classification",
    "order",
    "fill",
    "snapshot",
    "other",
}
_ALLOWED_P2C_BLOCKERS = {"DECISION_LINK_AMBIGUOUS", "DECISION_LINK_INVALID"}
_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
_CANONICALIZATION = {
    "json_profile": "utf8-json-sorted-keys-no-float",
    "sort_version": "p2f.review_input_bundle.sort.v1",
    "hash_algorithm": "sha256",
    "excluded_fields": ["content_id"],
    "array_order": {
        "frozen_sources.episode_snapshot_catalog": "account_id,as_of_date,knowledge_cutoff_at,revision,snapshot_id",
        "frozen_sources.linked_decisions": "source_id,content_id",
        "frozen_sources.supplemental_sources": "source_kind,source_id,content_id",
        "source_requests": "source_kind,source_id,request_basis",
        "excluded_sources": "source_kind,source_id,reason_code",
        "source_inventory": "source_kind,source_id,content_id",
        "warnings": "severity,code,source_ids",
    },
}


class ReviewInputBundleError(ValueError):
    """Raised when a P2F input bundle cannot be built or verified safely."""


def _parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ReviewInputBundleError(f"{field} must be a timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReviewInputBundleError(f"invalid {field}: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewInputBundleError(f"{field} must include a timezone")
    if parsed.microsecond:
        raise ReviewInputBundleError(f"{field} must use whole seconds")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _value_content_id(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _content_id(payload: Mapping[str, Any]) -> str:
    material = deepcopy(dict(payload))
    material.pop("content_id", None)
    return _value_content_id(material)


def _file_sha256(path: str | Path) -> str:
    source = Path(path).resolve()
    if not source.is_file():
        raise ReviewInputBundleError(f"portfolio database does not exist: {source}")
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    main_digest = digest.hexdigest()
    wal_path = Path(str(source) + "-wal")
    if not wal_path.is_file():
        return main_digest
    wal_digest = hashlib.sha256()
    with wal_path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            wal_digest.update(block)
    return hashlib.sha256(
        f"sqlite-main:{main_digest}\nsqlite-wal:{wal_digest.hexdigest()}".encode(
            "ascii"
        )
    ).hexdigest()


def _finding(severity: str, code: str, message: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message}


def _warning_code(value: object, fallback: str = "SOURCE_WARNING") -> str:
    candidate = re.sub(r"[^A-Z0-9_]+", "_", str(value or "").upper()).strip("_")
    if not candidate or not candidate[0].isalpha():
        candidate = fallback
    return candidate


def _warning(
    code: str,
    message: str,
    *,
    severity: str = "warning",
    source_ids: Iterable[object] = (),
) -> dict[str, Any]:
    normalized_severity = severity if severity in _SEVERITY_ORDER else "warning"
    return {
        "code": _warning_code(code),
        "severity": normalized_severity,
        "message": str(message),
        "source_ids": sorted({str(item) for item in source_ids if str(item)}),
    }


def _merge_availability(*values: object) -> str:
    normalized = {
        str(value)
        for value in values
        if str(value) in _AVAILABILITY
    }
    return next(
        (value for value in _AVAILABILITY_PRIORITY if value in normalized),
        "available",
    )


def _sorted_warnings(values: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[bytes, dict[str, Any]] = {}
    for value in values:
        normalized = {
            "code": _warning_code(value.get("code")),
            "severity": (
                str(value.get("severity"))
                if str(value.get("severity")) in _SEVERITY_ORDER
                else "warning"
            ),
            "message": str(value.get("message") or value.get("code") or "warning"),
            "source_ids": sorted(
                {str(item) for item in value.get("source_ids", []) if str(item)}
            ),
        }
        unique[canonical_json_bytes(normalized)] = normalized
    return sorted(
        unique.values(),
        key=lambda item: (
            item["severity"],
            item["code"],
            canonical_json_bytes(item["source_ids"]),
            item["message"],
        ),
    )


def _source_ids_from_warning(value: Mapping[str, Any]) -> list[str]:
    result = {
        str(item)
        for item in value.get("source_ids", [])
        if item not in (None, "")
    }
    for ref in value.get("source_refs", []):
        if isinstance(ref, Mapping) and ref.get("source_id") not in (None, ""):
            result.add(str(ref["source_id"]))
    for ref in value.get("related_refs", []):
        if ref not in (None, ""):
            result.add(str(ref))
    return sorted(result)


def _upstream_warning(value: Mapping[str, Any]) -> dict[str, Any]:
    severity = str(value.get("severity") or "warning")
    if severity == "blocker":
        severity = "error"
    return _warning(
        str(value.get("code") or "UPSTREAM_WARNING"),
        str(value.get("message") or value.get("code") or "upstream warning"),
        severity=severity,
        source_ids=_source_ids_from_warning(value),
    )


@lru_cache(maxsize=1)
def _contract_validator() -> Draft202012Validator:
    try:
        schema = json.loads(_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewInputBundleError(f"cannot load P2F input schema: {exc}") from exc
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


@lru_cache(maxsize=8)
def _p2e3_definition_validator(definition: str) -> Draft202012Validator:
    try:
        upstream = json.loads(
            _P2E3_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewInputBundleError(
            f"cannot load P2E-3 contract schema: {exc}"
        ) from exc
    definitions = upstream.get("$defs")
    if not isinstance(definitions, Mapping) or definition not in definitions:
        raise ReviewInputBundleError(
            f"P2E-3 contract definition is unavailable: {definition}"
        )
    schema = {
        "$schema": upstream.get(
            "$schema", "https://json-schema.org/draft/2020-12/schema"
        ),
        "$defs": definitions,
        "$ref": f"#/$defs/{definition}",
    }
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _schema_path(error: Any) -> str:
    parts = [str(item) for item in error.absolute_path]
    return "$" + "".join(
        f"[{part}]" if part.isdigit() else f".{part}" for part in parts
    )


def _source_id(payload: Mapping[str, Any], *, decision: bool = False) -> str:
    keys = (
        ("source_id", "decision_id", "id")
        if decision
        else ("source_id", "id", "decision_id", "note_id")
    )
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    raise ReviewInputBundleError("source_id is required")


def _availability(payload: Mapping[str, Any]) -> str:
    availability = payload.get("availability")
    status = payload.get("status")
    if (
        availability not in (None, "")
        and status not in (None, "")
        and str(availability) != str(status)
    ):
        raise ReviewInputBundleError(
            "source status and availability must agree when both are supplied"
        )
    value = str(availability or status or "available")
    if value not in _AVAILABILITY:
        raise ReviewInputBundleError(f"unsupported source availability: {value}")
    return value


def _source_warning_codes(payload: Mapping[str, Any]) -> list[str]:
    raw = payload.get("warning_codes", [])
    if raw in (None, ""):
        return []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ReviewInputBundleError("warning_codes must be an array")
    return sorted({_warning_code(item) for item in raw})


def _normalize_source_envelope(
    raw: Mapping[str, Any],
    *,
    expected_kind: str | None,
    decision: bool,
    field: str,
) -> dict[str, Any]:
    aliases = {
        "known_at",
        "knowledge_cutoff",
        "recorded_at",
        "occurred_at",
        "as_of",
        "observed_at",
    }
    present_aliases = sorted(key for key in aliases if raw.get(key) not in (None, ""))
    if present_aliases:
        raise ReviewInputBundleError(
            f"{field} must use only effective_at/knowledge_at; aliases present: "
            + ", ".join(present_aliases)
        )
    source_id = _source_id(raw, decision=decision)
    source_kind = str(raw.get("source_kind") or "")
    if expected_kind and source_kind != expected_kind:
        raise ReviewInputBundleError(
            f"{field}.source_kind must be {expected_kind!r}"
        )
    if not expected_kind and source_kind not in _SUPPLEMENTAL_KINDS:
        raise ReviewInputBundleError(
            f"unsupported supplemental source kind: {source_kind}"
        )
    effective = _parse_timestamp(raw.get("effective_at"), f"{field}.effective_at")
    known = _parse_timestamp(raw.get("knowledge_at"), f"{field}.knowledge_at")
    if known < effective:
        raise ReviewInputBundleError(
            f"{field}.knowledge_at cannot precede effective_at"
        )
    payload = raw.get("payload")
    if not isinstance(payload, Mapping):
        raise ReviewInputBundleError(f"{field}.payload must be an object")
    payload_copy = deepcopy(dict(payload))
    payload_content_id = _value_content_id(payload_copy)
    supplied_content_id = raw.get("content_id")
    if supplied_content_id not in (None, "", payload_content_id):
        raise ReviewInputBundleError(
            f"{field}.content_id does not match its canonical payload"
        )
    wrapper: dict[str, Any] = {
        "source_id": source_id,
        "source_kind": source_kind,
        "payload_content_id": payload_content_id,
        "content_id": "",
        "availability": _availability(raw),
        "effective_at": _iso(effective),
        "knowledge_at": _iso(known),
        "locator": str(raw.get("locator") or ""),
        "warning_codes": _source_warning_codes(raw),
        "payload": payload_copy,
    }
    wrapper["content_id"] = _wrapped_source_content_id(wrapper)
    return wrapper


def _source_request_record(
    *,
    source_id: str,
    source_kind: str,
    request_basis: str,
    supplied: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = supplied.get("payload") if isinstance(supplied, Mapping) else None
    return {
        "source_id": source_id,
        "source_kind": source_kind,
        "request_basis": request_basis,
        "provided": supplied is not None,
        "payload_content_id": (
            _value_content_id(payload) if isinstance(payload, Mapping) else None
        ),
    }


def _excluded_source_record(
    wrapper: Mapping[str, Any], *, reason_code: str
) -> dict[str, Any]:
    return {
        "source_id": str(wrapper.get("source_id") or ""),
        "source_kind": str(wrapper.get("source_kind") or ""),
        "reason_code": reason_code,
        "effective_at": str(wrapper.get("effective_at") or ""),
        "knowledge_at": str(wrapper.get("knowledge_at") or ""),
        "payload_content_id": str(wrapper.get("payload_content_id") or ""),
        "locator": str(wrapper.get("locator") or ""),
    }


def _wrapped_source_content_id(wrapper: Mapping[str, Any]) -> str:
    material = {
        "source_id": str(wrapper.get("source_id") or ""),
        "source_kind": str(wrapper.get("source_kind") or ""),
        "payload_content_id": str(wrapper.get("payload_content_id") or ""),
        "availability": str(wrapper.get("availability") or ""),
        "effective_at": str(wrapper.get("effective_at") or ""),
        "knowledge_at": str(wrapper.get("knowledge_at") or ""),
        "locator": str(wrapper.get("locator") or ""),
        "warning_codes": sorted(
            {_warning_code(item) for item in wrapper.get("warning_codes", [])}
        ),
        "payload": deepcopy(dict(wrapper.get("payload") or {})),
    }
    if wrapper.get("source_kind") == "decision":
        material["source_availability"] = str(
            wrapper.get("source_availability") or ""
        )
        material["source_warning_codes"] = sorted(
            {
                _warning_code(item)
                for item in wrapper.get("source_warning_codes", [])
            }
        )
        material["decision_link_refs"] = deepcopy(
            list(wrapper.get("decision_link_refs") or [])
        )
    return _value_content_id(material)


def _decision_link_matches(
    link: Mapping[str, Any],
    *,
    source_id: str,
    event_id: str,
    relation: str,
    effective_at: datetime,
    knowledge_at: datetime,
) -> bool:
    try:
        return (
            str(link.get("decision_id") or "") == source_id
            and str(link.get("container_event_id") or "") == event_id
            and str(link.get("event_id") or "") == event_id
            and str(link.get("relation") or "") == relation
            and str(link.get("link_source") or "") == "decision_event_links"
            and _parse_timestamp(
                link.get("effective_at"), "decision_link.effective_at"
            )
            == effective_at
            and _parse_timestamp(
                link.get("known_at"), "decision_link.known_at"
            )
            == knowledge_at
        )
    except ReviewInputBundleError:
        return False


def _normalize_decisions(
    episode: Mapping[str, Any],
    decision_sources: Iterable[Mapping[str, Any]],
    *,
    review_cutoff: datetime,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    linkage = (
        episode.get("decision_linkage")
        if isinstance(episode.get("decision_linkage"), Mapping)
        else {}
    )
    decision_refs = sorted(
        {
            str(item)
            for item in linkage.get("decision_refs", [])
            if isinstance(item, str) and item
        }
    )
    decision_links = [
        dict(item)
        for item in linkage.get("decision_links", [])
        if isinstance(item, Mapping)
    ]
    if decision_refs and not decision_links:
        raise ReviewInputBundleError(
            "P2C episode lacks canonical decision_links evidence; rebuild P2C"
        )
    links_by_decision: dict[str, list[dict[str, Any]]] = {}
    for link in decision_links:
        decision_id = str(link.get("decision_id") or "")
        if decision_id:
            links_by_decision.setdefault(decision_id, []).append(link)
    if decision_refs != sorted(links_by_decision):
        raise ReviewInputBundleError(
            "P2C decision_refs do not close over canonical decision_links"
        )
    supplied: dict[str, dict[str, Any]] = {}
    for raw in decision_sources:
        if not isinstance(raw, Mapping):
            raise ReviewInputBundleError("decision_sources must contain objects")
        payload = dict(raw)
        source_id = _source_id(payload, decision=True)
        if source_id not in links_by_decision:
            raise ReviewInputBundleError(
                f"Decision {source_id!r} is not explicitly linked by the episode"
            )
        if source_id in supplied and canonical_json_bytes(supplied[source_id]) != canonical_json_bytes(
            payload
        ):
            raise ReviewInputBundleError(
                f"conflicting Decision source content for {source_id}"
            )
        supplied[source_id] = payload

    requests = [
        _source_request_record(
            source_id=source_id,
            source_kind="decision",
            request_basis="p2c_decision_link",
            supplied=supplied.get(source_id),
        )
        for source_id in decision_refs
    ]

    included: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    linkage_status = str(linkage.get("status") or "unlinked")
    episode_events = {
        str(item.get("event_id")): item
        for item in episode.get("event_refs", [])
        if isinstance(item, Mapping) and item.get("event_id")
    }
    linkage_availability = {
        "linked": "available",
        "ambiguous": "ambiguous",
        "invalid": "invalid",
        "unlinked": "unlinked",
    }.get(linkage_status, "missing")
    for source_id in decision_refs:
        if source_id not in supplied:
            warnings.append(
                _warning(
                    "DECISION_SOURCE_MISSING",
                    "An explicitly linked Decision payload was not supplied.",
                    source_ids=[source_id],
                )
            )
            continue
        raw = deepcopy(supplied[source_id])
        if (
            raw.get("decision_id") not in (None, "", source_id)
            or raw.get("source_id") not in (None, "", source_id)
        ):
            raise ReviewInputBundleError(
                f"Decision payload identity does not match explicit ref {source_id}"
            )
        wrapper = _normalize_source_envelope(
            raw,
            expected_kind="decision",
            decision=True,
            field=f"decision[{source_id}]",
        )
        raw_event_ids = raw.get("event_ids")
        raw_event_id = raw.get("event_id")
        relation = str(raw.get("relation") or "").strip()
        if raw_event_ids not in (None, "") and raw_event_id not in (None, ""):
            raise ReviewInputBundleError(
                f"Decision {source_id} must use either event_id or event_ids, not both"
            )
        if raw_event_ids not in (None, ""):
            if not isinstance(raw_event_ids, list) or any(
                not isinstance(item, str) or not item for item in raw_event_ids
            ):
                raise ReviewInputBundleError(
                    f"Decision {source_id}.event_ids must be an array of non-empty strings"
                )
            event_ids = list(raw_event_ids)
            if event_ids != sorted(set(event_ids)):
                raise ReviewInputBundleError(
                    f"Decision {source_id}.event_ids must be sorted and unique"
                )
        elif isinstance(raw_event_id, str) and raw_event_id:
            event_ids = [raw_event_id]
        else:
            event_ids = []
        if not event_ids or not relation:
            warnings.append(
                _warning(
                    "DECISION_EVENT_BINDING_MISSING",
                    "A supplied Decision lacked the explicit event_ids/relation binding required for freezing.",
                    source_ids=[source_id],
                )
            )
            excluded.append(
                _excluded_source_record(
                    wrapper, reason_code="DECISION_EVENT_BINDING_MISSING"
                )
            )
            continue
        expected_event_ids = sorted(
            {
                str(link.get("event_id") or "")
                for link in links_by_decision[source_id]
                if str(link.get("event_id") or "")
            }
        )
        if event_ids != expected_event_ids:
            raise ReviewInputBundleError(
                f"Decision {source_id} event_ids do not close over all canonical P2C links"
            )
        if any(event_id not in episode_events for event_id in event_ids):
            raise ReviewInputBundleError(
                f"Decision {source_id} points outside the selected episode"
            )
        effective = _parse_timestamp(
            wrapper["effective_at"], f"decision[{source_id}].effective_at"
        )
        known = _parse_timestamp(
            wrapper["knowledge_at"], f"decision[{source_id}].knowledge_at"
        )
        if effective > review_cutoff or known > review_cutoff:
            warnings.append(
                _warning(
                    "DECISION_WITHHELD_BY_CUTOFF",
                    "Explicit Decision source was excluded by the review cutoff.",
                    source_ids=[source_id],
                )
            )
            excluded.append(
                _excluded_source_record(
                    wrapper, reason_code="DECISION_WITHHELD_BY_CUTOFF"
                )
            )
            continue
        matching_links = list(links_by_decision[source_id])
        if any(
            not _decision_link_matches(
                link,
                source_id=source_id,
                event_id=str(link.get("event_id") or ""),
                relation=relation,
                effective_at=effective,
                knowledge_at=known,
            )
            for link in matching_links
        ):
            raise ReviewInputBundleError(
                f"Decision {source_id!r} binding/times do not match canonical P2C decision_links"
            )
        wrapper["source_availability"] = wrapper["availability"]
        wrapper["source_warning_codes"] = list(wrapper["warning_codes"])
        link_refs: list[dict[str, Any]] = []
        aggregate_warning_codes = set(wrapper["warning_codes"])
        for link in matching_links:
            event_id = str(link.get("event_id") or "")
            event_time = _parse_timestamp(
                episode_events[event_id].get("effective_at"),
                f"episode.event_refs[{event_id}].effective_at",
            )
            link_availability = _merge_availability(
                wrapper["availability"], linkage_availability
            )
            link_warning_codes: set[str] = set()
            if relation != "execution":
                link_availability = _merge_availability(
                    link_availability, "invalid"
                )
                link_warning_codes.add("DECISION_LINK_RELATION_INVALID")
            if known > event_time:
                link_availability = _merge_availability(
                    link_availability, "invalid"
                )
                link_warning_codes.add("DECISION_KNOWN_AFTER_LINKED_EVENT")
            aggregate_warning_codes.update(link_warning_codes)
            link_refs.append(
                {
                    "event_id": event_id,
                    "relation": relation,
                    "link_content_id": _value_content_id(link),
                    "availability": link_availability,
                    "warning_codes": sorted(link_warning_codes),
                }
            )
        if "DECISION_KNOWN_AFTER_LINKED_EVENT" in aggregate_warning_codes:
            warnings.append(
                _warning(
                    "DECISION_KNOWN_AFTER_LINKED_EVENT",
                    "The Decision became known after at least one explicitly linked event and cannot support that execution comparison.",
                    source_ids=[source_id],
                )
            )
        if "DECISION_LINK_RELATION_INVALID" in aggregate_warning_codes:
            warnings.append(
                _warning(
                    "DECISION_LINK_RELATION_INVALID",
                    "The explicit Decision relation is not an execution link.",
                    source_ids=[source_id],
                )
            )
        wrapper["decision_link_refs"] = link_refs
        wrapper["warning_codes"] = sorted(aggregate_warning_codes)
        wrapper["availability"] = _merge_availability(
            wrapper["availability"],
            linkage_availability,
            *(item["availability"] for item in link_refs),
        )
        wrapper["content_id"] = _wrapped_source_content_id(wrapper)
        included.append(wrapper)
    included.sort(key=lambda item: (item["source_id"], item["content_id"]))
    excluded.sort(
        key=lambda item: (
            item["source_kind"],
            item["source_id"],
            item["reason_code"],
        )
    )
    return included, warnings, requests, excluded


def _normalize_supplemental(
    values: Iterable[Mapping[str, Any]], *, review_cutoff: datetime
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    sources: dict[str, dict[str, Any]] = {}
    for raw in values:
        if not isinstance(raw, Mapping):
            raise ReviewInputBundleError("supplemental_sources must contain objects")
        payload = dict(raw)
        source_id = _source_id(payload)
        if source_id in sources and canonical_json_bytes(sources[source_id]) != canonical_json_bytes(
            payload
        ):
            raise ReviewInputBundleError(
                f"conflicting supplemental source content for {source_id}"
            )
        sources[source_id] = payload

    included: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    requests = [
        _source_request_record(
            source_id=source_id,
            source_kind=str(payload.get("source_kind") or ""),
            request_basis="caller_supplemental",
            supplied=payload,
        )
        for source_id, payload in sorted(sources.items())
    ]
    excluded: list[dict[str, Any]] = []
    for source_id, payload in sorted(sources.items()):
        wrapper = _normalize_source_envelope(
            payload,
            expected_kind=None,
            decision=False,
            field=f"supplemental[{source_id}]",
        )
        source_kind = str(wrapper["source_kind"])
        effective = _parse_timestamp(
            wrapper["effective_at"], f"supplemental[{source_id}].effective_at"
        )
        known = _parse_timestamp(
            wrapper["knowledge_at"], f"supplemental[{source_id}].knowledge_at"
        )
        if effective > review_cutoff or known > review_cutoff:
            warnings.append(
                _warning(
                    f"{source_kind}_withheld_by_cutoff",
                    "Supplemental source was excluded by the review cutoff.",
                    source_ids=[source_id],
                )
            )
            excluded.append(
                _excluded_source_record(
                    wrapper,
                    reason_code=f"{source_kind.upper()}_WITHHELD_BY_CUTOFF",
                )
            )
            continue
        included.append(wrapper)
    included.sort(
        key=lambda item: (
            item["source_kind"],
            item["source_id"],
            item["content_id"],
        )
    )
    excluded.sort(
        key=lambda item: (
            item["source_kind"],
            item["source_id"],
            item["reason_code"],
        )
    )
    return included, warnings, requests, excluded


def _slice_content_id(value: Mapping[str, Any]) -> str:
    material = deepcopy(dict(value))
    material.pop("slice_content_id", None)
    return _value_content_id(material)


def _episode_snapshot_catalog(
    episode_collection: Mapping[str, Any], episode: Mapping[str, Any]
) -> list[dict[str, Any]]:
    referenced_ids = {
        str(item.get("snapshot_ref") or "")
        for item in episode.get("snapshot_links", [])
        if isinstance(item, Mapping) and item.get("snapshot_ref")
    }
    catalog = [
        deepcopy(dict(item))
        for item in episode_collection.get("snapshot_catalog", [])
        if isinstance(item, Mapping)
        and str(item.get("snapshot_id") or "") in referenced_ids
    ]
    catalog_ids = [str(item.get("snapshot_id") or "") for item in catalog]
    if len(catalog_ids) != len(set(catalog_ids)):
        raise ReviewInputBundleError(
            "P2C snapshot catalog contains duplicate referenced snapshot IDs"
        )
    if set(catalog_ids) != referenced_ids:
        missing = sorted(referenced_ids - set(catalog_ids))
        raise ReviewInputBundleError(
            "P2C episode snapshot links do not close over snapshot_catalog: "
            + ", ".join(missing)
        )
    return sorted(catalog, key=snapshot_catalog_sort_key)


def _episode_portfolio_slice(
    artifact: Mapping[str, Any], *, episode_id: str
) -> dict[str, Any]:
    source_binding = (
        artifact.get("source_binding")
        if isinstance(artifact.get("source_binding"), Mapping)
        else {}
    )
    selection = (
        source_binding.get("selection")
        if isinstance(source_binding.get("selection"), Mapping)
        else {}
    )
    resolved = sorted(
        str(item) for item in selection.get("resolved_episode_ids", []) if str(item)
    )
    if episode_id not in resolved:
        raise ReviewInputBundleError(
            "P2E-3 artifact does not resolve the selected episode"
        )
    material_events = [
        deepcopy(dict(item))
        for item in source_binding.get("material_events", [])
        if isinstance(item, Mapping) and item.get("episode_id") == episode_id
    ]
    contexts = [
        deepcopy(dict(item))
        for item in artifact.get("contexts", [])
        if isinstance(item, Mapping) and item.get("episode_id") == episode_id
    ]
    deltas = [
        deepcopy(dict(item))
        for item in artifact.get("deltas", [])
        if isinstance(item, Mapping) and item.get("episode_id") == episode_id
    ]
    scoped_binding = deepcopy(dict(source_binding))
    scoped_binding["selection"] = {
        "mode": "explicit",
        "requested_episode_ids": [episode_id],
        "resolved_episode_ids": [episode_id],
    }
    scoped_binding["material_events"] = material_events
    scoped_binding["material_event_set_content_id"] = _value_content_id(
        material_events
    )
    selected_source_ids = {
        str(item.get("event_id") or "") for item in material_events
    }
    selected_source_ids.update(
        str(item.get("context_id") or "") for item in contexts
    )
    selected_source_ids.update(str(item.get("delta_id") or "") for item in deltas)
    for context in contexts:
        snapshot = (
            context.get("portfolio_snapshot")
            if isinstance(context.get("portfolio_snapshot"), Mapping)
            else {}
        )
        selected_source_ids.add(str(snapshot.get("snapshot_id") or ""))
    selected_source_ids.discard("")
    scoped_warnings: list[dict[str, Any]] = []
    for item in artifact.get("warnings", []):
        if not isinstance(item, Mapping):
            continue
        referenced_ids = {
            str(ref.get("source_id") or "")
            for ref in item.get("source_refs", [])
            if isinstance(ref, Mapping)
        }
        referenced_ids.update(
            str(value)
            for key in ("related_refs", "target_ids", "source_ids")
            for value in item.get(key, [])
            if str(value)
        )
        if referenced_ids & selected_source_ids:
            scoped = deepcopy(dict(item))
            scoped["scope"] = "episode"
            scoped_warnings.append(scoped)
        elif not referenced_ids:
            scoped = deepcopy(dict(item))
            scoped["scope"] = "collection"
            scoped_warnings.append(scoped)
    result: dict[str, Any] = {
        "schema_version": P2E3_SCHEMA_VERSION,
        "artifact_content_id": str(artifact.get("content_id") or ""),
        "episode_id": episode_id,
        "episode_artifact_ref": deepcopy(dict(artifact.get("episode_artifact_ref") or {})),
        "source_binding": scoped_binding,
        "as_of": str(artifact.get("as_of") or ""),
        "knowledge_cutoff": str(artifact.get("knowledge_cutoff") or ""),
        "metric_registry_version": str(artifact.get("metric_registry_version") or ""),
        "material_events": material_events,
        "contexts": contexts,
        "deltas": deltas,
        "warnings": scoped_warnings,
        "slice_content_id": "",
    }
    result["slice_content_id"] = _slice_content_id(result)
    return result


def _inventory_item(
    *,
    source_id: str,
    source_kind: str,
    status: str,
    effective_at: str | None,
    knowledge_at: str,
    content_id: str,
    locator: str,
    frozen_pointer: str,
    warning_codes: Iterable[str] = (),
    effective_date: str | None = None,
    effective_precision: str = "second",
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_kind": source_kind,
        "status": status,
        "effective_at": effective_at,
        "effective_date": effective_date,
        "effective_precision": effective_precision,
        "knowledge_at": knowledge_at,
        "content_id": content_id,
        "locator": locator,
        "frozen_pointer": frozen_pointer,
        "warning_codes": sorted({_warning_code(item) for item in warning_codes}),
    }


def _context_status(context: Mapping[str, Any]) -> tuple[str, list[str]]:
    portfolio = (
        context.get("portfolio_snapshot")
        if isinstance(context.get("portfolio_snapshot"), Mapping)
        else {}
    )
    raw = str(portfolio.get("status") or "missing")
    status = {
        "exact": "available",
        "replayed": "available",
        "partial": "ambiguous",
    }.get(raw, raw if raw in _AVAILABILITY else "available")
    codes = {
        _warning_code(item)
        for item in (
            warning.get("code")
            for warning in context.get("warnings", [])
            if isinstance(warning, Mapping)
        )
    }
    source_binding = (
        context.get("source_binding")
        if isinstance(context.get("source_binding"), Mapping)
        else {}
    )
    snapshot_binding = (
        source_binding.get("snapshot_binding")
        if isinstance(source_binding.get("snapshot_binding"), Mapping)
        else {}
    )
    ceiling = str(snapshot_binding.get("metric_availability_ceiling") or "")
    if ceiling == "partial":
        status = _merge_availability(status, "ambiguous")
        codes.add("PORTFOLIO_CURSOR_SCOPE_LIMITED")
    elif ceiling == "none":
        status = _merge_availability(status, "missing")
    metric_availability: set[str] = set()
    for metric in (context.get("metrics") or {}).values():
        if isinstance(metric, Mapping):
            metric_availability.add(str(metric.get("availability") or ""))
            codes.update(_warning_code(item) for item in metric.get("warning_codes", []))
    if "invalid" in metric_availability:
        status = _merge_availability(status, "invalid")
    if "partial" in metric_availability:
        status = _merge_availability(status, "ambiguous")
    if "missing" in metric_availability:
        non_missing = metric_availability - {"missing", ""}
        status = _merge_availability(
            status,
            "ambiguous" if non_missing else "missing",
        )
    if "TARGET_POSITION_UNPRICED" in codes or "MISSING_PRICE" in codes:
        status = _merge_availability(status, "unpriced")
    if "STALE_POSITION" in codes:
        status = _merge_availability(status, "stale")
    return status, sorted(codes)


def _ordering_ambiguity(
    portfolio_slice: Mapping[str, Any],
) -> tuple[set[str], set[str]]:
    event_ids: set[str] = set()
    codes: set[str] = set()
    ordering_codes = {"AMBIGUOUS_EVENT_ORDER", "SAME_SECOND_AMBIGUOUS"}
    for context in portfolio_slice.get("contexts", []):
        if not isinstance(context, Mapping):
            continue
        context_codes = {
            str(item.get("code") or "")
            for item in context.get("warnings", [])
            if isinstance(item, Mapping)
        } & ordering_codes
        if context_codes:
            codes.update(context_codes)
            anchor = context.get("anchor")
            if isinstance(anchor, Mapping) and anchor.get("event_id"):
                event_ids.add(str(anchor["event_id"]))
    for warning in portfolio_slice.get("warnings", []):
        if not isinstance(warning, Mapping) or warning.get("scope") == "collection":
            continue
        code = str(warning.get("code") or "")
        if code not in ordering_codes:
            continue
        codes.add(code)
        for ref in warning.get("source_refs", []):
            if isinstance(ref, Mapping) and ref.get("source_id"):
                event_ids.add(str(ref["source_id"]))
        for key in ("related_refs", "target_ids", "source_ids"):
            for value in warning.get(key, []):
                if str(value):
                    event_ids.add(str(value))
    material_ids = {
        str(item.get("event_id") or "")
        for item in portfolio_slice.get("material_events", [])
        if isinstance(item, Mapping) and item.get("event_id")
    }
    return event_ids & material_ids, codes


def _source_inventory(
    episode: Mapping[str, Any],
    episode_snapshot_catalog: Sequence[Mapping[str, Any]],
    portfolio_slice: Mapping[str, Any],
    linked_decisions: Sequence[Mapping[str, Any]],
    supplemental_sources: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    episode_id = str(episode.get("episode_id") or "")
    episode_end = str(
        episode.get("closed_at") or episode.get("cutoff_at") or episode.get("opened_at")
    )
    episode_known = str(episode.get("cutoff_at") or episode_end)
    values: list[dict[str, Any]] = [
        _inventory_item(
            source_id=episode_id,
            source_kind="trade_episode",
            status="available",
            effective_at=episode_end,
            knowledge_at=episode_known,
            content_id="sha256:"
            + str(
                (episode.get("lineage") or {}).get("canonical_content_digest")
                if isinstance(episode.get("lineage"), Mapping)
                else ""
            ),
            locator=f"p2c:episode/{episode_id}",
            frozen_pointer="/frozen_sources/episode",
            warning_codes=[
                str(item.get("code"))
                for item in (episode.get("validation") or {}).get("findings", [])
                if isinstance(item, Mapping)
            ],
        )
    ]
    for index, snapshot in enumerate(episode_snapshot_catalog):
        snapshot_id = str(snapshot.get("snapshot_id") or "")
        knowledge_at = str(snapshot.get("knowledge_cutoff_at") or "")
        values.append(
            _inventory_item(
                source_id=snapshot_id,
                source_kind="snapshot",
                status="available",
                effective_at=None,
                effective_date=str(snapshot.get("as_of_date") or ""),
                effective_precision="date",
                knowledge_at=knowledge_at,
                content_id=_value_content_id(snapshot),
                locator=str(
                    snapshot.get("source_path")
                    or f"p2c:snapshot/{snapshot_id}"
                ),
                frozen_pointer=f"/frozen_sources/episode_snapshot_catalog/{index}",
            )
        )
    if portfolio_slice.get("status") != "missing":
        slice_id = str(portfolio_slice.get("slice_content_id") or "")
        as_of = str(portfolio_slice.get("as_of") or "")
        known = str(portfolio_slice.get("knowledge_cutoff") or "")
        values.append(
            _inventory_item(
                source_id=f"{episode_id}:portfolio_context_slice",
                source_kind="portfolio_context_slice",
                status="available",
                effective_at=as_of,
                knowledge_at=known,
                content_id=slice_id,
                locator=f"p2e3:{portfolio_slice.get('artifact_content_id')}#episode/{episode_id}",
                frozen_pointer="/frozen_sources/portfolio_context_episode_slice",
                warning_codes=[
                    str(item.get("code"))
                    for item in portfolio_slice.get("warnings", [])
                    if isinstance(item, Mapping)
                ],
            )
        )
        ambiguous_event_ids, ordering_codes = _ordering_ambiguity(portfolio_slice)
        for index, event in enumerate(portfolio_slice.get("material_events", [])):
            event_id = str(event.get("event_id") or f"event:{index}")
            values.append(
                _inventory_item(
                    source_id=event_id,
                    source_kind="material_event",
                    status=(
                        "ambiguous" if event_id in ambiguous_event_ids else "available"
                    ),
                    effective_at=str(event.get("event_at") or ""),
                    knowledge_at=str(event.get("known_at") or ""),
                    content_id=_value_content_id(event),
                    locator=f"p2e3:material_event/{event.get('event_id')}",
                    frozen_pointer=f"/frozen_sources/portfolio_context_episode_slice/material_events/{index}",
                    warning_codes=(
                        ordering_codes if event_id in ambiguous_event_ids else ()
                    ),
                )
            )
        context_by_id: dict[str, Mapping[str, Any]] = {}
        for index, context in enumerate(portfolio_slice.get("contexts", [])):
            context_id = str(context.get("context_id") or f"context:{index}")
            context_by_id[context_id] = context
            anchor = context.get("anchor") if isinstance(context.get("anchor"), Mapping) else {}
            status, codes = _context_status(context)
            values.append(
                _inventory_item(
                    source_id=context_id,
                    source_kind="context",
                    status=status,
                    effective_at=str(anchor.get("as_of") or anchor.get("event_at") or ""),
                    knowledge_at=str(anchor.get("knowledge_cutoff") or ""),
                    content_id=_value_content_id(context),
                    locator=f"p2e3:context/{context_id}",
                    frozen_pointer=f"/frozen_sources/portfolio_context_episode_slice/contexts/{index}",
                    warning_codes=codes,
                )
            )
        for index, delta in enumerate(portfolio_slice.get("deltas", [])):
            delta_id = str(delta.get("delta_id") or f"delta:{index}")
            target = context_by_id.get(str(delta.get("to_context_id") or ""), {})
            anchor = target.get("anchor") if isinstance(target.get("anchor"), Mapping) else {}
            values.append(
                _inventory_item(
                    source_id=delta_id,
                    source_kind="delta",
                    status=(
                        "not_applicable"
                        if str(delta.get("availability")) == "not_comparable"
                        else str(delta.get("availability"))
                        if str(delta.get("availability")) in _AVAILABILITY
                        else "ambiguous"
                    ),
                    effective_at=str(anchor.get("as_of") or anchor.get("event_at") or ""),
                    knowledge_at=str(anchor.get("knowledge_cutoff") or ""),
                    content_id=_value_content_id(delta),
                    locator=f"p2e3:delta/{delta_id}",
                    frozen_pointer=f"/frozen_sources/portfolio_context_episode_slice/deltas/{index}",
                    warning_codes=delta.get("warning_codes", []),
                )
            )
    for index, decision in enumerate(linked_decisions):
        values.append(
            _inventory_item(
                source_id=str(decision["source_id"]),
                source_kind="decision",
                status=str(decision["availability"]),
                effective_at=str(decision["effective_at"]),
                knowledge_at=str(decision["knowledge_at"]),
                content_id=str(decision["content_id"]),
                locator=str(decision.get("locator") or f"decision:{decision['source_id']}"),
                frozen_pointer=f"/frozen_sources/linked_decisions/{index}",
                warning_codes=decision.get("warning_codes", []),
            )
        )
    for index, source in enumerate(supplemental_sources):
        values.append(
            _inventory_item(
                source_id=str(source["source_id"]),
                source_kind=str(source["source_kind"]),
                status=str(source["availability"]),
                effective_at=str(source["effective_at"]),
                knowledge_at=str(source["knowledge_at"]),
                content_id=str(source["content_id"]),
                locator=str(source.get("locator") or f"{source['source_kind']}:{source['source_id']}"),
                frozen_pointer=f"/frozen_sources/supplemental_sources/{index}",
                warning_codes=source.get("warning_codes", []),
            )
        )
    unique: dict[bytes, dict[str, Any]] = {
        canonical_json_bytes(item): item for item in values
    }
    source_ids = [str(item.get("source_id") or "") for item in unique.values()]
    duplicate_ids = sorted(
        {source_id for source_id in source_ids if source_ids.count(source_id) > 1}
    )
    if duplicate_ids:
        raise ReviewInputBundleError(
            "source_id must be globally unique within a bundle: "
            + ", ".join(duplicate_ids)
        )
    return sorted(
        unique.values(),
        key=lambda item: (
            item["source_kind"],
            item["source_id"],
            item["content_id"],
            item["frozen_pointer"],
        ),
    )


def _section(
    status: str,
    reason: str,
    *,
    source_ids: Iterable[object] = (),
    warning_codes: Iterable[object] = (),
) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "source_ids": sorted({str(item) for item in source_ids if str(item)}),
        "warning_codes": sorted({_warning_code(item) for item in warning_codes}),
    }


def _portfolio_section(portfolio_slice: Mapping[str, Any]) -> dict[str, Any]:
    if portfolio_slice.get("status") == "missing":
        return _section(
            "missing",
            str(portfolio_slice.get("reason") or "P2E-3 context is missing"),
            warning_codes=["PORTFOLIO_CONTEXT_MISSING"],
        )
    contexts = [
        item for item in portfolio_slice.get("contexts", []) if isinstance(item, Mapping)
    ]
    statuses: list[str] = []
    codes: set[str] = set()
    for context in contexts:
        status, context_codes = _context_status(context)
        statuses.append(status)
        codes.update(context_codes)
    if not contexts:
        status = "missing"
    elif "missing" in statuses and any(item != "missing" for item in statuses):
        status = "ambiguous"
    else:
        status = _merge_availability(*statuses)
    return _section(
        status,
        "P2E-3 episode slice is frozen with its original availability states.",
        source_ids=[item.get("context_id") for item in contexts],
        warning_codes=codes,
    )


def _optional_section(
    sources: Sequence[Mapping[str, Any]],
    kinds: set[str],
    *,
    label: str,
    withheld_warning_codes: Iterable[str] = (),
) -> dict[str, Any]:
    selected = [item for item in sources if item.get("source_kind") in kinds]
    if not selected:
        withheld = sorted(
            {
                str(item)
                for item in withheld_warning_codes
                if str(item).endswith("_WITHHELD_BY_CUTOFF")
            }
        )
        if withheld:
            return _section(
                "withheld_by_cutoff",
                f"{label} sources existed but exceeded review_cutoff.",
                warning_codes=withheld,
            )
        return _section("missing", f"No {label} source was available at review_cutoff.")
    statuses = [str(item.get("availability") or "available") for item in selected]
    status = _merge_availability(*statuses)
    return _section(
        status,
        f"{label} sources are frozen without reinterpretation.",
        source_ids=[item.get("source_id") for item in selected],
        warning_codes=[
            code for item in selected for code in item.get("warning_codes", [])
        ],
    )


def _section_availability(
    episode: Mapping[str, Any],
    portfolio_slice: Mapping[str, Any],
    linked_decisions: Sequence[Mapping[str, Any]],
    supplemental_sources: Sequence[Mapping[str, Any]],
    source_warnings: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    episode_id = str(episode.get("episode_id") or "")
    event_ids = [
        str(item.get("event_id"))
        for item in episode.get("event_refs", [])
        if isinstance(item, Mapping) and item.get("event_id")
    ]
    decision_status = str(
        (episode.get("decision_linkage") or {}).get("status") or "unlinked"
    )
    warning_codes = {
        str(item.get("code") or "")
        for item in source_warnings
        if isinstance(item, Mapping)
    }
    ambiguous_event_ids, ordering_codes = _ordering_ambiguity(portfolio_slice)
    linkage_availability = {
        "linked": "available",
        "ambiguous": "ambiguous",
        "invalid": "invalid",
        "unlinked": "unlinked",
    }.get(decision_status, "missing")
    warning_availability: list[str] = []
    if "DECISION_KNOWN_AFTER_LINKED_EVENT" in warning_codes:
        warning_availability.append("invalid")
    if "DECISION_EVENT_BINDING_MISSING" in warning_codes:
        warning_availability.append("ambiguous")
    if "DECISION_WITHHELD_BY_CUTOFF" in warning_codes:
        warning_availability.append("withheld_by_cutoff")
    if "DECISION_SOURCE_MISSING" in warning_codes:
        warning_availability.append("missing")
    execution_status = _merge_availability(
        linkage_availability,
        *(item.get("availability") for item in linked_decisions),
        *warning_availability,
    )
    execution_warning_codes = {
        code
        for code in warning_codes
        if code
        in {
            "DECISION_EVENT_BINDING_MISSING",
            "DECISION_KNOWN_AFTER_LINKED_EVENT",
            "DECISION_SOURCE_MISSING",
            "DECISION_WITHHELD_BY_CUTOFF",
        }
    }
    execution_warning_codes.update(
        code
        for item in linked_decisions
        for code in item.get("warning_codes", [])
    )
    if decision_status in {"ambiguous", "invalid", "unlinked"}:
        execution_warning_codes.add(
            f"DECISION_LINK_{decision_status.upper()}"
        )
    return {
        "timeline": _section(
            (
                "ambiguous"
                if event_ids and ordering_codes
                else "available"
                if event_ids
                else "missing"
            ),
            (
                "Canonical storage order is frozen, but same-time business order remains ambiguous."
                if ordering_codes
                else "P2C event_refs are frozen in canonical episode order."
            ),
            source_ids=event_ids,
            warning_codes=ordering_codes,
        ),
        "security_context": _section(
            "available" if (episode.get("scope") or {}).get("instrument_id") else "missing",
            "P2C episode scope is the security identity source.",
            source_ids=[episode_id],
        ),
        "portfolio_context": _portfolio_section(portfolio_slice),
        "market_context": _optional_section(
            supplemental_sources,
            {"market_context", "price", "classification"},
            label="market context",
            withheld_warning_codes={
                item
                for item in warning_codes
                if item
                in {
                    "MARKET_CONTEXT_WITHHELD_BY_CUTOFF",
                    "PRICE_WITHHELD_BY_CUTOFF",
                    "CLASSIFICATION_WITHHELD_BY_CUTOFF",
                }
            },
        ),
        "outcome_context": _optional_section(
            supplemental_sources,
            {"outcome"},
            label="outcome context",
            withheld_warning_codes={
                item
                for item in warning_codes
                if item == "OUTCOME_WITHHELD_BY_CUTOFF"
            },
        ),
        "execution_consistency": _section(
            execution_status,
            "Only explicit decision_event_links are eligible; no Decision was inferred.",
            source_ids=[item.get("source_id") for item in linked_decisions],
            warning_codes=(
                []
                if execution_status == "available"
                else sorted(execution_warning_codes)
            ),
        ),
    }


def _source_manifest_warnings(
    *,
    source_requests: Sequence[Mapping[str, Any]],
    excluded_sources: Sequence[Mapping[str, Any]],
    linked_decisions: Sequence[Mapping[str, Any]],
    supplemental_sources: Sequence[Mapping[str, Any]],
    portfolio_context_ref: Mapping[str, Any],
    episode_id: str,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for request in source_requests:
        if (
            request.get("source_kind") == "decision"
            and request.get("provided") is False
        ):
            warnings.append(
                _warning(
                    "DECISION_SOURCE_MISSING",
                    "An explicitly linked Decision payload was not supplied.",
                    source_ids=[str(request.get("source_id") or "")],
                )
            )
    excluded_messages = {
        "DECISION_EVENT_BINDING_MISSING": "A supplied Decision lacked the explicit event_ids/relation binding required for freezing.",
        "DECISION_WITHHELD_BY_CUTOFF": "Explicit Decision source was excluded by the review cutoff.",
    }
    for source in excluded_sources:
        reason = str(source.get("reason_code") or "")
        warnings.append(
            _warning(
                reason,
                excluded_messages.get(
                    reason,
                    "Supplemental source was excluded by the review cutoff.",
                ),
                source_ids=[str(source.get("source_id") or "")],
            )
        )
    for source in [*linked_decisions, *supplemental_sources]:
        source_id = str(source.get("source_id") or "")
        source_codes = (
            source.get("source_warning_codes", [])
            if source.get("source_kind") == "decision"
            else source.get("warning_codes", [])
        )
        for code in source_codes:
            warnings.append(
                _warning(
                    str(code),
                    "Upstream source warning was preserved without reinterpretation.",
                    source_ids=[source_id],
                )
            )
        if source.get("source_kind") == "decision":
            link_codes = {
                str(code)
                for link_ref in source.get("decision_link_refs", [])
                if isinstance(link_ref, Mapping)
                for code in link_ref.get("warning_codes", [])
            }
            for code in link_codes:
                message = {
                    "DECISION_KNOWN_AFTER_LINKED_EVENT": "The Decision became known after at least one explicitly linked event and cannot support that execution comparison.",
                    "DECISION_LINK_RELATION_INVALID": "The explicit Decision relation is not an execution link.",
                    "DECISION_EVENT_BINDING_INVALID": "The explicit Decision link points outside the selected episode.",
                }.get(code, "Decision-link warning was preserved without reinterpretation.")
                warnings.append(_warning(code, message, source_ids=[source_id]))
    if portfolio_context_ref.get("status") == "missing":
        warnings.append(
            _warning(
                "P2E3_SOURCE_VERIFICATION_MISSING",
                "P2E-3 context is missing; this bundle is contract-only and not release-ready.",
                severity="error",
                source_ids=[episode_id],
            )
        )
    return warnings


def _build_warnings(
    episode: Mapping[str, Any],
    portfolio_slice: Mapping[str, Any],
    *,
    source_requests: Sequence[Mapping[str, Any]],
    excluded_sources: Sequence[Mapping[str, Any]],
    linked_decisions: Sequence[Mapping[str, Any]],
    supplemental_sources: Sequence[Mapping[str, Any]],
    portfolio_context_ref: Mapping[str, Any],
) -> list[dict[str, Any]]:
    warnings = _source_manifest_warnings(
        source_requests=source_requests,
        excluded_sources=excluded_sources,
        linked_decisions=linked_decisions,
        supplemental_sources=supplemental_sources,
        portfolio_context_ref=portfolio_context_ref,
        episode_id=str(episode.get("episode_id") or ""),
    )
    validation = (
        episode.get("validation")
        if isinstance(episode.get("validation"), Mapping)
        else {}
    )
    warnings.extend(
        _upstream_warning(item)
        for item in validation.get("findings", [])
        if isinstance(item, Mapping)
    )
    if portfolio_slice.get("status") != "missing":
        warnings.extend(
            _upstream_warning(item)
            for item in portfolio_slice.get("warnings", [])
            if isinstance(item, Mapping) and item.get("scope") != "collection"
        )
        for context in portfolio_slice.get("contexts", []):
            if not isinstance(context, Mapping):
                continue
            warnings.extend(
                _upstream_warning(item)
                for item in context.get("warnings", [])
                if isinstance(item, Mapping)
            )
            for metric in (context.get("metrics") or {}).values():
                if not isinstance(metric, Mapping):
                    continue
                warnings.extend(
                    _warning(
                        str(code),
                        f"P2E-3 metric warning propagated for {context.get('context_id')}.",
                        source_ids=[str(context.get("context_id") or "")],
                    )
                    for code in metric.get("warning_codes", [])
                )
    return _sorted_warnings(warnings)


def _validate_source_manifests(
    artifact: Mapping[str, Any],
    *,
    episode: Mapping[str, Any],
    portfolio_slice: Mapping[str, Any],
    linked_decisions: Sequence[Mapping[str, Any]],
    supplemental_sources: Sequence[Mapping[str, Any]],
    review_cutoff: datetime | None,
    findings: list[dict[str, str]],
) -> list[dict[str, Any]]:
    raw_requests = artifact.get("source_requests")
    raw_excluded = artifact.get("excluded_sources")
    requests = (
        [dict(item) for item in raw_requests if isinstance(item, Mapping)]
        if isinstance(raw_requests, list)
        else []
    )
    excluded = (
        [dict(item) for item in raw_excluded if isinstance(item, Mapping)]
        if isinstance(raw_excluded, list)
        else []
    )
    if not isinstance(raw_requests, list) or len(requests) != len(raw_requests):
        findings.append(
            _finding(
                "blocker",
                "SOURCE_REQUEST_MANIFEST_INVALID",
                "source_requests must contain only objects",
            )
        )
    if not isinstance(raw_excluded, list) or len(excluded) != len(raw_excluded):
        findings.append(
            _finding(
                "blocker",
                "EXCLUDED_SOURCE_MANIFEST_INVALID",
                "excluded_sources must contain only objects",
            )
        )
    expected_request_order = sorted(
        requests,
        key=lambda item: (
            str(item.get("source_kind") or ""),
            str(item.get("source_id") or ""),
            str(item.get("request_basis") or ""),
        ),
    )
    expected_excluded_order = sorted(
        excluded,
        key=lambda item: (
            str(item.get("source_kind") or ""),
            str(item.get("source_id") or ""),
            str(item.get("reason_code") or ""),
        ),
    )
    if requests != expected_request_order or excluded != expected_excluded_order:
        findings.append(
            _finding(
                "blocker",
                "SOURCE_MANIFEST_ORDER_MISMATCH",
                "source request/exclusion manifests are not canonical",
            )
        )
    request_ids = [str(item.get("source_id") or "") for item in requests]
    if not all(request_ids) or len(request_ids) != len(set(request_ids)):
        findings.append(
            _finding(
                "blocker",
                "SOURCE_REQUEST_IDENTITY_MISMATCH",
                "source request IDs must be globally unique and non-empty",
            )
        )
    request_by_id = {
        str(item.get("source_id") or ""): item for item in requests
    }
    explicit_decision_ids = sorted(
        str(item)
        for item in (episode.get("decision_linkage") or {}).get(
            "decision_refs", []
        )
        if isinstance(item, str) and item
    )
    decision_request_ids = sorted(
        str(item.get("source_id") or "")
        for item in requests
        if item.get("request_basis") == "p2c_decision_link"
    )
    if decision_request_ids != explicit_decision_ids:
        findings.append(
            _finding(
                "blocker",
                "SOURCE_REQUEST_CLOSURE_MISMATCH",
                "Decision source requests do not equal P2C decision_refs",
            )
        )
    requested_supplemental = (
        artifact.get("build_request", {}).get(
            "requested_supplemental_source_ids", []
        )
        if isinstance(artifact.get("build_request"), Mapping)
        else []
    )
    supplemental_request_ids = sorted(
        str(item.get("source_id") or "")
        for item in requests
        if item.get("request_basis") == "caller_supplemental"
    )
    if supplemental_request_ids != requested_supplemental:
        findings.append(
            _finding(
                "blocker",
                "SOURCE_REQUEST_CLOSURE_MISMATCH",
                "supplemental source requests do not equal build_request",
            )
        )
    frozen_by_id = {
        str(item.get("source_id") or ""): item
        for item in [*linked_decisions, *supplemental_sources]
    }
    excluded_by_id = {
        str(item.get("source_id") or ""): item for item in excluded
    }
    if set(frozen_by_id) & set(excluded_by_id):
        findings.append(
            _finding(
                "blocker",
                "SOURCE_MANIFEST_STATE_CONFLICT",
                "a source cannot be both frozen and excluded",
            )
        )
    if len(excluded_by_id) != len(excluded):
        findings.append(
            _finding(
                "blocker",
                "EXCLUDED_SOURCE_IDENTITY_MISMATCH",
                "excluded source IDs must be unique",
            )
        )
    for source_id, request in request_by_id.items():
        material = frozen_by_id.get(source_id) or excluded_by_id.get(source_id)
        expected_provided = material is not None
        if request.get("provided") is not expected_provided:
            findings.append(
                _finding(
                    "blocker",
                    "SOURCE_REQUEST_STATE_MISMATCH",
                    f"source request state does not close for {source_id}",
                )
            )
        expected_payload_id = (
            str(material.get("payload_content_id") or "")
            if material is not None
            else None
        )
        if request.get("payload_content_id") != expected_payload_id:
            findings.append(
                _finding(
                    "blocker",
                    "SOURCE_REQUEST_HASH_MISMATCH",
                    f"source request payload hash does not close for {source_id}",
                )
            )
        expected_kind = (
            "decision"
            if request.get("request_basis") == "p2c_decision_link"
            else str(material.get("source_kind") or "")
            if material is not None
            else ""
        )
        if request.get("source_kind") != expected_kind:
            findings.append(
                _finding(
                    "blocker",
                    "SOURCE_REQUEST_KIND_MISMATCH",
                    f"source request kind does not close for {source_id}",
                )
            )
    if (set(frozen_by_id) | set(excluded_by_id)) - set(request_by_id):
        findings.append(
            _finding(
                "blocker",
                "SOURCE_REQUEST_CLOSURE_MISMATCH",
                "every frozen/excluded optional source requires a request entry",
            )
        )
    for source_id, source in excluded_by_id.items():
        reason = str(source.get("reason_code") or "")
        request = request_by_id.get(source_id, {})
        source_kind = str(source.get("source_kind") or "")
        request_basis = str(request.get("request_basis") or "")
        try:
            if request_basis == "p2c_decision_link":
                allowed_reasons = {
                    "DECISION_EVENT_BINDING_MISSING",
                    "DECISION_WITHHELD_BY_CUTOFF",
                }
                if source_kind != "decision":
                    raise ReviewInputBundleError(
                        "P2C Decision exclusions must identify a Decision"
                    )
            elif request_basis == "caller_supplemental":
                allowed_reasons = {
                    f"{source_kind.upper()}_WITHHELD_BY_CUTOFF"
                }
            else:
                allowed_reasons = set()
            if reason not in allowed_reasons:
                raise ReviewInputBundleError(
                    "excluded source reason is not allowed for its request basis "
                    f"and source kind: {reason!r}"
                )
            effective = _parse_timestamp(
                source.get("effective_at"),
                f"excluded_sources[{source_id}].effective_at",
            )
            known = _parse_timestamp(
                source.get("knowledge_at"),
                f"excluded_sources[{source_id}].knowledge_at",
            )
            if known < effective:
                raise ReviewInputBundleError(
                    "excluded source knowledge_at precedes effective_at"
                )
            if reason.endswith("_WITHHELD_BY_CUTOFF") and (
                review_cutoff is None
                or (effective <= review_cutoff and known <= review_cutoff)
            ):
                raise ReviewInputBundleError(
                    "withheld source does not exceed review_cutoff"
                )
            if reason == "DECISION_EVENT_BINDING_MISSING" and source.get(
                "source_kind"
            ) != "decision":
                raise ReviewInputBundleError(
                    "Decision binding exclusion must identify a Decision"
                )
        except ReviewInputBundleError as exc:
            findings.append(
                _finding(
                    "blocker",
                    "EXCLUDED_SOURCE_SEMANTICS_INVALID",
                    f"{source_id}: {exc}",
                )
            )
    portfolio_ref = (
        artifact.get("portfolio_context_ref")
        if isinstance(artifact.get("portfolio_context_ref"), Mapping)
        else {}
    )
    expected_warnings = _build_warnings(
        episode,
        portfolio_slice,
        source_requests=requests,
        excluded_sources=excluded,
        linked_decisions=linked_decisions,
        supplemental_sources=supplemental_sources,
        portfolio_context_ref=portfolio_ref,
    )
    if artifact.get("warnings") != expected_warnings:
        findings.append(
            _finding(
                "blocker",
                "WARNING_CLOSURE_MISMATCH",
                "warnings are not the exact derivation of frozen and excluded sources",
            )
        )
    return expected_warnings


def _verify_p2c_collection(
    episode_collection: Mapping[str, Any], *, episode_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    if episode_collection.get("schema_version") != COLLECTION_SCHEMA_VERSION:
        raise ReviewInputBundleError("unsupported P2C episode collection schema")
    if episode_collection.get("projection_version") != PROJECTION_VERSION:
        raise ReviewInputBundleError(
            "P2F requires the current P2C projection; rebuild the episode collection"
        )
    validation = validate_episode_collection(episode_collection)
    blockers = {
        str(item.get("code") or "")
        for item in validation.get("findings", [])
        if isinstance(item, Mapping) and item.get("severity") == "blocker"
    }
    unexpected = blockers - _ALLOWED_P2C_BLOCKERS
    if unexpected:
        raise ReviewInputBundleError(
            "P2C collection validation is blocked: " + ", ".join(sorted(unexpected))
        )
    selected = query_episode_collection(episode_collection, episode_id=episode_id)
    if len(selected) != 1:
        raise ReviewInputBundleError(
            f"episode_id must resolve exactly once: {episode_id!r}"
        )
    selected_episode = selected[0]
    lineage = (
        selected_episode.get("lineage")
        if isinstance(selected_episode.get("lineage"), Mapping)
        else {}
    )
    decision_linkage = (
        selected_episode.get("decision_linkage")
        if isinstance(selected_episode.get("decision_linkage"), Mapping)
        else {}
    )
    if (
        selected_episode.get("projection_version") != PROJECTION_VERSION
        or lineage.get("builder_version") != PROJECTION_VERSION
        or decision_linkage.get("contract_version")
        != DECISION_LINKAGE_CONTRACT_VERSION
    ):
        raise ReviewInputBundleError(
            "P2F requires P2C canonical Decision-linkage closure; rebuild P2C"
        )
    collection_digest = str(episode_collection.get("collection_digest") or "")
    if not _SHA256_RE.fullmatch(collection_digest):
        raise ReviewInputBundleError("P2C collection_digest must be a SHA-256 digest")
    return selected_episode, validation


def build_review_input_bundle(
    episode_collection: Mapping[str, Any],
    episode_portfolio_context: Mapping[str, Any] | None,
    *,
    portfolio_db: str | Path,
    episode_id: str,
    review_cutoff: str,
    decision_sources: Iterable[Mapping[str, Any]] = (),
    supplemental_sources: Iterable[Mapping[str, Any]] = (),
    allow_missing_portfolio_context: bool = False,
) -> dict[str, Any]:
    """Freeze one deterministic P2F input bundle without modifying source data."""

    if not isinstance(episode_collection, Mapping):
        raise ReviewInputBundleError("episode_collection must be an object")
    if not str(episode_id):
        raise ReviewInputBundleError("episode_id is required")
    selected_episode, _ = _verify_p2c_collection(
        episode_collection, episode_id=str(episode_id)
    )
    episode_snapshot_catalog = _episode_snapshot_catalog(
        episode_collection, selected_episode
    )
    review_time = _parse_timestamp(review_cutoff, "review_cutoff")
    episode_cutoff = _parse_timestamp(
        selected_episode.get("cutoff_at"), "episode.cutoff_at"
    )
    collection_cutoff = _parse_timestamp(
        episode_collection.get("cutoff_at"), "episode_collection.cutoff_at"
    )
    if episode_cutoff != collection_cutoff:
        raise ReviewInputBundleError(
            "episode cutoff does not match its P2C collection cutoff"
        )
    if review_time < episode_cutoff:
        raise ReviewInputBundleError(
            "review_cutoff cannot precede the selected episode cutoff"
        )

    db_before = _file_sha256(portfolio_db)
    if episode_portfolio_context is None:
        if not allow_missing_portfolio_context:
            raise ReviewInputBundleError(
                "P2E-3 portfolio context is required outside explicit contract-only mode"
            )
        as_of_time = episode_cutoff
        knowledge_time = episode_cutoff
        portfolio_ref: dict[str, Any] = {
            "status": "missing",
            "expected_schema_version": P2E3_SCHEMA_VERSION,
            "episode_id": str(episode_id),
            "reason": "explicit_contract_only_mode",
        }
        portfolio_slice: dict[str, Any] = {
            "status": "missing",
            "reason": "P2E-3 source artifact was explicitly omitted for contract-only testing.",
        }
        source_verification: dict[str, Any] = {
            "status": "missing",
            "validation_mode": "not_run",
            "reason": "P2E-3 source artifact was not supplied.",
            "validator_version": P2E3_VALIDATION_SCHEMA_VERSION,
        }
        release_readiness = {
            "status": "blocked",
            "blocker_codes": ["P2E3_SOURCE_VERIFICATION_MISSING"],
            "reasons": [
                "A contract-only bundle without source-verified P2E-3 context cannot be released."
            ],
        }
    else:
        if not isinstance(episode_portfolio_context, Mapping):
            raise ReviewInputBundleError(
                "episode_portfolio_context must be an object or None"
            )
        structural = validate_episode_portfolio_context(episode_portfolio_context)
        if structural.get("validation_status") == "blocked":
            raise ReviewInputBundleError(
                "P2E-3 structural validation is blocked: "
                + "; ".join(
                    str(item.get("message"))
                    for item in structural.get("findings", [])
                    if isinstance(item, Mapping)
                )
            )
        replay = replay_validate_episode_portfolio_context(
            episode_portfolio_context,
            episode_collection=episode_collection,
            portfolio_db=portfolio_db,
        )
        if (
            replay.get("validation_status") == "blocked"
            or (replay.get("source_verification") or {}).get("status") != "verified"
        ):
            raise ReviewInputBundleError(
                "P2E-3 source replay did not produce source_verification=verified"
            )
        expected_collection_id = "sha256:" + str(
            episode_collection.get("collection_digest")
        )
        episode_ref = (
            episode_portfolio_context.get("episode_artifact_ref")
            if isinstance(
                episode_portfolio_context.get("episode_artifact_ref"), Mapping
            )
            else {}
        )
        binding = (
            episode_portfolio_context.get("source_binding")
            if isinstance(episode_portfolio_context.get("source_binding"), Mapping)
            else {}
        )
        if (
            episode_ref.get("content_id") != expected_collection_id
            or binding.get("episode_collection_content_id") != expected_collection_id
        ):
            raise ReviewInputBundleError(
                "P2E-3 source binding does not match the supplied P2C collection"
            )
        if _parse_timestamp(
            binding.get("episode_collection_cutoff"),
            "P2E-3 source_binding.episode_collection_cutoff",
        ) != collection_cutoff:
            raise ReviewInputBundleError(
                "P2E-3 source binding cutoff does not match P2C"
            )
        as_of_time = _parse_timestamp(
            episode_portfolio_context.get("as_of"), "P2E-3 as_of"
        )
        knowledge_time = _parse_timestamp(
            episode_portfolio_context.get("knowledge_cutoff"),
            "P2E-3 knowledge_cutoff",
        )
        if review_time < as_of_time or review_time < knowledge_time:
            raise ReviewInputBundleError(
                "review_cutoff cannot precede P2E-3 as_of or knowledge_cutoff"
            )
        portfolio_slice = _episode_portfolio_slice(
            episode_portfolio_context, episode_id=str(episode_id)
        )
        portfolio_ref = {
            "status": "available",
            "schema_version": P2E3_SCHEMA_VERSION,
            "content_id": str(episode_portfolio_context.get("content_id") or ""),
            "episode_id": str(episode_id),
        }
        replay_verification = replay.get("source_verification") or {}
        source_verification = {
            "status": "verified",
            "validation_mode": "source_replay",
            "verified_content_id": str(
                episode_portfolio_context.get("content_id") or ""
            ),
            "rebuilt_content_id": str(
                replay_verification.get("rebuilt_content_id") or ""
            ),
            "portfolio_db_sha256_before": db_before,
            "portfolio_db_sha256_after": "",
            "database_unchanged": True,
            "validator_version": P2E3_VALIDATION_SCHEMA_VERSION,
        }
        release_readiness = {
            "status": "ready",
            "blocker_codes": [],
            "reasons": [],
        }

    (
        linked_decisions,
        _decision_warnings,
        decision_requests,
        decision_excluded,
    ) = _normalize_decisions(
        selected_episode, decision_sources, review_cutoff=review_time
    )
    (
        frozen_supplemental,
        _supplemental_warnings,
        supplemental_requests,
        supplemental_excluded,
    ) = _normalize_supplemental(
        supplemental_sources, review_cutoff=review_time
    )
    source_requests = sorted(
        [*decision_requests, *supplemental_requests],
        key=lambda item: (
            item["source_kind"],
            item["source_id"],
            item["request_basis"],
        ),
    )
    excluded_sources = sorted(
        [*decision_excluded, *supplemental_excluded],
        key=lambda item: (
            item["source_kind"],
            item["source_id"],
            item["reason_code"],
        ),
    )
    db_after = _file_sha256(portfolio_db)
    if db_before != db_after:
        raise ReviewInputBundleError(
            "portfolio database SHA-256 changed during read-only bundle construction"
        )
    if source_verification["status"] == "verified":
        source_verification["portfolio_db_sha256_after"] = db_after

    frozen_sources = {
        "episode": deepcopy(dict(selected_episode)),
        "episode_snapshot_catalog": episode_snapshot_catalog,
        "portfolio_context_episode_slice": portfolio_slice,
        "linked_decisions": linked_decisions,
        "supplemental_sources": frozen_supplemental,
    }
    source_warnings = _source_manifest_warnings(
        source_requests=source_requests,
        excluded_sources=excluded_sources,
        linked_decisions=linked_decisions,
        supplemental_sources=frozen_supplemental,
        portfolio_context_ref=portfolio_ref,
        episode_id=str(episode_id),
    )
    section_availability = _section_availability(
        selected_episode,
        portfolio_slice,
        linked_decisions,
        frozen_supplemental,
        source_warnings,
    )
    artifact_warnings = _build_warnings(
        selected_episode,
        portfolio_slice,
        source_requests=source_requests,
        excluded_sources=excluded_sources,
        linked_decisions=linked_decisions,
        supplemental_sources=frozen_supplemental,
        portfolio_context_ref=portfolio_ref,
    )
    artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "content_id": "",
        "build_request": {
            "selection_mode": "explicit_episode",
            "episode_id": str(episode_id),
            "as_of": _iso(as_of_time),
            "knowledge_cutoff": _iso(knowledge_time),
            "review_cutoff": _iso(review_time),
            "include_linked_decisions": True,
            "requested_supplemental_source_ids": [
                item["source_id"]
                for item in supplemental_requests
            ],
        },
        "episode_ref": {
            "collection_schema_version": COLLECTION_SCHEMA_VERSION,
            "collection_digest": str(episode_collection.get("collection_digest")),
            "episode_schema_version": EPISODE_SCHEMA_VERSION,
            "episode_id": str(episode_id),
            "lineage": deepcopy(dict(selected_episode.get("lineage") or {})),
        },
        "portfolio_context_ref": portfolio_ref,
        "source_verification": source_verification,
        "frozen_sources": frozen_sources,
        "source_requests": source_requests,
        "excluded_sources": excluded_sources,
        "source_inventory": _source_inventory(
            selected_episode,
            episode_snapshot_catalog,
            portfolio_slice,
            linked_decisions,
            frozen_supplemental,
        ),
        "section_availability": section_availability,
        "release_readiness": release_readiness,
        "warnings": artifact_warnings,
        "canonicalization": deepcopy(_CANONICALIZATION),
    }
    artifact["content_id"] = _content_id(artifact)
    validation = validate_review_input_bundle(artifact)
    if validation["validation_status"] == "blocked":
        raise ReviewInputBundleError(
            "built P2F input bundle failed validation: "
            + "; ".join(item["message"] for item in validation["findings"])
        )
    return artifact


def _canonical_timestamp(
    value: object, *, field: str, findings: list[dict[str, str]]
) -> datetime | None:
    try:
        parsed = _parse_timestamp(value, field)
    except ReviewInputBundleError as exc:
        findings.append(_finding("blocker", "INVALID_TIMESTAMP", str(exc)))
        return None
    if value != _iso(parsed):
        findings.append(
            _finding(
                "blocker",
                "NON_CANONICAL_TIME",
                f"{field} must use canonical UTC seconds",
            )
        )
    return parsed


def _validate_episode_binding(
    artifact: Mapping[str, Any], findings: list[dict[str, str]]
) -> Mapping[str, Any]:
    frozen = (
        artifact.get("frozen_sources")
        if isinstance(artifact.get("frozen_sources"), Mapping)
        else {}
    )
    episode = frozen.get("episode") if isinstance(frozen.get("episode"), Mapping) else {}
    snapshot_catalog = [
        item
        for item in frozen.get("episode_snapshot_catalog", [])
        if isinstance(item, Mapping)
    ]
    episode_ref = (
        artifact.get("episode_ref")
        if isinstance(artifact.get("episode_ref"), Mapping)
        else {}
    )
    request = (
        artifact.get("build_request")
        if isinstance(artifact.get("build_request"), Mapping)
        else {}
    )
    episode_id = str(episode.get("episode_id") or "")
    if not episode_id or episode_id != episode_ref.get("episode_id") or episode_id != request.get(
        "episode_id"
    ):
        findings.append(
            _finding(
                "blocker",
                "EPISODE_REF_MISMATCH",
                "embedded episode identity does not match build_request and episode_ref",
            )
        )
    if episode.get("schema_version") != EPISODE_SCHEMA_VERSION:
        findings.append(
            _finding(
                "blocker",
                "EPISODE_CONTENT_MISMATCH",
                "embedded episode has an unsupported schema",
            )
        )
    lineage = episode.get("lineage") if isinstance(episode.get("lineage"), Mapping) else {}
    decision_linkage = (
        episode.get("decision_linkage")
        if isinstance(episode.get("decision_linkage"), Mapping)
        else {}
    )
    if (
        episode.get("projection_version") != PROJECTION_VERSION
        or lineage.get("builder_version") != PROJECTION_VERSION
        or decision_linkage.get("contract_version")
        != DECISION_LINKAGE_CONTRACT_VERSION
    ):
        findings.append(
            _finding(
                "blocker",
                "P2C_PROJECTION_CONTRACT_MISMATCH",
                "embedded episode is not the P2C projection required by P2F",
            )
        )
    if dict(lineage) != dict(episode_ref.get("lineage") or {}):
        findings.append(
            _finding(
                "blocker",
                "EPISODE_REF_MISMATCH",
                "episode_ref.lineage does not equal embedded episode lineage",
            )
        )
    material = deepcopy(dict(episode))
    material.pop("validation", None)
    material_lineage = dict(material.get("lineage") or {})
    expected_digest = str(material_lineage.pop("canonical_content_digest", ""))
    material["lineage"] = material_lineage
    actual_digest = hashlib.sha256(canonical_json_bytes(material)).hexdigest()
    if expected_digest != actual_digest:
        findings.append(
            _finding(
                "blocker",
                "EPISODE_CONTENT_MISMATCH",
                "embedded episode canonical_content_digest does not match",
            )
        )
    referenced_snapshot_ids = {
        str(item.get("snapshot_ref") or "")
        for item in episode.get("snapshot_links", [])
        if isinstance(item, Mapping) and item.get("snapshot_ref")
    }
    catalog_ids = [str(item.get("snapshot_id") or "") for item in snapshot_catalog]
    if (
        len(snapshot_catalog)
        != len(frozen.get("episode_snapshot_catalog", []))
        or len(catalog_ids) != len(set(catalog_ids))
        or set(catalog_ids) != referenced_snapshot_ids
        or snapshot_catalog
        != sorted(snapshot_catalog, key=snapshot_catalog_sort_key)
    ):
        findings.append(
            _finding(
                "blocker",
                "EPISODE_SNAPSHOT_CATALOG_MISMATCH",
                "embedded P2C snapshot catalog is not the exact referenced closure",
            )
        )
    episode_validation = validate_episode(
        episode, snapshot_catalog=snapshot_catalog
    )
    unexpected_blockers = {
        str(item.get("code") or "")
        for item in episode_validation.get("findings", [])
        if isinstance(item, Mapping) and item.get("severity") == "blocker"
    } - _ALLOWED_P2C_BLOCKERS
    if unexpected_blockers:
        findings.append(
            _finding(
                "blocker",
                "EPISODE_CONTRACT_INVALID",
                "embedded episode fails P2C validation: "
                + ", ".join(sorted(unexpected_blockers)),
            )
        )
    return episode


def _validate_wrapped_source(
    wrapper: Mapping[str, Any],
    *,
    decision: bool,
    episode_events: Mapping[str, Mapping[str, Any]] | None = None,
    decision_links: Sequence[Mapping[str, Any]] = (),
    decision_linkage_status: str = "missing",
    review_cutoff: datetime | None,
    findings: list[dict[str, str]],
    field: str,
) -> None:
    payload = wrapper.get("payload") if isinstance(wrapper.get("payload"), Mapping) else {}
    payload_content_id = _value_content_id(payload)
    if wrapper.get("payload_content_id") != payload_content_id:
        findings.append(
            _finding(
                "blocker",
                "EMBEDDED_PAYLOAD_HASH_MISMATCH",
                f"{field}.payload_content_id does not hash its payload",
            )
        )
    if wrapper.get("content_id") != _wrapped_source_content_id(wrapper):
        findings.append(
            _finding(
                "blocker",
                "EMBEDDED_SOURCE_HASH_MISMATCH",
                f"{field}.content_id does not bind its envelope and payload",
            )
        )
    try:
        wrapper_id = str(wrapper.get("source_id") or "")
        payload_id = next(
            (
                str(payload[key])
                for key in ("source_id", "decision_id", "id")
                if payload.get(key) not in (None, "")
            ),
            wrapper_id,
        )
        if wrapper_id != payload_id:
            findings.append(
                _finding(
                    "blocker",
                    "EMBEDDED_SOURCE_ID_MISMATCH",
                    f"{field}.source_id does not match its payload",
                )
            )
        if decision and wrapper.get("source_kind") != "decision":
            findings.append(
                _finding(
                    "blocker",
                    "EMBEDDED_SOURCE_KIND_MISMATCH",
                    f"{field}.source_kind must be decision",
                )
            )
        if not decision and wrapper.get("source_kind") not in _SUPPLEMENTAL_KINDS:
            findings.append(
                _finding(
                    "blocker",
                    "EMBEDDED_SOURCE_KIND_MISMATCH",
                    f"{field}.source_kind is unsupported",
                )
            )
        effective = _parse_timestamp(wrapper.get("effective_at"), f"{field}.effective_at")
        known = _parse_timestamp(wrapper.get("knowledge_at"), f"{field}.knowledge_at")
        if known < effective:
            findings.append(
                _finding(
                    "blocker",
                    "INVALID_SOURCE_TIME_ORDER",
                    f"{field}.knowledge_at precedes effective_at",
                )
            )
        if wrapper.get("effective_at") != _iso(effective) or wrapper.get(
            "knowledge_at"
        ) != _iso(known):
            findings.append(
                _finding(
                    "blocker",
                    "EMBEDDED_SOURCE_TIME_MISMATCH",
                    f"{field} wrapper times are not canonical UTC seconds",
                )
            )
        if wrapper.get("availability") not in _AVAILABILITY:
            findings.append(
                _finding(
                    "blocker",
                    "EMBEDDED_SOURCE_AVAILABILITY_INVALID",
                    f"{field}.availability is unsupported",
                )
            )
        if decision:
            source_availability = wrapper.get("source_availability")
            if source_availability not in _AVAILABILITY:
                findings.append(
                    _finding(
                        "blocker",
                        "EMBEDDED_SOURCE_AVAILABILITY_INVALID",
                        f"{field}.source_availability is unsupported",
                    )
                )
                source_availability = "invalid"
            source_warning_codes = wrapper.get("source_warning_codes")
            if not isinstance(source_warning_codes, list) or list(
                source_warning_codes
            ) != sorted({_warning_code(item) for item in source_warning_codes}):
                findings.append(
                    _finding(
                        "blocker",
                        "EMBEDDED_SOURCE_WARNING_ORDER_INVALID",
                        f"{field}.source_warning_codes are not canonical",
                    )
                )
                source_warning_codes = []
            linkage_availability = {
                "linked": "available",
                "ambiguous": "ambiguous",
                "invalid": "invalid",
                "unlinked": "unlinked",
            }.get(decision_linkage_status, "missing")
            matching_links = [
                link
                for link in decision_links
                if str(link.get("decision_id") or "") == wrapper_id
            ]
            if not matching_links:
                findings.append(
                    _finding(
                        "blocker",
                        "DECISION_LINK_EVIDENCE_MISMATCH",
                        f"{field} has no canonical P2C Decision link",
                    )
                )
            expected_link_refs: list[dict[str, Any]] = []
            aggregate_warning_codes = set(source_warning_codes)
            for link in matching_links:
                event_id = str(link.get("event_id") or "")
                relation = str(link.get("relation") or "")
                if not _decision_link_matches(
                    link,
                    source_id=wrapper_id,
                    event_id=event_id,
                    relation=relation,
                    effective_at=effective,
                    knowledge_at=known,
                ):
                    findings.append(
                        _finding(
                            "blocker",
                            "DECISION_LINK_EVIDENCE_MISMATCH",
                            f"{field} times/identity do not match all canonical P2C links",
                        )
                    )
                link_availability = _merge_availability(
                    str(source_availability), linkage_availability
                )
                link_warning_codes: set[str] = set()
                if relation != "execution":
                    link_availability = _merge_availability(
                        link_availability, "invalid"
                    )
                    link_warning_codes.add("DECISION_LINK_RELATION_INVALID")
                if not episode_events or event_id not in episode_events:
                    link_availability = _merge_availability(
                        link_availability, "invalid"
                    )
                    link_warning_codes.add("DECISION_EVENT_BINDING_INVALID")
                else:
                    linked_event_time = _parse_timestamp(
                        episode_events[event_id].get("effective_at"),
                        f"{field}.linked_event.effective_at",
                    )
                    if known > linked_event_time:
                        link_availability = _merge_availability(
                            link_availability, "invalid"
                        )
                        link_warning_codes.add(
                            "DECISION_KNOWN_AFTER_LINKED_EVENT"
                        )
                aggregate_warning_codes.update(link_warning_codes)
                expected_link_refs.append(
                    {
                        "event_id": event_id,
                        "relation": relation,
                        "link_content_id": _value_content_id(link),
                        "availability": link_availability,
                        "warning_codes": sorted(link_warning_codes),
                    }
                )
            if wrapper.get("decision_link_refs") != expected_link_refs:
                findings.append(
                    _finding(
                        "blocker",
                        "DECISION_LINK_CLOSURE_MISMATCH",
                        f"{field}.decision_link_refs are not the exact P2C link closure",
                    )
                )
            expected_warning_codes = sorted(aggregate_warning_codes)
            if wrapper.get("warning_codes") != expected_warning_codes:
                findings.append(
                    _finding(
                        "blocker",
                        "DECISION_WARNING_CLOSURE_MISMATCH",
                        f"{field}.warning_codes are not derived from its links",
                    )
                )
            expected_availability = _merge_availability(
                str(source_availability),
                linkage_availability,
                *(item["availability"] for item in expected_link_refs),
            )
            if wrapper.get("availability") != expected_availability:
                findings.append(
                    _finding(
                        "blocker",
                        "DECISION_AVAILABILITY_MISMATCH",
                        f"{field}.availability is not derived from its links",
                    )
                )
        if list(wrapper.get("warning_codes", [])) != sorted(
            {_warning_code(item) for item in wrapper.get("warning_codes", [])}
        ):
            findings.append(
                _finding(
                    "blocker",
                    "EMBEDDED_SOURCE_WARNING_ORDER_INVALID",
                    f"{field}.warning_codes are not canonical",
                )
            )
        if review_cutoff is not None and (
            effective > review_cutoff or known > review_cutoff
        ):
            findings.append(
                _finding(
                    "blocker",
                    "FUTURE_SOURCE",
                    f"{field} exceeds review_cutoff",
                )
            )
    except (ReviewInputBundleError, ArtifactIOError) as exc:
        findings.append(_finding("blocker", "INVALID_EMBEDDED_SOURCE", str(exc)))


def _validate_p2e3_slice_shapes(
    portfolio_slice: Mapping[str, Any],
    findings: list[dict[str, str]],
) -> None:
    checks: list[tuple[str, Any, str]] = [
        (
            "artifact_ref",
            portfolio_slice.get("episode_artifact_ref"),
            "portfolio_context_episode_slice.episode_artifact_ref",
        ),
        (
            "source_binding",
            portfolio_slice.get("source_binding"),
            "portfolio_context_episode_slice.source_binding",
        ),
    ]
    checks.extend(
        (
            "material_event",
            item,
            f"portfolio_context_episode_slice.material_events[{index}]",
        )
        for index, item in enumerate(portfolio_slice.get("material_events", []))
    )
    checks.extend(
        (
            "context",
            item,
            f"portfolio_context_episode_slice.contexts[{index}]",
        )
        for index, item in enumerate(portfolio_slice.get("contexts", []))
    )
    checks.extend(
        (
            "delta",
            item,
            f"portfolio_context_episode_slice.deltas[{index}]",
        )
        for index, item in enumerate(portfolio_slice.get("deltas", []))
    )
    for index, item in enumerate(portfolio_slice.get("warnings", [])):
        if isinstance(item, Mapping):
            warning = deepcopy(dict(item))
            warning.pop("scope", None)
        else:
            warning = item
        checks.append(
            (
                "warning",
                warning,
                f"portfolio_context_episode_slice.warnings[{index}]",
            )
        )
    for definition, value, field in checks:
        try:
            errors = sorted(
                _p2e3_definition_validator(definition).iter_errors(value),
                key=lambda item: (_schema_path(item), item.message),
            )
        except Exception as exc:
            findings.append(
                _finding(
                    "blocker",
                    "P2E3_SLICE_SCHEMA_VALIDATOR_ERROR",
                    f"{field}: {exc}",
                )
            )
            continue
        findings.extend(
            _finding(
                "blocker",
                "P2E3_SLICE_SCHEMA_VIOLATION",
                f"{field}{_schema_path(error)[1:]}: {error.message}",
            )
            for error in errors
        )


def _validate_portfolio_slice(
    artifact: Mapping[str, Any],
    episode: Mapping[str, Any],
    findings: list[dict[str, str]],
) -> Mapping[str, Any]:
    frozen = artifact.get("frozen_sources") or {}
    portfolio_slice = (
        frozen.get("portfolio_context_episode_slice")
        if isinstance(frozen, Mapping)
        and isinstance(frozen.get("portfolio_context_episode_slice"), Mapping)
        else {}
    )
    portfolio_ref = (
        artifact.get("portfolio_context_ref")
        if isinstance(artifact.get("portfolio_context_ref"), Mapping)
        else {}
    )
    verification = (
        artifact.get("source_verification")
        if isinstance(artifact.get("source_verification"), Mapping)
        else {}
    )
    readiness = (
        artifact.get("release_readiness")
        if isinstance(artifact.get("release_readiness"), Mapping)
        else {}
    )
    episode_id = str(episode.get("episode_id") or "")
    if portfolio_ref.get("status") == "missing":
        if (
            portfolio_slice.get("status") != "missing"
            or verification.get("status") != "missing"
            or readiness.get("status") != "blocked"
            or not readiness.get("blocker_codes")
            or not readiness.get("reasons")
        ):
            findings.append(
                _finding(
                    "blocker",
                    "MISSING_CONTEXT_GATE_MISMATCH",
                    "contract-only missing context must remain release-blocked",
                )
            )
        return portfolio_slice
    _validate_p2e3_slice_shapes(portfolio_slice, findings)
    if (
        portfolio_ref.get("status") != "available"
        or portfolio_ref.get("episode_id") != episode_id
        or portfolio_slice.get("episode_id") != episode_id
        or portfolio_slice.get("artifact_content_id") != portfolio_ref.get("content_id")
        or verification.get("status") != "verified"
        or verification.get("verified_content_id") != portfolio_ref.get("content_id")
        or verification.get("rebuilt_content_id") != portfolio_ref.get("content_id")
        or verification.get("portfolio_db_sha256_before")
        != verification.get("portfolio_db_sha256_after")
        or verification.get("database_unchanged") is not True
        or readiness
        != {"status": "ready", "blocker_codes": [], "reasons": []}
    ):
        findings.append(
            _finding(
                "blocker",
                "SOURCE_VERIFICATION_INVALID",
                "available P2E-3 context lacks an exact verified and release-ready binding",
            )
        )
    if portfolio_slice.get("slice_content_id") != _slice_content_id(portfolio_slice):
        findings.append(
            _finding(
                "blocker",
                "PORTFOLIO_SLICE_HASH_MISMATCH",
                "P2E-3 episode slice content hash does not match",
            )
        )
    binding = (
        portfolio_slice.get("source_binding")
        if isinstance(portfolio_slice.get("source_binding"), Mapping)
        else {}
    )
    selection = (
        binding.get("selection")
        if isinstance(binding.get("selection"), Mapping)
        else {}
    )
    if sorted(str(item) for item in selection.get("resolved_episode_ids", [])) != [
        episode_id
    ]:
        findings.append(
            _finding(
                "blocker",
                "PORTFOLIO_SLICE_SCOPE_MISMATCH",
                "P2E-3 slice selection is not exactly the embedded episode",
            )
        )
    material_events = [
        item for item in portfolio_slice.get("material_events", []) if isinstance(item, Mapping)
    ]
    contexts = [
        item for item in portfolio_slice.get("contexts", []) if isinstance(item, Mapping)
    ]
    deltas = [
        item for item in portfolio_slice.get("deltas", []) if isinstance(item, Mapping)
    ]
    if any(item.get("episode_id") != episode_id for item in material_events + contexts + deltas):
        findings.append(
            _finding(
                "blocker",
                "PORTFOLIO_SLICE_SCOPE_MISMATCH",
                "P2E-3 slice contains another episode",
            )
        )
    if material_events != binding.get("material_events"):
        findings.append(
            _finding(
                "blocker",
                "PORTFOLIO_SLICE_EVENT_MISMATCH",
                "slice material_events differ from source_binding",
            )
        )
    event_ids = [str(item.get("event_id") or "") for item in material_events]
    context_pairs = {
        (
            str((item.get("anchor") or {}).get("event_id") or ""),
            str((item.get("anchor") or {}).get("side") or ""),
        )
        for item in contexts
    }
    expected_pairs = {(event_id, side) for event_id in event_ids for side in ("pre", "post")}
    if context_pairs != expected_pairs:
        findings.append(
            _finding(
                "blocker",
                "PORTFOLIO_SLICE_CONTEXT_CLOSURE_MISMATCH",
                "slice does not contain exactly one pre/post context per material event",
            )
        )
    return portfolio_slice


def _validate_review_input_bundle_impl(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Validate schema, canonical hash, closure, availability and time semantics."""

    findings: list[dict[str, str]] = []
    if not isinstance(artifact, Mapping):
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "validation_mode": "offline_structural",
            "validation_status": "blocked",
            "release_readiness": "blocked",
            "findings": [
                _finding("blocker", "INVALID_ROOT", "artifact root must be an object")
            ],
        }
    try:
        schema_errors = sorted(
            _contract_validator().iter_errors(artifact),
            key=lambda item: (_schema_path(item), item.message),
        )
        findings.extend(
            _finding(
                "blocker",
                "SCHEMA_VIOLATION",
                f"{_schema_path(error)}: {error.message}",
            )
            for error in schema_errors
        )
    except Exception as exc:
        findings.append(_finding("blocker", "SCHEMA_VALIDATOR_ERROR", str(exc)))
    try:
        canonical_json_bytes(artifact)
    except ArtifactIOError as exc:
        findings.append(_finding("blocker", "NON_CANONICAL_JSON", str(exc)))
    if artifact.get("schema_version") != SCHEMA_VERSION:
        findings.append(
            _finding("blocker", "UNSUPPORTED_SCHEMA", "unsupported schema_version")
        )
    if artifact.get("canonicalization") != _CANONICALIZATION:
        findings.append(
            _finding(
                "blocker",
                "CANONICALIZATION_PROFILE_MISMATCH",
                "canonicalization profile does not match the fixed P2F v1 profile",
            )
        )
    try:
        if artifact.get("content_id") != _content_id(artifact):
            findings.append(
                _finding(
                    "blocker",
                    "CONTENT_ID_MISMATCH",
                    "content_id does not match canonical bundle content",
                )
            )
    except ArtifactIOError as exc:
        findings.append(_finding("blocker", "CONTENT_ID_ERROR", str(exc)))

    request = (
        artifact.get("build_request")
        if isinstance(artifact.get("build_request"), Mapping)
        else {}
    )
    as_of = _canonical_timestamp(
        request.get("as_of"), field="build_request.as_of", findings=findings
    )
    knowledge = _canonical_timestamp(
        request.get("knowledge_cutoff"),
        field="build_request.knowledge_cutoff",
        findings=findings,
    )
    review = _canonical_timestamp(
        request.get("review_cutoff"),
        field="build_request.review_cutoff",
        findings=findings,
    )
    if review is not None and (
        (as_of is not None and review < as_of)
        or (knowledge is not None and review < knowledge)
    ):
        findings.append(
            _finding(
                "blocker",
                "INVALID_CUTOFF_ORDER",
                "review_cutoff cannot precede as_of or knowledge_cutoff",
            )
        )

    episode = _validate_episode_binding(artifact, findings)
    portfolio_slice = _validate_portfolio_slice(artifact, episode, findings)
    try:
        episode_cutoff = _parse_timestamp(
            episode.get("cutoff_at"), "frozen_sources.episode.cutoff_at"
        )
        if review is not None and review < episode_cutoff:
            findings.append(
                _finding(
                    "blocker",
                    "INVALID_CUTOFF_ORDER",
                    "review_cutoff precedes embedded episode cutoff",
                )
            )
    except ReviewInputBundleError as exc:
        findings.append(_finding("blocker", "INVALID_EPISODE_CUTOFF", str(exc)))

    frozen = artifact.get("frozen_sources") if isinstance(artifact.get("frozen_sources"), Mapping) else {}
    decisions = [
        item for item in frozen.get("linked_decisions", []) if isinstance(item, Mapping)
    ]
    episode_snapshot_catalog = [
        item
        for item in frozen.get("episode_snapshot_catalog", [])
        if isinstance(item, Mapping)
    ]
    supplementals = [
        item for item in frozen.get("supplemental_sources", []) if isinstance(item, Mapping)
    ]
    explicit_ids: set[str] = set()
    for item in (episode.get("decision_linkage") or {}).get("decision_refs", []):
        if isinstance(item, str) and item:
            explicit_ids.add(item)
        elif isinstance(item, Mapping) and item.get("decision_id"):
            explicit_ids.add(str(item["decision_id"]))
    if {str(item.get("source_id")) for item in decisions} - explicit_ids:
        findings.append(
            _finding(
                "blocker",
                "DECISION_NOT_EXPLICIT",
                "frozen Decision source is not in episode decision_event_links",
            )
        )
    episode_events = {
        str(item.get("event_id")): item
        for item in episode.get("event_refs", [])
        if isinstance(item, Mapping) and item.get("event_id")
    }
    decision_links = [
        item
        for item in (episode.get("decision_linkage") or {}).get(
            "decision_links", []
        )
        if isinstance(item, Mapping)
    ]
    decision_linkage_status = str(
        (episode.get("decision_linkage") or {}).get("status") or "missing"
    )
    for index, item in enumerate(decisions):
        _validate_wrapped_source(
            item,
            decision=True,
            episode_events=episode_events,
            decision_links=decision_links,
            decision_linkage_status=decision_linkage_status,
            review_cutoff=review,
            findings=findings,
            field=f"frozen_sources.linked_decisions[{index}]",
        )
    for index, item in enumerate(supplementals):
        _validate_wrapped_source(
            item,
            decision=False,
            review_cutoff=review,
            findings=findings,
            field=f"frozen_sources.supplemental_sources[{index}]",
        )
    if decisions != sorted(
        decisions, key=lambda item: (item.get("source_id"), item.get("content_id"))
    ):
        findings.append(
            _finding(
                "blocker",
                "CANONICAL_ORDER_MISMATCH",
                "linked_decisions are not in canonical order",
            )
        )
    if supplementals != sorted(
        supplementals,
        key=lambda item: (
            item.get("source_kind"),
            item.get("source_id"),
            item.get("content_id"),
        ),
    ):
        findings.append(
            _finding(
                "blocker",
                "CANONICAL_ORDER_MISMATCH",
                "supplemental_sources are not in canonical order",
            )
        )

    expected_warnings = _validate_source_manifests(
        artifact,
        episode=episode,
        portfolio_slice=portfolio_slice,
        linked_decisions=decisions,
        supplemental_sources=supplementals,
        review_cutoff=review,
        findings=findings,
    )

    try:
        expected_inventory = _source_inventory(
            episode,
            episode_snapshot_catalog,
            portfolio_slice,
            decisions,
            supplementals,
        )
        if artifact.get("source_inventory") != expected_inventory:
            findings.append(
                _finding(
                    "blocker",
                    "SOURCE_INVENTORY_MISMATCH",
                    "source_inventory is not the exact frozen-source closure",
                )
            )
    except Exception as exc:
        findings.append(
            _finding("blocker", "SOURCE_INVENTORY_ERROR", str(exc))
        )
    expected_sections = _section_availability(
        episode,
        portfolio_slice,
        decisions,
        supplementals,
        expected_warnings,
    )
    if artifact.get("section_availability") != expected_sections:
        findings.append(
            _finding(
                "blocker",
                "SECTION_AVAILABILITY_MISMATCH",
                "section_availability is not derived from frozen sources",
            )
        )
    warnings = artifact.get("warnings")
    if isinstance(warnings, list) and warnings != _sorted_warnings(
        item for item in warnings if isinstance(item, Mapping)
    ):
        findings.append(
            _finding(
                "blocker",
                "CANONICAL_ORDER_MISMATCH",
                "warnings are not unique and canonically ordered",
            )
        )
    requested_ids = request.get("requested_supplemental_source_ids")
    if isinstance(requested_ids, list) and requested_ids != sorted(set(requested_ids)):
        findings.append(
            _finding(
                "blocker",
                "CANONICAL_ORDER_MISMATCH",
                "requested_supplemental_source_ids must be sorted and unique",
            )
        )
    findings = sorted(
        findings,
        key=lambda item: (
            0 if item["severity"] == "blocker" else 1,
            item["code"],
            item["message"],
        ),
    )
    blocked = any(item["severity"] == "blocker" for item in findings)
    release_status = str(
        (artifact.get("release_readiness") or {}).get("status") or "blocked"
    )
    validation_status = (
        "blocked"
        if blocked
        else "accepted_with_warnings"
        if artifact.get("warnings") or release_status == "blocked"
        else "accepted"
    )
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "validation_mode": "offline_structural",
        "validation_status": validation_status,
        "release_readiness": release_status,
        "findings": findings,
    }


def validate_review_input_bundle(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Validate arbitrary JSON-like input and always return a validation artifact."""

    if not isinstance(artifact, Mapping):
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "validation_mode": "offline_structural",
            "validation_status": "blocked",
            "release_readiness": "blocked",
            "findings": [
                _finding(
                    "blocker",
                    "MALFORMED_REVIEW_INPUT_BUNDLE",
                    "review input bundle must be an object",
                )
            ],
        }
    try:
        return _validate_review_input_bundle_impl(artifact)
    except Exception as exc:
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "validation_mode": "offline_structural",
            "validation_status": "blocked",
            "release_readiness": str(
                (artifact.get("release_readiness") or {}).get(
                    "status", "blocked"
                )
                if isinstance(artifact.get("release_readiness"), Mapping)
                else "blocked"
            ),
            "findings": [
                _finding(
                    "blocker",
                    "MALFORMED_REVIEW_INPUT_BUNDLE",
                    str(exc),
                )
            ],
        }


def replay_validate_review_input_bundle(
    artifact: Mapping[str, Any],
    *,
    episode_collection: Mapping[str, Any],
    episode_portfolio_context: Mapping[str, Any] | None,
    portfolio_db: str | Path,
    decision_sources: Iterable[Mapping[str, Any]] = (),
    supplemental_sources: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Rebuild from supplied P2C/P2E-3/database sources and compare exact bytes."""

    db_before = _file_sha256(portfolio_db)
    structural = validate_review_input_bundle(artifact)
    findings = list(structural["findings"])
    rebuilt_content_id: str | None = None
    if structural["validation_status"] != "blocked":
        request = artifact.get("build_request") or {}
        allow_missing = (
            (artifact.get("portfolio_context_ref") or {}).get("status") == "missing"
        )
        try:
            rebuilt = build_review_input_bundle(
                episode_collection,
                episode_portfolio_context,
                portfolio_db=portfolio_db,
                episode_id=str(request.get("episode_id") or ""),
                review_cutoff=str(request.get("review_cutoff") or ""),
                decision_sources=decision_sources,
                supplemental_sources=supplemental_sources,
                allow_missing_portfolio_context=allow_missing,
            )
            rebuilt_content_id = str(rebuilt.get("content_id") or "")
            if canonical_json_bytes(rebuilt) != canonical_json_bytes(artifact):
                findings.append(
                    _finding(
                        "blocker",
                        "SOURCE_REPLAY_MISMATCH",
                        "bundle bytes differ from deterministic source replay",
                    )
                )
        except Exception as exc:
            findings.append(
                _finding(
                    "blocker",
                    "SOURCE_REPLAY_ERROR",
                    f"source-aware rebuild failed: {exc}",
                )
            )
    db_after = _file_sha256(portfolio_db)
    if db_before != db_after:
        findings.append(
            _finding(
                "blocker",
                "SOURCE_DATABASE_MUTATED",
                "portfolio database changed during source replay",
            )
        )
    findings = sorted(
        findings,
        key=lambda item: (
            0 if item["severity"] == "blocker" else 1,
            item["code"],
            item["message"],
        ),
    )
    blocked = any(item["severity"] == "blocker" for item in findings)
    source_status = (
        "mismatch"
        if blocked
        else "missing"
        if (artifact.get("source_verification") or {}).get("status") == "missing"
        else "verified"
    )
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "validation_mode": "source_replay",
        "validation_status": (
            "blocked"
            if blocked
            else structural["validation_status"]
        ),
        "release_readiness": structural.get("release_readiness", "blocked"),
        "source_verification": {
            "status": source_status,
            "rebuilt_content_id": rebuilt_content_id,
            "portfolio_db_sha256_before": db_before,
            "portfolio_db_sha256_after": db_after,
        },
        "findings": findings,
    }


def save_review_input_bundle(
    path: str | Path, artifact: Mapping[str, Any]
) -> Path:
    validation = validate_review_input_bundle(artifact)
    if validation["validation_status"] == "blocked":
        raise ReviewInputBundleError("refusing to save an invalid P2F input bundle")
    try:
        return atomic_write_bytes(path, pretty_json_bytes(artifact))
    except ArtifactIOError as exc:
        raise ReviewInputBundleError(str(exc)) from exc


def load_review_input_bundle(path: str | Path) -> dict[str, Any]:
    try:
        return load_json_object(path)
    except ArtifactIOError as exc:
        raise ReviewInputBundleError(str(exc)) from exc


def query_review_input_bundle(
    artifact: Mapping[str, Any],
    *,
    section: str | None = None,
    source_id: str | None = None,
    content_id: str | None = None,
) -> list[Any]:
    if artifact.get("schema_version") != SCHEMA_VERSION:
        raise ReviewInputBundleError("unsupported P2F review-input schema")
    if content_id is not None and artifact.get("content_id") != content_id:
        return []
    if section is not None and source_id is not None:
        raise ReviewInputBundleError("section and source_id filters are mutually exclusive")
    if source_id is not None:
        return [
            deepcopy(dict(item))
            for item in artifact.get("source_inventory", [])
            if isinstance(item, Mapping) and item.get("source_id") == source_id
        ]
    if section is not None:
        frozen_sections = {
            "episode",
            "episode_snapshot_catalog",
            "portfolio_context_episode_slice",
            "linked_decisions",
            "supplemental_sources",
        }
        top_sections = {
            "build_request",
            "episode_ref",
            "portfolio_context_ref",
            "source_verification",
            "frozen_sources",
            "source_inventory",
            "section_availability",
            "release_readiness",
            "warnings",
            "canonicalization",
        }
        if section in frozen_sections:
            return [deepcopy((artifact.get("frozen_sources") or {}).get(section))]
        if section in top_sections:
            return [deepcopy(artifact.get(section))]
        raise ReviewInputBundleError(f"unsupported review-input section: {section}")
    return [deepcopy(dict(artifact))]
