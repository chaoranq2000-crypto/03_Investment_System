from __future__ import annotations

import re
from collections import Counter
from typing import Any, Mapping


_GENERIC_PATTERNS = [
    r"行业需求(?:持续)?增长.*公司(?:有望|可能)受益",
    r"竞争加剧.*毛利率",
    r"后续(?:需要|需)观察",
    r"收入增长.*利润增长",
]
_ACTION_PATTERNS = [
    r"(?:买入|卖出|加仓|减仓|仓位|目标价|止损|强烈推荐)",
    r"(?:建议|应当).{0,6}(?:买入|卖出|加仓|减仓)",
]


def run_semantic_gate(payload: Mapping[str, Any], config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    config = dict(config or {})
    min_metrics = int(config.get("minimum_company_specific_metrics_per_core_section", 1))
    min_model_links = int(config.get("minimum_model_links_per_economic_section", 1))
    max_proxy_share = float(config.get("maximum_proxy_revenue_share", 0.45))
    min_eligible_peers = int(config.get("minimum_eligible_peers_for_peer_multiples", 3))
    core_sections = set(config.get("core_sections", ["financials", "business", "industry", "forecast", "valuation", "risks"]))
    economic_sections = set(config.get("economic_sections", ["business", "forecast", "valuation"]))

    issues: list[dict[str, Any]] = []
    insight_owners: dict[str, str] = {}
    section_scores: list[dict[str, Any]] = []
    section_lengths: dict[str, int] = {}

    for section in payload.get("sections", []):
        section_id = str(section.get("section_id", ""))
        text = str(section.get("text", ""))
        normalized_text = _normalize(text)
        section_lengths[section_id] = len(re.findall(r"[\u4e00-\u9fff]", text))
        metrics = [str(x).strip() for x in section.get("company_specific_metrics", []) if str(x).strip()]
        model_links = [str(x).strip() for x in section.get("model_links", []) if str(x).strip()]
        insights = [str(x).strip() for x in section.get("insights", []) if str(x).strip()]
        watchpoints = section.get("watchpoints", [])
        local_issues: list[str] = []

        if section_id in core_sections and len(metrics) < min_metrics:
            issues.append(_issue("SECTION_GENERIC", "high", section_id, "core section lacks company-specific metrics"))
            local_issues.append("company_specific_metrics")
        if section_id in economic_sections and len(model_links) < min_model_links:
            issues.append(_issue("SECTION_NO_MODEL_LINK", "high", section_id, "economic section lacks a driver/model link"))
            local_issues.append("model_links")
        generic_hits = sum(bool(re.search(pattern, normalized_text)) for pattern in _GENERIC_PATTERNS)
        if generic_hits >= 2 and not metrics:
            issues.append(_issue("SECTION_GENERIC", "high", section_id, "generic causal language without issuer-specific evidence"))
            local_issues.append("generic_language")
        for insight in insights:
            key = _normalize(insight)
            if not key:
                continue
            if key in insight_owners and insight_owners[key] != section_id:
                issues.append(_issue("INSIGHT_DUPLICATED", "medium", section_id, f"same insight already used in {insight_owners[key]}"))
                local_issues.append("duplicate_insight")
            else:
                insight_owners[key] = section_id
        if section_id in core_sections:
            for idx, watchpoint in enumerate(watchpoints):
                missing = [name for name in ("metric", "trigger", "timeframe", "disconfirming_condition") if not watchpoint.get(name)]
                if missing:
                    issues.append(_issue("WATCHPOINT_NOT_FALSIFIABLE", "high", section_id, f"watchpoints[{idx}] missing {','.join(missing)}"))
                    local_issues.append("watchpoint")
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in _ACTION_PATTERNS):
            issues.append(_issue("DIRECT_TRADING_LANGUAGE", "critical", section_id, "direct action/target language detected"))
            local_issues.append("direct_trading_language")
        section_scores.append(
            {
                "section_id": section_id,
                "company_specific_metric_count": len(metrics),
                "model_link_count": len(model_links),
                "insight_count": len(insights),
                "issue_count": len(local_issues),
                "pass": not local_issues,
            }
        )

    model_summary = payload.get("model_summary", {})
    proxy_share = float(model_summary.get("proxy_revenue_share", 0.0) or 0.0)
    if proxy_share > max_proxy_share:
        issues.append(_issue("PROXY_REVENUE_SHARE_EXCEEDED", "high", "model", f"{proxy_share:.4f} > {max_proxy_share:.4f}"))

    peer_summary = payload.get("peer_summary", {})
    if peer_summary.get("peer_multiples_used") and int(peer_summary.get("eligible_count", 0)) < min_eligible_peers:
        issues.append(_issue("PEER_SET_INELIGIBLE", "critical", "valuation", "peer multiples used without enough qualified peers"))

    materiality = payload.get("section_materiality", {})
    if materiality and section_lengths:
        high_sections = [sid for sid, level in materiality.items() if level == "high" and sid in section_lengths]
        low_sections = [sid for sid, level in materiality.items() if level == "low" and sid in section_lengths]
        if high_sections and low_sections:
            high_avg = sum(section_lengths[sid] for sid in high_sections) / len(high_sections)
            low_avg = sum(section_lengths[sid] for sid in low_sections) / len(low_sections)
            if high_avg <= low_avg * float(config.get("minimum_high_to_low_length_ratio", 1.25)):
                issues.append(_issue("REPORT_EMPHASIS_FLAT", "medium", "report", "high-materiality sections are not meaningfully emphasized"))

    duplicates = _repeated_sentence_count(payload)
    if duplicates > int(config.get("maximum_repeated_sentences", 1)):
        issues.append(_issue("REPORT_REPETITION_EXCESSIVE", "medium", "report", f"repeated normalized sentences={duplicates}"))

    critical = sum(i["severity"] == "critical" for i in issues)
    high = sum(i["severity"] == "high" for i in issues)
    decision = "candidate_ready" if critical == 0 and high == 0 else "needs_research_backflow"
    return {
        "schema_version": 1,
        "artifact_type": "r5_bundle11r_semantic_quality_scorecard",
        "decision": decision,
        "critical_blockers": critical,
        "high_blockers": high,
        "medium_warnings": sum(i["severity"] == "medium" for i in issues),
        "section_scores": section_scores,
        "issues": issues,
        "fixed_boundaries": {"sample_quality_allowed": False, "p2_allowed": False},
    }


def _normalize(text: str) -> str:
    text = re.sub(r"\s+", "", text.lower())
    text = re.sub(r"[，。；：、,.!?！？;:\-—()（）\[\]【】]", "", text)
    return text


def _repeated_sentence_count(payload: Mapping[str, Any]) -> int:
    sentences: list[str] = []
    for section in payload.get("sections", []):
        text = str(section.get("text", ""))
        for sentence in re.split(r"[。！？!?]", text):
            normalized = _normalize(sentence)
            if len(normalized) >= 16:
                sentences.append(normalized)
    counts = Counter(sentences)
    return sum(count - 1 for count in counts.values() if count > 1)


def _issue(code: str, severity: str, scope: str, message: str) -> dict[str, Any]:
    return {"code": code, "severity": severity, "scope": scope, "message": message}
