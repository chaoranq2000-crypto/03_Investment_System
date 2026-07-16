"""Deterministic, traceable P2F episode-review artifacts.

P2F-2 is deliberately facts-only.  It consumes one already-frozen P2F-1
review-input bundle, never queries a database or network source, and emits six
sections whose statements are generated from fixed neutral templates.  Later
P2F units may add reviewed interpretations or human revisions without changing
the facts produced here.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
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
from .review_input_bundle import (
    SCHEMA_VERSION as INPUT_BUNDLE_SCHEMA_VERSION,
    ReviewInputBundleError,
    validate_review_input_bundle,
)


SCHEMA_VERSION = "p2f.episode_review.v1"
VALIDATION_SCHEMA_VERSION = "p2f.episode_review.validation.v1"
FACT_ENGINE_VERSION = "p2f.facts.v1"

FACT_SECTION_NAMES = (
    "timeline",
    "security_context",
    "portfolio_context",
    "market_context",
    "outcome_context",
    "execution_consistency",
)
INTERPRETATION_SECTION_NAMES = (
    "main_tensions",
    "hypotheses",
    "alternative_explanations",
    "counterfactual_options",
    "history_links",
)

_CONTRACT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "contracts"
    / "P2F_EPISODE_REVIEW_DRAFT.schema.json"
)
_CONTENT_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_FACT_ID_RE = re.compile(r"^fact:[0-9a-f]{32}$")
_REVIEW_ID_RE = re.compile(r"^review:[0-9a-f]{32}$")
_CLAIM_TYPES = {
    "fact",
    "estimate",
    "management_comment",
    "analyst_view",
    "opinion",
    "unknown",
}
_AVAILABILITY = {
    "available",
    "partial",
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
    "partial",
    "missing",
    "not_applicable",
    "available",
)
_TEMPORAL_ROLES = {
    "known_at_decision",
    "learned_during_episode",
    "known_after_episode",
    "not_applicable",
}
_KIND_SECTION = {
    "episode_lifecycle": "timeline",
    "execution_event": "timeline",
    "security_identity": "security_context",
    "recorded_decision": "security_context",
    "recorded_note": "security_context",
    "portfolio_anchor": "portfolio_context",
    "portfolio_metric": "portfolio_context",
    "portfolio_delta": "portfolio_context",
    "market_record": "market_context",
    "outcome_record": "outcome_context",
    "decision_execution_link": "execution_consistency",
    "plan_execution_comparison": "execution_consistency",
}
_KIND_ORDER = {kind: index for index, kind in enumerate(_KIND_SECTION)}
_NON_EX_ANTE_KINDS = {
    "execution_event",
    "portfolio_delta",
    "outcome_record",
    "decision_execution_link",
    "plan_execution_comparison",
}
_NOT_APPLICABLE_KINDS = {"episode_lifecycle", "security_identity"}
_MARKET_KINDS = {"market_context", "price", "classification"}
_PLAN_FIELDS = {
    "planned_symbol": "symbol",
    "planned_market": "market",
    "planned_side": "side",
    "planned_quantity": "quantity",
}
_DATA_KEYS: dict[str, tuple[set[str], set[str]]] = {
    "episode_lifecycle": (
        {
            "episode_id",
            "status",
            "origin",
            "direction",
            "opened_at",
            "closed_at",
            "opening_event_id",
            "closing_event_id",
            "starting_quantity",
            "ending_quantity",
            "maximum_absolute_quantity",
            "material_transition_count",
        },
        set(),
    ),
    "execution_event": (
        {
            "event_id",
            "event_type",
            "side",
            "signed_quantity",
            "quantity_before",
            "quantity_after",
            "ordering_key",
        },
        set(),
    ),
    "security_identity": (
        {"account_id", "instrument_id", "symbol", "market", "currency"},
        set(),
    ),
    "recorded_decision": (
        {
            "decision_id",
            "event_ids",
            "relations",
            "payload_content_id",
            "source_claim_type",
            "recorded_fields",
        },
        set(),
    ),
    "recorded_note": (
        {"source_id", "payload_content_id", "source_claim_type", "payload_keys"},
        set(),
    ),
    "portfolio_anchor": (
        {
            "context_id",
            "event_id",
            "anchor_kind",
            "side",
            "snapshot_status",
            "snapshot_id",
            "revision",
            "cursor_scope",
            "metric_availability_ceiling",
        },
        set(),
    ),
    "portfolio_metric": (
        {
            "context_id",
            "event_id",
            "anchor_kind",
            "side",
            "metric_key",
            "availability",
            "method",
        },
        {"value", "unit"},
    ),
    "portfolio_delta": (
        {
            "delta_id",
            "event_id",
            "metric_key",
            "from_context_id",
            "to_context_id",
            "availability",
            "method_compatibility",
        },
        {"value", "unit"},
    ),
    "market_record": (
        {
            "source_id",
            "source_kind",
            "payload_content_id",
            "source_claim_type",
            "payload_keys",
        },
        set(),
    ),
    "outcome_record": (
        {
            "source_id",
            "payload_content_id",
            "source_claim_type",
            "payload_keys",
            "final",
        },
        {"realized_pnl", "currency"},
    ),
    "decision_execution_link": (
        {
            "decision_id",
            "event_id",
            "relation",
            "link_status",
            "decision_known_at",
            "event_effective_at",
            "link_content_id",
        },
        set(),
    ),
    "plan_execution_comparison": (
        {
            "decision_id",
            "event_id",
            "field",
            "planned_value",
            "actual_value",
            "result",
        },
        set(),
    ),
}
_FORBIDDEN_DATA_KEYS = {
    "entry_reason",
    "decision_quality",
    "recommendation",
    "advice",
    "score",
    "buy_signal",
    "sell_signal",
}
_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


class EpisodeReviewError(ValueError):
    """Raised when an episode review cannot be built or verified safely."""


def _value_content_id(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _content_id(value: Mapping[str, Any]) -> str:
    material = deepcopy(dict(value))
    material.pop("content_id", None)
    return _value_content_id(material)


def _review_id(episode_id: str) -> str:
    digest = hashlib.sha256(
        canonical_json_bytes(
            {"schema_version": SCHEMA_VERSION, "episode_id": episode_id}
        )
    ).hexdigest()
    return "review:" + digest[:32]


def _parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise EpisodeReviewError(f"{field} must be a timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EpisodeReviewError(f"invalid {field}: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EpisodeReviewError(f"{field} must include a timezone")
    if parsed.microsecond:
        raise EpisodeReviewError(f"{field} must use whole seconds")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _canonical_timestamp(value: object, field: str) -> str:
    parsed = _parse_timestamp(value, field)
    return _iso(parsed)


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


def _merge_availability(*values: object) -> str:
    normalized = {
        str(value)
        for value in values
        if str(value) in _AVAILABILITY
    }
    for candidate in _AVAILABILITY_PRIORITY:
        if candidate in normalized:
            return candidate
    return "available"


def _source_claim_type(payload: Mapping[str, Any]) -> str:
    value = str(payload.get("claim_type") or "unknown")
    return value if value in _CLAIM_TYPES else "unknown"


def _inventory_index(bundle: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    inventory = bundle.get("source_inventory")
    if not isinstance(inventory, list):
        raise EpisodeReviewError("input bundle source_inventory must be an array")
    for item in inventory:
        if not isinstance(item, Mapping):
            raise EpisodeReviewError("input bundle source_inventory contains a non-object")
        source_id = str(item.get("source_id") or "")
        if not source_id or source_id in index:
            raise EpisodeReviewError("input bundle source IDs must be unique and non-empty")
        index[source_id] = dict(item)
    return index


def _source_ref(item: Mapping[str, Any]) -> dict[str, str]:
    return {
        "source_id": str(item.get("source_id") or ""),
        "source_kind": str(item.get("source_kind") or ""),
        "content_id": str(item.get("content_id") or ""),
        "locator": str(item.get("locator") or ""),
        "frozen_pointer": str(item.get("frozen_pointer") or ""),
    }


def _refs_for_ids(
    inventory: Mapping[str, Mapping[str, Any]], source_ids: Iterable[object]
) -> list[dict[str, str]]:
    refs: dict[str, dict[str, str]] = {}
    for raw_id in source_ids:
        source_id = str(raw_id or "")
        if not source_id or source_id not in inventory:
            continue
        refs[source_id] = _source_ref(inventory[source_id])
    return sorted(
        refs.values(),
        key=lambda item: (
            item["source_kind"],
            item["source_id"],
            item["content_id"],
            item["frozen_pointer"],
        ),
    )


def _times_from_source_rows(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[str, str] | None:
    effective_values: list[datetime] = []
    knowledge_values: list[datetime] = []
    for row in rows:
        effective = row.get("effective_at")
        known = row.get("knowledge_at")
        if effective in (None, "") or known in (None, ""):
            continue
        effective_values.append(_parse_timestamp(effective, "source.effective_at"))
        knowledge_values.append(_parse_timestamp(known, "source.knowledge_at"))
    if not effective_values or not knowledge_values:
        return None
    effective = max(effective_values)
    known = max(knowledge_values)
    if known < effective:
        raise EpisodeReviewError("source knowledge time precedes effective time")
    return _iso(effective), _iso(known)


def _nested_source_rows(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    snapshot = context.get("portfolio_snapshot")
    if isinstance(snapshot, Mapping):
        rows.extend(
            dict(item)
            for item in snapshot.get("source_refs", [])
            if isinstance(item, Mapping)
        )
    metrics = context.get("metrics")
    if isinstance(metrics, Mapping):
        for metric in metrics.values():
            if isinstance(metric, Mapping):
                rows.extend(
                    dict(item)
                    for item in metric.get("source_refs", [])
                    if isinstance(item, Mapping)
                )
    return rows


def _temporal_role(
    *,
    kind: str,
    knowledge_at: str,
    opened_at: str,
    closed_at: str | None,
    ex_ante_eligible: bool,
) -> str:
    known = _parse_timestamp(knowledge_at, "fact.knowledge_at")
    opened = _parse_timestamp(opened_at, "episode.opened_at")
    closed = (
        _parse_timestamp(closed_at, "episode.closed_at")
        if closed_at is not None
        else None
    )
    if kind not in _NON_EX_ANTE_KINDS and ex_ante_eligible and known < opened:
        return "known_at_decision"
    if closed is not None and known > closed:
        return "known_after_episode"
    return "learned_during_episode"


def _expected_statement(kind: str, data: Mapping[str, Any]) -> str:
    if kind == "episode_lifecycle":
        return (
            f"Episode {data['episode_id']} is recorded as {data['status']} with "
            f"{data['material_transition_count']} material transition(s)."
        )
    if kind == "execution_event":
        return (
            f"Execution event {data['event_id']} records side {data['side']} and "
            f"signed quantity {data['signed_quantity']}."
        )
    if kind == "security_identity":
        return (
            f"Episode scope identifies instrument {data['instrument_id']} with "
            f"symbol {data['symbol']}."
        )
    if kind == "recorded_decision":
        return (
            f"Decision source {data['decision_id']} is explicitly linked to "
            f"{len(data['event_ids'])} execution event(s)."
        )
    if kind == "recorded_note":
        return f"Recorded note source {data['source_id']} is frozen without reinterpretation."
    if kind == "portfolio_anchor":
        return (
            f"Portfolio context {data['context_id']} records the {data['side']} state "
            f"for event {data['event_id']} with snapshot status {data['snapshot_status']}."
        )
    if kind == "portfolio_metric":
        return (
            f"Portfolio metric {data['metric_key']} is recorded as "
            f"{data['availability']} for context {data['context_id']}."
        )
    if kind == "portfolio_delta":
        return (
            f"Portfolio delta {data['metric_key']} is recorded as "
            f"{data['availability']} for event {data['event_id']}."
        )
    if kind == "market_record":
        return (
            f"Market source {data['source_id']} of kind {data['source_kind']} is "
            "frozen without reinterpretation."
        )
    if kind == "outcome_record":
        return f"Outcome source {data['source_id']} is frozen without judging decision quality."
    if kind == "decision_execution_link":
        return (
            f"Decision {data['decision_id']} has an explicit {data['relation']} link "
            f"to event {data['event_id']}."
        )
    if kind == "plan_execution_comparison":
        return (
            f"Recorded plan field {data['field']} {data['result']} the linked "
            "execution value."
        )
    raise EpisodeReviewError(f"unsupported fact kind: {kind}")


def _fact(
    *,
    kind: str,
    availability: str,
    temporal_role: str,
    effective_at: str | None,
    knowledge_at: str | None,
    source_refs: Sequence[Mapping[str, Any]],
    warning_codes: Iterable[object],
    data: Mapping[str, Any],
) -> dict[str, Any]:
    if kind not in _KIND_SECTION:
        raise EpisodeReviewError(f"unsupported fact kind: {kind}")
    if availability not in _AVAILABILITY:
        raise EpisodeReviewError(f"unsupported fact availability: {availability}")
    if temporal_role not in _TEMPORAL_ROLES:
        raise EpisodeReviewError(f"unsupported temporal role: {temporal_role}")
    if temporal_role == "not_applicable":
        if effective_at is not None or knowledge_at is not None:
            raise EpisodeReviewError("not_applicable facts cannot carry source times")
    else:
        effective_at = _canonical_timestamp(effective_at, "fact.effective_at")
        knowledge_at = _canonical_timestamp(knowledge_at, "fact.knowledge_at")
        if _parse_timestamp(knowledge_at, "fact.knowledge_at") < _parse_timestamp(
            effective_at, "fact.effective_at"
        ):
            raise EpisodeReviewError("fact knowledge_at precedes effective_at")
    refs = [dict(item) for item in source_refs]
    if not refs:
        raise EpisodeReviewError(f"{kind} fact requires at least one frozen source ref")
    refs.sort(
        key=lambda item: (
            str(item.get("source_kind") or ""),
            str(item.get("source_id") or ""),
            str(item.get("content_id") or ""),
            str(item.get("frozen_pointer") or ""),
        )
    )
    payload: dict[str, Any] = {
        "fact_id": "",
        "kind": kind,
        "claim_type": "fact",
        "statement": _expected_statement(kind, data),
        "availability": availability,
        "temporal_role": temporal_role,
        "effective_at": effective_at,
        "knowledge_at": knowledge_at,
        "source_refs": refs,
        "warning_codes": sorted({str(item) for item in warning_codes if str(item)}),
        "data": deepcopy(dict(data)),
    }
    identity = deepcopy(payload)
    identity.pop("fact_id", None)
    payload["fact_id"] = "fact:" + hashlib.sha256(
        canonical_json_bytes(identity)
    ).hexdigest()[:32]
    return payload


def _event_order(event: Mapping[str, Any]) -> tuple[datetime, int, str, str]:
    ordering = event.get("ordering_key")
    if not isinstance(ordering, list) or len(ordering) != 4:
        raise EpisodeReviewError("event ordering_key must contain four fields")
    try:
        rank = int(ordering[1])
    except (TypeError, ValueError) as exc:
        raise EpisodeReviewError("event ordering rank must be an integer") from exc
    return (
        _parse_timestamp(ordering[0], "event.ordering_key[0]"),
        rank,
        str(ordering[2]),
        str(ordering[3]),
    )


def _fact_sort_key(fact: Mapping[str, Any]) -> tuple[Any, ...]:
    kind = str(fact.get("kind") or "")
    data = fact.get("data") if isinstance(fact.get("data"), Mapping) else {}
    if kind == "episode_lifecycle":
        detail = (0, "", 0, "", "")
    elif kind == "execution_event":
        ordering = data.get("ordering_key")
        if isinstance(ordering, list) and len(ordering) == 4:
            try:
                rank = int(ordering[1])
            except (TypeError, ValueError):
                rank = 999999
            detail = (1, str(ordering[0]), rank, str(ordering[2]), str(ordering[3]))
        else:
            detail = (1, str(fact.get("effective_at") or ""), 999999, "", "")
    else:
        detail = (
            2 + _KIND_ORDER.get(kind, 999),
            str(fact.get("effective_at") or ""),
            0,
            canonical_json_bytes(data).decode("utf-8"),
            "",
        )
    return (*detail, str(fact.get("fact_id") or ""))


def _section(
    availability: Mapping[str, Any],
    facts: Iterable[Mapping[str, Any]],
    *,
    gap_codes: Iterable[object] = (),
) -> dict[str, Any]:
    rows = sorted([deepcopy(dict(item)) for item in facts], key=_fact_sort_key)
    source_ids = sorted(
        {str(item) for item in availability.get("source_ids", []) if str(item)}
    )
    warning_codes = sorted(
        {str(item) for item in availability.get("warning_codes", []) if str(item)}
    )
    status = str(availability.get("status") or "missing")
    if status not in _AVAILABILITY:
        status = "invalid"
    return {
        "status": status,
        "reason": str(availability.get("reason") or "No availability reason supplied."),
        "source_ids": source_ids,
        "warning_codes": warning_codes,
        "gap_codes": sorted({str(item) for item in gap_codes if str(item)}),
        "facts": rows,
    }


def _require_ready_bundle(bundle: Mapping[str, Any]) -> None:
    if not isinstance(bundle, Mapping):
        raise EpisodeReviewError("input bundle must be an object")
    validation = validate_review_input_bundle(bundle)
    if validation.get("validation_status") == "blocked":
        raise EpisodeReviewError("P2F-1 input bundle failed validation")
    if bundle.get("schema_version") != INPUT_BUNDLE_SCHEMA_VERSION:
        raise EpisodeReviewError("unsupported P2F-1 input bundle schema")
    release = bundle.get("release_readiness")
    verification = bundle.get("source_verification")
    if not isinstance(release, Mapping) or release.get("status") != "ready":
        raise EpisodeReviewError("facts review requires a release-ready P2F-1 bundle")
    if not isinstance(verification, Mapping) or verification.get("status") != "verified":
        raise EpisodeReviewError("facts review requires source-verified P2F-1 input")


def _safe_recorded_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    structured = _structured_plan(payload)
    result: dict[str, Any] = {}
    for key in _PLAN_FIELDS:
        value = structured.get(key)
        if value in (None, "") or isinstance(value, (Mapping, list, tuple, bool, float)):
            continue
        if key == "planned_quantity":
            try:
                result[key] = format(Decimal(str(value)), "f")
            except (InvalidOperation, ValueError):
                continue
        else:
            result[key] = str(value)
    return {key: result[key] for key in sorted(result)}


def _structured_plan(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        key: payload[key]
        for key in _PLAN_FIELDS
        if key in payload
    }
    nested = payload.get("execution_plan")
    gap_codes: set[str] = set()
    if isinstance(nested, Mapping):
        aliases = {
            "symbol": "planned_symbol",
            "market": "planned_market",
            "side": "planned_side",
            "quantity": "planned_quantity",
        }
        for source_key, target_key in aliases.items():
            if source_key not in nested:
                continue
            if target_key in result:
                left = _normalized_plan_value(target_key, result[target_key])
                right = _normalized_plan_value(target_key, nested[source_key])
                if left != right:
                    result.pop(target_key, None)
                    gap_codes.add("STRUCTURED_PLAN_CONTRADICTION")
                continue
            result[target_key] = nested[source_key]
        if nested.get("event_id") not in (None, ""):
            result["planned_event_id"] = str(nested["event_id"])
    result["_gap_codes"] = sorted(gap_codes)
    return result


def _source_payload_keys(payload: Mapping[str, Any]) -> list[str]:
    return sorted(str(key) for key in payload if str(key) != "statement")


def _context_source_ids(context: Mapping[str, Any]) -> list[str]:
    ids = [str(context.get("context_id") or "")]
    for row in _nested_source_rows(context):
        source_id = str(row.get("source_id") or "")
        if source_id:
            ids.append(source_id)
    return ids


def _context_times(
    context: Mapping[str, Any], event_by_id: Mapping[str, Mapping[str, Any]]
) -> tuple[str, str]:
    values = _times_from_source_rows(_nested_source_rows(context))
    if values is not None:
        return values
    anchor = context.get("anchor") if isinstance(context.get("anchor"), Mapping) else {}
    event_id = str(anchor.get("event_id") or "")
    event = event_by_id.get(event_id, {})
    effective = event.get("effective_at") or anchor.get("event_at")
    known = event.get("known_at") or effective
    return (
        _canonical_timestamp(effective, "context.event_at"),
        _canonical_timestamp(known, "context.known_at"),
    )


def _build_timeline_facts(
    episode: Mapping[str, Any],
    inventory: Mapping[str, Mapping[str, Any]],
    opened_at: str,
    closed_at: str | None,
) -> list[dict[str, Any]]:
    episode_id = str(episode.get("episode_id") or "")
    episode_refs = _refs_for_ids(inventory, [episode_id])
    lifecycle = _fact(
        kind="episode_lifecycle",
        availability="available",
        temporal_role="not_applicable",
        effective_at=None,
        knowledge_at=None,
        source_refs=episode_refs,
        warning_codes=[],
        data={
            "episode_id": episode_id,
            "status": str(episode.get("status") or ""),
            "origin": str(episode.get("origin") or ""),
            "direction": str(episode.get("direction") or ""),
            "opened_at": opened_at,
            "closed_at": closed_at,
            "opening_event_id": str(episode.get("opening_event_ref") or ""),
            "closing_event_id": (
                str(episode.get("closing_event_ref"))
                if episode.get("closing_event_ref") is not None
                else None
            ),
            "starting_quantity": str(episode.get("starting_quantity") or ""),
            "ending_quantity": str(episode.get("ending_quantity") or ""),
            "maximum_absolute_quantity": str(
                episode.get("maximum_absolute_quantity") or ""
            ),
            "material_transition_count": int(
                episode.get("material_transition_count") or 0
            ),
        },
    )
    facts = [lifecycle]
    events = sorted(
        [dict(item) for item in episode.get("event_refs", []) if isinstance(item, Mapping)],
        key=_event_order,
    )
    for event in events:
        event_id = str(event.get("event_id") or "")
        inventory_row = inventory.get(event_id, {})
        availability = str(inventory_row.get("status") or "available")
        effective = _canonical_timestamp(event.get("effective_at"), "event.effective_at")
        known = _canonical_timestamp(event.get("known_at"), "event.known_at")
        facts.append(
            _fact(
                kind="execution_event",
                availability=(availability if availability in _AVAILABILITY else "available"),
                temporal_role=_temporal_role(
                    kind="execution_event",
                    knowledge_at=known,
                    opened_at=opened_at,
                    closed_at=closed_at,
                    ex_ante_eligible=False,
                ),
                effective_at=effective,
                knowledge_at=known,
                source_refs=_refs_for_ids(inventory, [event_id]),
                warning_codes=inventory_row.get("warning_codes", []),
                data={
                    "event_id": event_id,
                    "event_type": str(event.get("event_type") or ""),
                    "side": str(event.get("side") or ""),
                    "signed_quantity": str(event.get("signed_quantity") or ""),
                    "quantity_before": str(event.get("quantity_before") or ""),
                    "quantity_after": str(event.get("quantity_after") or ""),
                    "ordering_key": [
                        effective,
                        event["ordering_key"][1],
                        str(event["ordering_key"][2]),
                        event_id,
                    ],
                },
            )
        )
    return facts


def _build_security_facts(
    episode: Mapping[str, Any],
    decisions: Sequence[Mapping[str, Any]],
    supplemental: Sequence[Mapping[str, Any]],
    inventory: Mapping[str, Mapping[str, Any]],
    opened_at: str,
    closed_at: str | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    episode_id = str(episode.get("episode_id") or "")
    scope = episode.get("scope") if isinstance(episode.get("scope"), Mapping) else {}
    facts = [
        _fact(
            kind="security_identity",
            availability="available",
            temporal_role="not_applicable",
            effective_at=None,
            knowledge_at=None,
            source_refs=_refs_for_ids(inventory, [episode_id]),
            warning_codes=[],
            data={
                "account_id": str(scope.get("account_id") or ""),
                "instrument_id": str(scope.get("instrument_id") or ""),
                "symbol": str(scope.get("symbol") or ""),
                "market": (
                    str(scope.get("market")) if scope.get("market") is not None else None
                ),
                "currency": str(scope.get("currency") or ""),
            },
        )
    ]
    gaps: set[str] = set()
    opening_id = str(episode.get("opening_event_ref") or "")
    if not decisions:
        gaps.add("RECORDED_DECISION_MISSING")
    for decision in decisions:
        decision_id = str(decision.get("source_id") or "")
        links = [
            dict(item)
            for item in decision.get("decision_link_refs", [])
            if isinstance(item, Mapping)
        ]
        event_ids = sorted(str(item.get("event_id") or "") for item in links)
        relations = sorted({str(item.get("relation") or "") for item in links})
        payload = decision.get("payload") if isinstance(decision.get("payload"), Mapping) else {}
        effective = _canonical_timestamp(
            decision.get("effective_at"), "decision.effective_at"
        )
        known = _canonical_timestamp(decision.get("knowledge_at"), "decision.knowledge_at")
        same_second_opening = (
            opening_id in event_ids
            and _parse_timestamp(known, "decision.knowledge_at")
            == _parse_timestamp(opened_at, "episode.opened_at")
        )
        decision_warnings = list(decision.get("warning_codes", []))
        decision_availability = str(decision.get("availability") or "available")
        if same_second_opening:
            decision_warnings.append(
                "SAME_SECOND_DECISION_AVAILABILITY_AMBIGUOUS"
            )
            decision_availability = _merge_availability(
                decision_availability, "ambiguous"
            )
            gaps.add("SAME_SECOND_DECISION_AVAILABILITY_AMBIGUOUS")
        facts.append(
            _fact(
                kind="recorded_decision",
                availability=decision_availability,
                temporal_role=_temporal_role(
                    kind="recorded_decision",
                    knowledge_at=known,
                    opened_at=opened_at,
                    closed_at=closed_at,
                    ex_ante_eligible=opening_id in event_ids,
                ),
                effective_at=effective,
                knowledge_at=known,
                source_refs=_refs_for_ids(inventory, [decision_id]),
                warning_codes=decision_warnings,
                data={
                    "decision_id": decision_id,
                    "event_ids": event_ids,
                    "relations": relations,
                    "payload_content_id": str(decision.get("payload_content_id") or ""),
                    "source_claim_type": _source_claim_type(payload),
                    "recorded_fields": _safe_recorded_fields(payload),
                },
            )
        )
    notes = [item for item in supplemental if item.get("source_kind") == "note"]
    for note in notes:
        source_id = str(note.get("source_id") or "")
        payload = note.get("payload") if isinstance(note.get("payload"), Mapping) else {}
        effective = _canonical_timestamp(note.get("effective_at"), "note.effective_at")
        known = _canonical_timestamp(note.get("knowledge_at"), "note.knowledge_at")
        facts.append(
            _fact(
                kind="recorded_note",
                availability=str(note.get("availability") or "available"),
                temporal_role=_temporal_role(
                    kind="recorded_note",
                    knowledge_at=known,
                    opened_at=opened_at,
                    closed_at=closed_at,
                    ex_ante_eligible=True,
                ),
                effective_at=effective,
                knowledge_at=known,
                source_refs=_refs_for_ids(inventory, [source_id]),
                warning_codes=note.get("warning_codes", []),
                data={
                    "source_id": source_id,
                    "payload_content_id": str(note.get("payload_content_id") or ""),
                    "source_claim_type": _source_claim_type(payload),
                    "payload_keys": _source_payload_keys(payload),
                },
            )
        )
    return facts, sorted(gaps)


def _build_portfolio_facts(
    portfolio_slice: Mapping[str, Any],
    episode: Mapping[str, Any],
    inventory: Mapping[str, Mapping[str, Any]],
    opened_at: str,
    closed_at: str | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    facts: list[dict[str, Any]] = []
    gaps: set[str] = set()
    events = {
        str(item.get("event_id") or ""): item
        for item in episode.get("event_refs", [])
        if isinstance(item, Mapping)
    }
    contexts = [
        dict(item)
        for item in portfolio_slice.get("contexts", [])
        if isinstance(item, Mapping)
    ]
    context_by_id = {str(item.get("context_id") or ""): item for item in contexts}
    if not contexts:
        gaps.add("PORTFOLIO_CONTEXT_MISSING")
    for context in contexts:
        context_id = str(context.get("context_id") or "")
        anchor = context.get("anchor") if isinstance(context.get("anchor"), Mapping) else {}
        snapshot = (
            context.get("portfolio_snapshot")
            if isinstance(context.get("portfolio_snapshot"), Mapping)
            else {}
        )
        binding = (
            context.get("source_binding")
            if isinstance(context.get("source_binding"), Mapping)
            else {}
        )
        snapshot_binding = (
            binding.get("snapshot_binding")
            if isinstance(binding.get("snapshot_binding"), Mapping)
            else {}
        )
        effective, known = _context_times(context, events)
        side = str(anchor.get("side") or "")
        anchor_kind = str(anchor.get("kind") or "")
        context_row = inventory.get(context_id, {})
        context_status = str(context_row.get("status") or "missing")
        refs = _refs_for_ids(inventory, _context_source_ids(context))
        facts.append(
            _fact(
                kind="portfolio_anchor",
                availability=(context_status if context_status in _AVAILABILITY else "ambiguous"),
                temporal_role=_temporal_role(
                    kind="portfolio_anchor",
                    knowledge_at=known,
                    opened_at=opened_at,
                    closed_at=closed_at,
                    ex_ante_eligible=anchor_kind == "episode_open" and side == "pre",
                ),
                effective_at=effective,
                knowledge_at=known,
                source_refs=refs,
                warning_codes=context_row.get("warning_codes", []),
                data={
                    "context_id": context_id,
                    "event_id": str(anchor.get("event_id") or ""),
                    "anchor_kind": anchor_kind,
                    "side": side,
                    "snapshot_status": str(snapshot.get("status") or "missing"),
                    "snapshot_id": snapshot.get("snapshot_id"),
                    "revision": snapshot.get("revision"),
                    "cursor_scope": str(
                        (snapshot.get("cursor_proof") or {}).get("cursor_scope")
                        if isinstance(snapshot.get("cursor_proof"), Mapping)
                        else "unknown"
                    ),
                    "metric_availability_ceiling": str(
                        snapshot_binding.get("metric_availability_ceiling") or "none"
                    ),
                },
            )
        )
        metrics = context.get("metrics") if isinstance(context.get("metrics"), Mapping) else {}
        for metric_key in sorted(metrics):
            metric = metrics[metric_key]
            if not isinstance(metric, Mapping):
                continue
            metric_data: dict[str, Any] = {
                "context_id": context_id,
                "event_id": str(anchor.get("event_id") or ""),
                "anchor_kind": anchor_kind,
                "side": side,
                "metric_key": str(metric_key),
                "availability": str(metric.get("availability") or "missing"),
                "method": deepcopy(metric.get("method")),
            }
            if metric.get("value") is not None:
                metric_data["value"] = str(metric.get("value"))
            if metric.get("unit") is not None:
                metric_data["unit"] = str(metric.get("unit"))
            metric_source_ids = [context_id]
            metric_source_rows = [
                dict(item)
                for item in metric.get("source_refs", [])
                if isinstance(item, Mapping)
            ]
            metric_source_ids.extend(
                str(item.get("source_id") or "") for item in metric_source_rows
            )
            metric_times = _times_from_source_rows(metric_source_rows) or (effective, known)
            availability = str(metric.get("availability") or "missing")
            facts.append(
                _fact(
                    kind="portfolio_metric",
                    availability=(availability if availability in _AVAILABILITY else "invalid"),
                    temporal_role=_temporal_role(
                        kind="portfolio_metric",
                        knowledge_at=metric_times[1],
                        opened_at=opened_at,
                        closed_at=closed_at,
                        ex_ante_eligible=anchor_kind == "episode_open" and side == "pre",
                    ),
                    effective_at=metric_times[0],
                    knowledge_at=metric_times[1],
                    source_refs=_refs_for_ids(inventory, metric_source_ids),
                    warning_codes=metric.get("warning_codes", []),
                    data=metric_data,
                )
            )
    for delta in [
        dict(item)
        for item in portfolio_slice.get("deltas", [])
        if isinstance(item, Mapping)
    ]:
        delta_id = str(delta.get("delta_id") or "")
        before = context_by_id.get(str(delta.get("from_context_id") or ""), {})
        after = context_by_id.get(str(delta.get("to_context_id") or ""), {})
        anchor = after.get("anchor") if isinstance(after.get("anchor"), Mapping) else {}
        endpoint_rows = [*_nested_source_rows(before), *_nested_source_rows(after)]
        times = _times_from_source_rows(endpoint_rows)
        if times is None:
            times = _context_times(after, events)
        raw_availability = str(delta.get("availability") or "missing")
        availability = (
            "not_applicable" if raw_availability == "not_comparable" else raw_availability
        )
        if availability not in _AVAILABILITY:
            availability = "invalid"
        data: dict[str, Any] = {
            "delta_id": delta_id,
            "event_id": str(anchor.get("event_id") or ""),
            "metric_key": str(delta.get("metric_key") or ""),
            "from_context_id": str(delta.get("from_context_id") or ""),
            "to_context_id": str(delta.get("to_context_id") or ""),
            "availability": availability,
            "method_compatibility": str(delta.get("method_compatibility") or "unknown"),
        }
        if delta.get("value") is not None and availability == "available":
            data["value"] = str(delta.get("value"))
        if delta.get("unit") is not None:
            data["unit"] = str(delta.get("unit"))
        delta_row = inventory.get(delta_id, {})
        facts.append(
            _fact(
                kind="portfolio_delta",
                availability=availability,
                temporal_role=_temporal_role(
                    kind="portfolio_delta",
                    knowledge_at=times[1],
                    opened_at=opened_at,
                    closed_at=closed_at,
                    ex_ante_eligible=False,
                ),
                effective_at=times[0],
                knowledge_at=times[1],
                source_refs=_refs_for_ids(inventory, [delta_id]),
                warning_codes=[
                    *delta.get("warning_codes", []),
                    *delta_row.get("warning_codes", []),
                ],
                data=data,
            )
        )
    return facts, sorted(gaps)


def _build_optional_source_facts(
    sources: Sequence[Mapping[str, Any]],
    *,
    source_kinds: set[str],
    fact_kind: str,
    inventory: Mapping[str, Mapping[str, Any]],
    opened_at: str,
    closed_at: str | None,
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for source in sources:
        source_kind = str(source.get("source_kind") or "")
        if source_kind not in source_kinds:
            continue
        source_id = str(source.get("source_id") or "")
        payload = source.get("payload") if isinstance(source.get("payload"), Mapping) else {}
        effective = _canonical_timestamp(source.get("effective_at"), "source.effective_at")
        known = _canonical_timestamp(source.get("knowledge_at"), "source.knowledge_at")
        if fact_kind == "market_record":
            data: dict[str, Any] = {
                "source_id": source_id,
                "source_kind": source_kind,
                "payload_content_id": str(source.get("payload_content_id") or ""),
                "source_claim_type": _source_claim_type(payload),
                "payload_keys": _source_payload_keys(payload),
            }
            eligible = True
        else:
            source_claim_type = _source_claim_type(payload)
            effective_dt = _parse_timestamp(effective, "outcome.effective_at")
            known_dt = _parse_timestamp(known, "outcome.knowledge_at")
            closed_dt = (
                _parse_timestamp(closed_at, "episode.closed_at")
                if closed_at is not None
                else None
            )
            data = {
                "source_id": source_id,
                "payload_content_id": str(source.get("payload_content_id") or ""),
                "source_claim_type": source_claim_type,
                "payload_keys": _source_payload_keys(payload),
                "final": bool(
                    source_claim_type == "fact"
                    and (
                        payload.get("final") is True
                        or payload.get("is_final") is True
                    )
                    and
                    closed_dt is not None
                    and effective_dt >= closed_dt
                    and known_dt >= closed_dt
                ),
            }
            if source_claim_type == "fact" and payload.get("realized_pnl") not in (None, "") and not isinstance(
                payload.get("realized_pnl"), (Mapping, list, tuple, bool, float)
            ):
                try:
                    data["realized_pnl"] = format(
                        Decimal(str(payload["realized_pnl"])), "f"
                    )
                except (InvalidOperation, ValueError):
                    pass
            if source_claim_type == "fact" and payload.get("currency") not in (None, "") and not isinstance(
                payload.get("currency"), (Mapping, list, tuple, bool, float)
            ):
                data["currency"] = str(payload["currency"]).upper()
            eligible = False
        source_warning_codes = list(source.get("warning_codes", []))
        if fact_kind == "outcome_record":
            if data["source_claim_type"] != "fact" and any(
                key in payload for key in ("realized_pnl", "final", "is_final")
            ):
                source_warning_codes.append("OUTCOME_CLAIM_NOT_FACT")
            if (
                payload.get("final") is True or payload.get("is_final") is True
            ) and data["final"] is not True:
                source_warning_codes.append("OUTCOME_FINALITY_UNVERIFIED")
        facts.append(
            _fact(
                kind=fact_kind,
                availability=str(source.get("availability") or "available"),
                temporal_role=_temporal_role(
                    kind=fact_kind,
                    knowledge_at=known,
                    opened_at=opened_at,
                    closed_at=closed_at,
                    ex_ante_eligible=eligible,
                ),
                effective_at=effective,
                knowledge_at=known,
                source_refs=_refs_for_ids(inventory, [source_id]),
                warning_codes=source_warning_codes,
                data=data,
            )
        )
    return facts


def _normalized_plan_value(field: str, value: object) -> str | None:
    if value in (None, "") or isinstance(value, (Mapping, list, tuple, bool, float)):
        return None
    if field == "planned_quantity":
        try:
            return format(abs(Decimal(str(value))), "f")
        except (InvalidOperation, ValueError):
            return None
    return str(value).strip().upper()


def _actual_plan_value(
    field: str, scope: Mapping[str, Any], event: Mapping[str, Any]
) -> str | None:
    if field == "planned_symbol":
        value = scope.get("symbol")
        return str(value).strip().upper() if value not in (None, "") else None
    if field == "planned_market":
        value = scope.get("market")
        return str(value).strip().upper() if value not in (None, "") else None
    if field == "planned_side":
        value = event.get("side")
        return str(value).strip().upper() if value not in (None, "") else None
    if field == "planned_quantity":
        try:
            return format(abs(Decimal(str(event.get("signed_quantity")))), "f")
        except (InvalidOperation, ValueError, TypeError):
            return None
    return None


def _build_execution_facts(
    episode: Mapping[str, Any],
    decisions: Sequence[Mapping[str, Any]],
    inventory: Mapping[str, Mapping[str, Any]],
    opened_at: str,
    closed_at: str | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    facts: list[dict[str, Any]] = []
    gaps: set[str] = set()
    events = {
        str(item.get("event_id") or ""): item
        for item in episode.get("event_refs", [])
        if isinstance(item, Mapping)
    }
    scope = episode.get("scope") if isinstance(episode.get("scope"), Mapping) else {}
    if not decisions:
        gaps.add("DECISION_LINK_MISSING")
    for decision in decisions:
        decision_id = str(decision.get("source_id") or "")
        decision_known = _canonical_timestamp(
            decision.get("knowledge_at"), "decision.knowledge_at"
        )
        payload = decision.get("payload") if isinstance(decision.get("payload"), Mapping) else {}
        structured_plan = _structured_plan(payload)
        gaps.update(str(item) for item in structured_plan.get("_gap_codes", []))
        links = [
            dict(item)
            for item in decision.get("decision_link_refs", [])
            if isinstance(item, Mapping)
        ]
        planned_event_id = str(structured_plan.get("planned_event_id") or "")
        link_event_ids = {
            str(item.get("event_id") or "") for item in links
        }
        if planned_event_id and planned_event_id not in link_event_ids:
            gaps.add("PLAN_EVENT_BINDING_MISMATCH")
        comparable_count = 0
        deviated = False
        for link in links:
            event_id = str(link.get("event_id") or "")
            event = events.get(event_id)
            if not isinstance(event, Mapping):
                continue
            event_effective = _canonical_timestamp(
                event.get("effective_at"), "event.effective_at"
            )
            event_known = _canonical_timestamp(event.get("known_at"), "event.known_at")
            fact_known = _iso(
                max(
                    _parse_timestamp(decision_known, "decision.knowledge_at"),
                    _parse_timestamp(event_known, "event.known_at"),
                )
            )
            refs = _refs_for_ids(inventory, [decision_id, event_id])
            link_status = str(link.get("availability") or "available")
            link_warnings = list(link.get("warning_codes", []))
            if _parse_timestamp(decision_known, "decision.knowledge_at") == _parse_timestamp(
                event_effective, "event.effective_at"
            ):
                link_status = _merge_availability(link_status, "ambiguous")
                link_warnings.append(
                    "SAME_SECOND_DECISION_AVAILABILITY_AMBIGUOUS"
                )
                gaps.add("SAME_SECOND_DECISION_AVAILABILITY_AMBIGUOUS")
            facts.append(
                _fact(
                    kind="decision_execution_link",
                    availability=(link_status if link_status in _AVAILABILITY else "invalid"),
                    temporal_role=_temporal_role(
                        kind="decision_execution_link",
                        knowledge_at=fact_known,
                        opened_at=opened_at,
                        closed_at=closed_at,
                        ex_ante_eligible=False,
                    ),
                    effective_at=event_effective,
                    knowledge_at=fact_known,
                    source_refs=refs,
                    warning_codes=link_warnings,
                    data={
                        "decision_id": decision_id,
                        "event_id": event_id,
                        "relation": str(link.get("relation") or ""),
                        "link_status": link_status,
                        "decision_known_at": decision_known,
                        "event_effective_at": event_effective,
                        "link_content_id": str(link.get("link_content_id") or ""),
                    },
                )
            )
            for plan_field in _PLAN_FIELDS:
                if planned_event_id and planned_event_id != event_id:
                    continue
                planned = _normalized_plan_value(
                    plan_field, structured_plan.get(plan_field)
                )
                actual = _actual_plan_value(plan_field, scope, event)
                if planned is None or actual is None:
                    continue
                if plan_field == "planned_quantity" and len(links) > 1:
                    gaps.add("PLAN_QUANTITY_MULTI_EVENT_NOT_COMPARABLE")
                    continue
                comparable_count += 1
                result = "matches" if planned == actual else "deviates"
                deviated = deviated or result == "deviates"
                facts.append(
                    _fact(
                        kind="plan_execution_comparison",
                        availability=(link_status if link_status in _AVAILABILITY else "invalid"),
                        temporal_role=_temporal_role(
                            kind="plan_execution_comparison",
                            knowledge_at=fact_known,
                            opened_at=opened_at,
                            closed_at=closed_at,
                            ex_ante_eligible=False,
                        ),
                        effective_at=event_effective,
                        knowledge_at=fact_known,
                        source_refs=refs,
                        warning_codes=link_warnings,
                        data={
                            "decision_id": decision_id,
                            "event_id": event_id,
                            "field": plan_field,
                            "planned_value": planned,
                            "actual_value": actual,
                            "result": result,
                        },
                    )
                )
        if comparable_count == 0:
            gaps.add("COMPARABLE_PLAN_FIELDS_MISSING")
        if deviated and payload.get("deviation_reason") in (None, ""):
            gaps.add("DEVIATION_REASON_MISSING")
    return facts, sorted(gaps)


def _review_warnings(bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for item in bundle.get("warnings", []):
        if not isinstance(item, Mapping):
            continue
        severity = str(item.get("severity") or "warning")
        if severity not in _SEVERITY_ORDER:
            severity = "warning"
        values.append(
            {
                "code": str(item.get("code") or "SOURCE_WARNING"),
                "severity": severity,
                "message": str(item.get("message") or "Upstream warning preserved."),
                "target_ids": sorted(
                    {
                        str(value)
                        for value in item.get("source_ids", [])
                        if str(value)
                    }
                ),
            }
        )
    unique = {canonical_json_bytes(item): item for item in values}
    return sorted(
        unique.values(),
        key=lambda item: (
            _SEVERITY_ORDER[item["severity"]],
            item["code"],
            item["target_ids"],
            item["message"],
        ),
    )


def build_facts_only_episode_review(
    input_bundle: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a deterministic six-section facts-only episode review."""

    _require_ready_bundle(input_bundle)
    inventory = _inventory_index(input_bundle)
    frozen = input_bundle.get("frozen_sources")
    if not isinstance(frozen, Mapping):
        raise EpisodeReviewError("input bundle frozen_sources must be an object")
    episode = frozen.get("episode")
    if not isinstance(episode, Mapping):
        raise EpisodeReviewError("input bundle has no frozen episode")
    episode_id = str(episode.get("episode_id") or "")
    opened_at = _canonical_timestamp(episode.get("opened_at"), "episode.opened_at")
    closed_at = (
        _canonical_timestamp(episode.get("closed_at"), "episode.closed_at")
        if episode.get("closed_at") is not None
        else None
    )
    portfolio_slice = frozen.get("portfolio_context_episode_slice")
    if not isinstance(portfolio_slice, Mapping):
        raise EpisodeReviewError("input bundle has no portfolio context episode slice")
    decisions = [
        dict(item)
        for item in frozen.get("linked_decisions", [])
        if isinstance(item, Mapping)
    ]
    supplemental = [
        dict(item)
        for item in frozen.get("supplemental_sources", [])
        if isinstance(item, Mapping)
    ]
    section_availability = input_bundle.get("section_availability")
    if not isinstance(section_availability, Mapping):
        raise EpisodeReviewError("input bundle section_availability must be an object")

    timeline_facts = _build_timeline_facts(
        episode, inventory, opened_at, closed_at
    )
    security_facts, security_gaps = _build_security_facts(
        episode,
        decisions,
        supplemental,
        inventory,
        opened_at,
        closed_at,
    )
    portfolio_facts, portfolio_gaps = _build_portfolio_facts(
        portfolio_slice,
        episode,
        inventory,
        opened_at,
        closed_at,
    )
    market_facts = _build_optional_source_facts(
        supplemental,
        source_kinds=_MARKET_KINDS,
        fact_kind="market_record",
        inventory=inventory,
        opened_at=opened_at,
        closed_at=closed_at,
    )
    outcome_facts = _build_optional_source_facts(
        supplemental,
        source_kinds={"outcome"},
        fact_kind="outcome_record",
        inventory=inventory,
        opened_at=opened_at,
        closed_at=closed_at,
    )
    execution_facts, execution_gaps = _build_execution_facts(
        episode, decisions, inventory, opened_at, closed_at
    )
    timeline_gaps: list[str] = []
    if not any(item["kind"] == "execution_event" for item in timeline_facts):
        timeline_gaps.append("TIMELINE_MISSING")
    if str((section_availability.get("timeline") or {}).get("status")) == "ambiguous":
        timeline_gaps.append("EVENT_ORDER_AMBIGUOUS")
    market_status = str(
        (section_availability.get("market_context") or {}).get("status") or "missing"
    )
    market_gaps = (
        ["MARKET_CONTEXT_WITHHELD_BY_CUTOFF"]
        if market_status == "withheld_by_cutoff"
        else ["MARKET_CONTEXT_MISSING"]
        if not market_facts
        else []
    )
    outcome_status = str(
        (section_availability.get("outcome_context") or {}).get("status") or "missing"
    )
    outcome_gaps: list[str] = []
    if outcome_status == "withheld_by_cutoff":
        outcome_gaps.append("OUTCOME_WITHHELD_BY_CUTOFF")
    elif not outcome_facts:
        outcome_gaps.append("OUTCOME_CONTEXT_MISSING")
    if any(
        (fact.get("data") or {}).get("source_claim_type") != "fact"
        for fact in outcome_facts
        if isinstance(fact.get("data"), Mapping)
    ):
        outcome_gaps.append("OUTCOME_CLAIM_NOT_FACT")
    if closed_at is not None and outcome_facts and not any(
        (fact.get("data") or {}).get("final") is True
        for fact in outcome_facts
        if isinstance(fact.get("data"), Mapping)
    ):
        outcome_gaps.append("FINAL_OUTCOME_UNVERIFIED")
    if closed_at is None:
        outcome_gaps.append("OPEN_EPISODE_OUTCOME_NOT_FINAL")

    artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "content_id": "",
        "review_id": _review_id(episode_id),
        "input_bundle_ref": {
            "schema_version": INPUT_BUNDLE_SCHEMA_VERSION,
            "content_id": str(input_bundle.get("content_id") or ""),
            "episode_id": episode_id,
        },
        "revision": {
            "revision_no": 1,
            "status": "draft",
            "supersedes_content_id": None,
            "correction_reason": None,
        },
        "fact_sections": {
            "timeline": _section(
                section_availability.get("timeline", {}),
                timeline_facts,
                gap_codes=timeline_gaps,
            ),
            "security_context": _section(
                section_availability.get("security_context", {}),
                security_facts,
                gap_codes=security_gaps,
            ),
            "portfolio_context": _section(
                section_availability.get("portfolio_context", {}),
                portfolio_facts,
                gap_codes=portfolio_gaps,
            ),
            "market_context": _section(
                section_availability.get("market_context", {}),
                market_facts,
                gap_codes=market_gaps,
            ),
            "outcome_context": _section(
                section_availability.get("outcome_context", {}),
                outcome_facts,
                gap_codes=outcome_gaps,
            ),
            "execution_consistency": _section(
                section_availability.get("execution_consistency", {}),
                execution_facts,
                gap_codes=execution_gaps,
            ),
        },
        "interpretation_sections": {
            name: [] for name in INTERPRETATION_SECTION_NAMES
        },
        "governance": {
            "facts_interpretation_separated": True,
            "no_advice": True,
            "no_mechanical_score": True,
            "generation_mode": "facts_only",
            "model_generation": None,
            "human_reviews": [],
        },
        "warnings": _review_warnings(input_bundle),
    }
    artifact["content_id"] = _content_id(artifact)
    validation = validate_episode_review(artifact)
    if validation["validation_status"] == "blocked":
        raise EpisodeReviewError(
            "built facts-only review failed validation: "
            + "; ".join(item["message"] for item in validation["findings"])
        )
    return artifact


