"""Bundle 16R reviewed-evidence pack materializer.

This module closes a narrow runtime gap between the repository's reviewed evidence
catalogs and the Bundle 15R reviewed-evidence-pack contract.  It is intentionally
issuer-neutral, deterministic, fail-closed, and release-inert.

It does not fetch evidence, review evidence, invent values, mutate canonical
workflow state, generate a Reader, accept human review, or authorize sample
quality/P2.  Missing or ambiguous inputs become source requests, mapping tasks,
and owner/stage backflow rows.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

import yaml

BUNDLE_ID = "R5_BUNDLE16R_REVIEWED_EVIDENCE_PACK_MATERIALIZATION"
SCHEMA_VERSION = "r5_bundle16r_materialization_suite_v1"
MAPPING_SCHEMA_VERSION = "r5_bundle16r_review_mapping_v1"
PACK_SCHEMA_VERSION = "r5_bundle15r_reviewed_evidence_pack_v1"
GENERATION_LOCK_SCHEMA_VERSION = "r5_bundle16r_generation_lock_v1"

ALLOWED_REVIEW_STATUSES = {"accepted", "accepted_with_limitations"}
ALLOWED_RECORD_STATUSES = {
    "confirmed",
    "bounded_estimate",
    "context_only",
    "blocked",
    "not_applicable",
}
QUALIFYING_RECORD_STATUSES = {"confirmed", "bounded_estimate"}
ALLOWED_CONFIDENCE = {"high", "medium", "low", "unknown"}
ALLOWED_HUMAN_REVIEW_STATUSES = {"not_triggered", "pending", "accepted", "rejected"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DEFAULT_POLICY: dict[str, Any] = {
    "schema_version": "r5_bundle16r_materialization_policy_v1",
    "allowed_catalog_extensions": [".yaml", ".yml", ".json", ".csv"],
    "required_source_official": True,
    "allowed_review_statuses": sorted(ALLOWED_REVIEW_STATUSES),
    "qualifying_confidence": ["high", "medium"],
    "require_physical_source_hash": True,
    "require_pack_review_identity": True,
    "forbidden_path_fragments": [
        "个股研究报告样例",
        "个股研究案例样例",
        "narrative_sample",
        "sample_report",
        "reports/samples",
    ],
    "release": {
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "workflow_state_mutation_allowed": False,
    },
}

SOURCE_ID_ALIASES = ("source_id", "evidence_id", "evidence_source_id", "id")
SOURCE_CLASS_ALIASES = ("source_class", "source_type", "evidence_type", "type")
SOURCE_PATH_ALIASES = (
    "archive_path",
    "source_path",
    "raw_file_path",
    "raw_path",
    "raw_snapshot_path",
    "file_path",
    "path",
)
SOURCE_HASH_ALIASES = (
    "sha256",
    "source_sha256",
    "file_sha256",
    "content_sha256",
    "file_hash",
    "content_hash",
)
SOURCE_REVIEW_ALIASES = ("review_status", "status")
SOURCE_PUBLICATION_DATE_ALIASES = (
    "publication_date",
    "publish_date",
    "published_at",
    "filing_date",
    "date",
)
SOURCE_COVERED_PERIOD_ALIASES = ("covered_period", "period", "reporting_period", "as_of_date")

RECORD_ID_ALIASES = ("record_id", "metric_id", "claim_id", "candidate_id", "id")
RECORD_SOURCE_IDS_ALIASES = (
    "source_ids",
    "evidence_ids",
    "source_evidence_ids",
    "evidence_id",
    "source_id",
)
RECORD_REVIEW_ALIASES = ("review_status", "promotion_status", "status")
RECORD_VALUE_ALIASES = ("value", "normalized_value", "metric_value", "claim_value")
RECORD_UNIT_ALIASES = ("unit", "normalized_unit")
RECORD_PERIOD_ALIASES = ("period", "covered_period", "reporting_period", "as_of_date")
RECORD_DEFINITION_ALIASES = (
    "definition",
    "operating_definition",
    "metric_definition",
    "claim",
    "text",
    "name",
)
RECORD_CONFIDENCE_ALIASES = ("confidence", "confidence_level")

FORBIDDEN_RECORD_BINDING_KEYS = {
    "value",
    "unit",
    "period",
    "definition",
    "confidence",
    "source_ids",
    "evidence_ids",
}


class MaterializationContractError(ValueError):
    """Raised when a Bundle 16R input contract is structurally invalid."""


@dataclass(frozen=True)
class MaterializationIssue:
    case_id: str
    code: str
    severity: str
    field: str
    message: str
    owner_skill: str
    target_stage: str
    requested_evidence: str = ""


@dataclass(frozen=True)
class CaseContract:
    case_id: str
    issuer_name: str
    issuer_ticker: str
    required_source_classes: tuple[str, ...]
    driver_ids: tuple[str, ...]
    required_question_ids: tuple[str, ...]
    question_to_drivers: dict[str, tuple[str, ...]]
    backflow_routes: dict[str, dict[str, str]]
    source_path: str
    source_sha256: str


@dataclass
class Catalog:
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    input_paths: tuple[str, ...] = ()
    input_sha256: dict[str, str] = field(default_factory=dict)
    issues: list[MaterializationIssue] = field(default_factory=list)
    duplicate_source_count: int = 0
    duplicate_record_count: int = 0


@dataclass
class CaseMaterializationResult:
    case_id: str
    issuer_name: str
    issuer_ticker: str
    mapping_present: bool
    mapping_valid: bool
    pack_materialized: bool
    pack_schema_version: str
    bound_source_count: int
    required_source_class_count: int
    covered_source_classes: tuple[str, ...]
    missing_source_classes: tuple[str, ...]
    bound_record_count: int
    required_driver_count: int
    qualifying_driver_ids: tuple[str, ...]
    missing_driver_ids: tuple[str, ...]
    required_question_count: int
    classified_question_ids: tuple[str, ...]
    missing_question_ids: tuple[str, ...]
    artifact_block_status: dict[str, str]
    issue_count: int
    blocker_count: int
    decision: str
    pack_relative_path: str | None
    pack_sha256: str | None
    issues: list[MaterializationIssue]


@dataclass
class MaterializationSuite:
    schema_version: str
    bundle_id: str
    baseline_commit: str
    case_count: int
    mapping_present_count: int
    pack_materialized_count: int
    fully_mapped_case_count: int
    blocker_count: int
    source_request_count: int
    mapping_task_count: int
    decision: str
    canonical_workflow_state_mutation_allowed: bool
    sample_quality_allowed: bool
    p2_allowed: bool
    cases: list[CaseMaterializationResult]


@dataclass
class MaterializationArtifacts:
    suite: MaterializationSuite
    packs: dict[str, dict[str, Any]]
    source_requests: list[dict[str, str]]
    mapping_tasks: list[dict[str, str]]
    backflow_rows: list[dict[str, str]]
    inventory: dict[str, Any]
    status_proposal: dict[str, Any]
    generation_lock: dict[str, Any]


def _string(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _pick(mapping: Mapping[str, Any], aliases: Sequence[str], default: Any = "") -> Any:
    for key in aliases:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return default


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    return _string(value).lower() in {"1", "true", "yes", "y", "accepted", "official"}


def _valid_date(value: str) -> bool:
    if not DATE_RE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _valid_datetime(value: str) -> bool:
    if not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _parse_scalar(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if stripped == "":
        return ""
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    lowered = stripped.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        number = float(stripped)
        if math.isfinite(number):
            return int(number) if number.is_integer() else number
    except ValueError:
        pass
    return stripped


def _parse_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    try:
        decoded = json.loads(text)
        if isinstance(decoded, list):
            return [str(item).strip() for item in decoded if str(item).strip()]
    except json.JSONDecodeError:
        pass
    separator = ";" if ";" in text else ","
    return [part.strip() for part in text.split(separator) if part.strip()]


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative_path(value: str) -> bool:
    text = value.replace("\\", "/").strip()
    if not text or text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        return False
    path = PurePosixPath(text)
    return not path.is_absolute() and ".." not in path.parts and "." != text


def _repo_relative_path(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _resolve_repo_path(repo_root: Path, relative_path: str) -> Path:
    if not _safe_relative_path(relative_path):
        raise MaterializationContractError(f"unsafe repository-relative path: {relative_path!r}")
    resolved = (repo_root / relative_path.replace("\\", "/")).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise MaterializationContractError(f"path escapes repository root: {relative_path!r}") from exc
    return resolved


def load_document(path: str | Path) -> Any:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".json":
        return json.loads(source.read_text(encoding="utf-8"))
    if suffix in {".yaml", ".yml"}:
        return yaml.safe_load(source.read_text(encoding="utf-8"))
    if suffix == ".csv":
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    raise MaterializationContractError(f"unsupported input format: {source}")


def discover_document_paths(path: str | Path | None, *, extensions: Iterable[str]) -> list[Path]:
    if path is None:
        return []
    root = Path(path)
    allowed = {item.lower() for item in extensions}
    if root.is_file():
        return [root] if root.suffix.lower() in allowed else []
    if not root.exists():
        return []
    return sorted(
        candidate
        for candidate in root.rglob("*")
        if candidate.is_file() and candidate.suffix.lower() in allowed
    )


def _policy(document: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = json.loads(json.dumps(DEFAULT_POLICY, ensure_ascii=False))
    if document:
        for key, value in document.items():
            if key == "release":
                continue
            merged[key] = value
    merged["release"] = dict(DEFAULT_POLICY["release"])
    return merged


def _forbidden_path(path: str, policy: Mapping[str, Any]) -> bool:
    lowered = path.replace("\\", "/").lower()
    return any(_string(fragment).lower() in lowered for fragment in _sequence(policy.get("forbidden_path_fragments")))


def _issue_route(contract: CaseContract, code: str) -> tuple[str, str]:
    route_key = "EVIDENCE_MISSING"
    if code.startswith("RECORD_") or code.startswith("QUESTION_") or code.startswith("DRIVER_"):
        route_key = "DRIVER_UNQUALIFIED"
    elif code.startswith("OVERLAP_"):
        route_key = "OVERLAP_UNRESOLVED"
    elif code.startswith("FORECAST_") or code.startswith("VALUATION_"):
        route_key = "VALUATION_INELIGIBLE"
    elif code.startswith("SEMANTIC_") or code.startswith("DETERMINISM_") or code.startswith("HUMAN_"):
        route_key = "SEMANTIC_QUALITY_FAILED"
    route = _mapping(contract.backflow_routes.get(route_key))
    default_stage = {
        "EVIDENCE_MISSING": "T1_evidence_plan",
        "DRIVER_UNQUALIFIED": "T2_evidence_acquire_parse",
        "OVERLAP_UNRESOLVED": "T5_analysis_pack_build",
        "VALUATION_INELIGIBLE": "T6_forecast_valuation_model",
        "SEMANTIC_QUALITY_FAILED": "T9_quality_review",
    }[route_key]
    default_skill = {
        "EVIDENCE_MISSING": "evidence-ingest",
        "DRIVER_UNQUALIFIED": "evidence-ingest",
        "OVERLAP_UNRESOLVED": "stock-deep-dive",
        "VALUATION_INELIGIBLE": "valuation-model",
        "SEMANTIC_QUALITY_FAILED": "quality-review",
    }[route_key]
    return _string(route.get("skill")) or default_skill, _string(route.get("stage")) or default_stage


def make_issue(
    contract: CaseContract,
    code: str,
    field: str,
    message: str,
    *,
    severity: str = "blocker",
    requested_evidence: str = "",
) -> MaterializationIssue:
    owner, stage = _issue_route(contract, code)
    return MaterializationIssue(
        case_id=contract.case_id,
        code=code,
        severity=severity,
        field=field,
        message=message,
        owner_skill=owner,
        target_stage=stage,
        requested_evidence=requested_evidence,
    )


def extract_case_contract(document: Mapping[str, Any], *, source_path: Path, repo_root: Path) -> CaseContract:
    case_id = _string(document.get("case_id"))
    issuer = _mapping(document.get("issuer"))
    ticker = _string(issuer.get("ticker"))
    name = _string(issuer.get("name"))
    if not case_id or not ticker:
        raise MaterializationContractError(f"invalid Bundle 14R case contract: {source_path}")

    drivers: list[str] = []
    for raw in _sequence(document.get("drivers")):
        driver_id = _string(_mapping(raw).get("driver_id"))
        if driver_id:
            drivers.append(driver_id)
    if not drivers:
        for archetype in _sequence(document.get("economic_archetypes")):
            drivers.extend(_parse_list(_mapping(archetype).get("required_driver_ids")))
    drivers = sorted(set(drivers))

    question_to_drivers: dict[str, tuple[str, ...]] = {}
    required_questions: list[str] = []
    for raw in _sequence(document.get("research_questions")):
        row = _mapping(raw)
        question_id = _string(row.get("question_id"))
        if not question_id:
            continue
        question_to_drivers[question_id] = tuple(sorted(set(_parse_list(row.get("driver_ids")))))
        if row.get("required") is not False:
            required_questions.append(question_id)

    required_source_classes = tuple(sorted(set(_parse_list(document.get("required_source_classes")))))
    backflow_routes = {
        str(key): dict(_mapping(value)) for key, value in _mapping(document.get("backflow_routes")).items()
    }
    return CaseContract(
        case_id=case_id,
        issuer_name=name,
        issuer_ticker=ticker,
        required_source_classes=required_source_classes,
        driver_ids=tuple(drivers),
        required_question_ids=tuple(sorted(set(required_questions))),
        question_to_drivers=question_to_drivers,
        backflow_routes=backflow_routes,
        source_path=_repo_relative_path(source_path, repo_root),
        source_sha256=sha256_file(source_path),
    )


def load_case_contracts(cases_dir: str | Path, *, repo_root: Path) -> list[CaseContract]:
    paths = discover_document_paths(cases_dir, extensions={".yaml", ".yml"})
    if not paths:
        raise MaterializationContractError(f"no Bundle 14R case contracts found under {cases_dir}")
    contracts = [
        extract_case_contract(_mapping(load_document(path)), source_path=path, repo_root=repo_root)
        for path in paths
    ]
    case_ids = [item.case_id for item in contracts]
    if len(case_ids) != len(set(case_ids)):
        raise MaterializationContractError("duplicate case_id in Bundle 14R case contracts")
    return sorted(contracts, key=lambda item: item.case_id)


def _normalize_source(raw: Mapping[str, Any], *, origin_path: str, origin_index: int) -> dict[str, Any] | None:
    source_id = _string(_pick(raw, SOURCE_ID_ALIASES))
    archive_path = _string(_pick(raw, SOURCE_PATH_ALIASES))
    content_hash = _string(_pick(raw, SOURCE_HASH_ALIASES)).lower()
    if not source_id or not archive_path or not content_hash:
        return None
    source_type = _string(raw.get("source_type")).lower()
    source_group = _string(raw.get("source_group")).lower()
    source_class = _string(_pick(raw, SOURCE_CLASS_ALIASES))
    official = (
        _bool(raw.get("official"))
        or source_group == "official_disclosure"
        or source_class.lower() in {"official", "official_disclosure"}
    )
    if official and (
        source_class.lower() in {"official", "official_disclosure"}
        or source_type
        in {
            "annual_report",
            "interim_report",
            "quarterly_report",
            "announcement",
            "official_disclosure",
        }
    ):
        source_class = "issuer_exchange_filings"
    return {
        "source_id": source_id,
        "source_class": source_class,
        "official": official,
        "review_status": _string(_pick(raw, SOURCE_REVIEW_ALIASES)).lower(),
        "archive_path": archive_path.replace("\\", "/"),
        "sha256": content_hash,
        "publication_date": _string(_pick(raw, SOURCE_PUBLICATION_DATE_ALIASES)),
        "covered_period": _string(_pick(raw, SOURCE_COVERED_PERIOD_ALIASES)),
        "locator": _string(raw.get("locator")),
        "limitations": _string(raw.get("limitations")),
        "_origin_path": origin_path,
        "_origin_index": origin_index,
    }


def _normalize_record(raw: Mapping[str, Any], *, origin_path: str, origin_index: int) -> dict[str, Any] | None:
    record_id = _string(_pick(raw, RECORD_ID_ALIASES))
    if not record_id:
        return None
    source_ids = _parse_list(_pick(raw, RECORD_SOURCE_IDS_ALIASES))
    value = _parse_scalar(_pick(raw, RECORD_VALUE_ALIASES, None))
    definition = _string(_pick(raw, RECORD_DEFINITION_ALIASES))
    # Avoid treating a pure source-manifest row as an operating record.
    if not source_ids and value is None and not definition:
        return None
    status = _string(raw.get("record_status") or raw.get("classification_status") or "confirmed").lower()
    if status not in ALLOWED_RECORD_STATUSES:
        status = "confirmed"
    return {
        "record_id": record_id,
        "status": status,
        "value": value,
        "unit": _string(_pick(raw, RECORD_UNIT_ALIASES)),
        "period": _string(_pick(raw, RECORD_PERIOD_ALIASES)),
        "definition": definition,
        "confidence": _string(_pick(raw, RECORD_CONFIDENCE_ALIASES, "unknown")).lower() or "unknown",
        "review_status": _string(_pick(raw, RECORD_REVIEW_ALIASES)).lower(),
        "source_ids": source_ids,
        "_origin_path": origin_path,
        "_origin_index": origin_index,
    }


def _iter_catalog_rows(document: Any) -> Iterable[tuple[str, Mapping[str, Any]]]:
    if isinstance(document, list):
        for item in document:
            if isinstance(item, Mapping):
                yield "auto", item
        return
    if not isinstance(document, Mapping):
        return
    section_map = {
        "sources": "source",
        "evidence": "source",
        "evidence_sources": "source",
        "source_records": "source",
        "records": "record",
        "claims": "record",
        "metrics": "record",
        "claim_candidates": "record",
        "metric_candidates": "record",
        "company_metrics": "record",
    }
    emitted = False
    for key, kind in section_map.items():
        value = document.get(key)
        if isinstance(value, list):
            emitted = True
            for item in value:
                if isinstance(item, Mapping):
                    yield kind, item
    if not emitted:
        yield "auto", document


def _dedupe_insert(
    target: MutableMapping[str, dict[str, Any]],
    key: str,
    value: dict[str, Any],
) -> tuple[bool, bool]:
    """Return (inserted, duplicate_equal). Raise on a conflicting duplicate."""
    if key not in target:
        target[key] = value
        return True, False
    existing = {k: v for k, v in target[key].items() if not k.startswith("_origin")}
    incoming = {k: v for k, v in value.items() if not k.startswith("_origin")}
    if canonical_json_bytes(existing) == canonical_json_bytes(incoming):
        return False, True
    raise MaterializationContractError(f"conflicting duplicate catalog ID: {key}")


def load_catalog(
    catalog_paths: Sequence[Path],
    *,
    repo_root: Path,
    policy_document: Mapping[str, Any] | None = None,
) -> Catalog:
    policy = _policy(policy_document)
    catalog = Catalog()
    input_paths: list[str] = []
    input_sha: dict[str, str] = {}
    for path in sorted(set(item.resolve() for item in catalog_paths)):
        relative = _repo_relative_path(path, repo_root)
        input_paths.append(relative)
        input_sha[relative] = sha256_file(path)
        document = load_document(path)
        for index, (kind, raw) in enumerate(_iter_catalog_rows(document)):
            if kind in {"source", "auto"}:
                source = _normalize_source(raw, origin_path=relative, origin_index=index)
                if source:
                    try:
                        _, duplicate = _dedupe_insert(catalog.sources, source["source_id"], source)
                    except MaterializationContractError as exc:
                        catalog.issues.append(
                            MaterializationIssue(
                                case_id="*",
                                code="CATALOG_SOURCE_CONFLICT",
                                severity="blocker",
                                field=source["source_id"],
                                message=str(exc),
                                owner_skill="evidence-ingest",
                                target_stage="T2_evidence_acquire_parse",
                            )
                        )
                    else:
                        catalog.duplicate_source_count += int(duplicate)
            if kind in {"record", "auto"}:
                record = _normalize_record(raw, origin_path=relative, origin_index=index)
                if record:
                    try:
                        _, duplicate = _dedupe_insert(catalog.records, record["record_id"], record)
                    except MaterializationContractError as exc:
                        catalog.issues.append(
                            MaterializationIssue(
                                case_id="*",
                                code="CATALOG_RECORD_CONFLICT",
                                severity="blocker",
                                field=record["record_id"],
                                message=str(exc),
                                owner_skill="evidence-ingest",
                                target_stage="T2_evidence_acquire_parse",
                            )
                        )
                    else:
                        catalog.duplicate_record_count += int(duplicate)
    catalog.input_paths = tuple(input_paths)
    catalog.input_sha256 = input_sha
    return catalog


def load_mappings(mapping_paths: Sequence[Path]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    by_case: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    for path in sorted(set(item.resolve() for item in mapping_paths)):
        document = load_document(path)
        documents: list[Mapping[str, Any]] = []
        if isinstance(document, Mapping) and isinstance(document.get("cases"), list):
            documents.extend(item for item in document["cases"] if isinstance(item, Mapping))
        elif isinstance(document, Mapping):
            documents.append(document)
        else:
            raise MaterializationContractError(f"review mapping is not an object: {path}")
        for mapping in documents:
            case_id = _string(mapping.get("case_id"))
            if not case_id:
                raise MaterializationContractError(f"review mapping missing case_id: {path}")
            if case_id in by_case:
                raise MaterializationContractError(f"duplicate review mapping for case: {case_id}")
            payload = dict(mapping)
            payload["_source_path"] = str(path)
            by_case[case_id] = payload
        hashes[str(path)] = sha256_file(path)
    return by_case, hashes


def _validate_mapping_identity(
    contract: CaseContract,
    mapping: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    issues: list[MaterializationIssue],
) -> tuple[bool, dict[str, str]]:
    valid = True
    if _string(mapping.get("schema_version")) != MAPPING_SCHEMA_VERSION:
        issues.append(
            make_issue(
                contract,
                "REVIEW_MAPPING_INVALID",
                "schema_version",
                f"expected {MAPPING_SCHEMA_VERSION}",
            )
        )
        valid = False
    if _string(mapping.get("case_id")) != contract.case_id:
        issues.append(make_issue(contract, "REVIEW_MAPPING_INVALID", "case_id", "mapping case_id mismatch"))
        valid = False
    ticker = _string(mapping.get("issuer_ticker"))
    if ticker and ticker != contract.issuer_ticker:
        issues.append(make_issue(contract, "REVIEW_MAPPING_INVALID", "issuer_ticker", "mapping ticker mismatch"))
        valid = False
    as_of_date = _string(mapping.get("as_of_date"))
    if not _valid_date(as_of_date):
        issues.append(make_issue(contract, "REVIEW_MAPPING_INVALID", "as_of_date", "as_of_date must be YYYY-MM-DD"))
        valid = False
    review = _mapping(mapping.get("pack_review"))
    review_status = _string(review.get("status")).lower()
    reviewer = _string(review.get("reviewer"))
    reviewed_at = _string(review.get("reviewed_at"))
    if review_status not in set(_sequence(policy.get("allowed_review_statuses"))):
        issues.append(
            make_issue(
                contract,
                "REVIEW_MAPPING_UNREVIEWED",
                "pack_review.status",
                "mapping must be accepted or accepted_with_limitations",
            )
        )
        valid = False
    if policy.get("require_pack_review_identity", True) and (not reviewer or not _valid_datetime(reviewed_at)):
        issues.append(
            make_issue(
                contract,
                "REVIEW_MAPPING_UNREVIEWED",
                "pack_review",
                "real reviewer identity and ISO reviewed_at are required",
            )
        )
        valid = False
    return valid, {"status": review_status, "reviewer": reviewer, "reviewed_at": reviewed_at}


def _validate_bound_source(
    contract: CaseContract,
    source: Mapping[str, Any],
    *,
    repo_root: Path,
    policy: Mapping[str, Any],
    issues: list[MaterializationIssue],
    field: str,
) -> bool:
    valid = True
    if policy.get("required_source_official", True) and source.get("official") is not True:
        issues.append(make_issue(contract, "SOURCE_UNQUALIFIED", f"{field}.official", "source is not official"))
        valid = False
    if _string(source.get("review_status")) not in set(_sequence(policy.get("allowed_review_statuses"))):
        issues.append(make_issue(contract, "SOURCE_UNQUALIFIED", f"{field}.review_status", "source is not reviewed"))
        valid = False
    source_class = _string(source.get("source_class"))
    if not source_class:
        issues.append(make_issue(contract, "SOURCE_UNQUALIFIED", f"{field}.source_class", "source_class is required"))
        valid = False
    publication_date = _string(source.get("publication_date"))
    if not _valid_date(publication_date):
        issues.append(
            make_issue(contract, "SOURCE_UNQUALIFIED", f"{field}.publication_date", "publication_date must be YYYY-MM-DD")
        )
        valid = False
    if not _string(source.get("covered_period")):
        issues.append(make_issue(contract, "SOURCE_UNQUALIFIED", f"{field}.covered_period", "covered_period is required"))
        valid = False
    archive_path = _string(source.get("archive_path"))
    expected_hash = _string(source.get("sha256")).lower()
    if _forbidden_path(archive_path, policy):
        issues.append(
            make_issue(
                contract,
                "SAMPLE_PATH_FORBIDDEN",
                f"{field}.archive_path",
                "narrative sample paths cannot be evidence",
            )
        )
        valid = False
    if not _safe_relative_path(archive_path):
        issues.append(make_issue(contract, "SOURCE_PATH_INVALID", f"{field}.archive_path", "unsafe source path"))
        return False
    physical = _resolve_repo_path(repo_root, archive_path)
    if not physical.is_file():
        issues.append(
            make_issue(
                contract,
                "SOURCE_PATH_MISSING",
                f"{field}.archive_path",
                f"physical archived source is missing: {archive_path}",
                requested_evidence=f"Archive and review {source_class} evidence for {contract.issuer_ticker}",
            )
        )
        valid = False
    if not HEX64.fullmatch(expected_hash):
        issues.append(make_issue(contract, "SOURCE_HASH_INVALID", f"{field}.sha256", "sha256 must be 64 lowercase hex"))
        valid = False
    elif physical.is_file() and sha256_file(physical) != expected_hash:
        issues.append(make_issue(contract, "SOURCE_HASH_MISMATCH", f"{field}.sha256", "physical source hash mismatch"))
        valid = False
    return valid


def _extract_pointer(document: Any, pointer: str) -> Any:
    if pointer in ("", "/"):
        return document
    if not pointer.startswith("/"):
        raise MaterializationContractError(f"JSON pointer must start with '/': {pointer!r}")
    current = document
    for token in pointer.split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            if token not in current:
                raise MaterializationContractError(f"JSON pointer token is missing: {token!r}")
            current = current[token]
        elif isinstance(current, list):
            try:
                current = current[int(token)]
            except (ValueError, IndexError) as exc:
                raise MaterializationContractError(f"invalid JSON pointer list token: {token!r}") from exc
        else:
            raise MaterializationContractError(f"JSON pointer traverses a scalar at token: {token!r}")
    return current


def _artifact_binding_block(
    contract: CaseContract,
    key: str,
    binding: Mapping[str, Any],
    *,
    repo_root: Path,
    policy: Mapping[str, Any],
    issues: list[MaterializationIssue],
) -> Mapping[str, Any] | None:
    path = _string(binding.get("artifact_path") or binding.get("path"))
    expected_hash = _string(binding.get("artifact_sha256") or binding.get("sha256")).lower()
    pointer = _string(binding.get("json_pointer") or binding.get("pointer"))
    if not path:
        return None
    if _forbidden_path(path, policy):
        issues.append(make_issue(contract, "SAMPLE_PATH_FORBIDDEN", f"artifact_bindings.{key}", "sample path forbidden"))
        return None
    if not _safe_relative_path(path):
        issues.append(make_issue(contract, f"{key.upper()}_ARTIFACT_INVALID", f"artifact_bindings.{key}.path", "unsafe path"))
        return None
    physical = _resolve_repo_path(repo_root, path)
    if not physical.is_file():
        issues.append(
            make_issue(contract, f"{key.upper()}_ARTIFACT_MISSING", f"artifact_bindings.{key}.path", f"artifact missing: {path}")
        )
        return None
    if not HEX64.fullmatch(expected_hash) or sha256_file(physical) != expected_hash:
        issues.append(
            make_issue(contract, f"{key.upper()}_ARTIFACT_HASH_MISMATCH", f"artifact_bindings.{key}.sha256", "artifact hash mismatch")
        )
        return None
    try:
        document = load_document(physical)
        block = _extract_pointer(document, pointer)
    except (OSError, ValueError, MaterializationContractError, json.JSONDecodeError, yaml.YAMLError) as exc:
        issues.append(
            make_issue(contract, f"{key.upper()}_ARTIFACT_INVALID", f"artifact_bindings.{key}", str(exc))
        )
        return None
    if not isinstance(block, Mapping):
        issues.append(
            make_issue(contract, f"{key.upper()}_ARTIFACT_INVALID", f"artifact_bindings.{key}", "extracted block must be an object")
        )
        return None
    return dict(block)


def _default_blocks() -> dict[str, Any]:
    return {
        "overlap_reconciliation": {
            "status": "blocked",
            "revenue_overlap_resolved": False,
            "gross_profit_overlap_resolved": False,
            "unresolved_items": ["Bundle 16R did not receive a hash-bound overlap artifact"],
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
    }


def _validate_artifact_block(
    contract: CaseContract,
    key: str,
    block: Mapping[str, Any],
    *,
    binding: Mapping[str, Any],
    issues: list[MaterializationIssue],
) -> dict[str, Any] | None:
    if key == "overlap_reconciliation":
        required = {"status", "revenue_overlap_resolved", "gross_profit_overlap_resolved", "unresolved_items"}
        if not required.issubset(block) or _string(block.get("status")) not in {"passed", "blocked"}:
            return None
        return {
            "status": _string(block.get("status")),
            "revenue_overlap_resolved": _bool(block.get("revenue_overlap_resolved")),
            "gross_profit_overlap_resolved": _bool(block.get("gross_profit_overlap_resolved")),
            "unresolved_items": [str(item) for item in _sequence(block.get("unresolved_items"))],
        }
    if key == "forecast_bridge":
        required = {
            "status",
            "driver_to_statement_reconciliation",
            "working_capital_bridge",
            "cash_flow_bridge",
            "segment_revenue_coverage",
            "segment_gross_profit_coverage",
        }
        if not required.issubset(block) or _string(block.get("status")) not in {"passed", "blocked"}:
            return None
        try:
            revenue = float(block["segment_revenue_coverage"])
            gross_profit = float(block["segment_gross_profit_coverage"])
        except (TypeError, ValueError):
            return None
        if not (0 <= revenue <= 1 and 0 <= gross_profit <= 1):
            return None
        return {
            "status": _string(block.get("status")),
            "driver_to_statement_reconciliation": _bool(block.get("driver_to_statement_reconciliation")),
            "working_capital_bridge": _bool(block.get("working_capital_bridge")),
            "cash_flow_bridge": _bool(block.get("cash_flow_bridge")),
            "segment_revenue_coverage": revenue,
            "segment_gross_profit_coverage": gross_profit,
        }
    if key == "valuation":
        methods = block.get("methods")
        if not isinstance(methods, list):
            return None
        return {"methods": [dict(item) for item in methods if isinstance(item, Mapping)]}
    if key == "semantic_candidate":
        status = _string(block.get("status"))
        if status not in {"pending", "passed", "failed"}:
            return None
        path = _string(binding.get("artifact_path") or binding.get("path"))
        expected_hash = _string(binding.get("artifact_sha256") or binding.get("sha256")).lower()
        if status == "passed":
            return {
                "status": "passed",
                "semantic_gate_path": path,
                "semantic_gate_sha256": expected_hash,
            }
        return {"status": status, "semantic_gate_path": None, "semantic_gate_sha256": None}
    if key == "determinism":
        required = {"rerun_hash_equal", "input_lock_complete", "output_lock_complete"}
        if not required.issubset(block):
            return None
        return {name: _bool(block.get(name)) for name in sorted(required)}
    if key == "exact_hash_human_review":
        status = _string(block.get("status")) or "not_triggered"
        if status not in ALLOWED_HUMAN_REVIEW_STATUSES:
            return None
        if status != "accepted":
            return {"status": status}
        reviewer = _string(block.get("reviewer"))
        reviewed_at = _string(block.get("reviewed_at"))
        path = _string(binding.get("artifact_path") or binding.get("path"))
        expected_hash = _string(binding.get("artifact_sha256") or binding.get("sha256")).lower()
        if not reviewer or not _valid_datetime(reviewed_at):
            return None
        return {
            "status": "accepted",
            "reviewer": reviewer,
            "reviewed_at": reviewed_at,
            "review_path": path,
            "review_sha256": expected_hash,
        }
    issues.append(make_issue(contract, "ARTIFACT_BINDING_UNKNOWN", f"artifact_bindings.{key}", "unsupported block"))
    return None


def _materialize_blocks(
    contract: CaseContract,
    mapping: Mapping[str, Any],
    *,
    repo_root: Path,
    policy: Mapping[str, Any],
    issues: list[MaterializationIssue],
) -> tuple[dict[str, Any], dict[str, str]]:
    blocks = _default_blocks()
    status = {key: "default_blocked" for key in blocks}
    bindings = _mapping(mapping.get("artifact_bindings"))
    for key in blocks:
        binding = _mapping(bindings.get(key))
        if not binding:
            code = {
                "overlap_reconciliation": "OVERLAP_ARTIFACT_MISSING",
                "forecast_bridge": "FORECAST_ARTIFACT_MISSING",
                "valuation": "VALUATION_ARTIFACT_MISSING",
                "semantic_candidate": "SEMANTIC_ARTIFACT_MISSING",
                "determinism": "DETERMINISM_ARTIFACT_MISSING",
                "exact_hash_human_review": "HUMAN_REVIEW_ARTIFACT_MISSING",
            }[key]
            severity = "info" if key == "exact_hash_human_review" else "blocker"
            issues.append(make_issue(contract, code, f"artifact_bindings.{key}", "hash-bound artifact not supplied", severity=severity))
            continue
        raw_block = _artifact_binding_block(
            contract,
            key,
            binding,
            repo_root=repo_root,
            policy=policy,
            issues=issues,
        )
        if raw_block is None:
            continue
        validated = _validate_artifact_block(contract, key, raw_block, binding=binding, issues=issues)
        if validated is None:
            code = {
                "overlap_reconciliation": "OVERLAP_ARTIFACT_INVALID",
                "forecast_bridge": "FORECAST_ARTIFACT_INVALID",
                "valuation": "VALUATION_ARTIFACT_INVALID",
                "semantic_candidate": "SEMANTIC_ARTIFACT_INVALID",
                "determinism": "DETERMINISM_ARTIFACT_INVALID",
                "exact_hash_human_review": "HUMAN_REVIEW_ARTIFACT_INVALID",
            }[key]
            issues.append(make_issue(contract, code, f"artifact_bindings.{key}", "artifact block does not match expected contract"))
            continue
        blocks[key] = validated
        status[key] = _string(validated.get("status")) or "bound"
    return blocks, status


def materialize_case(
    contract: CaseContract,
    catalog: Catalog,
    mapping: Mapping[str, Any] | None,
    *,
    repo_root: Path,
    policy_document: Mapping[str, Any] | None = None,
) -> tuple[CaseMaterializationResult, dict[str, Any] | None, list[dict[str, str]], list[dict[str, str]]]:
    policy = _policy(policy_document)
    issues: list[MaterializationIssue] = []
    source_requests: list[dict[str, str]] = []
    mapping_tasks: list[dict[str, str]] = []
    if mapping is None:
        issues.append(
            make_issue(
                contract,
                "REVIEW_MAPPING_MISSING",
                "review_mapping",
                "no reviewed mapping exists for this case",
                requested_evidence="Create an exact reviewer-authored Bundle 16R mapping",
            )
        )
        for source_class in contract.required_source_classes:
            source_requests.append(
                {
                    "case_id": contract.case_id,
                    "issuer_ticker": contract.issuer_ticker,
                    "request_type": "source_class",
                    "request_id": source_class,
                    "owner_skill": "evidence-ingest",
                    "target_stage": "T1_evidence_plan",
                    "request": f"Archive and review one or more physical official sources for {source_class}",
                }
            )
        for driver_id in contract.driver_ids:
            mapping_tasks.append(
                {
                    "case_id": contract.case_id,
                    "issuer_ticker": contract.issuer_ticker,
                    "task_type": "driver_mapping",
                    "task_id": driver_id,
                    "owner_skill": "stock-deep-dive",
                    "target_stage": "T5_analysis_pack_build",
                    "task": "Map a reviewed catalog record to this driver without overriding value/unit/period/definition",
                }
            )
        result = CaseMaterializationResult(
            case_id=contract.case_id,
            issuer_name=contract.issuer_name,
            issuer_ticker=contract.issuer_ticker,
            mapping_present=False,
            mapping_valid=False,
            pack_materialized=False,
            pack_schema_version=PACK_SCHEMA_VERSION,
            bound_source_count=0,
            required_source_class_count=len(contract.required_source_classes),
            covered_source_classes=(),
            missing_source_classes=contract.required_source_classes,
            bound_record_count=0,
            required_driver_count=len(contract.driver_ids),
            qualifying_driver_ids=(),
            missing_driver_ids=contract.driver_ids,
            required_question_count=len(contract.required_question_ids),
            classified_question_ids=(),
            missing_question_ids=contract.required_question_ids,
            artifact_block_status={key: "not_materialized" for key in _default_blocks()},
            issue_count=len(issues),
            blocker_count=sum(item.severity == "blocker" for item in issues),
            decision="review_mapping_required",
            pack_relative_path=None,
            pack_sha256=None,
            issues=issues,
        )
        return result, None, source_requests, mapping_tasks

    mapping_valid, pack_review = _validate_mapping_identity(contract, mapping, policy=policy, issues=issues)
    bound_sources: list[dict[str, Any]] = []
    source_id_map: dict[str, str] = {}
    covered_source_classes: set[str] = set()
    seen_output_source_ids: set[str] = set()
    for index, raw_binding in enumerate(_sequence(mapping.get("source_bindings"))):
        binding = _mapping(raw_binding)
        catalog_source_id = _string(binding.get("catalog_source_id"))
        output_source_id = _string(binding.get("output_source_id")) or catalog_source_id
        field = f"source_bindings[{index}]"
        if not catalog_source_id or catalog_source_id not in catalog.sources:
            issues.append(make_issue(contract, "SOURCE_CATALOG_ID_MISSING", field, f"catalog source not found: {catalog_source_id}"))
            continue
        if output_source_id in seen_output_source_ids:
            issues.append(make_issue(contract, "SOURCE_BINDING_DUPLICATE", field, f"duplicate output source_id: {output_source_id}"))
            continue
        source = catalog.sources[catalog_source_id]
        if not _validate_bound_source(
            contract,
            source,
            repo_root=repo_root,
            policy=policy,
            issues=issues,
            field=field,
        ):
            continue
        seen_output_source_ids.add(output_source_id)
        source_id_map[catalog_source_id] = output_source_id
        covered_source_classes.add(_string(source.get("source_class")))
        bound_sources.append(
            {
                "source_id": output_source_id,
                "source_class": _string(source.get("source_class")),
                "official": True,
                "review_status": _string(source.get("review_status")),
                "archive_path": _string(source.get("archive_path")),
                "sha256": _string(source.get("sha256")),
                "publication_date": _string(source.get("publication_date")),
                "covered_period": _string(source.get("covered_period")),
                "locator": _string(source.get("locator")),
                "limitations": _string(source.get("limitations")),
            }
        )

    missing_source_classes = tuple(sorted(set(contract.required_source_classes).difference(covered_source_classes)))
    for source_class in missing_source_classes:
        issues.append(
            make_issue(
                contract,
                "SOURCE_CLASS_MISSING",
                "source_bindings",
                f"required source class is not bound: {source_class}",
                requested_evidence=f"Archive and review official evidence for source class {source_class}",
            )
        )
        source_requests.append(
            {
                "case_id": contract.case_id,
                "issuer_ticker": contract.issuer_ticker,
                "request_type": "source_class",
                "request_id": source_class,
                "owner_skill": "evidence-ingest",
                "target_stage": "T1_evidence_plan",
                "request": f"Archive, hash and review official evidence for {source_class}",
            }
        )

    bound_records: list[dict[str, Any]] = []
    qualifying_driver_ids: set[str] = set()
    classified_question_ids: set[str] = set()
    seen_output_record_ids: set[str] = set()
    qualifying_confidence = set(_sequence(policy.get("qualifying_confidence")))
    for index, raw_binding in enumerate(_sequence(mapping.get("record_bindings"))):
        binding = _mapping(raw_binding)
        field = f"record_bindings[{index}]"
        forbidden = sorted(FORBIDDEN_RECORD_BINDING_KEYS.intersection(binding))
        if forbidden:
            issues.append(
                make_issue(
                    contract,
                    "RECORD_VALUE_OVERRIDE_FORBIDDEN",
                    field,
                    f"mapping cannot override catalog evidence fields: {', '.join(forbidden)}",
                )
            )
            continue
        catalog_record_id = _string(binding.get("catalog_record_id"))
        output_record_id = _string(binding.get("output_record_id")) or catalog_record_id
        if not catalog_record_id or catalog_record_id not in catalog.records:
            issues.append(make_issue(contract, "RECORD_CATALOG_ID_MISSING", field, f"catalog record not found: {catalog_record_id}"))
            continue
        if output_record_id in seen_output_record_ids:
            issues.append(make_issue(contract, "RECORD_BINDING_DUPLICATE", field, f"duplicate output record_id: {output_record_id}"))
            continue
        driver_id = _string(binding.get("driver_id"))
        if driver_id not in set(contract.driver_ids):
            issues.append(make_issue(contract, "RECORD_DRIVER_UNKNOWN", f"{field}.driver_id", f"unknown driver: {driver_id}"))
            continue
        question_ids = tuple(sorted(set(_parse_list(binding.get("question_ids")))))
        unknown_questions = sorted(set(question_ids).difference(contract.question_to_drivers))
        if unknown_questions:
            issues.append(
                make_issue(contract, "RECORD_QUESTION_UNKNOWN", f"{field}.question_ids", f"unknown questions: {unknown_questions}")
            )
            continue
        record = catalog.records[catalog_record_id]
        review_status = _string(record.get("review_status"))
        if review_status not in set(_sequence(policy.get("allowed_review_statuses"))):
            issues.append(make_issue(contract, "RECORD_UNREVIEWED", f"{field}.review_status", "catalog record is not reviewed"))
            continue
        status = _string(binding.get("status") or record.get("status")).lower()
        if status not in ALLOWED_RECORD_STATUSES:
            issues.append(make_issue(contract, "RECORD_STATUS_INVALID", f"{field}.status", f"unsupported status: {status}"))
            continue
        confidence = _string(record.get("confidence")) or "unknown"
        if confidence not in ALLOWED_CONFIDENCE:
            issues.append(make_issue(contract, "RECORD_CONFIDENCE_INVALID", f"{field}.confidence", f"unsupported confidence: {confidence}"))
            continue
        catalog_source_ids = tuple(sorted(set(_parse_list(record.get("source_ids")))))
        missing_bound_sources = sorted(set(catalog_source_ids).difference(source_id_map))
        if missing_bound_sources:
            issues.append(
                make_issue(
                    contract,
                    "RECORD_SOURCE_UNBOUND",
                    f"{field}.source_ids",
                    f"record sources are not bound: {missing_bound_sources}",
                )
            )
            continue
        if status in QUALIFYING_RECORD_STATUSES:
            required_fields = {
                "value": record.get("value"),
                "unit": _string(record.get("unit")),
                "period": _string(record.get("period")),
                "definition": _string(record.get("definition")),
            }
            missing_fields = [name for name, value in required_fields.items() if value in (None, "")]
            if missing_fields:
                issues.append(
                    make_issue(contract, "RECORD_FIELDS_MISSING", field, f"qualifying record is missing: {missing_fields}")
                )
                continue
            if confidence not in qualifying_confidence:
                issues.append(
                    make_issue(
                        contract,
                        "RECORD_CONFIDENCE_UNQUALIFIED",
                        f"{field}.confidence",
                        f"{status} requires one of {sorted(qualifying_confidence)}",
                    )
                )
                continue
        overlap_rule = _string(binding.get("overlap_rule"))
        stale_trigger = _string(binding.get("stale_trigger"))
        if not overlap_rule or not stale_trigger:
            issues.append(
                make_issue(
                    contract,
                    "RECORD_MAPPING_INCOMPLETE",
                    field,
                    "overlap_rule and stale_trigger are required reviewer-authored mapping fields",
                )
            )
            continue
        seen_output_record_ids.add(output_record_id)
        classified_question_ids.update(question_ids)
        if status in QUALIFYING_RECORD_STATUSES and confidence in qualifying_confidence:
            qualifying_driver_ids.add(driver_id)
        bound_records.append(
            {
                "record_id": output_record_id,
                "driver_id": driver_id,
                "question_ids": list(question_ids),
                "status": status,
                "value": record.get("value"),
                "unit": _string(record.get("unit")),
                "period": _string(record.get("period")),
                "definition": _string(record.get("definition")),
                "confidence": confidence,
                "review_status": review_status,
                "source_ids": [source_id_map[source_id] for source_id in catalog_source_ids],
                "overlap_rule": overlap_rule,
                "stale_trigger": stale_trigger,
                "dependencies": sorted(set(_parse_list(binding.get("dependencies")))),
            }
        )

    missing_driver_ids = tuple(sorted(set(contract.driver_ids).difference(qualifying_driver_ids)))
    for driver_id in missing_driver_ids:
        issues.append(
            make_issue(
                contract,
                "DRIVER_MAPPING_MISSING",
                f"drivers.{driver_id}",
                f"no qualifying reviewed record is mapped to driver {driver_id}",
                requested_evidence=f"Find or classify reviewed evidence for operating driver {driver_id}",
            )
        )
        mapping_tasks.append(
            {
                "case_id": contract.case_id,
                "issuer_ticker": contract.issuer_ticker,
                "task_type": "driver_mapping",
                "task_id": driver_id,
                "owner_skill": "stock-deep-dive",
                "target_stage": "T5_analysis_pack_build",
                "task": "Bind a reviewed high/medium-confidence record to the driver; do not invent a proxy",
            }
        )

    missing_question_ids = tuple(sorted(set(contract.required_question_ids).difference(classified_question_ids)))
    for question_id in missing_question_ids:
        issues.append(
            make_issue(
                contract,
                "QUESTION_MAPPING_MISSING",
                f"research_questions.{question_id}",
                f"required question is not classified: {question_id}",
            )
        )
        mapping_tasks.append(
            {
                "case_id": contract.case_id,
                "issuer_ticker": contract.issuer_ticker,
                "task_type": "question_classification",
                "task_id": question_id,
                "owner_skill": "stock-deep-dive",
                "target_stage": "T5_analysis_pack_build",
                "task": "Classify the question as confirmed, bounded, context-only, blocked or not-applicable",
            }
        )

    blocks, block_status = _materialize_blocks(
        contract,
        mapping,
        repo_root=repo_root,
        policy=policy,
        issues=issues,
    )

    pack: dict[str, Any] | None = None
    if mapping_valid and bound_sources:
        pack = {
            "schema_version": PACK_SCHEMA_VERSION,
            "case_id": contract.case_id,
            "issuer": {"ticker": contract.issuer_ticker},
            "as_of_date": _string(mapping.get("as_of_date")),
            "review": pack_review,
            "sources": sorted(bound_sources, key=lambda item: item["source_id"]),
            "records": sorted(bound_records, key=lambda item: item["record_id"]),
            "overlap_reconciliation": blocks["overlap_reconciliation"],
            "forecast_bridge": blocks["forecast_bridge"],
            "valuation": blocks["valuation"],
            "semantic_candidate": blocks["semantic_candidate"],
            "determinism": blocks["determinism"],
            "exact_hash_human_review": blocks["exact_hash_human_review"],
            "release": dict(DEFAULT_POLICY["release"]),
        }

    blocker_count = sum(item.severity == "blocker" for item in issues)
    all_mapping_complete = (
        mapping_valid
        and not missing_source_classes
        and not missing_driver_ids
        and not missing_question_ids
        and not any(item.code.startswith("CATALOG_") and item.severity == "blocker" for item in issues)
    )
    if not mapping_valid:
        decision = "review_mapping_invalid"
    elif all_mapping_complete and blocker_count == 0:
        decision = "pack_ready_for_bundle15r_qualification"
    elif pack is not None:
        decision = "pack_materialized_with_targeted_backflow"
    else:
        decision = "pack_not_materialized"

    result = CaseMaterializationResult(
        case_id=contract.case_id,
        issuer_name=contract.issuer_name,
        issuer_ticker=contract.issuer_ticker,
        mapping_present=True,
        mapping_valid=mapping_valid,
        pack_materialized=pack is not None,
        pack_schema_version=PACK_SCHEMA_VERSION,
        bound_source_count=len(bound_sources),
        required_source_class_count=len(contract.required_source_classes),
        covered_source_classes=tuple(sorted(covered_source_classes)),
        missing_source_classes=missing_source_classes,
        bound_record_count=len(bound_records),
        required_driver_count=len(contract.driver_ids),
        qualifying_driver_ids=tuple(sorted(qualifying_driver_ids)),
        missing_driver_ids=missing_driver_ids,
        required_question_count=len(contract.required_question_ids),
        classified_question_ids=tuple(sorted(classified_question_ids)),
        missing_question_ids=missing_question_ids,
        artifact_block_status=block_status,
        issue_count=len(issues),
        blocker_count=blocker_count,
        decision=decision,
        pack_relative_path=f"pack_candidates/{contract.case_id}.yaml" if pack is not None else None,
        pack_sha256=sha256_bytes(yaml.safe_dump(pack, allow_unicode=True, sort_keys=True).encode("utf-8")) if pack is not None else None,
        issues=issues,
    )
    return result, pack, source_requests, mapping_tasks


def _status_proposal(suite: MaterializationSuite) -> dict[str, Any]:
    if suite.pack_materialized_count == 0:
        proposed = "R5_BUNDLE16R_WAITING_FOR_REVIEWED_EVIDENCE_AND_MAPPING"
    elif suite.fully_mapped_case_count < suite.case_count:
        proposed = "R5_BUNDLE16R_PARTIAL_PACKS_READY_FOR_15R"
    else:
        proposed = "R5_BUNDLE16R_ALL_PACKS_READY_FOR_15R_QUALIFICATION"
    return {
        "schema_version": "r5_bundle16r_status_proposal_v1",
        "bundle_id": BUNDLE_ID,
        "proposed_status": proposed,
        "canonical_workflow_state_mutation_allowed": False,
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "note": (
            "Non-canonical proposal only. Run Bundle 15R and, when applicable, Bundle 14R before any "
            "research-orchestrator state synchronization."
        ),
    }


def materialize_suite(
    *,
    repo_root: Path,
    cases_dir: Path,
    catalog_paths: Sequence[Path],
    mapping_paths: Sequence[Path],
    policy_document: Mapping[str, Any] | None,
    baseline_commit: str,
) -> MaterializationArtifacts:
    contracts = load_case_contracts(cases_dir, repo_root=repo_root)
    catalog = load_catalog(catalog_paths, repo_root=repo_root, policy_document=policy_document)
    mappings, mapping_hashes_abs = load_mappings(mapping_paths)
    mapping_hashes: dict[str, str] = {}
    for raw_path, digest in mapping_hashes_abs.items():
        path = Path(raw_path)
        try:
            key = _repo_relative_path(path, repo_root)
        except ValueError:
            key = path.as_posix()
        mapping_hashes[key] = digest

    packs: dict[str, dict[str, Any]] = {}
    case_results: list[CaseMaterializationResult] = []
    source_requests: list[dict[str, str]] = []
    mapping_tasks: list[dict[str, str]] = []
    for contract in contracts:
        result, pack, case_source_requests, case_mapping_tasks = materialize_case(
            contract,
            catalog,
            mappings.get(contract.case_id),
            repo_root=repo_root,
            policy_document=policy_document,
        )
        # Global catalog conflicts are attached to every affected suite, never hidden.
        for global_issue in catalog.issues:
            result.issues.append(
                MaterializationIssue(
                    case_id=contract.case_id,
                    code=global_issue.code,
                    severity=global_issue.severity,
                    field=global_issue.field,
                    message=global_issue.message,
                    owner_skill=global_issue.owner_skill,
                    target_stage=global_issue.target_stage,
                    requested_evidence=global_issue.requested_evidence,
                )
            )
        result.issue_count = len(result.issues)
        result.blocker_count = sum(item.severity == "blocker" for item in result.issues)
        if pack is not None:
            packs[contract.case_id] = pack
        case_results.append(result)
        source_requests.extend(case_source_requests)
        mapping_tasks.extend(case_mapping_tasks)

    case_results.sort(key=lambda item: item.case_id)
    source_requests = sorted(source_requests, key=lambda item: (item["case_id"], item["request_type"], item["request_id"]))
    mapping_tasks = sorted(mapping_tasks, key=lambda item: (item["case_id"], item["task_type"], item["task_id"]))
    blocker_count = sum(item.blocker_count for item in case_results)
    pack_count = sum(item.pack_materialized for item in case_results)
    fully_mapped = sum(item.decision == "pack_ready_for_bundle15r_qualification" for item in case_results)
    if pack_count == 0:
        decision = "waiting_for_reviewed_evidence_and_mapping"
    elif fully_mapped < len(case_results):
        decision = "partial_pack_materialization_with_backflow"
    else:
        decision = "all_packs_ready_for_bundle15r_qualification"

    suite = MaterializationSuite(
        schema_version=SCHEMA_VERSION,
        bundle_id=BUNDLE_ID,
        baseline_commit=baseline_commit,
        case_count=len(case_results),
        mapping_present_count=sum(item.mapping_present for item in case_results),
        pack_materialized_count=pack_count,
        fully_mapped_case_count=fully_mapped,
        blocker_count=blocker_count,
        source_request_count=len(source_requests),
        mapping_task_count=len(mapping_tasks),
        decision=decision,
        canonical_workflow_state_mutation_allowed=False,
        sample_quality_allowed=False,
        p2_allowed=False,
        cases=case_results,
    )
    status_proposal = _status_proposal(suite)
    backflow_rows = sorted(
        [
            {
                "case_id": issue.case_id,
                "code": issue.code,
                "severity": issue.severity,
                "owner_skill": issue.owner_skill,
                "target_stage": issue.target_stage,
                "field": issue.field,
                "message": issue.message,
                "requested_evidence": issue.requested_evidence,
            }
            for case in case_results
            for issue in case.issues
        ],
        key=lambda item: (item["case_id"], item["severity"], item["code"], item["field"]),
    )
    inventory = {
        "schema_version": "r5_bundle16r_catalog_inventory_v1",
        "source_count": len(catalog.sources),
        "record_count": len(catalog.records),
        "duplicate_source_count": catalog.duplicate_source_count,
        "duplicate_record_count": catalog.duplicate_record_count,
        "catalog_paths": list(catalog.input_paths),
        "catalog_sha256": dict(sorted(catalog.input_sha256.items())),
        "mapping_sha256": dict(sorted(mapping_hashes.items())),
        "case_contracts": [
            {
                "case_id": contract.case_id,
                "issuer_ticker": contract.issuer_ticker,
                "source_path": contract.source_path,
                "sha256": contract.source_sha256,
                "required_source_classes": list(contract.required_source_classes),
                "driver_ids": list(contract.driver_ids),
                "required_question_ids": list(contract.required_question_ids),
            }
            for contract in contracts
        ],
        "release": dict(DEFAULT_POLICY["release"]),
    }
    lock_inputs = {
        **{f"case:{item.source_path}": item.source_sha256 for item in contracts},
        **{f"catalog:{key}": value for key, value in catalog.input_sha256.items()},
        **{f"mapping:{key}": value for key, value in mapping_hashes.items()},
        "declared:baseline_commit": baseline_commit,
    }
    prelock_payload = {
        "schema_version": GENERATION_LOCK_SCHEMA_VERSION,
        "bundle_id": BUNDLE_ID,
        "input_sha256": dict(sorted(lock_inputs.items())),
        "suite_sha256": sha256_bytes(canonical_json_bytes(asdict(suite))),
        "inventory_sha256": sha256_bytes(canonical_json_bytes(inventory)),
        "status_proposal_sha256": sha256_bytes(canonical_json_bytes(status_proposal)),
        "pack_sha256": {
            case_id: sha256_bytes(yaml.safe_dump(pack, allow_unicode=True, sort_keys=True).encode("utf-8"))
            for case_id, pack in sorted(packs.items())
        },
        "release_authority": False,
        "canonical_workflow_state_mutation_allowed": False,
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    generation_lock = dict(prelock_payload)
    generation_lock["generation_id"] = "pack_materialization_gen_" + sha256_bytes(canonical_json_bytes(prelock_payload))[:16]
    return MaterializationArtifacts(
        suite=suite,
        packs=packs,
        source_requests=source_requests,
        mapping_tasks=mapping_tasks,
        backflow_rows=backflow_rows,
        inventory=inventory,
        status_proposal=status_proposal,
        generation_lock=generation_lock,
    )


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_yaml(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=True), encoding="utf-8", newline="\n")


def write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def render_readout(artifacts: MaterializationArtifacts) -> str:
    rows = []
    for case in artifacts.suite.cases:
        rows.append(
            "| {case_id} | {ticker} | {mapping} | {sources}/{required_sources} | "
            "{drivers}/{required_drivers} | {questions}/{required_questions} | {decision} |".format(
                case_id=case.case_id,
                ticker=case.issuer_ticker,
                mapping="yes" if case.mapping_valid else "no",
                sources=case.bound_source_count,
                required_sources=case.required_source_class_count,
                drivers=len(case.qualifying_driver_ids),
                required_drivers=case.required_driver_count,
                questions=len(case.classified_question_ids),
                required_questions=case.required_question_count,
                decision=case.decision,
            )
        )
    return """# R5 Bundle 16R Reviewed-Evidence Pack Materialization Readout

