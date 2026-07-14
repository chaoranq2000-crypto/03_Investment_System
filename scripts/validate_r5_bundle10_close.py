from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


DEFAULT_WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_validator(repo_root: Path):
    path = repo_root / "scripts/validate_r5_reader_report_pack.py"
    spec = importlib.util.spec_from_file_location("validate_r5_reader_report_pack_bundle10", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_submission_validator(repo_root: Path):
    path = repo_root / "scripts/validate_r5_bundle10_human_review_submission.py"
    spec = importlib.util.spec_from_file_location(
        "validate_r5_bundle10_human_review_submission_bundle10", path
    )
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_bundle10(repo_root: Path, workflow_id: str) -> dict[str, Any]:
    run = repo_root / "reports/workflow_runs" / workflow_id
    required = [
        "R5_bundle10_technical_market_pack.yaml",
        "R5_bundle10_sentiment_event_pack.yaml",
        "R5_bundle10_reader_gate_forecast.yaml",
        "R5_bundle10_reader_gate_valuation.yaml",
        "R5_bundle10_reader_pack.yaml",
        "R5_bundle10_reader_pack_build_readout.yaml",
        "R5_stock_research_report_reader_v3.md",
        "R5_stock_research_report_traceability_v3.yaml",
        "R5_stock_research_report_reader_v3_quality_scorecard.yaml",
        "R5_bundle10_cross_industry_writer_regression.yaml",
        "bundle10_cross_industry_regression/industrial_equipment_reader.md",
        "bundle10_cross_industry_regression/healthcare_services_reader.md",
        "R5_stock_research_report_reader_v3_human_review.yaml",
        "R5_stock_research_report_reader_v3_human_review_form.md",
        "R5_stock_research_report_reader_v3_human_review_submission_template.yaml",
        "R5_bundle10_ai_assisted_semantic_precheck.yaml",
    ]
    errors: list[str] = []
    missing = [name for name in required if not (run / name).exists()]
    if missing:
        errors.extend(f"missing required artifact: {name}" for name in missing)
    checks: dict[str, Any] = {"required_artifacts": {"count": len(required), "missing": missing}}
    if missing:
        return {
            "artifact_type": "R5_bundle10_close_input_validation",
            "schema_version": "v0.1",
            "workflow_id": workflow_id,
            "decision": "fail",
            "checks": checks,
            "errors": errors,
        }

    writer_source = (repo_root / "src/report/r5_reader_report_writer.py").read_text(encoding="utf-8")
    hardcoded = [token for token in ("英维克", "002837", workflow_id) if token in writer_source]
    if hardcoded:
        errors.append(f"reader writer contains workflow identity hardcoding: {hardcoded}")
    checks["writer_hardcoding"] = {"identity_tokens_found": hardcoded}

    pack = load_yaml(run / "R5_bundle10_reader_pack.yaml")
    pack_issues = load_validator(repo_root).validate_pack(pack, repo_root)
    if pack_issues:
        errors.append(f"reader pack contract issues: {pack_issues}")
    checks["reader_pack_contract"] = {
        "section_count": len(pack.get("sections") or []),
        "traceability_record_count": len(pack.get("traceability_records") or []),
        "issues": pack_issues,
    }

    scorecard = load_yaml(run / "R5_stock_research_report_reader_v3_quality_scorecard.yaml")
    if scorecard.get("decision") != "candidate_ready_for_human_review":
        errors.append("reader scorecard is not candidate_ready_for_human_review")
    if scorecard.get("score", 0) < scorecard.get("threshold", 999):
        errors.append("reader score is below threshold")
    if scorecard.get("critical_blocker_count") != 0 or scorecard.get("truthfulness_status") != "pass":
        errors.append("reader truthfulness or blocker gate failed")
    if scorecard.get("candidate_blockers") or scorecard.get("truthfulness_blockers"):
        errors.append("reader scorecard contains blockers")
    if scorecard.get("human_review_status") != "pending":
        errors.append("automated gate must keep external human review pending")
    if scorecard.get("sample_quality_report_allowed") is not False or scorecard.get("p2_allowed") is not False:
        errors.append("reader gate must remain fail-closed for sample quality and P2")
    expected_report_hash = sha(run / "R5_stock_research_report_reader_v3.md")
    expected_appendix_hash = sha(run / "R5_stock_research_report_traceability_v3.yaml")
    hashes = scorecard.get("input_hashes") or {}
    if hashes.get("report_sha256") != expected_report_hash:
        errors.append("scorecard report hash does not match reader v3")
    if hashes.get("appendix_sha256") != expected_appendix_hash:
        errors.append("scorecard appendix hash does not match traceability v3")
    checks["reader_quality_gate"] = {
        "decision": scorecard.get("decision"),
        "score": scorecard.get("score"),
        "threshold": scorecard.get("threshold"),
        "critical_blockers": scorecard.get("critical_blocker_count"),
        "truthfulness": scorecard.get("truthfulness_status"),
        "human_review": scorecard.get("human_review_status"),
    }

    market = scorecard.get("market_event_capabilities") or {}
    market_required = (
        "technical", "sentiment", "future_dated_event", "event_impact_path",
        "event_verification_metric", "event_counterevidence_condition",
    )
    missing_market = [key for key in market_required if market.get(key) is not True]
    if missing_market:
        errors.append(f"market/sentiment/event chain incomplete: {missing_market}")
    forecast = scorecard.get("forecast_capabilities") or {}
    if not all(
        forecast.get(key) is True
        for key in (
            "has_base_case_2026E_2028E", "has_driver_assumptions", "has_three_scenarios",
            "arithmetic_reconciles", "segment_driven", "disaggregated_cost_tax_minority_bridge",
        )
    ) or forecast.get("uses_aggregate_residual_bridge") is not False:
        errors.append("reader forecast capabilities are incomplete")
    valuation = scorecard.get("valuation_capabilities") or {}
    if valuation.get("credible_peer_count", 0) < 3:
        errors.append("fewer than three reviewed peer inputs reached the reader gate")
    if not (valuation.get("reverse_valuation") and valuation.get("scenario_value_ranges")):
        errors.append("reverse and scenario valuation must both be visible")
    checks["capabilities"] = {
        "market_event": {key: market.get(key) for key in market_required},
        "forecast": forecast,
        "valuation": valuation,
    }

    cross = load_yaml(run / "R5_bundle10_cross_industry_writer_regression.yaml")
    if cross.get("decision") != "pass" or cross.get("case_count", 0) < 2 or cross.get("distinct_industries", 0) < 2:
        errors.append("cross-industry Writer regression did not pass two distinct industries")
    if cross.get("writer_identity_hardcoding") is not False or cross.get("cross_sample_identity_leakage") is not False:
        errors.append("cross-industry Writer regression found identity leakage")
    if cross.get("fixture_boundary") != "synthetic_layout_and_schema_regression_only":
        errors.append("cross-industry fixture boundary is missing or overstated")
    narrative = cross.get("narrative_quality") or {}
    if (
        narrative.get("status") != "pass"
        or narrative.get("total_duplicate_paragraph_count") != 0
        or narrative.get("malformed_pattern_hits")
        or narrative.get("prohibited_advice_hits")
        or narrative.get("minimum_unique_section_judgment_count") != 10
        or narrative.get("total_judgment_restatement_count") != 0
    ):
        errors.append("cross-industry Writer narrative-quality regression failed")
    result_quality = [row.get("narrative_quality") or {} for row in cross.get("results") or []]
    if len(result_quality) < 2 or any(row.get("status") != "pass" for row in result_quality):
        errors.append("cross-industry Writer cases lack per-case narrative-quality evidence")
    checks["cross_industry_regression"] = {
        "decision": cross.get("decision"),
        "case_count": cross.get("case_count"),
        "distinct_industries": cross.get("distinct_industries"),
        "fixture_boundary": cross.get("fixture_boundary"),
        "narrative_quality": narrative,
    }

    handoff = load_yaml(run / "R5_stock_research_report_reader_v3_human_review.yaml")
    review_form_path = run / "R5_stock_research_report_reader_v3_human_review_form.md"
    review_form = review_form_path.read_text(encoding="utf-8")
    submission_template_path = run / "R5_stock_research_report_reader_v3_human_review_submission_template.yaml"
    submission_template = load_yaml(submission_template_path)
    submission_validator = repo_root / "scripts/validate_r5_bundle10_human_review_submission.py"
    finalizer = repo_root / "scripts/finalize_r5_bundle10_after_human_review.py"
    precheck = load_yaml(run / "R5_bundle10_ai_assisted_semantic_precheck.yaml")
    if handoff.get("reader_report_sha256") != expected_report_hash:
        errors.append("human-review handoff report hash mismatch")
    if handoff.get("traceability_appendix_sha256") != expected_appendix_hash:
        errors.append("human-review handoff appendix hash mismatch")
    handoff_status = handoff.get("status")
    if handoff_status not in {
        "pending_external_human_review",
        "passed_external_human_review",
    }:
        errors.append("external human review status is neither pending nor passed")
    if Path(str(handoff.get("review_form_path") or "")).name != review_form_path.name:
        errors.append("external human-review form path is missing or mismatched")
    if Path(str(handoff.get("submission_template_path") or "")).name != submission_template_path.name:
        errors.append("external human-review submission template path is missing or mismatched")
    if expected_report_hash not in review_form or expected_appendix_hash not in review_form:
        errors.append("external human-review form is not bound to current report and appendix hashes")
    if any(f"| HR-{number} |" not in review_form for number in range(1, 7)):
        errors.append("external human-review form does not expose all six checklist rows")
    if review_form.count("| `pending` |") != 6 or "form_status: `pending_external_human_review`" not in review_form:
        errors.append("external human-review form is not fail-closed pending")
    template_rows = submission_template.get("required_checklist") or []
    template_attestation = submission_template.get("attestation") or {}
    if (
        submission_template.get("decision") is not None
        or submission_template.get("external_reviewer") is not None
        or len(template_rows) != 6
        or any(row.get("status") != "pending" for row in template_rows)
        or template_attestation.get("external_human_review_confirmed") is not False
        or template_attestation.get("automated_agent_generated") is not None
    ):
        errors.append("external human-review submission template is not fail-closed")
    if not submission_validator.exists() or not finalizer.exists():
        errors.append("external human-review validation/finalization path is incomplete")
    if precheck.get("status") != "pass_for_external_human_handoff" or precheck.get("external_human_review_status") != "pending":
        errors.append("AI semantic precheck or external-review boundary is invalid")
    if not all((precheck.get("checks") or {}).values()):
        errors.append("AI semantic precheck contains a failing check")
    if precheck.get("sample_quality_report_allowed") is not False or precheck.get("p2_allowed") is not False:
        errors.append("AI precheck must remain fail-closed and cannot claim P2")

    lifecycle = "invalid"
    submission_validation_result: Mapping[str, Any] | None = None
    final_close_validation: Mapping[str, Any] | None = None
    final_artifact_missing: list[str] = []
    if handoff_status == "pending_external_human_review":
        lifecycle = "pending_external_human_review"
        if handoff.get("external_reviewer") is not None or handoff.get("reviewed_at") is not None:
            errors.append("pending handoff must not contain reviewer identity or timestamp")
        if any(row.get("status") != "pending" for row in handoff.get("required_checklist") or []):
            errors.append("pending handoff checklist must remain pending")
        if handoff.get("sample_quality_report_allowed") is not False or handoff.get("p2_allowed") is not False:
            errors.append("pending handoff must keep sample quality and P2 false")
    elif handoff_status == "passed_external_human_review":
        lifecycle = "passed_external_human_review"
        final_artifacts = [
            "R5_stock_research_report_reader_v3_human_review_submission.yaml",
            "R5_bundle10_human_review_submission_validation.json",
            "R5_bundle10_final_close_validation.json",
            "bundle10_final_close_readout.md",
        ]
        final_artifact_missing = [name for name in final_artifacts if not (run / name).exists()]
        errors.extend(f"missing final-close artifact: {name}" for name in final_artifact_missing)
        if not handoff.get("external_reviewer") or not handoff.get("reviewed_at"):
            errors.append("passed handoff must contain reviewer identity and timestamp")
        if any(row.get("status") != "pass" for row in handoff.get("required_checklist") or []):
            errors.append("passed handoff must contain six passed checklist rows")
        if handoff.get("blocking_comments"):
            errors.append("passed handoff must contain zero blocking comments")
        if (handoff.get("signoff_fields") or {}).get("decision") != "pass":
            errors.append("passed handoff signoff decision must be pass")
        if handoff.get("sample_quality_report_allowed") is not True or handoff.get("p2_allowed") is not False:
            errors.append("passed handoff must allow sample quality and keep P2 false")
        if not final_artifact_missing:
            submission_path = run / final_artifacts[0]
            submission_validation_result = load_submission_validator(repo_root).validate_submission(
                run, submission_path
            )
            if (
                submission_validation_result.get("decision") != "pass"
                or submission_validation_result.get("eligible_for_bundle10_final_close") is not True
            ):
                errors.append(
                    "final human-review submission validation failed: "
                    + "; ".join(submission_validation_result.get("errors") or [])
                )
            stored_submission_validation = json.loads(
                (run / final_artifacts[1]).read_text(encoding="utf-8")
            )
            if (
                stored_submission_validation.get("decision") != "pass"
                or stored_submission_validation.get("eligible_for_bundle10_final_close") is not True
                or stored_submission_validation.get("report_sha256") != expected_report_hash
            ):
                errors.append("stored human-review submission validation is invalid")
            final_close_validation = json.loads(
                (run / final_artifacts[2]).read_text(encoding="utf-8")
            )
            if (
                final_close_validation.get("decision") != "pass"
                or final_close_validation.get("sample_quality_allowed") is not True
                or final_close_validation.get("p2_allowed") is not False
            ):
                errors.append("stored Bundle 10 final-close validation is invalid")
            state = load_yaml(run / "workflow_state.yaml")
            close = state.get("bundle10_close") or {}
            snapshot = state.get("reader_candidate_snapshot") or {}
            internal = state.get("bundle10_internal_completion") or {}
            forward_bundle9r = state.get("bundle9r_close") or {}
            forward_bundle10r_review = state.get("bundle10r_v5_human_review") or {}
            forward_bundle13r = state.get("bundle13r_backflow_execution") or {}
            forward_bundle10r_review_failure_is_valid = (
                state.get("status") == "needs_fix"
                and state.get("current_stage") == "T9_quality_review"
                and state.get("next_stage") == "T7_stock_report_draft"
                and state.get("required_next_skill") == "stock-deep-dive"
                and state.get("canonical_reader_status") == "reader_v5_human_review_revision_required"
                and forward_bundle10r_review.get("decision") in {"revision_required", "rejected"}
                and forward_bundle10r_review.get("status") == "needs_fix"
                and forward_bundle10r_review.get("sample_quality_allowed") is False
                and forward_bundle10r_review.get("p2_allowed") is False
            )
            forward_bundle13r_backflow_is_valid = (
                state.get("status") == "in_progress"
                and state.get("current_stage") == "R5_bundle13r_t1_t2_evidence_backflow"
                and state.get("next_stage") == "R5_bundle13r_t1_t2_evidence_backflow"
                and state.get("required_next_skill") == "evidence-ingest"
                and forward_bundle13r.get("status") == "backflow_execution_in_progress"
                and forward_bundle13r.get("unresolved_t1_t2_item_count", 0) > 0
                and forward_bundle13r.get("human_review_status") == "pending"
                and forward_bundle13r.get("sample_quality_allowed") is False
                and forward_bundle13r.get("p2_allowed") is False
            )
            historical_bundle10_close_is_preserved = (
                state.get("current_stage") == "T10_close_readout"
                or (
                    state.get("current_stage") == "R5_bundle9r_closed"
                    and forward_bundle9r.get("bundle_closed") is True
                    and forward_bundle9r.get("historical_bundle10_preserved") is True
                )
                or forward_bundle10r_review_failure_is_valid
                or forward_bundle13r_backflow_is_valid
            )
            if (
                (
                    state.get("status") != "accepted_with_todos"
                    and not forward_bundle10r_review_failure_is_valid
                    and not forward_bundle13r_backflow_is_valid
                )
                or not historical_bundle10_close_is_preserved
                or state.get("external_action_required") is not None
            ):
                errors.append("historical Bundle 10 close is not finalized or preserved across forward rebuild")
            if (
                close.get("bundle_closed") is not True
                or close.get("external_human_review") != "passed"
                or close.get("sample_quality_allowed") is not True
                or close.get("p2_allowed") is not False
            ):
                errors.append("workflow bundle10_close boundary is invalid")
            if (
                snapshot.get("human_review_status") != "passed_external"
                or snapshot.get("sample_quality_report_allowed") is not True
                or snapshot.get("p2_allowed") is not False
            ):
                errors.append("reader candidate snapshot is not synchronized to final review")
            if (
                internal.get("bundle_closed") is not True
                or internal.get("external_human_review") != "passed"
                or internal.get("sample_quality_allowed") is not True
                or internal.get("p2_allowed") is not False
            ):
                errors.append("Bundle 10 internal completion state is not finalized")
            final_readout = (run / final_artifacts[3]).read_text(encoding="utf-8")
            if "external_human_review: `passed`" not in final_readout or "p2_allowed: `false`" not in final_readout:
                errors.append("final close readout does not preserve human-review/P2 boundary")
    checks["required_artifacts"]["final_close_missing"] = final_artifact_missing
    checks["human_review_boundary"] = {
        "lifecycle": lifecycle,
        "handoff_status": handoff_status,
        "review_form": review_form_path.name,
        "submission_template": submission_template_path.name,
        "submission_validator": submission_validator.name,
        "finalizer": finalizer.name,
        "external_reviewer": handoff.get("external_reviewer"),
        "ai_precheck": precheck.get("status"),
        "sample_quality_allowed": handoff.get("sample_quality_report_allowed"),
        "p2_allowed": handoff.get("p2_allowed"),
        "submission_validation": (
            submission_validation_result.get("decision")
            if submission_validation_result is not None
            else None
        ),
        "final_close_validation": (
            final_close_validation.get("decision")
            if final_close_validation is not None
            else None
        ),
    }

    return {
        "artifact_type": "R5_bundle10_close_input_validation",
        "schema_version": "v0.1",
        "workflow_id": workflow_id,
        "decision": "pass" if not errors else "fail",
        "checks": checks,
        "errors": errors,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Bundle 10 automated completion and external-review boundary.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--workflow-id", default=DEFAULT_WORKFLOW_ID)
    parser.add_argument("--output", default="")
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    payload = validate_bundle10(root, args.workflow_id)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
