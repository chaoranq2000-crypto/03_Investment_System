"""Non-compensating semantic quality gate for Bundle 14R.

The gate is intentionally stricter than a word-count or field-presence check.
A long report cannot compensate for missing company-specific operating drivers,
unsupported valuation, repeated insights, or an unresolved truthfulness issue.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


SEMANTIC_GATE_SCHEMA_VERSION = "r5_bundle14r_semantic_gate_v1"


@dataclass(frozen=True)
class GateCheck:
    gate: str
    passed: bool
    score: float
    maximum: float
    message: str
    core: bool = True


@dataclass(frozen=True)
class SemanticGateResult:
    schema_version: str
    case_id: str
    decision: str
    total_score: float
    threshold: float
    core_gate_passed: bool
    blocker_count: int
    checks: tuple[GateCheck, ...]
    candidate_ready_for_exact_hash_review: bool
    release_authority: bool = False
    sample_quality_allowed: bool = False
    p2_allowed: bool = False


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


def _integer(value: Any, default: int = 0) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return default


def evaluate_semantic_candidate(
    case_id: str,
    candidate: Mapping[str, Any],
    *,
    company_specific_metric_minimum: int,
    quantified_links_minimum: int,
    unique_conclusions_minimum: int,
    maximum_duplicate_insight_ratio: float,
    threshold: float = 80.0,
) -> SemanticGateResult:
    """Evaluate a report/model candidate with non-compensating core gates."""

    checks: list[GateCheck] = []

    truthfulness = _mapping(candidate.get("truthfulness"))
    unresolved_claims = _integer(truthfulness.get("unresolved_claim_count"))
    sample_evidence_claims = _integer(truthfulness.get("sample_evidence_claim_count"))
    conflicts = _integer(truthfulness.get("source_conflict_count"))
    truth_passed = unresolved_claims == 0 and sample_evidence_claims == 0 and conflicts == 0
    checks.append(
        GateCheck(
            gate="truthfulness",
            passed=truth_passed,
            score=20.0 if truth_passed else 0.0,
            maximum=20.0,
            message=(
                "all claims resolve to reviewed sources or labelled estimates"
                if truth_passed
                else (
                    f"unresolved={unresolved_claims}, sample_as_evidence={sample_evidence_claims}, "
                    f"source_conflicts={conflicts}"
                )
            ),
        )
    )

    model = _mapping(candidate.get("economic_model"))
    qualified_ratio = _number(model.get("qualified_required_driver_ratio"))
    reconciliation = model.get("statement_reconciliation_passed") is True
    overlap = model.get("overlap_resolved") is True
    model_passed = qualified_ratio >= 1.0 and reconciliation and overlap
    model_partial = min(max(qualified_ratio, 0.0), 1.0) * 12.0
    if reconciliation:
        model_partial += 4.0
    if overlap:
        model_partial += 4.0
    checks.append(
        GateCheck(
            gate="economic_driver_to_statement_bridge",
            passed=model_passed,
            score=20.0 if model_passed else model_partial,
            maximum=20.0,
            message=(
                "all required operating drivers reconcile through segment and statement bridges"
                if model_passed
                else (
                    f"qualified_driver_ratio={qualified_ratio:.3f}, "
                    f"reconciliation={reconciliation}, overlap_resolved={overlap}"
                )
            ),
        )
    )

    narrative = _mapping(candidate.get("narrative"))
    metric_count = _integer(narrative.get("company_specific_metric_count"))
    quantified_links = _integer(narrative.get("quantified_driver_to_financial_link_count"))
    unique_conclusions = _integer(narrative.get("unique_core_conclusion_count"))
    duplicate_ratio = _number(narrative.get("duplicate_insight_ratio"), default=1.0)
    generic_ratio = _number(narrative.get("generic_sentence_ratio"), default=1.0)
    empty_core_sections = _integer(narrative.get("empty_core_section_count"), default=99)
    narrative_passed = (
        metric_count >= company_specific_metric_minimum
        and quantified_links >= quantified_links_minimum
        and unique_conclusions >= unique_conclusions_minimum
        and duplicate_ratio <= maximum_duplicate_insight_ratio
        and generic_ratio <= 0.35
        and empty_core_sections == 0
    )
    narrative_score = 0.0
    narrative_score += min(metric_count / max(company_specific_metric_minimum, 1), 1.0) * 5.0
    narrative_score += min(quantified_links / max(quantified_links_minimum, 1), 1.0) * 5.0
    narrative_score += min(unique_conclusions / max(unique_conclusions_minimum, 1), 1.0) * 4.0
    narrative_score += max(0.0, 1.0 - duplicate_ratio / max(maximum_duplicate_insight_ratio, 0.01)) * 3.0
    narrative_score += max(0.0, 1.0 - generic_ratio / 0.35) * 3.0
    checks.append(
        GateCheck(
            gate="semantic_incrementality",
            passed=narrative_passed,
            score=20.0 if narrative_passed else min(narrative_score, 19.0),
            maximum=20.0,
            message=(
                "company-specific, quantified, non-duplicative analytical narrative"
                if narrative_passed
                else (
                    f"metrics={metric_count}/{company_specific_metric_minimum}, "
                    f"links={quantified_links}/{quantified_links_minimum}, "
                    f"conclusions={unique_conclusions}/{unique_conclusions_minimum}, "
                    f"duplicate_ratio={duplicate_ratio:.3f}, generic_ratio={generic_ratio:.3f}, "
                    f"empty_core_sections={empty_core_sections}"
                )
            ),
        )
    )

    valuation = _mapping(candidate.get("valuation"))
    eligible_method_count = _integer(valuation.get("eligible_method_count"))
    ineligible_used = valuation.get("ineligible_methods_used")
    if not isinstance(ineligible_used, list):
        ineligible_used = ["invalid_payload"]
    valuation_passed = eligible_method_count >= 1 and len(ineligible_used) == 0
    checks.append(
        GateCheck(
            gate="valuation_eligibility",
            passed=valuation_passed,
            score=15.0 if valuation_passed else 0.0,
            maximum=15.0,
            message=(
                "at least one independently qualified valuation method is used"
                if valuation_passed
                else f"eligible_method_count={eligible_method_count}, ineligible_used={ineligible_used}"
            ),
        )
    )

    backflow = _mapping(candidate.get("backflow"))
    unresolved_issue_count = _integer(backflow.get("unresolved_issue_count"))
    routed_issue_count = _integer(backflow.get("routed_issue_count"))
    actionable_issue_count = _integer(backflow.get("actionable_issue_count"))
    invalid_route_count = _integer(backflow.get("invalid_route_count"))
    backflow_passed = (
        invalid_route_count == 0
        and routed_issue_count == actionable_issue_count
        and unresolved_issue_count == 0
    )
    checks.append(
        GateCheck(
            gate="backflow_actionability",
            passed=backflow_passed,
            score=10.0 if backflow_passed else 0.0,
            maximum=10.0,
            message=(
                "all quality issues are resolved or routed to a named stage and skill"
                if backflow_passed
                else (
                    f"unresolved={unresolved_issue_count}, routed={routed_issue_count}, "
                    f"actionable={actionable_issue_count}, invalid_routes={invalid_route_count}"
                )
            ),
        )
    )

    determinism = _mapping(candidate.get("determinism"))
    rerun_equal = determinism.get("rerun_hash_equal") is True
    input_lock_complete = determinism.get("input_lock_complete") is True
    output_lock_complete = determinism.get("output_lock_complete") is True
    determinism_passed = rerun_equal and input_lock_complete and output_lock_complete
    checks.append(
        GateCheck(
            gate="deterministic_generation_lock",
            passed=determinism_passed,
            score=10.0 if determinism_passed else 0.0,
            maximum=10.0,
            message=(
                "rerun and complete input/output locks agree"
                if determinism_passed
                else (
                    f"rerun_equal={rerun_equal}, input_lock={input_lock_complete}, "
                    f"output_lock={output_lock_complete}"
                )
            ),
        )
    )

    events = _mapping(candidate.get("future_events"))
    dated_count = _integer(events.get("dated_or_windowed_event_count"))
    transmitted_count = _integer(events.get("event_with_operating_transmission_count"))
    past_as_future = _integer(events.get("past_event_misclassified_count"))
    events_passed = dated_count >= 2 and transmitted_count >= 2 and past_as_future == 0
    event_score = 5.0 if events_passed else min(dated_count, transmitted_count, 2) / 2 * 5.0
    checks.append(
        GateCheck(
            gate="future_event_transmission",
            passed=events_passed,
            score=event_score,
            maximum=5.0,
            message=(
                "future events have dates/windows, operating transmission, and falsification criteria"
                if events_passed
                else (
                    f"dated={dated_count}, transmitted={transmitted_count}, "
                    f"past_misclassified={past_as_future}"
                )
            ),
            core=False,
        )
    )

    total_score = round(sum(check.score for check in checks), 2)
    core_gate_passed = all(check.passed for check in checks if check.core)
    blocker_count = sum(1 for check in checks if check.core and not check.passed)
    ready = core_gate_passed and total_score >= threshold
    decision = "candidate_ready_for_exact_hash_review" if ready else "needs_backflow"

    return SemanticGateResult(
        schema_version=SEMANTIC_GATE_SCHEMA_VERSION,
        case_id=case_id,
        decision=decision,
        total_score=total_score,
        threshold=threshold,
        core_gate_passed=core_gate_passed,
        blocker_count=blocker_count,
        checks=tuple(checks),
        candidate_ready_for_exact_hash_review=ready,
        release_authority=False,
        sample_quality_allowed=False,
        p2_allowed=False,
    )


def semantic_result_to_dict(result: SemanticGateResult) -> dict[str, Any]:
    return asdict(result)


__all__ = [
    "GateCheck",
    "SEMANTIC_GATE_SCHEMA_VERSION",
    "SemanticGateResult",
    "evaluate_semantic_candidate",
    "semantic_result_to_dict",
]