- Baseline: `{baseline}`
- Generation ID: `{generation}`
- Decision: `{decision}`
- Cases: `{cases}`
- Packs materialized: `{packs}`
- Fully mapped cases: `{fully_mapped}`
- Blockers: `{blockers}`
- Canonical workflow-state mutation: `false`
- Sample quality allowed: `false`
- P2 allowed: `false`

## Case matrix

| Case | Ticker | Mapping valid | Sources | Drivers | Questions | Decision |
|---|---|---|---:|---:|---:|---|
{rows}

## Boundary

Bundle 16R only converts already-reviewed, physically archived evidence and explicit reviewer mappings into Bundle 15R-compatible pack candidates. It does not fetch or review evidence, does not claim research readiness, and does not authorize sample quality or P2. Missing inputs are preserved in the source-request, mapping and backflow queues.
""".format(
        baseline=artifacts.suite.baseline_commit,
        generation=artifacts.generation_lock["generation_id"],
        decision=artifacts.suite.decision,
        cases=artifacts.suite.case_count,
        packs=artifacts.suite.pack_materialized_count,
        fully_mapped=artifacts.suite.fully_mapped_case_count,
        blockers=artifacts.suite.blocker_count,
        rows="\n".join(rows),
    )


def write_materialization_outputs(output_dir: str | Path, artifacts: MaterializationArtifacts) -> None:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "R5_bundle16r_materialization_suite.json", asdict(artifacts.suite))
    write_json(root / "R5_bundle16r_catalog_inventory.json", artifacts.inventory)
    write_csv(
        root / "R5_bundle16r_source_request_queue.csv",
        artifacts.source_requests,
        ["case_id", "issuer_ticker", "request_type", "request_id", "owner_skill", "target_stage", "request"],
    )
    write_csv(
        root / "R5_bundle16r_mapping_queue.csv",
        artifacts.mapping_tasks,
        ["case_id", "issuer_ticker", "task_type", "task_id", "owner_skill", "target_stage", "task"],
    )
    write_csv(
        root / "R5_bundle16r_backflow_queue.csv",
        artifacts.backflow_rows,
        ["case_id", "code", "severity", "owner_skill", "target_stage", "field", "message", "requested_evidence"],
    )
    for case_id, pack in sorted(artifacts.packs.items()):
        write_yaml(root / "pack_candidates" / f"{case_id}.yaml", pack)
    write_yaml(root / "R5_bundle16r_status_proposal.yaml", artifacts.status_proposal)
    write_yaml(root / "R5_bundle16r_generation_lock.yaml", artifacts.generation_lock)
    (root / "R5_BUNDLE16R_MATERIALIZATION_READOUT.md").write_text(
        render_readout(artifacts), encoding="utf-8", newline="\n"
    )


def atomic_publish_packs(candidate_dir: str | Path, packs_dir: str | Path) -> list[Path]:
    source = Path(candidate_dir)
    destination = Path(packs_dir)
    destination.mkdir(parents=True, exist_ok=True)
    published: list[Path] = []
    for candidate in sorted(source.glob("*.yaml")):
        target = destination / candidate.name
        with tempfile.NamedTemporaryFile("wb", delete=False, dir=destination, prefix=f".{candidate.name}.") as handle:
            temporary = Path(handle.name)
            handle.write(candidate.read_bytes())
        os.replace(temporary, target)
        published.append(target)
    return published


def copytree_atomic(source: Path, destination: Path) -> None:
    """Testing/utility helper: replace a generated directory without partial output."""
    temporary = destination.with_name(destination.name + ".tmp")
    if temporary.exists():
        shutil.rmtree(temporary)
    shutil.copytree(source, temporary)
    if destination.exists():
        shutil.rmtree(destination)
    os.replace(temporary, destination)


__all__ = [
    "BUNDLE_ID",
    "GENERATION_LOCK_SCHEMA_VERSION",
    "MAPPING_SCHEMA_VERSION",
    "PACK_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "CaseContract",
    "CaseMaterializationResult",
    "Catalog",
    "MaterializationArtifacts",
    "MaterializationContractError",
    "MaterializationIssue",
    "MaterializationSuite",
    "atomic_publish_packs",
    "canonical_json_bytes",
    "discover_document_paths",
    "extract_case_contract",
    "load_case_contracts",
    "load_catalog",
    "load_document",
    "load_mappings",
    "materialize_case",
    "materialize_suite",
    "render_readout",
    "sha256_file",
    "write_materialization_outputs",
]
