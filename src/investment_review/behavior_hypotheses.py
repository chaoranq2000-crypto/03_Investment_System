"""Offline, deterministic P2G-3 behavior hypothesis candidates.

P2G-3 consumes one validated P2G-2 behavior-observation set plus one explicitly
recorded JSON response.  It never calls a model, reads a database, opens the
network, or changes the source artifact.  Unsafe or invalid responses return the
exact source observation object and a separate attempt receipt.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from jsonschema import Draft202012Validator

from .artifact_io import (
    ArtifactIOError,
    atomic_create_bytes,
    canonical_json_bytes,
    load_json_object,
    pretty_json_bytes,
)
from .behavior_observations import (
    SCHEMA_VERSION as OBSERVATION_SCHEMA_VERSION,
    validate_behavior_observation_set,
)
from .episode_interpretation import interpretation_policy_codes


SCHEMA_VERSION = "p2g.behavior_hypothesis_set.v1"
RESPONSE_SCHEMA_VERSION = "p2g.behavior_hypothesis_response.v1"
ATTEMPT_SCHEMA_VERSION = "p2g.behavior_hypothesis_attempt.v1"
VALIDATION_SCHEMA_VERSION = "p2g.behavior_hypothesis_set.validation.v1"
ATTEMPT_VALIDATION_SCHEMA_VERSION = (
    "p2g.behavior_hypothesis_attempt.validation.v1"
)
BUILDER_VERSION = "p2g.behavior_hypothesis_set.builder.v1"
CANONICAL_SORT_VERSION = "p2g.behavior_hypothesis_sort.v1"
MAX_RESPONSE_BYTES = 1_048_576

_ROOT = Path(__file__).resolve().parents[2]
_RESPONSE_SCHEMA_PATH = (
    _ROOT
    / "docs"
    / "contracts"
    / "P2G_3_BEHAVIOR_HYPOTHESIS_RESPONSE.schema.json"
)
_ARTIFACT_SCHEMA_PATH = (
    _ROOT
    / "docs"
    / "contracts"
    / "P2G_3_BEHAVIOR_HYPOTHESIS_SET.schema.json"
)
_ATTEMPT_SCHEMA_PATH = (
    _ROOT
    / "docs"
    / "contracts"
    / "P2G_3_BEHAVIOR_HYPOTHESIS_ATTEMPT.schema.json"
)

_CONTENT_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ATTEMPT_ID_RE = re.compile(r"^attempt:[0-9a-f]{32}$")
_HYPOTHESIS_ID_RE = re.compile(r"^hypothesis:[0-9a-f]{32}$")
_EVALUATION_ID_RE = re.compile(r"^evaluation:[0-9a-f]{32}$")

_PSYCHOLOGICAL_CAUSALITY_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE | re.DOTALL)
    for pattern in (
        r"\bbecause\s+(?:of\s+)?(?:fear|greed|panic|anxiety|emotion)\b",
        r"\b(?:fear|greed|panic|anxiety|emotion)\b.{0,32}\bcaused?\b",
        r"因为.{0,12}(?:恐惧|贪婪|焦虑|恐慌|情绪).{0,12}(?:所以|导致|因而)",
        r"(?:恐惧|贪婪|焦虑|恐慌|情绪).{0,12}(?:导致|造成|所以)",
    )
)
_UNBOUNDED_LONGITUDINAL_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:always|inevitably|invariably|will certainly)\b",
        r"\b(?:permanent|fixed)\s+(?:behavior|behaviour|trait|pattern)\b",
        r"总是|必然|永远|一贯如此|长期必定|以后一定",
    )
)
_REPEAT_CLAIM_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:stable|repeated|recurring|persistent|established)\s+(?:behavior\s+)?pattern\b",
        r"\bpattern\s+(?:is|has been)\s+(?:stable|repeated|recurring|established)\b",
        r"稳定(?:行为)?模式|重复模式(?:已经|已)?形成|反复出现的固定模式",
    )
)
_REPEAT_LIMITATION_MARKERS = (
    "insufficient",
    "not enough",
    "does not establish",
    "cannot establish",
    "not established",
    "证据不足",
    "尚不能",
    "不能确认",
    "未形成",
)


class BehaviorHypothesisError(ValueError):
    """Raised when caller input or P2G-3 artifact I/O violates the contract."""


class _ResponseRejected(BehaviorHypothesisError):
    def __init__(
        self,
        errors: Sequence[Mapping[str, Any]],
        *,
        status: str = "invalid_response",
        canonical_response_sha256: str | None = None,
    ) -> None:
        self.errors = _canonical_errors(errors)
        self.codes = tuple(item["code"] for item in self.errors)
        self.status = status
        self.canonical_response_sha256 = canonical_response_sha256
        super().__init__(", ".join(self.codes) or "MODEL_OUTPUT_INVALID")


@dataclass(frozen=True)
class BehaviorHypothesisBuildResult:
    artifact: dict[str, Any]
    attempt: dict[str, Any]
    used_fallback: bool


def _value_content_id(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _text_content_id(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _content_id(value: Mapping[str, Any]) -> str:
    material = deepcopy(dict(value))
    material.pop("content_id", None)
    return _value_content_id(material)


def _stable_id(prefix: str, value: object) -> str:
    return f"{prefix}:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()[:32]


def _declared_or_observed_content_id(value: Mapping[str, Any]) -> str:
    declared = str(value.get("content_id") or "")
    if _CONTENT_ID_RE.fullmatch(declared):
        return declared
    try:
        return _value_content_id(value)
    except Exception:
        return "sha256:" + hashlib.sha256(repr(value).encode("utf-8")).hexdigest()


def _normalize_text(value: object, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise BehaviorHypothesisError(f"{field} must be text")
    normalized = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace(
        "\r", "\n"
    ).strip()
    if not normalized and not allow_empty:
        raise BehaviorHypothesisError(f"{field} must not be empty")
    return normalized


def _normalize_string_set(value: object, field: str, *, required: bool) -> list[str]:
    if not isinstance(value, list):
        raise BehaviorHypothesisError(f"{field} must be an array")
    normalized = sorted(
        {
            _normalize_text(item, f"{field}[]")
            for item in value
        }
    )
    if required and not normalized:
        raise BehaviorHypothesisError(f"{field} must not be empty")
    return normalized


def _canonical_timestamp(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise BehaviorHypothesisError(f"{field} must be a timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BehaviorHypothesisError(f"invalid {field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.microsecond:
        raise BehaviorHypothesisError(
            f"{field} must use timezone-aware whole seconds"
        )
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _normalize_scope(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise BehaviorHypothesisError("scope must be an object")
    start_raw = value.get("start_at")
    end_raw = value.get("end_at")
    start_at = (
        _canonical_timestamp(start_raw, "scope.start_at")
        if start_raw is not None
        else None
    )
    end_at = (
        _canonical_timestamp(end_raw, "scope.end_at")
        if end_raw is not None
        else None
    )
    if start_at is not None and end_at is not None:
        start = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_at.replace("Z", "+00:00"))
        if start > end:
            raise BehaviorHypothesisError("scope.start_at must not exceed scope.end_at")
    return {
        "episode_ids": _normalize_string_set(
            value.get("episode_ids"), "scope.episode_ids", required=True
        ),
        "start_at": start_at,
        "end_at": end_at,
        "market_contexts": _normalize_string_set(
            value.get("market_contexts", []),
            "scope.market_contexts",
            required=False,
        ),
    }


def _source_temporal_scope(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise BehaviorHypothesisError("source scope must be an object")
    scope = deepcopy(dict(value))
    allowed = {
        "effective_from",
        "effective_to",
        "effective_anchor",
        "knowledge_cutoff",
        "filters",
    }
    unknown = sorted(set(scope) - allowed)
    if unknown:
        raise BehaviorHypothesisError(
            "source scope has unsupported fields: " + ", ".join(unknown)
        )
    for field in ("effective_from", "effective_to", "knowledge_cutoff"):
        canonical = _canonical_timestamp(scope.get(field), f"source_scope.{field}")
        if scope.get(field) != canonical:
            raise BehaviorHypothesisError(
                f"source_scope.{field} must use canonical UTC seconds"
            )
    start = datetime.fromisoformat(scope["effective_from"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(scope["effective_to"].replace("Z", "+00:00"))
    if start >= end:
        raise BehaviorHypothesisError(
            "source_scope.effective_from must precede effective_to"
        )
    anchor = scope.get("effective_anchor")
    if anchor is not None and anchor not in {
        "episode_opened_at",
        "episode_closed_at",
    }:
        raise BehaviorHypothesisError("source_scope.effective_anchor is unsupported")
    filters = scope.get("filters")
    if filters is not None:
        if not isinstance(filters, Mapping) or set(filters) != {
            "account_ids",
            "instrument_ids",
        }:
            raise BehaviorHypothesisError("source_scope.filters is malformed")
        for field in ("account_ids", "instrument_ids"):
            values = filters.get(field)
            if (
                not isinstance(values, list)
                or not all(isinstance(item, str) and item for item in values)
                or values != sorted(set(values))
            ):
                raise BehaviorHypothesisError(
                    f"source_scope.filters.{field} is not canonical"
                )
    canonical_json_bytes(scope)
    return scope


def _scope_outside_source(
    scope: Mapping[str, Any], source_scope: Mapping[str, Any]
) -> bool:
    effective_from = datetime.fromisoformat(
        str(source_scope["effective_from"]).replace("Z", "+00:00")
    )
    effective_to = datetime.fromisoformat(
        str(source_scope["effective_to"]).replace("Z", "+00:00")
    )
    knowledge_cutoff = datetime.fromisoformat(
        str(source_scope["knowledge_cutoff"]).replace("Z", "+00:00")
    )
    upper_bound = min(effective_to, knowledge_cutoff)
    for field in ("start_at", "end_at"):
        value = scope.get(field)
        if value is None:
            continue
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed < effective_from or parsed > upper_bound:
            return True
    return False


def _normalize_proposal(value: Mapping[str, Any]) -> dict[str, Any]:
    search_raw = value.get("counterevidence_search")
    search = (
        _normalize_text(search_raw, "counterevidence_search", allow_empty=True)
        if search_raw is not None
        else None
    )
    if search == "":
        search = None
    return {
        "statement": _normalize_text(value.get("statement"), "statement"),
        "scope": _normalize_scope(value.get("scope")),
        "evaluation_refs": _normalize_string_set(
            value.get("evaluation_refs"), "evaluation_refs", required=True
        ),
        "supporting_reasons": _normalize_string_set(
            value.get("supporting_reasons"), "supporting_reasons", required=True
        ),
        "counterevidence_evaluation_refs": _normalize_string_set(
            value.get("counterevidence_evaluation_refs"),
            "counterevidence_evaluation_refs",
            required=False,
        ),
        "counterevidence_search": search,
        "alternative_explanations": _normalize_string_set(
            value.get("alternative_explanations"),
            "alternative_explanations",
            required=True,
        ),
        "assumptions": _normalize_string_set(
            value.get("assumptions"), "assumptions", required=True
        ),
        "uncertainty_notes": _normalize_string_set(
            value.get("uncertainty_notes"), "uncertainty_notes", required=True
        ),
        "falsification_conditions": _normalize_string_set(
            value.get("falsification_conditions"),
            "falsification_conditions",
            required=True,
        ),
        "next_observations_needed": _normalize_string_set(
            value.get("next_observations_needed"),
            "next_observations_needed",
            required=True,
        ),
        "temporal_perspective": _normalize_text(
            value.get("temporal_perspective"), "temporal_perspective"
        ),
    }


@lru_cache(maxsize=3)
def _validator(path: str) -> Draft202012Validator:
    schema = json.loads(Path(path).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _response_validator() -> Draft202012Validator:
    return _validator(str(_RESPONSE_SCHEMA_PATH))


def _artifact_validator() -> Draft202012Validator:
    return _validator(str(_ARTIFACT_SCHEMA_PATH))


def _attempt_validator() -> Draft202012Validator:
    return _validator(str(_ATTEMPT_SCHEMA_PATH))


def _json_path(parts: Iterable[object]) -> str:
    value = "$"
    for part in parts:
        value += f"[{part}]" if isinstance(part, int) else f".{part}"
    return value


def _error(code: str, message: str, path: str | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "path": path}


def _canonical_errors(values: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[bytes, dict[str, Any]] = {}
    for value in values:
        row = {
            "code": str(value.get("code") or "MODEL_OUTPUT_INVALID"),
            "message": str(value.get("message") or "response failed validation"),
            "path": (
                str(value.get("path")) if value.get("path") is not None else None
            ),
        }
        unique[canonical_json_bytes(row)] = row
    return sorted(
        unique.values(),
        key=lambda item: (item["code"], item["path"] or "", item["message"]),
    )


def _schema_response_errors(value: object) -> list[dict[str, Any]]:
    return [
        _error(
            "MODEL_OUTPUT_SCHEMA_INVALID",
            error.message,
            _json_path(error.absolute_path),
        )
        for error in sorted(
            _response_validator().iter_errors(value),
            key=lambda item: (_json_path(item.absolute_path), item.message),
        )
    ]


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


def _evaluation_index(
    observation_artifact: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    return {
        str(item.get("evaluation_id")): item
        for item in observation_artifact.get("evaluations", [])
        if isinstance(item, Mapping) and str(item.get("evaluation_id") or "")
    }


def _inventory_item(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    subject = evaluation.get("subject")
    if not isinstance(subject, Mapping):
        raise BehaviorHypothesisError("source evaluation subject is malformed")
    return {
        "evaluation_id": str(evaluation.get("evaluation_id") or ""),
        "evaluation_sha256": _value_content_id(evaluation),
        "detector_id": str(evaluation.get("detector_id") or ""),
        "detector_version": str(evaluation.get("detector_version") or ""),
        "status": str(evaluation.get("status") or ""),
        "reason_codes": sorted(
            {str(item) for item in evaluation.get("reason_codes", [])}
        ),
        "episode_ids": sorted(
            {str(item) for item in subject.get("episode_ids", [])}
        ),
        "review_ids": sorted(
            {str(item) for item in subject.get("review_ids", [])}
        ),
    }


def _claims_repeat_without_limit(statement: str) -> bool:
    folded = statement.casefold()
    if any(marker in folded for marker in _REPEAT_LIMITATION_MARKERS):
        return False
    return any(pattern.search(statement) for pattern in _REPEAT_CLAIM_PATTERNS)


def _p2g_policy_codes(value: object) -> set[str]:
    codes = set(interpretation_policy_codes(value))
    material = "\n".join(_walk_strings(value))
    if any(pattern.search(material) for pattern in _PSYCHOLOGICAL_CAUSALITY_PATTERNS):
        codes.add("POLICY_PSYCHOLOGY_CAUSALITY")
    if any(pattern.search(material) for pattern in _UNBOUNDED_LONGITUDINAL_PATTERNS):
        codes.add("POLICY_UNBOUNDED_LONGITUDINAL_CLAIM")
    return codes


def _walk_strings(value: object) -> list[str]:
    result: list[str] = []
    if isinstance(value, str):
        result.append(value)
    elif isinstance(value, Mapping):
        for item in value.values():
            result.extend(_walk_strings(item))
    elif isinstance(value, list):
        for item in value:
            result.extend(_walk_strings(item))
    return result


def _hypothesis_id(
    source_content_id: str, proposal: Mapping[str, Any]
) -> str:
    return _stable_id(
        "hypothesis",
        {
            "source_observation_content_id": source_content_id,
            "statement": proposal.get("statement"),
            "evaluation_refs": proposal.get("evaluation_refs"),
            "scope": proposal.get("scope"),
        },
    )


def _compile_hypotheses(
    proposals: Sequence[Mapping[str, Any]],
    *,
    source_content_id: str,
    evaluation_index: Mapping[str, Mapping[str, Any]],
    source_scope: Mapping[str, Any],
) -> list[dict[str, Any]]:
    semantic_errors: list[dict[str, Any]] = []
    policy_errors: list[dict[str, Any]] = []
    hypotheses: list[dict[str, Any]] = []
    for index, proposal in enumerate(proposals):
        path = f"$.hypotheses[{index}]"
        support_refs = list(proposal["evaluation_refs"])
        counter_refs = list(proposal["counterevidence_evaluation_refs"])
        unknown_support = sorted(set(support_refs) - set(evaluation_index))
        unknown_counter = sorted(set(counter_refs) - set(evaluation_index))
        if unknown_support:
            semantic_errors.append(
                _error(
                    "EVALUATION_REF_UNKNOWN",
                    f"unknown supporting evaluations: {unknown_support}",
                    f"{path}.evaluation_refs",
                )
            )
        if unknown_counter:
            semantic_errors.append(
                _error(
                    "COUNTEREVIDENCE_REF_UNKNOWN",
                    f"unknown counterevidence evaluations: {unknown_counter}",
                    f"{path}.counterevidence_evaluation_refs",
                )
            )
        non_observed = [
            ref
            for ref in support_refs
            if ref in evaluation_index
            and evaluation_index[ref].get("status") != "observed"
        ]
        if non_observed:
            semantic_errors.append(
                _error(
                    "SUPPORT_EVALUATION_NOT_OBSERVED",
                    f"supporting evaluations are not observed: {non_observed}",
                    f"{path}.evaluation_refs",
                )
            )
        overlap = sorted(set(support_refs) & set(counter_refs))
        if overlap:
            semantic_errors.append(
                _error(
                    "SUPPORT_COUNTEREVIDENCE_OVERLAP",
                    f"support and counterevidence overlap: {overlap}",
                    path,
                )
            )
        if not counter_refs and proposal.get("counterevidence_search") is None:
            semantic_errors.append(
                _error(
                    "COUNTEREVIDENCE_REQUIRED",
                    "counterevidence refs or an explicit search note is required",
                    path,
                )
            )
        support_episodes = sorted(
            {
                str(episode_id)
                for ref in support_refs
                if ref in evaluation_index
                for episode_id in (
                    evaluation_index[ref].get("subject", {}).get("episode_ids", [])
                    if isinstance(evaluation_index[ref].get("subject"), Mapping)
                    else []
                )
            }
        )
        if proposal["scope"]["episode_ids"] != support_episodes:
            semantic_errors.append(
                _error(
                    "SCOPE_EPISODE_MISMATCH",
                    "scope episode_ids must exactly match supporting evaluations",
                    f"{path}.scope.episode_ids",
                )
            )
        if _scope_outside_source(proposal["scope"], source_scope):
            semantic_errors.append(
                _error(
                    "TEMPORAL_SCOPE_OUTSIDE_SOURCE",
                    (
                        "scope times must remain inside the source effective window "
                        "and knowledge cutoff"
                    ),
                    f"{path}.scope",
                )
            )
        warning_codes: list[str] = []
        if len(support_episodes) < 2:
            warning_codes.append("insufficient_repeat_evidence")
            if _claims_repeat_without_limit(str(proposal["statement"])):
                policy_errors.append(
                    _error(
                        "INSUFFICIENT_REPEAT_CLAIM",
                        "single-episode evidence cannot claim an established repeated pattern",
                        f"{path}.statement",
                    )
                )
        for code in sorted(_p2g_policy_codes(proposal)):
            policy_errors.append(
                _error(
                    code,
                    "hypothesis text violates the shared P2G interpretation policy",
                    path,
                )
            )
        hypothesis = {
            "hypothesis_id": "",
            "status": "proposed",
            **deepcopy(dict(proposal)),
            "warning_codes": warning_codes,
            "guardrail_flags": [],
        }
        hypothesis["hypothesis_id"] = _hypothesis_id(
            source_content_id, hypothesis
        )
        hypotheses.append(hypothesis)
    ids = [item["hypothesis_id"] for item in hypotheses]
    if len(ids) != len(set(ids)):
        semantic_errors.append(
            _error(
                "DUPLICATE_HYPOTHESIS_ID",
                "semantic duplicate hypotheses are not allowed",
                "$.hypotheses",
            )
        )
    if policy_errors:
        raise _ResponseRejected(policy_errors, status="guardrail_rejected")
    if semantic_errors:
        raise _ResponseRejected(semantic_errors)
    return sorted(hypotheses, key=lambda item: item["hypothesis_id"])


def _attempt_receipt(
    *,
    status: str,
    source_content_id: str,
    model_id: str,
    generated_at: str,
    raw_response_sha256: str | None,
    canonical_response_sha256: str | None,
    output_content_id: str,
    errors: Sequence[Mapping[str, Any]],
    warnings: Sequence[str],
) -> dict[str, Any]:
    canonical_errors = _canonical_errors(errors)
    receipt: dict[str, Any] = {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "content_id": "",
        "attempt_id": "",
        "status": status,
        "source_observation_content_id": source_content_id,
        "model_id": model_id,
        "generated_at": generated_at,
        "raw_response_sha256": raw_response_sha256,
        "canonical_response_sha256": canonical_response_sha256,
        "output_content_id": output_content_id,
        "failure_codes": sorted({item["code"] for item in canonical_errors}),
        "errors": canonical_errors,
        "warnings": sorted({str(item) for item in warnings if str(item)}),
    }
    identity = deepcopy(receipt)
    identity.pop("content_id", None)
    identity.pop("attempt_id", None)
    receipt["attempt_id"] = _stable_id("attempt", identity)
    receipt["content_id"] = _content_id(receipt)
    return receipt


def _fallback(
    source: Mapping[str, Any],
    *,
    status: str,
    source_content_id: str,
    model_id: str,
    generated_at: str,
    raw_response_sha256: str | None,
    canonical_response_sha256: str | None,
    errors: Sequence[Mapping[str, Any]],
) -> BehaviorHypothesisBuildResult:
    artifact = deepcopy(dict(source))
    receipt = _attempt_receipt(
        status=status,
        source_content_id=source_content_id,
        model_id=model_id,
        generated_at=generated_at,
        raw_response_sha256=raw_response_sha256,
        canonical_response_sha256=canonical_response_sha256,
        output_content_id=source_content_id,
        errors=errors,
        warnings=[],
    )
    return BehaviorHypothesisBuildResult(artifact, receipt, True)


def build_behavior_hypothesis_set(
    observation_artifact: Mapping[str, Any],
    *,
    response_text: str | None,
    model_id: str,
    generated_at: str,
) -> BehaviorHypothesisBuildResult:
    """Compile one recorded response or return the exact P2G-2 fallback."""

    if not isinstance(observation_artifact, Mapping):
        raise BehaviorHypothesisError("observation_artifact must be an object")
    normalized_model_id = _normalize_text(model_id, "model_id")
    canonical_generated_at = _canonical_timestamp(generated_at, "generated_at")
    source = deepcopy(dict(observation_artifact))
    source_content_id = _declared_or_observed_content_id(source)
    source_validation = validate_behavior_observation_set(source)
    source_scope: dict[str, Any] | None = None
    try:
        source_scope = _source_temporal_scope(source.get("scope"))
    except (ArtifactIOError, BehaviorHypothesisError, TypeError, ValueError) as exc:
        source_scope_error = str(exc)
    else:
        source_scope_error = None
    if (
        source_validation.get("validation_status") == "blocked"
        or (source.get("release_readiness") or {}).get("status") != "ready"
        or (source.get("source_verification") or {}).get("status") != "verified"
        or source_scope_error is not None
    ):
        return _fallback(
            source,
            status="source_validation_failed",
            source_content_id=source_content_id,
            model_id=normalized_model_id,
            generated_at=canonical_generated_at,
            raw_response_sha256=(
                _text_content_id(response_text) if response_text is not None else None
            ),
            canonical_response_sha256=None,
            errors=[
                _error(
                    "SOURCE_OBSERVATION_SET_INVALID",
                    (
                        "P2G-2 source must be structurally valid, ready, verified, "
                        "and temporally bounded: "
                        f"{source_scope_error or 'source validation failed'}"
                    ),
                    "$.source",
                )
            ],
        )
    if response_text is None:
        return _fallback(
            source,
            status="provider_unavailable",
            source_content_id=source_content_id,
            model_id=normalized_model_id,
            generated_at=canonical_generated_at,
            raw_response_sha256=None,
            canonical_response_sha256=None,
            errors=[
                _error(
                    "MODEL_PROVIDER_UNAVAILABLE",
                    "no recorded response was supplied; source observations preserved",
                    None,
                )
            ],
        )
    if not isinstance(response_text, str):
        raise BehaviorHypothesisError("response_text must be text or None")
    raw_response_sha256 = _text_content_id(response_text)
    if len(response_text.encode("utf-8")) > MAX_RESPONSE_BYTES:
        return _fallback(
            source,
            status="invalid_response",
            source_content_id=source_content_id,
            model_id=normalized_model_id,
            generated_at=canonical_generated_at,
            raw_response_sha256=raw_response_sha256,
            canonical_response_sha256=None,
            errors=[
                _error(
                    "MODEL_RESPONSE_TOO_LARGE",
                    f"recorded response exceeds {MAX_RESPONSE_BYTES} UTF-8 bytes",
                    "$",
                )
            ],
        )

    parsed: object
    canonical_response_sha256: str | None = None
    try:
        parsed = json.loads(response_text)
        canonical_json_bytes(parsed)
    except (json.JSONDecodeError, ArtifactIOError, TypeError, ValueError):
        return _fallback(
            source,
            status="invalid_response",
            source_content_id=source_content_id,
            model_id=normalized_model_id,
            generated_at=canonical_generated_at,
            raw_response_sha256=raw_response_sha256,
            canonical_response_sha256=None,
            errors=[
                _error(
                    "MODEL_OUTPUT_INVALID_JSON",
                    "recorded response must be one strict canonical JSON object",
                    "$",
                )
            ],
        )
    try:
        canonical_response_sha256 = _value_content_id(parsed)
    except Exception:
        canonical_response_sha256 = None
    schema_errors = _schema_response_errors(parsed)
    if schema_errors:
        return _fallback(
            source,
            status="invalid_response",
            source_content_id=source_content_id,
            model_id=normalized_model_id,
            generated_at=canonical_generated_at,
            raw_response_sha256=raw_response_sha256,
            canonical_response_sha256=canonical_response_sha256,
            errors=schema_errors,
        )

    try:
        assert isinstance(parsed, Mapping)
        normalized_proposals = [
            _normalize_proposal(item)
            for item in parsed["hypotheses"]
            if isinstance(item, Mapping)
        ]
        normalized_proposals.sort(key=canonical_json_bytes)
        normalized_response = {
            "schema_version": RESPONSE_SCHEMA_VERSION,
            "hypotheses": normalized_proposals,
        }
        canonical_response_sha256 = _value_content_id(normalized_response)
        hypotheses = _compile_hypotheses(
            normalized_proposals,
            source_content_id=source_content_id,
            evaluation_index=_evaluation_index(source),
            source_scope=source_scope,
        )
    except _ResponseRejected as exc:
        return _fallback(
            source,
            status=exc.status,
            source_content_id=source_content_id,
            model_id=normalized_model_id,
            generated_at=canonical_generated_at,
            raw_response_sha256=raw_response_sha256,
            canonical_response_sha256=(
                exc.canonical_response_sha256 or canonical_response_sha256
            ),
            errors=exc.errors,
        )
    except (ArtifactIOError, BehaviorHypothesisError, TypeError, ValueError) as exc:
        return _fallback(
            source,
            status="invalid_response",
            source_content_id=source_content_id,
            model_id=normalized_model_id,
            generated_at=canonical_generated_at,
            raw_response_sha256=raw_response_sha256,
            canonical_response_sha256=canonical_response_sha256,
            errors=[
                _error(
                    "MODEL_OUTPUT_NORMALIZATION_FAILED",
                    str(exc),
                    "$.hypotheses",
                )
            ],
        )

    referenced_ids = sorted(
        {
            ref
            for item in hypotheses
            for ref in [
                *item["evaluation_refs"],
                *item["counterevidence_evaluation_refs"],
            ]
        }
    )
    evaluation_index = _evaluation_index(source)
    inventory = [_inventory_item(evaluation_index[item]) for item in referenced_ids]
    model_provenance = {
        "model_id": normalized_model_id,
        "generated_at": canonical_generated_at,
        "response_sha256": canonical_response_sha256,
    }
    artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "behavior_hypothesis_candidate_set",
        "content_id": "",
        "hypothesis_set_id": _stable_id(
            "hypothesis-set",
            {
                "schema_version": SCHEMA_VERSION,
                "source_observation_content_id": source_content_id,
                "model_provenance": model_provenance,
            },
        ),
        "source_observation_set": {
            "schema_version": OBSERVATION_SCHEMA_VERSION,
            "observation_set_id": str(source.get("observation_set_id") or ""),
            "content_id": source_content_id,
            "release_readiness": "ready",
            "source_verification": "verified",
            "temporal_scope": source_scope,
        },
        "evaluation_inventory": inventory,
        "model_provenance": model_provenance,
        "hypotheses": hypotheses,
        "warnings": sorted(
            {
                warning
                for item in hypotheses
                for warning in item["warning_codes"]
            }
        ),
        "release_readiness": {"status": "ready", "blocker_codes": []},
        "source_verification": {
            "status": "verified",
            "validation_mode": "validated_p2g2_observation_set",
            "verified_content_id": source_content_id,
        },
        "canonicalization": {
            "builder_version": BUILDER_VERSION,
            "canonical_json": "utf8_nfc_sorted_keys_compact_no_float",
            "content_hash": "sha256",
            "sort_version": CANONICAL_SORT_VERSION,
        },
    }
    artifact["content_id"] = _content_id(artifact)
    validation = validate_behavior_hypothesis_set(artifact)
    if validation["validation_status"] == "blocked":
        codes = [item["code"] for item in validation["findings"]]
        raise BehaviorHypothesisError(
            f"built P2G-3 artifact failed validation: {codes}"
        )
    receipt = _attempt_receipt(
        status="succeeded",
        source_content_id=source_content_id,
        model_id=normalized_model_id,
        generated_at=canonical_generated_at,
        raw_response_sha256=raw_response_sha256,
        canonical_response_sha256=canonical_response_sha256,
        output_content_id=str(artifact["content_id"]),
        errors=[],
        warnings=artifact["warnings"],
    )
    return BehaviorHypothesisBuildResult(artifact, receipt, False)


def _validate_hypothesis_impl(artifact: Mapping[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    try:
        canonical_json_bytes(artifact)
    except Exception as exc:
        return _validation([_finding("NON_CANONICAL_VALUE", str(exc))])
    schema_errors = list(_artifact_validator().iter_errors(artifact))
    for error in schema_errors:
        findings.append(_finding("SCHEMA_VALIDATION_ERROR", error.message))
    if artifact.get("schema_version") != SCHEMA_VERSION:
        findings.append(_finding("SCHEMA_VERSION_MISMATCH", "unsupported P2G-3 schema"))
    if artifact.get("artifact_type") != "behavior_hypothesis_candidate_set":
        findings.append(_finding("ARTIFACT_TYPE_MISMATCH", "unexpected artifact type"))
    try:
        expected_content_id = _content_id(artifact)
    except Exception:
        expected_content_id = ""
    if artifact.get("content_id") != expected_content_id:
        findings.append(_finding("CONTENT_ID_MISMATCH", "content_id is not canonical"))
    source = artifact.get("source_observation_set")
    if not isinstance(source, Mapping):
        source = {}
        findings.append(_finding("SOURCE_OBSERVATION_SET_INVALID", "source binding is missing"))
    source_content_id = str(source.get("content_id") or "")
    if source.get("schema_version") != OBSERVATION_SCHEMA_VERSION:
        findings.append(_finding("SOURCE_OBSERVATION_SET_INVALID", "source schema mismatch"))
    if (
        source.get("release_readiness") != "ready"
        or source.get("source_verification") != "verified"
    ):
        findings.append(_finding("SOURCE_OBSERVATION_SET_INVALID", "source status mismatch"))
    source_scope: dict[str, Any] | None = None
    try:
        source_scope = _source_temporal_scope(source.get("temporal_scope"))
    except (ArtifactIOError, BehaviorHypothesisError, TypeError, ValueError) as exc:
        findings.append(_finding("SOURCE_TEMPORAL_SCOPE_INVALID", str(exc)))

    inventory = artifact.get("evaluation_inventory")
    if not isinstance(inventory, list):
        inventory = []
        findings.append(_finding("EVALUATION_INVENTORY_INVALID", "inventory must be an array"))
    mapping_inventory = [item for item in inventory if isinstance(item, Mapping)]
    if mapping_inventory != sorted(
        mapping_inventory, key=lambda item: str(item.get("evaluation_id") or "")
    ):
        findings.append(_finding("EVALUATION_INVENTORY_ORDER_INVALID", "inventory is not sorted"))
    inventory_index: dict[str, Mapping[str, Any]] = {}
    for item in mapping_inventory:
        evaluation_id = str(item.get("evaluation_id") or "")
        if not _EVALUATION_ID_RE.fullmatch(evaluation_id):
            findings.append(_finding("EVALUATION_INVENTORY_INVALID", evaluation_id or "missing id"))
        if evaluation_id in inventory_index:
            findings.append(_finding("EVALUATION_INVENTORY_DUPLICATE", evaluation_id))
        inventory_index[evaluation_id] = item
        if not _CONTENT_ID_RE.fullmatch(str(item.get("evaluation_sha256") or "")):
            findings.append(_finding("EVALUATION_INVENTORY_INVALID", f"{evaluation_id} hash"))
        for field in ("episode_ids", "review_ids", "reason_codes"):
            values = item.get(field)
            if not isinstance(values, list) or values != sorted(set(values)):
                findings.append(
                    _finding(
                        "EVALUATION_INVENTORY_INVALID", f"{evaluation_id} {field}"
                    )
                )

    hypotheses = artifact.get("hypotheses")
    if not isinstance(hypotheses, list):
        hypotheses = []
        findings.append(_finding("HYPOTHESES_INVALID", "hypotheses must be an array"))
    mapping_hypotheses = [item for item in hypotheses if isinstance(item, Mapping)]
    if mapping_hypotheses != sorted(
        mapping_hypotheses, key=lambda item: str(item.get("hypothesis_id") or "")
    ):
        findings.append(_finding("HYPOTHESIS_ORDER_INVALID", "hypotheses are not sorted"))
    hypothesis_ids: set[str] = set()
    used_inventory_ids: set[str] = set()
    expected_warnings: set[str] = set()
    for item in mapping_hypotheses:
        hypothesis_id = str(item.get("hypothesis_id") or "")
        if hypothesis_id in hypothesis_ids:
            findings.append(_finding("DUPLICATE_HYPOTHESIS_ID", hypothesis_id))
        hypothesis_ids.add(hypothesis_id)
        if (
            not _HYPOTHESIS_ID_RE.fullmatch(hypothesis_id)
            or hypothesis_id != _hypothesis_id(source_content_id, item)
        ):
            findings.append(_finding("HYPOTHESIS_ID_MISMATCH", hypothesis_id or "missing id"))
        if item.get("status") != "proposed":
            findings.append(_finding("HYPOTHESIS_STATUS_INVALID", hypothesis_id))
        if item.get("guardrail_flags") != []:
            findings.append(_finding("GUARDRAIL_FLAGS_PRESENT", hypothesis_id))
        if item.get("temporal_perspective") != "retrospective":
            findings.append(_finding("TEMPORAL_PERSPECTIVE_INVALID", hypothesis_id))
        proposal_fields = {
            key: deepcopy(item.get(key))
            for key in (
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
        }
        try:
            canonical_proposal = _normalize_proposal(proposal_fields)
        except BehaviorHypothesisError as exc:
            findings.append(
                _finding(
                    "HYPOTHESIS_CANONICALIZATION_INVALID", f"{hypothesis_id}: {exc}"
                )
            )
        else:
            if proposal_fields != canonical_proposal:
                findings.append(_finding("HYPOTHESIS_CANONICALIZATION_INVALID", hypothesis_id))
        support_refs = item.get("evaluation_refs")
        counter_refs = item.get("counterevidence_evaluation_refs")
        if not isinstance(support_refs, list):
            support_refs = []
        if not isinstance(counter_refs, list):
            counter_refs = []
        used_inventory_ids.update(str(ref) for ref in [*support_refs, *counter_refs])
        unknown_support = sorted(set(support_refs) - set(inventory_index))
        unknown_counter = sorted(set(counter_refs) - set(inventory_index))
        if unknown_support:
            findings.append(
                _finding(
                    "EVALUATION_REF_UNKNOWN", f"{hypothesis_id}: {unknown_support}"
                )
            )
        if unknown_counter:
            findings.append(
                _finding(
                    "COUNTEREVIDENCE_REF_UNKNOWN",
                    f"{hypothesis_id}: {unknown_counter}",
                )
            )
        if set(support_refs) & set(counter_refs):
            findings.append(_finding("SUPPORT_COUNTEREVIDENCE_OVERLAP", hypothesis_id))
        if not counter_refs and not item.get("counterevidence_search"):
            findings.append(_finding("COUNTEREVIDENCE_REQUIRED", hypothesis_id))
        non_observed = [
            ref
            for ref in support_refs
            if ref in inventory_index and inventory_index[ref].get("status") != "observed"
        ]
        if non_observed:
            findings.append(
                _finding(
                    "SUPPORT_EVALUATION_NOT_OBSERVED",
                    f"{hypothesis_id}: {non_observed}",
                )
            )
        expected_episodes = sorted(
            {
                str(episode_id)
                for ref in support_refs
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
                if _scope_outside_source(scope, source_scope):
                    findings.append(
                        _finding("TEMPORAL_SCOPE_OUTSIDE_SOURCE", hypothesis_id)
                    )
            except Exception as exc:
                findings.append(
                    _finding("HYPOTHESIS_CANONICALIZATION_INVALID", str(exc))
                )
        expected_item_warnings = (
            ["insufficient_repeat_evidence"] if len(expected_episodes) < 2 else []
        )
        if item.get("warning_codes") != expected_item_warnings:
            findings.append(_finding("HYPOTHESIS_WARNING_MISMATCH", hypothesis_id))
        expected_warnings.update(expected_item_warnings)
        if len(expected_episodes) < 2 and _claims_repeat_without_limit(
            str(item.get("statement") or "")
        ):
            findings.append(_finding("INSUFFICIENT_REPEAT_CLAIM", hypothesis_id))
        for code in sorted(_p2g_policy_codes(item)):
            findings.append(_finding(code, hypothesis_id))
    if set(inventory_index) != used_inventory_ids:
        findings.append(
            _finding(
                "EVALUATION_INVENTORY_SCOPE_MISMATCH",
                "inventory must equal referenced evaluations",
            )
        )
    if artifact.get("warnings") != sorted(expected_warnings):
        findings.append(_finding("WARNINGS_MISMATCH", "top-level warnings are inconsistent"))

    model = artifact.get("model_provenance")
    if not isinstance(model, Mapping):
        model = {}
        findings.append(_finding("MODEL_PROVENANCE_INVALID", "model provenance is missing"))
    try:
        generated_at = _canonical_timestamp(model.get("generated_at"), "model.generated_at")
    except BehaviorHypothesisError:
        findings.append(_finding("MODEL_PROVENANCE_INVALID", "generated_at is invalid"))
    else:
        if generated_at != model.get("generated_at"):
            findings.append(_finding("MODEL_PROVENANCE_INVALID", "generated_at is not canonical"))
    if not _CONTENT_ID_RE.fullmatch(str(model.get("response_sha256") or "")):
        findings.append(_finding("MODEL_PROVENANCE_INVALID", "response hash is invalid"))
    expected_set_id = _stable_id(
        "hypothesis-set",
        {
            "schema_version": SCHEMA_VERSION,
            "source_observation_content_id": source_content_id,
            "model_provenance": deepcopy(dict(model)),
        },
    )
    if artifact.get("hypothesis_set_id") != expected_set_id:
        findings.append(_finding("HYPOTHESIS_SET_ID_MISMATCH", "set identity mismatch"))
    if artifact.get("release_readiness") != {"status": "ready", "blocker_codes": []}:
        findings.append(_finding("RELEASE_READINESS_MISMATCH", "release readiness must be ready"))
    if artifact.get("source_verification") != {
        "status": "verified",
        "validation_mode": "validated_p2g2_observation_set",
        "verified_content_id": source_content_id,
    }:
        findings.append(
            _finding(
                "SOURCE_VERIFICATION_MISMATCH", "source verification is inconsistent"
            )
        )
    if artifact.get("canonicalization") != {
        "builder_version": BUILDER_VERSION,
        "canonical_json": "utf8_nfc_sorted_keys_compact_no_float",
        "content_hash": "sha256",
        "sort_version": CANONICAL_SORT_VERSION,
    }:
        findings.append(
            _finding(
                "CANONICALIZATION_MISMATCH",
                "canonicalization metadata is inconsistent",
            )
        )
    return _validation(findings)


def validate_behavior_hypothesis_set(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Validate arbitrary JSON-like P2G-3 input without raising."""

    if not isinstance(artifact, Mapping):
        return _validation([_finding("MALFORMED_HYPOTHESIS_SET", "artifact must be an object")])
    try:
        return _validate_hypothesis_impl(artifact)
    except Exception as exc:
        return _validation([_finding("MALFORMED_HYPOTHESIS_SET", str(exc))])


