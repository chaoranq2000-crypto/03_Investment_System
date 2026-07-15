from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


INPUT_SCHEMA = "r5_bundle16r_case_input_v1"
OUTPUT_SCHEMA = "r5_bundle16r_real_company_regression_v1"
TRUTHFULNESS_FLAGS = (
    "sample_text_used_as_evidence",
    "management_guidance_recast_as_fact",
    "low_confidence_peer_ranked",
    "direct_trading_instruction_present",
    "past_event_presented_as_future",
    "undisclosed_segment_economics_presented_as_fact",
    "consensus_estimate_presented_as_issuer_fact",
)


class CaseInputError(ValueError):
    pass


def load_mapping(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CaseInputError(f"mapping required: {path}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(dict(payload), allow_unicode=True, sort_keys=True),
        encoding="utf-8",
    )


def _repo_path(repo_root: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    candidate = candidate if candidate.is_absolute() else repo_root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise CaseInputError(f"path escapes repository: {raw_path}") from exc
    return resolved


def _repo_rel(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _float(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise CaseInputError(f"{field} must be numeric") from exc
    if result != result or result in {float("inf"), float("-inf")}:
        raise CaseInputError(f"{field} must be finite")
    return result


def _strings(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _registry_case(registry: Mapping[str, Any], case_id: str) -> Mapping[str, Any]:
    for raw in registry.get("cases", []):
        if isinstance(raw, Mapping) and raw.get("case_id") == case_id:
            return raw
    raise CaseInputError(f"case_id not found in registry: {case_id}")


def _source_integrity(repo_root: Path, sources: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not sources:
        raise CaseInputError("at least one reviewed official source is required")
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, source in enumerate(sources):
        evidence_id = str(source.get("evidence_id", "")).strip()
        if not evidence_id or evidence_id in seen:
            raise CaseInputError(f"sources[{index}].evidence_id missing or duplicated")
        seen.add(evidence_id)
        source_path = _repo_path(repo_root, str(source.get("source_path", "")))
        processed_path = _repo_path(repo_root, str(source.get("processed_text_path", "")))
        if not source_path.is_file() or not processed_path.is_file():
            raise CaseInputError(f"source or processed text missing for {evidence_id}")
        actual_hash = sha256_file(source_path)
        expected_hash = str(source.get("file_hash", "")).lower()
        if actual_hash != expected_hash:
            raise CaseInputError(f"source hash mismatch for {evidence_id}")
        if source.get("review_status") != "reviewed":
            raise CaseInputError(f"source is not reviewed: {evidence_id}")
        results.append(
            {
                "evidence_id": evidence_id,
                "source_path": _repo_rel(repo_root, source_path),
                "processed_text_path": _repo_rel(repo_root, processed_path),
                "sha256": actual_hash,
                "page_count": int(source.get("page_count", 0)),
                "review_status": "reviewed",
            }
        )
    return results


def _driver_is_bound(segment: Mapping[str, Any]) -> bool:
    contract = segment.get("driver_contract")
    if not isinstance(contract, Mapping):
        return False
    topics = _strings(contract.get("driver_topics"))
    evidence_ids = _strings(contract.get("source_evidence_ids"))
    estimate_logic = str(contract.get("estimate_logic", "")).strip()
    return bool(
        str(contract.get("archetype_id", "")).strip()
        and str(contract.get("equation", "")).strip()
        and topics
        and (evidence_ids or estimate_logic)
    )


def build_operating_driver_pack(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, float]]:
    historical = payload.get("historical")
    if not isinstance(historical, Mapping):
        raise CaseInputError("historical mapping required")
    total_revenue = _float(historical.get("total_revenue"), "historical.total_revenue")
    total_gross_profit = _float(historical.get("total_gross_profit"), "historical.total_gross_profit")
    raw_segments = historical.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise CaseInputError("historical.segments must be a non-empty list")

    segments: list[dict[str, Any]] = []
    material_count = 0
    bound_material_count = 0
    explained_revenue = 0.0
    explained_gross_profit = 0.0
    seen: set[str] = set()
    for index, raw in enumerate(raw_segments):
        if not isinstance(raw, Mapping):
            raise CaseInputError(f"historical.segments[{index}] must be a mapping")
        segment_id = str(raw.get("segment_id", "")).strip()
        if not segment_id or segment_id in seen:
            raise CaseInputError(f"segment_id missing or duplicated: {segment_id}")
        seen.add(segment_id)
        revenue = _float(raw.get("revenue"), f"{segment_id}.revenue")
        cost = _float(raw.get("cost"), f"{segment_id}.cost")
        gross_profit = revenue - cost
        if raw.get("gross_profit") is not None:
            declared = _float(raw.get("gross_profit"), f"{segment_id}.gross_profit")
            if abs(declared - gross_profit) > max(1.0, abs(revenue) * 1e-8):
                raise CaseInputError(f"gross-profit bridge mismatch: {segment_id}")
        material = raw.get("material") is True
        bound = _driver_is_bound(raw)
        if material:
            material_count += 1
            bound_material_count += int(bound)
        if bound:
            explained_revenue += revenue
            explained_gross_profit += gross_profit
        segments.append(
            {
                "segment_id": segment_id,
                "display_name": str(raw.get("display_name", segment_id)),
                "material": material,
                "revenue": round(revenue, 6),
                "cost": round(cost, 6),
                "gross_profit": round(gross_profit, 6),
                "gross_margin": round(gross_profit / revenue, 8) if revenue else None,
                "disclosure_boundary": str(raw.get("disclosure_boundary", "")),
                "driver_bound": bound,
                "driver_contract": dict(raw.get("driver_contract", {})) if isinstance(raw.get("driver_contract"), Mapping) else {},
            }
        )

    segment_revenue = sum(float(row["revenue"]) for row in segments)
    segment_gross_profit = sum(float(row["gross_profit"]) for row in segments)
    revenue_tolerance = max(0.01, abs(total_revenue) * 1e-10)
    gp_tolerance = max(0.01, abs(total_gross_profit) * 1e-10)
    if abs(segment_revenue - total_revenue) > revenue_tolerance:
        raise CaseInputError("historical segment revenue does not reconcile to total revenue")
    if abs(segment_gross_profit - total_gross_profit) > gp_tolerance:
        raise CaseInputError("historical segment gross profit does not reconcile to total gross profit")
    if material_count == 0:
        raise CaseInputError("at least one material segment is required")

    def ratio(numerator: float, denominator: float) -> float:
        if denominator == 0:
            return 1.0 if abs(numerator) <= 1e-9 else 0.0
        return max(0.0, min(1.0, numerator / denominator))

    metrics = {
        "material_segment_driver_coverage": round(bound_material_count / material_count, 8),
        "revenue_explained_ratio": round(ratio(explained_revenue, total_revenue), 8),
        "gross_profit_explained_ratio": round(ratio(explained_gross_profit, total_gross_profit), 8),
    }
    metrics["residual_revenue_ratio"] = round(1.0 - metrics["revenue_explained_ratio"], 8)
    metrics["residual_gross_profit_ratio"] = round(1.0 - metrics["gross_profit_explained_ratio"], 8)
    pack = {
        "schema_version": 1,
        "artifact_type": "r5_bundle16r_operating_driver_pack",
        "period": str(historical.get("period", "")),
        "unit": str(historical.get("unit", "CNY")),
        "total_revenue": round(total_revenue, 6),
        "total_gross_profit": round(total_gross_profit, 6),
        "segments": segments,
        "reconciliation": {
            "segment_revenue_sum": round(segment_revenue, 6),
            "segment_gross_profit_sum": round(segment_gross_profit, 6),
            "revenue_difference": round(total_revenue - segment_revenue, 6),
            "gross_profit_difference": round(total_gross_profit - segment_gross_profit, 6),
        },
        "coverage_metrics": metrics,
        "decision": "pass" if metrics["material_segment_driver_coverage"] == 1.0 else "needs_backflow",
    }
    return pack, metrics


def _assumption_traced(raw: Mapping[str, Any]) -> bool:
    evidence_ids = _strings(raw.get("evidence_ids"))
    locator = str(raw.get("locator", "")).strip()
    estimate_logic = str(raw.get("estimate_logic", "")).strip()
    return bool((evidence_ids and locator) or estimate_logic)


def build_forecast_model(payload: Mapping[str, Any]) -> tuple[dict[str, Any], float, int]:
    forecast = payload.get("forecast")
    if not isinstance(forecast, Mapping):
        raise CaseInputError("forecast mapping required")
    periods = _strings(forecast.get("periods"))
    scenarios = _strings(forecast.get("scenarios"))
    if not periods or not scenarios:
        raise CaseInputError("forecast periods and scenarios are required")
    assumptions = forecast.get("assumptions")
    if not isinstance(assumptions, list) or not assumptions:
        raise CaseInputError("forecast assumptions are required")
    traced = sum(1 for raw in assumptions if isinstance(raw, Mapping) and _assumption_traced(raw))
    traceability = round(traced / len(assumptions), 8)

    raw_segments = forecast.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise CaseInputError("forecast segments are required")
    scenario_rows: dict[str, Any] = {}
    for scenario in scenarios:
        segment_rows: list[dict[str, Any]] = []
        totals = {period: {"revenue": 0.0, "gross_profit": 0.0} for period in periods}
        for raw in raw_segments:
            if not isinstance(raw, Mapping):
                raise CaseInputError("forecast segment must be a mapping")
            segment_id = str(raw.get("segment_id", "")).strip()
            previous_revenue = _float(raw.get("base_revenue"), f"forecast.{segment_id}.base_revenue")
            explicit = raw.get("revenue_values")
            growth = raw.get("growth_rates")
            margins = raw.get("gross_margins")
            if not isinstance(margins, Mapping) or not isinstance(margins.get(scenario), list):
                raise CaseInputError(f"gross margins missing for {segment_id}/{scenario}")
            margin_values = margins[scenario]
            if len(margin_values) != len(periods):
                raise CaseInputError(f"gross margin length mismatch for {segment_id}/{scenario}")
            if isinstance(explicit, Mapping) and isinstance(explicit.get(scenario), list):
                revenue_values = explicit[scenario]
                if len(revenue_values) != len(periods):
                    raise CaseInputError(f"revenue value length mismatch for {segment_id}/{scenario}")
            elif isinstance(growth, Mapping) and isinstance(growth.get(scenario), list):
                growth_values = growth[scenario]
                if len(growth_values) != len(periods):
                    raise CaseInputError(f"growth length mismatch for {segment_id}/{scenario}")
                revenue_values = []
                for raw_growth in growth_values:
                    previous_revenue *= 1.0 + _float(raw_growth, f"growth.{segment_id}.{scenario}")
                    revenue_values.append(previous_revenue)
            else:
                raise CaseInputError(f"revenue values or growth rates missing for {segment_id}/{scenario}")

            projections: list[dict[str, Any]] = []
            for period, raw_revenue, raw_margin in zip(periods, revenue_values, margin_values):
                revenue = _float(raw_revenue, f"revenue.{segment_id}.{scenario}.{period}")
                margin = _float(raw_margin, f"margin.{segment_id}.{scenario}.{period}")
                gross_profit = revenue * margin
                projections.append(
                    {
                        "period": period,
                        "revenue": round(revenue, 6),
                        "gross_margin": round(margin, 8),
                        "gross_profit": round(gross_profit, 6),
                    }
                )
                totals[period]["revenue"] += revenue
                totals[period]["gross_profit"] += gross_profit
            segment_rows.append({"segment_id": segment_id, "projections": projections})
        scenario_rows[scenario] = {
            "segments": segment_rows,
            "consolidated": [
                {
                    "period": period,
                    "revenue": round(totals[period]["revenue"], 6),
                    "gross_profit": round(totals[period]["gross_profit"], 6),
                    "gross_margin": round(totals[period]["gross_profit"] / totals[period]["revenue"], 8)
                    if totals[period]["revenue"]
                    else None,
                }
                for period in periods
            ],
        }

    events = forecast.get("future_events")
    if not isinstance(events, list):
        raise CaseInputError("forecast.future_events must be a list")
    linked_events = sum(
        1
        for event in events
        if isinstance(event, Mapping)
        and str(event.get("event_id", "")).strip()
        and _strings(event.get("model_links"))
        and str(event.get("verification_metric", "")).strip()
    )
    model = {
        "schema_version": 1,
        "artifact_type": "r5_bundle16r_forecast_model",
        "periods": periods,
        "scenarios": scenario_rows,
        "assumptions": assumptions,
        "assumption_traceability": traceability,
        "future_events": events,
        "future_event_model_link_count": linked_events,
        "forecast_classification": "estimate",
        "management_guidance_is_not_fact": True,
    }
    return model, traceability, linked_events


def _reference_index(payload: Mapping[str, Any], operating: Mapping[str, Any], forecast: Mapping[str, Any]) -> set[str]:
    refs = {str(row.get("evidence_id")) for row in payload.get("sources", []) if isinstance(row, Mapping)}
    refs.update(str(row.get("metric_id")) for row in payload.get("company_metrics", []) if isinstance(row, Mapping))
    refs.update(str(row.get("claim_id")) for row in payload.get("claims", []) if isinstance(row, Mapping))
    refs.update(str(row.get("segment_id")) for row in operating.get("segments", []) if isinstance(row, Mapping))
    refs.update(str(row.get("assumption_id")) for row in forecast.get("assumptions", []) if isinstance(row, Mapping))
    refs.update(str(row.get("event_id")) for row in forecast.get("future_events", []) if isinstance(row, Mapping))
    return {ref for ref in refs if ref and ref != "None"}


def _sentence_novelty(sections: Sequence[Mapping[str, Any]]) -> float:
    sentences: list[str] = []
    for section in sections:
        texts = [str(section.get("judgment", ""))]
        for paragraph in section.get("paragraphs", []):
            if isinstance(paragraph, Mapping):
                texts.append(str(paragraph.get("text", "")))
        for text in texts:
            for raw in re.split(r"[。！？!?；;]+", text):
                normalized = re.sub(r"\s+", "", raw).strip()
                if len(normalized) >= 8:
                    sentences.append(normalized)
    if not sentences:
        return 0.0
    return round(len(set(sentences)) / len(sentences), 8)


def render_reader(payload: Mapping[str, Any], reference_index: set[str]) -> tuple[str, float, float, float]:
    reader = payload.get("reader")
    if not isinstance(reader, Mapping) or not isinstance(reader.get("sections"), list):
        raise CaseInputError("reader.sections must be a list")
    sections = reader["sections"]
    lines = [
        f"# {payload['issuer_name']}（{payload['ticker']}）真实公司回归研究稿",
        "",
        f"- information_cutoff: `{payload['as_of_date']}`",
        f"- workflow_id: `{payload['workflow_id']}`",
        "- status: `engineering_candidate / human_review_pending`",
        "- boundary: 本稿为证据约束的研究候选，不构成买入、卖出、持有或仓位建议。",
        "",
    ]
    total_refs = 0
    resolved_refs = 0
    model_linked = 0
    for section in sections:
        if not isinstance(section, Mapping):
            raise CaseInputError("reader section must be a mapping")
        title = str(section.get("title", section.get("section_id", ""))).strip()
        if not title:
            raise CaseInputError("reader section title missing")
        links = _strings(section.get("model_links"))
        section_refs: list[str] = []
        lines.extend([f"## {title}", "", str(section.get("judgment", "")).strip(), ""])
        for paragraph in section.get("paragraphs", []):
            if not isinstance(paragraph, Mapping):
                continue
            refs = _strings(paragraph.get("refs"))
            section_refs.extend(refs)
            total_refs += len(refs)
            resolved_refs += sum(ref in reference_index for ref in refs)
            suffix = " ".join(f"〔{ref}〕" for ref in refs)
            text = str(paragraph.get("text", "")).strip()
            lines.extend([f"{text} {suffix}".rstrip(), ""])
        if links or section_refs:
            model_linked += 1
        if links:
            lines.extend(["模型链接：" + "、".join(f"`{link}`" for link in links), ""])
    section_count = len(sections)
    citation_rate = round(resolved_refs / total_refs, 8) if total_refs else 0.0
    link_ratio = round(model_linked / section_count, 8) if section_count else 0.0
    novelty = _sentence_novelty([section for section in sections if isinstance(section, Mapping)])
    lines.extend(
        [
            "## 边界与复核状态",
            "",
            "所有事实、管理层表述与估计均按来源类型区分；未披露分部经济性保持为 MISSING_DISCLOSURE。",
            "外部人工复核尚未签署，因此 sample_quality_allowed=false，p2_allowed=false。",
            "",
        ]
    )
    return "\n".join(lines), citation_rate, link_ratio, novelty


def _company_metric_count(rows: Any) -> int:
    if not isinstance(rows, list):
        return 0
    required = ("metric_id", "name", "value", "unit", "period", "evidence_id", "locator")
    return sum(1 for row in rows if isinstance(row, Mapping) and all(row.get(key) not in (None, "") for key in required))


def _unresolved_critical_questions(rows: Any) -> int:
    if not isinstance(rows, list):
        return 0
    return sum(
        1
        for row in rows
        if isinstance(row, Mapping)
        and row.get("severity") == "critical"
        and row.get("status") not in {"resolved", "closed", "not_applicable"}
    )


def _metric_gate_issues(metrics: Mapping[str, Any], thresholds: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
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
    for metric, threshold in min_pairs:
        if float(metrics[metric]) < float(thresholds[threshold]):
            issues.append({"code": "METRIC_BELOW_MINIMUM", "metric": metric})
    for metric, threshold in max_pairs:
        if float(metrics[metric]) > float(thresholds[threshold]):
            issues.append({"code": "METRIC_ABOVE_MAXIMUM", "metric": metric})
    if int(metrics["company_specific_metric_count"]) < int(thresholds["company_specific_metric_count_min"]):
        issues.append({"code": "COMPANY_METRIC_COUNT_LOW", "metric": "company_specific_metric_count"})
    if int(metrics["future_event_model_link_count"]) < int(thresholds["future_event_model_link_count_min"]):
        issues.append({"code": "FUTURE_EVENT_LINK_COUNT_LOW", "metric": "future_event_model_link_count"})
    if int(metrics["unresolved_critical_question_count"]) != 0:
        issues.append({"code": "CRITICAL_QUESTION_OPEN", "metric": "unresolved_critical_question_count"})
    return issues


def route_gate_issues(issues: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    metric_routes = {
        "material_segment_driver_coverage": ("operating_driver_engine", "bind missing material segments to explicit economic drivers"),
        "revenue_explained_ratio": ("operating_driver_engine", "rebuild the segment revenue bridge and label residuals"),
        "gross_profit_explained_ratio": ("operating_driver_engine", "rebuild the segment gross-profit bridge and label residuals"),
        "residual_revenue_ratio": ("operating_driver_engine", "reduce or explicitly research the unexplained revenue residual"),
        "residual_gross_profit_ratio": ("operating_driver_engine", "reduce or explicitly research the unexplained gross-profit residual"),
        "forecast_assumption_traceability": ("forecast_model", "attach evidence locators or declared estimate logic to forecast assumptions"),
        "model_linked_core_section_ratio": ("report_planner_semantic_quality", "link core sections to model or evidence objects"),
        "section_novelty_ratio": ("report_planner_semantic_quality", "replace repeated generic prose with company-specific analysis"),
        "citation_resolution_rate": ("quality_review", "resolve every report citation to a physical upstream object"),
        "company_specific_metric_count": ("evidence_ingest_research_question_planner", "acquire and review additional company-specific operating metrics"),
        "future_event_model_link_count": ("forecast_model_research_question_planner", "add dated verification events linked to model assumptions"),
        "unresolved_critical_question_count": ("research_question_planner", "resolve or explicitly block on every critical research question"),
    }
    routed: list[dict[str, str]] = []
    for issue in issues:
        metric = str(issue.get("metric", ""))
        owner, action = metric_routes.get(metric, ("quality_review", "triage the failed gate and assign the owning stage"))
        routed.append(
            {
                "issue_code": str(issue.get("code", "UNKNOWN_GATE_FAILURE")),
                "metric": metric,
                "owner": owner,
                "severity": "critical",
                "next_step": action,
            }
        )
    return routed


def build_case(
    *,
    repo_root: Path,
    input_path: Path,
    registry_path: Path,
    output_dir: Path | None = None,
    case_results_dir: Path | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    payload = load_mapping(input_path)
    registry = load_mapping(registry_path)
    if payload.get("schema_version") != INPUT_SCHEMA:
        raise CaseInputError(f"input schema must be {INPUT_SCHEMA}")
    case_id = str(payload.get("case_id", ""))
    registry_case = _registry_case(registry, case_id)
    for field in ("ticker", "issuer_name"):
        if str(payload.get(field, "")) != str(registry_case.get(field, "")):
            raise CaseInputError(f"{field} does not match registry")

    workflow_id = str(payload.get("workflow_id", "")).strip()
    if not workflow_id:
        raise CaseInputError("workflow_id required")
    output_dir = output_dir or repo_root / "reports" / "workflow_runs" / workflow_id / "bundle16r" / "generated"
    case_results_dir = case_results_dir or repo_root / "bundle16r" / "generated" / "case_results"
    output_dir = _repo_path(repo_root, str(output_dir))
    case_results_dir = _repo_path(repo_root, str(case_results_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    case_results_dir.mkdir(parents=True, exist_ok=True)

    sources_raw = payload.get("sources")
    if not isinstance(sources_raw, list):
        raise CaseInputError("sources must be a list")
    source_checks = _source_integrity(repo_root, [row for row in sources_raw if isinstance(row, Mapping)])
    official_count = sum(1 for row in sources_raw if isinstance(row, Mapping) and row.get("source_class") == "official")
    evidence_pack = {
        "schema_version": 1,
        "artifact_type": "r5_bundle16r_reviewed_evidence_pack",
        "case_id": case_id,
        "as_of_date": str(payload.get("as_of_date", "")),
        "review_status": "reviewed",
        "source_count": len(sources_raw),
        "official_source_count": official_count,
        "sources": sources_raw,
        "source_integrity": source_checks,
        "company_metrics": payload.get("company_metrics", []),
        "claims": payload.get("claims", []),
        "research_questions": payload.get("research_questions", []),
        "evidence_integrity_incidents": payload.get("evidence_integrity_incidents", []),
        "sample_reports_used_as_evidence": False,
    }
    operating_pack, operating_metrics = build_operating_driver_pack(payload)
    forecast_model, forecast_traceability, future_event_links = build_forecast_model(payload)
    reference_index = _reference_index(payload, operating_pack, forecast_model)
    reader_text, citation_rate, model_link_ratio, novelty_ratio = render_reader(payload, reference_index)

    valuation_input = payload.get("valuation")
    if not isinstance(valuation_input, Mapping):
        raise CaseInputError("valuation mapping required")
    peer_multiple_used = valuation_input.get("peer_multiple_used")
    if peer_multiple_used is not False:
        raise CaseInputError("this builder requires peer multiples to be disabled unless a qualified peer adapter is added")
    qualified_peers = valuation_input.get("qualified_peers", [])
    if not isinstance(qualified_peers, list):
        raise CaseInputError("valuation.qualified_peers must be a list")
    valuation_pack = {
        "schema_version": 1,
        "artifact_type": "r5_bundle16r_valuation_pack",
        "method": str(valuation_input.get("alternative_method", "scenario_valuation")),
        "peer_multiple_used": False,
        "qualified_peers": qualified_peers,
        "scenario_operating_context": {
            scenario: rows.get("consolidated", [])
            for scenario, rows in forecast_model["scenarios"].items()
        },
        "eligibility": valuation_input.get("eligibility", {}),
        "limitations": valuation_input.get("limitations", []),
        "price_target": None,
        "rating": None,
        "position_instruction": None,
        "no_advice_boundary": True,
    }

    truthfulness = payload.get("truthfulness")
    if not isinstance(truthfulness, Mapping):
        raise CaseInputError("truthfulness mapping required")
    for flag in TRUTHFULNESS_FLAGS:
        if truthfulness.get(flag) is not False:
            raise CaseInputError(f"truthfulness flag must be explicitly false: {flag}")

    metrics: dict[str, Any] = {
        **operating_metrics,
        "forecast_assumption_traceability": forecast_traceability,
        "model_linked_core_section_ratio": model_link_ratio,
        "section_novelty_ratio": novelty_ratio,
        "citation_resolution_rate": citation_rate,
        "company_specific_metric_count": _company_metric_count(payload.get("company_metrics")),
        "future_event_model_link_count": future_event_links,
        "qualified_peer_count": len(qualified_peers),
        "unresolved_critical_question_count": _unresolved_critical_questions(payload.get("research_questions")),
    }
    thresholds = registry.get("thresholds")
    if not isinstance(thresholds, Mapping):
        raise CaseInputError("registry thresholds missing")
    gate_issues = _metric_gate_issues(metrics, thresholds)
    declared_backflow = payload.get("backflow_tasks", [])
    if not isinstance(declared_backflow, list):
        raise CaseInputError("backflow_tasks must be a list")
    quality_readout = {
        "schema_version": 1,
        "artifact_type": "r5_bundle16r_quality_readout",
        "case_id": case_id,
        "decision": "pass" if not gate_issues else "needs_backflow",
        "metrics": metrics,
        "metric_provenance": {
            "operating_metrics": "derived from reconciled historical segment bridge and driver bindings",
            "forecast_assumption_traceability": "derived from evidence locators or explicit estimate logic",
            "reader_metrics": "derived from physical section references and sentence novelty",
            "company_specific_metric_count": "derived from complete metric records",
            "future_event_model_link_count": "derived from dated verification events with model links",
        },
        "gate_issues": gate_issues,
        "truthfulness": dict(truthfulness),
        "backflow_tasks": [*declared_backflow, *route_gate_issues(gate_issues)],
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "no_advice_boundary": True,
    }
    workflow_state = {
        "schema_version": 1,
        "workflow_id": workflow_id,
        "workflow_type": "stock_first_closed_loop",
        "active_company_id": str(payload.get("company_id", "")),
        "active_stock_code": str(payload.get("ticker", "")),
        "stage": "bundle16r_engineering_candidate",
        "status": "ready_for_exact_hash_human_review" if not gate_issues else "needs_backflow",
        "information_cutoff": str(payload.get("as_of_date", "")),
        "generated_at": str(payload.get("generated_at", "")),
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "remaining_gate": "exact_hash_human_review",
    }

    paths = {
        "workflow_state": output_dir / "workflow_state.yaml",
        "evidence_pack": output_dir / "evidence_pack.json",
        "operating_driver_pack": output_dir / "operating_driver_pack.json",
        "forecast_model": output_dir / "forecast_model.json",
        "valuation_pack": output_dir / "valuation_pack.json",
        "reader_report": output_dir / "reader_report.md",
        "quality_readout": output_dir / "quality_readout.json",
        "generation_lock": output_dir / "generation_lock.json",
        "human_review": output_dir / "human_review.yaml",
    }
    write_yaml(paths["workflow_state"], workflow_state)
    write_json(paths["evidence_pack"], evidence_pack)
    write_json(paths["operating_driver_pack"], operating_pack)
    write_json(paths["forecast_model"], forecast_model)
    write_json(paths["valuation_pack"], valuation_pack)
    paths["reader_report"].write_text(reader_text, encoding="utf-8")
    write_json(paths["quality_readout"], quality_readout)

    pre_lock_roles = (
        "workflow_state",
        "evidence_pack",
        "operating_driver_pack",
        "forecast_model",
        "valuation_pack",
        "reader_report",
        "quality_readout",
    )
    pre_lock_hashes = {role: sha256_file(paths[role]) for role in pre_lock_roles}
    generation_lock = {
        "schema_version": 1,
        "artifact_type": "r5_bundle16r_generation_lock",
        "case_id": case_id,
        "reader_report_sha256": pre_lock_hashes["reader_report"],
        "artifact_hashes": pre_lock_hashes,
        "input_path": _repo_rel(repo_root, input_path.resolve()),
        "input_sha256": sha256_file(input_path),
        "information_cutoff": str(payload.get("as_of_date", "")),
    }
    write_json(paths["generation_lock"], generation_lock)
    lock_hash = sha256_file(paths["generation_lock"])
    human_review = {
        "schema_version": 1,
        "case_id": case_id,
        "status": "pending",
        "reviewer": "",
        "reviewed_at": "",
        "reader_report_sha256": pre_lock_hashes["reader_report"],
        "generation_lock_sha256": lock_hash,
        "note": "Automated generation cannot synthesize acceptance. A real reviewer must sign the exact hashes.",
    }
    write_yaml(paths["human_review"], human_review)

    source_classes = {
        "workflow_state": "workflow",
        "evidence_pack": "evidence",
        "operating_driver_pack": "model",
        "forecast_model": "model",
        "valuation_pack": "model",
        "reader_report": "report",
        "quality_readout": "quality",
        "generation_lock": "lock",
        "human_review": "review",
    }
    artifacts = [
        {
            "role": role,
            "path": _repo_rel(repo_root, path),
            "sha256": sha256_file(path),
            "source_class": source_classes[role],
        }
        for role, path in paths.items()
    ]
    case_manifest = {
        "schema_version": OUTPUT_SCHEMA,
        "case_id": case_id,
        "ticker": str(payload.get("ticker", "")),
        "issuer_name": str(payload.get("issuer_name", "")),
        "artifacts": artifacts,
        "metrics": metrics,
        "valuation": {
            "peer_multiple_used": False,
            "peer_definition_compatible": False,
            "peer_periods_aligned": False,
            "alternative_method": valuation_pack["method"],
        },
        "truthfulness": dict(truthfulness),
        "metric_provenance_path": _repo_rel(repo_root, paths["quality_readout"]),
    }
    manifest_path = case_results_dir / f"{case_id}.json"
    write_json(manifest_path, case_manifest)
    return {
        "case_id": case_id,
        "case_manifest": _repo_rel(repo_root, manifest_path),
        "output_dir": _repo_rel(repo_root, output_dir),
        "metrics": metrics,
        "gate_issues": gate_issues,
        "human_review_status": "pending",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build one deterministic Bundle 16R real-company case pack.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--input", required=True)
    parser.add_argument("--registry", default="config/r5_bundle16r_real_company_cases.yaml")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--case-results-dir", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    input_path = _repo_path(repo_root, args.input)
    registry_path = _repo_path(repo_root, args.registry)
    output_dir = _repo_path(repo_root, args.output_dir) if args.output_dir else None
    case_results_dir = _repo_path(repo_root, args.case_results_dir) if args.case_results_dir else None
    result = build_case(
        repo_root=repo_root,
        input_path=input_path,
        registry_path=registry_path,
        output_dir=output_dir,
        case_results_dir=case_results_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
