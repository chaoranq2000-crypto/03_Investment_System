#!/usr/bin/env python3
"""Translate Bundle 7 quality backflow into a deterministic Bundle 8 plan.

The planner consumes existing blocker metadata. It does not acquire evidence,
change workflow state, or mark any TODO resolved.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
from pathlib import Path
from typing import Any

import yaml


DEFAULT_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
BASELINE_COMMIT = "6513350ab371cd2e5612fe2fb4a3f4c1f2f5f9d0"

BUNDLE8_CODES = {
    "independent_research_evidence_below_minimum": "B8-M3-EVIDENCE-COVERAGE",
    "peer_operating_evidence_missing": "B8-M3-EVIDENCE-COVERAGE",
    "independent_industry_evidence_missing": "B8-M3-INDUSTRY-RESEARCH",
    "insufficient_analytical_unit_coverage": "B8-M4-ANALYSIS-ENGINE",
}

DEFERRED_BUNDLES = {
    "forecast_not_bottom_up_or_segment_driven": "R5_BUNDLE_9",
    "forecast_bridge_uses_aggregate_residual": "R5_BUNDLE_9",
    "valuation_lacks_reverse_or_scenario_value_range": "R5_BUNDLE_9",
    "credible_peer_context_below_minimum": "R5_BUNDLE_9",
    "technical_analysis_inputs_missing": "R5_BUNDLE_10",
    "sentiment_analysis_inputs_missing": "R5_BUNDLE_10",
    "catalyst_event_chain_incomplete": "R5_BUNDLE_10",
    "reader_report_below_research_density_floor": "R5_BUNDLE_10",
}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _stable_task_id(code: str) -> str:
    digest = hashlib.sha1(code.encode("utf-8"), usedforsecurity=False).hexdigest()[:8].upper()
    return f"R5B8-{digest}"


def _workstream_templates() -> list[dict[str, Any]]:
    return [
        {
            "workstream_id": "B8-M3-EVIDENCE-COVERAGE",
            "module": "M3_evidence_coverage_and_research_inputs",
            "owner_skill": "evidence-ingest",
            "stage": "T2_evidence_acquire_parse",
            "depends_on": [],
            "target_artifacts": [
                "R5_bundle8_evidence_source_catalog.yaml",
                "evidence_coverage_matrix.yaml",
                "company_operating_evidence_pack.yaml",
                "peer_operating_pack.yaml",
            ],
            "exit_criteria": [
                "all blocking coverage rows are covered",
                "underlying-source deduplication is applied",
                "at least four independent underlying sources are reviewed",
                "at least three unique peers have operating evidence",
                "issuer-only material does not satisfy independent-industry thresholds",
            ],
        },
        {
            "workstream_id": "B8-M3-INDUSTRY-RESEARCH",
            "module": "M3_evidence_coverage_and_research_inputs",
            "owner_skill": "segment-research",
            "stage": "T5_analysis_pack_build",
            "depends_on": ["B8-M3-EVIDENCE-COVERAGE"],
            "target_artifacts": [
                "industry_evidence_pack.yaml",
                "competitive_position_matrix.yaml",
            ],
            "exit_criteria": [
                "industry demand has at least two independent underlying sources",
                "industry supply/competition has at least two independent underlying sources",
                "counterevidence and uncertainty remain visible",
                "peer comparability and non-comparability are explicit",
            ],
        },
        {
            "workstream_id": "B8-M4-ANALYSIS-ENGINE",
            "module": "M4_research_analysis_engine",
            "owner_skill": "stock-deep-dive",
            "stage": "T5_analysis_pack_build",
            "depends_on": [
                "B8-M3-EVIDENCE-COVERAGE",
                "B8-M3-INDUSTRY-RESEARCH",
            ],
            "target_artifacts": [
                "R5_bundle8_analysis_inputs_v2.yaml",
                "analysis_pack_v2.yaml",
                "thesis_tree.yaml",
                "business_driver_tree.yaml",
                "segment_economics.yaml",
                "competitive_position_matrix.yaml",
                "risk_counterevidence_pack.yaml",
            ],
            "exit_criteria": [
                "at least seven complete analysis units pass",
                "each required unit contains judgment, trend, mechanism and financial impact",
                "each required unit contains counterevidence, falsification and watch metrics",
                "all source and metric references resolve to reviewed inputs",
                "generic or duplicated template analysis is rejected",
            ],
        },
        {
            "workstream_id": "B8-INTEGRATION-GATE",
            "module": "M3_M4_integration",
            "owner_skill": "quality-review",
            "stage": "T9_quality_review",
            "depends_on": ["B8-M4-ANALYSIS-ENGINE"],
            "target_artifacts": [
                "R5_bundle8_research_depth_gate.yaml",
                "R5_bundle8_research_depth_gate.md",
            ],
            "exit_criteria": [
                "evidence coverage gate passes",
                "analysis pack gate passes",
                "workflow state is not mutated by the gate",
                "reader report is not regenerated in Bundle 8",
                "Bundle 9 handoff is explicit and Bundle 8 is not auto-closed",
            ],
        },
    ]


def build_plan(
    backflow: dict[str, Any],
    *,
    as_of_date: str,
    source_path: str,
) -> dict[str, Any]:
    issues = backflow.get("generated_issues") or []
    accepted: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    workstream_issue_ids: dict[str, list[str]] = {}

    for issue in issues:
        if not isinstance(issue, dict):
            continue
        code = str(issue.get("code", ""))
        normalized = {
            "task_id": _stable_task_id(code),
            "source_issue_id": str(issue.get("issue_id", "")),
            "code": code,
            "description": str(issue.get("description", "")),
            "source_owner_skill": str(issue.get("fix_owner_skill", "")),
            "source_stage": str(issue.get("stage", "")),
            "source_target_artifact": str(issue.get("target_artifact", "")),
            "status": "open",
        }
        if code in BUNDLE8_CODES:
            workstream_id = BUNDLE8_CODES[code]
            normalized["workstream_id"] = workstream_id
            accepted.append(normalized)
            workstream_issue_ids.setdefault(workstream_id, []).append(
                str(issue.get("issue_id", ""))
            )
        elif code in DEFERRED_BUNDLES:
            normalized["deferred_to_bundle"] = DEFERRED_BUNDLES[code]
            deferred.append(normalized)
        else:
            normalized["reason"] = "unmapped_backflow_code"
            unknown.append(normalized)

    workstreams = _workstream_templates()
    for workstream in workstreams:
        workstream["source_issue_ids"] = sorted(
            item for item in workstream_issue_ids.get(workstream["workstream_id"], []) if item
        )

    required_codes = set(BUNDLE8_CODES)
    accepted_codes = {item["code"] for item in accepted}
    missing_required_codes = sorted(required_codes - accepted_codes)
    entry_state = backflow.get("target_state") or {}
    entry_ok = (
        backflow.get("source_decision") == "rejected"
        and str(entry_state.get("status", "needs_fix")) == "needs_fix"
        and str(entry_state.get("required_next_skill", "evidence-ingest")) == "evidence-ingest"
    )
    plan_decision = (
        "bundle8_plan_ready"
        if entry_ok and not missing_required_codes and not unknown
        else "bundle8_plan_blocked"
    )

    return {
        "artifact_type": "R5_bundle8_research_depth_execution_plan",
        "schema_version": "v0.1",
        "bundle_id": "R5_BUNDLE_8_RESEARCH_DEPTH",
        "baseline_commit": BASELINE_COMMIT,
        "workflow_id": str(backflow.get("workflow_id", "")),
        "as_of_date": as_of_date,
        "source_backflow_plan": source_path,
        "entry_state": {
            "source_decision": backflow.get("source_decision"),
            "quality_band": backflow.get("quality_band"),
            "reader_score": backflow.get("score"),
            "reader_threshold": backflow.get("threshold"),
            "workflow_status": entry_state.get("status", "needs_fix"),
            "required_next_skill": entry_state.get("required_next_skill", "evidence-ingest"),
            "entry_gate_passed": entry_ok,
        },
        "scope": {
            "included_modules": [
                "M3_evidence_coverage_and_research_inputs",
                "M4_research_analysis_engine",
            ],
            "excluded_modules": [
                "M5_forecast_engine",
                "M6_valuation_and_implied_expectations",
                "M7_report_narrative_and_traceability",
                "M8_end_to_end_and_sample_benchmark",
            ],
        },
        "plan_decision": plan_decision,
        "accepted_bundle8_issues": accepted,
        "deferred_issues": deferred,
        "unmapped_issues": unknown,
        "missing_required_codes": missing_required_codes,
        "workstreams": workstreams,
        "execution_order": [item["workstream_id"] for item in workstreams],
        "research_input_minimums": {
            "independent_underlying_sources": 4,
            "credible_peers_with_operating_data": 3,
            "complete_analysis_units": 7,
            "industry_demand_independent_sources": 2,
            "industry_supply_independent_sources": 2,
        },
        "state_policy": {
            "mutate_workflow_state_on_plan": False,
            "resolve_open_todos_on_plan": False,
            "update_canonical_index_on_plan": False,
            "reader_regeneration_allowed": False,
            "automatic_bundle_close_allowed": False,
            "bundle9_handoff_allowed_after_gate_pass": True,
        },
        "close_conditions": [
            "Bundle 8 evidence and analysis gates pass on real reviewed inputs",
            "full repository tests and CI pass",
            "truthfulness/no-advice boundaries remain green",
            "a separate close patch updates canonical state and TODOs",
        ],
    }


def render_readout(plan: dict[str, Any]) -> str:
    lines = [
        "# R5 Bundle 8 Research Depth Execution Plan",
        "",
        f"- Decision: `{plan['plan_decision']}`",
        f"- Workflow: `{plan['workflow_id']}`",
        f"- Baseline: `{plan['baseline_commit']}`",
        (
            f"- Entry reader score: `{plan['entry_state']['reader_score']}` / "
            f"`{plan['entry_state']['reader_threshold']}`"
        ),
        f"- Accepted Bundle 8 issues: `{len(plan['accepted_bundle8_issues'])}`",
        f"- Deferred issues: `{len(plan['deferred_issues'])}`",
        "",
        "## Execution order",
        "",
    ]
    for index, workstream in enumerate(plan["workstreams"], start=1):
        lines.extend(
            [
                f"### {index}. {workstream['workstream_id']}",
                "",
                f"- Owner: `{workstream['owner_skill']}`",
                f"- Stage: `{workstream['stage']}`",
                f"- Dependencies: `{', '.join(workstream['depends_on']) or 'none'}`",
                f"- Source issues: `{', '.join(workstream['source_issue_ids']) or 'none'}`",
                "- Outputs:",
                *[f"  - `{item}`" for item in workstream["target_artifacts"]],
                "- Exit criteria:",
                *[f"  - {item}" for item in workstream["exit_criteria"]],
                "",
            ]
        )
    lines.extend(
        [
            "## Boundary",
            "",
            "Planning does not change workflow state, resolve TODOs, regenerate "
            "the reader report, or close Bundle 8.",
            "",
            "Forecast/valuation are deferred to Bundle 9; "
            "technical/sentiment/event, Writer and end-to-end benchmarking are "
            "deferred to Bundle 10.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--workflow-run", default=DEFAULT_RUN)
    parser.add_argument("--backflow-plan")
    parser.add_argument("--output")
    parser.add_argument("--readout-output")
    parser.add_argument("--as-of-date", default=dt.date.today().isoformat())
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    run = Path(args.workflow_run)
    if not run.is_absolute():
        run = root / run
    backflow_path = (
        Path(args.backflow_plan)
        if args.backflow_plan
        else run / "R5_bundle7_quality_backflow_plan.yaml"
    )
    output = (
        Path(args.output)
        if args.output
        else run / "R5_bundle8_research_depth_execution_plan.yaml"
    )
    readout = (
        Path(args.readout_output)
        if args.readout_output
        else run / "R5_bundle8_research_depth_execution_plan.md"
    )
    backflow_path = backflow_path if backflow_path.is_absolute() else root / backflow_path
    output = output if output.is_absolute() else root / output
    readout = readout if readout.is_absolute() else root / readout

    plan = build_plan(
        load_yaml(backflow_path),
        as_of_date=args.as_of_date,
        source_path=_relative(backflow_path, root),
    )
    write_yaml(output, plan)
    readout.parent.mkdir(parents=True, exist_ok=True)
    readout.write_text(render_readout(plan), encoding="utf-8")
    print(
        "bundle8_plan "
        f"decision={plan['plan_decision']} "
        f"accepted={len(plan['accepted_bundle8_issues'])} "
        f"deferred={len(plan['deferred_issues'])} "
        f"unmapped={len(plan['unmapped_issues'])}"
    )
    return 0 if plan["plan_decision"] == "bundle8_plan_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
