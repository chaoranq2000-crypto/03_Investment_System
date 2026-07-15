"""Bundle 15R reviewed-evidence qualification compiler.

This module bridges reviewed, archived official evidence into the qualification
mapping consumed by the Bundle 14R cross-industry golden-regression harness.
It is issuer-neutral, deterministic, fail-closed, and has no release authority.

The compiler deliberately does not fetch evidence, review evidence, generate a
Reader, accept human review, mutate canonical workflow state, or open sample
quality/P2. Missing or conflicting evidence becomes explicit backflow.
"""

from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

BUNDLE_ID = "R5_BUNDLE15R_REVIEWED_EVIDENCE_QUALIFICATION"
SCHEMA_VERSION = "r5_bundle15r_qualification_suite_v1"
PACK_SCHEMA_VERSION = "r5_bundle15r_reviewed_evidence_pack_v1"
BUNDLE14R_QUALIFICATION_SCHEMA_VERSION = "r5_bundle14r_qualification_v1"

ALLOWED_PACK_REVIEW_STATUSES = {"accepted", "accepted_with_limitations"}
ALLOWED_SOURCE_REVIEW_STATUSES = {"accepted", "accepted_with_limitations"}
ALLOWED_RECORD_REVIEW_STATUSES = {"accepted", "accepted_with_limitations"}
ALLOWED_RECORD_STATUSES = {
    "confirmed",
    "bounded_estimate",
    "context_only",
    "blocked",
    "not_applicable",
}
QUALIFYING_RECORD_STATUSES = {"confirmed", "bounded_estimate"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
QUALIFYING_CONFIDENCE = {"high", "medium"}
ALLOWED_HUMAN_REVIEW_STATUSES = {"not_triggered", "pending", "accepted", "rejected"}
PROHIBITED_SOURCE_CLASSES = {
    "sample_report",
    "narrative_sample",
    "benchmark_sample",
    "generated_report",
    "model_output_as_evidence",
}

DEFAULT_SOURCE_CLASSES = {
    "issuer_exchange_filings",
    "issuer_investor_relations_records",
    "peer_official_disclosures",
    "industry_regulator_or_association",
    "market_data_primary_or_licensed",
    "government_or_regulator",
    "audited_financial_statement",
    "transaction_or_legal_filing",
}

ISSUE_ROUTE = {
    "PACK_MISSING": ("T1_evidence_plan", "evidence-ingest"),
    "PACK_CONTRACT_INVALID": ("T1_evidence_plan", "evidence-ingest"),
    "SOURCE_CLASS_MISSING": ("T1_evidence_plan", "evidence-ingest"),
    "SOURCE_INVALID": ("T2_evidence_acquire_parse", "evidence-ingest"),
    "SOURCE_HASH_MISMATCH": ("T2_evidence_acquire_parse", "evidence-ingest"),
    "QUESTION_UNCLASSIFIED": ("T1_evidence_plan", "stock-deep-dive"),
    "DRIVER_UNQUALIFIED": ("T5_analysis_pack_build", "stock-deep-dive"),
    "DRIVER_CONFLICT": ("T5_analysis_pack_build", "quality-review"),
    "OVERLAP_UNRESOLVED": ("T5_analysis_pack_build", "stock-deep-dive"),
    "FORECAST_BRIDGE_INCOMPLETE": ("T6_forecast_valuation_model", "stock-deep-dive"),
    "VALUATION_INELIGIBLE": ("T6_forecast_valuation_model", "stock-deep-dive"),
    "SEMANTIC_GATE_UNVERIFIED": ("T9_quality_review", "quality-review"),
    "DETERMINISM_UNPROVED": ("T9_quality_review", "quality-review"),
    "HUMAN_REVIEW_INVALID": ("T9_quality_review", "quality-review"),
    "RELEASE_BOUNDARY_VIOLATION": ("T9_quality_review", "research-orchestrator"),
}


class QualificationContractError(ValueError):
    """Raised for a malformed case, policy, or reviewed-evidence pack."""


@dataclass(frozen=True)
class QualificationIssue:
    case_id: str
    code: str
    severity: str
    path: str
    message: str
    stage: str
    skill: str
    owner: str = "workflow_orchestrator"


@dataclass(frozen=True)
class ConflictRecord:
    case_id: str
    driver_id: str
    period: str
    unit: str
    definition: str
    record_ids: tuple[str, ...]
    normalized_values: tuple[str, ...]


@dataclass(frozen=True)
class CaseContract:
    case_id: str
    issuer_name: str
    issuer_ticker: str
    source_path: str
    driver_ids: tuple[str, ...]
    required_driver_ids: tuple[str, ...]
    research_question_ids: tuple[str, ...]
    required_source_classes: tuple[str, ...]
    allowed_valuation_methods: tuple[str, ...]
    minimum_segment_revenue_coverage: float
    minimum_segment_gross_profit_coverage: float


@dataclass(frozen=True)
class CaseQualification:
    schema_version: str
    case_id: str
    issuer_ticker: str
    decision: str
    input_contract_valid: bool
    evidence_pack_present: bool
    evidence_pack_complete: bool
    reviewed_official_source_count: int
    covered_source_classes: tuple[str, ...]
    missing_source_classes: tuple[str, ...]
    qualified_driver_ids: tuple[str, ...]
    required_driver_ids: tuple[str, ...]
    missing_driver_ids: tuple[str, ...]
    driver_coverage_ratio: float
    classified_question_ids: tuple[str, ...]
    missing_question_ids: tuple[str, ...]
    question_coverage_ratio: float
    duplicate_record_count: int
    conflict_count: int
    overlap_resolved: bool
    forecast_bridge_complete: bool
    valuation_eligible: bool
    eligible_valuation_methods: tuple[str, ...]
    semantic_gate_passed: bool
    deterministic_rerun: bool
    exact_hash_human_review_status: str
    bundle14r_candidate_ready: bool
    issues: tuple[QualificationIssue, ...]
    conflicts: tuple[ConflictRecord, ...]
    sample_quality_allowed: bool = False
    p2_allowed: bool = False
    workflow_state_mutation_allowed: bool = False


@dataclass(frozen=True)
class QualificationSuite:
    schema_version: str
    bundle_id: str
    case_results: tuple[CaseQualification, ...]
    input_contract_passed: bool
    case_count: int
    evidence_pack_present_count: int
    evidence_pack_complete_count: int
    bundle14r_candidate_ready_count: int
    issue_count: int
    blocker_count: int
    conflict_count: int
    release_authority: bool = False
    sample_quality_allowed: bool = False
    p2_allowed: bool = False
    workflow_state_mutation_allowed: bool = False


@dataclass(frozen=True)
class CompilationArtifacts:
    suite: QualificationSuite
    qualification_payloads: Mapping[str, Mapping[str, Any]]
    evidence_requests: tuple[Mapping[str, Any], ...]
    generation_lock: Mapping[str, Any]


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    source = Path(path)
    digest = sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_yaml_document(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise QualificationContractError(f"{source}: YAML root must be a mapping")
    return payload


def write_yaml(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(
        dict(payload),
        allow_unicode=True,
        sort_keys=True,
        default_flow_style=False,
        width=1000,
    )
    target.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _string(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _bool(value: Any) -> bool:
    return value is True


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return number


def _safe_relative_path(value: str) -> bool:
    if not value:
        return False
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts


def _valid_sha256(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", value.lower()))


def _valid_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _valid_datetime(value: str) -> bool:
    if not value:
        return False
    candidate = value.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(candidate)
        return True
    except ValueError:
        return False


def _logical_path(path: str | Path, root: str | Path | None = None) -> str:
    source = Path(path)
    if root is not None:
        try:
            return source.resolve().relative_to(Path(root).resolve()).as_posix()
        except ValueError:
            pass
    if source.is_absolute():
        return source.name
    return source.as_posix()


def _issue(
    case_id: str,
    code: str,
    path: str,
    message: str,
    *,
    severity: str = "blocker",
) -> QualificationIssue:
    stage, skill = ISSUE_ROUTE.get(code, ("T1_evidence_plan", "research-orchestrator"))
    return QualificationIssue(
        case_id=case_id,
        code=code,
        severity=severity,
        path=path,
        message=message,
        stage=stage,
        skill=skill,
    )


def discover_yaml_paths(directory: str | Path) -> tuple[Path, ...]:
    root = Path(directory)
    if not root.exists():
        return ()
    return tuple(
        sorted(
            path
            for path in root.iterdir()
            if path.is_file() and path.suffix.lower() in {".yaml", ".yml"}
        )
    )


def extract_case_contract(
    case_document: Mapping[str, Any],
    *,
    source_path: str | Path,
    path_root: str | Path | None = None,
) -> CaseContract:
    case_id = _string(case_document.get("case_id"))
    if not case_id:
        raise QualificationContractError(f"{source_path}: case_id is required")

    issuer = _mapping(case_document.get("issuer"))
    issuer_name = _string(issuer.get("name"))
    issuer_ticker = _string(issuer.get("ticker"))
    if not issuer_name or not issuer_ticker:
        raise QualificationContractError(f"{source_path}: issuer.name and issuer.ticker are required")

    driver_ids: list[str] = []
    for index, item in enumerate(_sequence(case_document.get("drivers"))):
        driver_id = _string(_mapping(item).get("driver_id"))
        if not driver_id:
            raise QualificationContractError(f"{source_path}: drivers[{index}].driver_id is required")
        driver_ids.append(driver_id)
    if not driver_ids or len(driver_ids) != len(set(driver_ids)):
        raise QualificationContractError(f"{source_path}: drivers must be non-empty and unique")

    required_driver_ids: list[str] = []
    for archetype in _sequence(case_document.get("economic_archetypes")):
        for value in _sequence(_mapping(archetype).get("required_driver_ids")):
            driver_id = _string(value)
            if driver_id:
                required_driver_ids.append(driver_id)
    if not required_driver_ids:
        required_driver_ids = list(driver_ids)
    unknown_required = sorted(set(required_driver_ids).difference(driver_ids))
    if unknown_required:
        raise QualificationContractError(
            f"{source_path}: economic archetypes reference unknown drivers: {', '.join(unknown_required)}"
        )

    question_ids: list[str] = []
    for index, item in enumerate(_sequence(case_document.get("research_questions"))):
        question_id = _string(_mapping(item).get("question_id"))
        if not question_id:
            raise QualificationContractError(
                f"{source_path}: research_questions[{index}].question_id is required"
            )
        question_ids.append(question_id)
    if len(question_ids) != len(set(question_ids)):
        raise QualificationContractError(f"{source_path}: research question IDs must be unique")

    source_classes = tuple(
        sorted(
            {
                _string(value)
                for value in _sequence(case_document.get("required_source_classes"))
                if _string(value)
            }
        )
    )

    methods = tuple(
        sorted(
            {
                _string(_mapping(item).get("method"))
                for item in _sequence(case_document.get("valuation_methods"))
                if _string(_mapping(item).get("method"))
            }
        )
    )

    forecast = _mapping(case_document.get("forecast_contract"))
    minimum_revenue = _number(forecast.get("minimum_segment_revenue_coverage"), 0.8)
    minimum_gross_profit = _number(
        forecast.get("minimum_segment_gross_profit_coverage"), 0.8
    )
    if not (0 <= minimum_revenue <= 1 and 0 <= minimum_gross_profit <= 1):
        raise QualificationContractError(f"{source_path}: forecast coverage thresholds must be [0, 1]")

    release = _mapping(case_document.get("release_policy"))
    if any(
        _bool(release.get(key))
        for key in (
            "automated_sample_quality_allowed",
            "automated_p2_allowed",
            "workflow_state_mutation_allowed",
        )
    ):
        raise QualificationContractError(f"{source_path}: release policy attempts to open a hard boundary")

    return CaseContract(
        case_id=case_id,
        issuer_name=issuer_name,
        issuer_ticker=issuer_ticker,
        source_path=_logical_path(source_path, path_root),
        driver_ids=tuple(sorted(set(driver_ids))),
        required_driver_ids=tuple(sorted(set(required_driver_ids))),
        research_question_ids=tuple(sorted(set(question_ids))),
        required_source_classes=source_classes,
        allowed_valuation_methods=methods,
        minimum_segment_revenue_coverage=minimum_revenue,
        minimum_segment_gross_profit_coverage=minimum_gross_profit,
    )


def _load_policy(policy_document: Mapping[str, Any] | None) -> dict[str, Any]:
    policy = dict(policy_document or {})
    allowed_source_classes = set(DEFAULT_SOURCE_CLASSES)
    allowed_source_classes.update(
        _string(item)
        for item in _sequence(policy.get("allowed_source_classes"))
        if _string(item)
    )
    policy["allowed_source_classes"] = sorted(allowed_source_classes)
    policy.setdefault("minimum_driver_confidence", "medium")
    policy.setdefault("require_physical_source_archive", True)
    policy.setdefault("require_all_case_source_classes", True)
    policy.setdefault("require_all_research_questions_classified", True)
    policy.setdefault("minimum_qualified_peers", 3)
    return policy


def _record_value_key(value: Any) -> str:
    try:
        return _canonical_json_bytes(value).decode("utf-8")
    except (TypeError, ValueError):
        return repr(value)


def _source_is_valid(
    source: Mapping[str, Any],
    *,
    case_id: str,
    source_path: str,
    repo_root: Path,
    allowed_source_classes: set[str],
    verify_source_paths: bool,
    issues: list[QualificationIssue],
) -> tuple[bool, str]:
    source_id = _string(source.get("source_id"))
    source_class = _string(source.get("source_class"))
    prefix = f"sources[{source_id or '?'}]"
    valid = True

    if not source_id:
        issues.append(_issue(case_id, "SOURCE_INVALID", prefix, "source_id is required"))
        valid = False
    if source_class in PROHIBITED_SOURCE_CLASSES or "sample" in source_class.lower():
        issues.append(
            _issue(
                case_id,
                "SOURCE_INVALID",
                f"{prefix}.source_class",
                f"sample or generated material cannot be evidence: {source_class!r}",
            )
        )
        valid = False
    elif source_class not in allowed_source_classes:
        issues.append(
            _issue(
                case_id,
                "SOURCE_INVALID",
                f"{prefix}.source_class",
                f"source class is not allowed by policy: {source_class!r}",
            )
        )
        valid = False

    if source.get("official") is not True:
        issues.append(_issue(case_id, "SOURCE_INVALID", f"{prefix}.official", "official must be true"))
        valid = False
    review_status = _string(source.get("review_status"))
    if review_status not in ALLOWED_SOURCE_REVIEW_STATUSES:
        issues.append(
            _issue(
                case_id,
                "SOURCE_INVALID",
                f"{prefix}.review_status",
                f"source is not reviewed: {review_status!r}",
            )
        )
        valid = False

    publication_date = _string(source.get("publication_date"))
    if not _valid_date(publication_date):
        issues.append(
            _issue(
                case_id,
                "SOURCE_INVALID",
                f"{prefix}.publication_date",
                "publication_date must be YYYY-MM-DD",
            )
        )
        valid = False
    if not _string(source.get("covered_period")):
        issues.append(
            _issue(case_id, "SOURCE_INVALID", f"{prefix}.covered_period", "covered_period is required")
        )
        valid = False

    archive_path = _string(source.get("archive_path"))
    expected_hash = _string(source.get("sha256")).lower()
    if not _safe_relative_path(archive_path):
        issues.append(
            _issue(
                case_id,
                "SOURCE_INVALID",
                f"{prefix}.archive_path",
                "archive_path must be a safe repository-relative path",
            )
        )
        valid = False
    if not _valid_sha256(expected_hash):
        issues.append(
            _issue(case_id, "SOURCE_INVALID", f"{prefix}.sha256", "sha256 must contain 64 hex characters")
        )
        valid = False
    if archive_path and _safe_relative_path(archive_path) and verify_source_paths:
        physical_path = repo_root / archive_path
        if not physical_path.is_file():
            issues.append(
                _issue(
                    case_id,
                    "SOURCE_INVALID",
                    f"{prefix}.archive_path",
                    f"archived source does not exist: {archive_path}",
                )
            )
            valid = False
        elif _valid_sha256(expected_hash):
            actual_hash = sha256_file(physical_path)
            if actual_hash != expected_hash:
                issues.append(
                    _issue(
                        case_id,
                        "SOURCE_HASH_MISMATCH",
                        f"{prefix}.sha256",
                        f"expected {expected_hash}, got {actual_hash}",
                    )
                )
                valid = False

    return valid, source_class


def _verify_hashed_artifact(
    block: Mapping[str, Any],
    *,
    path_key: str,
    hash_key: str,
    case_id: str,
    repo_root: Path,
    verify_paths: bool,
    issues: list[QualificationIssue],
    issue_code: str,
) -> bool:
    relative_path = _string(block.get(path_key))
    expected_hash = _string(block.get(hash_key)).lower()
    if not _safe_relative_path(relative_path) or not _valid_sha256(expected_hash):
        issues.append(
            _issue(
                case_id,
                issue_code,
                path_key,
                f"{path_key} and {hash_key} must identify a safe, hash-bound artifact",
            )
        )
        return False
    if not verify_paths:
        return True
    physical = repo_root / relative_path
    if not physical.is_file():
        issues.append(_issue(case_id, issue_code, path_key, f"artifact is missing: {relative_path}"))
        return False
    actual = sha256_file(physical)
    if actual != expected_hash:
        issues.append(
            _issue(
                case_id,
                issue_code,
                hash_key,
                f"artifact hash mismatch: expected {expected_hash}, got {actual}",
            )
        )
        return False
    return True


def _evaluate_valuation(
    valuation_block: Mapping[str, Any],
    *,
    contract: CaseContract,
    minimum_qualified_peers: int,
) -> tuple[tuple[str, ...], list[str]]:
    eligible: list[str] = []
    notes: list[str] = []
    allowed = set(contract.allowed_valuation_methods)
    for raw_method in _sequence(valuation_block.get("methods")):
        method = _mapping(raw_method)
        name = _string(method.get("method"))
        if not name or name not in allowed:
            continue
        if method.get("eligible") is not True:
            continue
        passed = False
        if name == "reverse_valuation":
            passed = all(
                _bool(method.get(key))
                for key in (
                    "market_value_reconciled",
                    "share_count_reconciled",
                    "forecast_definition_reconciled",
                    "implied_operating_assumptions_documented",
                )
            )
        elif name == "peer_multiples":
            passed = (
                int(_number(method.get("qualified_peer_count"), 0)) >= minimum_qualified_peers
                and all(
                    _bool(method.get(key))
                    for key in (
                        "definition_compatible",
                        "period_compatible",
                        "metric_compatible",
                    )
                )
            )
        elif name == "dcf_or_sotp":
            passed = all(
                _bool(method.get(key))
                for key in (
                    "cash_flow_or_segment_economics_qualified",
                    "overlap_eliminated",
                    "discount_inputs_qualified",
                    "terminal_assumptions_qualified",
                )
            )
        else:
            passed = _bool(method.get("independent_gate_passed"))
        if passed:
            eligible.append(name)
        else:
            notes.append(f"{name}: declared eligible but independent method gate did not pass")
    return tuple(sorted(set(eligible))), notes


def _empty_case_result(contract: CaseContract, *, reason: str) -> CaseQualification:
    issue = _issue(contract.case_id, "PACK_MISSING", "reviewed_evidence_pack", reason)
    return CaseQualification(
        schema_version=SCHEMA_VERSION,
        case_id=contract.case_id,
        issuer_ticker=contract.issuer_ticker,
        decision="evidence_qualification_pending",
        input_contract_valid=True,
        evidence_pack_present=False,
        evidence_pack_complete=False,
        reviewed_official_source_count=0,
        covered_source_classes=(),
        missing_source_classes=contract.required_source_classes,
        qualified_driver_ids=(),
        required_driver_ids=contract.required_driver_ids,
        missing_driver_ids=contract.required_driver_ids,
        driver_coverage_ratio=0.0,
        classified_question_ids=(),
        missing_question_ids=contract.research_question_ids,
        question_coverage_ratio=0.0 if contract.research_question_ids else 1.0,
        duplicate_record_count=0,
        conflict_count=0,
        overlap_resolved=False,
        forecast_bridge_complete=False,
        valuation_eligible=False,
        eligible_valuation_methods=(),
        semantic_gate_passed=False,
        deterministic_rerun=False,
        exact_hash_human_review_status="not_triggered",
        bundle14r_candidate_ready=False,
        issues=(issue,),
        conflicts=(),
    )


def evaluate_evidence_pack(
    contract: CaseContract,
    pack_document: Mapping[str, Any] | None,
    *,
    pack_source_path: str | Path | None,
    repo_root: str | Path,
    policy_document: Mapping[str, Any] | None = None,
    verify_paths: bool = True,
) -> CaseQualification:
    if pack_document is None:
        return _empty_case_result(
            contract,
            reason="no reviewed evidence pack has been supplied for this case",
        )

    policy = _load_policy(policy_document)
    root = Path(repo_root).resolve()
    issues: list[QualificationIssue] = []
    conflicts: list[ConflictRecord] = []
    case_id = contract.case_id
    contract_valid = True

    if _string(pack_document.get("schema_version")) != PACK_SCHEMA_VERSION:
        issues.append(
            _issue(
                case_id,
                "PACK_CONTRACT_INVALID",
                "schema_version",
                f"expected {PACK_SCHEMA_VERSION}",
            )
        )
        contract_valid = False
    if _string(pack_document.get("case_id")) != case_id:
        issues.append(
            _issue(
                case_id,
                "PACK_CONTRACT_INVALID",
                "case_id",
                f"pack case_id does not match {case_id}",
            )
        )
        contract_valid = False
    issuer = _mapping(pack_document.get("issuer"))
    if _string(issuer.get("ticker")) != contract.issuer_ticker:
        issues.append(
            _issue(
                case_id,
                "PACK_CONTRACT_INVALID",
                "issuer.ticker",
                f"pack ticker does not match {contract.issuer_ticker}",
            )
        )
        contract_valid = False
    if not _valid_date(_string(pack_document.get("as_of_date"))):
        issues.append(
            _issue(case_id, "PACK_CONTRACT_INVALID", "as_of_date", "as_of_date must be YYYY-MM-DD")
        )
        contract_valid = False

    review = _mapping(pack_document.get("review"))
    if _string(review.get("status")) not in ALLOWED_PACK_REVIEW_STATUSES:
        issues.append(
            _issue(
                case_id,
                "PACK_CONTRACT_INVALID",
                "review.status",
                "pack must have a real accepted or accepted_with_limitations review",
            )
        )
        contract_valid = False
    if not _string(review.get("reviewer")) or not _valid_datetime(_string(review.get("reviewed_at"))):
        issues.append(
            _issue(
                case_id,
                "PACK_CONTRACT_INVALID",
                "review",
                "reviewer identity and ISO reviewed_at timestamp are required",
            )
        )
        contract_valid = False

    release = _mapping(pack_document.get("release"))
    for key in ("sample_quality_allowed", "p2_allowed", "workflow_state_mutation_allowed"):
        if release.get(key) is True:
            issues.append(
                _issue(
                    case_id,
                    "RELEASE_BOUNDARY_VIOLATION",
                    f"release.{key}",
                    f"Bundle 15R cannot set {key}=true",
                )
            )
            contract_valid = False

    allowed_source_classes = set(policy["allowed_source_classes"])
    sources_by_id: dict[str, Mapping[str, Any]] = {}
    valid_source_ids: set[str] = set()
    covered_source_classes: set[str] = set()
    for index, raw_source in enumerate(_sequence(pack_document.get("sources"))):
        source = _mapping(raw_source)
        source_id = _string(source.get("source_id"))
        if source_id in sources_by_id:
            issues.append(
                _issue(
                    case_id,
                    "SOURCE_INVALID",
                    f"sources[{index}].source_id",
                    f"duplicate source_id: {source_id}",
                )
            )
            contract_valid = False
            continue
        if source_id:
            sources_by_id[source_id] = source
        source_valid, source_class = _source_is_valid(
            source,
            case_id=case_id,
            source_path=_string(pack_source_path),
            repo_root=root,
            allowed_source_classes=allowed_source_classes,
            verify_source_paths=verify_paths,
            issues=issues,
        )
        if source_valid and source_id:
            valid_source_ids.add(source_id)
            covered_source_classes.add(source_class)

    if not sources_by_id:
        issues.append(_issue(case_id, "SOURCE_INVALID", "sources", "at least one source is required"))
        contract_valid = False

    required_source_classes = set(contract.required_source_classes)
    missing_source_classes = sorted(required_source_classes.difference(covered_source_classes))
    if policy.get("require_all_case_source_classes", True):
        for source_class in missing_source_classes:
            issues.append(
                _issue(
                    case_id,
                    "SOURCE_CLASS_MISSING",
                    "sources",
                    f"required source class is missing: {source_class}",
                )
            )

    driver_ids = set(contract.driver_ids)
    question_ids = set(contract.research_question_ids)
    valid_records: list[Mapping[str, Any]] = []
    record_ids: set[str] = set()
    classified_question_ids: set[str] = set()

    for index, raw_record in enumerate(_sequence(pack_document.get("records"))):
        record = _mapping(raw_record)
        record_id = _string(record.get("record_id"))
        prefix = f"records[{index}]"
        record_valid = True
        if not record_id or record_id in record_ids:
            issues.append(
                _issue(
                    case_id,
                    "PACK_CONTRACT_INVALID",
                    f"{prefix}.record_id",
                    "record_id is required and must be unique",
                )
            )
            contract_valid = False
            record_valid = False
        record_ids.add(record_id)

        driver_id = _string(record.get("driver_id"))
        if driver_id not in driver_ids:
            issues.append(
                _issue(
                    case_id,
                    "PACK_CONTRACT_INVALID",
                    f"{prefix}.driver_id",
                    f"unknown driver_id: {driver_id!r}",
                )
            )
            contract_valid = False
            record_valid = False

        status = _string(record.get("status"))
        if status not in ALLOWED_RECORD_STATUSES:
            issues.append(
                _issue(
                    case_id,
                    "PACK_CONTRACT_INVALID",
                    f"{prefix}.status",
                    f"unsupported record status: {status!r}",
                )
            )
            contract_valid = False
            record_valid = False
        review_status = _string(record.get("review_status"))
        if review_status not in ALLOWED_RECORD_REVIEW_STATUSES:
            issues.append(
                _issue(
                    case_id,
                    "PACK_CONTRACT_INVALID",
                    f"{prefix}.review_status",
                    "record must be reviewed",
                )
            )
            contract_valid = False
            record_valid = False

        confidence = _string(record.get("confidence"))
        if confidence not in ALLOWED_CONFIDENCE:
            issues.append(
                _issue(
                    case_id,
                    "PACK_CONTRACT_INVALID",
                    f"{prefix}.confidence",
                    f"unsupported confidence: {confidence!r}",
                )
            )
            contract_valid = False
            record_valid = False

        linked_sources = {_string(value) for value in _sequence(record.get("source_ids")) if _string(value)}
        if not linked_sources or not linked_sources.issubset(valid_source_ids):
            issues.append(
                _issue(
                    case_id,
                    "SOURCE_INVALID",
                    f"{prefix}.source_ids",
                    "every record must link only to valid reviewed official sources",
                )
            )
            record_valid = False

        linked_questions = {
            _string(value) for value in _sequence(record.get("question_ids")) if _string(value)
        }
        unknown_questions = linked_questions.difference(question_ids)
        if unknown_questions:
            issues.append(
                _issue(
                    case_id,
                    "PACK_CONTRACT_INVALID",
                    f"{prefix}.question_ids",
                    "unknown research questions: " + ", ".join(sorted(unknown_questions)),
                )
            )
            contract_valid = False
            record_valid = False
        classified_question_ids.update(linked_questions.intersection(question_ids))

        if status in QUALIFYING_RECORD_STATUSES:
            for field_name in ("unit", "period", "definition", "overlap_rule", "stale_trigger"):
                if not _string(record.get(field_name)):
                    issues.append(
                        _issue(
                            case_id,
                            "DRIVER_UNQUALIFIED",
                            f"{prefix}.{field_name}",
                            f"qualifying record requires {field_name}",
                        )
                    )
                    record_valid = False
            if record.get("value") is None:
                issues.append(
                    _issue(
                        case_id,
                        "DRIVER_UNQUALIFIED",
                        f"{prefix}.value",
                        "qualifying record requires a concrete value or range",
                    )
                )
                record_valid = False
            if confidence not in QUALIFYING_CONFIDENCE:
                issues.append(
                    _issue(
                        case_id,
                        "DRIVER_UNQUALIFIED",
                        f"{prefix}.confidence",
                        "low-confidence records cannot qualify a required operating driver",
                    )
                )
                record_valid = False

        if record_valid:
            valid_records.append(record)

    # Deterministic equal-value deduplication and conflict detection.
    grouped: dict[tuple[str, str, str, str], list[Mapping[str, Any]]] = {}
    for record in valid_records:
        if _string(record.get("status")) not in QUALIFYING_RECORD_STATUSES:
            continue
        key = (
            _string(record.get("driver_id")),
            _string(record.get("period")),
            _string(record.get("unit")),
            _string(record.get("definition")),
        )
        grouped.setdefault(key, []).append(record)

    duplicate_count = 0
    conflicted_driver_ids: set[str] = set()
    qualifying_driver_ids: set[str] = set()
    for (driver_id, period, unit, definition), records in sorted(grouped.items()):
        values = {_record_value_key(item.get("value")) for item in records}
        if len(values) > 1:
            conflict = ConflictRecord(
                case_id=case_id,
                driver_id=driver_id,
                period=period,
                unit=unit,
                definition=definition,
                record_ids=tuple(sorted(_string(item.get("record_id")) for item in records)),
                normalized_values=tuple(sorted(values)),
            )
            conflicts.append(conflict)
            conflicted_driver_ids.add(driver_id)
            issues.append(
                _issue(
                    case_id,
                    "DRIVER_CONFLICT",
                    f"records.{driver_id}",
                    f"conflicting reviewed values for {driver_id} / {period} / {unit}",
                )
            )
        else:
            duplicate_count += max(0, len(records) - 1)
            qualifying_driver_ids.add(driver_id)

    qualifying_driver_ids.difference_update(conflicted_driver_ids)
    required_drivers = set(contract.required_driver_ids)
    qualified_required = required_drivers.intersection(qualifying_driver_ids)
    missing_driver_ids = sorted(required_drivers.difference(qualified_required))
    for driver_id in missing_driver_ids:
        issues.append(
            _issue(
                case_id,
                "DRIVER_UNQUALIFIED",
                f"drivers.{driver_id}",
                f"required operating driver remains unqualified: {driver_id}",
            )
        )

    missing_question_ids = sorted(question_ids.difference(classified_question_ids))
    if policy.get("require_all_research_questions_classified", True):
        for question_id in missing_question_ids:
            issues.append(
                _issue(
                    case_id,
                    "QUESTION_UNCLASSIFIED",
                    f"research_questions.{question_id}",
                    f"research question is not classified by reviewed evidence: {question_id}",
                )
            )

    overlap = _mapping(pack_document.get("overlap_reconciliation"))
    overlap_resolved = (
        _string(overlap.get("status")) == "passed"
        and _bool(overlap.get("revenue_overlap_resolved"))
        and _bool(overlap.get("gross_profit_overlap_resolved"))
        and len(_sequence(overlap.get("unresolved_items"))) == 0
    )
    if not overlap_resolved:
        issues.append(
            _issue(
                case_id,
                "OVERLAP_UNRESOLVED",
                "overlap_reconciliation",
                "revenue and gross-profit overlap must both be reconciled with no unresolved items",
            )
        )

    forecast = _mapping(pack_document.get("forecast_bridge"))
    revenue_coverage = _number(forecast.get("segment_revenue_coverage"), 0.0)
    gross_profit_coverage = _number(forecast.get("segment_gross_profit_coverage"), 0.0)
    forecast_bridge_complete = (
        _string(forecast.get("status")) == "passed"
        and _bool(forecast.get("driver_to_statement_reconciliation"))
        and _bool(forecast.get("working_capital_bridge"))
        and _bool(forecast.get("cash_flow_bridge"))
        and revenue_coverage >= contract.minimum_segment_revenue_coverage
        and gross_profit_coverage >= contract.minimum_segment_gross_profit_coverage
    )
    if not forecast_bridge_complete:
        issues.append(
            _issue(
                case_id,
                "FORECAST_BRIDGE_INCOMPLETE",
                "forecast_bridge",
                (
                    "driver-to-statement, working-capital and cash-flow bridges must pass; "
                    f"revenue coverage={revenue_coverage:.3f}, gross-profit coverage={gross_profit_coverage:.3f}"
                ),
            )
        )

    eligible_methods, valuation_notes = _evaluate_valuation(
        _mapping(pack_document.get("valuation")),
        contract=contract,
        minimum_qualified_peers=int(policy.get("minimum_qualified_peers", 3)),
    )
    valuation_eligible = bool(eligible_methods)
    if not valuation_eligible:
        message = "no independently qualified valuation method"
        if valuation_notes:
            message += "; " + "; ".join(valuation_notes)
        issues.append(_issue(case_id, "VALUATION_INELIGIBLE", "valuation", message))

    semantic = _mapping(pack_document.get("semantic_candidate"))
    semantic_artifact_verified = False
    if _string(semantic.get("status")) == "passed":
        semantic_artifact_verified = _verify_hashed_artifact(
            semantic,
            path_key="semantic_gate_path",
            hash_key="semantic_gate_sha256",
            case_id=case_id,
            repo_root=root,
            verify_paths=verify_paths,
            issues=issues,
            issue_code="SEMANTIC_GATE_UNVERIFIED",
        )
    else:
        issues.append(
            _issue(
                case_id,
                "SEMANTIC_GATE_UNVERIFIED",
                "semantic_candidate.status",
                "semantic candidate gate has not passed",
            )
        )

    determinism = _mapping(pack_document.get("determinism"))
    deterministic_rerun = all(
        _bool(determinism.get(key))
        for key in ("rerun_hash_equal", "input_lock_complete", "output_lock_complete")
    )
    if not deterministic_rerun:
        issues.append(
            _issue(
                case_id,
                "DETERMINISM_UNPROVED",
                "determinism",
                "rerun equality and complete input/output locks are required",
            )
        )

    human = _mapping(pack_document.get("exact_hash_human_review"))
    human_status = _string(human.get("status")) or "not_triggered"
    if human_status not in ALLOWED_HUMAN_REVIEW_STATUSES:
        issues.append(
            _issue(
                case_id,
                "HUMAN_REVIEW_INVALID",
                "exact_hash_human_review.status",
                f"unsupported review status: {human_status!r}",
            )
        )
        human_status = "not_triggered"
    elif human_status == "accepted":
        accepted_review_valid = (
            _string(human.get("reviewer"))
            and _valid_datetime(_string(human.get("reviewed_at")))
            and _verify_hashed_artifact(
                human,
                path_key="review_path",
                hash_key="review_sha256",
                case_id=case_id,
                repo_root=root,
                verify_paths=verify_paths,
                issues=issues,
                issue_code="HUMAN_REVIEW_INVALID",
            )
        )
        if not accepted_review_valid:
            human_status = "rejected"

    source_coverage_complete = not missing_source_classes
    questions_complete = not missing_question_ids
    drivers_complete = not missing_driver_ids
    evidence_pack_complete = (
        contract_valid
        and bool(valid_source_ids)
        and source_coverage_complete
        and questions_complete
        and drivers_complete
        and not conflicts
    )

    # A semantic pass is usable only when the evidence pack itself is complete;
    # this prevents a structurally polished report from compensating for missing evidence.
    semantic_gate_passed = semantic_artifact_verified and evidence_pack_complete
    if semantic_artifact_verified and not evidence_pack_complete:
        issues.append(
            _issue(
                case_id,
                "SEMANTIC_GATE_UNVERIFIED",
                "semantic_candidate",
                "semantic artifact passed but evidence completeness gate did not",
            )
        )

    bundle14r_candidate_ready = (
        evidence_pack_complete
        and overlap_resolved
        and forecast_bridge_complete
        and valuation_eligible
        and semantic_gate_passed
        and deterministic_rerun
        and human_status in {"not_triggered", "pending"}
    )

    blockers = [item for item in issues if item.severity == "blocker"]
    if not contract_valid:
        decision = "input_contract_failed"
    elif bundle14r_candidate_ready:
        decision = "qualification_ready_for_bundle14r"
    elif not valid_source_ids:
        decision = "evidence_qualification_pending"
    else:
        decision = "needs_targeted_backflow"

    driver_coverage = len(qualified_required) / len(required_drivers) if required_drivers else 1.0
    question_coverage = (
        len(classified_question_ids.intersection(question_ids)) / len(question_ids)
        if question_ids
        else 1.0
    )

    return CaseQualification(
        schema_version=SCHEMA_VERSION,
        case_id=case_id,
        issuer_ticker=contract.issuer_ticker,
        decision=decision,
        input_contract_valid=contract_valid and not any(
            issue.code in {"PACK_CONTRACT_INVALID", "RELEASE_BOUNDARY_VIOLATION"}
            for issue in blockers
        ),
        evidence_pack_present=True,
        evidence_pack_complete=evidence_pack_complete,
        reviewed_official_source_count=len(valid_source_ids),
        covered_source_classes=tuple(sorted(covered_source_classes)),
        missing_source_classes=tuple(missing_source_classes),
        qualified_driver_ids=tuple(sorted(qualified_required)),
        required_driver_ids=contract.required_driver_ids,
        missing_driver_ids=tuple(missing_driver_ids),
        driver_coverage_ratio=round(driver_coverage, 6),
        classified_question_ids=tuple(sorted(classified_question_ids.intersection(question_ids))),
        missing_question_ids=tuple(missing_question_ids),
        question_coverage_ratio=round(question_coverage, 6),
        duplicate_record_count=duplicate_count,
        conflict_count=len(conflicts),
        overlap_resolved=overlap_resolved,
        forecast_bridge_complete=forecast_bridge_complete,
        valuation_eligible=valuation_eligible,
        eligible_valuation_methods=eligible_methods,
        semantic_gate_passed=semantic_gate_passed,
        deterministic_rerun=deterministic_rerun,
        exact_hash_human_review_status=human_status,
        bundle14r_candidate_ready=bundle14r_candidate_ready,
        issues=tuple(sorted(issues, key=lambda item: (item.severity, item.code, item.path, item.message))),
        conflicts=tuple(conflicts),
    )


def bundle14r_qualification_payload(result: CaseQualification) -> dict[str, Any]:
    """Return the exact keys consumed by Bundle 14R, plus non-authoritative audit metadata."""

    return {
        "schema_version": BUNDLE14R_QUALIFICATION_SCHEMA_VERSION,
        "case_id": result.case_id,
        "qualified_driver_ids": list(result.qualified_driver_ids),
        "reviewed_official_source_count": result.reviewed_official_source_count,
        "overlap_resolved": result.overlap_resolved,
        "forecast_bridge_complete": result.forecast_bridge_complete,
        "valuation_eligible": result.valuation_eligible,
        "semantic_gate_passed": result.semantic_gate_passed,
        "deterministic_rerun": result.deterministic_rerun,
        "exact_hash_human_review_status": result.exact_hash_human_review_status,
        "bundle15r_audit": {
            "decision": result.decision,
            "evidence_pack_complete": result.evidence_pack_complete,
            "driver_coverage_ratio": result.driver_coverage_ratio,
            "question_coverage_ratio": result.question_coverage_ratio,
            "missing_source_classes": list(result.missing_source_classes),
            "missing_driver_ids": list(result.missing_driver_ids),
            "missing_question_ids": list(result.missing_question_ids),
            "eligible_valuation_methods": list(result.eligible_valuation_methods),
            "issue_count": len(result.issues),
            "conflict_count": result.conflict_count,
            "sample_quality_allowed": False,
            "p2_allowed": False,
            "workflow_state_mutation_allowed": False,
        },
    }


def _evidence_requests_for_case(result: CaseQualification) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for issue in result.issues:
        if issue.severity != "blocker":
            continue
        rows.append(
            {
                "case_id": result.case_id,
                "issuer_ticker": result.issuer_ticker,
                "issue_code": issue.code,
                "stage": issue.stage,
                "skill": issue.skill,
                "owner": issue.owner,
                "path": issue.path,
                "request": issue.message,
                "status": "open",
            }
        )
    return rows


def build_generation_lock(
    *,
    suite_payload: Mapping[str, Any],
    case_paths: Iterable[str | Path],
    pack_paths: Iterable[str | Path],
    source_archive_paths: Iterable[str | Path],
    core_paths: Iterable[str | Path],
    path_root: str | Path,
    extra_inputs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(path_root).resolve()
    file_rows: list[dict[str, str]] = []
    for role, paths in (
        ("case_contract", case_paths),
        ("reviewed_evidence_pack", pack_paths),
        ("source_archive", source_archive_paths),
        ("compiler_source", core_paths),
    ):
        for raw_path in sorted({Path(path) for path in paths}, key=lambda item: item.as_posix()):
            if raw_path.is_file():
                file_rows.append(
                    {
                        "role": role,
                        "path": _logical_path(raw_path, root),
                        "sha256": sha256_file(raw_path),
                    }
                )
    lock_seed = {
        "schema_version": SCHEMA_VERSION,
        "bundle_id": BUNDLE_ID,
        "files": file_rows,
        "suite_sha256": sha256_bytes(_canonical_json_bytes(suite_payload)),
        "extra_inputs": dict(extra_inputs or {}),
        "release_authority": False,
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "workflow_state_mutation_allowed": False,
    }
    generation_id = "evidence_qualification_gen_r5_bundle15r_" + sha256_bytes(
        _canonical_json_bytes(lock_seed)
    )[:16]
    return {**lock_seed, "generation_id": generation_id}


def compile_qualification_suite(
    case_documents: Sequence[tuple[Path, Mapping[str, Any]]],
    *,
    pack_by_case: Mapping[str, tuple[Path, Mapping[str, Any]]],
    repo_root: str | Path,
    policy_document: Mapping[str, Any] | None = None,
    verify_paths: bool = True,
    core_paths: Iterable[str | Path] = (),
    extra_lock_inputs: Mapping[str, Any] | None = None,
) -> CompilationArtifacts:
    root = Path(repo_root).resolve()
    contracts: list[CaseContract] = []
    results: list[CaseQualification] = []
    used_pack_paths: list[Path] = []
    source_archive_paths: list[Path] = []

    for case_path, case_document in sorted(case_documents, key=lambda item: item[0].as_posix()):
        contract = extract_case_contract(case_document, source_path=case_path, path_root=root)
        contracts.append(contract)
        pack_entry = pack_by_case.get(contract.case_id)
        if pack_entry is None:
            result = evaluate_evidence_pack(
                contract,
                None,
                pack_source_path=None,
                repo_root=root,
                policy_document=policy_document,
                verify_paths=verify_paths,
            )
        else:
            pack_path, pack_document = pack_entry
            used_pack_paths.append(pack_path)
            for raw_source in _sequence(pack_document.get("sources")):
                archive = _string(_mapping(raw_source).get("archive_path"))
                if _safe_relative_path(archive):
                    source_archive_paths.append(root / archive)
            result = evaluate_evidence_pack(
                contract,
                pack_document,
                pack_source_path=pack_path,
                repo_root=root,
                policy_document=policy_document,
                verify_paths=verify_paths,
            )
        results.append(result)

    case_ids = {contract.case_id for contract in contracts}
    orphan_packs = sorted(set(pack_by_case).difference(case_ids))
    if orphan_packs:
        raise QualificationContractError(
            "reviewed evidence packs reference unknown cases: " + ", ".join(orphan_packs)
        )

    suite = QualificationSuite(
        schema_version=SCHEMA_VERSION,
        bundle_id=BUNDLE_ID,
        case_results=tuple(results),
        input_contract_passed=all(result.input_contract_valid for result in results),
        case_count=len(results),
        evidence_pack_present_count=sum(result.evidence_pack_present for result in results),
        evidence_pack_complete_count=sum(result.evidence_pack_complete for result in results),
        bundle14r_candidate_ready_count=sum(result.bundle14r_candidate_ready for result in results),
        issue_count=sum(len(result.issues) for result in results),
        blocker_count=sum(
            1 for result in results for issue in result.issues if issue.severity == "blocker"
        ),
        conflict_count=sum(result.conflict_count for result in results),
    )
    suite_payload = asdict(suite)
    qualifications = {
        result.case_id: bundle14r_qualification_payload(result) for result in results
    }
    requests = tuple(
        row for result in results for row in _evidence_requests_for_case(result)
    )
    lock = build_generation_lock(
        suite_payload=suite_payload,
        case_paths=[path for path, _ in case_documents],
        pack_paths=used_pack_paths,
        source_archive_paths=source_archive_paths,
        core_paths=core_paths,
        path_root=root,
        extra_inputs=extra_lock_inputs,
    )
    return CompilationArtifacts(
        suite=suite,
        qualification_payloads=qualifications,
        evidence_requests=requests,
        generation_lock=lock,
    )


def load_pack_directory(directory: str | Path | None) -> dict[str, tuple[Path, Mapping[str, Any]]]:
    if directory is None:
        return {}
    result: dict[str, tuple[Path, Mapping[str, Any]]] = {}
    for path in discover_yaml_paths(directory):
        document = load_yaml_document(path)
        case_id = _string(document.get("case_id"))
        if not case_id:
            raise QualificationContractError(f"{path}: case_id is required")
        if case_id in result:
            raise QualificationContractError(f"duplicate reviewed evidence pack for case {case_id}")
        result[case_id] = (path, document)
    return result


def scaffold_pack(contract: CaseContract) -> dict[str, Any]:
    """Create a deterministic, visibly incomplete intake template for a case."""

    records = []
    question_cycle = list(contract.research_question_ids)
    for index, driver_id in enumerate(contract.required_driver_ids):
        question_refs = [question_cycle[index % len(question_cycle)]] if question_cycle else []
        records.append(
            {
                "record_id": f"TODO_{driver_id}",
                "driver_id": driver_id,
                "question_ids": question_refs,
                "status": "blocked",
                "value": None,
                "unit": "TODO",
                "period": "TODO",
                "definition": "TODO: replace with reviewed operating definition",
                "confidence": "low",
                "review_status": "accepted_with_limitations",
                "source_ids": [],
                "overlap_rule": "TODO",
                "stale_trigger": "TODO",
            }
        )
    return {
        "schema_version": PACK_SCHEMA_VERSION,
        "case_id": contract.case_id,
        "issuer": {"ticker": contract.issuer_ticker},
        "as_of_date": "1970-01-01",
        "review": {
            "status": "pending",
            "reviewer": None,
            "reviewed_at": None,
        },
        "sources": [],
        "records": records,
        "overlap_reconciliation": {
            "status": "blocked",
            "revenue_overlap_resolved": False,
            "gross_profit_overlap_resolved": False,
            "unresolved_items": ["TODO: reconcile segment and cross-cutting economics"],
        },
        "forecast_bridge": {
            "status": "blocked",
            "driver_to_statement_reconciliation": False,
            "working_capital_bridge": False,
            "cash_flow_bridge": False,
            "segment_revenue_coverage": 0.0,
            "segment_gross_profit_coverage": 0.0,
        },
        "valuation": {"methods": []},
        "semantic_candidate": {
            "status": "pending",
            "semantic_gate_path": None,
            "semantic_gate_sha256": None,
        },
        "determinism": {
            "rerun_hash_equal": False,
            "input_lock_complete": False,
            "output_lock_complete": False,
        },
        "exact_hash_human_review": {"status": "not_triggered"},
        "release": {
            "sample_quality_allowed": False,
            "p2_allowed": False,
            "workflow_state_mutation_allowed": False,
        },
    }


def write_evidence_request_csv(path: str | Path, rows: Iterable[Mapping[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "case_id",
        "issuer_ticker",
        "issue_code",
        "stage",
        "skill",
        "owner",
        "path",
        "request",
        "status",
    ]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_conflict_csv(path: str | Path, results: Iterable[CaseQualification]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "case_id",
        "driver_id",
        "period",
        "unit",
        "definition",
        "record_ids",
        "normalized_values",
    ]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            for conflict in result.conflicts:
                writer.writerow(
                    {
                        "case_id": conflict.case_id,
                        "driver_id": conflict.driver_id,
                        "period": conflict.period,
                        "unit": conflict.unit,
                        "definition": conflict.definition,
                        "record_ids": "|".join(conflict.record_ids),
                        "normalized_values": "|".join(conflict.normalized_values),
                    }
                )


def write_status_proposal(path: str | Path, artifacts: CompilationArtifacts, *, git_head: str) -> None:
    """Write a non-canonical status proposal without mutating workflow state."""

    proposal = {
        "artifact_type": "R5_bundle15r_noncanonical_status_proposal",
        "schema_version": "r5_bundle15r_status_proposal_v1",
        "git_head": git_head,
        "bundle_id": artifacts.suite.bundle_id,
        "proposed_execution_state": (
            "R5_BUNDLE15R_QUALIFICATION_READY_FOR_SELECTIVE_BUNDLE14R"
            if artifacts.suite.bundle14r_candidate_ready_count > 0
            else "R5_BUNDLE15R_WAITING_FOR_REVIEWED_OFFICIAL_EVIDENCE"
        ),
        "case_count": artifacts.suite.case_count,
        "evidence_pack_present_count": artifacts.suite.evidence_pack_present_count,
        "evidence_pack_complete_count": artifacts.suite.evidence_pack_complete_count,
        "bundle14r_candidate_ready_count": artifacts.suite.bundle14r_candidate_ready_count,
        "blocker_count": artifacts.suite.blocker_count,
        "conflict_count": artifacts.suite.conflict_count,
        "generation_id": artifacts.generation_lock["generation_id"],
        "canonical_workflow_state_mutation_allowed": False,
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "note": (
            "This is a proposed status artifact only. The research-orchestrator must review "
            "it before any later canonical status synchronization."
        ),
    }
    write_yaml(path, proposal)


def write_readout(path: str | Path, artifacts: CompilationArtifacts, *, git_head: str) -> None:
    rows = []
    for result in artifacts.suite.case_results:
        rows.append(
            "| {case} | {decision} | {sources} | {qualified}/{required} | {questions:.0%} | {candidate} |".format(
                case=result.case_id,
                decision=result.decision,
                sources=result.reviewed_official_source_count,
                qualified=len(result.qualified_driver_ids),
                required=len(result.required_driver_ids),
                questions=result.question_coverage_ratio,
                candidate="yes" if result.bundle14r_candidate_ready else "no",
            )
        )
    text = f"""# R5 Bundle 15R Reviewed-Evidence Qualification Readout

- Git HEAD: `{git_head}`
- Generation ID: `{artifacts.generation_lock['generation_id']}`
- Input contract passed: `{str(artifacts.suite.input_contract_passed).lower()}`
- Cases: `{artifacts.suite.case_count}`
- Evidence packs present / complete: `{artifacts.suite.evidence_pack_present_count}` / `{artifacts.suite.evidence_pack_complete_count}`
- Ready to feed Bundle 14R: `{artifacts.suite.bundle14r_candidate_ready_count}`
- Open blockers: `{artifacts.suite.blocker_count}`
- Conflicts: `{artifacts.suite.conflict_count}`
- Automated release authority: `false`
- `sample_quality_allowed`: `false`
- `p2_allowed`: `false`
- Canonical workflow-state mutation: `false`

## Case matrix

| Case | Decision | Reviewed official sources | Qualified drivers | Questions | Bundle 14R ready |
|---|---|---:|---:|---:|---:|
{chr(10).join(rows)}

## Meaning

Bundle 15R only compiles already-reviewed, physically archived evidence into the qualification
mapping consumed by Bundle 14R. A case that remains blocked is a truthful outcome. This readout
does not claim that any official evidence was acquired, any Reader was accepted, sample quality
was released, or P2 was authorized.
"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")


def write_compilation_outputs(
    output_dir: str | Path,
    artifacts: CompilationArtifacts,
    *,
    git_head: str = "unknown",
) -> None:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    qualification_dir = root / "qualification"
    audit_dir = root / "audit"
    for result in artifacts.suite.case_results:
        write_yaml(
            qualification_dir / f"{result.case_id}.yaml",
            artifacts.qualification_payloads[result.case_id],
        )
        write_json(audit_dir / f"{result.case_id}_qualification_audit.json", asdict(result))
    write_json(root / "R5_bundle15r_qualification_suite.json", asdict(artifacts.suite))
    write_json(root / "R5_bundle15r_generation_lock.json", artifacts.generation_lock)
    write_evidence_request_csv(root / "R5_bundle15r_evidence_request_queue.csv", artifacts.evidence_requests)
    write_conflict_csv(root / "R5_bundle15r_conflict_ledger.csv", artifacts.suite.case_results)
    write_status_proposal(root / "R5_bundle15r_status_proposal.yaml", artifacts, git_head=git_head)
    write_readout(root / "R5_bundle15r_close_readout.md", artifacts, git_head=git_head)


__all__ = [
    "BUNDLE14R_QUALIFICATION_SCHEMA_VERSION",
    "BUNDLE_ID",
    "CaseContract",
    "CaseQualification",
    "CompilationArtifacts",
    "PACK_SCHEMA_VERSION",
    "QualificationContractError",
    "QualificationIssue",
    "QualificationSuite",
    "SCHEMA_VERSION",
    "bundle14r_qualification_payload",
    "compile_qualification_suite",
    "discover_yaml_paths",
    "evaluate_evidence_pack",
    "extract_case_contract",
    "load_pack_directory",
    "load_yaml_document",
    "scaffold_pack",
    "sha256_file",
    "write_compilation_outputs",
    "write_json",
    "write_status_proposal",
    "write_yaml",
]
