"""Deterministic, artifact-only behavior hypothesis ledger."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
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
from .behavior_hypothesis_audit import _string_list, _wrapped
from .behavior_hypothesis_review import (
    _canonical_timestamp,
    replay_validate_behavior_hypothesis_revision,
    validate_behavior_hypothesis_revision_chain,
)
from .behavior_observations import validate_behavior_observation_set
from .episode_review import _markdown_code, _markdown_escape


SCHEMA_VERSION = "p2g.behavior_hypothesis_ledger.v1"
VALIDATION_SCHEMA_VERSION = "p2g.behavior_hypothesis_ledger.validation.v1"
QUERY_SCHEMA_VERSION = "p2g.behavior_hypothesis_ledger.query.v1"
BUILDER_VERSION = "p2g.behavior_hypothesis_ledger.builder.v1"
CANONICAL_SORT_VERSION = "p2g.behavior_hypothesis_ledger_sort.v1"
FINGERPRINT_VERSION = "p2g.behavior_hypothesis_fingerprint.v1"

_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = (
    _ROOT
    / "docs"
    / "contracts"
    / "P2G_BEHAVIOR_HYPOTHESIS_LEDGER.schema.json"
)

_PAYLOAD_FIELDS = (
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
)
_HISTORY_FIELDS = (
    "review_event_id",
    "request_id",
    "actor",
    "reviewed_at",
    "action",
    "reason",
    "target_hypothesis_id",
    "result_hypothesis_id",
)
_STATUSES = ("proposed", "accepted", "rejected", "superseded")


class BehaviorHypothesisLedgerError(ValueError):
    """Raised when ledger source, validation, query, or create-only I/O fails."""


def _value_content_id(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _content_id(value: Mapping[str, Any]) -> str:
    material = deepcopy(dict(value))
    material.pop("content_id", None)
    return _value_content_id(material)


def _stable_id(prefix: str, value: object) -> str:
    return f"{prefix}:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()[:32]


def _finding(code: str, message: str) -> dict[str, str]:
    return {"severity": "blocker", "code": code, "message": message}


def _validation(
    findings: Iterable[Mapping[str, str]], *, mode: str = "offline"
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
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "validation_mode": mode,
        "validation_status": "blocked" if blockers else "accepted",
        "blocker_count": len(blockers),
        "finding_count": len(rows),
        "findings": rows,
    }


@lru_cache(maxsize=1)
def _schema_validator() -> Draft202012Validator:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _json_path(parts: Iterable[object]) -> str:
    value = "$"
    for part in parts:
        value += f"[{part}]" if isinstance(part, int) else f".{part}"
    return value


def _payload(hypothesis: Mapping[str, Any]) -> dict[str, Any]:
    return {field: deepcopy(hypothesis.get(field)) for field in _PAYLOAD_FIELDS}


def _fingerprint_id(payload: Mapping[str, Any]) -> str:
    return _stable_id(
        "hypothesis-fingerprint",
        {
            "fingerprint_version": FINGERPRINT_VERSION,
            "hypothesis": deepcopy(dict(payload)),
        },
    )


def _history_item(event: Mapping[str, Any]) -> dict[str, Any]:
    return {field: deepcopy(event.get(field)) for field in _HISTORY_FIELDS}


def _occurrence(
    hypothesis: Mapping[str, Any], head: Mapping[str, Any]
) -> dict[str, Any]:
    hypothesis_id = str(hypothesis.get("hypothesis_id") or "")
    history = [
        _history_item(event)
        for event in head.get("review_events", [])
        if isinstance(event, Mapping)
        and hypothesis_id
        in {
            str(event.get("target_hypothesis_id") or ""),
            str(event.get("result_hypothesis_id") or ""),
        }
    ]
    history.sort(
        key=lambda item: (
            str(item.get("reviewed_at") or ""),
            str(item.get("review_event_id") or ""),
        )
    )
    source = head["source_hypothesis_set"]
    observation = head["source_observation_set"]
    occurrence: dict[str, Any] = {
        "occurrence_id": "",
        "revision_chain_id": head["revision_chain_id"],
        "head_content_id": head["content_id"],
        "hypothesis_id": hypothesis_id,
        "lineage_root_hypothesis_id": hypothesis["lineage_root_hypothesis_id"],
        "supersedes_hypothesis_id": hypothesis["supersedes_hypothesis_id"],
        "status": hypothesis["status"],
        "source_hypothesis_set_content_id": source["content_id"],
        "source_observation_content_id": observation["content_id"],
        "review_history": history,
    }
    identity = deepcopy(occurrence)
    identity.pop("occurrence_id", None)
    occurrence["occurrence_id"] = _stable_id("hypothesis-occurrence", identity)
    return occurrence


def _source_revision_record(
    chain: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    ordered = sorted(chain, key=lambda item: item["revision"]["revision_no"])
    head = ordered[-1]
    observation = head["source_observation_set"]
    return {
        "revision_chain_id": head["revision_chain_id"],
        "head_content_id": head["content_id"],
        "head_revision_no": head["revision"]["revision_no"],
        "root_hypothesis_set_content_id": head["revision"][
            "root_hypothesis_set_content_id"
        ],
        "source_observation_content_id": observation["content_id"],
        "source_observation_set_id": observation["observation_set_id"],
        "revision_lineage": [
            {
                "revision_no": item["revision"]["revision_no"],
                "content_id": item["content_id"],
                "parent_content_id": item["revision"]["parent_content_id"],
                "request_id": item["revision"]["request_id"],
            }
            for item in ordered
        ],
    }


def _prepare_sources(
    revisions: Sequence[Mapping[str, Any]],
    observation_artifacts: Sequence[Mapping[str, Any]],
) -> tuple[list[list[Mapping[str, Any]]], dict[str, Mapping[str, Any]]]:
    if not revisions:
        raise BehaviorHypothesisLedgerError("at least one P2G-4 revision is required")
    if not observation_artifacts:
        raise BehaviorHypothesisLedgerError("at least one P2G-2 observation artifact is required")
    if not all(isinstance(item, Mapping) for item in revisions):
        raise BehaviorHypothesisLedgerError("all revisions must be objects")
    if not all(isinstance(item, Mapping) for item in observation_artifacts):
        raise BehaviorHypothesisLedgerError("all observation artifacts must be objects")
    observations: dict[str, Mapping[str, Any]] = {}
    for artifact in observation_artifacts:
        content_id = str(artifact.get("content_id") or "")
        if content_id in observations:
            raise BehaviorHypothesisLedgerError("duplicate observation artifact")
        validation = validate_behavior_observation_set(artifact)
        if (
            validation["validation_status"] == "blocked"
            or (artifact.get("release_readiness") or {}).get("status") != "ready"
            or (artifact.get("source_verification") or {}).get("status") != "verified"
        ):
            raise BehaviorHypothesisLedgerError(
                "observation artifact must be valid, ready and verified"
            )
        observations[content_id] = artifact
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for revision in revisions:
        groups.setdefault(str(revision.get("revision_chain_id") or ""), []).append(
            revision
        )
    chains: list[list[Mapping[str, Any]]] = []
    referenced_observations: set[str] = set()
    for chain_id in sorted(groups):
        group = groups[chain_id]
        validation = validate_behavior_hypothesis_revision_chain(group)
        if validation["validation_status"] == "blocked":
            codes = sorted({item["code"] for item in validation["findings"]})
            raise BehaviorHypothesisLedgerError(
                f"invalid revision chain {chain_id}: {', '.join(codes)}"
            )
        ordered = sorted(group, key=lambda item: item["revision"]["revision_no"])
        observation_id = str(ordered[-1]["source_observation_set"]["content_id"])
        observation = observations.get(observation_id)
        if observation is None:
            raise BehaviorHypothesisLedgerError(
                "missing observation artifact for revision chain"
            )
        referenced_observations.add(observation_id)
        for revision in ordered:
            replay = replay_validate_behavior_hypothesis_revision(
                revision, observation_artifact=observation
            )
            if replay["validation_status"] == "blocked":
                raise BehaviorHypothesisLedgerError(
                    "revision failed exact P2G-2 source replay"
                )
        chains.append(ordered)
    extra = sorted(set(observations) - referenced_observations)
    if extra:
        raise BehaviorHypothesisLedgerError("unreferenced observation artifact supplied")
    return chains, observations


def _counts(
    entries: Sequence[Mapping[str, Any]],
    source_revisions: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    occurrences = [
        occurrence
        for entry in entries
        for occurrence in entry.get("occurrences", [])
        if isinstance(occurrence, Mapping)
    ]
    active = {
        str(entry.get("fingerprint_id") or "")
        for entry in entries
        if any(
            occurrence.get("status") == "accepted"
            for occurrence in entry.get("occurrences", [])
            if isinstance(occurrence, Mapping)
        )
    }
    result = {
        "source_chain_count": len(source_revisions),
        "source_revision_count": sum(
            len(item.get("revision_lineage", [])) for item in source_revisions
        ),
        "fingerprint_count": len(entries),
        "occurrence_count": len(occurrences),
        "active_fingerprint_count": len(active),
    }
    for status in _STATUSES:
        result[f"{status}_occurrence_count"] = sum(
            1 for occurrence in occurrences if occurrence.get("status") == status
        )
    return result


def build_behavior_hypothesis_ledger(
    revisions: Sequence[Mapping[str, Any]],
    observation_artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one deterministic ledger from complete, source-replayed P2G-4 chains."""

    revision_bytes = [canonical_json_bytes(item) for item in revisions]
    observation_bytes = [canonical_json_bytes(item) for item in observation_artifacts]
    chains, observations = _prepare_sources(revisions, observation_artifacts)
    source_revisions = [_source_revision_record(chain) for chain in chains]
    source_revisions.sort(key=lambda item: item["revision_chain_id"])
    entries_by_fingerprint: dict[str, dict[str, Any]] = {}
    for chain in chains:
        head = chain[-1]
        for hypothesis in head["hypotheses"]:
            payload = _payload(hypothesis)
            fingerprint_id = _fingerprint_id(payload)
            entry = entries_by_fingerprint.setdefault(
                fingerprint_id,
                {
                    "fingerprint_id": fingerprint_id,
                    "hypothesis": payload,
                    "occurrences": [],
                },
            )
            if canonical_json_bytes(entry["hypothesis"]) != canonical_json_bytes(payload):
                raise BehaviorHypothesisLedgerError("fingerprint collision")
            entry["occurrences"].append(_occurrence(hypothesis, head))
    entries = sorted(entries_by_fingerprint.values(), key=lambda item: item["fingerprint_id"])
    for entry in entries:
        entry["occurrences"].sort(key=lambda item: item["occurrence_id"])
    audit_ids = [item["fingerprint_id"] for item in entries]
    active_ids = [
        item["fingerprint_id"]
        for item in entries
        if any(
            occurrence["status"] == "accepted"
            for occurrence in item["occurrences"]
        )
    ]
    all_revision_ids = sorted(
        {
            item["content_id"]
            for source in source_revisions
            for item in source["revision_lineage"]
        }
    )
    observation_ids = sorted(observations)
    ledger: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "behavior_hypothesis_ledger",
        "content_id": "",
        "ledger_id": _stable_id(
            "behavior-hypothesis-ledger",
            {
                "schema_version": SCHEMA_VERSION,
                "head_content_ids": sorted(
                    item["head_content_id"] for item in source_revisions
                ),
            },
        ),
        "source_revisions": source_revisions,
        "entries": entries,
        "active_fingerprint_ids": active_ids,
        "audit_fingerprint_ids": audit_ids,
        "counts": _counts(entries, source_revisions),
        "release_readiness": {"status": "ready", "blocker_codes": []},
        "source_verification": {
            "status": "verified",
            "validation_mode": "p2g4_revision_chain_source_replay",
            "verified_revision_content_ids": all_revision_ids,
            "verified_observation_content_ids": observation_ids,
        },
        "canonicalization": {
            "builder_version": BUILDER_VERSION,
            "canonical_json": "utf8_nfc_sorted_keys_compact_no_float",
            "content_hash": "sha256",
            "sort_version": CANONICAL_SORT_VERSION,
            "fingerprint_version": FINGERPRINT_VERSION,
        },
    }
    ledger["content_id"] = _content_id(ledger)
    validation = validate_behavior_hypothesis_ledger(ledger)
    if validation["validation_status"] == "blocked":
        codes = sorted({item["code"] for item in validation["findings"]})
        raise BehaviorHypothesisLedgerError(
            "built ledger failed validation: " + ", ".join(codes)
        )
    if revision_bytes != [canonical_json_bytes(item) for item in revisions]:
        raise BehaviorHypothesisLedgerError("source revision was mutated")
    if observation_bytes != [canonical_json_bytes(item) for item in observation_artifacts]:
        raise BehaviorHypothesisLedgerError("source observation was mutated")
    return ledger


