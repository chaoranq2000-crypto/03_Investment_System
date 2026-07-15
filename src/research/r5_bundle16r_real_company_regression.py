"""R5 Bundle 16R: deterministic real-company regression release gate.

This module evaluates four real-company research runs without creating facts,
rewriting reports, or authorizing P2.  It is deliberately downstream of the
existing evidence, operating-driver, forecast, valuation, Reader and semantic
quality layers.

The evaluator consumes one case-result manifest per company.  Each manifest
must point to physical artifacts and include the metrics emitted by the
upstream workflow.  The evaluator then:

* verifies artifact existence and SHA-256 integrity;
* rejects narrative benchmark text used as evidence;
* enforces operating-driver, model-link and semantic-quality thresholds;
* validates peer-valuation eligibility and fallback valuation behavior;
* binds any human acceptance to the exact report and generation-lock hashes;
* scans runtime implementation paths for issuer-specific hard-coding; and
* emits deterministic JSON and Markdown suite readouts.

Passing this module's engineering gate does not imply sample-quality approval.
``sample_quality_allowed`` remains false until all four cases have exact-hash
human acceptance.  ``p2_allowed`` is never granted automatically here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "r5_bundle16r_real_company_regression_v1"
DEFAULT_REQUIRED_ARTIFACT_ROLES = (
    "workflow_state",
    "evidence_pack",
    "operating_driver_pack",
    "forecast_model",
    "valuation_pack",
    "reader_report",
    "quality_readout",
    "generation_lock",
    "human_review",
)
DEFAULT_CASE_RESULT_GLOB = "*.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TICKER_RE = re.compile(r"^[0-9]{6}$")
ALLOWED_HUMAN_STATUSES = {"pending", "accepted", "rejected"}
ALLOWED_ALTERNATIVE_VALUATION_METHODS = {
    "reverse_valuation",
    "scenario_valuation",
    "asset_value_range",
    "none",
}


class Bundle16RValidationError(ValueError):
    """Raised when the registry or a case manifest is structurally invalid."""


def _backflow_for_issue(code: str) -> tuple[str, str]:
    if code in {"human_review_exact_hash_mismatch", "human_review_status_invalid"}:
        return "review_handoff", "return the exact Reader and generation-lock hashes to a real reviewer"
    if code in {"narrative_sample_used_as_evidence", "truthfulness_flag_active", "truthfulness_missing"}:
        return "quality_review", "remove unsupported evidence use or resolve the truthfulness blocker"
    if code.startswith("peer_") or code.startswith("valuation_"):
        return "peer_eligibility_valuation", "disable peer multiples or repair peer definitions and period alignment"
    if code in {"issuer_specific_runtime_token", "runtime_scan_path_invalid"}:
        return "runtime_integration", "remove issuer-specific logic from generic runtime paths"
    if code in {"golden_case_missing", "case_result_missing", "unexpected_case_result"}:
        return "research_orchestrator", "restore the registered case run and regenerate its manifest"
    if code.startswith("artifact_") or code in {"required_artifact_missing", "duplicate_artifact_role"}:
        return "artifact_producer_quality_review", "regenerate the owning artifact and rebind its physical SHA-256"
    if code.startswith("metric_") or code in {"metrics_missing", "critical_question_open"}:
        return "upstream_metric_owner", "repair the upstream operating, forecast, report, evidence, or question pack named by the metric"
    if code == "p2_manual_authorization_required":
        return "canonical_governance", "request a separate canonical P2 decision after sample-quality prerequisites"
    return "quality_review", "triage the failed gate and assign the narrowest upstream owner"


@dataclass(frozen=True)
class GateIssue:
    code: str
    message: str
    severity: str = "error"
    field: str | None = None

    def as_dict(self) -> dict[str, Any]:
        backflow_owner, next_step = _backflow_for_issue(self.code)
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "backflow_owner": backflow_owner,
            "next_step": next_step,
        }
        if self.field:
            payload["field"] = self.field
        return payload


@dataclass
class CaseEvaluation:
    case_id: str
    ticker: str
    issuer_name: str
    engineering_pass: bool
    human_review_status: str
    exact_hash_human_acceptance: bool
    sample_quality_case_allowed: bool
    metrics: dict[str, Any]
    issues: list[GateIssue] = field(default_factory=list)
    artifact_hashes: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "ticker": self.ticker,
            "issuer_name": self.issuer_name,
            "engineering_pass": self.engineering_pass,
            "human_review_status": self.human_review_status,
            "exact_hash_human_acceptance": self.exact_hash_human_acceptance,
            "sample_quality_case_allowed": self.sample_quality_case_allowed,
            "metrics": _canonicalize(self.metrics),
            "artifact_hashes": dict(sorted(self.artifact_hashes.items())),
            "issues": [issue.as_dict() for issue in self.issues],
        }


@dataclass
class SuiteEvaluation:
    suite_id: str
    baseline_commit: str
    engineering_pass: bool
    all_cases_present: bool
    all_cases_exact_hash_accepted: bool
    sample_quality_allowed: bool
    p2_allowed: bool
    cases: list[CaseEvaluation]
    issues: list[GateIssue] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "suite_id": self.suite_id,
            "baseline_commit": self.baseline_commit,
            "engineering_pass": self.engineering_pass,
            "all_cases_present": self.all_cases_present,
            "all_cases_exact_hash_accepted": self.all_cases_exact_hash_accepted,
            "sample_quality_allowed": self.sample_quality_allowed,
            "p2_allowed": self.p2_allowed,
            "cases": [case.as_dict() for case in sorted(self.cases, key=lambda x: x.case_id)],
            "issues": [issue.as_dict() for issue in self.issues],
        }


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    if isinstance(value, tuple):
        return [_canonicalize(item) for item in value]
    return value


def _load_structured(path: Path) -> dict[str, Any]:
    """Load JSON first, then YAML when PyYAML is available.

    The committed registry intentionally uses JSON syntax in a ``.yaml`` file,
    so the core implementation has no mandatory third-party dependency.
    """

    text = path.read_text(encoding="utf-8")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as json_error:
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional fallback
            raise Bundle16RValidationError(
                f"{path} is not JSON and PyYAML is unavailable: {json_error}"
            ) from exc
        value = yaml.safe_load(text)
    if not isinstance(value, dict):
        raise Bundle16RValidationError(f"{path} must contain a mapping at the root")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_canonicalize(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _resolve_repo_path(repo_root: Path, raw_path: str) -> Path:
    candidate = (repo_root / raw_path).resolve()
    root = repo_root.resolve()
    if not _is_relative_to(candidate, root):
        raise Bundle16RValidationError(f"artifact path escapes repository root: {raw_path}")
    return candidate


def _expect_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Bundle16RValidationError(f"{label} must be a mapping")
    return value


def _expect_sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Bundle16RValidationError(f"{label} must be a sequence")
    return value


def _as_float(metrics: Mapping[str, Any], key: str, issues: list[GateIssue]) -> float | None:
    value = metrics.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        issues.append(GateIssue("metric_missing_or_non_numeric", f"metric {key} must be numeric", field=key))
        return None
    return float(value)


def _as_int(metrics: Mapping[str, Any], key: str, issues: list[GateIssue]) -> int | None:
    value = metrics.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        issues.append(GateIssue("metric_missing_or_non_integer", f"metric {key} must be an integer", field=key))
        return None
    return value


def validate_registry(registry: Mapping[str, Any]) -> None:
    if registry.get("schema_version") != SCHEMA_VERSION:
        raise Bundle16RValidationError(
            f"registry schema_version must be {SCHEMA_VERSION!r}"
        )
    suite_id = registry.get("suite_id")
    if not isinstance(suite_id, str) or not suite_id.strip():
        raise Bundle16RValidationError("registry suite_id must be a non-empty string")
    baseline_commit = registry.get("baseline_commit")
    if not isinstance(baseline_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", baseline_commit):
        raise Bundle16RValidationError("registry baseline_commit must be a full 40-character SHA")

    cases = _expect_sequence(registry.get("cases"), "registry.cases")
    if len(cases) != 4:
        raise Bundle16RValidationError("registry must define exactly four golden regression cases")

    seen_case_ids: set[str] = set()
    seen_tickers: set[str] = set()
    for index, raw_case in enumerate(cases):
        case = _expect_mapping(raw_case, f"registry.cases[{index}]")
        case_id = case.get("case_id")
        ticker = case.get("ticker")
        issuer_name = case.get("issuer_name")
        if not isinstance(case_id, str) or not case_id.strip():
            raise Bundle16RValidationError(f"case {index} has invalid case_id")
        if case_id in seen_case_ids:
            raise Bundle16RValidationError(f"duplicate case_id: {case_id}")
        seen_case_ids.add(case_id)
        if not isinstance(ticker, str) or not TICKER_RE.fullmatch(ticker):
            raise Bundle16RValidationError(f"case {case_id} has invalid six-digit ticker")
        if ticker in seen_tickers:
            raise Bundle16RValidationError(f"duplicate ticker: {ticker}")
        seen_tickers.add(ticker)
        if not isinstance(issuer_name, str) or not issuer_name.strip():
            raise Bundle16RValidationError(f"case {case_id} has invalid issuer_name")

        archetypes = _expect_sequence(case.get("required_economic_archetypes"), f"{case_id}.required_economic_archetypes")
        segments = _expect_sequence(case.get("material_segments"), f"{case_id}.material_segments")
        if not archetypes:
            raise Bundle16RValidationError(f"case {case_id} must define economic archetypes")
        if not segments:
            raise Bundle16RValidationError(f"case {case_id} must define material segments")

        benchmark_policy = _expect_mapping(case.get("benchmark_policy"), f"{case_id}.benchmark_policy")
        if benchmark_policy.get("sample_text_role") != "narrative_density_only":
            raise Bundle16RValidationError(
                f"case {case_id} must mark sample text as narrative_density_only"
            )
        if benchmark_policy.get("sample_text_may_be_evidence") is not False:
            raise Bundle16RValidationError(
                f"case {case_id} must explicitly prohibit sample text as evidence"
            )


def _thresholds(registry: Mapping[str, Any]) -> Mapping[str, Any]:
    thresholds = _expect_mapping(registry.get("thresholds"), "registry.thresholds")
    required = {
        "material_segment_driver_coverage_min",
        "revenue_explained_ratio_min",
        "gross_profit_explained_ratio_min",
        "residual_revenue_ratio_max",
        "residual_gross_profit_ratio_max",
        "forecast_assumption_traceability_min",
        "model_linked_core_section_ratio_min",
        "section_novelty_ratio_min",
        "citation_resolution_rate_min",
        "company_specific_metric_count_min",
        "future_event_model_link_count_min",
        "qualified_peer_count_min_when_peer_multiple_used",
    }
    missing = sorted(required.difference(thresholds))
    if missing:
        raise Bundle16RValidationError(f"registry thresholds missing: {', '.join(missing)}")
    return thresholds


def _artifact_index(
    repo_root: Path,
    case_manifest: Mapping[str, Any],
    issues: list[GateIssue],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, str]]:
    raw_artifacts = case_manifest.get("artifacts")
    if not isinstance(raw_artifacts, list):
        issues.append(GateIssue("artifacts_missing", "artifacts must be a list", field="artifacts"))
        return {}, {}

    by_role: dict[str, Mapping[str, Any]] = {}
    hashes: dict[str, str] = {}
    for index, raw in enumerate(raw_artifacts):
        if not isinstance(raw, Mapping):
            issues.append(GateIssue("artifact_invalid", f"artifact {index} must be a mapping"))
            continue
        role = raw.get("role")
        rel_path = raw.get("path")
        expected_sha = raw.get("sha256")
        if not isinstance(role, str) or not role:
            issues.append(GateIssue("artifact_role_invalid", f"artifact {index} has invalid role"))
            continue
        if role in by_role:
            issues.append(GateIssue("artifact_role_duplicate", f"duplicate artifact role: {role}"))
            continue
        by_role[role] = raw
        if not isinstance(rel_path, str) or not rel_path:
            issues.append(GateIssue("artifact_path_invalid", f"artifact {role} has invalid path"))
            continue
        if not isinstance(expected_sha, str) or not SHA256_RE.fullmatch(expected_sha):
            issues.append(GateIssue("artifact_sha_invalid", f"artifact {role} has invalid sha256"))
            continue
        try:
            path = _resolve_repo_path(repo_root, rel_path)
        except Bundle16RValidationError as exc:
            issues.append(GateIssue("artifact_path_escape", str(exc), field=role))
            continue
        if not path.is_file():
            issues.append(GateIssue("artifact_missing", f"artifact {role} does not exist: {rel_path}", field=role))
            continue
        actual_sha = _sha256(path)
        hashes[role] = actual_sha
        if actual_sha != expected_sha:
            issues.append(
                GateIssue(
                    "artifact_sha_mismatch",
                    f"artifact {role} sha mismatch: expected {expected_sha}, got {actual_sha}",
                    field=role,
                )
            )
    return by_role, hashes


def _check_required_artifacts(
    artifact_by_role: Mapping[str, Mapping[str, Any]],
    required_roles: Iterable[str],
    issues: list[GateIssue],
) -> None:
    for role in required_roles:
        if role not in artifact_by_role:
            issues.append(GateIssue("required_artifact_missing", f"required artifact role missing: {role}", field=role))


def _normalized_path_parts(raw_path: str) -> list[str]:
    return [part.casefold() for part in Path(raw_path.replace("\\", "/")).parts]


def _check_evidence_provenance(
    artifact_by_role: Mapping[str, Mapping[str, Any]],
    case_manifest: Mapping[str, Any],
    issues: list[GateIssue],
) -> None:
    truthfulness = case_manifest.get("truthfulness", {})
    if isinstance(truthfulness, Mapping) and truthfulness.get("sample_text_used_as_evidence") is True:
        issues.append(GateIssue("sample_text_as_evidence", "case manifest admits sample text was used as evidence"))

    prohibited_parts = {
        "narrative_samples",
        "sample_reports",
        "report_samples",
        "golden_text",
        "样例",
        "案例样例",
    }
    for role, artifact in artifact_by_role.items():
        source_class = artifact.get("source_class")
        raw_path = artifact.get("path")
        if role != "evidence_pack" and source_class != "evidence":
            continue
        if not isinstance(raw_path, str):
            continue
        parts = set(_normalized_path_parts(raw_path))
        if parts.intersection(prohibited_parts):
            issues.append(
                GateIssue(
                    "sample_path_used_as_evidence",
                    f"evidence artifact points into a narrative sample path: {raw_path}",
                    field=role,
                )
            )
        if artifact.get("purpose") == "narrative_density_only":
            issues.append(
                GateIssue(
                    "narrative_benchmark_promoted_to_evidence",
                    f"artifact {role} is marked narrative_density_only but used as evidence",
                    field=role,
                )
            )


def _check_truthfulness_flags(case_manifest: Mapping[str, Any], issues: list[GateIssue]) -> None:
    truthfulness = case_manifest.get("truthfulness")
    if not isinstance(truthfulness, Mapping):
        issues.append(GateIssue("truthfulness_missing", "truthfulness must be a mapping"))
        return
    prohibited_true_flags = (
        "sample_text_used_as_evidence",
        "management_guidance_recast_as_fact",
        "low_confidence_peer_ranked",
        "direct_trading_instruction_present",
        "past_event_presented_as_future",
        "undisclosed_segment_economics_presented_as_fact",
        "consensus_estimate_presented_as_issuer_fact",
    )
    for flag in prohibited_true_flags:
        value = truthfulness.get(flag)
        if value is not False:
            issues.append(
                GateIssue(
                    "truthfulness_flag_not_clean",
                    f"truthfulness.{flag} must be explicitly false",
                    field=f"truthfulness.{flag}",
                )
            )


def _check_metric_bounds(
    metrics: Mapping[str, Any],
    thresholds: Mapping[str, Any],
    issues: list[GateIssue],
) -> None:
    min_pairs = (
        ("material_segment_driver_coverage", "material_segment_driver_coverage_min"),
        ("revenue_explained_ratio", "revenue_explained_ratio_min"),
        ("gross_profit_explained_ratio", "gross_profit_explained_ratio_min"),
        ("forecast_assumption_traceability", "forecast_assumption_traceability_min"),
        ("model_linked_core_section_ratio", "model_linked_core_section_ratio_min"),
        ("section_novelty_ratio", "section_novelty_ratio_min"),
        ("citation_resolution_rate", "citation_resolution_rate_min"),
    )
    max_pairs = (
        ("residual_revenue_ratio", "residual_revenue_ratio_max"),
        ("residual_gross_profit_ratio", "residual_gross_profit_ratio_max"),
    )
    for metric_key, threshold_key in min_pairs:
        value = _as_float(metrics, metric_key, issues)
        threshold = float(thresholds[threshold_key])
        if value is not None and value < threshold:
            issues.append(
                GateIssue(
                    "metric_below_minimum",
                    f"{metric_key}={value:.4f} is below minimum {threshold:.4f}",
                    field=metric_key,
                )
            )
    for metric_key, threshold_key in max_pairs:
        value = _as_float(metrics, metric_key, issues)
        threshold = float(thresholds[threshold_key])
        if value is not None and value > threshold:
            issues.append(
                GateIssue(
                    "metric_above_maximum",
                    f"{metric_key}={value:.4f} is above maximum {threshold:.4f}",
                    field=metric_key,
                )
            )

    company_specific_metric_count = _as_int(metrics, "company_specific_metric_count", issues)
    if company_specific_metric_count is not None:
        minimum = int(thresholds["company_specific_metric_count_min"])
        if company_specific_metric_count < minimum:
            issues.append(
                GateIssue(
                    "company_specific_metrics_insufficient",
                    f"company_specific_metric_count={company_specific_metric_count} is below {minimum}",
                    field="company_specific_metric_count",
                )
            )

    future_event_links = _as_int(metrics, "future_event_model_link_count", issues)
    if future_event_links is not None:
        minimum = int(thresholds["future_event_model_link_count_min"])
        if future_event_links < minimum:
            issues.append(
                GateIssue(
                    "future_event_links_insufficient",
                    f"future_event_model_link_count={future_event_links} is below {minimum}",
                    field="future_event_model_link_count",
                )
            )

    unresolved_critical = _as_int(metrics, "unresolved_critical_question_count", issues)
    if unresolved_critical is not None and unresolved_critical != 0:
        issues.append(
            GateIssue(
                "critical_questions_unresolved",
                f"unresolved_critical_question_count must be 0, got {unresolved_critical}",
                field="unresolved_critical_question_count",
            )
        )


def _check_peer_valuation(
    case_manifest: Mapping[str, Any],
    metrics: Mapping[str, Any],
    thresholds: Mapping[str, Any],
    issues: list[GateIssue],
) -> None:
    valuation = case_manifest.get("valuation")
    if not isinstance(valuation, Mapping):
        issues.append(GateIssue("valuation_metadata_missing", "valuation must be a mapping"))
        return
    peer_multiple_used = valuation.get("peer_multiple_used")
    if not isinstance(peer_multiple_used, bool):
        issues.append(GateIssue("peer_multiple_flag_invalid", "valuation.peer_multiple_used must be boolean"))
        return
    peer_count = _as_int(metrics, "qualified_peer_count", issues)
    if peer_count is None:
        return
    if peer_multiple_used:
        minimum = int(thresholds["qualified_peer_count_min_when_peer_multiple_used"])
        if peer_count < minimum:
            issues.append(
                GateIssue(
                    "peer_multiple_without_qualified_peers",
                    f"peer multiple used with only {peer_count} qualified peers; minimum is {minimum}",
                    field="qualified_peer_count",
                )
            )
        if valuation.get("peer_definition_compatible") is not True:
            issues.append(
                GateIssue(
                    "peer_definition_incompatible",
                    "peer multiple requires definition-compatible peers",
                    field="valuation.peer_definition_compatible",
                )
            )
        if valuation.get("peer_periods_aligned") is not True:
            issues.append(
                GateIssue(
                    "peer_periods_not_aligned",
                    "peer multiple requires aligned forecast periods",
                    field="valuation.peer_periods_aligned",
                )
            )
    else:
        alternative = valuation.get("alternative_method")
        if alternative not in ALLOWED_ALTERNATIVE_VALUATION_METHODS:
            issues.append(
                GateIssue(
                    "alternative_valuation_method_invalid",
                    f"alternative_method must be one of {sorted(ALLOWED_ALTERNATIVE_VALUATION_METHODS)}",
                    field="valuation.alternative_method",
                )
            )


def _check_generation_and_human_review(
    repo_root: Path,
    case_manifest: Mapping[str, Any],
    artifact_by_role: Mapping[str, Mapping[str, Any]],
    artifact_hashes: Mapping[str, str],
    issues: list[GateIssue],
) -> tuple[str, bool]:
    report_sha = artifact_hashes.get("reader_report")
    lock_sha = artifact_hashes.get("generation_lock")
    review_artifact = artifact_by_role.get("human_review")
    lock_artifact = artifact_by_role.get("generation_lock")
    if report_sha is None or lock_sha is None or review_artifact is None or lock_artifact is None:
        return "pending", False

    lock_path_raw = lock_artifact.get("path")
    review_path_raw = review_artifact.get("path")
    if not isinstance(lock_path_raw, str) or not isinstance(review_path_raw, str):
        return "pending", False

    try:
        generation_lock = _load_structured(_resolve_repo_path(repo_root, lock_path_raw))
        human_review = _load_structured(_resolve_repo_path(repo_root, review_path_raw))
    except (Bundle16RValidationError, OSError) as exc:
        issues.append(GateIssue("review_or_lock_unreadable", str(exc)))
        return "pending", False

    if generation_lock.get("reader_report_sha256") != report_sha:
        issues.append(
            GateIssue(
                "generation_lock_report_hash_mismatch",
                "generation lock does not bind the physical Reader report hash",
            )
        )
    if generation_lock.get("case_id") != case_manifest.get("case_id"):
        issues.append(GateIssue("generation_lock_case_mismatch", "generation lock case_id mismatch"))

    status = human_review.get("status")
    if status not in ALLOWED_HUMAN_STATUSES:
        issues.append(
            GateIssue(
                "human_review_status_invalid",
                f"human review status must be one of {sorted(ALLOWED_HUMAN_STATUSES)}",
                field="human_review.status",
            )
        )
        return "pending", False

    exact_match = (
        status == "accepted"
        and human_review.get("reader_report_sha256") == report_sha
        and human_review.get("generation_lock_sha256") == lock_sha
        and isinstance(human_review.get("reviewer"), str)
        and bool(human_review.get("reviewer", "").strip())
        and isinstance(human_review.get("reviewed_at"), str)
        and bool(human_review.get("reviewed_at", "").strip())
    )
    if status == "accepted" and not exact_match:
        issues.append(
            GateIssue(
                "human_review_exact_hash_mismatch",
                "accepted human review must bind exact report and generation-lock hashes and identify reviewer/time",
            )
        )
    return str(status), exact_match


def evaluate_case(
    repo_root: Path,
    registry_case: Mapping[str, Any],
    case_manifest: Mapping[str, Any],
    thresholds: Mapping[str, Any],
    required_artifact_roles: Sequence[str] = DEFAULT_REQUIRED_ARTIFACT_ROLES,
) -> CaseEvaluation:
    issues: list[GateIssue] = []
    case_id = str(registry_case.get("case_id", ""))
    ticker = str(registry_case.get("ticker", ""))
    issuer_name = str(registry_case.get("issuer_name", ""))

    if case_manifest.get("schema_version") != SCHEMA_VERSION:
        issues.append(GateIssue("case_schema_mismatch", f"case schema_version must be {SCHEMA_VERSION}"))
    for field_name, expected in (
        ("case_id", case_id),
        ("ticker", ticker),
        ("issuer_name", issuer_name),
    ):
        if case_manifest.get(field_name) != expected:
            issues.append(
                GateIssue(
                    "case_identity_mismatch",
                    f"{field_name} mismatch: expected {expected!r}, got {case_manifest.get(field_name)!r}",
                    field=field_name,
                )
            )

    artifact_by_role, artifact_hashes = _artifact_index(repo_root, case_manifest, issues)
    _check_required_artifacts(artifact_by_role, required_artifact_roles, issues)
    _check_evidence_provenance(artifact_by_role, case_manifest, issues)
    _check_truthfulness_flags(case_manifest, issues)

    metrics_raw = case_manifest.get("metrics")
    metrics = metrics_raw if isinstance(metrics_raw, Mapping) else {}
    if not isinstance(metrics_raw, Mapping):
        issues.append(GateIssue("metrics_missing", "metrics must be a mapping", field="metrics"))
    _check_metric_bounds(metrics, thresholds, issues)
    _check_peer_valuation(case_manifest, metrics, thresholds, issues)

    human_status, exact_hash_accepted = _check_generation_and_human_review(
        repo_root,
        case_manifest,
        artifact_by_role,
        artifact_hashes,
        issues,
    )

    engineering_pass = not any(issue.severity == "error" for issue in issues)
    sample_quality_case_allowed = engineering_pass and exact_hash_accepted
    return CaseEvaluation(
        case_id=case_id,
        ticker=ticker,
        issuer_name=issuer_name,
        engineering_pass=engineering_pass,
        human_review_status=human_status,
        exact_hash_human_acceptance=exact_hash_accepted,
        sample_quality_case_allowed=sample_quality_case_allowed,
        metrics=dict(metrics),
        issues=issues,
        artifact_hashes=artifact_hashes,
    )


def _scan_runtime_for_issuer_specific_tokens(
    repo_root: Path,
    registry: Mapping[str, Any],
) -> list[GateIssue]:
    config = registry.get("runtime_scan")
    if not isinstance(config, Mapping) or config.get("enabled") is not True:
        return []

    include_dirs = config.get("include_dirs", [])
    allow_paths = {str(item).replace("\\", "/") for item in config.get("allow_paths", []) if isinstance(item, str)}
    extensions = {str(item) for item in config.get("extensions", [".py"])}
    tokens: set[str] = set()
    for raw_case in registry.get("cases", []):
        if not isinstance(raw_case, Mapping):
            continue
        for key in ("issuer_name", "ticker"):
            value = raw_case.get(key)
            if isinstance(value, str) and value:
                tokens.add(value)
        for token in raw_case.get("forbidden_runtime_tokens", []):
            if isinstance(token, str) and token:
                tokens.add(token)

    issues: list[GateIssue] = []
    for raw_dir in include_dirs:
        if not isinstance(raw_dir, str):
            continue
        try:
            directory = _resolve_repo_path(repo_root, raw_dir)
        except Bundle16RValidationError as exc:
            issues.append(GateIssue("runtime_scan_path_invalid", str(exc)))
            continue
        if not directory.exists():
            continue
        for path in sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix in extensions):
            rel = path.relative_to(repo_root).as_posix()
            if rel in allow_paths:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for token in sorted(tokens):
                if token in text:
                    issues.append(
                        GateIssue(
                            "issuer_specific_runtime_token",
                            f"issuer-specific token {token!r} found in runtime implementation: {rel}",
                            field=rel,
                        )
                    )
    return issues


def _case_registry_by_id(registry: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(case["case_id"]): case
        for case in registry["cases"]
        if isinstance(case, Mapping)
    }


def load_case_manifests(case_results_dir: Path) -> dict[str, Mapping[str, Any]]:
    manifests: dict[str, Mapping[str, Any]] = {}
    if not case_results_dir.is_dir():
        return manifests
    for path in sorted(case_results_dir.glob(DEFAULT_CASE_RESULT_GLOB)):
        payload = _load_structured(path)
        case_id = payload.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise Bundle16RValidationError(f"case result lacks case_id: {path}")
        if case_id in manifests:
            raise Bundle16RValidationError(f"duplicate case result for {case_id}")
        manifests[case_id] = payload
    return manifests


def evaluate_suite(
    repo_root: Path,
    registry: Mapping[str, Any],
    case_manifests: Mapping[str, Mapping[str, Any]],
) -> SuiteEvaluation:
    validate_registry(registry)
    thresholds = _thresholds(registry)
    required_roles_raw = registry.get("required_artifact_roles", DEFAULT_REQUIRED_ARTIFACT_ROLES)
    required_roles = tuple(str(item) for item in _expect_sequence(required_roles_raw, "required_artifact_roles"))
    registry_cases = _case_registry_by_id(registry)

    suite_issues = _scan_runtime_for_issuer_specific_tokens(repo_root, registry)
    case_evaluations: list[CaseEvaluation] = []
    for case_id, registry_case in sorted(registry_cases.items()):
        manifest = case_manifests.get(case_id)
        if manifest is None:
            suite_issues.append(
                GateIssue(
                    "golden_case_missing",
                    f"required golden case result is missing: {case_id}",
                    field=case_id,
                )
            )
            continue
        case_evaluations.append(
            evaluate_case(repo_root, registry_case, manifest, thresholds, required_roles)
        )

    unexpected = sorted(set(case_manifests).difference(registry_cases))
    for case_id in unexpected:
        suite_issues.append(
            GateIssue(
                "unexpected_case_result",
                f"case result is not registered: {case_id}",
                severity="warning",
                field=case_id,
            )
        )

    all_cases_present = len(case_evaluations) == len(registry_cases)
    engineering_pass = (
        all_cases_present
        and not any(issue.severity == "error" for issue in suite_issues)
        and all(case.engineering_pass for case in case_evaluations)
    )
    all_cases_exact_hash_accepted = (
        all_cases_present
        and all(case.exact_hash_human_acceptance for case in case_evaluations)
    )
    sample_quality_allowed = engineering_pass and all_cases_exact_hash_accepted

    # P2 remains a separate, explicit governance decision.  This evaluator can
    # make the prerequisite visible but cannot authorize P2 by itself.
    p2_allowed = False
    if sample_quality_allowed:
        suite_issues.append(
            GateIssue(
                "p2_manual_authorization_required",
                "all Bundle 16R gates passed, but P2 still requires a separate canonical authorization",
                severity="info",
            )
        )

    return SuiteEvaluation(
        suite_id=str(registry["suite_id"]),
        baseline_commit=str(registry["baseline_commit"]),
        engineering_pass=engineering_pass,
        all_cases_present=all_cases_present,
        all_cases_exact_hash_accepted=all_cases_exact_hash_accepted,
        sample_quality_allowed=sample_quality_allowed,
        p2_allowed=p2_allowed,
        cases=case_evaluations,
        issues=suite_issues,
    )


def render_markdown(evaluation: SuiteEvaluation) -> str:
    status = "PASS" if evaluation.engineering_pass else "FAIL"
    sample_status = "ALLOWED" if evaluation.sample_quality_allowed else "BLOCKED"
    lines = [
        "# R5 Bundle 16R Real-Company Regression Readout",
        "",
        f"- Suite: `{evaluation.suite_id}`",
        f"- Baseline commit: `{evaluation.baseline_commit}`",
        f"- Engineering gate: **{status}**",
        f"- All four cases present: **{evaluation.all_cases_present}**",
        f"- All four exact-hash human reviews accepted: **{evaluation.all_cases_exact_hash_accepted}**",
        f"- Sample-quality release: **{sample_status}**",
        f"- P2 allowed: **{evaluation.p2_allowed}**",
        "",
        "## Case matrix",
        "",
        "| Case | Ticker | Issuer | Engineering | Human review | Exact-hash accepted | Sample-quality case |",
        "|---|---:|---|---|---|---|---|",
    ]
    for case in sorted(evaluation.cases, key=lambda item: item.case_id):
        lines.append(
            "| {case} | {ticker} | {issuer} | {engineering} | {human} | {exact} | {sample} |".format(
                case=case.case_id,
                ticker=case.ticker,
                issuer=case.issuer_name,
                engineering="PASS" if case.engineering_pass else "FAIL",
                human=case.human_review_status,
                exact=case.exact_hash_human_acceptance,
                sample=case.sample_quality_case_allowed,
            )
        )

    lines.extend(["", "## Blocking and informational issues", ""])
    combined: list[tuple[str, GateIssue]] = [("suite", issue) for issue in evaluation.issues]
    for case in evaluation.cases:
        combined.extend((case.case_id, issue) for issue in case.issues)
    if not combined:
        lines.append("No issues recorded.")
    else:
        for scope, issue in combined:
            lines.append(f"- **{issue.severity.upper()}** `{scope}:{issue.code}` — {issue.message}")

    lines.extend(
        [
            "",
            "## Governance boundary",
            "",
            "Passing the engineering gate only proves deterministic evaluation, artifact integrity,",
            "minimum operating-model coverage and semantic guardrails. It does not permit sample-quality",
            "or P2 claims unless all four real cases are accepted by a named human reviewer against the",
            "exact Reader and generation-lock hashes, followed by a separate canonical P2 decision.",
            "",
        ]
    )
    return "\n".join(lines)


def write_suite_outputs(output_dir: Path, evaluation: SuiteEvaluation) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "bundle16r_suite_readout.json"
    markdown_path = output_dir / "bundle16r_suite_readout.md"
    _write_json(json_path, evaluation.as_dict())
    markdown_path.write_text(render_markdown(evaluation), encoding="utf-8")
    return json_path, markdown_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-registry", help="validate the four-case registry")
    validate.add_argument("--registry", type=Path, required=True)

    evaluate = subparsers.add_parser("evaluate", help="evaluate physical real-company case results")
    evaluate.add_argument("--repo-root", type=Path, default=Path.cwd())
    evaluate.add_argument("--registry", type=Path, required=True)
    evaluate.add_argument("--case-results-dir", type=Path, required=True)
    evaluate.add_argument("--output-dir", type=Path, required=True)
    evaluate.add_argument(
        "--require-human-acceptance",
        action="store_true",
        help="return non-zero unless sample_quality_allowed is true",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        registry = _load_structured(args.registry)
        validate_registry(registry)
        if args.command == "validate-registry":
            print(f"validated {args.registry} against {SCHEMA_VERSION}")
            return 0

        repo_root = args.repo_root.resolve()
        manifests = load_case_manifests(args.case_results_dir)
        evaluation = evaluate_suite(repo_root, registry, manifests)
        json_path, markdown_path = write_suite_outputs(args.output_dir, evaluation)
        print(json.dumps(evaluation.as_dict(), ensure_ascii=False, sort_keys=True))
        print(f"wrote {json_path}")
        print(f"wrote {markdown_path}")
        if args.require_human_acceptance:
            return 0 if evaluation.sample_quality_allowed else 1
        return 0 if evaluation.engineering_pass else 1
    except (Bundle16RValidationError, OSError) as exc:
        print(f"bundle16r validation error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
