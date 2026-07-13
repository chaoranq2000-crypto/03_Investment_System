"""Executable R5 Bundle 7 reader-quality gate.

The Bundle 6 gate awarded full dimension scores before inspecting the report and
then deducted points only for formatting or traceability defects.  This version
scores every dimension from zero, separates truthfulness blockers from research-
depth blockers, and emits deterministic fix routes for the orchestrator.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import yaml


SECTION_HEADINGS = {
    "executive_summary": "## 一、核心研究观点",
    "company_context_and_scope": "## 二、公司背景与研究边界",
    "financial_history_and_cashflow_quality": "## 三、财务历史与现金流质量",
    "business_breakdown_and_economics": "## 四、业务拆分与细分经济性",
    "industry_structure_and_competition": "## 五、行业结构与竞争",
    "forecast_and_scenarios": "## 六、预测与情景",
    "valuation_and_market_expectations": "## 七、估值与市场预期",
    "dated_events": "## 八、有日期的公司事件",
    "risks_counterevidence_and_watchpoints": "## 九、风险、反证与观察条件",
    "research_conclusion": "## 十、研究结论与跟踪清单",
}

CORE_ANALYSIS_SECTIONS = (
    "executive_summary",
    "financial_history_and_cashflow_quality",
    "business_breakdown_and_economics",
    "industry_structure_and_competition",
    "forecast_and_scenarios",
    "valuation_and_market_expectations",
    "dated_events",
    "risks_counterevidence_and_watchpoints",
    "research_conclusion",
)

SIGNAL_PATTERNS = {
    "judgment": r"(?:核心|判断|结论|定位|说明|反映|意味着|支撑|研究矛盾|关键)",
    "trend": r"(?:同比|环比|CAGR|复合增速|上升|下降|增长|下滑|改善|恶化|扩大|收窄|背离|从[^。；]{0,30}(?:升|降|增|减)至)",
    "causal": r"(?:因为|由于|源于|驱动|导致|受[^。；]{0,25}影响|背后|核心原因|根本原因|传导|决定|解释|带动)",
    "economic_impact": r"(?:收入|毛利|利润|现金流|成本|费用率|净利率|ROE|ROIC|每股收益|估值|市盈率|市销率|定价|盈利|资本回报)",
    "counterevidence": r"(?:但|然而|反证|风险|限制|约束|不确定|不足|不能|尚未|缺少|未披露|低于预期|相反)",
    "watchpoint": r"(?:关注|跟踪|观察|验证|条件|阈值|若|一旦|未来|后续|触发|关键节点|发布日期|偏差)",
    "assumption": r"(?:假设|情景|基准|上行|下行|敏感性|模型输入|口径|约束)",
    "peer": r"(?:同业|可比|同行|竞争对手|相对估值|同口径)",
    "reverse_valuation": r"(?:隐含[^。；]{0,20}(?:收入|利润|利润率|增速)|反向估值|反推|需要[^。；]{0,20}(?:达到|贡献)|市值[^。；]{0,20}支撑)",
    "technical": r"(?:MA5|MA10|MA20|MA60|均线|成交量|支撑位|阻力位|趋势状态|OHLCV)",
    "sentiment": r"(?:宏观情绪|行业情绪|公司情绪|资金流|换手率|舆情|一致预期|风险偏好)",
    "future_event": r"(?:未来|下一|预计|计划|将于|截至|窗口|催化|会议|业绩预告|年报|中报|季报)",
    "verification_metric": r"(?:毛利率|净利率|收入|利润|现金流|订单|产能|客户|份额|费用率|应收|存货|合同负债|回款)",
}

ROUTE_CATALOG = {
    "evidence": {
        "owner_skill": "evidence-ingest",
        "stage": "T2_evidence_acquire_parse",
        "target_artifacts": [
            "evidence_coverage_matrix.yaml",
            "industry_evidence_pack.yaml",
            "peer_operating_pack.yaml",
        ],
    },
    "analysis": {
        "owner_skill": "stock-deep-dive",
        "stage": "T5_analysis_pack_build",
        "target_artifacts": [
            "thesis_tree.yaml",
            "business_driver_tree.yaml",
            "segment_economics.yaml",
            "risk_counterevidence_pack.yaml",
        ],
    },
    "industry": {
        "owner_skill": "segment-research",
        "stage": "T5_analysis_pack_build",
        "target_artifacts": ["industry_evidence_pack.yaml", "competitive_position_matrix.yaml"],
    },
    "forecast": {
        "owner_skill": "stock-deep-dive",
        "stage": "T6_forecast_valuation_model",
        "target_artifacts": ["segment_forecast_model.yaml", "forecast_bridge.yaml", "forecast_sensitivity.csv"],
    },
    "valuation": {
        "owner_skill": "company-valuation",
        "stage": "RP6_valuation",
        "target_artifacts": ["reverse_valuation.yaml", "scenario_valuation.yaml", "peer_operating_pack.yaml"],
    },
    "market": {
        "owner_skill": "stock-deep-dive",
        "stage": "T7_technical_sentiment_event_pack",
        "target_artifacts": ["technical_snapshot.yaml", "market_sentiment_pack.yaml", "catalyst_calendar.yaml"],
    },
    "narrative": {
        "owner_skill": "memo-writer",
        "stage": "T8_report_draft",
        "target_artifacts": ["reader_report.md", "section_payloads.yaml"],
    },
    "quality": {
        "owner_skill": "quality-review",
        "stage": "T9_quality_review",
        "target_artifacts": ["reader_quality_scorecard.yaml"],
    },
}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clamp(value: float, maximum: int) -> int:
    return max(0, min(maximum, int(round(value))))


def _han_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def _numeric_fact_count(text: str) -> int:
    return len(re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?:%|倍|亿元|万元|元|年|季度|Q[1-4]|E)?", text))


def _extract_sections(report: str) -> tuple[dict[str, str], list[str], list[str]]:
    positions: list[tuple[int, str, str]] = []
    missing: list[str] = []
    duplicated: list[str] = []
    for key, heading in SECTION_HEADINGS.items():
        count = report.count(heading)
        if count == 0:
            missing.append(key)
            continue
        if count > 1:
            duplicated.append(key)
        positions.append((report.index(heading), key, heading))
    positions.sort()
    sections: dict[str, str] = {}
    for idx, (start, key, heading) in enumerate(positions):
        body_start = start + len(heading)
        body_end = positions[idx + 1][0] if idx + 1 < len(positions) else len(report)
        sections[key] = report[body_start:body_end].strip()
    return sections, missing, duplicated


def _signals(text: str) -> dict[str, bool]:
    return {name: bool(re.search(pattern, text, flags=re.I | re.S)) for name, pattern in SIGNAL_PATTERNS.items()}


def _section_diagnostics(sections: dict[str, str], rubric: dict[str, Any]) -> dict[str, dict[str, Any]]:
    minimums = rubric.get("section_minimums") or {}
    diagnostics: dict[str, dict[str, Any]] = {}
    for key in SECTION_HEADINGS:
        text = sections.get(key, "")
        refs = sorted(set(re.findall(r"\[(E[1-9][0-9]*)\]", text)))
        signals = _signals(text)
        cfg = minimums.get(key, {})
        min_han = int(cfg.get("min_han_chars", 100))
        min_refs = int(cfg.get("min_unique_refs", 1))
        required_signals = list(cfg.get("required_signals") or [])
        present_required = [name for name in required_signals if signals.get(name)]
        signal_ratio = len(present_required) / len(required_signals) if required_signals else 1.0
        density_pass = _han_count(text) >= min_han and len(refs) >= min_refs
        analysis_unit_pass = density_pass and signal_ratio >= float(cfg.get("required_signal_ratio", 0.67))
        diagnostics[key] = {
            "han_chars": _han_count(text),
            "numeric_fact_count": _numeric_fact_count(text),
            "paragraph_count": len([x for x in re.split(r"\n\s*\n", text) if x.strip()]),
            "unique_references": refs,
            "signals": signals,
            "required_signals": required_signals,
            "present_required_signals": present_required,
            "signal_ratio": round(signal_ratio, 3),
            "density_pass": density_pass,
            "analysis_unit_pass": analysis_unit_pass,
        }
    return diagnostics


def _underlying_source_ids(appendix: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for record in appendix.get("records", []) or []:
        raw = record.get("raw_evidence_ids") or []
        if isinstance(raw, str):
            raw = [raw]
        ids.update(str(item) for item in raw if item)
    return ids


def _source_category(source_id: str) -> str:
    value = source_id.lower()
    if any(token in value for token in ("annual_report", "interim_report", "quarterly_report", "issuer", "cninfo", "szse", "sse")):
        return "issuer"
    if any(token in value for token in ("market_data", "ohlcv", "quote", "price")):
        return "market"
    if any(token in value for token in ("industry", "association", "policy", "market_size", "supply", "demand")):
        return "industry"
    if any(token in value for token in ("peer", "competitor", "comparable")):
        return "peer"
    if any(token in value for token in ("analyst", "consensus", "broker")):
        return "consensus"
    if any(token in value for token in ("ir", "investor", "interaction", "order", "customer", "capacity")):
        return "company_operating"
    return "other"


def _source_diagnostics(appendix: dict[str, Any]) -> dict[str, Any]:
    records = appendix.get("records", []) or []
    source_ids = _underlying_source_ids(appendix)
    explicit_categories: dict[str, str] = {}
    for record in records:
        category = str(record.get("source_category") or "").strip()
        raw_ids = record.get("raw_evidence_ids") or []
        if isinstance(raw_ids, str):
            raw_ids = [raw_ids]
        for source_id in raw_ids:
            if category:
                explicit_categories[str(source_id)] = category
    category_by_source = {
        source_id: explicit_categories.get(source_id, _source_category(source_id))
        for source_id in source_ids
    }
    categories = Counter(category_by_source.values())
    independent_ids = {
        source_id
        for source_id in source_ids
        if category_by_source[source_id] in {"market", "industry", "peer", "consensus", "company_operating", "other"}
    }
    issuer_ids = {source_id for source_id in source_ids if category_by_source[source_id] == "issuer"}
    complete_metadata = sum(
        1
        for record in records
        if record.get("confidence") and record.get("limitation") and record.get("reviewer_state")
    )
    return {
        "underlying_source_count": len(source_ids),
        "underlying_source_ids": sorted(source_ids),
        "category_counts": dict(sorted(categories.items())),
        "issuer_source_count": len(issuer_ids),
        "independent_source_count": len(independent_ids),
        "independent_source_ids": sorted(independent_ids),
        "metadata_complete_ratio": round(complete_metadata / len(records), 3) if records else 0.0,
    }


def _forecast_capabilities(bridge: dict[str, Any], report_section: str) -> dict[str, Any]:
    rows = bridge.get("base_case_bridge") or []
    scenarios = bridge.get("scenarios") or {}
    assumptions = bridge.get("driver_assumptions") or []
    driver_names = {str(item.get("driver", "")).lower() for item in assumptions if isinstance(item, dict)}
    segment_keywords = ("segment", "business_line", "product", "机房", "机柜", "液冷", "分业务")
    segment_driven = any(any(token in name for token in segment_keywords) for name in driver_names)
    disaggregated_costs = any(
        any(token in str(item.get("driver", "")).lower() for token in ("sales_expense", "admin", "r&d", "finance", "tax", "minority"))
        for item in assumptions
        if isinstance(item, dict)
    )
    residual_bridge = any("implied_tax_finance_other_and_minority" in row for row in rows if isinstance(row, dict))
    arithmetic_ok = bool(rows) and all(abs(float(row.get("reconciliation_difference", 1))) < 1e-6 for row in rows)
    scenario_ok = set(scenarios) == {"base_case", "bull_case", "bear_case"}
    report_signals = _signals(report_section)
    return {
        "has_base_case_2026E_2028E": len(rows) >= 3,
        "has_driver_assumptions": bool(assumptions),
        "has_three_scenarios": scenario_ok,
        "arithmetic_reconciles": arithmetic_ok,
        "segment_driven": segment_driven,
        "disaggregated_cost_tax_minority_bridge": disaggregated_costs,
        "uses_aggregate_residual_bridge": residual_bridge,
        "report_has_assumption_language": report_signals["assumption"],
        "report_has_watch_or_counterevidence": report_signals["watchpoint"] and report_signals["counterevidence"],
        "consensus_comparison": bool(bridge.get("consensus_used")) or bool(re.search(r"一致预期|券商预期|市场预期差", report_section)),
    }


def _valuation_capabilities(valuation: dict[str, Any], report_section: str) -> dict[str, Any]:
    snapshot = valuation.get("dated_snapshot") or {}
    peers = valuation.get("peer_matrix") or []
    scenario_context = valuation.get("scenario_context") or []
    methods = valuation.get("method_eligibility") or []
    active_methods = [item for item in methods if item.get("status") not in {"inactive", "disabled"}]
    credible_peers = [
        item
        for item in peers
        if str(item.get("confidence", "")).lower() not in {"low", "very_low"}
        or (
            str(item.get("source_status", "")).lower() in {"reviewed", "ready", "accepted"}
            and bool(item.get("selection_reason") or item.get("inclusion_reason"))
            and bool(item.get("comparability_limitation") or item.get("limitations"))
        )
    ]
    signals = _signals(report_section)
    has_reverse = signals["reverse_valuation"] or bool(valuation.get("reverse_valuation"))
    scenario_values = valuation.get("scenario_valuation") or valuation.get("valuation_ranges")
    return {
        "dated_snapshot": bool(valuation.get("as_of_date")) and bool(snapshot),
        "denominator_control": "TTM" in str(snapshot.get("denominator_control", "")),
        "peer_count": len(peers),
        "credible_peer_count": len(credible_peers),
        "method_explanation": bool(methods) and bool(active_methods),
        "forward_context": bool(scenario_context),
        "reverse_valuation": has_reverse,
        "scenario_value_ranges": bool(scenario_values),
        "report_has_peer_context": signals["peer"],
    }


def _market_capabilities(sections: dict[str, str], valuation: dict[str, Any]) -> dict[str, Any]:
    joined = "\n".join(sections.values())
    events = sections.get("dated_events", "")
    signals = _signals(joined)
    event_signals = _signals(events)
    date_count = len(re.findall(r"20\d{2}[-年/.]\d{1,2}(?:[-月/.]\d{1,2})?", events))
    future_event = event_signals["future_event"] and date_count > 0
    impact_path = event_signals["causal"] or bool(re.search(r"(?:影响|传导|验证|兑现|改善|压制)", events))
    verification = event_signals["verification_metric"] and event_signals["watchpoint"]
    counter_condition = event_signals["counterevidence"] and event_signals["watchpoint"]
    return {
        "technical": signals["technical"],
        "sentiment": signals["sentiment"],
        "dated_event_count": date_count,
        "future_dated_event": future_event,
        "event_impact_path": impact_path,
        "event_verification_metric": verification,
        "event_counterevidence_condition": counter_condition,
        "market_snapshot": bool(valuation.get("dated_snapshot")),
    }


def _issue(code: str, evidence: str, route: str, severity: str = "medium") -> dict[str, Any]:
    route_def = ROUTE_CATALOG[route]
    return {
        "code": code,
        "severity": severity,
        "evidence": evidence,
        "fix_owner_skill": route_def["owner_skill"],
        "fix_stage": route_def["stage"],
        "target_artifacts": route_def["target_artifacts"],
    }


def _dedupe_issues(issues: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in issues:
        if item["code"] in seen:
            continue
        seen.add(item["code"])
        out.append(item)
    return out


def _build_fix_routes(issues: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    for issue in issues:
        key = (issue["fix_owner_skill"], issue["fix_stage"])
        entry = grouped.setdefault(
            key,
            {
                "owner_skill": issue["fix_owner_skill"],
                "stage": issue["fix_stage"],
                "reason_codes": [],
                "target_artifacts": [],
                "priority": issue["severity"],
            },
        )
        entry["reason_codes"].append(issue["code"])
        entry["target_artifacts"].extend(issue.get("target_artifacts") or [])
        if severity_rank[issue["severity"]] < severity_rank[entry["priority"]]:
            entry["priority"] = issue["severity"]
    routes = []
    for entry in grouped.values():
        entry["reason_codes"] = sorted(set(entry["reason_codes"]))
        entry["target_artifacts"] = sorted(set(entry["target_artifacts"]))
        routes.append(entry)
    return sorted(routes, key=lambda x: (severity_rank[x["priority"]], x["stage"], x["owner_skill"]))


def evaluate(
    report: str,
    appendix: dict[str, Any],
    bridge: dict[str, Any],
    valuation: dict[str, Any],
    rubric: dict[str, Any],
    density_targets: dict[str, Any] | None = None,
    benchmark_rubric: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score a report from zero and return deterministic quality/backflow data."""

    del density_targets, benchmark_rubric  # Loaded by the CLI and hashed; v0.2 rules are normalized in config.
    truthfulness_blockers: list[dict[str, Any]] = []
    candidate_blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    def truth_block(code: str, evidence: str, route: str = "quality") -> None:
        truthfulness_blockers.append(_issue(code, evidence, route, severity="high"))

    for code, pattern in (rubric.get("forbidden_main_body_patterns") or {}).items():
        match = re.search(pattern, report, flags=re.I)
        if not match:
            continue
        mapping = {
            "raw_internal_id": "raw_internal_evidence_id_in_main_report",
            "internal_path": "raw_registry_or_workflow_path_in_main_report",
            "machine_label": "readiness_or_visible_gap_token_in_main_report",
            "raw_gap_token": "raw_todo_missing_or_unreviewed_token_in_main_report",
            "direct_advice": "direct_buy_sell_hold_or_position_instruction",
            "fabricated_review": "fabricated_human_review_acceptance",
        }
        truth_block(mapping[code], match.group(0)[:120])
    if re.search(r"\b(?:SAMPLE_FACT|sample_evidence)\b|样例事实", report, re.I):
        truth_block("sample_fact_used_as_evidence", "sample marker found in main report")
    if re.search(r"(?<![0-9])\d{7,}\.\d+", report):
        truth_block("unrounded_raw_cny_dump", "raw large decimal found")

    sections, missing_sections, duplicated_sections = _extract_sections(report)
    if missing_sections:
        truth_block("missing_mandatory_section", ",".join(missing_sections), route="narrative")
    if duplicated_sections:
        truth_block("duplicate_machine_readiness_sections", ",".join(duplicated_sections), route="narrative")
    if re.search(r"(?:必然|一定|毫无疑问)(?:造成|导致|带来)", report) and not re.search(r"(?:推断|假设|限制|不确定)", report):
        truth_block("unsupported_causal_language", "absolute causal language without qualification")

    used_refs = set(re.findall(r"\[(E[1-9][0-9]*)\]", report))
    appendix_refs = [x.get("display_reference_id") for x in appendix.get("records", []) or []]
    unresolved = sorted(ref for ref in used_refs if appendix_refs.count(ref) != 1)
    duplicate_appendix_refs = sorted({ref for ref in appendix_refs if appendix_refs.count(ref) > 1})
    if unresolved:
        truth_block("unresolved_traceability_reference", ",".join(unresolved))
    if duplicate_appendix_refs:
        truth_block("unresolved_traceability_reference", "duplicate:" + ",".join(duplicate_appendix_refs))
    if not used_refs:
        truth_block("unsupported_material_fact", "no display citations in main report")

    section_diag = _section_diagnostics(sections, rubric)
    source_diag = _source_diagnostics(appendix)
    forecast = _forecast_capabilities(bridge, sections.get("forecast_and_scenarios", ""))
    valuation_caps = _valuation_capabilities(valuation, sections.get("valuation_and_market_expectations", ""))
    market = _market_capabilities(sections, valuation)

    if not forecast["has_base_case_2026E_2028E"] or not forecast["has_driver_assumptions"] or not forecast["has_three_scenarios"]:
        truth_block("forecast_without_driver_bridge", "missing bridge, drivers or scenarios", route="forecast")
    if not forecast["arithmetic_reconciles"]:
        truth_block("forecast_arithmetic_mismatch", "forecast reconciliation exceeds tolerance", route="forecast")
    if not valuation_caps["dated_snapshot"] or not valuation_caps["denominator_control"]:
        truth_block("valuation_without_date_or_denominator_control", "dated snapshot or denominator control absent", route="valuation")

    candidate_cfg = rubric.get("candidate_requirements") or {}
    total_han = _han_count(report)
    analysis_unit_sections = [key for key in CORE_ANALYSIS_SECTIONS if section_diag.get(key, {}).get("analysis_unit_pass")]

    if total_han < int(candidate_cfg.get("extremely_thin_han_chars", 900)):
        candidate_blockers.append(_issue("extremely_thin_report", f"han_chars={total_han}", "narrative", severity="high"))
    min_han = int(candidate_cfg.get("min_total_han_chars", 3200))
    if total_han < min_han:
        candidate_blockers.append(_issue("reader_report_below_research_density_floor", f"han_chars={total_han}; required={min_han}", "narrative"))
    min_units = int(candidate_cfg.get("min_complete_analysis_sections", 7))
    if len(analysis_unit_sections) < min_units:
        candidate_blockers.append(
            _issue(
                "insufficient_analytical_unit_coverage",
                f"complete={len(analysis_unit_sections)}; required={min_units}; complete_sections={','.join(analysis_unit_sections)}",
                "analysis",
            )
        )
    min_independent = int(candidate_cfg.get("min_independent_underlying_sources", 2))
    if source_diag["independent_source_count"] < min_independent:
        candidate_blockers.append(
            _issue(
                "independent_research_evidence_below_minimum",
                f"independent_sources={source_diag['independent_source_count']}; required={min_independent}",
                "evidence",
            )
        )
    if source_diag["category_counts"].get("industry", 0) == 0:
        candidate_blockers.append(_issue("independent_industry_evidence_missing", "no independent industry underlying source", "industry"))
    if source_diag["category_counts"].get("peer", 0) == 0 and valuation_caps["credible_peer_count"] < 3:
        candidate_blockers.append(_issue("peer_operating_evidence_missing", "no peer evidence source and fewer than three credible peers", "evidence"))
    if not forecast["segment_driven"]:
        candidate_blockers.append(_issue("forecast_not_bottom_up_or_segment_driven", "forecast drivers remain company-total/mechanical", "forecast"))
    if not forecast["disaggregated_cost_tax_minority_bridge"] or forecast["uses_aggregate_residual_bridge"]:
        candidate_blockers.append(_issue("forecast_bridge_uses_aggregate_residual", "tax/finance/other/minority are not separately modeled", "forecast"))
    if not valuation_caps["reverse_valuation"] and not valuation_caps["scenario_value_ranges"]:
        candidate_blockers.append(_issue("valuation_lacks_reverse_or_scenario_value_range", "no reverse valuation or bull/base/bear value range", "valuation"))
    if valuation_caps["credible_peer_count"] < int(candidate_cfg.get("min_credible_peers", 3)):
        candidate_blockers.append(_issue("credible_peer_context_below_minimum", f"credible_peers={valuation_caps['credible_peer_count']}", "valuation"))
    if not market["technical"]:
        candidate_blockers.append(_issue("technical_analysis_inputs_missing", "no reviewed technical-series analysis in reader report", "market"))
    if not market["sentiment"]:
        candidate_blockers.append(_issue("sentiment_analysis_inputs_missing", "no macro/industry/company sentiment layers", "market"))
    if not all(
        [
            market["future_dated_event"],
            market["event_impact_path"],
            market["event_verification_metric"],
            market["event_counterevidence_condition"],
        ]
    ):
        candidate_blockers.append(
            _issue(
                "catalyst_event_chain_incomplete",
                "future date, impact path, verification metric and counterevidence condition are not all present",
                "market",
            )
        )

    truthfulness_blockers = _dedupe_issues(truthfulness_blockers)
    candidate_blockers = _dedupe_issues(candidate_blockers)

    max_scores = rubric["dimensions"]
    dimension_scores: dict[str, int] = {}

    # Evidence integrity (20): correctness, section coverage, source diversity and metadata discipline.
    evidence_score = 0.0
    if used_refs and not unresolved and not duplicate_appendix_refs:
        evidence_score += 5
    cite_sections = [key for key, diag in section_diag.items() if diag["unique_references"]]
    evidence_score += 4 * len(cite_sections) / max(1, len(SECTION_HEADINGS))
    evidence_score += 3 * min(source_diag["underlying_source_count"], 5) / 5
    evidence_score += 5 * min(source_diag["independent_source_count"], 4) / 4
    evidence_score += 3 * source_diag["metadata_complete_ratio"]
    dimension_scores["evidence_integrity"] = _clamp(evidence_score, max_scores["evidence_integrity"])

    # Coverage completeness (15): headings are not enough; core benchmark capabilities must be present.
    coverage_score = 5 * (len(SECTION_HEADINGS) - len(missing_sections)) / len(SECTION_HEADINGS)
    density_passes = sum(1 for diag in section_diag.values() if diag["density_pass"])
    coverage_score += 4 * density_passes / len(SECTION_HEADINGS)
    benchmark_caps = [
        section_diag["financial_history_and_cashflow_quality"]["analysis_unit_pass"],
        section_diag["business_breakdown_and_economics"]["analysis_unit_pass"],
        section_diag["industry_structure_and_competition"]["analysis_unit_pass"] and source_diag["category_counts"].get("industry", 0) > 0,
        forecast["segment_driven"],
        valuation_caps["reverse_valuation"] or valuation_caps["scenario_value_ranges"],
        market["technical"],
        market["sentiment"],
        market["future_dated_event"] and market["event_impact_path"],
        section_diag["research_conclusion"]["analysis_unit_pass"],
    ]
    coverage_score += 6 * sum(bool(x) for x in benchmark_caps) / len(benchmark_caps)
    dimension_scores["coverage_completeness"] = _clamp(coverage_score, max_scores["coverage_completeness"])

    # Analytical synthesis (20): positive credit only for complete fact-to-watchpoint units.
    analytical_score = 12 * len(analysis_unit_sections) / len(CORE_ANALYSIS_SECTIONS)
    thesis_text = sections.get("executive_summary", "") + "\n" + sections.get("research_conclusion", "")
    thesis_signals = _signals(thesis_text)
    if thesis_signals["judgment"] and thesis_signals["counterevidence"]:
        analytical_score += 2
    if thesis_signals["economic_impact"] and thesis_signals["watchpoint"]:
        analytical_score += 2
    counter_sections = sum(1 for diag in section_diag.values() if diag["signals"]["counterevidence"])
    watch_sections = sum(1 for diag in section_diag.values() if diag["signals"]["watchpoint"])
    analytical_score += 2 * min(counter_sections, 6) / 6
    analytical_score += 2 * min(watch_sections, 6) / 6
    dimension_scores["analytical_synthesis"] = _clamp(analytical_score, max_scores["analytical_synthesis"])

    # Forecast and valuation (15): arithmetic is necessary but not sufficient.
    fv_score = 0.0
    fv_score += 2 if forecast["arithmetic_reconciles"] else 0
    fv_score += 1 if forecast["has_three_scenarios"] else 0
    fv_score += 1 if forecast["has_driver_assumptions"] else 0
    fv_score += 2 if forecast["segment_driven"] else 0
    fv_score += 1 if forecast["disaggregated_cost_tax_minority_bridge"] and not forecast["uses_aggregate_residual_bridge"] else 0
    fv_score += 1 if forecast["consensus_comparison"] else 0
    fv_score += 1 if valuation_caps["dated_snapshot"] and valuation_caps["denominator_control"] else 0
    fv_score += 1 if valuation_caps["credible_peer_count"] >= 3 else 0
    fv_score += 2 if valuation_caps["reverse_valuation"] else 0
    fv_score += 1 if valuation_caps["scenario_value_ranges"] else 0
    fv_score += 1 if valuation_caps["method_explanation"] else 0
    fv_score += 1 if valuation_caps["report_has_peer_context"] else 0
    dimension_scores["forecast_and_valuation"] = _clamp(fv_score, max_scores["forecast_and_valuation"])

    # Narrative and readability (15): structure is necessary, but analytical
    # continuity and section density carry more weight than headings alone.
    narrative_score = 0.0
    narrative_score += 3 * (len(SECTION_HEADINGS) - len(missing_sections)) / len(SECTION_HEADINGS)
    narrative_score += 3 * min(total_han / max(1, min_han), 1.0)
    narrative_score += 4 * density_passes / len(SECTION_HEADINGS)
    paragraph_count = len([x for x in re.split(r"\n\s*\n", report) if x.strip()])
    narrative_score += 1.5 if paragraph_count >= 18 else 1.5 * paragraph_count / 18
    narrative_score += 2.5 * len(analysis_unit_sections) / len(CORE_ANALYSIS_SECTIONS)
    repeated_judgments = Counter(
        re.sub(r"\s+", "", re.sub(r"\[(?:E\d+)\]", "", paragraph))[:80]
        for paragraph in re.split(r"\n\s*\n", report)
        if _han_count(paragraph) >= 35
    )
    narrative_score += 1 if not any(count > 1 for count in repeated_judgments.values()) else 0
    dimension_scores["narrative_and_readability"] = _clamp(narrative_score, max_scores["narrative_and_readability"])

    hygiene_codes = {
        "raw_internal_evidence_id_in_main_report",
        "raw_registry_or_workflow_path_in_main_report",
        "readiness_or_visible_gap_token_in_main_report",
        "raw_todo_missing_or_unreviewed_token_in_main_report",
        "unrounded_raw_cny_dump",
        "direct_buy_sell_hold_or_position_instruction",
        "fabricated_human_review_acceptance",
        "sample_fact_used_as_evidence",
    }
    hygiene_hits = sum(1 for item in truthfulness_blockers if item["code"] in hygiene_codes)
    dimension_scores["presentation_hygiene"] = max(0, max_scores["presentation_hygiene"] - 2 * hygiene_hits)

    risk_diag = section_diag["risks_counterevidence_and_watchpoints"]
    conclusion_diag = section_diag["research_conclusion"]
    risk_score = 0.0
    risk_score += 1 if risk_diag["signals"]["counterevidence"] else 0
    risk_score += 1 if risk_diag["signals"]["watchpoint"] else 0
    risk_score += 1 if risk_diag["numeric_fact_count"] >= 2 or len(re.findall(r"^\s*[-*]", sections.get("risks_counterevidence_and_watchpoints", ""), re.M)) >= 3 else 0
    risk_score += 1 if conclusion_diag["signals"]["watchpoint"] else 0
    risk_score += 1 if re.search(r"(?:失效|证伪|不成立|偏离|触发降级|撤销判断)", sections.get("research_conclusion", "")) else 0
    dimension_scores["risks_and_watch_conditions"] = _clamp(risk_score, max_scores["risks_and_watch_conditions"])

    score = sum(dimension_scores.values())
    candidate_threshold = int(rubric["candidate_threshold"])
    research_draft_threshold = int(rubric.get("research_draft_threshold", 45))
    all_blockers = truthfulness_blockers + candidate_blockers
    if truthfulness_blockers:
        quality_band = "blocked"
    elif score >= candidate_threshold and not candidate_blockers:
        quality_band = "candidate_ready_for_human_review"
    elif score >= research_draft_threshold:
        quality_band = "research_draft"
    else:
        quality_band = "source_gapped_draft"
    decision = "candidate_ready_for_human_review" if quality_band == "candidate_ready_for_human_review" else "rejected"

    if score < candidate_threshold and not all_blockers:
        warnings.append(_issue("score_below_candidate_threshold", f"score={score}; threshold={candidate_threshold}", "quality", severity="low"))

    fix_routes = _build_fix_routes(candidate_blockers + truthfulness_blockers + warnings)
    leakage_codes = {
        "raw_internal_evidence_id_in_main_report",
        "raw_registry_or_workflow_path_in_main_report",
        "readiness_or_visible_gap_token_in_main_report",
        "raw_todo_missing_or_unreviewed_token_in_main_report",
    }
    numeric_violations = sum(1 for x in truthfulness_blockers if x["code"] == "unrounded_raw_cny_dump")
    return {
        "artifact_type": "R5_reader_quality_scorecard",
        "schema_version": "v0.2",
        "rubric_id": rubric.get("rubric_id"),
        "scoring_method": "positive_from_zero",
        "decision": decision,
        "quality_band": quality_band,
        "score": score,
        "threshold": candidate_threshold,
        "research_draft_threshold": research_draft_threshold,
        "critical_blocker_count": len(all_blockers),
        "critical_blockers": all_blockers,
        "truthfulness_blockers": truthfulness_blockers,
        "candidate_blockers": candidate_blockers,
        "warnings": warnings,
        "dimension_scores": dimension_scores,
        "dimension_max_scores": max_scores,
        "required_section_coverage": {
            "covered": len(SECTION_HEADINGS) - len(missing_sections),
            "required": len(SECTION_HEADINGS),
            "missing": missing_sections,
            "duplicated": duplicated_sections,
        },
        "section_diagnostics": section_diag,
        "analysis_unit_coverage": {
            "complete": len(analysis_unit_sections),
            "required_for_candidate": min_units,
            "complete_sections": analysis_unit_sections,
        },
        "source_diagnostics": source_diag,
        "forecast_capabilities": forecast,
        "valuation_capabilities": valuation_caps,
        "market_event_capabilities": market,
        "fix_routes": fix_routes,
        "display_citations": {
            "used": sorted(used_refs),
            "appendix_records": len(appendix_refs),
            "unresolved": unresolved,
            "duplicate_appendix_references": duplicate_appendix_refs,
        },
        "unresolved_citation_count": len(unresolved) + len(duplicate_appendix_refs),
        "machine_token_leakage_count": sum(1 for x in truthfulness_blockers if x["code"] in leakage_codes),
        "numeric_format_violation_count": numeric_violations,
        "conclusion_state": quality_band,
        "truthfulness_status": "fail" if truthfulness_blockers else "pass",
        "human_review_required": True,
        "human_review_status": "pending" if decision == "candidate_ready_for_human_review" else "not_ready",
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--workflow-run", default="reports/workflow_runs/wf_20260703_stock_first_002837_invic")
    parser.add_argument("--report")
    parser.add_argument("--appendix")
    parser.add_argument("--bridge")
    parser.add_argument("--valuation")
    parser.add_argument("--rubric")
    parser.add_argument("--density-targets")
    parser.add_argument("--benchmark-rubric")
    parser.add_argument("--output")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    run = Path(args.workflow_run)
    if not run.is_absolute():
        run = root / run
    report_path = Path(args.report) if args.report else run / "R5_stock_research_report_reader_v2.md"
    appendix_path = Path(args.appendix) if args.appendix else run / "R5_stock_research_report_traceability_v2.yaml"
    bridge_path = Path(args.bridge) if args.bridge else run / "R5_bundle6_forecast_bridge.yaml"
    valuation_path = Path(args.valuation) if args.valuation else run / "R5_bundle6_valuation_reasoning_pack.yaml"
    rubric_path = Path(args.rubric) if args.rubric else root / "config/r5_reader_quality_rubric.yaml"
    density_path = Path(args.density_targets) if args.density_targets else root / "benchmarks/r5_section_density_targets.yaml"
    benchmark_path = Path(args.benchmark_rubric) if args.benchmark_rubric else root / "benchmarks/r5_report_quality_rubric.yaml"
    output_path = Path(args.output) if args.output else run / "R5_stock_research_report_reader_v2_quality_scorecard.yaml"

    report = report_path.read_text(encoding="utf-8")
    scorecard = evaluate(
        report,
        load_yaml(appendix_path),
        load_yaml(bridge_path),
        load_yaml(valuation_path),
        load_yaml(rubric_path),
        load_yaml(density_path) if density_path.exists() else {},
        load_yaml(benchmark_path) if benchmark_path.exists() else {},
    )
    hash_paths = {
        "report_sha256": report_path,
        "appendix_sha256": appendix_path,
        "forecast_bridge_sha256": bridge_path,
        "valuation_reasoning_sha256": valuation_path,
        "live_rubric_sha256": rubric_path,
        "density_targets_sha256": density_path,
        "benchmark_rubric_sha256": benchmark_path,
    }
    scorecard["input_hashes"] = {
        key: hashlib.sha256(path.read_bytes()).hexdigest()
        for key, path in hash_paths.items()
        if path.exists()
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(scorecard, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(
        "reader_quality_gate "
        f"decision={scorecard['decision']} quality_band={scorecard['quality_band']} "
        f"score={scorecard['score']} blockers={scorecard['critical_blocker_count']} "
        f"truthfulness={scorecard['truthfulness_status']} human_review={scorecard['human_review_status']} "
        "sample_quality=false p2=false"
    )
    return 0 if scorecard["decision"] == "candidate_ready_for_human_review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