def replay_validate_behavior_hypothesis_set(
    artifact: Mapping[str, Any], *, observation_artifact: Mapping[str, Any]
) -> dict[str, Any]:
    """Replay the P2G-2 source binding and every referenced evaluation projection."""

    offline = validate_behavior_hypothesis_set(artifact)
    findings = list(offline["findings"])
    source_validation = validate_behavior_observation_set(observation_artifact)
    source = artifact.get("source_observation_set")
    source = source if isinstance(source, Mapping) else {}
    expected_source_id = str(source.get("content_id") or "")
    actual_source_id = str(observation_artifact.get("content_id") or "")
    if (
        source_validation.get("validation_status") == "blocked"
        or (observation_artifact.get("release_readiness") or {}).get("status") != "ready"
        or (observation_artifact.get("source_verification") or {}).get("status") != "verified"
    ):
        findings.append(
            _finding(
                "SOURCE_REPLAY_ERROR",
                "P2G-2 source is not valid, ready and verified",
            )
        )
    if expected_source_id != actual_source_id:
        findings.append(_finding("SOURCE_REPLAY_MISMATCH", "source content_id differs"))
    if source.get("observation_set_id") != observation_artifact.get("observation_set_id"):
        findings.append(_finding("SOURCE_REPLAY_MISMATCH", "observation_set_id differs"))
    if source.get("temporal_scope") != observation_artifact.get("scope"):
        findings.append(_finding("SOURCE_REPLAY_MISMATCH", "source temporal scope differs"))
    source_index = _evaluation_index(observation_artifact)
    for item in artifact.get("evaluation_inventory", []):
        if not isinstance(item, Mapping):
            continue
        evaluation_id = str(item.get("evaluation_id") or "")
        source_evaluation = source_index.get(evaluation_id)
        if source_evaluation is None:
            findings.append(
                _finding(
                    "SOURCE_REPLAY_MISMATCH",
                    f"missing source evaluation {evaluation_id}",
                )
            )
        else:
            try:
                expected_item = _inventory_item(source_evaluation)
            except Exception as exc:
                findings.append(_finding("SOURCE_REPLAY_ERROR", str(exc)))
            else:
                if canonical_json_bytes(expected_item) != canonical_json_bytes(item):
                    findings.append(
                        _finding(
                            "SOURCE_REPLAY_MISMATCH",
                            f"evaluation projection differs: {evaluation_id}",
                        )
                    )
    result = _validation(findings, mode="source_replay")
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