def _validate_ledger_impl(ledger: Mapping[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    try:
        canonical_json_bytes(ledger)
    except Exception as exc:
        return _validation([_finding("NON_CANONICAL_LEDGER", str(exc))])
    for error in sorted(
        _schema_validator().iter_errors(ledger),
        key=lambda item: (_json_path(item.absolute_path), item.message),
    ):
        findings.append(
            _finding(
                "LEDGER_SCHEMA_INVALID",
                f"{_json_path(error.absolute_path)}: {error.message}",
            )
        )
    try:
        expected_content_id = _content_id(ledger)
    except Exception:
        expected_content_id = ""
    if ledger.get("content_id") != expected_content_id:
        findings.append(_finding("LEDGER_CONTENT_ID_MISMATCH", "content_id differs"))
    sources = ledger.get("source_revisions")
    sources = sources if isinstance(sources, list) else []
    mapping_sources = [item for item in sources if isinstance(item, Mapping)]
    if mapping_sources != sorted(
        mapping_sources, key=lambda item: str(item.get("revision_chain_id") or "")
    ):
        findings.append(_finding("SOURCE_REVISION_ORDER_INVALID", "sources are not sorted"))
    source_index: dict[str, Mapping[str, Any]] = {}
    all_revision_ids: set[str] = set()
    observation_ids: set[str] = set()
    for source in mapping_sources:
        chain_id = str(source.get("revision_chain_id") or "")
        if chain_id in source_index:
            findings.append(_finding("SOURCE_REVISION_DUPLICATE", chain_id))
        source_index[chain_id] = source
        lineage = source.get("revision_lineage")
        lineage = lineage if isinstance(lineage, list) else []
        numbers = [item.get("revision_no") for item in lineage if isinstance(item, Mapping)]
        if numbers != list(range(1, len(lineage) + 1)):
            findings.append(_finding("SOURCE_LINEAGE_INVALID", chain_id))
        for index, item in enumerate(lineage):
            if not isinstance(item, Mapping):
                continue
            all_revision_ids.add(str(item.get("content_id") or ""))
            if index:
                previous = lineage[index - 1]
                if item.get("parent_content_id") != previous.get("content_id"):
                    findings.append(_finding("SOURCE_LINEAGE_BROKEN", chain_id))
        if lineage:
            if (
                source.get("head_content_id") != lineage[-1].get("content_id")
                or source.get("head_revision_no") != lineage[-1].get("revision_no")
            ):
                findings.append(_finding("SOURCE_HEAD_MISMATCH", chain_id))
            if lineage[0].get("parent_content_id") != source.get(
                "root_hypothesis_set_content_id"
            ):
                findings.append(_finding("SOURCE_ROOT_MISMATCH", chain_id))
        observation_ids.add(str(source.get("source_observation_content_id") or ""))

    entries = ledger.get("entries")
    entries = entries if isinstance(entries, list) else []
    mapping_entries = [item for item in entries if isinstance(item, Mapping)]
    if mapping_entries != sorted(
        mapping_entries, key=lambda item: str(item.get("fingerprint_id") or "")
    ):
        findings.append(_finding("LEDGER_ENTRY_ORDER_INVALID", "entries are not sorted"))
    entry_index: dict[str, Mapping[str, Any]] = {}
    occurrence_ids: set[str] = set()
    for entry in mapping_entries:
        fingerprint_id = str(entry.get("fingerprint_id") or "")
        payload = entry.get("hypothesis")
        payload = payload if isinstance(payload, Mapping) else {}
        if fingerprint_id in entry_index:
            findings.append(_finding("LEDGER_FINGERPRINT_DUPLICATE", fingerprint_id))
        entry_index[fingerprint_id] = entry
        if fingerprint_id != _fingerprint_id(payload):
            findings.append(_finding("LEDGER_FINGERPRINT_MISMATCH", fingerprint_id))
        proposal = {
            key: deepcopy(payload.get(key))
            for key in _PAYLOAD_FIELDS
            if key not in {"warning_codes", "guardrail_flags"}
        }
        try:
            normalized = p2g3._normalize_proposal(proposal)  # noqa: SLF001
            if normalized != proposal:
                findings.append(_finding("LEDGER_PAYLOAD_NON_CANONICAL", fingerprint_id))
        except Exception as exc:
            findings.append(_finding("LEDGER_PAYLOAD_INVALID", str(exc)))
        for code in sorted(p2g3._p2g_policy_codes(proposal)):  # noqa: SLF001
            findings.append(_finding(code, fingerprint_id))
        occurrences = entry.get("occurrences")
        occurrences = occurrences if isinstance(occurrences, list) else []
        mapping_occurrences = [item for item in occurrences if isinstance(item, Mapping)]
        if mapping_occurrences != sorted(
            mapping_occurrences, key=lambda item: str(item.get("occurrence_id") or "")
        ):
            findings.append(_finding("LEDGER_OCCURRENCE_ORDER_INVALID", fingerprint_id))
        for occurrence in mapping_occurrences:
            occurrence_id = str(occurrence.get("occurrence_id") or "")
            identity = deepcopy(dict(occurrence))
            identity.pop("occurrence_id", None)
            if occurrence_id != _stable_id("hypothesis-occurrence", identity):
                findings.append(_finding("LEDGER_OCCURRENCE_ID_MISMATCH", occurrence_id))
            if occurrence_id in occurrence_ids:
                findings.append(_finding("LEDGER_OCCURRENCE_DUPLICATE", occurrence_id))
            occurrence_ids.add(occurrence_id)
            source = source_index.get(str(occurrence.get("revision_chain_id") or ""))
            if source is None:
                findings.append(_finding("LEDGER_OCCURRENCE_SOURCE_MISSING", occurrence_id))
            elif (
                occurrence.get("head_content_id") != source.get("head_content_id")
                or occurrence.get("source_hypothesis_set_content_id")
                != source.get("root_hypothesis_set_content_id")
                or occurrence.get("source_observation_content_id")
                != source.get("source_observation_content_id")
            ):
                findings.append(_finding("LEDGER_OCCURRENCE_SOURCE_MISMATCH", occurrence_id))
            history = occurrence.get("review_history")
            history = history if isinstance(history, list) else []
            if history != sorted(
                history,
                key=lambda item: (
                    str(item.get("reviewed_at") or "") if isinstance(item, Mapping) else "",
                    str(item.get("review_event_id") or "") if isinstance(item, Mapping) else "",
                ),
            ):
                findings.append(_finding("LEDGER_REVIEW_HISTORY_ORDER_INVALID", occurrence_id))

    audit_ids = sorted(entry_index)
    active_ids = sorted(
        fingerprint_id
        for fingerprint_id, entry in entry_index.items()
        if any(
            occurrence.get("status") == "accepted"
            for occurrence in entry.get("occurrences", [])
            if isinstance(occurrence, Mapping)
        )
    )
    if ledger.get("audit_fingerprint_ids") != audit_ids:
        findings.append(_finding("LEDGER_AUDIT_VIEW_MISMATCH", "audit view differs"))
    if ledger.get("active_fingerprint_ids") != active_ids:
        findings.append(_finding("LEDGER_ACTIVE_VIEW_MISMATCH", "active view differs"))
    expected_counts = _counts(mapping_entries, mapping_sources)
    if ledger.get("counts") != expected_counts:
        findings.append(_finding("LEDGER_COUNTS_MISMATCH", "counts differ"))
    expected_ledger_id = _stable_id(
        "behavior-hypothesis-ledger",
        {
            "schema_version": SCHEMA_VERSION,
            "head_content_ids": sorted(
                str(item.get("head_content_id") or "") for item in mapping_sources
            ),
        },
    )
    if ledger.get("ledger_id") != expected_ledger_id:
        findings.append(_finding("LEDGER_ID_MISMATCH", "ledger identity differs"))
    if ledger.get("source_verification") != {
        "status": "verified",
        "validation_mode": "p2g4_revision_chain_source_replay",
        "verified_revision_content_ids": sorted(all_revision_ids),
        "verified_observation_content_ids": sorted(observation_ids),
    }:
        findings.append(_finding("LEDGER_SOURCE_VERIFICATION_MISMATCH", "source receipt differs"))
    if ledger.get("release_readiness") != {"status": "ready", "blocker_codes": []}:
        findings.append(_finding("LEDGER_RELEASE_READINESS_MISMATCH", "release is not ready"))
    if ledger.get("canonicalization") != {
        "builder_version": BUILDER_VERSION,
        "canonical_json": "utf8_nfc_sorted_keys_compact_no_float",
        "content_hash": "sha256",
        "sort_version": CANONICAL_SORT_VERSION,
        "fingerprint_version": FINGERPRINT_VERSION,
    }:
        findings.append(_finding("LEDGER_CANONICALIZATION_MISMATCH", "metadata differs"))
    return _validation(findings)


def validate_behavior_hypothesis_ledger(
    ledger: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate arbitrary ledger JSON-like input without raising."""

    if not isinstance(ledger, Mapping):
        return _validation([_finding("MALFORMED_LEDGER", "ledger must be an object")])
    try:
        return _validate_ledger_impl(ledger)
    except Exception as exc:
        return _validation([_finding("MALFORMED_LEDGER", str(exc))])


def replay_validate_behavior_hypothesis_ledger(
    ledger: Mapping[str, Any],
    *,
    revisions: Sequence[Mapping[str, Any]],
    observation_artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Rebuild from explicit sources and compare canonical ledger bytes."""

    offline = validate_behavior_hypothesis_ledger(ledger)
    findings = list(offline["findings"])
    try:
        rebuilt = build_behavior_hypothesis_ledger(revisions, observation_artifacts)
    except Exception as exc:
        rebuilt = None
        findings.append(_finding("LEDGER_SOURCE_REPLAY_FAILED", str(exc)))
    if rebuilt is not None and canonical_json_bytes(rebuilt) != canonical_json_bytes(ledger):
        findings.append(_finding("LEDGER_SOURCE_REPLAY_MISMATCH", "rebuilt bytes differ"))
    result = _validation(findings, mode="source_replay")
    result["release_readiness"] = str(
        (ledger.get("release_readiness") or {}).get("status") or "blocked"
    )
    result["source_verification"] = {
        "status": (
            "verified"
            if result["validation_status"] == "accepted"
            and result["release_readiness"] == "ready"
            else "blocked"
        ),
        "ledger_content_id": ledger.get("content_id"),
        "rebuilt_content_id": rebuilt.get("content_id") if rebuilt is not None else None,
    }
    return result


def _event_matches(
    occurrence: Mapping[str, Any],
    *,
    actor: str | None,
    reviewed_from: str | None,
    reviewed_to: str | None,
) -> bool:
    if actor is None and reviewed_from is None and reviewed_to is None:
        return True
    for event in occurrence.get("review_history", []):
        if not isinstance(event, Mapping):
            continue
        reviewed_at = str(event.get("reviewed_at") or "")
        if actor is not None and event.get("actor") != actor:
            continue
        if reviewed_from is not None and reviewed_at < reviewed_from:
            continue
        if reviewed_to is not None and reviewed_at >= reviewed_to:
            continue
        return True
    return False


def query_behavior_hypothesis_ledger(
    ledger: Mapping[str, Any],
    *,
    view: str = "active",
    status: str | None = None,
    hypothesis_id: str | None = None,
    episode_id: str | None = None,
    market_context: str | None = None,
    evaluation_id: str | None = None,
    source_observation_content_id: str | None = None,
    actor: str | None = None,
    reviewed_from: str | None = None,
    reviewed_to: str | None = None,
) -> dict[str, Any]:
    """Return deterministic AND-filtered active or audit projections."""

    if validate_behavior_hypothesis_ledger(ledger)["validation_status"] == "blocked":
        raise BehaviorHypothesisLedgerError("refusing to query an invalid ledger")
    if view not in {"active", "audit"}:
        raise BehaviorHypothesisLedgerError("view must be active or audit")
    if status is not None and status not in _STATUSES:
        raise BehaviorHypothesisLedgerError("unsupported status filter")
    canonical_from = (
        _canonical_timestamp(reviewed_from, "reviewed_from")
        if reviewed_from is not None
        else None
    )
    canonical_to = (
        _canonical_timestamp(reviewed_to, "reviewed_to")
        if reviewed_to is not None
        else None
    )
    if canonical_from is not None and canonical_from != reviewed_from:
        raise BehaviorHypothesisLedgerError("reviewed_from must use canonical UTC Z")
    if canonical_to is not None and canonical_to != reviewed_to:
        raise BehaviorHypothesisLedgerError("reviewed_to must use canonical UTC Z")
    if canonical_from is not None and canonical_to is not None and canonical_from >= canonical_to:
        raise BehaviorHypothesisLedgerError("reviewed_from must precede reviewed_to")
    result_entries: list[dict[str, Any]] = []
    for entry in ledger["entries"]:
        payload = entry["hypothesis"]
        scope = payload["scope"]
        if episode_id is not None and episode_id not in scope["episode_ids"]:
            continue
        if market_context is not None and market_context not in scope["market_contexts"]:
            continue
        if evaluation_id is not None and evaluation_id not in {
            *payload["evaluation_refs"],
            *payload["counterevidence_evaluation_refs"],
        }:
            continue
        occurrences = []
        for occurrence in entry["occurrences"]:
            if view == "active" and occurrence["status"] != "accepted":
                continue
            if status is not None and occurrence["status"] != status:
                continue
            if hypothesis_id is not None and occurrence["hypothesis_id"] != hypothesis_id:
                continue
            if (
                source_observation_content_id is not None
                and occurrence["source_observation_content_id"]
                != source_observation_content_id
            ):
                continue
            if not _event_matches(
                occurrence,
                actor=actor,
                reviewed_from=canonical_from,
                reviewed_to=canonical_to,
            ):
                continue
            occurrences.append(deepcopy(occurrence))
        if occurrences:
            result_entries.append(
                {
                    "fingerprint_id": entry["fingerprint_id"],
                    "hypothesis": deepcopy(payload),
                    "occurrences": occurrences,
                }
            )
    filters = {
        "status": status,
        "hypothesis_id": hypothesis_id,
        "episode_id": episode_id,
        "market_context": market_context,
        "evaluation_id": evaluation_id,
        "source_observation_content_id": source_observation_content_id,
        "actor": actor,
        "reviewed_from": canonical_from,
        "reviewed_to": canonical_to,
    }
    return {
        "schema_version": QUERY_SCHEMA_VERSION,
        "ledger_content_id": ledger["content_id"],
        "view": view,
        "filters": filters,
        "match_count": len(result_entries),
        "entries": result_entries,
    }


def render_behavior_hypothesis_ledger_markdown(ledger: Mapping[str, Any]) -> str:
    """Render active and audit projections without turning the ledger into a profile."""

    if validate_behavior_hypothesis_ledger(ledger)["validation_status"] == "blocked":
        raise BehaviorHypothesisLedgerError("refusing to render an invalid ledger")
    lines = [
        "# Behavior Hypothesis Ledger",
        "",
        f"- schema_version: {_markdown_code(ledger['schema_version'])}",
        f"- content_id: {_markdown_code(ledger['content_id'])}",
        f"- ledger_id: {_markdown_code(ledger['ledger_id'])}",
        "- source_chain_count: " + _markdown_code(ledger["counts"]["source_chain_count"]),
        "- source_revision_count: "
        + _markdown_code(ledger["counts"]["source_revision_count"]),
        "- source_replay_status: "
        + _markdown_code(ledger["source_verification"]["status"]),
        "",
        "> 本台账不是心理画像、评分器或交易建议。accepted 只是人工确认的工作假设。",
        "",
        "## Source Revision Chains",
    ]
    for source in ledger["source_revisions"]:
        lines.extend(
            [
                "",
                f"### {_markdown_code(source['revision_chain_id'])}",
                "",
                f"- head_content_id: {_markdown_code(source['head_content_id'])}",
                f"- head_revision_no: {_markdown_code(source['head_revision_no'])}",
                "- source_observation_content_id: "
                + _markdown_code(source["source_observation_content_id"]),
                "- lineage: "
                + ", ".join(
                    _markdown_code(item["content_id"])
                    for item in source["revision_lineage"]
                ),
            ]
        )

    def append_view(title: str, query: Mapping[str, Any]) -> None:
        lines.extend(["", f"## {title}"])
        if not query["entries"]:
            lines.extend(["", "无条目。"])
            return
        for entry in query["entries"]:
            payload = entry["hypothesis"]
            lines.extend(
                [
                    "",
                    f"### {_markdown_code(entry['fingerprint_id'])}",
                    "",
                ]
            )
            lines.extend(_wrapped(payload["statement"], prefix="- statement: "))
            _string_list(lines, "episode_ids", payload["scope"]["episode_ids"])
            _string_list(lines, "market_contexts", payload["scope"]["market_contexts"])
            _string_list(lines, "evaluation_refs", payload["evaluation_refs"])
            _string_list(
                lines,
                "counterevidence_evaluation_refs",
                payload["counterevidence_evaluation_refs"],
            )
            _string_list(
                lines, "alternative_explanations", payload["alternative_explanations"]
            )
            _string_list(lines, "assumptions", payload["assumptions"])
            _string_list(lines, "uncertainty_notes", payload["uncertainty_notes"])
            _string_list(
                lines, "falsification_conditions", payload["falsification_conditions"]
            )
            _string_list(
                lines, "next_observations_needed", payload["next_observations_needed"]
            )
            lines.append(
                "- temporal_perspective: "
                + _markdown_code(payload["temporal_perspective"])
            )
            lines.append("- occurrences:")
            for occurrence in entry["occurrences"]:
                lines.append(
                    "  - "
                    + _markdown_code(occurrence["status"])
                    + " | "
                    + _markdown_code(occurrence["hypothesis_id"])
                    + " | "
                    + _markdown_code(occurrence["revision_chain_id"])
                )
                for event in occurrence["review_history"]:
                    lines.append(
                        "    - "
                        + _markdown_code(event["reviewed_at"])
                        + " | "
                        + _markdown_escape(event["actor"])
                        + " | "
                        + _markdown_code(event["action"])
                    )

    append_view("Active View", query_behavior_hypothesis_ledger(ledger, view="active"))
    append_view("Audit View", query_behavior_hypothesis_ledger(ledger, view="audit"))
    return "\n".join(lines) + "\n"


def save_behavior_hypothesis_ledger(
    path: str | Path, ledger: Mapping[str, Any]
) -> Path:
    if validate_behavior_hypothesis_ledger(ledger)["validation_status"] == "blocked":
        raise BehaviorHypothesisLedgerError("refusing to save an invalid ledger")
    output = Path(path)
    if output.exists():
        raise BehaviorHypothesisLedgerError("ledger output already exists")
    try:
        return atomic_create_bytes(output, pretty_json_bytes(ledger))
    except (ArtifactIOError, OSError) as exc:
        raise BehaviorHypothesisLedgerError("failed to create ledger output") from exc


def save_behavior_hypothesis_ledger_markdown(path: str | Path, rendered: str) -> Path:
    output = Path(path)
    if output.exists():
        raise BehaviorHypothesisLedgerError("ledger Markdown output already exists")
    try:
        return atomic_create_bytes(output, rendered.encode("utf-8"))
    except (ArtifactIOError, OSError) as exc:
        raise BehaviorHypothesisLedgerError("failed to create ledger Markdown") from exc


def load_behavior_hypothesis_ledger(path: str | Path) -> dict[str, Any]:
    try:
        return load_json_object(path)
    except (ArtifactIOError, OSError, ValueError) as exc:
        raise BehaviorHypothesisLedgerError("failed to load ledger JSON") from exc


__all__ = [
    "BUILDER_VERSION",
    "CANONICAL_SORT_VERSION",
    "FINGERPRINT_VERSION",
    "QUERY_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "VALIDATION_SCHEMA_VERSION",
    "BehaviorHypothesisLedgerError",
    "build_behavior_hypothesis_ledger",
    "load_behavior_hypothesis_ledger",
    "query_behavior_hypothesis_ledger",
    "render_behavior_hypothesis_ledger_markdown",
    "replay_validate_behavior_hypothesis_ledger",
    "save_behavior_hypothesis_ledger",
    "save_behavior_hypothesis_ledger_markdown",
    "validate_behavior_hypothesis_ledger",
]
