"""Deterministic reader-first narrative for periodic investment reports.

The structured ``sections`` payload remains the fact source.  This module only
selects material facts, forms a compact analysis brief, and renders a reader
report without a runtime model or a second approval workflow.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence


ANALYSIS_BRIEF_SCHEMA_VERSION = "investment_review.periodic_analysis_brief.v1"
READER_REPORT_SCHEMA_VERSION = "investment_review.reader_report.v1"

_PERIOD_LABELS = {
    "daily": "当日",
    "weekly": "本周",
    "monthly": "本月",
}
_PERIOD_TITLES = {
    "daily": "日报",
    "weekly": "周报",
    "monthly": "月报",
}
_BASIS_LABELS = {
    "total_assets": "总资产",
    "invested_market_value_ex_cash": "持仓市值（不含现金）",
    "instrument_close_price": "收盘价",
    "instrument_position_market_value": "标的持仓市值",
}
_APPENDIX_KEYS = (
    "performance_and_positions",
    "decision_context",
    "operations_and_motives",
    "review_judgments",
    "recommendation",
    "risks_invalidation_and_missing",
)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return list(value)
    return []


def _decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _visible(value: object, fallback: str = "MISSING") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def _shorten(value: object, *, limit: int = 96) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip("，。； ") + "…"


def _motive_summary(value: object) -> str:
    text = " ".join(str(value or "").split())
    if text.startswith("系统推断："):
        text = text.removeprefix("系统推断：")
    if "更像" in text:
        text = text[text.index("更像") :]
    for separator in ("；", "。"):
        if separator in text:
            text = text.split(separator, 1)[0]
    return _shorten(text, limit=56).rstrip("，。； ")


def _fundamental_constraint_summary(value: object) -> str:
    text = " ".join(str(value or "").split())
    parts: list[str] = []
    if "亏损" in text:
        parts.append("最新可得财务仍显示亏损")
    if "不能单独证明便宜" in text or "不能证明便宜" in text:
        parts.append("现有估值信息不能证明当前价格便宜")
    if "不能证明基本面反转" in text or "不等于基本面反转" in text:
        parts.append("短期上涨尚不能证明基本面反转")
    if parts:
        return "，".join(dict.fromkeys(parts))
    return _shorten(text, limit=72).rstrip("，。； ")


def _period_label(report: Mapping[str, Any]) -> str:
    period_type = str(_mapping(report.get("period")).get("type") or "")
    return _PERIOD_LABELS.get(period_type, "本期")


def _fact_ref(report: Mapping[str, Any], path: str) -> str:
    report_id = str(report.get("report_id") or "unknown")
    return f"periodic_report:{report_id}#{path}"


def _collect_refs(value: object) -> list[str]:
    refs: set[str] = set()
    payload = _mapping(value)
    source_ref = str(payload.get("source_ref") or "").strip()
    if source_ref:
        refs.add(source_ref)
    for item in _sequence(payload.get("source_refs")):
        selected = str(item or "").strip()
        if selected:
            refs.add(selected)
    return sorted(refs)


def _refs(
    report: Mapping[str, Any],
    path: str,
    *payloads: object,
) -> list[str]:
    refs = {_fact_ref(report, path)}
    for payload in payloads:
        refs.update(_collect_refs(payload))
    return sorted(refs)


def _finding(
    *,
    kind: str,
    claim_type: str,
    importance: int,
    text: str,
    source_refs: Sequence[str],
) -> dict[str, Any]:
    return {
        "kind": kind,
        "type": claim_type,
        "importance": importance,
        "text": text.strip(),
        "source_refs": sorted({str(item) for item in source_refs if item}),
    }


def _performance_finding(report: Mapping[str, Any]) -> dict[str, Any]:
    sections = _mapping(report.get("sections"))
    facts = _mapping(sections.get("performance_and_positions"))
    performance = _mapping(facts.get("performance"))
    subject = _mapping(report.get("subject"))
    period_label = _period_label(report)
    basis = str(performance.get("performance_basis") or "MISSING")
    basis_label = _BASIS_LABELS.get(basis, "可核对表现")
    change_pct = _decimal(performance.get("period_change_pct"))
    change_value = performance.get("period_change_cny")
    covered = _sequence(performance.get("covered_trading_days"))
    coverage_text = (
        f"，覆盖 {len(covered)} 个交易日" if len(covered) > 1 else ""
    )

    if change_pct is None:
        if subject.get("type") == "instrument":
            text = (
                f"{period_label}缺少可比期初价格，标的收益率保持 MISSING"
                f"{coverage_text}；持仓市值变化包含买卖数量影响，不能替代收益。"
            )
        else:
            text = (
                f"{period_label}{basis_label}收益率无法完整计算{coverage_text}；"
                "报告只保留可核对变化，不用零或其他口径填补。"
            )
    else:
        direction = "上涨" if change_pct > 0 else ("回落" if change_pct < 0 else "持平")
        unit = "元/股" if basis == "instrument_close_price" else "元"
        text = (
            f"{period_label}{basis_label}{direction} {abs(change_pct)}%"
            f"{coverage_text}，对应变化 {_visible(change_value)} {unit}。"
        )
    return _finding(
        kind="period_performance",
        claim_type="fact",
        importance=100,
        text=text,
        source_refs=_refs(
            report,
            "sections.performance_and_positions.performance",
            performance,
        ),
    )


def _risk_finding(report: Mapping[str, Any]) -> dict[str, Any] | None:
    sections = _mapping(report.get("sections"))
    facts = _mapping(sections.get("performance_and_positions"))
    risk = _mapping(facts.get("risk_change"))
    subject = _mapping(report.get("subject"))
    positions = [
        _mapping(item) for item in _sequence(facts.get("positions"))
    ]
    period_label = _period_label(report)

    if subject.get("type") == "portfolio":
        cash_weight = _decimal(risk.get("cash_weight_pct"))
        top_weight = _decimal(risk.get("top_position_weight_pct"))
        top3_weight = _decimal(risk.get("top3_weight_pct"))
        material: list[str] = []
        if cash_weight is None:
            material.append("现金权重 MISSING")
        elif cash_weight < Decimal("5"):
            material.append(f"现金权重仅 {cash_weight}%")
        else:
            material.append(f"现金权重 {cash_weight}%")
        if top_weight is not None and top_weight > Decimal("20"):
            material.append(f"最大单一标的 {top_weight}%")
        if top3_weight is not None and top3_weight > Decimal("50"):
            material.append(f"前三大合计 {top3_weight}%")
        if not material:
            return None
        return _finding(
            kind="portfolio_risk",
            claim_type="fact_and_inference",
            importance=95,
            text=(
                f"{period_label}风险承载主要受"
                + "、".join(material)
                + "等因素约束；收益变化不能替代对现金与集中度的检查。"
            ),
            source_refs=_refs(
                report,
                "sections.performance_and_positions.risk_change",
                risk,
            ),
        )

    selected = next(
        (
            item
            for item in positions
            if str(item.get("ts_code") or "") == str(subject.get("id") or "")
        ),
        None,
    )
    if selected is None:
        return _finding(
            kind="position_risk",
            claim_type="fact",
            importance=90,
            text=f"{period_label}期末已无该标的持仓；后续建议应按退出后的暴露重新评估。",
            source_refs=_refs(
                report,
                "sections.performance_and_positions.positions",
                facts,
            ),
        )
    weight = _visible(selected.get("portfolio_weight_pct"))
    unrealized = selected.get("unrealized_return_pct")
    cost = selected.get("average_cost_cny")
    close = selected.get("close_cny")
    return _finding(
        kind="position_risk",
        claim_type="fact_and_inference",
        importance=90,
        text=(
            f"{period_label}期末仓位权重 {weight}%，收盘价 "
            f"{_visible(close)} 元、账面成本 {_visible(cost)} 元"
            + (
                f"，未实现收益率 {_visible(unrealized)}%。"
                if unrealized is not None
                else "，未实现收益率 MISSING。"
            )
        ),
        source_refs=_refs(
            report,
            "sections.performance_and_positions.positions",
            selected,
        ),
    )


def _context_findings(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    sections = _mapping(report.get("sections"))
    context = _mapping(sections.get("decision_context"))
    subject = _mapping(report.get("subject"))
    period_type = str(_mapping(report.get("period")).get("type") or "")
    findings: list[dict[str, Any]] = []

    fundamental = _mapping(context.get("fundamental_and_valuation"))
    if (
        subject.get("type") == "instrument"
        and fundamental.get("status") in {"available", "partial"}
        and str(fundamental.get("summary") or "").strip()
    ):
        findings.append(
            _finding(
                kind="fundamental_constraint",
                claim_type="fact_and_inference",
                importance=85 if period_type == "monthly" else 75,
                text=_shorten(fundamental.get("summary")),
                source_refs=_refs(
                    report,
                    "sections.decision_context.fundamental_and_valuation",
                    fundamental,
                ),
            )
        )

    market = _mapping(context.get("market_and_sector"))
    technical = _mapping(context.get("technical_and_trend"))
    context_parts: list[str] = []
    context_refs: set[str] = set()
    if subject.get("type") == "instrument":
        for key, layer, prefix in (
            ("market_and_sector", market, "市场与板块"),
            ("technical_and_trend", technical, "技术与趋势"),
        ):
            if (
                layer.get("status") in {"available", "partial"}
                and str(layer.get("summary") or "").strip()
            ):
                summary = _shorten(layer.get("summary"), limit=130).rstrip(
                    "，。； "
                )
                context_parts.append(f"{prefix}：{summary}")
                context_refs.update(
                    _refs(report, f"sections.decision_context.{key}", layer)
                )
    if context_parts:
        findings.append(
            _finding(
                kind="market_trend_context",
                claim_type="fact_and_inference",
                importance=70,
                text="；".join(context_parts) + "。这些信息只提供概率性环境。",
                source_refs=sorted(context_refs),
            )
        )
    return findings


def _operation_finding(report: Mapping[str, Any]) -> dict[str, Any]:
    sections = _mapping(report.get("sections"))
    operations_section = _mapping(sections.get("operations_and_motives"))
    operations = [
        _mapping(item) for item in _sequence(operations_section.get("operations"))
    ]
    summaries = [
        _mapping(item)
        for item in _sequence(operations_section.get("episode_summaries"))
    ]
    count = int(operations_section.get("operation_count") or len(operations))
    period_label = _period_label(report)
    refs: set[str] = set(
        _refs(report, "sections.operations_and_motives", operations_section)
    )
    for operation in operations:
        refs.update(_collect_refs(operation))
        refs.update(_collect_refs(_mapping(operation.get("motive"))))
    for summary in summaries:
        refs.update(_collect_refs(summary))

    if count == 0:
        return _finding(
            kind="operation_review",
            claim_type="fact",
            importance=60,
            text=f"{period_label}没有持仓变动操作，不构造虚假动机或执行评价。",
            source_refs=sorted(refs),
        )

    inferred = [
        operation
        for operation in operations
        if _mapping(operation.get("motive")).get("label") == "system_inference"
    ]
    motives = list(
        dict.fromkeys(
            _motive_summary(
                _mapping(operation.get("motive")).get("most_likely_motive"),
            )
            for operation in inferred
            if _mapping(operation.get("motive")).get("most_likely_motive")
        )
    )
    text = f"{period_label}共有 {count} 笔操作。"
    if inferred:
        text += (
            f"其中 {len(inferred)} 笔缺少 Decision，以下仅为 "
            f"system_inference：{'；'.join(motives[:2]) or '动机信息有限'}。"
            "替代解释与时点证据保留在附录。"
        )
    if summaries:
        primary = next(
            (
                item
                for item in summaries
                if (_decimal(item.get("net_round_trip_pnl_cny")) or Decimal("0"))
                < 0
            ),
            summaries[0],
        )
        path = " → ".join(
            _visible(primary.get(key))
            for key in (
                "opening_quantity",
                "peak_quantity",
                "closing_quantity",
            )
        )
        text += (
            f"{_visible(primary.get('name'), _visible(primary.get('ts_code')))}"
            f"仓位路径为 {path} 股；"
            f"{_shorten(primary.get('assessment'), limit=100)}"
        )
    text += "事后结果只用于检验执行，不用于倒推动机。"
    return _finding(
        kind="operation_review",
        claim_type=(
            "system_inference_and_retrospective"
            if inferred
            else "fact_and_retrospective"
        ),
        importance=88,
        text=text,
        source_refs=sorted(refs),
    )


def _cross_period_finding(
    report: Mapping[str, Any],
) -> dict[str, Any] | None:
    period = _mapping(report.get("period"))
    if period.get("type") not in {"weekly", "monthly"}:
        return None
    sections = _mapping(report.get("sections"))
    facts = _mapping(sections.get("performance_and_positions"))
    attribution = _mapping(facts.get("period_attribution"))
    daily_changes = [
        _mapping(item) for item in _sequence(attribution.get("daily_changes"))
    ]
    if not daily_changes:
        return None
    positive = 0
    negative = 0
    operation_days = 0
    for item in daily_changes:
        change = _decimal(item.get("period_change_pct"))
        if change is None:
            change = _decimal(item.get("period_change_cny"))
        if change is not None and change > 0:
            positive += 1
        elif change is not None and change < 0:
            negative += 1
        if int(item.get("operation_count") or 0) > 0:
            operation_days += 1
    risk = _mapping(facts.get("risk_change"))
    changes = [
        _mapping(item) for item in _sequence(risk.get("position_changes"))
    ]
    added = sum(
        str(item.get("status") or "") in {"opened", "added"} for item in changes
    )
    reduced = sum(
        str(item.get("status") or "") in {"reduced", "exited"} for item in changes
    )
    label = _period_label(report)
    return _finding(
        kind="cross_period_synthesis",
        claim_type="fact_and_inference",
        importance=92,
        text=(
            f"{label}覆盖 {len(daily_changes)} 个交易日："
            f"{positive} 日走强、{negative} 日回落，"
            f"操作发生在 {operation_days} 个交易日；"
            f"期初至期末新增或加仓 {added} 个标的、减仓或退出 {reduced} 个标的。"
        ),
        source_refs=_refs(
            report,
            "sections.performance_and_positions.period_attribution",
            attribution,
        ),
    )


def _action_plan(report: Mapping[str, Any]) -> dict[str, Any]:
    sections = _mapping(report.get("sections"))
    recommendation = _mapping(sections.get("recommendation"))
    target = _mapping(recommendation.get("target_position"))
    action = str(recommendation.get("action") or "hold")
    target_note = str(
        target.get("target_position_note")
        or "仓位精度受当前缺失数据限制。"
    )
    confidence = str(recommendation.get("confidence") or "low")
    horizon = str(recommendation.get("time_horizon") or "下一次实质性信息更新前")
    return {
        "type": "analyst_view",
        "action": action,
        "target_position": dict(target),
        "target_position_note": target_note,
        "time_horizon": horizon,
        "confidence": confidence,
        "text": (
            f"维持 {confidence} 置信度的 {action} 建议："
            f"{target_note}期限为 {horizon}。"
        ),
        "source_refs": _refs(
            report,
            "sections.recommendation",
            recommendation,
        ),
        "orders_executed": False,
        "guaranteed_return": False,
    }


def _central_judgment(
    report: Mapping[str, Any],
    *,
    performance: Mapping[str, Any],
    risk: Mapping[str, Any] | None,
    contexts: Sequence[Mapping[str, Any]],
    operation: Mapping[str, Any],
    action_plan: Mapping[str, Any],
) -> dict[str, Any]:
    subject = _mapping(report.get("subject"))
    subject_name = str(subject.get("name") or subject.get("id") or "报告对象")
    action = str(action_plan.get("action") or "hold")
    target_note = str(action_plan.get("target_position_note") or "")
    performance_text = str(performance.get("text") or "").rstrip("。； ")
    constraints: list[str] = []
    fundamental = next(
        (
            item
            for item in contexts
            if item.get("kind") == "fundamental_constraint"
        ),
        None,
    )
    if fundamental is not None:
        constraints.append(_fundamental_constraint_summary(fundamental.get("text")))
    if risk is not None:
        constraints.append(_shorten(risk.get("text"), limit=82).rstrip("。； "))
    operation_text = str(operation.get("text") or "")
    if (
        "没有持仓变动操作" not in operation_text
        and any(
            token in operation_text
            for token in ("净结果", "需要改进", "未覆盖", "拖累", "亏损")
        )
    ):
        constraints.append("本期操作暴露出需要改进的执行问题")
    connector = "但" if "上涨" in performance_text else "同时"
    central = f"{subject_name}{performance_text}"
    if constraints:
        central += f"；{connector}{'；'.join(dict.fromkeys(constraints))}"
    central += f"。因此现有 {action} 建议不变：{target_note}"
    refs = set(_sequence(performance.get("source_refs")))
    if risk is not None:
        refs.update(_sequence(risk.get("source_refs")))
    elif contexts:
        refs.update(_sequence(contexts[0].get("source_refs")))
    refs.update(_sequence(action_plan.get("source_refs")))
    return {
        "type": "inference_and_analyst_view",
        "text": " ".join(central.split()),
        "source_refs": sorted(str(item) for item in refs if item),
    }


def build_analysis_brief(report: Mapping[str, Any]) -> dict[str, Any]:
    """Select material facts and form one deterministic analysis brief."""

    sections = _mapping(report.get("sections"))
    performance = _performance_finding(report)
    risk = _risk_finding(report)
    contexts = _context_findings(report)
    operation = _operation_finding(report)
    cross_period = _cross_period_finding(report)
    action_plan = _action_plan(report)

    candidates: list[dict[str, Any]] = [performance]
    if risk is not None:
        candidates.append(risk)
    if cross_period is not None:
        candidates.append(cross_period)
    candidates.extend(contexts)
    candidates.append(operation)
    candidates.sort(key=lambda item: int(item.get("importance") or 0), reverse=True)

    material_findings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in candidates:
        normalized = " ".join(str(item.get("text") or "").split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        material_findings.append(item)
        if len(material_findings) == 5:
            break
    if operation not in material_findings:
        material_findings[-1:] = [operation]

    recommendation = _mapping(sections.get("recommendation"))
    limitations = _mapping(sections.get("risks_invalidation_and_missing"))
    risks = list(
        dict.fromkeys(
            str(item)
            for item in _sequence(recommendation.get("major_downside_risks"))
            if str(item).strip()
        )
    )
    invalidation = list(
        dict.fromkeys(
            str(item)
            for item in _sequence(recommendation.get("invalidation_conditions"))
            if str(item).strip()
        )
    )
    missing = sorted(
        {
            str(item)
            for item in (
                _sequence(recommendation.get("important_missing_inputs"))
                + _sequence(limitations.get("missing_inputs"))
                + _sequence(limitations.get("data_limitations"))
            )
            if str(item).strip()
        }
    )
    central = _central_judgment(
        report,
        performance=performance,
        risk=risk,
        contexts=contexts,
        operation=operation,
        action_plan=action_plan,
    )
    return {
        "schema_version": ANALYSIS_BRIEF_SCHEMA_VERSION,
        "source_report_schema_version": str(report.get("schema_version") or ""),
        "subject": dict(_mapping(report.get("subject"))),
        "period": dict(_mapping(report.get("period"))),
        "central_judgment": central,
        "material_findings": material_findings,
        "causal_chain": [
            {
                "type": "inference",
                "text": str(item.get("text") or ""),
                "source_refs": list(item.get("source_refs") or []),
            }
            for item in material_findings
        ],
        "operation_assessment": {
            "text": operation["text"],
            "source_refs": operation["source_refs"],
            "separates_motive_from_retrospective": True,
        },
        "action_plan": action_plan,
        "risks_and_invalidation": {
            "major_risks": risks,
            "invalidation_conditions": invalidation,
            "missing_inputs": missing,
            "source_refs": _refs(
                report,
                "sections.risks_invalidation_and_missing",
                limitations,
            ),
        },
        "evidence_pool": {
            "section_keys": list(_APPENDIX_KEYS),
            "four_layer_context_is_not_mandatory_headings": True,
        },
    }


def build_reader_report(
    report: Mapping[str, Any],
    *,
    analysis_brief: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Turn an analysis brief into compact reader-facing prose."""

    brief = (
        dict(analysis_brief)
        if isinstance(analysis_brief, Mapping)
        else build_analysis_brief(report)
    )
    findings = [
        _mapping(item) for item in _sequence(brief.get("material_findings"))
    ]
    cross = [item for item in findings if item.get("kind") == "cross_period_synthesis"]
    operations = [item for item in findings if item.get("kind") == "operation_review"]
    main = [
        item
        for item in findings
        if item.get("kind") not in {"cross_period_synthesis", "operation_review"}
    ]
    subject = _mapping(report.get("subject"))
    narrative_sections: list[dict[str, Any]] = []

    if main:
        title = (
            "收益变化与风险结构"
            if subject.get("type") == "portfolio"
            else "趋势、基本面与仓位约束"
        )
        paragraphs: list[str] = []
        if subject.get("type") == "instrument":
            by_kind = {
                str(item.get("kind") or ""): item
                for item in main
            }
            performance_item = by_kind.get("period_performance")
            market_item = by_kind.get("market_trend_context")
            if performance_item is not None:
                paragraph = str(performance_item.get("text") or "")
                if market_item is not None:
                    paragraph += " " + str(market_item.get("text") or "")
                paragraphs.append(paragraph)
            fundamental_item = by_kind.get("fundamental_constraint")
            risk_item = by_kind.get("position_risk")
            constraint_parts = [
                str(item.get("text") or "")
                for item in (fundamental_item, risk_item)
                if item is not None
            ]
            if constraint_parts:
                paragraphs.append(" ".join(constraint_parts))
            used_kinds = {
                "period_performance",
                "market_trend_context",
                "fundamental_constraint",
                "position_risk",
            }
            paragraphs.extend(
                str(item.get("text") or "")
                for item in main
                if item.get("kind") not in used_kinds
            )
        else:
            paragraphs = [str(item.get("text") or "") for item in main]
        narrative_sections.append(
            {
                "key": "judgment_basis",
                "title": title,
                "paragraphs": paragraphs,
                "source_refs": sorted(
                    {
                        str(ref)
                        for item in main
                        for ref in _sequence(item.get("source_refs"))
                        if ref
                    }
                ),
            }
        )
    if cross:
        narrative_sections.append(
            {
                "key": "cross_period_synthesis",
                "title": "跨期变化",
                "paragraphs": [str(item.get("text") or "") for item in cross],
                "source_refs": sorted(
                    {
                        str(ref)
                        for item in cross
                        for ref in _sequence(item.get("source_refs"))
                        if ref
                    }
                ),
            }
        )
    if operations:
        narrative_sections.append(
            {
                "key": "operation_review",
                "title": "操作复盘",
                "paragraphs": [str(item.get("text") or "") for item in operations],
                "source_refs": sorted(
                    {
                        str(ref)
                        for item in operations
                        for ref in _sequence(item.get("source_refs"))
                        if ref
                    }
                ),
            }
        )

    risks = _mapping(brief.get("risks_and_invalidation"))
    action_plan = dict(_mapping(brief.get("action_plan")))
    return {
        "schema_version": READER_REPORT_SCHEMA_VERSION,
        "central_judgment": str(
            _mapping(brief.get("central_judgment")).get("text") or ""
        ),
        "central_judgment_source_refs": list(
            _mapping(brief.get("central_judgment")).get("source_refs") or []
        ),
        "narrative_sections": narrative_sections,
        "action_plan": action_plan,
        "major_risks": list(risks.get("major_risks") or []),
        "invalidation_conditions": list(
            risks.get("invalidation_conditions") or []
        ),
        "missing_inputs": list(risks.get("missing_inputs") or []),
        "appendix": {
            "collapsed_by_default": True,
            "section_keys": list(_APPENDIX_KEYS),
            "includes_source_and_safety": True,
        },
        "orders_executed": False,
        "guaranteed_return": False,
    }


