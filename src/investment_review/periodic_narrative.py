"""Deterministic reader-first narrative for periodic investment reports.

The structured ``sections`` payload remains the fact source.  This module only
selects material facts, forms a compact analysis brief, and renders a reader
report without a runtime model or a second approval workflow.
"""

from __future__ import annotations

import json
import re
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
_ACTION_LABELS = {
    "buy": "买入",
    "sell": "卖出",
    "hold": "维持现有持仓",
    "add": "增加持仓",
    "reduce": "降低持仓",
    "exit": "退出持仓",
}
_MISSING_INPUT_LABELS = {
    "MISSING_DECISION": "本期操作缺少对应的原始决策说明",
    "MISSING_FULL_PORTFOLIO_FUNDAMENTAL_COVERAGE": (
        "尚未完成组合全部持仓的基本面覆盖"
    ),
    "MISSING_FUNDAMENTAL_AND_VALUATION_CONTEXT": (
        "缺少可核对的基本面与估值材料"
    ),
    "MISSING_INTRADAY_MARKET_CONTEXT": "缺少操作时点的市场环境资料",
    "MISSING_MARKET_AND_SECTOR_CONTEXT": "缺少可核对的市场与板块资料",
    "MISSING_TECHNICAL_AND_TREND_CONTEXT": "缺少可核对的价格趋势资料",
    "MISSING_STRATEGY_OR_TARGET_POSITION": "尚未确认投资策略与目标仓位",
    "UNKNOWN_TRADE_FEE_PROVENANCE": "部分交易费用的来源仍待核实",
}
_OBSERVATION_INPUT_CODES = {
    "MISSING_EXPLICIT_USER_REVIEW_MODE",
    "MISSING_EXPLICIT_USER_RISK_BUDGET",
    "MISSING_EXPLICIT_USER_RISK_POLICY",
    "MISSING_EXPLICIT_USER_TIME_HORIZON",
}
_INTERNAL_MISSING_CODE = re.compile(r"\b(?:MISSING|UNKNOWN)(?:_[A-Z0-9]+)*\b")
_READER_FORBIDDEN_TERM = re.compile(
    r"\b(?:MISSING|UNKNOWN)(?:_[A-Z0-9]+)*\b"
    r"|\bsystem_inference\b|\bobservation_only\b|\bDecision\b"
    r"|\b(?:buy|sell|hold|add|reduce|exit)\b"
)
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


def _reader_value(value: object, fallback: str = "暂缺可靠数据") -> str:
    """Render a missing value for a reader without leaking storage sentinels."""

    if value is None or value == "":
        return fallback
    return str(value)


def _action_label(value: object) -> str:
    action = str(value or "").strip()
    return _ACTION_LABELS.get(action, action or "继续观察")


def _missing_input_label(value: object) -> str:
    code = str(value or "").strip()
    if code in _MISSING_INPUT_LABELS:
        return _MISSING_INPUT_LABELS[code]
    if code.startswith("MISSING_") or code.startswith("UNKNOWN_"):
        return "仍有一项基础资料尚未核实"
    return code


def _reader_text(value: object) -> str:
    """Translate storage vocabulary only when it enters reader-visible prose."""

    text = " ".join(str(value or "").split())
    text = re.sub(r"(\d+日)\s*=\s*MISSING\s*%", r"\1数据暂缺", text)
    text = text.replace("system_inference", "系统推测")
    text = text.replace("observation_only", "事实复盘")
    text = text.replace("advice 模式", "行动建议")
    text = text.replace("Decision", "原始决策说明")

    def replace_missing(match: re.Match[str]) -> str:
        code = match.group(0)
        if code == "MISSING":
            return "数据暂缺"
        if code == "UNKNOWN":
            return "来源待核实"
        return _missing_input_label(code)

    text = _INTERNAL_MISSING_CODE.sub(replace_missing, text)
    for action, label in _ACTION_LABELS.items():
        text = re.sub(rf"`?\b{action}\b`?", label, text)
    return text


def _reader_action_plan(value: object) -> dict[str, Any]:
    plan = dict(_mapping(value))
    for key in (
        "text",
        "target_position_note",
        "time_horizon",
        "user_risk_budget",
    ):
        if plan.get(key) is not None:
            plan[key] = _reader_text(plan.get(key))
    if plan.get("action"):
        plan["action_label"] = _action_label(plan.get("action"))
    if plan.get("mode") == "observation_only":
        plan["questions_to_resolve"] = [
            "如需进一步形成行动方案，需要先明确投资期限、可承受损失和仓位边界。"
        ]
    else:
        plan["questions_to_resolve"] = [
            _reader_text(item)
            for item in _sequence(plan.get("questions_to_resolve"))
            if str(item).strip()
        ]
    return plan


