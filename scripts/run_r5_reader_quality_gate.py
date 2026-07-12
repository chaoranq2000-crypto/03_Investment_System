"""Executable R5 Bundle 6 reader-quality gate."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from typing import Any

import yaml


SECTION_HEADINGS = {
    "executive_summary": "## 一、核心研究观点",
    "company_context_and_scope": "## 二、公司背景与研究边界",
    "financial_history_and_cashflow_quality": "## 三、财务历史与现金流质量",
    "business_breakdown_and_economics": "## 四、业务拆分与细分经济性",
    "industry_structure_and_competition": "## 五、行业结构与竞争",
    "forecast_and_scenarios": "## 六、预测与情景",
    "valuation_and_market_expectations": "## 七、估值与市场预期",
    "risks_counterevidence_and_watchpoints": "## 九、风险、反证与观察条件",
    "research_conclusion": "## 十、研究结论与跟踪清单",
}


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def evaluate(report: str, appendix: dict[str, Any], bridge: dict[str, Any], valuation: dict[str, Any], rubric: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []

    def block(code: str, evidence: str) -> None:
        if code not in {x["code"] for x in blockers}:
            blockers.append({"code": code, "evidence": evidence})

    for code, pattern in rubric["forbidden_main_body_patterns"].items():
        match = re.search(pattern, report, flags=re.I)
        if match:
            mapping = {
                "raw_internal_id": "raw_internal_evidence_id_in_main_report",
                "internal_path": "raw_registry_or_workflow_path_in_main_report",
                "machine_label": "readiness_or_visible_gap_token_in_main_report",
                "raw_gap_token": "raw_todo_missing_or_unreviewed_token_in_main_report",
                "direct_advice": "direct_buy_sell_hold_or_position_instruction",
                "fabricated_review": "fabricated_human_review_acceptance",
            }
            block(mapping[code], match.group(0)[:120])
    if re.search(r"\b(?:SAMPLE_FACT|sample_evidence)\b|样例事实", report, re.I):
        block("sample_fact_used_as_evidence", "sample marker found in main report")
    if re.search(r"(?<![0-9])\d{7,}\.\d+", report):
        block("unrounded_raw_cny_dump", "raw large decimal found")

    missing_sections = [section for section, heading in SECTION_HEADINGS.items() if report.count(heading) == 0]
    duplicated_sections = [section for section, heading in SECTION_HEADINGS.items() if report.count(heading) > 1]
    if missing_sections:
        block("missing_mandatory_section", ",".join(missing_sections))
    if duplicated_sections:
        block("duplicate_machine_readiness_sections", ",".join(duplicated_sections))
    if re.search(r"(?:必然|一定|毫无疑问)(?:造成|导致|带来)", report) and not re.search(r"(?:推断|假设|限制|不确定)", report):
        block("unsupported_causal_language", "absolute causal language without qualification")

    used_refs = set(re.findall(r"\[(E[1-9][0-9]*)\]", report))
    appendix_refs = [x.get("display_reference_id") for x in appendix.get("records", [])]
    unresolved = sorted(ref for ref in used_refs if appendix_refs.count(ref) != 1)
    duplicate_appendix_refs = sorted({ref for ref in appendix_refs if appendix_refs.count(ref) > 1})
    if unresolved:
        block("unresolved_traceability_reference", ",".join(unresolved))
    if duplicate_appendix_refs:
        block("unresolved_traceability_reference", "duplicate:" + ",".join(duplicate_appendix_refs))
    if not used_refs:
        block("unsupported_material_fact", "no display citations in main report")

    rows = bridge.get("base_case_bridge") or []
    if not rows or not bridge.get("driver_assumptions") or set((bridge.get("scenarios") or {}).keys()) != {"base_case", "bull_case", "bear_case"}:
        block("forecast_without_driver_bridge", "missing bridge, drivers or scenarios")
    if rows and any(abs(float(row.get("reconciliation_difference", 1))) >= 1e-6 for row in rows):
        block("forecast_arithmetic_mismatch", "EPS reconciliation difference exceeds tolerance")
    snap = valuation.get("dated_snapshot") or {}
    if not valuation.get("as_of_date") or "denominator_control" not in snap or "TTM" not in str(snap.get("denominator_control")):
        block("valuation_without_date_or_denominator_control", "dated snapshot or denominator control absent")

    dimension_scores = dict(rubric["dimensions"])
    if unresolved or duplicate_appendix_refs or not used_refs:
        dimension_scores["evidence_integrity"] = 0
    if missing_sections:
        dimension_scores["coverage_completeness"] = max(0, rubric["dimensions"]["coverage_completeness"] - 2 * len(missing_sections))
    if any(x["code"] in {"forecast_without_driver_bridge", "forecast_arithmetic_mismatch", "valuation_without_date_or_denominator_control"} for x in blockers):
        dimension_scores["forecast_and_valuation"] = 0
    if duplicated_sections:
        dimension_scores["narrative_and_readability"] = 0
    if any(x["code"] in {"raw_internal_evidence_id_in_main_report", "raw_registry_or_workflow_path_in_main_report", "readiness_or_visible_gap_token_in_main_report", "raw_todo_missing_or_unreviewed_token_in_main_report", "unrounded_raw_cny_dump"} for x in blockers):
        dimension_scores["presentation_hygiene"] = 0
    score = sum(dimension_scores.values())
    decision = "candidate_ready_for_human_review" if score >= rubric["candidate_threshold"] and not blockers else "rejected"
    leakage_codes = {"raw_internal_evidence_id_in_main_report", "raw_registry_or_workflow_path_in_main_report", "readiness_or_visible_gap_token_in_main_report", "raw_todo_missing_or_unreviewed_token_in_main_report"}
    numeric_violations = sum(1 for x in blockers if x["code"] == "unrounded_raw_cny_dump")
    return {
        "artifact_type": "R5_stock_research_report_reader_v2_quality_scorecard",
        "schema_version": "v0.1",
        "decision": decision,
        "score": score,
        "threshold": rubric["candidate_threshold"],
        "critical_blocker_count": len(blockers),
        "critical_blockers": blockers,
        "warnings": [],
        "dimension_scores": dimension_scores,
        "required_section_coverage": {"covered": len(SECTION_HEADINGS) - len(missing_sections), "required": len(SECTION_HEADINGS), "missing": missing_sections, "duplicated": duplicated_sections},
        "display_citations": {"used": sorted(used_refs), "appendix_records": len(appendix_refs), "unresolved": unresolved, "duplicate_appendix_references": duplicate_appendix_refs},
        "unresolved_citation_count": len(unresolved) + len(duplicate_appendix_refs),
        "machine_token_leakage_count": sum(1 for x in blockers if x["code"] in leakage_codes),
        "numeric_format_violation_count": numeric_violations,
        "conclusion_state": decision,
        "truthfulness_status": "pass",
        "human_review_required": True,
        "human_review_status": "pending",
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--report")
    parser.add_argument("--appendix")
    parser.add_argument("--bridge")
    parser.add_argument("--valuation")
    parser.add_argument("--output")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    run = root / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
    report_path = Path(args.report) if args.report else run / "R5_stock_research_report_reader_v2.md"
    appendix_path = Path(args.appendix) if args.appendix else run / "R5_stock_research_report_traceability_v2.yaml"
    bridge_path = Path(args.bridge) if args.bridge else run / "R5_bundle6_forecast_bridge.yaml"
    valuation_path = Path(args.valuation) if args.valuation else run / "R5_bundle6_valuation_reasoning_pack.yaml"
    output_path = Path(args.output) if args.output else run / "R5_stock_research_report_reader_v2_quality_scorecard.yaml"
    report = report_path.read_text(encoding="utf-8")
    scorecard = evaluate(report, load_yaml(appendix_path), load_yaml(bridge_path), load_yaml(valuation_path), load_yaml(root / "config/r5_reader_quality_rubric.yaml"))
    scorecard["input_hashes"] = {"report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(), "appendix_sha256": hashlib.sha256(appendix_path.read_bytes()).hexdigest(), "forecast_bridge_sha256": hashlib.sha256(bridge_path.read_bytes()).hexdigest(), "valuation_reasoning_sha256": hashlib.sha256(valuation_path.read_bytes()).hexdigest()}
    output_path.write_text(yaml.safe_dump(scorecard, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"reader_quality_gate decision={scorecard['decision']} score={scorecard['score']} blockers={scorecard['critical_blocker_count']} human_review=pending sample_quality=false p2=false")
    return 0 if scorecard["decision"] == "candidate_ready_for_human_review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