def validate_periodic_narrative(report: Mapping[str, Any]) -> list[str]:
    """Return V2 narrative validation errors without validating base facts."""

    errors: list[str] = []
    brief = report.get("analysis_brief")
    reader = report.get("reader_report")
    if not isinstance(brief, Mapping):
        return ["missing_analysis_brief"]
    if brief.get("schema_version") != ANALYSIS_BRIEF_SCHEMA_VERSION:
        errors.append("invalid_analysis_brief_schema")
    central = _mapping(brief.get("central_judgment"))
    if not str(central.get("text") or "").strip():
        errors.append("missing_central_judgment")
    if not _sequence(central.get("source_refs")):
        errors.append("central_judgment_missing_source_refs")
    findings = [
        _mapping(item) for item in _sequence(brief.get("material_findings"))
    ]
    if not 1 <= len(findings) <= 5:
        errors.append("invalid_material_finding_count")
    finding_texts: set[str] = set()
    for item in findings:
        text = " ".join(str(item.get("text") or "").split())
        if not text:
            errors.append("empty_material_finding")
        elif text in finding_texts:
            errors.append("duplicate_material_finding")
        finding_texts.add(text)
        if not _sequence(item.get("source_refs")):
            errors.append("material_finding_missing_source_refs")
    action = _mapping(brief.get("action_plan"))
    if not str(action.get("action") or "").strip():
        errors.append("analysis_brief_missing_action")
    if action.get("orders_executed") is not False:
        errors.append("analysis_brief_orders_executed_not_false")
    if action.get("guaranteed_return") is not False:
        errors.append("analysis_brief_guaranteed_return_not_false")

    if not isinstance(reader, Mapping):
        return sorted(set(errors + ["missing_reader_report"]))
    if reader.get("schema_version") != READER_REPORT_SCHEMA_VERSION:
        errors.append("invalid_reader_report_schema")
    if reader.get("central_judgment") != central.get("text"):
        errors.append("reader_central_judgment_mismatch")
    narrative_sections = [
        _mapping(item) for item in _sequence(reader.get("narrative_sections"))
    ]
    if not 1 <= len(narrative_sections) <= 3:
        errors.append("invalid_reader_section_count")
    paragraph_texts: set[str] = set()
    forbidden_titles = {
        "基本面与估值",
        "大盘与板块",
        "技术与趋势",
        "仓位与执行",
    }
    for section in narrative_sections:
        if str(section.get("title") or "") in forbidden_titles:
            errors.append("reader_uses_mandatory_four_layer_heading")
        paragraphs = [
            " ".join(str(item or "").split())
            for item in _sequence(section.get("paragraphs"))
            if str(item or "").strip()
        ]
        if not paragraphs:
            errors.append("empty_reader_section")
        for paragraph in paragraphs:
            if paragraph in paragraph_texts:
                errors.append("duplicate_reader_paragraph")
            paragraph_texts.add(paragraph)
        if not _sequence(section.get("source_refs")):
            errors.append("reader_section_missing_source_refs")
    appendix = _mapping(reader.get("appendix"))
    if not set(_APPENDIX_KEYS).issubset(
        {str(item) for item in _sequence(appendix.get("section_keys"))}
    ):
        errors.append("reader_appendix_incomplete")
    if reader.get("orders_executed") is not False:
        errors.append("reader_orders_executed_not_false")
    if reader.get("guaranteed_return") is not False:
        errors.append("reader_guaranteed_return_not_false")
    return sorted(set(errors))


