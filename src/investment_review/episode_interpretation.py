"""Bounded, auditable P2F interpretation over an immutable facts layer.

The default implementation does not know how to call a network model.  Callers
must inject a provider explicitly.  Provider failures and invalid outputs return
the original facts-only artifact byte-for-byte and record a separate attempt
receipt, so model availability can never damage the deterministic fact record.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from jsonschema import Draft202012Validator

from .artifact_io import (
    ArtifactIOError,
    atomic_write_bytes,
    canonical_json_bytes,
    pretty_json_bytes,
)
from .episode_review import (
    FACT_SECTION_NAMES,
    INTERPRETATION_SECTION_NAMES,
    SCHEMA_VERSION as EPISODE_REVIEW_SCHEMA_VERSION,
    EpisodeReviewError,
    validate_episode_review,
)


OUTPUT_SCHEMA_VERSION = "p2f.interpretation_output.v1"
ATTEMPT_SCHEMA_VERSION = "p2f.interpretation_attempt.v1"
ATTEMPT_VALIDATION_SCHEMA_VERSION = "p2f.interpretation_attempt.validation.v1"
INTERPRETATION_ENGINE_VERSION = "p2f.interpretation.v1"
PROMPT_TEMPLATE_ID = "p2f.bounded_interpretation.v1"

_OUTPUT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "contracts"
    / "P2F_INTERPRETATION_OUTPUT_DRAFT.schema.json"
)
_CONTENT_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ATTEMPT_ID_RE = re.compile(r"^attempt:[0-9a-f]{32}$")
_FINDING_ID_RE = re.compile(r"^finding:[0-9a-f]{32}$")
_OPTION_ID_RE = re.compile(r"^option:[0-9a-f]{32}$")
_SECTION_KIND = {
    "main_tensions": "main_tension",
    "hypotheses": "hypothesis",
    "alternative_explanations": "alternative_explanation",
}
_PSYCHOLOGY_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        (
            r"\b(?:greed|fear|panic|loss aversion|psychological diagnosis|"
            r"undisciplined|poor discipline)\b"
        ),
        r"贪婪|恐惧|恐慌|纪律差|损失厌恶|心理诊断",
    )
)
_ADVICE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:should|must|recommend(?:ed|ation)?(?:\s+to)?)\s+(?:buy|sell|hold|add|reduce|close)",
        r"\brecommend(?:ed|s|ing)?\s+(?:buying|selling|holding|adding|reducing|closing)\b",
        r"(?:^|\n|[.!?]\s+)(?:buy|sell|hold|add|reduce|close)\b",
        r"\b(?:allocate|put)\s+\d+(?:\.\d+)?%\s+(?:of\s+)?(?:the\s+)?portfolio\b",
        r"\bposition\s+size\b.{0,12}\d+(?:\.\d+)?%",
        r"(?:建议|应该|应当|必须|立即|现在).{0,8}(?:买入|卖出|持有|加仓|减仓|清仓)",
        r"(?:^|\n|[。！？]\s*)(?:买入|卖出|持有|加仓|减仓|清仓).{0,12}(?:。|！|？|$)",
        r"仓位.{0,6}\d+(?:\.\d+)?%",
    )
)
_SCORE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:mechanical\s+score|overall\s+score|rating)\b.{0,8}\d",
        r"(?:机械评分|总分|综合评分|评级).{0,8}\d",
        r"\bscore\s*(?::|=|is)?\s*\d+(?:\s*/\s*100)?\b",
    )
)
_OUTCOME_QUALITY_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bprofit(?:able)?\b.{0,24}\b(?:correct|good decision|right decision)\b",
        r"\bloss\b.{0,24}\b(?:wrong|bad decision|incorrect)\b",
        r"\b(?:correct|good decision|right decision)\b.{0,24}\bprofit(?:able)?\b",
        r"\b(?:wrong|bad decision|incorrect)\b.{0,24}\bloss\b",
        r"盈利.{0,16}(?:正确|好决策)|亏损.{0,16}(?:错误|坏决策)",
        r"(?:正确|好决策).{0,16}盈利|(?:错误|坏决策).{0,16}亏损",
    )
)
_HINDSIGHT_PRICE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:best|highest|lowest|peak|bottom)\s+(?:future\s+)?price\b",
        r"\b(?:sell|exit)\s+at\s+(?:the\s+)?(?:peak|highest)\b",
        r"\b(?:buy|enter)\s+at\s+(?:the\s+)?(?:bottom|lowest)\b",
        r"(?:事后最佳价|最高价卖出|最低价买入|卖在最高点|买在最低点)",
    )
)


class InterpretationError(ValueError):
    """Raised for invalid caller input or an unsafe interpretation artifact."""


class InterpretationOutputError(InterpretationError):
    """Raised when provider output fails a closed contract or policy gate."""

    def __init__(self, codes: Sequence[str]):
        self.codes = tuple(sorted({str(code) for code in codes if str(code)}))
        super().__init__(", ".join(self.codes) or "MODEL_OUTPUT_INVALID")


class InterpretationProvider(Protocol):
    """Minimal injectable provider interface; no network behavior is implied."""

    model_id: str

    def generate(self, *, prompt: str, parameters: Mapping[str, Any]) -> str:
        """Return the exact raw UTF-8 model response text."""


@dataclass(frozen=True)
class RecordedResponseProvider:
    """Deterministic provider backed by one already-recorded response."""

    model_id: str
    response_text: str

    def generate(self, *, prompt: str, parameters: Mapping[str, Any]) -> str:
        del prompt, parameters
        return self.response_text


@dataclass(frozen=True)
class UnavailableInterpretationProvider:
    """Explicit provider used to exercise the safe fallback path."""

    model_id: str

    def generate(self, *, prompt: str, parameters: Mapping[str, Any]) -> str:
        del prompt, parameters
        raise TimeoutError("provider unavailable")


@dataclass(frozen=True)
class InterpretationBuildResult:
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


def _canonical_timestamp(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise InterpretationError(f"{field} must be a timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InterpretationError(f"invalid {field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.microsecond:
        raise InterpretationError(f"{field} must use timezone-aware whole seconds")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


@lru_cache(maxsize=1)
def _output_validator() -> Draft202012Validator:
    schema = json.loads(_OUTPUT_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _schema_error_codes(value: object) -> list[str]:
    return [
        "MODEL_OUTPUT_SCHEMA_INVALID"
        for _ in _output_validator().iter_errors(value)
    ]


def facts_only_projection(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Reconstruct the immutable P2F-2 projection from a revision-1 review."""

    projection = deepcopy(dict(artifact))
    projection["interpretation_sections"] = {
        name: [] for name in INTERPRETATION_SECTION_NAMES
    }
    governance = (
        projection.get("governance")
        if isinstance(projection.get("governance"), dict)
        else {}
    )
    governance["facts_interpretation_separated"] = True
    governance["no_advice"] = True
    governance["no_mechanical_score"] = True
    governance["generation_mode"] = "facts_only"
    governance["model_generation"] = None
    governance["human_reviews"] = []
    projection["governance"] = governance
    projection["content_id"] = _content_id(projection)
    return projection


