from __future__ import annotations

from copy import deepcopy

MODEL_ID = "model_gen_r5_bundle9r_1cd42241e6a38fb3"
MODEL_SHA = "1cd42241e6a38fb3fc24e6ceb5be1261dbad6e1ee860393b44932282bacd54cc"
EVIDENCE_ID = "evidence_gen_r5_bundle8r_231a51f4673156df"


def binding():
    return {
        "expected_model_generation_id": MODEL_ID,
        "expected_model_aggregate_sha256": MODEL_SHA,
        "expected_evidence_generation_id": EVIDENCE_ID,
        "required_downstream_consumer": "R5_BUNDLE_10R_READER_REBUILD",
    }


def reader_contract():
    return {
        "required_sections": [
            "executive_summary", "company_context_and_scope", "financial_quality",
            "segment_economics", "industry_and_competition", "forecast_and_scenarios",
            "valuation_and_market_implied_expectations", "market_technical_sentiment_and_events",
            "risks_and_falsification", "conclusion_and_watchlist",
        ],
        "core_sections": [
            "financial_quality", "segment_economics", "industry_and_competition",
            "forecast_and_scenarios", "valuation_and_market_implied_expectations",
            "risks_and_falsification", "conclusion_and_watchlist",
        ],
        "required_analysis_fields": [
            "judgment", "facts", "causal_mechanism", "economic_implications",
            "counterevidence", "uncertainty", "watchpoints", "references",
        ],
        "minimums": {
            "facts_per_section": 2, "causal_mechanisms_per_section": 1,
            "implications_per_section": 1, "counterevidence_per_section": 1,
            "uncertainties_per_section": 1, "watchpoints_per_section": 2,
            "quantified_watchpoints_per_core_section": 1,
        },
    }


def quality_contract(min_han=1200):
    return {
        "candidate_threshold": 82,
        "research_draft_threshold": 45,
        "candidate_requirements": {
            "min_total_han_chars": min_han,
            "min_independent_underlying_sources": 4,
            "required_source_categories": ["issuer", "industry", "peer", "market"],
            "min_peer_sources": 3,
        },
        "dimensions": {
            "evidence_integrity": 20, "coverage_completeness": 15,
            "analytical_synthesis": 20, "forecast_and_valuation": 15,
            "narrative_and_readability": 15, "presentation_hygiene": 10,
            "risks_and_watch_conditions": 5,
        },
    }


def _long(label):
    return (
        f"{label}显示经营变量与财务结果之间存在可验证的传导关系。"
        "本段同时说明变化方向、原因、经济影响与反向证据，避免只复述数字。"
        "结论必须随后续披露更新，不能把估计写成发行人事实。"
    )


def _section(section_id, title, refs):
    return {
        "section_id": section_id,
        "title": title,
        "judgment": _long("本节判断"),
        "judgment_refs": refs,
        "facts": [
            {"text": _long("事实一"), "refs": refs[:1]},
            {"text": _long("事实二"), "refs": refs[-1:]},
        ],
        "causal_mechanism": [{"text": _long("因果机制"), "refs": refs}],
        "economic_implications": [{"text": _long("经济含义"), "refs": refs}],
        "counterevidence": [{"text": _long("反向证据"), "refs": refs}],
        "uncertainty": [{"text": _long("不确定性"), "refs": refs}],
        "watchpoints": [
            {"metric": "指标甲", "trigger": "同比变化超过10%", "horizon": "下一季度", "direction": "验证主判断", "refs": refs},
            {"metric": "指标乙", "trigger": "连续2个季度低于基准", "horizon": "未来六个月", "direction": "触发判断降级", "refs": refs},
        ],
        "references": refs,
    }