def render_reader_report_markdown(report: Mapping[str, Any]) -> str:
    """Render V2 main prose and keep the complete fact payload collapsed."""

    subject = _mapping(report.get("subject"))
    period = _mapping(report.get("period"))
    reader = _mapping(report.get("reader_report"))
    subject_label = (
        str(subject.get("name") or subject.get("id") or "组合")
        if subject.get("type") == "portfolio"
        else (
            f"{_visible(subject.get('name'), _visible(subject.get('id')))}"
            f"（{_visible(subject.get('id'))}）"
        )
    )
    period_type = str(period.get("type") or "")
    action = _mapping(reader.get("action_plan"))
    lines = [
        f"# {subject_label} {period.get('end')} {_PERIOD_TITLES.get(period_type, '周期报告')}",
        "",
        f"> **中心判断：** {reader.get('central_judgment')}",
        "",
        f"**报告截止：** {period.get('report_cutoff_at')}",
        "",
    ]
    for section in _sequence(reader.get("narrative_sections")):
        selected = _mapping(section)
        lines.extend([f"## {selected.get('title')}", ""])
        for paragraph in _sequence(selected.get("paragraphs")):
            lines.extend([str(paragraph), ""])
    lines.extend(
        [
            "## 下一步行动",
            "",
            f"- **动作：** `{action.get('action')}`",
            f"- **仓位：** {action.get('target_position_note')}",
            f"- **期限：** {action.get('time_horizon')}",
            f"- **置信度：** `{action.get('confidence')}`",
            "",
            "这是一项分析建议，不是订单；报告不会连接券商或自动执行交易。",
            "",
            "## 风险、失效条件与数据缺口",
            "",
        ]
    )
    for item in _sequence(reader.get("major_risks")):
        lines.append(f"- 主要风险：{item}")
    for item in _sequence(reader.get("invalidation_conditions")):
        lines.append(f"- 失效条件：{item}")
    missing = [str(item) for item in _sequence(reader.get("missing_inputs"))]
    lines.append(f"- 缺失输入：{', '.join(missing) if missing else '无明确缺失项'}")
    appendix_payload = {
        "analysis_brief": report.get("analysis_brief"),
        "sections": report.get("sections"),
        "source": report.get("source"),
        "safety": report.get("safety"),
    }
    lines.extend(
        [
            "",
            "<details>",
            "<summary>结构化事实与来源</summary>",
            "",
            f"- 报告 ID：`{report.get('report_id')}`",
            f"- 报告 schema：`{report.get('schema_version')}`",
            "- 完整四层事实、逐笔操作、缺失项和来源如下；默认折叠。",
            "",
            "```json",
            json.dumps(
                appendix_payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "</details>",
            "",
        ]
    )
    return "\n".join(lines)