def _prompt_input(facts_artifact: Mapping[str, Any]) -> dict[str, Any]:
    sections = facts_artifact.get("fact_sections")
    if not isinstance(sections, Mapping):
        raise InterpretationError("fact_sections must be an object")
    prompt_sections: dict[str, Any] = {}
    for name in FACT_SECTION_NAMES:
        section = sections.get(name)
        if not isinstance(section, Mapping):
            raise InterpretationError(f"missing fact section {name}")
        prompt_sections[name] = {
            "status": section.get("status"),
            "reason": section.get("reason"),
            "warning_codes": deepcopy(section.get("warning_codes")),
            "gap_codes": deepcopy(section.get("gap_codes")),
            "facts": [
                {
                    "fact_id": fact.get("fact_id"),
                    "kind": fact.get("kind"),
                    "statement": fact.get("statement"),
                    "availability": fact.get("availability"),
                    "temporal_role": fact.get("temporal_role"),
                    "effective_at": fact.get("effective_at"),
                    "knowledge_at": fact.get("knowledge_at"),
                    "warning_codes": deepcopy(fact.get("warning_codes")),
                }
                for fact in section.get("facts", [])
                if isinstance(fact, Mapping)
            ],
        }
    return {
        "schema_version": "p2f.interpretation_prompt_input.v1",
        "review_id": facts_artifact.get("review_id"),
        "facts_content_id": facts_artifact.get("content_id"),
        "input_bundle_ref": deepcopy(facts_artifact.get("input_bundle_ref")),
        "fact_sections": prompt_sections,
    }


def build_interpretation_prompt(facts_artifact: Mapping[str, Any]) -> str:
    """Build the fixed prompt from facts only, excluding raw source payloads."""

    prompt_input = canonical_json_bytes(_prompt_input(facts_artifact)).decode("utf-8")
    return "\n".join(
        (
            "P2F bounded interpretation contract v1.",
            "Return only one JSON object matching p2f.interpretation_output.v1.",
            "Every finding must cite fact IDs, state assumptions and uncertainty, "
            "and preserve counterevidence.",
            "decision_time findings may use only known_at_decision or not_applicable facts.",
            "Counterfactuals may use only information available within their "
            "declared temporal_scope.",
            "Do not diagnose psychology, score decisions, infer missing motives, "
            "issue trading advice, or use hindsight-best prices.",
            "history_links must be an empty array because no typed history input is supplied.",
            "FACTS_JSON:",
            prompt_input,
        )
    )