def _validate_behavior_hypothesis_attempt_impl(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(receipt, Mapping):
        return {
            "schema_version": ATTEMPT_VALIDATION_SCHEMA_VERSION,
            "validation_status": "blocked",
            "findings": [_finding("MALFORMED_HYPOTHESIS_ATTEMPT", "attempt must be an object")],
        }
    findings: list[dict[str, str]] = []
    try:
        canonical_json_bytes(receipt)
    except Exception as exc:
        findings.append(_finding("ATTEMPT_NON_CANONICAL", str(exc)))
    for error in _attempt_validator().iter_errors(receipt):
        findings.append(_finding("ATTEMPT_SCHEMA_INVALID", error.message))
    try:
        expected_content_id = _content_id(receipt)
    except Exception:
        expected_content_id = ""
    if receipt.get("content_id") != expected_content_id:
        findings.append(_finding("ATTEMPT_CONTENT_ID_MISMATCH", "attempt content_id mismatch"))
    material = deepcopy(dict(receipt))
    material.pop("content_id", None)
    material.pop("attempt_id", None)
    try:
        expected_attempt_id = _stable_id("attempt", material)
    except Exception:
        expected_attempt_id = ""
    attempt_id = str(receipt.get("attempt_id") or "")
    if not _ATTEMPT_ID_RE.fullmatch(attempt_id) or attempt_id != expected_attempt_id:
        findings.append(_finding("ATTEMPT_ID_MISMATCH", "attempt_id mismatch"))
    try:
        generated_at = _canonical_timestamp(receipt.get("generated_at"), "generated_at")
    except BehaviorHypothesisError:
        findings.append(_finding("ATTEMPT_GENERATED_AT_INVALID", "generated_at is invalid"))
    else:
        if generated_at != receipt.get("generated_at"):
            findings.append(
                _finding(
                    "ATTEMPT_GENERATED_AT_INVALID",
                    "generated_at is not canonical",
                )
            )
    errors = receipt.get("errors")
    failures = receipt.get("failure_codes")
    warnings = receipt.get("warnings")
    if not isinstance(errors, list):
        errors = []
    expected_failures = sorted(
        {
            str(item.get("code"))
            for item in errors
            if isinstance(item, Mapping) and str(item.get("code") or "")
        }
    )
    if failures != expected_failures:
        findings.append(
            _finding(
                "ATTEMPT_FAILURE_CODES_INVALID", "failure codes do not match errors"
            )
        )
    if isinstance(errors, list) and errors != _canonical_errors(
        [item for item in errors if isinstance(item, Mapping)]
    ):
        findings.append(_finding("ATTEMPT_ERRORS_NOT_CANONICAL", "errors are not canonical"))
    if not isinstance(warnings, list) or warnings != sorted(set(warnings)):
        findings.append(_finding("ATTEMPT_WARNINGS_INVALID", "warnings are not canonical"))
    status = receipt.get("status")
    source_content_id = str(receipt.get("source_observation_content_id") or "")
    output_content_id = str(receipt.get("output_content_id") or "")
    raw_hash = receipt.get("raw_response_sha256")
    canonical_hash = receipt.get("canonical_response_sha256")
    if status == "succeeded":
        if (
            errors
            or failures
            or raw_hash is None
            or canonical_hash is None
            or output_content_id == source_content_id
        ):
            findings.append(_finding("ATTEMPT_SUCCESS_INVALID", "success receipt is inconsistent"))
    elif status == "provider_unavailable":
        if (
            not errors
            or raw_hash is not None
            or canonical_hash is not None
            or output_content_id != source_content_id
        ):
            findings.append(
                _finding(
                    "ATTEMPT_FALLBACK_INVALID",
                    "provider fallback receipt is inconsistent",
                )
            )
    elif status in {"invalid_response", "guardrail_rejected", "source_validation_failed"}:
        if not errors or not failures or output_content_id != source_content_id:
            findings.append(_finding("ATTEMPT_FALLBACK_INVALID", "failure receipt is inconsistent"))
    rows = _validation(findings)
    return {
        "schema_version": ATTEMPT_VALIDATION_SCHEMA_VERSION,
        "validation_status": rows["validation_status"],
        "findings": rows["findings"],
    }


def validate_behavior_hypothesis_attempt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Validate arbitrary JSON-like attempt input without raising."""

    if not isinstance(receipt, Mapping):
        return {
            "schema_version": ATTEMPT_VALIDATION_SCHEMA_VERSION,
            "validation_status": "blocked",
            "findings": [
                _finding(
                    "MALFORMED_HYPOTHESIS_ATTEMPT", "attempt must be an object"
                )
            ],
        }
    try:
        return _validate_behavior_hypothesis_attempt_impl(receipt)
    except Exception as exc:
        return {
            "schema_version": ATTEMPT_VALIDATION_SCHEMA_VERSION,
            "validation_status": "blocked",
            "findings": [
                _finding("MALFORMED_HYPOTHESIS_ATTEMPT", str(exc))
            ],
        }


def replay_validate_behavior_hypothesis_attempt(
    receipt: Mapping[str, Any], *, response_text: str | None
) -> dict[str, Any]:
    validation = validate_behavior_hypothesis_attempt(receipt)
    findings = list(validation["findings"])
    actual_raw = _text_content_id(response_text) if response_text is not None else None
    if receipt.get("raw_response_sha256") != actual_raw:
        findings.append(_finding("MODEL_OUTPUT_HASH_MISMATCH", "raw response hash differs"))
    result = _validation(findings, mode="attempt_replay")
    return {
        "schema_version": ATTEMPT_VALIDATION_SCHEMA_VERSION,
        "validation_status": result["validation_status"],
        "findings": result["findings"],
        "output_verification": {
            "status": "verified" if result["validation_status"] == "accepted" else "blocked",
            "expected_raw_response_sha256": receipt.get("raw_response_sha256"),
            "actual_raw_response_sha256": actual_raw,
        },
    }


def save_behavior_hypothesis_result(
    output_path: str | Path,
    artifact: Mapping[str, Any],
    attempt_path: str | Path,
    attempt: Mapping[str, Any],
) -> tuple[Path, Path]:
    """Create the result and receipt as a guarded pair, rolling back on failure."""

    attempt_validation = validate_behavior_hypothesis_attempt(attempt)
    if attempt_validation["validation_status"] == "blocked":
        raise BehaviorHypothesisError("refusing to save an invalid attempt receipt")
    status = attempt.get("status")
    artifact_content_id = _declared_or_observed_content_id(artifact)
    if attempt.get("output_content_id") != artifact_content_id:
        raise BehaviorHypothesisError(
            "artifact does not match the attempt output binding"
        )
    if status == "succeeded":
        if validate_behavior_hypothesis_set(artifact)["validation_status"] == "blocked":
            raise BehaviorHypothesisError("refusing to save an invalid P2G-3 artifact")
        source = artifact.get("source_observation_set")
        model = artifact.get("model_provenance")
        source = source if isinstance(source, Mapping) else {}
        model = model if isinstance(model, Mapping) else {}
        if attempt.get("source_observation_content_id") != source.get("content_id"):
            raise BehaviorHypothesisError(
                "artifact source does not match the attempt receipt"
            )
        if (
            attempt.get("model_id") != model.get("model_id")
            or attempt.get("generated_at") != model.get("generated_at")
            or attempt.get("canonical_response_sha256")
            != model.get("response_sha256")
            or attempt.get("warnings") != artifact.get("warnings")
        ):
            raise BehaviorHypothesisError(
                "artifact provenance does not match the attempt receipt"
            )
    else:
        source_validation = validate_behavior_observation_set(artifact)
        if (
            source_validation.get("validation_status") == "blocked"
            and status != "source_validation_failed"
        ):
            raise BehaviorHypothesisError("fallback output is not a valid P2G-2 artifact")
        if artifact_content_id != attempt.get("source_observation_content_id"):
            raise BehaviorHypothesisError("fallback output does not match the attempt receipt")
    output = Path(output_path)
    attempt_output = Path(attempt_path)
    if output.resolve() == attempt_output.resolve():
        raise BehaviorHypothesisError("output and attempt-output must be distinct")
    if output.exists():
        raise BehaviorHypothesisError(f"output already exists: {output}")
    if attempt_output.exists():
        raise BehaviorHypothesisError(f"attempt output already exists: {attempt_output}")
    created_output = False
    try:
        atomic_create_bytes(output, pretty_json_bytes(artifact))
        created_output = True
        atomic_create_bytes(attempt_output, pretty_json_bytes(attempt))
    except (ArtifactIOError, FileExistsError, OSError) as exc:
        if created_output and output.exists():
            output.unlink()
        raise BehaviorHypothesisError(f"failed to create result pair: {exc}") from exc
    return output, attempt_output


def load_behavior_hypothesis_set(path: str | Path) -> dict[str, Any]:
    try:
        return load_json_object(path)
    except (ArtifactIOError, json.JSONDecodeError, OSError) as exc:
        raise BehaviorHypothesisError(str(exc)) from exc


def load_behavior_hypothesis_attempt(path: str | Path) -> dict[str, Any]:
    try:
        return load_json_object(path)
    except (ArtifactIOError, json.JSONDecodeError, OSError) as exc:
        raise BehaviorHypothesisError(str(exc)) from exc


__all__ = [
    "ATTEMPT_SCHEMA_VERSION",
    "ATTEMPT_VALIDATION_SCHEMA_VERSION",
    "BUILDER_VERSION",
    "CANONICAL_SORT_VERSION",
    "MAX_RESPONSE_BYTES",
    "RESPONSE_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "VALIDATION_SCHEMA_VERSION",
    "BehaviorHypothesisBuildResult",
    "BehaviorHypothesisError",
    "build_behavior_hypothesis_set",
    "load_behavior_hypothesis_attempt",
    "load_behavior_hypothesis_set",
    "replay_validate_behavior_hypothesis_attempt",
    "replay_validate_behavior_hypothesis_set",
    "save_behavior_hypothesis_result",
    "validate_behavior_hypothesis_attempt",
    "validate_behavior_hypothesis_set",
]
