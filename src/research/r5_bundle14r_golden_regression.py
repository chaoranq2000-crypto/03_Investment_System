"""Bundle 14R cross-industry golden regression contracts and runner primitives.

This module deliberately separates three ideas that were conflated in older
research-report regressions:

1. A case *contract* can be structurally valid.
2. A case can still be waiting for reviewed official evidence.
3. No automated regression is allowed to grant sample-quality or P2 status.

The fixtures that accompany this module contain research questions and economic
model contracts only.  Narrative samples may be used to define dimensions and
expected analytical density, but never as factual evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    import yaml
except ImportError as exc:  # pragma: no cover - repository environments install PyYAML
    raise RuntimeError("PyYAML is required for Bundle 14R case contracts") from exc


BUNDLE_ID = "R5_BUNDLE_14R"
CASE_SCHEMA_VERSION = "r5_bundle14r_case_v1"
SUITE_SCHEMA_VERSION = "r5_bundle14r_suite_v1"
GENERATION_LOCK_SCHEMA_VERSION = "r5_bundle14r_generation_lock_v1"

ALLOWED_FALLBACK_POLICIES = {
    "block",
    "bounded_estimate",
    "context_only",
    "not_applicable",
}
ALLOWED_EXPECTED_STATUSES = {
    "evidence_qualification_pending",
    "candidate_pending",
    "candidate_ready_for_exact_hash_review",
}
ALLOWED_VALUATION_ELIGIBILITY = {"conditional", "disabled"}
ALLOWED_BACKFLOW_STAGES = {
    "T1_evidence_plan",
    "T2_evidence_acquire_parse",
    "T5_analysis_pack_build",
    "T6_forecast_valuation_model",
    "T8_report_draft",
    "T9_quality_review",
}
REQUIRED_BACKFLOW_CLASSES = {
    "EVIDENCE_MISSING",
    "DRIVER_UNQUALIFIED",
    "OVERLAP_UNRESOLVED",
    "VALUATION_INELIGIBLE",
    "SEMANTIC_QUALITY_FAILED",
}
REQUIRED_EXPECTED_ARTIFACT_ROLES = {
    "reviewed_evidence_pack",
    "operating_driver_model",
    "forecast_valuation_model",
    "reader_report",
    "semantic_quality_report",
    "generation_lock",
    "exact_hash_human_review",
}


class ContractViolation(ValueError):
    """Raised when a golden-regression case violates a hard contract."""


@dataclass(frozen=True)
class ContractIssue:
    code: str
    message: str
    path: str
    severity: str = "blocker"


@dataclass(frozen=True)
class BackflowItem:
    issue_code: str
    stage: str
    skill: str
    reason: str
    case_id: str
    owner: str = "workflow_orchestrator"


@dataclass(frozen=True)
class CaseContractResult:
    case_id: str
    issuer_label: str
    source_path: str
    contract_valid: bool
    expected_status: str
    required_driver_count: int
    required_question_count: int
    archetype_count: int
    report_emphasis_top3_weight: float
    release_authority: bool
    sample_quality_allowed: bool
    p2_allowed: bool
    workflow_state_mutation_allowed: bool
    issues: tuple[ContractIssue, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class QualificationResult:
    case_id: str
    status: str
    research_ready: bool
    candidate_ready_for_exact_hash_review: bool
    qualified_driver_count: int
    required_driver_count: int
    reviewed_official_source_count: int
    forecast_bridge_complete: bool
    semantic_gate_passed: bool
    deterministic_rerun: bool
    exact_hash_human_review_status: str
    backflow_items: tuple[BackflowItem, ...]
    sample_quality_allowed: bool = False
    p2_allowed: bool = False


@dataclass(frozen=True)
class CoreGeneralityResult:
    passed: bool
    scanned_paths: tuple[str, ...]
    violations: tuple[str, ...]


@dataclass(frozen=True)
class SuiteResult:
    schema_version: str
    bundle_id: str
    case_results: tuple[CaseContractResult, ...]
    qualification_results: tuple[QualificationResult, ...]
    core_generality: CoreGeneralityResult
    contract_passed: bool
    research_ready_case_count: int
    candidate_ready_case_count: int
    release_authority: bool
    sample_quality_allowed: bool
    p2_allowed: bool
    workflow_state_mutation_allowed: bool


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    file_path = Path(path)
    digest = sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _logical_path(path: str | Path, path_root: str | Path | None = None) -> str:
    file_path = Path(path)
    if path_root is not None:
        root = Path(path_root).resolve()
        try:
            return file_path.resolve().relative_to(root).as_posix()
        except ValueError:
            pass
    if not file_path.is_absolute():
        return file_path.as_posix()
    return file_path.name


def load_yaml_document(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ContractViolation(f"{source}: root must be a mapping")
    return data


def discover_case_paths(cases_dir: str | Path) -> tuple[Path, ...]:
    directory = Path(cases_dir)
    if not directory.exists():
        raise FileNotFoundError(f"case directory does not exist: {directory}")
    paths = sorted(
        p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in {".yaml", ".yml"}
    )
    if not paths:
        raise ContractViolation(f"no case YAML files found in {directory}")
    return tuple(paths)


def _mapping(value: Any, path: str, issues: list[ContractIssue]) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    issues.append(ContractIssue("TYPE_MAPPING_REQUIRED", "expected a mapping", path))
    return {}


def _sequence(value: Any, path: str, issues: list[ContractIssue]) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    issues.append(ContractIssue("TYPE_SEQUENCE_REQUIRED", "expected a sequence", path))
    return ()


def _non_empty_string(value: Any, path: str, issues: list[ContractIssue]) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    issues.append(ContractIssue("STRING_REQUIRED", "expected a non-empty string", path))
    return ""


def _false_flag(value: Any, path: str, issues: list[ContractIssue]) -> bool:
    if value is False:
        return False
    issues.append(
        ContractIssue(
            "AUTOMATED_RELEASE_FORBIDDEN",
            "automated release/status mutation must be explicitly false",
            path,
        )
    )
    return bool(value)


def _unique_strings(values: Iterable[Any], path: str, issues: list[ContractIssue]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        text = _non_empty_string(value, f"{path}[{index}]", issues)
        if not text:
            continue
        if text in seen:
            issues.append(
                ContractIssue("DUPLICATE_IDENTIFIER", f"duplicate value: {text}", f"{path}[{index}]")
            )
            continue
        seen.add(text)
        result.append(text)
    return tuple(result)


def validate_case_document(
    document: Mapping[str, Any], *, source_path: str | Path = "<memory>"
) -> CaseContractResult:
    """Validate a single golden-regression case contract.

    The function validates research design, not factual completeness.  Missing
    reviewed evidence is handled later by :func:`evaluate_qualification` and is
    expected for a newly seeded case.
    """

    issues: list[ContractIssue] = []
    source = str(source_path)

    schema_version = _non_empty_string(document.get("schema_version"), "schema_version", issues)
    if schema_version and schema_version != CASE_SCHEMA_VERSION:
        issues.append(
            ContractIssue(
                "SCHEMA_VERSION_MISMATCH",
                f"expected {CASE_SCHEMA_VERSION}, got {schema_version}",
                "schema_version",
            )
        )

    case_id = _non_empty_string(document.get("case_id"), "case_id", issues)
    issuer = _mapping(document.get("issuer"), "issuer", issues)
    issuer_name = _non_empty_string(issuer.get("name"), "issuer.name", issues)
    issuer_ticker = _non_empty_string(issuer.get("ticker"), "issuer.ticker", issues)
    issuer_label = " / ".join(part for part in (issuer_name, issuer_ticker) if part)

    benchmark_policy = _mapping(document.get("benchmark_policy"), "benchmark_policy", issues)
    if benchmark_policy.get("sample_reports_role") != "narrative_dimensions_only":
        issues.append(
            ContractIssue(
                "SAMPLE_ROLE_INVALID",
                "sample reports may define narrative dimensions only",
                "benchmark_policy.sample_reports_role",
            )
        )
    if benchmark_policy.get("sample_text_as_evidence") != "prohibited":
        issues.append(
            ContractIssue(
                "SAMPLE_EVIDENCE_PROMOTION_FORBIDDEN",
                "sample text must be prohibited as factual evidence",
                "benchmark_policy.sample_text_as_evidence",
            )
        )
    if benchmark_policy.get("official_evidence_role") != "required":
        issues.append(
            ContractIssue(
                "OFFICIAL_EVIDENCE_NOT_REQUIRED",
                "reviewed official evidence must be required",
                "benchmark_policy.official_evidence_role",
            )
        )

    release_policy = _mapping(document.get("release_policy"), "release_policy", issues)
    auto_sample = _false_flag(
        release_policy.get("automated_sample_quality_allowed"),
        "release_policy.automated_sample_quality_allowed",
        issues,
    )
    auto_p2 = _false_flag(
        release_policy.get("automated_p2_allowed"),
        "release_policy.automated_p2_allowed",
        issues,
    )
    workflow_mutation = _false_flag(
        release_policy.get("workflow_state_mutation_allowed"),
        "release_policy.workflow_state_mutation_allowed",
        issues,
    )
    if release_policy.get("exact_hash_human_review_required") is not True:
        issues.append(
            ContractIssue(
                "EXACT_HASH_REVIEW_REQUIRED",
                "exact-hash human review must be required",
                "release_policy.exact_hash_human_review_required",
            )
        )

    source_classes = _unique_strings(
        _sequence(document.get("required_source_classes"), "required_source_classes", issues),
        "required_source_classes",
        issues,
    )
    if len(source_classes) < 3:
        issues.append(
            ContractIssue(
                "SOURCE_CLASS_COVERAGE_LOW",
                "at least three independent source classes are required",
                "required_source_classes",
            )
        )
    if not any("issuer" in item or "exchange" in item for item in source_classes):
        issues.append(
            ContractIssue(
                "ISSUER_OFFICIAL_SOURCE_MISSING",
                "an issuer/exchange official source class is required",
                "required_source_classes",
            )
        )

    driver_items = _sequence(document.get("drivers"), "drivers", issues)
    driver_ids: list[str] = []
    driver_fallbacks: dict[str, str] = {}
    for index, raw_driver in enumerate(driver_items):
        path = f"drivers[{index}]"
        driver = _mapping(raw_driver, path, issues)
        driver_id = _non_empty_string(driver.get("driver_id"), f"{path}.driver_id", issues)
        _non_empty_string(driver.get("label"), f"{path}.label", issues)
        _non_empty_string(driver.get("unit"), f"{path}.unit", issues)
        _non_empty_string(driver.get("period_rule"), f"{path}.period_rule", issues)
        evidence_requirements = _sequence(
            driver.get("evidence_requirements"), f"{path}.evidence_requirements", issues
        )
        if not evidence_requirements:
            issues.append(
                ContractIssue(
                    "DRIVER_EVIDENCE_REQUIREMENT_MISSING",
                    "each driver needs at least one official evidence requirement",
                    f"{path}.evidence_requirements",
                )
            )
        model_mapping = _unique_strings(
            _sequence(driver.get("model_mapping"), f"{path}.model_mapping", issues),
            f"{path}.model_mapping",
            issues,
        )
        if not model_mapping:
            issues.append(
                ContractIssue(
                    "DRIVER_MODEL_MAPPING_MISSING",
                    "each driver must map to one or more financial/model outputs",
                    f"{path}.model_mapping",
                )
            )
        fallback = _non_empty_string(driver.get("fallback_policy"), f"{path}.fallback_policy", issues)
        if fallback and fallback not in ALLOWED_FALLBACK_POLICIES:
            issues.append(
                ContractIssue(
                    "DRIVER_FALLBACK_INVALID",
                    f"unsupported fallback policy: {fallback}",
                    f"{path}.fallback_policy",
                )
            )
        route = _mapping(driver.get("backflow_route"), f"{path}.backflow_route", issues)
        stage = _non_empty_string(route.get("stage"), f"{path}.backflow_route.stage", issues)
        _non_empty_string(route.get("skill"), f"{path}.backflow_route.skill", issues)
        if stage and stage not in ALLOWED_BACKFLOW_STAGES:
            issues.append(
                ContractIssue(
                    "BACKFLOW_STAGE_INVALID",
                    f"unsupported backflow stage: {stage}",
                    f"{path}.backflow_route.stage",
                )
            )
        if driver_id:
            if driver_id in driver_ids:
                issues.append(
                    ContractIssue(
                        "DUPLICATE_DRIVER_ID",
                        f"duplicate driver_id: {driver_id}",
                        f"{path}.driver_id",
                    )
                )
            driver_ids.append(driver_id)
            driver_fallbacks[driver_id] = fallback

    archetype_items = _sequence(
        document.get("economic_archetypes"), "economic_archetypes", issues
    )
    referenced_driver_ids: set[str] = set()
    archetype_ids: set[str] = set()
    for index, raw_archetype in enumerate(archetype_items):
        path = f"economic_archetypes[{index}]"
        archetype = _mapping(raw_archetype, path, issues)
        archetype_id = _non_empty_string(
            archetype.get("archetype_id"), f"{path}.archetype_id", issues
        )
        _non_empty_string(archetype.get("formula"), f"{path}.formula", issues)
        segments = _unique_strings(
            _sequence(archetype.get("segment_ids"), f"{path}.segment_ids", issues),
            f"{path}.segment_ids",
            issues,
        )
        required = _unique_strings(
            _sequence(archetype.get("required_driver_ids"), f"{path}.required_driver_ids", issues),
            f"{path}.required_driver_ids",
            issues,
        )
        if not segments:
            issues.append(
                ContractIssue(
                    "ARCHETYPE_SEGMENT_MISSING",
                    "each archetype must name at least one segment",
                    f"{path}.segment_ids",
                )
            )
        if not required:
            issues.append(
                ContractIssue(
                    "ARCHETYPE_DRIVER_MISSING",
                    "each archetype must bind required drivers",
                    f"{path}.required_driver_ids",
                )
            )
        referenced_driver_ids.update(required)
        if archetype_id:
            if archetype_id in archetype_ids:
                issues.append(
                    ContractIssue(
                        "DUPLICATE_ARCHETYPE_ID",
                        f"duplicate archetype_id: {archetype_id}",
                        f"{path}.archetype_id",
                    )
                )
            archetype_ids.add(archetype_id)

    if not archetype_items:
        issues.append(
            ContractIssue(
                "ECONOMIC_ARCHETYPE_MISSING",
                "at least one segment-level economic archetype is required",
                "economic_archetypes",
            )
        )

    unknown_references = sorted(referenced_driver_ids.difference(driver_ids))
    if unknown_references:
        issues.append(
            ContractIssue(
                "ARCHETYPE_REFERENCES_UNKNOWN_DRIVER",
                f"unknown driver ids: {', '.join(unknown_references)}",
                "economic_archetypes",
            )
        )
    unreferenced_drivers = sorted(set(driver_ids).difference(referenced_driver_ids))
    if unreferenced_drivers:
        issues.append(
            ContractIssue(
                "UNREFERENCED_DRIVER",
                f"drivers not bound to an archetype: {', '.join(unreferenced_drivers)}",
                "drivers",
                severity="warning",
            )
        )

    question_items = _sequence(document.get("research_questions"), "research_questions", issues)
    question_ids: set[str] = set()
    for index, raw_question in enumerate(question_items):
        path = f"research_questions[{index}]"
        question = _mapping(raw_question, path, issues)
        question_id = _non_empty_string(question.get("question_id"), f"{path}.question_id", issues)
        _non_empty_string(question.get("question"), f"{path}.question", issues)
        linked = _unique_strings(
            _sequence(question.get("driver_ids"), f"{path}.driver_ids", issues),
            f"{path}.driver_ids",
            issues,
        )
        if not linked:
            issues.append(
                ContractIssue(
                    "QUESTION_DRIVER_LINK_MISSING",
                    "each research question must link to an operating driver",
                    f"{path}.driver_ids",
                )
            )
        unknown = sorted(set(linked).difference(driver_ids))
        if unknown:
            issues.append(
                ContractIssue(
                    "QUESTION_REFERENCES_UNKNOWN_DRIVER",
                    f"unknown driver ids: {', '.join(unknown)}",
                    f"{path}.driver_ids",
                )
            )
        resolution_policy = _non_empty_string(
            question.get("resolution_policy"), f"{path}.resolution_policy", issues
        )
        if resolution_policy and resolution_policy not in {
            "official_fact",
            "bounded_estimate_or_block",
            "context_only_or_block",
        }:
            issues.append(
                ContractIssue(
                    "QUESTION_RESOLUTION_POLICY_INVALID",
                    f"unsupported resolution policy: {resolution_policy}",
                    f"{path}.resolution_policy",
                )
            )
        if question_id:
            if question_id in question_ids:
                issues.append(
                    ContractIssue(
                        "DUPLICATE_QUESTION_ID",
                        f"duplicate question_id: {question_id}",
                        f"{path}.question_id",
                    )
                )
            question_ids.add(question_id)

    if len(question_items) < max(3, len(archetype_items)):
        issues.append(
            ContractIssue(
                "RESEARCH_QUESTION_COVERAGE_LOW",
                "research questions must cover every major economic archetype",
                "research_questions",
            )
        )

    forecast_contract = _mapping(document.get("forecast_contract"), "forecast_contract", issues)
    horizons = _sequence(forecast_contract.get("horizon_years"), "forecast_contract.horizon_years", issues)
    if len(horizons) < 3:
        issues.append(
            ContractIssue(
                "FORECAST_HORIZON_TOO_SHORT",
                "at least three forecast years are required",
                "forecast_contract.horizon_years",
            )
        )
    for field_name in (
        "minimum_segment_revenue_coverage",
        "minimum_segment_gross_profit_coverage",
    ):
        value = forecast_contract.get(field_name)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 <= float(value) <= 1.0:
            issues.append(
                ContractIssue(
                    "FORECAST_COVERAGE_INVALID",
                    "coverage must be a number between zero and one",
                    f"forecast_contract.{field_name}",
                )
            )
        elif float(value) < 0.8:
            issues.append(
                ContractIssue(
                    "FORECAST_COVERAGE_BELOW_FLOOR",
                    "golden regressions require at least 80% segment coverage",
                    f"forecast_contract.{field_name}",
                )
            )
    for field_name in (
        "requires_cash_flow_bridge",
        "requires_working_capital_bridge",
        "requires_driver_to_statement_reconciliation",
    ):
        if forecast_contract.get(field_name) is not True:
            issues.append(
                ContractIssue(
                    "FORECAST_BRIDGE_REQUIRED",
                    f"{field_name} must be true",
                    f"forecast_contract.{field_name}",
                )
            )

    valuation_items = _sequence(document.get("valuation_methods"), "valuation_methods", issues)
    if not valuation_items:
        issues.append(
            ContractIssue(
                "VALUATION_METHODS_MISSING",
                "at least one conditionally gated valuation method is required",
                "valuation_methods",
            )
        )
    for index, raw_method in enumerate(valuation_items):
        path = f"valuation_methods[{index}]"
        method = _mapping(raw_method, path, issues)
        _non_empty_string(method.get("method"), f"{path}.method", issues)
        eligibility = _non_empty_string(method.get("eligibility"), f"{path}.eligibility", issues)
        _non_empty_string(method.get("gate"), f"{path}.gate", issues)
        if eligibility and eligibility not in ALLOWED_VALUATION_ELIGIBILITY:
            issues.append(
                ContractIssue(
                    "VALUATION_AUTO_ELIGIBILITY_FORBIDDEN",
                    "valuation methods must be conditional or disabled",
                    f"{path}.eligibility",
                )
            )
        if method.get("automatically_eligible") is not False:
            issues.append(
                ContractIssue(
                    "VALUATION_AUTO_ELIGIBILITY_FORBIDDEN",
                    "automatically_eligible must be false",
                    f"{path}.automatically_eligible",
                )
            )

    emphasis_items = _sequence(document.get("report_emphasis"), "report_emphasis", issues)
    weights: list[float] = []
    topic_ids: set[str] = set()
    for index, raw_topic in enumerate(emphasis_items):
        path = f"report_emphasis[{index}]"
        topic = _mapping(raw_topic, path, issues)
        topic_id = _non_empty_string(topic.get("topic_id"), f"{path}.topic_id", issues)
        _non_empty_string(topic.get("reason"), f"{path}.reason", issues)
        weight = topic.get("weight")
        if not isinstance(weight, (int, float)) or isinstance(weight, bool) or float(weight) <= 0:
            issues.append(
                ContractIssue(
                    "REPORT_EMPHASIS_WEIGHT_INVALID",
                    "weight must be a positive number",
                    f"{path}.weight",
                )
            )
        else:
            weights.append(float(weight))
        if topic_id:
            if topic_id in topic_ids:
                issues.append(
                    ContractIssue(
                        "DUPLICATE_REPORT_TOPIC",
                        f"duplicate report topic: {topic_id}",
                        f"{path}.topic_id",
                    )
                )
            topic_ids.add(topic_id)
    total_weight = sum(weights)
    if not weights:
        issues.append(
            ContractIssue(
                "REPORT_EMPHASIS_MISSING",
                "report emphasis weights are required",
                "report_emphasis",
            )
        )
    elif abs(total_weight - 1.0) > 1e-6:
        issues.append(
            ContractIssue(
                "REPORT_EMPHASIS_NOT_NORMALISED",
                f"weights must sum to 1.0, got {total_weight:.6f}",
                "report_emphasis",
            )
        )
    top3_weight = sum(sorted(weights, reverse=True)[:3])
    if weights and top3_weight < 0.6:
        issues.append(
            ContractIssue(
                "REPORT_THESIS_TOO_DIFFUSE",
                "the three highest-priority topics must carry at least 60% of report weight",
                "report_emphasis",
            )
        )

    semantic = _mapping(document.get("semantic_requirements"), "semantic_requirements", issues)
    for field_name, floor in (
        ("company_specific_metric_minimum", 3),
        ("quantified_driver_to_financial_links_minimum", 2),
        ("unique_core_conclusions_minimum", 3),
    ):
        value = semantic.get(field_name)
        if not isinstance(value, int) or isinstance(value, bool) or value < floor:
            issues.append(
                ContractIssue(
                    "SEMANTIC_FLOOR_TOO_LOW",
                    f"{field_name} must be an integer >= {floor}",
                    f"semantic_requirements.{field_name}",
                )
            )
    duplicate_ratio = semantic.get("maximum_duplicate_insight_ratio")
    if (
        not isinstance(duplicate_ratio, (int, float))
        or isinstance(duplicate_ratio, bool)
        or not 0.0 <= float(duplicate_ratio) <= 0.25
    ):
        issues.append(
            ContractIssue(
                "DUPLICATE_INSIGHT_RATIO_INVALID",
                "maximum_duplicate_insight_ratio must be between 0 and 0.25",
                "semantic_requirements.maximum_duplicate_insight_ratio",
            )
        )

    routes = _mapping(document.get("backflow_routes"), "backflow_routes", issues)
    missing_route_classes = sorted(REQUIRED_BACKFLOW_CLASSES.difference(routes.keys()))
    if missing_route_classes:
        issues.append(
            ContractIssue(
                "BACKFLOW_ROUTE_COVERAGE_MISSING",
                f"missing issue classes: {', '.join(missing_route_classes)}",
                "backflow_routes",
            )
        )
    for issue_class, raw_route in routes.items():
        path = f"backflow_routes.{issue_class}"
        route = _mapping(raw_route, path, issues)
        stage = _non_empty_string(route.get("stage"), f"{path}.stage", issues)
        _non_empty_string(route.get("skill"), f"{path}.skill", issues)
        if stage and stage not in ALLOWED_BACKFLOW_STAGES:
            issues.append(
                ContractIssue(
                    "BACKFLOW_STAGE_INVALID",
                    f"unsupported backflow stage: {stage}",
                    f"{path}.stage",
                )
            )

    artifact_items = _sequence(document.get("expected_artifacts"), "expected_artifacts", issues)
    artifact_roles: set[str] = set()
    for index, raw_artifact in enumerate(artifact_items):
        path = f"expected_artifacts[{index}]"
        artifact = _mapping(raw_artifact, path, issues)
        role = _non_empty_string(artifact.get("role"), f"{path}.role", issues)
        _non_empty_string(artifact.get("relative_path"), f"{path}.relative_path", issues)
        if role:
            artifact_roles.add(role)
    missing_roles = sorted(REQUIRED_EXPECTED_ARTIFACT_ROLES.difference(artifact_roles))
    if missing_roles:
        issues.append(
            ContractIssue(
                "EXPECTED_ARTIFACT_COVERAGE_MISSING",
                f"missing artifact roles: {', '.join(missing_roles)}",
                "expected_artifacts",
            )
        )

    expected_status = _non_empty_string(document.get("expected_status"), "expected_status", issues)
    if expected_status and expected_status not in ALLOWED_EXPECTED_STATUSES:
        issues.append(
            ContractIssue(
                "EXPECTED_STATUS_INVALID",
                f"unsupported expected status: {expected_status}",
                "expected_status",
            )
        )

    blocker_count = sum(1 for issue in issues if issue.severity == "blocker")
    return CaseContractResult(
        case_id=case_id or Path(source).stem,
        issuer_label=issuer_label or "unknown issuer",
        source_path=source,
        contract_valid=blocker_count == 0,
        expected_status=expected_status or "evidence_qualification_pending",
        required_driver_count=len(set(referenced_driver_ids)),
        required_question_count=len(question_ids),
        archetype_count=len(archetype_ids),
        report_emphasis_top3_weight=round(top3_weight, 6),
        release_authority=False,
        sample_quality_allowed=auto_sample,
        p2_allowed=auto_p2,
        workflow_state_mutation_allowed=workflow_mutation,
        issues=tuple(issues),
    )


def _qualification_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return value or {}


def evaluate_qualification(
    document: Mapping[str, Any],
    contract: CaseContractResult,
    qualification: Mapping[str, Any] | None = None,
) -> QualificationResult:
    """Evaluate evidence/model/report readiness without granting release status."""

    state = _qualification_mapping(qualification)
    case_id = contract.case_id
    drivers = {
        str(item.get("driver_id"))
        for item in document.get("drivers", [])
        if isinstance(item, Mapping) and item.get("driver_id")
    }
    required_drivers = {
        str(driver_id)
        for archetype in document.get("economic_archetypes", [])
        if isinstance(archetype, Mapping)
        for driver_id in archetype.get("required_driver_ids", [])
    }
    qualified_drivers = {
        str(value) for value in state.get("qualified_driver_ids", []) if str(value) in drivers
    }
    reviewed_source_count = int(state.get("reviewed_official_source_count", 0) or 0)
    forecast_bridge_complete = state.get("forecast_bridge_complete") is True
    semantic_gate_passed = state.get("semantic_gate_passed") is True
    deterministic_rerun = state.get("deterministic_rerun") is True
    human_status = str(state.get("exact_hash_human_review_status", "not_triggered"))
    overlap_resolved = state.get("overlap_resolved") is True
    valuation_eligible = state.get("valuation_eligible") is True

    backflow: list[BackflowItem] = []
    routes = document.get("backflow_routes", {})

    def add(issue_code: str, reason: str) -> None:
        route = routes.get(issue_code, {}) if isinstance(routes, Mapping) else {}
        backflow.append(
            BackflowItem(
                issue_code=issue_code,
                stage=str(route.get("stage", "T1_evidence_plan")),
                skill=str(route.get("skill", "evidence-ingest")),
                reason=reason,
                case_id=case_id,
            )
        )

    if reviewed_source_count <= 0:
        add("EVIDENCE_MISSING", "no reviewed official evidence pack has been attached")
    missing_drivers = sorted(required_drivers.difference(qualified_drivers))
    if missing_drivers:
        add(
            "DRIVER_UNQUALIFIED",
            "required operating drivers remain unqualified: " + ", ".join(missing_drivers),
        )
    if not overlap_resolved:
        add("OVERLAP_UNRESOLVED", "segment and cross-cutting revenue/gross-profit overlap is unresolved")
    if not forecast_bridge_complete:
        add(
            "DRIVER_UNQUALIFIED",
            "driver-to-statement, working-capital, and cash-flow bridges are incomplete",
        )
    if not valuation_eligible:
        add("VALUATION_INELIGIBLE", "no valuation method has passed its independent eligibility gate")
    if not semantic_gate_passed:
        add("SEMANTIC_QUALITY_FAILED", "semantic quality candidate has not passed")
    if not deterministic_rerun:
        add("SEMANTIC_QUALITY_FAILED", "deterministic rerun has not been demonstrated")

    research_ready = (
        contract.contract_valid
        and reviewed_source_count > 0
        and required_drivers.issubset(qualified_drivers)
        and overlap_resolved
        and forecast_bridge_complete
        and valuation_eligible
        and semantic_gate_passed
        and deterministic_rerun
    )
    candidate_ready = research_ready and human_status in {"pending", "not_triggered"}
    if not contract.contract_valid:
        status = "contract_failed"
    elif candidate_ready:
        status = "candidate_ready_for_exact_hash_review"
    elif reviewed_source_count == 0:
        status = "evidence_qualification_pending"
    else:
        status = "needs_backflow"

    return QualificationResult(
        case_id=case_id,
        status=status,
        research_ready=research_ready,
        candidate_ready_for_exact_hash_review=candidate_ready,
        qualified_driver_count=len(qualified_drivers.intersection(required_drivers)),
        required_driver_count=len(required_drivers),
        reviewed_official_source_count=reviewed_source_count,
        forecast_bridge_complete=forecast_bridge_complete,
        semantic_gate_passed=semantic_gate_passed,
        deterministic_rerun=deterministic_rerun,
        exact_hash_human_review_status=human_status,
        backflow_items=tuple(backflow),
        sample_quality_allowed=False,
        p2_allowed=False,
    )


def scan_core_generality(
    source_paths: Iterable[str | Path],
    forbidden_tokens: Iterable[str],
    *,
    path_root: str | Path | None = None,
) -> CoreGeneralityResult:
    """Reject issuer names/tickers embedded in generic Bundle 14R runtime code."""

    violations: list[str] = []
    scanned: list[str] = []
    tokens = tuple(token for token in (str(item).strip() for item in forbidden_tokens) if token)
    for raw_path in source_paths:
        path = Path(raw_path)
        scanned.append(_logical_path(path, path_root))
        if not path.exists():
            violations.append(f"missing source path: {path}")
            continue
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            if token in text:
                violations.append(f"{path}: contains issuer-specific token {token!r}")
    return CoreGeneralityResult(
        passed=not violations,
        scanned_paths=tuple(scanned),
        violations=tuple(violations),
    )


def build_suite_result(
    case_documents: Sequence[tuple[Path, Mapping[str, Any]]],
    *,
    qualification_by_case: Mapping[str, Mapping[str, Any]] | None = None,
    core_source_paths: Iterable[str | Path] = (),
    path_root: str | Path | None = None,
) -> SuiteResult:
    qualification_state = qualification_by_case or {}
    contracts: list[CaseContractResult] = []
    qualifications: list[QualificationResult] = []
    forbidden_tokens: list[str] = []

    for source_path, document in case_documents:
        contract = validate_case_document(
            document, source_path=_logical_path(source_path, path_root)
        )
        contracts.append(contract)
        issuer = document.get("issuer", {})
        if isinstance(issuer, Mapping):
            forbidden_tokens.extend(
                str(value)
                for value in (issuer.get("name"), issuer.get("ticker"))
                if isinstance(value, str) and value.strip()
            )
        qualifications.append(
            evaluate_qualification(
                document,
                contract,
                qualification_state.get(contract.case_id),
            )
        )

    generality = scan_core_generality(
        core_source_paths, forbidden_tokens, path_root=path_root
    )
    contract_passed = all(item.contract_valid for item in contracts) and generality.passed
    research_ready_count = sum(1 for item in qualifications if item.research_ready)
    candidate_ready_count = sum(
        1 for item in qualifications if item.candidate_ready_for_exact_hash_review
    )
    return SuiteResult(
        schema_version=SUITE_SCHEMA_VERSION,
        bundle_id=BUNDLE_ID,
        case_results=tuple(contracts),
        qualification_results=tuple(qualifications),
        core_generality=generality,
        contract_passed=contract_passed,
        research_ready_case_count=research_ready_count,
        candidate_ready_case_count=candidate_ready_count,
        release_authority=False,
        sample_quality_allowed=False,
        p2_allowed=False,
        workflow_state_mutation_allowed=False,
    )


def suite_to_dict(result: SuiteResult) -> dict[str, Any]:
    return asdict(result)


def build_generation_lock(
    *,
    suite_result: SuiteResult,
    case_paths: Sequence[str | Path],
    source_paths: Sequence[str | Path],
    extra_inputs: Mapping[str, str] | None = None,
    path_root: str | Path | None = None,
) -> dict[str, Any]:
    inputs: dict[str, str] = {}
    for path in [*case_paths, *source_paths]:
        file_path = Path(path)
        inputs[f"repo:{_logical_path(file_path, path_root)}"] = sha256_file(file_path)
    for key, value in sorted((extra_inputs or {}).items()):
        inputs[f"declared:{key}"] = str(value)

    suite_payload = suite_to_dict(suite_result)
    suite_sha = sha256_bytes(_canonical_json_bytes(suite_payload))
    lock_payload: dict[str, Any] = {
        "schema_version": GENERATION_LOCK_SCHEMA_VERSION,
        "bundle_id": BUNDLE_ID,
        "input_sha256": dict(sorted(inputs.items())),
        "suite_result_sha256": suite_sha,
        "release_authority": False,
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "workflow_state_mutation_allowed": False,
    }
    lock_payload["generation_id"] = "golden_regression_gen_" + sha256_bytes(
        _canonical_json_bytes(lock_payload)
    )[:16]
    return lock_payload


def write_json(path: str | Path, value: Any) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "BUNDLE_ID",
    "CASE_SCHEMA_VERSION",
    "CaseContractResult",
    "ContractIssue",
    "ContractViolation",
    "CoreGeneralityResult",
    "QualificationResult",
    "SuiteResult",
    "build_generation_lock",
    "build_suite_result",
    "discover_case_paths",
    "evaluate_qualification",
    "load_yaml_document",
    "scan_core_generality",
    "sha256_file",
    "suite_to_dict",
    "validate_case_document",
    "write_json",
]