def _contains_forbidden_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN_DATA_KEYS:
                return True
            if _contains_forbidden_key(item):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _nullable_string(value: object) -> bool:
    return value is None or _nonempty_string(value)


def _integer(value: object, *, minimum: int | None = None) -> bool:
    if isinstance(value, bool) or not isinstance(value, int):
        return False
    return minimum is None or value >= minimum


def _decimal_string(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return False
    return parsed.is_finite() and format(parsed, "f") == value


def _canonical_time(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return value == _iso(_parse_timestamp(value, "fact.data timestamp"))
    except EpisodeReviewError:
        return False


def _sorted_unique_strings(value: object, *, allow_empty: bool = True) -> bool:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        return False
    if not allow_empty and not value:
        return False
    return value == sorted(set(value))


def _fact_data_type_errors(
    kind: str, data: Mapping[str, Any], fact: Mapping[str, Any]
) -> list[str]:
    errors: list[str] = []

    def require_strings(*keys: str) -> None:
        for key in keys:
            if not _nonempty_string(data.get(key)):
                errors.append(f"{key} must be a non-empty string")

    if kind == "episode_lifecycle":
        require_strings(
            "episode_id",
            "status",
            "origin",
            "direction",
            "opened_at",
            "opening_event_id",
            "starting_quantity",
            "ending_quantity",
            "maximum_absolute_quantity",
        )
        if data.get("status") not in {"open", "closed", "data_gap", "ambiguous"}:
            errors.append("status is outside the P2C episode enum")
        if data.get("direction") not in {"long", "short"}:
            errors.append("direction must be long or short")
        if not _canonical_time(data.get("opened_at")):
            errors.append("opened_at must be canonical UTC seconds")
        if data.get("closed_at") is not None and not _canonical_time(
            data.get("closed_at")
        ):
            errors.append("closed_at must be null or canonical UTC seconds")
        if not _nullable_string(data.get("closing_event_id")):
            errors.append("closing_event_id must be null or a non-empty string")
        for key in (
            "starting_quantity",
            "ending_quantity",
            "maximum_absolute_quantity",
        ):
            if not _decimal_string(data.get(key)):
                errors.append(f"{key} must be a canonical Decimal string")
        if not _integer(data.get("material_transition_count"), minimum=1):
            errors.append("material_transition_count must be a positive integer")
    elif kind == "execution_event":
        require_strings("event_id", "event_type", "side")
        if data.get("side") not in {
            "BUY",
            "SELL",
            "TRANSFER_IN",
            "TRANSFER_OUT",
            "OTHER",
        }:
            errors.append("side is outside the P2C execution enum")
        for key in ("signed_quantity", "quantity_before", "quantity_after"):
            if not _decimal_string(data.get(key)):
                errors.append(f"{key} must be a canonical Decimal string")
        ordering = data.get("ordering_key")
        if not isinstance(ordering, list) or len(ordering) != 4:
            errors.append("ordering_key must contain exactly four fields")
        else:
            if not _canonical_time(ordering[0]):
                errors.append("ordering_key[0] must be canonical UTC seconds")
            if not _integer(ordering[1]):
                errors.append("ordering_key[1] must be an integer")
            if not _nonempty_string(ordering[2]) or not _nonempty_string(ordering[3]):
                errors.append("ordering_key tie-break fields must be non-empty strings")
            if ordering[3] != data.get("event_id"):
                errors.append("ordering_key must close over event_id")
            if ordering[0] != fact.get("effective_at"):
                errors.append("ordering_key time must equal fact effective_at")
    elif kind == "security_identity":
        require_strings("account_id", "instrument_id", "symbol", "currency")
        if not _nullable_string(data.get("market")):
            errors.append("market must be null or a non-empty string")
    elif kind == "recorded_decision":
        require_strings("decision_id", "payload_content_id", "source_claim_type")
        if not _CONTENT_ID_RE.fullmatch(str(data.get("payload_content_id") or "")):
            errors.append("payload_content_id must be a canonical content ID")
        if data.get("source_claim_type") not in _CLAIM_TYPES:
            errors.append("source_claim_type is invalid")
        if not _sorted_unique_strings(data.get("event_ids"), allow_empty=False):
            errors.append("event_ids must be sorted, unique and non-empty")
        if not _sorted_unique_strings(data.get("relations"), allow_empty=False):
            errors.append("relations must be sorted, unique and non-empty")
        recorded = data.get("recorded_fields")
        if not isinstance(recorded, Mapping) or set(recorded) - set(_PLAN_FIELDS):
            errors.append("recorded_fields contains unsupported plan fields")
        else:
            for key, value in recorded.items():
                if not _nonempty_string(value):
                    errors.append(f"recorded_fields.{key} must be a non-empty string")
                if key == "planned_quantity" and not _decimal_string(value):
                    errors.append("recorded planned_quantity must be Decimal text")
    elif kind in {"recorded_note", "market_record", "outcome_record"}:
        require_strings("source_id", "payload_content_id", "source_claim_type")
        if not _CONTENT_ID_RE.fullmatch(str(data.get("payload_content_id") or "")):
            errors.append("payload_content_id must be a canonical content ID")
        if data.get("source_claim_type") not in _CLAIM_TYPES:
            errors.append("source_claim_type is invalid")
        if not _sorted_unique_strings(data.get("payload_keys")):
            errors.append("payload_keys must be sorted unique strings")
        if kind == "market_record":
            require_strings("source_kind")
            if data.get("source_kind") not in _MARKET_KINDS:
                errors.append("market source_kind is invalid")
        if kind == "outcome_record":
            if not isinstance(data.get("final"), bool):
                errors.append("final must be boolean")
            if "realized_pnl" in data and not _decimal_string(data.get("realized_pnl")):
                errors.append("realized_pnl must be a canonical Decimal string")
            if "currency" in data and not _nonempty_string(data.get("currency")):
                errors.append("currency must be a non-empty string")
            if (
                data.get("final") is True or "realized_pnl" in data
            ) and data.get("source_claim_type") != "fact":
                errors.append("final/P&L values require source_claim_type=fact")
    elif kind == "portfolio_anchor":
        require_strings(
            "context_id",
            "event_id",
            "anchor_kind",
            "side",
            "snapshot_status",
            "cursor_scope",
            "metric_availability_ceiling",
        )
        if data.get("anchor_kind") not in {
            "episode_open",
            "episode_close",
            "position_change",
        }:
            errors.append("anchor_kind is invalid")
        if data.get("side") not in {"pre", "post"}:
            errors.append("portfolio side must be pre or post")
        if data.get("snapshot_status") not in {
            "exact",
            "replayed",
            "missing",
            "ambiguous",
            "invalid",
        }:
            errors.append("snapshot_status is invalid")
        if not _nullable_string(data.get("snapshot_id")):
            errors.append("snapshot_id must be null or a non-empty string")
        if data.get("revision") is not None and not _integer(
            data.get("revision"), minimum=1
        ):
            errors.append("revision must be null or a positive integer")
        if data.get("cursor_scope") not in {"unknown", "partition", "account"}:
            errors.append("cursor_scope is invalid")
        if data.get("metric_availability_ceiling") not in {
            "available",
            "partial",
            "none",
        }:
            errors.append("metric_availability_ceiling is invalid")
    elif kind == "portfolio_metric":
        require_strings(
            "context_id",
            "event_id",
            "anchor_kind",
            "side",
            "metric_key",
            "availability",
        )
        if data.get("anchor_kind") not in {
            "episode_open",
            "episode_close",
            "position_change",
        }:
            errors.append("anchor_kind is invalid")
        if data.get("side") not in {"pre", "post"}:
            errors.append("portfolio side must be pre or post")
        if data.get("availability") not in _AVAILABILITY:
            errors.append("metric availability is invalid")
        if fact.get("availability") != data.get("availability"):
            errors.append("metric fact/data availability mismatch")
        if not isinstance(data.get("method"), Mapping):
            errors.append("metric method must be an object")
        if "value" in data and not _decimal_string(data.get("value")):
            errors.append("metric value must be a canonical Decimal string")
        if data.get("availability") in {"available", "partial"} and "value" not in data:
            errors.append("available/partial metric requires value")
        if "unit" in data and not _nonempty_string(data.get("unit")):
            errors.append("metric unit must be a non-empty string")
    elif kind == "portfolio_delta":
        require_strings(
            "delta_id",
            "event_id",
            "metric_key",
            "from_context_id",
            "to_context_id",
            "availability",
            "method_compatibility",
        )
        if data.get("availability") not in _AVAILABILITY:
            errors.append("delta availability is invalid")
        if fact.get("availability") != data.get("availability"):
            errors.append("delta fact/data availability mismatch")
        if data.get("method_compatibility") not in {
            "same",
            "incompatible",
            "unknown",
        }:
            errors.append("method_compatibility is invalid")
        if "value" in data and not _decimal_string(data.get("value")):
            errors.append("delta value must be a canonical Decimal string")
        if data.get("availability") == "available" and "value" not in data:
            errors.append("available delta requires value")
        if data.get("availability") != "available" and "value" in data:
            errors.append("non-available delta cannot publish a value")
        if "unit" in data and not _nonempty_string(data.get("unit")):
            errors.append("delta unit must be a non-empty string")
    elif kind == "decision_execution_link":
        require_strings(
            "decision_id",
            "event_id",
            "relation",
            "link_status",
            "decision_known_at",
            "event_effective_at",
            "link_content_id",
        )
        if data.get("link_status") not in _AVAILABILITY:
            errors.append("link_status is invalid")
        if fact.get("availability") != data.get("link_status"):
            errors.append("link fact/data availability mismatch")
        for key in ("decision_known_at", "event_effective_at"):
            if not _canonical_time(data.get(key)):
                errors.append(f"{key} must be canonical UTC seconds")
        if data.get("event_effective_at") != fact.get("effective_at"):
            errors.append("event_effective_at must equal fact effective_at")
        if not _CONTENT_ID_RE.fullmatch(str(data.get("link_content_id") or "")):
            errors.append("link_content_id must be a canonical content ID")
    elif kind == "plan_execution_comparison":
        require_strings(
            "decision_id",
            "event_id",
            "field",
            "planned_value",
            "actual_value",
            "result",
        )
        field = str(data.get("field") or "")
        if field not in _PLAN_FIELDS:
            errors.append("comparison field is invalid")
        if data.get("result") not in {"matches", "deviates"}:
            errors.append("comparison result is invalid")
        planned = str(data.get("planned_value") or "")
        actual = str(data.get("actual_value") or "")
        if field == "planned_quantity":
            if not _decimal_string(planned) or not _decimal_string(actual):
                errors.append("quantity comparison values must be Decimal strings")
            else:
                expected_result = (
                    "matches" if Decimal(planned) == Decimal(actual) else "deviates"
                )
                if data.get("result") != expected_result:
                    errors.append("quantity comparison result is not derived")
        elif field in _PLAN_FIELDS:
            expected_result = (
                "matches" if planned.upper() == actual.upper() else "deviates"
            )
            if data.get("result") != expected_result:
                errors.append("comparison result is not derived")
    return errors


def _validate_fact_data(
    fact: Mapping[str, Any], findings: list[dict[str, str]]
) -> None:
    kind = str(fact.get("kind") or "")
    data = fact.get("data")
    if kind not in _DATA_KEYS or not isinstance(data, Mapping):
        findings.append(
            _finding("blocker", "FACT_DATA_INVALID", f"{kind} has no valid data object")
        )
        return
    required, optional = _DATA_KEYS[kind]
    keys = set(data)
    if not required.issubset(keys) or keys - required - optional:
        findings.append(
            _finding(
                "blocker",
                "FACT_DATA_SHAPE_MISMATCH",
                f"{kind} data keys do not match the closed contract",
            )
        )
    if _contains_forbidden_key(data):
        findings.append(
            _finding(
                "blocker",
                "FACT_POLICY_FIELD_FORBIDDEN",
                f"{kind} contains an interpretation/advice field",
            )
        )
    for error in _fact_data_type_errors(kind, data, fact):
        findings.append(
            _finding(
                "blocker",
                "FACT_DATA_TYPE_MISMATCH",
                f"{kind}: {error}",
            )
        )
    try:
        expected = _expected_statement(kind, data)
    except (EpisodeReviewError, KeyError, TypeError) as exc:
        findings.append(_finding("blocker", "FACT_TEMPLATE_INVALID", str(exc)))
    else:
        if fact.get("statement") != expected:
            findings.append(
                _finding(
                    "blocker",
                    "FACT_STATEMENT_NOT_DETERMINISTIC",
                    f"{kind} statement is not the fixed neutral template",
                )
            )
    if kind == "plan_execution_comparison" and data.get("result") not in {
        "matches",
        "deviates",
    }:
        findings.append(
            _finding(
                "blocker",
                "PLAN_COMPARISON_INVALID",
                "plan comparison result must be matches or deviates",
            )
        )
    if kind == "outcome_record" and not isinstance(data.get("final"), bool):
        findings.append(
            _finding(
                "blocker", "OUTCOME_FINALITY_INVALID", "outcome final must be boolean"
            )
        )


def _validate_temporal_fact(
    fact: Mapping[str, Any],
    *,
    opened_at: str,
    closed_at: str | None,
    opening_event_id: str,
    findings: list[dict[str, str]],
) -> None:
    kind = str(fact.get("kind") or "")
    role = str(fact.get("temporal_role") or "")
    if role not in _TEMPORAL_ROLES:
        findings.append(_finding("blocker", "TEMPORAL_ROLE_INVALID", "unsupported role"))
        return
    effective_raw = fact.get("effective_at")
    known_raw = fact.get("knowledge_at")
    if kind in _NOT_APPLICABLE_KINDS:
        if role != "not_applicable" or effective_raw is not None or known_raw is not None:
            findings.append(
                _finding(
                    "blocker",
                    "TEMPORAL_ROLE_INVALID",
                    f"{kind} must use not_applicable without source times",
                )
            )
        return
    if role == "not_applicable" or effective_raw is None or known_raw is None:
        findings.append(
            _finding(
                "blocker",
                "TEMPORAL_ROLE_INVALID",
                f"{kind} requires effective/knowledge time and an active role",
            )
        )
        return
    try:
        effective = _parse_timestamp(effective_raw, "fact.effective_at")
        known = _parse_timestamp(known_raw, "fact.knowledge_at")
        opened = _parse_timestamp(opened_at, "episode.opened_at")
        closed = (
            _parse_timestamp(closed_at, "episode.closed_at")
            if closed_at is not None
            else None
        )
    except EpisodeReviewError as exc:
        findings.append(_finding("blocker", "TEMPORAL_ROLE_INVALID", str(exc)))
        return
    if effective_raw != _iso(effective) or known_raw != _iso(known) or known < effective:
        findings.append(
            _finding(
                "blocker",
                "TEMPORAL_ROLE_INVALID",
                f"{kind} has non-canonical or inverted source time",
            )
        )
    data = fact.get("data") if isinstance(fact.get("data"), Mapping) else {}
    ex_ante_eligible = kind not in _NON_EX_ANTE_KINDS
    if kind in {"portfolio_anchor", "portfolio_metric"}:
        ex_ante_eligible = (
            data.get("anchor_kind") == "episode_open" and data.get("side") == "pre"
        )
    if kind == "recorded_decision":
        event_ids = data.get("event_ids")
        ex_ante_eligible = (
            isinstance(event_ids, list) and opening_event_id in event_ids
        )
        if ex_ante_eligible and known == opened:
            warning_codes = fact.get("warning_codes")
            if (
                fact.get("availability") != "ambiguous"
                or not isinstance(warning_codes, list)
                or "SAME_SECOND_DECISION_AVAILABILITY_AMBIGUOUS"
                not in warning_codes
            ):
                findings.append(
                    _finding(
                        "blocker",
                        "SAME_SECOND_DECISION_AMBIGUITY_MISSING",
                        "an opening decision known in the same second must remain ambiguous",
                    )
                )
    if kind == "decision_execution_link":
        try:
            decision_known = _parse_timestamp(
                data.get("decision_known_at"), "decision_execution_link.decision_known_at"
            )
            event_effective = _parse_timestamp(
                data.get("event_effective_at"),
                "decision_execution_link.event_effective_at",
            )
        except EpisodeReviewError:
            pass
        else:
            if decision_known == event_effective:
                warning_codes = fact.get("warning_codes")
                if (
                    fact.get("availability") != "ambiguous"
                    or data.get("link_status") != "ambiguous"
                    or not isinstance(warning_codes, list)
                    or "SAME_SECOND_DECISION_AVAILABILITY_AMBIGUOUS"
                    not in warning_codes
                ):
                    findings.append(
                        _finding(
                            "blocker",
                            "SAME_SECOND_DECISION_AMBIGUITY_MISSING",
                            "a decision link known in the execution second must remain ambiguous",
                        )
                    )
    if kind == "outcome_record" and data.get("final") is True:
        if (
            data.get("source_claim_type") != "fact"
            or closed is None
            or effective < closed
            or known < closed
        ):
            findings.append(
                _finding(
                    "blocker",
                    "OUTCOME_FINALITY_INVALID",
                    "final outcome requires a fact-typed source no earlier than episode close",
                )
            )
    if role == "known_at_decision":
        if kind in _NON_EX_ANTE_KINDS or not ex_ante_eligible or known >= opened:
            findings.append(
                _finding(
                    "blocker",
                    "TEMPORAL_ROLE_INVALID",
                    f"{kind} cannot be known_at_decision for these times/anchor",
                )
            )
    elif role == "known_after_episode":
        if closed is None or known <= closed:
            findings.append(
                _finding(
                    "blocker",
                    "TEMPORAL_ROLE_INVALID",
                    "known_after_episode requires knowledge strictly after close",
                )
            )
    elif role == "learned_during_episode":
        if known < opened and ex_ante_eligible:
            findings.append(
                _finding(
                    "blocker",
                    "TEMPORAL_ROLE_INVALID",
                    f"{kind} was already known before opening",
                )
            )
        if closed is not None and known > closed:
            findings.append(
                _finding(
                    "blocker",
                    "TEMPORAL_ROLE_INVALID",
                    f"{kind} was learned after episode close",
                )
                )


def _validate_lifecycle_event_closure(
    lifecycle_data: Mapping[str, Any],
    event_facts: Sequence[Mapping[str, Any]],
    findings: list[dict[str, str]],
) -> None:
    reasons: set[str] = set()
    if not event_facts:
        reasons.add("the lifecycle has no execution events")
    rows: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for fact in event_facts:
        data = fact.get("data")
        if isinstance(data, Mapping):
            rows.append((fact, data))
    if len(rows) != len(event_facts):
        reasons.add("an execution event has no data object")
    try:
        rows.sort(
            key=lambda row: (
                _parse_timestamp(row[1]["ordering_key"][0], "ordering_key[0]"),
                row[1]["ordering_key"][1],
                row[1]["ordering_key"][2],
                row[1]["ordering_key"][3],
            )
        )
    except (EpisodeReviewError, KeyError, IndexError, TypeError):
        reasons.add("execution event ordering cannot be reconstructed")
        rows = []

    if rows:
        event_ids = [str(data.get("event_id") or "") for _, data in rows]
        if len(set(event_ids)) != len(event_ids):
            reasons.add("execution event IDs are not unique")
        if lifecycle_data.get("material_transition_count") != len(rows):
            reasons.add("material_transition_count does not equal the event count")

        first_fact, first_data = rows[0]
        last_fact, last_data = rows[-1]
        opening_event_id = str(lifecycle_data.get("opening_event_id") or "")
        closing_event_id = lifecycle_data.get("closing_event_id")
        opened_at = lifecycle_data.get("opened_at")
        closed_at = lifecycle_data.get("closed_at")
        if opening_event_id != first_data.get("event_id"):
            reasons.add("opening_event_id is not the first canonical event")
        if opened_at != first_fact.get("effective_at"):
            reasons.add("opened_at does not equal the opening event time")
        if (closed_at is None) != (closing_event_id is None):
            reasons.add("closed_at and closing_event_id must be present together")
        if closing_event_id is not None:
            if closing_event_id != last_data.get("event_id"):
                reasons.add("closing_event_id is not the last canonical event")
            if closed_at != last_fact.get("effective_at"):
                reasons.add("closed_at does not equal the closing event time")

        try:
            starting = Decimal(str(lifecycle_data["starting_quantity"]))
            ending = Decimal(str(lifecycle_data["ending_quantity"]))
            maximum = Decimal(str(lifecycle_data["maximum_absolute_quantity"]))
            quantities: list[Decimal] = []
            previous_after: Decimal | None = None
            for _, data in rows:
                signed = Decimal(str(data["signed_quantity"]))
                before = Decimal(str(data["quantity_before"]))
                after = Decimal(str(data["quantity_after"]))
                quantities.extend((before, after))
                if after - before != signed:
                    reasons.add("an execution quantity transition is not arithmetically closed")
                if previous_after is not None and before != previous_after:
                    reasons.add("consecutive execution quantities do not form a chain")
                previous_after = after
            first_before = Decimal(str(first_data["quantity_before"]))
            first_after = Decimal(str(first_data["quantity_after"]))
            last_after = Decimal(str(last_data["quantity_after"]))
            if starting != first_before or starting != 0:
                reasons.add("starting_quantity does not equal the flat opening state")
            if first_after == 0:
                reasons.add("the opening event must leave the flat state")
            if ending != last_after:
                reasons.add("ending_quantity does not equal the last event state")
            if maximum != max(abs(value) for value in quantities):
                reasons.add("maximum_absolute_quantity is not derived from the events")
            expected_direction = "long" if first_after > 0 else "short"
            if lifecycle_data.get("direction") != expected_direction:
                reasons.add("direction is not derived from the opening event")
            if closing_event_id is None and ending == 0:
                reasons.add("a flat ending state requires a closing event")
            if closing_event_id is not None and ending != 0:
                reasons.add("a closing event requires a flat ending state")
            status = lifecycle_data.get("status")
            if status == "closed" and closing_event_id is None:
                reasons.add("closed status requires a closing event")
            if status == "open" and closing_event_id is not None:
                reasons.add("open status cannot have a closing event")
        except (InvalidOperation, KeyError, TypeError, ValueError):
            reasons.add("lifecycle quantities cannot be reconstructed")

    if reasons:
        findings.append(
            _finding(
                "blocker",
                "LIFECYCLE_EVENT_CLOSURE_MISMATCH",
                "; ".join(sorted(reasons)),
            )
        )


def _validate_episode_review_impl(artifact: Mapping[str, Any]) -> dict[str, Any]:
    findings = _schema_findings(artifact)
    try:
        canonical_json_bytes(artifact)
    except ArtifactIOError as exc:
        findings.append(_finding("blocker", "NON_CANONICAL_JSON", str(exc)))
    if artifact.get("schema_version") != SCHEMA_VERSION:
        findings.append(
            _finding("blocker", "UNSUPPORTED_REVIEW_SCHEMA", "unsupported schema")
        )
    content_id = str(artifact.get("content_id") or "")
    if not _CONTENT_ID_RE.fullmatch(content_id) or content_id != _content_id(artifact):
        findings.append(
            _finding(
                "blocker", "CONTENT_ID_MISMATCH", "review content_id is not canonical"
            )
        )
    input_ref = artifact.get("input_bundle_ref")
    if not isinstance(input_ref, Mapping):
        input_ref = {}
    episode_id = str(input_ref.get("episode_id") or "")
    if (
        input_ref.get("schema_version") != INPUT_BUNDLE_SCHEMA_VERSION
        or not _CONTENT_ID_RE.fullmatch(str(input_ref.get("content_id") or ""))
    ):
        findings.append(
            _finding("blocker", "INPUT_BUNDLE_REF_INVALID", "invalid P2F-1 reference")
        )
    expected_review_id = _review_id(episode_id) if episode_id else ""
    if (
        not _REVIEW_ID_RE.fullmatch(str(artifact.get("review_id") or ""))
        or artifact.get("review_id") != expected_review_id
    ):
        findings.append(
            _finding("blocker", "REVIEW_ID_MISMATCH", "review_id is not deterministic")
        )
    revision = artifact.get("revision") if isinstance(artifact.get("revision"), Mapping) else {}
    governance = (
        artifact.get("governance")
        if isinstance(artifact.get("governance"), Mapping)
        else {}
    )
    generation_mode = str(governance.get("generation_mode") or "")
    interpretations = artifact.get("interpretation_sections")
    if not isinstance(interpretations, Mapping):
        interpretations = {}
    if generation_mode == "facts_only":
        if dict(revision) != {
            "revision_no": 1,
            "status": "draft",
            "supersedes_content_id": None,
            "correction_reason": None,
        }:
            findings.append(
                _finding(
                    "blocker",
                    "FACTS_ONLY_REVISION_INVALID",
                    "facts-only build must be revision 1 draft",
                )
            )
        if governance.get("model_generation") is not None or any(
            interpretations.get(name) != [] for name in INTERPRETATION_SECTION_NAMES
        ):
            findings.append(
                _finding(
                    "blocker",
                    "FACTS_INTERPRETATION_LEAK",
                    "facts-only review cannot contain model output or interpretations",
                )
            )
        if governance.get("human_reviews") != []:
            findings.append(
                _finding(
                    "blocker",
                    "FACTS_ONLY_HUMAN_REVIEW_INVALID",
                    "initial facts-only artifact cannot contain human review events",
                )
            )
    if not all(
        governance.get(key) is True
        for key in (
            "facts_interpretation_separated",
            "no_advice",
            "no_mechanical_score",
        )
    ):
        findings.append(
            _finding("blocker", "GOVERNANCE_INVALID", "review safety flags must be true")
        )
    sections = artifact.get("fact_sections")
    if not isinstance(sections, Mapping):
        sections = {}
    lifecycle_facts: list[Mapping[str, Any]] = []
    execution_event_facts: list[Mapping[str, Any]] = []
    all_fact_ids: set[str] = set()
    for section_name in FACT_SECTION_NAMES:
        section = sections.get(section_name)
        if not isinstance(section, Mapping):
            findings.append(
                _finding(
                    "blocker", "FACT_SECTION_INVALID", f"missing section {section_name}"
                )
            )
            continue
        facts = section.get("facts")
        if not isinstance(facts, list):
            facts = []
        mapping_facts = [item for item in facts if isinstance(item, Mapping)]
        if len(mapping_facts) != len(facts):
            findings.append(
                _finding(
                    "blocker", "FACT_INVALID", f"{section_name} contains a non-object fact"
                )
            )
        if mapping_facts != sorted(mapping_facts, key=_fact_sort_key):
            findings.append(
                _finding(
                    "blocker",
                    "FACT_ORDER_MISMATCH",
                    f"{section_name} facts are not canonically ordered",
                )
            )
        for fact in mapping_facts:
            kind = str(fact.get("kind") or "")
            fact_id = str(fact.get("fact_id") or "")
            if kind not in _KIND_SECTION or _KIND_SECTION.get(kind) != section_name:
                findings.append(
                    _finding(
                        "blocker",
                        "FACT_SECTION_KIND_MISMATCH",
                        f"{kind} is not allowed in {section_name}",
                    )
                )
            if fact.get("claim_type") != "fact":
                findings.append(
                    _finding(
                        "blocker",
                        "FACT_CLAIM_TYPE_INVALID",
                        "P2F-2 facts must be typed as fact",
                    )
                )
            refs = fact.get("source_refs")
            if not isinstance(refs, list) or not refs or not all(
                isinstance(item, Mapping) for item in refs
            ):
                findings.append(
                    _finding(
                        "blocker", "FACT_SOURCE_REF_MISSING", f"{fact_id} lacks source refs"
                    )
                )
                refs = []
            canonical_refs = sorted(
                [dict(item) for item in refs if isinstance(item, Mapping)],
                key=lambda item: (
                    str(item.get("source_kind") or ""),
                    str(item.get("source_id") or ""),
                    str(item.get("content_id") or ""),
                    str(item.get("frozen_pointer") or ""),
                ),
            )
            if refs != canonical_refs or len(
                {canonical_json_bytes(item) for item in canonical_refs}
            ) != len(canonical_refs):
                findings.append(
                    _finding(
                        "blocker", "FACT_SOURCE_REF_INVALID", f"{fact_id} refs are not canonical"
                    )
            )
            for ref in canonical_refs:
                if (
                    not str(ref.get("source_id") or "")
                    or not str(ref.get("source_kind") or "")
                    or not _CONTENT_ID_RE.fullmatch(str(ref.get("content_id") or ""))
                    or not str(ref.get("frozen_pointer") or "").startswith(
                        "/frozen_sources/"
                    )
                ):
                    findings.append(
                        _finding(
                            "blocker",
                            "FACT_SOURCE_REF_INVALID",
                            f"{fact_id} has an incomplete frozen source ref",
                        )
                    )
            raw_warning_codes = fact.get("warning_codes")
            if not isinstance(raw_warning_codes, list) or raw_warning_codes != sorted(
                set(str(item) for item in raw_warning_codes)
            ):
                findings.append(
                    _finding(
                        "blocker", "FACT_WARNING_ORDER_INVALID", f"{fact_id} warnings invalid"
                    )
                )
            else:
                pass
            identity = deepcopy(dict(fact))
            identity.pop("fact_id", None)
            expected_fact_id = "fact:" + hashlib.sha256(
                canonical_json_bytes(identity)
            ).hexdigest()[:32]
            if not _FACT_ID_RE.fullmatch(fact_id) or fact_id != expected_fact_id:
                findings.append(
                    _finding(
                        "blocker", "FACT_ID_MISMATCH", f"{fact_id or kind} ID is not canonical"
                    )
                )
            if fact_id in all_fact_ids:
                findings.append(
                    _finding("blocker", "DUPLICATE_FACT_ID", f"duplicate fact {fact_id}")
                )
            all_fact_ids.add(fact_id)
            _validate_fact_data(fact, findings)
            if kind == "episode_lifecycle":
                lifecycle_facts.append(fact)
            elif kind == "execution_event":
                execution_event_facts.append(fact)
        raw_source_ids = section.get("source_ids")
        if not isinstance(raw_source_ids, list) or raw_source_ids != sorted(
            set(str(item) for item in raw_source_ids)
        ):
            findings.append(
                _finding(
                    "blocker",
                    "SECTION_SOURCE_ORDER_INVALID",
                    f"{section_name} source_ids are not sorted and unique",
                )
            )
        raw_section_warnings = section.get("warning_codes")
        if not isinstance(raw_section_warnings, list) or raw_section_warnings != sorted(
            set(str(item) for item in raw_section_warnings)
        ):
            findings.append(
                _finding(
                    "blocker",
                    "SECTION_WARNING_ORDER_INVALID",
                    f"{section_name} warning codes are not sorted and unique",
                )
            )
        raw_gaps = section.get("gap_codes")
        if not isinstance(raw_gaps, list) or raw_gaps != sorted(
            set(str(item) for item in raw_gaps)
        ):
            findings.append(
                _finding(
                    "blocker",
                    "SECTION_GAP_ORDER_INVALID",
                    f"{section_name} gaps are not sorted and unique",
                )
            )
    if len(lifecycle_facts) != 1:
        findings.append(
            _finding(
                "blocker", "LIFECYCLE_FACT_INVALID", "exactly one lifecycle fact is required"
            )
        )
    else:
        lifecycle_data = lifecycle_facts[0].get("data")
        if isinstance(lifecycle_data, Mapping):
            opened_at = str(lifecycle_data.get("opened_at") or "")
            closed_at = (
                str(lifecycle_data.get("closed_at"))
                if lifecycle_data.get("closed_at") is not None
                else None
            )
            if lifecycle_data.get("episode_id") != episode_id:
                findings.append(
                    _finding(
                        "blocker",
                        "EPISODE_ID_MISMATCH",
                        "lifecycle episode_id does not match input_bundle_ref",
                    )
                )
            _validate_lifecycle_event_closure(
                lifecycle_data,
                execution_event_facts,
                findings,
            )
            for section_name in FACT_SECTION_NAMES:
                section = sections.get(section_name)
                if not isinstance(section, Mapping):
                    continue
                for fact in section.get("facts", []):
                    if isinstance(fact, Mapping):
                        _validate_temporal_fact(
                            fact,
                            opened_at=opened_at,
                            closed_at=closed_at,
                            opening_event_id=str(
                                lifecycle_data.get("opening_event_id") or ""
                            ),
                            findings=findings,
                        )
    warnings = artifact.get("warnings")
    if isinstance(warnings, list):
        canonical_warnings = sorted(
            [dict(item) for item in warnings if isinstance(item, Mapping)],
            key=lambda item: (
                _SEVERITY_ORDER.get(str(item.get("severity") or ""), 99),
                str(item.get("code") or ""),
                item.get("target_ids", []),
                str(item.get("message") or ""),
            ),
        )
        if warnings != canonical_warnings or len(
            {canonical_json_bytes(item) for item in canonical_warnings}
        ) != len(canonical_warnings):
            findings.append(
                _finding(
                    "blocker", "WARNING_ORDER_INVALID", "warnings are not canonical"
                )
            )
    if generation_mode in {"model_assisted", "human_authored"}:
        from .episode_interpretation import interpretation_layer_findings

        findings.extend(interpretation_layer_findings(artifact))
    elif generation_mode != "facts_only":
        findings.append(
            _finding(
                "blocker",
                "GENERATION_MODE_INVALID",
                "unsupported episode-review generation mode",
            )
        )
    return _validation(findings)


def validate_episode_review(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Validate arbitrary JSON-like input and always return a validation artifact."""

    if not isinstance(artifact, Mapping):
        return _validation(
            [
                _finding(
                    "blocker", "MALFORMED_EPISODE_REVIEW", "review must be an object"
                )
            ]
        )
    try:
        return _validate_episode_review_impl(artifact)
    except Exception as exc:
        return _validation(
            [
                _finding(
                    "blocker", "MALFORMED_EPISODE_REVIEW", str(exc)
                )
            ]
        )


def replay_validate_episode_review(
    artifact: Mapping[str, Any], *, input_bundle: Mapping[str, Any]
) -> dict[str, Any]:
    """Rebuild P2F-2 facts and verify the immutable layer of later reviews."""

    offline = validate_episode_review(artifact)
    findings = list(offline.get("findings", []))
    if offline.get("validation_status") == "blocked":
        result = _validation(findings, mode="source_replay")
        result["source_verification"] = {"status": "blocked"}
        return result
    try:
        expected = build_facts_only_episode_review(input_bundle)
    except (EpisodeReviewError, ReviewInputBundleError) as exc:
        findings.append(
            _finding("blocker", "SOURCE_REPLAY_FAILED", str(exc))
        )
        result = _validation(findings, mode="source_replay")
        result["source_verification"] = {"status": "blocked"}
        return result
    governance = (
        artifact.get("governance")
        if isinstance(artifact.get("governance"), Mapping)
        else {}
    )
    generation_mode = str(governance.get("generation_mode") or "")
    replay_material: Mapping[str, Any] = artifact
    if generation_mode != "facts_only":
        from .episode_interpretation import facts_only_projection

        replay_material = facts_only_projection(artifact)
    if canonical_json_bytes(replay_material) != canonical_json_bytes(expected):
        findings.append(
            _finding(
                "blocker",
                "SOURCE_REPLAY_MISMATCH",
                "review facts layer does not equal deterministic rebuild from P2F-1",
            )
        )
    result = _validation(findings, mode="source_replay")
    result["source_verification"] = {
        "status": (
            "verified" if result["validation_status"] != "blocked" else "blocked"
        ),
        "input_content_id": str(input_bundle.get("content_id") or ""),
        "verified_content_id": str(artifact.get("content_id") or ""),
        "rebuilt_content_id": expected["content_id"],
        "facts_content_id": str(replay_material.get("content_id") or ""),
        "generation_mode": generation_mode,
        "interpretation_replay": (
            "not_replayed" if generation_mode != "facts_only" else "not_applicable"
        ),
        "fact_engine_version": FACT_ENGINE_VERSION,
    }
    return result


def save_episode_review(path: str | Path, artifact: Mapping[str, Any]) -> Path:
    validation = validate_episode_review(artifact)
    if validation["validation_status"] == "blocked":
        raise EpisodeReviewError("refusing to save an invalid episode review")
    try:
        return atomic_write_bytes(path, pretty_json_bytes(artifact))
    except ArtifactIOError as exc:
        raise EpisodeReviewError(str(exc)) from exc


def load_episode_review(path: str | Path) -> dict[str, Any]:
    try:
        return load_json_object(path)
    except ArtifactIOError as exc:
        raise EpisodeReviewError(str(exc)) from exc


def query_episode_review(
    artifact: Mapping[str, Any],
    *,
    section: str | None = None,
    fact_id: str | None = None,
    content_id: str | None = None,
) -> list[Any]:
    validation = validate_episode_review(artifact)
    if validation["validation_status"] == "blocked":
        raise EpisodeReviewError("refusing to query an invalid episode review")
    if content_id is not None and artifact.get("content_id") != content_id:
        return []
    if section is not None and fact_id is not None:
        raise EpisodeReviewError("section and fact_id filters are mutually exclusive")
    sections = artifact.get("fact_sections")
    if not isinstance(sections, Mapping):
        raise EpisodeReviewError("review fact_sections must be an object")
    if section is not None:
        if section not in FACT_SECTION_NAMES:
            raise EpisodeReviewError(f"unsupported fact section: {section}")
        return [deepcopy(sections[section])]
    if fact_id is not None:
        return [
            deepcopy(dict(fact))
            for section_name in FACT_SECTION_NAMES
            for fact in (sections.get(section_name) or {}).get("facts", [])
            if isinstance(fact, Mapping) and fact.get("fact_id") == fact_id
        ]
    return [deepcopy(dict(artifact))]


def render_episode_review_markdown(artifact: Mapping[str, Any]) -> str:
    """Render the facts layer only, preserving fact and frozen-source IDs."""

    validation = validate_episode_review(artifact)
    if validation["validation_status"] == "blocked":
        raise EpisodeReviewError("refusing to render an invalid episode review")
    titles = {
        "timeline": "事件时间线",
        "security_context": "标的与记录来源",
        "portfolio_context": "操作前后组合事实",
        "market_context": "市场上下文",
        "outcome_context": "结果上下文",
        "execution_consistency": "计划与执行的可证明比较",
    }
    lines = [
        "# 单笔交易事实复盘",
        "",
        f"- review_id: `{artifact['review_id']}`",
        f"- content_id: `{artifact['content_id']}`",
        f"- input_bundle: `{artifact['input_bundle_ref']['content_id']}`",
        "- generation_mode: `facts_only`",
        "",
        "> 本文只呈现冻结来源可证明的事实与缺口，不包含交易建议、评分或心理归因。",
    ]
    sections = artifact["fact_sections"]
    for name in FACT_SECTION_NAMES:
        section = sections[name]
        lines.extend(
            [
                "",
                f"## {titles[name]}",
                "",
                f"- status: `{section['status']}`",
                f"- reason: {section['reason']}",
                f"- gaps: `{', '.join(section['gap_codes']) or 'none'}`",
            ]
        )
        if not section["facts"]:
            lines.extend(["", "无可用事实记录。"])
            continue
        for fact in section["facts"]:
            lines.extend(
                [
                    "",
                    f"### `{fact['fact_id']}`",
                    "",
                    fact["statement"],
                    "",
                    f"- kind: `{fact['kind']}`",
                    f"- availability: `{fact['availability']}`",
                    f"- temporal_role: `{fact['temporal_role']}`",
                    f"- data: `{canonical_json_bytes(fact['data']).decode('utf-8')}`",
                    "- sources:",
                ]
            )
            for ref in fact["source_refs"]:
                lines.append(
                    f"  - `{ref['source_id']}` | `{ref['content_id']}` | "
                    f"`{ref['frozen_pointer']}` | {ref['locator']}"
                )
    return "\n".join(lines) + "\n"


render_facts_only_episode_review_markdown = render_episode_review_markdown


__all__ = [
    "FACT_ENGINE_VERSION",
    "FACT_SECTION_NAMES",
    "SCHEMA_VERSION",
    "VALIDATION_SCHEMA_VERSION",
    "EpisodeReviewError",
    "build_facts_only_episode_review",
    "load_episode_review",
    "query_episode_review",
    "render_episode_review_markdown",
    "render_facts_only_episode_review_markdown",
    "replay_validate_episode_review",
    "save_episode_review",
    "validate_episode_review",
]