def payload():
    section_specs = [
        ("executive_summary", "核心矛盾", ["E1", "E2"]),
        ("company_context_and_scope", "公司与研究边界", ["E1", "E3"]),
        ("financial_quality", "财务质量", ["E1", "E2"]),
        ("segment_economics", "分部经济性", ["E1", "E3"]),
        ("industry_and_competition", "行业与竞争", ["E4", "E5"]),
        ("forecast_and_scenarios", "预测与情景", ["E1", "E6"]),
        ("valuation_and_market_implied_expectations", "估值与市场隐含预期", ["E7", "E8", "E9"]),
        ("market_technical_sentiment_and_events", "技术、情绪与事件", ["E7", "E10"]),
        ("risks_and_falsification", "风险与证伪", ["E2", "E5"]),
        ("conclusion_and_watchlist", "结论与跟踪", ["E1", "E6", "E10"]),
    ]
    sections = [_section(*spec) for spec in section_specs]
    market = next(x for x in sections if x["section_id"] == "market_technical_sentiment_and_events")
    market["technical_context"] = {"status": "reviewed", "as_of_date": "2026-07-13", "series_start": "2025-07-13"}
    market["sentiment_context"] = {"status": "reviewed", "as_of_date": "2026-07-13", "layers": ["macro", "industry", "company"]}
    market["events"] = [{
        "date": "2026-08-20", "status": "future", "impact_path": "披露更新影响预测锚点",
        "verification_metric": "毛利率与经营现金流", "counterevidence_condition": "低于基准且现金流继续转弱",
        "refs": ["E10"],
    }]
    catalog = [
        {"display_reference_id": "E1", "underlying_source_id": "issuer_annual", "source_title": "年度报告", "source_category": "issuer", "independent": False},
        {"display_reference_id": "E2", "underlying_source_id": "issuer_quarter", "source_title": "季度报告", "source_category": "issuer", "independent": False},
        {"display_reference_id": "E3", "underlying_source_id": "issuer_ir", "source_title": "投资者关系记录", "source_category": "issuer", "independent": False},
        {"display_reference_id": "E4", "underlying_source_id": "industry_one", "source_title": "行业报告", "source_category": "industry", "independent": True},
        {"display_reference_id": "E5", "underlying_source_id": "industry_two", "source_title": "政策与行业资料", "source_category": "industry", "independent": True},
        {"display_reference_id": "E6", "underlying_source_id": "consensus_one", "source_title": "一致预期", "source_category": "consensus", "independent": True},
        {"display_reference_id": "E7", "underlying_source_id": "market_one", "source_title": "市场快照", "source_category": "market", "independent": True},
        {"display_reference_id": "E8", "underlying_source_id": "peer_one", "source_title": "同业甲报告", "source_category": "peer", "independent": True},
        {"display_reference_id": "E9", "underlying_source_id": "peer_two", "source_title": "同业乙报告", "source_category": "peer", "independent": True},
        {"display_reference_id": "E10", "underlying_source_id": "peer_three", "source_title": "同业丙与事件资料", "source_category": "peer", "independent": True},
    ]
    return {
        "workflow_id": "fixture_workflow",
        "company": {"name": "示例制造公司", "ticker": "000001.SZ", "as_of_date": "2026-07-13"},
        "report_level": "研究候选稿",
        "human_review_status": "pending",
        "input_model_generation_id": MODEL_ID,
        "input_model_aggregate_sha256": MODEL_SHA,
        "sections": sections,
        "reference_catalog": catalog,
        "claims": [
            {"claim_id": "c1", "topic": "consensus", "claim_type": "analyst_view", "refs": ["E6"]},
            {"claim_id": "c2", "topic": "liquid_cooling_standalone_economics", "claim_type": "unknown", "additivity": "non_additive", "refs": ["E3"]},
            {"claim_id": "c3", "topic": "peer_comparison", "claim_type": "analytical_view", "peer_confidence": "low", "ranking_performed": False, "refs": ["E8", "E9", "E10"]},
        ],
    }


def model_lock():
    return {
        "generation_id": MODEL_ID,
        "aggregate_sha256": MODEL_SHA,
        "input_evidence_generation_id": EVIDENCE_ID,
        "artifact_count": 1,
        "missing_artifact_count": 0,
        "artifacts": [{"path": "model.yaml", "sha256": "0" * 64}],
        "downstream_consumers": ["R5_BUNDLE_10R_READER_REBUILD"],
    }