def _finding_id(section_name: str, item: Mapping[str, Any]) -> str:
    material = deepcopy(dict(item))
    material.pop("finding_id", None)
    return _stable_id("finding", {"section": section_name, "finding": material})


def _option_id(item: Mapping[str, Any]) -> str:
    material = deepcopy(dict(item))
    material.pop("option_id", None)
    return _stable_id("option", material)


def _sorted_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        raise InterpretationOutputError(["MODEL_OUTPUT_SCHEMA_INVALID"])
    return sorted({str(item).strip() for item in value if str(item).strip()})


def _normalize_provider_output(raw_text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
        canonical_json_bytes(parsed)
    except (json.JSONDecodeError, ArtifactIOError, TypeError) as exc:
        raise InterpretationOutputError(["MODEL_OUTPUT_INVALID_JSON"]) from exc
    schema_codes = _schema_error_codes(parsed)
    if schema_codes:
        raise InterpretationOutputError(schema_codes)
    sections = parsed["interpretation_sections"]
    normalized: dict[str, list[dict[str, Any]]] = {
        name: [] for name in INTERPRETATION_SECTION_NAMES
    }
    for section_name, expected_kind in _SECTION_KIND.items():
        for raw in sections[section_name]:
            item = {
                "finding_id": "",
                "kind": str(raw["kind"]),
                "perspective": str(raw["perspective"]),
                "statement": str(raw["statement"]).strip(),
                "confidence": str(raw["confidence"]),
                "fact_refs": _sorted_strings(raw["fact_refs"]),
                "counterevidence_status": str(raw["counterevidence_status"]),
                "counterevidence_fact_refs": _sorted_strings(
                    raw["counterevidence_fact_refs"]
                ),
                "assumptions": _sorted_strings(raw["assumptions"]),
                "uncertainty": str(raw["uncertainty"]).strip(),
                "review_status": "draft",
            }
            if item["kind"] != expected_kind:
                raise InterpretationOutputError(["INTERPRETATION_KIND_MISMATCH"])
            item["finding_id"] = _finding_id(section_name, item)
            normalized[section_name].append(item)
        normalized[section_name].sort(key=lambda item: item["finding_id"])
        if len({item["finding_id"] for item in normalized[section_name]}) != len(
            normalized[section_name]
        ):
            raise InterpretationOutputError(["DUPLICATE_INTERPRETATION_ID"])
    for raw in sections["counterfactual_options"]:
        item = {
            "option_id": "",
            "description": str(raw["description"]).strip(),
            "fact_refs": _sorted_strings(raw["fact_refs"]),
            "temporal_scope": str(raw["temporal_scope"]),
            "feasibility": str(raw["feasibility"]),
            "tradeoffs": _sorted_strings(raw["tradeoffs"]),
            "not_advice": True,
        }
        item["option_id"] = _option_id(item)
        normalized["counterfactual_options"].append(item)
    normalized["counterfactual_options"].sort(key=lambda item: item["option_id"])
    if len(
        {item["option_id"] for item in normalized["counterfactual_options"]}
    ) != len(normalized["counterfactual_options"]):
        raise InterpretationOutputError(["DUPLICATE_INTERPRETATION_ID"])
    normalized["history_links"] = []
    return normalized


def _fact_index(artifact: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    sections = artifact.get("fact_sections")
    if not isinstance(sections, Mapping):
        return {}
    return {
        str(fact.get("fact_id")): fact
        for name in FACT_SECTION_NAMES
        for fact in (
            sections.get(name, {}).get("facts", [])
            if isinstance(sections.get(name), Mapping)
            else []
        )
        if isinstance(fact, Mapping) and str(fact.get("fact_id") or "")
    }


def _strings(value: object) -> list[str]:
    values: list[str] = []
    if isinstance(value, str):
        values.append(value)
    elif isinstance(value, Mapping):
        for item in value.values():
            values.extend(_strings(item))
    elif isinstance(value, list):
        for item in value:
            values.extend(_strings(item))
    return values


def _policy_codes(sections: Mapping[str, Any]) -> set[str]:
    material = "\n".join(_strings(sections))
    codes: set[str] = set()
    if any(pattern.search(material) for pattern in _PSYCHOLOGY_PATTERNS):
        codes.add("POLICY_PSYCHOLOGY_DIAGNOSIS")
    if any(pattern.search(material) for pattern in _ADVICE_PATTERNS):
        codes.add("POLICY_DIRECT_ADVICE")
    if any(pattern.search(material) for pattern in _SCORE_PATTERNS):
        codes.add("POLICY_MECHANICAL_SCORE")
    if any(pattern.search(material) for pattern in _OUTCOME_QUALITY_PATTERNS):
        codes.add("POLICY_OUTCOME_QUALITY")
    if any(pattern.search(material) for pattern in _HINDSIGHT_PRICE_PATTERNS):
        codes.add("POLICY_HINDSIGHT_PRICE")
    return codes


def _finding(code: str, message: str) -> dict[str, str]:
    return {"severity": "blocker", "code": code, "message": message}


def interpretation_layer_findings(
    artifact: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Return semantic/policy findings for model-assisted P2F-3 content."""

    governance = artifact.get("governance")
    if not isinstance(governance, Mapping):
        return [_finding("GOVERNANCE_INVALID", "governance must be an object")]
    mode = governance.get("generation_mode")
    if mode == "human_authored":
        return [
            _finding(
                "GENERATION_MODE_NOT_ENABLED",
                "human-authored revisions are not enabled until P2F-4",
            )
        ]
    if mode != "model_assisted":
        return []

    findings: list[dict[str, str]] = []
    revision = artifact.get("revision")
    if revision != {
        "revision_no": 1,
        "status": "draft",
        "supersedes_content_id": None,
        "correction_reason": None,
    }:
        findings.append(
            _finding(
                "MODEL_ASSISTED_REVISION_INVALID",
                "P2F-3 model output must remain revision 1 draft",
            )
        )
    if governance.get("human_reviews") != []:
        findings.append(
            _finding(
                "MODEL_ASSISTED_HUMAN_REVIEW_INVALID",
                "P2F-3 cannot contain human review events",
            )
        )
    sections = artifact.get("interpretation_sections")
    if not isinstance(sections, Mapping):
        return findings + [
            _finding("INTERPRETATION_INVALID", "interpretation_sections must be an object")
        ]
    if sections.get("history_links") != []:
        findings.append(
            _finding(
                "HISTORY_INPUT_NOT_TYPED",
                "history_links must remain empty without a typed history input",
            )
        )
    if not any(sections.get(name) for name in INTERPRETATION_SECTION_NAMES[:-1]):
        findings.append(
            _finding(
                "INTERPRETATION_EMPTY",
                "model-assisted mode requires at least one bounded interpretation",
            )
        )
    if (sections.get("main_tensions") or sections.get("hypotheses")) and not sections.get(
        "alternative_explanations"
    ):
        findings.append(
            _finding(
                "ALTERNATIVE_EXPLANATION_REQUIRED",
                "a tension or hypothesis requires at least one alternative explanation",
            )
        )

    fact_index = _fact_index(artifact)
    all_ids: set[str] = set()
    for section_name, expected_kind in _SECTION_KIND.items():
        raw_items = sections.get(section_name)
        if not isinstance(raw_items, list):
            continue
        mapping_items = [item for item in raw_items if isinstance(item, Mapping)]
        if mapping_items != sorted(
            mapping_items, key=lambda item: str(item.get("finding_id") or "")
        ):
            findings.append(
                _finding(
                    "INTERPRETATION_ORDER_INVALID",
                    f"{section_name} is not sorted by finding_id",
                )
            )
        for item in mapping_items:
            finding_id = str(item.get("finding_id") or "")
            if item.get("kind") != expected_kind:
                findings.append(
                    _finding(
                        "INTERPRETATION_KIND_MISMATCH",
                        f"{finding_id or section_name} has the wrong kind",
                    )
                )
            if (
                not _FINDING_ID_RE.fullmatch(finding_id)
                or finding_id != _finding_id(section_name, item)
            ):
                findings.append(
                    _finding(
                        "INTERPRETATION_ID_MISMATCH",
                        f"{finding_id or section_name} is not content-derived",
                    )
                )
            if finding_id in all_ids:
                findings.append(
                    _finding("DUPLICATE_INTERPRETATION_ID", finding_id)
                )
            all_ids.add(finding_id)
            if item.get("review_status") != "draft":
                findings.append(
                    _finding(
                        "MODEL_REVIEW_STATUS_INVALID",
                        f"{finding_id} must remain draft before P2F-4",
                    )
                )
            refs = item.get("fact_refs")
            counter_refs = item.get("counterevidence_fact_refs")
            if not isinstance(refs, list):
                refs = []
            if not isinstance(counter_refs, list):
                counter_refs = []
            if refs != sorted(set(refs)) or not refs:
                findings.append(
                    _finding(
                        "INTERPRETATION_FACT_REF_INVALID",
                        f"{finding_id} needs sorted, unique fact refs",
                    )
                )
            if counter_refs != sorted(set(counter_refs)):
                findings.append(
                    _finding(
                        "COUNTEREVIDENCE_REF_INVALID",
                        f"{finding_id} counterevidence refs are not canonical",
                    )
                )
            if set(refs) & set(counter_refs):
                findings.append(
                    _finding(
                        "COUNTEREVIDENCE_REF_INVALID",
                        f"{finding_id} cannot use one fact as support and counterevidence",
                    )
                )
            unknown = sorted((set(refs) | set(counter_refs)) - set(fact_index))
            if unknown:
                findings.append(
                    _finding(
                        "INTERPRETATION_FACT_REF_UNKNOWN",
                        f"{finding_id} references unknown facts",
                    )
                )
            counter_status = item.get("counterevidence_status")
            if counter_status == "available" and not counter_refs:
                findings.append(
                    _finding(
                        "COUNTEREVIDENCE_REF_REQUIRED",
                        f"{finding_id} declares available counterevidence without refs",
                    )
                )
            if counter_status in {"missing", "not_applicable"} and counter_refs:
                findings.append(
                    _finding(
                        "COUNTEREVIDENCE_STATUS_INVALID",
                        f"{finding_id} counterevidence status conflicts with refs",
                    )
                )
            if item.get("confidence") == "high" and counter_status != "available":
                uncertainty = str(item.get("uncertainty") or "").casefold()
                if not any(
                    marker in uncertainty
                    for marker in (
                        "counterevidence",
                        "missing",
                        "unavailable",
                        "not supplied",
                        "反证",
                        "缺失",
                        "未提供",
                        "不可用",
                    )
                ):
                    findings.append(
                        _finding(
                            "COUNTEREVIDENCE_MISSING_EXPLANATION_REQUIRED",
                            f"{finding_id} high confidence must explain absent counterevidence",
                        )
                    )
            if item.get("perspective") == "decision_time":
                leaked = [
                    ref
                    for ref in [*refs, *counter_refs]
                    if ref in fact_index
                    and fact_index[ref].get("temporal_role")
                    not in {"known_at_decision", "not_applicable"}
                ]
                if leaked:
                    findings.append(
                        _finding(
                            "INTERPRETATION_TEMPORAL_LEAKAGE",
                            f"{finding_id} consumes post-decision facts",
                        )
                    )

    options = sections.get("counterfactual_options")
    if isinstance(options, list):
        mapping_options = [item for item in options if isinstance(item, Mapping)]
        if mapping_options != sorted(
            mapping_options, key=lambda item: str(item.get("option_id") or "")
        ):
            findings.append(
                _finding(
                    "INTERPRETATION_ORDER_INVALID",
                    "counterfactual_options are not sorted by option_id",
                )
            )
        for item in mapping_options:
            option_id = str(item.get("option_id") or "")
            if (
                not _OPTION_ID_RE.fullmatch(option_id)
                or option_id != _option_id(item)
            ):
                findings.append(
                    _finding(
                        "INTERPRETATION_ID_MISMATCH",
                        f"{option_id or 'counterfactual'} is not content-derived",
                    )
                )
            if option_id in all_ids:
                findings.append(_finding("DUPLICATE_INTERPRETATION_ID", option_id))
            all_ids.add(option_id)
            refs = item.get("fact_refs") if isinstance(item.get("fact_refs"), list) else []
            if refs != sorted(set(refs)) or not refs or set(refs) - set(fact_index):
                findings.append(
                    _finding(
                        "COUNTERFACTUAL_FACT_REF_INVALID",
                        f"{option_id} needs valid sorted fact refs",
                    )
                )
            allowed_roles = (
                {"known_at_decision", "not_applicable"}
                if item.get("temporal_scope") == "decision_time"
                else {
                    "known_at_decision",
                    "learned_during_episode",
                    "not_applicable",
                }
            )
            if any(
                ref in fact_index
                and fact_index[ref].get("temporal_role") not in allowed_roles
                for ref in refs
            ):
                findings.append(
                    _finding(
                        "COUNTERFACTUAL_TEMPORAL_LEAKAGE",
                        f"{option_id} uses information unavailable in its temporal scope",
                    )
                )

    for code in sorted(_policy_codes(sections)):
        findings.append(_finding(code, "interpretation text violates the P2F policy gate"))

    model_generation = governance.get("model_generation")
    if not isinstance(model_generation, Mapping):
        findings.append(
            _finding("MODEL_PROVENANCE_INVALID", "model_generation must be an object")
        )
        return findings
    try:
        base = facts_only_projection(artifact)
        prompt = build_interpretation_prompt(base)
        expected_prompt_hash = _text_content_id(prompt)
    except (ArtifactIOError, InterpretationError, EpisodeReviewError):
        findings.append(
            _finding("MODEL_PROVENANCE_INVALID", "facts prompt cannot be reconstructed")
        )
        return findings
    if model_generation.get("input_content_id") != base.get("content_id"):
        findings.append(
            _finding(
                "MODEL_INPUT_BINDING_MISMATCH",
                "model input_content_id does not bind the facts-only artifact",
            )
        )
    if model_generation.get("prompt_template_id") != PROMPT_TEMPLATE_ID:
        findings.append(
            _finding("MODEL_PROMPT_TEMPLATE_INVALID", "unexpected prompt template")
        )
    if model_generation.get("prompt_hash") != expected_prompt_hash:
        findings.append(
            _finding("MODEL_PROMPT_HASH_MISMATCH", "prompt hash is not reproducible")
        )
    if model_generation.get("interpretation_engine_version") != INTERPRETATION_ENGINE_VERSION:
        findings.append(
            _finding("INTERPRETATION_ENGINE_INVALID", "unexpected interpretation engine")
        )
    if model_generation.get("interpretation_content_id") != _value_content_id(sections):
        findings.append(
            _finding(
                "INTERPRETATION_CONTENT_ID_MISMATCH",
                "interpretation content ID is not canonical",
            )
        )
    try:
        generated_at = _canonical_timestamp(
            model_generation.get("generated_at"), "model_generation.generated_at"
        )
    except InterpretationError:
        findings.append(
            _finding("MODEL_GENERATED_AT_INVALID", "generated_at is not canonical")
        )
    else:
        if generated_at != model_generation.get("generated_at"):
            findings.append(
                _finding("MODEL_GENERATED_AT_INVALID", "generated_at is not canonical")
            )
    try:
        canonical_json_bytes(model_generation.get("parameters"))
    except ArtifactIOError:
        findings.append(
            _finding("MODEL_PARAMETERS_INVALID", "parameters are not canonical JSON")
        )
    return findings


def _attempt_receipt(
    *,
    facts_artifact: Mapping[str, Any],
    model_id: str,
    prompt_hash: str,
    parameters: Mapping[str, Any],
    attempted_at: str,
    status: str,
    output_hash: str | None,
    result_review_content_id: str,
    error_code: str | None,
    error_message: str | None,
    failure_codes: Sequence[str],
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "content_id": "",
        "attempt_id": "",
        "review_id": str(facts_artifact.get("review_id") or ""),
        "facts_content_id": str(facts_artifact.get("content_id") or ""),
        "status": status,
        "error_code": error_code,
        "error_message": error_message,
        "failure_codes": sorted(set(str(code) for code in failure_codes)),
        "provenance": {
            "model_id": model_id,
            "prompt_template_id": PROMPT_TEMPLATE_ID,
            "prompt_hash": prompt_hash,
            "input_content_id": str(facts_artifact.get("content_id") or ""),
            "output_hash": output_hash,
            "parameters": deepcopy(dict(parameters)),
            "attempted_at": attempted_at,
        },
        "result_review_content_id": result_review_content_id,
    }
    attempt_material = deepcopy(receipt)
    attempt_material.pop("content_id", None)
    attempt_material.pop("attempt_id", None)
    receipt["attempt_id"] = _stable_id("attempt", attempt_material)
    receipt["content_id"] = _content_id(receipt)
    return receipt


def build_model_assisted_episode_review(
    facts_artifact: Mapping[str, Any],
    *,
    provider: InterpretationProvider,
    attempted_at: str,
    parameters: Mapping[str, Any] | None = None,
) -> InterpretationBuildResult:
    """Add a bounded interpretation or return an exact facts-only fallback."""

    base = deepcopy(dict(facts_artifact))
    base_bytes = canonical_json_bytes(base)
    validation = validate_episode_review(base)
    governance = base.get("governance")
    if validation.get("validation_status") == "blocked" or not isinstance(
        governance, Mapping
    ):
        raise InterpretationError("facts artifact must pass P2F validation")
    if governance.get("generation_mode") != "facts_only":
        raise InterpretationError("interpretation input must be a facts-only artifact")
    model_id = str(getattr(provider, "model_id", "") or "").strip()
    if not model_id:
        raise InterpretationError("provider.model_id is required")
    canonical_attempted_at = _canonical_timestamp(attempted_at, "attempted_at")
    if canonical_attempted_at != attempted_at:
        raise InterpretationError("attempted_at must be canonical UTC seconds")
    parameter_values = deepcopy(dict(parameters or {}))
    try:
        canonical_json_bytes(parameter_values)
    except ArtifactIOError as exc:
        raise InterpretationError("parameters must be canonical JSON without floats") from exc
    prompt = build_interpretation_prompt(base)
    prompt_hash = _text_content_id(prompt)

    try:
        raw_text = provider.generate(
            prompt=prompt,
            parameters=deepcopy(parameter_values),
        )
        if not isinstance(raw_text, str):
            raise TypeError("provider response must be text")
    except Exception:
        receipt = _attempt_receipt(
            facts_artifact=base,
            model_id=model_id,
            prompt_hash=prompt_hash,
            parameters=parameter_values,
            attempted_at=canonical_attempted_at,
            status="fallback_facts_only",
            output_hash=None,
            result_review_content_id=str(base.get("content_id") or ""),
            error_code="MODEL_PROVIDER_UNAVAILABLE",
            error_message=(
                "interpretation provider was unavailable; facts-only artifact preserved"
            ),
            failure_codes=["MODEL_PROVIDER_UNAVAILABLE"],
        )
        assert canonical_json_bytes(base) == base_bytes
        return InterpretationBuildResult(base, receipt, True)

    output_hash = _text_content_id(raw_text)
    try:
        normalized = _normalize_provider_output(raw_text)
        candidate = deepcopy(base)
        candidate["interpretation_sections"] = normalized
        candidate_governance = deepcopy(dict(governance))
        candidate_governance["generation_mode"] = "model_assisted"
        candidate_governance["model_generation"] = {
            "model_id": model_id,
            "prompt_template_id": PROMPT_TEMPLATE_ID,
            "prompt_hash": prompt_hash,
            "input_content_id": str(base.get("content_id") or ""),
            "output_hash": output_hash,
            "interpretation_engine_version": INTERPRETATION_ENGINE_VERSION,
            "interpretation_content_id": _value_content_id(normalized),
            "parameters": parameter_values,
            "generated_at": canonical_attempted_at,
        }
        candidate_governance["human_reviews"] = []
        candidate["governance"] = candidate_governance
        candidate["content_id"] = _content_id(candidate)
        candidate_validation = validate_episode_review(candidate)
        if candidate_validation.get("validation_status") == "blocked":
            raise InterpretationOutputError(
                [
                    str(item.get("code") or "MODEL_OUTPUT_INVALID")
                    for item in candidate_validation.get("findings", [])
                    if isinstance(item, Mapping)
                ]
            )
    except InterpretationOutputError as exc:
        receipt = _attempt_receipt(
            facts_artifact=base,
            model_id=model_id,
            prompt_hash=prompt_hash,
            parameters=parameter_values,
            attempted_at=canonical_attempted_at,
            status="fallback_facts_only",
            output_hash=output_hash,
            result_review_content_id=str(base.get("content_id") or ""),
            error_code="MODEL_OUTPUT_INVALID",
            error_message=(
                "interpretation output failed validation; facts-only artifact preserved"
            ),
            failure_codes=exc.codes,
        )
        assert canonical_json_bytes(base) == base_bytes
        return InterpretationBuildResult(base, receipt, True)

    receipt = _attempt_receipt(
        facts_artifact=base,
        model_id=model_id,
        prompt_hash=prompt_hash,
        parameters=parameter_values,
        attempted_at=canonical_attempted_at,
        status="succeeded",
        output_hash=output_hash,
        result_review_content_id=str(candidate.get("content_id") or ""),
        error_code=None,
        error_message=None,
        failure_codes=[],
    )
    return InterpretationBuildResult(candidate, receipt, False)


def validate_interpretation_attempt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(receipt, Mapping):
        return {
            "schema_version": ATTEMPT_VALIDATION_SCHEMA_VERSION,
            "validation_status": "blocked",
            "findings": [
                _finding("MALFORMED_INTERPRETATION_ATTEMPT", "attempt must be an object")
            ],
        }
    findings: list[dict[str, str]] = []
    required = {
        "schema_version",
        "content_id",
        "attempt_id",
        "review_id",
        "facts_content_id",
        "status",
        "error_code",
        "error_message",
        "failure_codes",
        "provenance",
        "result_review_content_id",
    }
    if set(receipt) != required:
        findings.append(_finding("ATTEMPT_SHAPE_INVALID", "attempt keys are not closed"))
    if receipt.get("schema_version") != ATTEMPT_SCHEMA_VERSION:
        findings.append(_finding("ATTEMPT_SCHEMA_INVALID", "unsupported attempt schema"))
    try:
        expected_content_id = _content_id(receipt)
    except (ArtifactIOError, TypeError, ValueError):
        expected_content_id = ""
    if not _CONTENT_ID_RE.fullmatch(
        str(receipt.get("content_id") or "")
    ) or receipt.get("content_id") != expected_content_id:
        findings.append(_finding("ATTEMPT_CONTENT_ID_MISMATCH", "invalid content ID"))
    attempt_id = str(receipt.get("attempt_id") or "")
    material = deepcopy(dict(receipt))
    material.pop("content_id", None)
    material.pop("attempt_id", None)
    try:
        expected_attempt_id = _stable_id("attempt", material)
    except (ArtifactIOError, TypeError, ValueError):
        expected_attempt_id = ""
    if not _ATTEMPT_ID_RE.fullmatch(attempt_id) or attempt_id != expected_attempt_id:
        findings.append(_finding("ATTEMPT_ID_MISMATCH", "invalid attempt ID"))
    status = receipt.get("status")
    if status not in {"succeeded", "fallback_facts_only"}:
        findings.append(_finding("ATTEMPT_STATUS_INVALID", "unsupported attempt status"))
    facts_content_id = str(receipt.get("facts_content_id") or "")
    result_content_id = str(receipt.get("result_review_content_id") or "")
    if not _CONTENT_ID_RE.fullmatch(facts_content_id) or not _CONTENT_ID_RE.fullmatch(
        result_content_id
    ):
        findings.append(_finding("ATTEMPT_BINDING_INVALID", "invalid review binding"))
    provenance = receipt.get("provenance")
    if not isinstance(provenance, Mapping) or set(provenance) != {
        "model_id",
        "prompt_template_id",
        "prompt_hash",
        "input_content_id",
        "output_hash",
        "parameters",
        "attempted_at",
    }:
        findings.append(_finding("ATTEMPT_PROVENANCE_INVALID", "invalid provenance"))
        provenance = {}
    if provenance.get("input_content_id") != facts_content_id:
        findings.append(_finding("ATTEMPT_BINDING_INVALID", "input binding mismatch"))
    for key in ("prompt_hash",):
        if not _CONTENT_ID_RE.fullmatch(str(provenance.get(key) or "")):
            findings.append(_finding("ATTEMPT_PROVENANCE_INVALID", f"invalid {key}"))
    output_hash = provenance.get("output_hash")
    if output_hash is not None and not _CONTENT_ID_RE.fullmatch(str(output_hash)):
        findings.append(_finding("ATTEMPT_PROVENANCE_INVALID", "invalid output_hash"))
    try:
        attempted_at = _canonical_timestamp(provenance.get("attempted_at"), "attempted_at")
    except InterpretationError:
        findings.append(_finding("ATTEMPT_PROVENANCE_INVALID", "invalid attempted_at"))
    else:
        if attempted_at != provenance.get("attempted_at"):
            findings.append(_finding("ATTEMPT_PROVENANCE_INVALID", "non-canonical attempted_at"))
    try:
        canonical_json_bytes(provenance.get("parameters"))
    except ArtifactIOError:
        findings.append(
            _finding("ATTEMPT_PROVENANCE_INVALID", "parameters are not canonical JSON")
        )
    failure_codes = receipt.get("failure_codes")
    if (
        not isinstance(failure_codes, list)
        or any(not isinstance(code, str) or not code for code in failure_codes)
        or failure_codes != sorted(set(failure_codes))
    ):
        findings.append(_finding("ATTEMPT_FAILURE_CODES_INVALID", "invalid failure codes"))
    if status == "succeeded":
        if (
            output_hash is None
            or receipt.get("error_code") is not None
            or receipt.get("error_message") is not None
            or failure_codes != []
            or result_content_id == facts_content_id
        ):
            findings.append(_finding("ATTEMPT_SUCCESS_INVALID", "invalid success receipt"))
    elif status == "fallback_facts_only":
        if (
            not receipt.get("error_code")
            or not receipt.get("error_message")
            or not failure_codes
            or result_content_id != facts_content_id
        ):
            findings.append(_finding("ATTEMPT_FALLBACK_INVALID", "invalid fallback receipt"))
    values = sorted(findings, key=lambda item: (item["code"], item["message"]))
    return {
        "schema_version": ATTEMPT_VALIDATION_SCHEMA_VERSION,
        "validation_status": "blocked" if values else "accepted",
        "findings": values,
    }


def replay_validate_interpretation_attempt(
    receipt: Mapping[str, Any], *, raw_output: str | None
) -> dict[str, Any]:
    result = validate_interpretation_attempt(receipt)
    findings = list(result["findings"])
    provenance = receipt.get("provenance")
    expected = (
        provenance.get("output_hash") if isinstance(provenance, Mapping) else None
    )
    actual = _text_content_id(raw_output) if raw_output is not None else None
    if expected != actual:
        findings.append(
            _finding("MODEL_OUTPUT_HASH_MISMATCH", "raw output does not match receipt")
        )
    findings.sort(key=lambda item: (item["code"], item["message"]))
    return {
        "schema_version": ATTEMPT_VALIDATION_SCHEMA_VERSION,
        "validation_status": "blocked" if findings else "accepted",
        "findings": findings,
        "output_verification": {
            "status": "verified" if not findings else "blocked",
            "expected_output_hash": expected,
            "actual_output_hash": actual,
        },
    }


def save_interpretation_attempt(
    path: str | Path, receipt: Mapping[str, Any]
) -> Path:
    if validate_interpretation_attempt(receipt)["validation_status"] == "blocked":
        raise InterpretationError("refusing to save an invalid interpretation attempt")
    return atomic_write_bytes(path, pretty_json_bytes(receipt))


__all__ = [
    "ATTEMPT_SCHEMA_VERSION",
    "INTERPRETATION_ENGINE_VERSION",
    "OUTPUT_SCHEMA_VERSION",
    "PROMPT_TEMPLATE_ID",
    "InterpretationBuildResult",
    "InterpretationError",
    "InterpretationOutputError",
    "InterpretationProvider",
    "RecordedResponseProvider",
    "UnavailableInterpretationProvider",
    "build_interpretation_prompt",
    "build_model_assisted_episode_review",
    "facts_only_projection",
    "interpretation_layer_findings",
    "replay_validate_interpretation_attempt",
    "save_interpretation_attempt",
    "validate_interpretation_attempt",
]