def _reader_risk_summary(
    value: object,
    *,
    action_mode: object,
) -> dict[str, list[str]]:
    risks = _mapping(value)
    observation_only = action_mode == "observation_only"
    major_risks = [
        _reader_text(item)
        for item in _sequence(risks.get("major_risks"))
        if str(item).strip()
        and not (
            observation_only and "不能单独决定交易动作" in str(item)
        )
    ][:1]
    invalidation_conditions = [
        _reader_text(item)
        for item in _sequence(risks.get("invalidation_conditions"))
        if str(item).strip()
        and not (observation_only and "风险策略" in str(item))
    ][:1]
    missing_codes = [
        str(item)
        for item in _sequence(risks.get("missing_inputs"))
        if str(item).strip()
        and not (
            observation_only
            and str(item) in _OBSERVATION_INPUT_CODES | {"MISSING_DECISION"}
        )
    ]
    missing_labels = list(
        dict.fromkeys(_reader_text(_missing_input_label(item)) for item in missing_codes)
    )
    return {
        "major_risks": major_risks,
        "invalidation_conditions": invalidation_conditions,
        "missing_inputs": ["；".join(missing_labels)] if missing_labels else [],
    }


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
                f"{period_label}缺少可比期初价格，暂时无法计算本期收益率"
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
            material.append("现金权重尚无法可靠计算")
        else:
            material.append(f"现金权重 {cash_weight}%")
        if top_weight is not None:
            material.append(f"最大单一标的 {top_weight}%")
        if top3_weight is not None:
            material.append(f"前三大合计 {top3_weight}%")
        if not material:
            return None
        return _finding(
            kind="portfolio_risk",
            claim_type="fact",
            importance=95,
            text=(
                f"{period_label}期末组合结构："
                + "、".join(material)
                + "。"
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
            text=f"{period_label}期末已无该标的持仓，当前暴露已经归零。",
            source_refs=_refs(
                report,
                "sections.performance_and_positions.positions",
                facts,
            ),
        )
    weight = _reader_value(selected.get("portfolio_weight_pct"))
    unrealized = selected.get("unrealized_return_pct")
    cost = selected.get("average_cost_cny")
    close = selected.get("close_cny")
    return _finding(
        kind="position_risk",
        claim_type="fact_and_inference",
        importance=90,
        text=(
            f"{period_label}期末仓位权重 {weight}%，收盘价 "
            f"{_reader_value(close)} 元、账面成本 {_reader_value(cost)} 元"
            + (
                f"，未实现收益率 {_reader_value(unrealized)}%。"
                if unrealized is not None
                else "，暂时无法可靠计算未实现收益率。"
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
            f"其中 {len(inferred)} 笔没有原始决策说明；系统按操作时点信息推测："
            f"{'；'.join(motives[:2]) or '现有信息不足以形成明确解释'}。"
            "这不是用户原话，替代解释和时点证据见附录。"
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
    if recommendation.get("mode") == "observation_only":
        return {
            "type": "observation",
            "mode": "observation_only",
            "action": None,
            "target_position": None,
            "target_position_note": None,
            "time_horizon": None,
            "confidence": "not_applicable",
            "text": (
                "本期先核对事实、操作结果和仍需确认的问题，不给出交易动作或目标仓位。"
            ),
            "questions_to_resolve": list(
                _sequence(recommendation.get("questions_to_resolve"))
            ),
            "source_refs": _refs(
                report,
                "sections.recommendation",
                recommendation,
            ),
            "orders_executed": False,
            "guaranteed_return": False,
        }
    target = _mapping(recommendation.get("target_position"))
    action = str(recommendation.get("action") or "")
    mode = (
        "advice"
        if recommendation.get("mode") == "advice"
        else "historical_snapshot"
    )
    source_target_note = str(
        target.get("target_position_note")
        or "仓位精度受当前缺失数据限制。"
    )
    target_note = source_target_note
    if action == "hold" and source_target_note.startswith("把超过"):
        target_note = (
            "维持现有总风险暴露；"
            + source_target_note.replace("把超过", "若有超过", 1).replace(
                "降至",
                "则降至",
                1,
            )
        )
    confidence = str(recommendation.get("confidence") or "low")
    horizon = str(recommendation.get("time_horizon") or "下一次实质性信息更新前")
    return {
        "type": "analyst_view",
        "mode": mode,
        "decision_basis": recommendation.get("decision_basis"),
        "user_risk_budget": recommendation.get("user_risk_budget"),
        "action": action,
        "target_position": dict(target),
        "target_position_note": target_note,
        "time_horizon": horizon,
        "confidence": confidence,
        "text": (
            f"当前判断为{_action_label(action)}："
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
    observation_only = action_plan.get("mode") == "observation_only"
    historical_snapshot = action_plan.get("mode") == "historical_snapshot"
    action = str(action_plan.get("action") or "")
    target_note = str(action_plan.get("target_position_note") or "")
    performance_text = str(performance.get("text") or "").rstrip("。； ")
    focus = ""
    focus_refs: set[str] = set()
    fundamental = next(
        (
            item
            for item in contexts
            if item.get("kind") == "fundamental_constraint"
        ),
        None,
    )
    risk_text = str(risk.get("text") or "") if risk is not None else ""
    if risk is not None and any(
        token in risk_text
        for token in ("现金权重尚无法可靠计算", "期末已无该标的持仓")
    ):
        focus = _shorten(risk_text, limit=88).rstrip("。； ")
        focus_refs.update(_sequence(risk.get("source_refs")))
    if fundamental is not None and not focus:
        fundamental_focus = _fundamental_constraint_summary(fundamental.get("text"))
        if any(
            token in fundamental_focus
            for token in ("亏损", "风险", "不能证明", "下滑", "恶化", "高估")
        ):
            focus = fundamental_focus
            focus_refs.update(_sequence(fundamental.get("source_refs")))
    operation_text = str(operation.get("text") or "")
    if not focus and "日内新增仓位已全部撤回" in operation_text:
        focus = "日内新增仓位最终全部撤回，本期更值得复盘的是这组往返操作"
        focus_refs.update(_sequence(operation.get("source_refs")))
    elif not focus and (
        "没有持仓变动操作" not in operation_text
        and any(
            token in operation_text
            for token in ("净结果", "需要改进", "未覆盖", "拖累", "亏损")
        )
    ):
        focus = "本期更值得关注的是操作中暴露出的执行问题"
        focus_refs.update(_sequence(operation.get("source_refs")))
    if not focus and risk is not None:
        focus = _shorten(risk.get("text"), limit=88).rstrip("。； ")
        focus_refs.update(_sequence(risk.get("source_refs")))
    central = f"{subject_name}{performance_text}"
    if focus:
        central += f"；{focus}"
    if historical_snapshot:
        central += (
            f"。当时的记录建议{_action_label(action)}：{target_note}"
            "这只是历史快照，不代表当前建议。"
        )
    elif not observation_only:
        central += f"。结合用户已经确认的策略，当前建议{_action_label(action)}：{target_note}"
    refs = set(_sequence(performance.get("source_refs")))
    if risk is not None:
        refs.update(_sequence(risk.get("source_refs")))
    elif contexts:
        refs.update(_sequence(contexts[0].get("source_refs")))
    refs.update(focus_refs)
    if not observation_only:
        refs.update(_sequence(action_plan.get("source_refs")))
    return {
        "type": (
            "inference"
            if observation_only or historical_snapshot
            else "inference_and_analyst_view"
        ),
        "text": _reader_text(central),
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
    central_text = str(_mapping(brief.get("central_judgment")).get("text") or "")

    def is_already_central(item: Mapping[str, Any]) -> bool:
        text = str(item.get("text") or "").strip("。； ")
        return bool(text and text in central_text)

    cross = [item for item in findings if item.get("kind") == "cross_period_synthesis"]
    operations = [item for item in findings if item.get("kind") == "operation_review"]
    main = [
        item
        for item in findings
        if item.get("kind") not in {"cross_period_synthesis", "operation_review"}
        and not is_already_central(item)
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
                paragraphs.append(_reader_text(paragraph))
            fundamental_item = by_kind.get("fundamental_constraint")
            risk_item = by_kind.get("position_risk")
            constraint_parts = [
                str(item.get("text") or "")
                for item in (fundamental_item, risk_item)
                if item is not None
            ]
            if constraint_parts:
                paragraphs.append(_reader_text(" ".join(constraint_parts)))
            used_kinds = {
                "period_performance",
                "market_trend_context",
                "fundamental_constraint",
                "position_risk",
            }
            paragraphs.extend(
                _reader_text(item.get("text"))
                for item in main
                if item.get("kind") not in used_kinds
            )
        else:
            paragraphs = [_reader_text(item.get("text")) for item in main]
        if paragraphs:
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
                "paragraphs": [_reader_text(item.get("text")) for item in cross],
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
                "paragraphs": [
                    _reader_text(item.get("text")) for item in operations
                ],
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
    action_plan = _reader_action_plan(brief.get("action_plan"))
    reader_risks = _reader_risk_summary(
        risks,
        action_mode=action_plan.get("mode"),
    )
    return {
        "schema_version": READER_REPORT_SCHEMA_VERSION,
        "central_judgment": _reader_text(
            _mapping(brief.get("central_judgment")).get("text")
        ),
        "central_judgment_source_refs": list(
            _mapping(brief.get("central_judgment")).get("source_refs") or []
        ),
        "narrative_sections": narrative_sections,
        "action_plan": action_plan,
        "major_risks": reader_risks["major_risks"],
        "invalidation_conditions": reader_risks["invalidation_conditions"],
        "missing_inputs": reader_risks["missing_inputs"],
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
    if action.get("mode") == "observation_only":
        if action.get("action") is not None:
            errors.append("observation_only_analysis_brief_has_action")
        if action.get("target_position") is not None:
            errors.append("observation_only_analysis_brief_has_target_position")
    elif not str(action.get("action") or "").strip():
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
    reader_visible_texts = [
        str(reader.get("central_judgment") or ""),
        *paragraph_texts,
        *(str(item) for item in _sequence(reader.get("major_risks"))),
        *(str(item) for item in _sequence(reader.get("invalidation_conditions"))),
        *(str(item) for item in _sequence(reader.get("missing_inputs"))),
        *(
            str(item)
            for item in _sequence(
                _mapping(reader.get("action_plan")).get("questions_to_resolve")
            )
        ),
    ]
    if any(_READER_FORBIDDEN_TERM.search(text) for text in reader_visible_texts):
        errors.append("reader_internal_vocabulary_visible")
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
        f"> **中心判断：** {_reader_text(reader.get('central_judgment'))}",
        "",
        f"**报告截止：** {period.get('report_cutoff_at')}",
        "",
    ]
    for section in _sequence(reader.get("narrative_sections")):
        selected = _mapping(section)
        lines.extend([f"## {selected.get('title')}", ""])
        for paragraph in _sequence(selected.get("paragraphs")):
            lines.extend([_reader_text(paragraph), ""])
    action_mode = action.get("mode")
    if action_mode == "observation_only":
        questions = [
            _reader_text(item)
            for item in _sequence(action.get("questions_to_resolve"))
            if str(item).strip()
        ]
        lines.extend(
            [
                "## 后续需要确认",
                "",
                "本期先核对已发生的变化，未生成交易动作或目标仓位。"
                + (
                    questions[0]
                    if questions
                    else "如需进一步形成行动方案，需要先明确投资期限、可承受损失和仓位边界。"
                ),
            ]
        )
    elif action_mode == "historical_snapshot" or (
        action_mode is None and action.get("action")
    ):
        lines.extend(
            [
                "## 历史建议快照",
                "",
                f"- **当时的判断：** {_action_label(action.get('action'))}",
                f"- **历史仓位：** {_reader_text(action.get('target_position_note'))}",
                f"- **原记录期限：** {_reader_text(action.get('time_horizon'))}",
                "",
                "该内容只用于复盘，不是当前有效建议。",
            ]
        )
    else:
        lines.extend(
            [
                "## 下一步行动",
                "",
                f"- **建议：** {_action_label(action.get('action'))}",
                f"- **仓位：** {_reader_text(action.get('target_position_note'))}",
                f"- **期限：** {_reader_text(action.get('time_horizon'))}",
                f"- **用户风险预算：** {_reader_text(action.get('user_risk_budget'))}",
                "",
                "这项建议仅供决策参考，不会自动执行。",
            ]
        )
    reader_risks = _reader_risk_summary(reader, action_mode=action_mode)
    risks = reader_risks["major_risks"]
    invalidation = reader_risks["invalidation_conditions"]
    missing = reader_risks["missing_inputs"]
    if risks or invalidation or missing:
        lines.extend(["", "## 需要继续关注", ""])
        for item in risks:
            lines.append(f"- 风险：{item}")
        for item in invalidation:
            lines.append(f"- 出现以下变化时应重新判断：{item}")
        if missing:
            lines.append(f"- 尚待核实：{missing[0]}")
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
            *(
                [f"- 内部建议依据：`{action.get('decision_basis')}`"]
                if action.get("decision_basis")
                else []
            ),
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
