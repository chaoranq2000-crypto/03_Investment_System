from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml

from src.research.r5_analysis_engine import (
    build_analysis_pack,
    build_analysis_subpacks,
    validate_analysis_pack,
)
from src.research.r5_evidence_coverage import build_coverage_matrix
from tests.test_r5_bundle8_evidence_coverage import complete_catalog, load_config


def unit(
    analysis_id: str,
    section: str,
    *,
    judgment: str,
    trend: str,
    mechanism: str,
    impact: str,
    support: list[str],
    metrics: list[str],
    counter: list[str],
    watch_source: str,
    watch_metric: str,
    dependencies: list[str] | None = None,
) -> dict:
    return {
        "analysis_id": analysis_id,
        "section": section,
        "judgment": judgment,
        "trend": trend,
        "causal_mechanism": mechanism,
        "financial_impact": impact,
        "supporting_source_ids": support,
        "supporting_metric_ids": metrics,
        "counter_evidence_source_ids": counter,
        "confidence": "medium",
        "falsification_condition": "若后续两个连续报告期的核心验证指标与预期方向相反，则撤销该判断并返回证据层复核。",
        "watch_metrics": [
            {
                "metric_name": f"{section}验证指标",
                "metric_id": watch_metric,
                "expected_direction": "up",
                "threshold": "连续两个报告期达到预设改善区间",
                "review_frequency": "quarterly",
                "source_id": watch_source,
            }
        ],
        "dependencies": dependencies or [],
    }


def complete_inputs() -> dict:
    units = [
        unit(
            "AN-CORE",
            "core_thesis",
            judgment="公司的核心矛盾是收入增长能否通过产品结构和交付效率转化为可持续利润改善。",
            trend="最近三个报告期收入仍扩张，但毛利率与利润表现分化，经营质量尚未同步确认。",
            mechanism="若高价值产品占比、订单兑现和交付效率共同改善，收入增长才会经过毛利率和费用率传导至利润；否则规模扩张会继续稀释回报。",
            impact="该链条直接决定未来收入增速的含金量、净利润修复斜率以及经营现金流能否同步转正。",
            support=["ISS-ANNUAL", "ISS-IR"],
            metrics=[],
            counter=["RISK-1"],
            watch_source="ISS-IR",
            watch_metric="M-ORDER",
        ),
        unit(
            "AN-FIN",
            "financial_quality",
            judgment="财务质量判断不能只看收入增速，必须同时观察毛利率、经营现金流和应收周转的方向。",
            trend="年度与一季度数据表明利润弹性弱于收入弹性，现金流验证仍是识别增长质量的关键。",
            mechanism="收入确认若快于回款且毛利率承压，会通过营运资金占用和费用刚性压低现金利润，反之则能形成经营杠杆。",
            impact="现金流、净利润和资本回报之间的偏离将影响融资需求、估值可信度和后续投入能力。",
            support=["ISS-ANNUAL", "ISS-Q1"],
            metrics=["M-REV", "M-CFO"],
            counter=["RISK-1"],
            watch_source="ISS-Q1",
            watch_metric="M-CFO",
            dependencies=["AN-CORE"],
        ),
        unit(
            "AN-DRIVER",
            "business_driver",
            judgment="业务增长需要拆分为订单、价格、产品结构与产能利用率，而不能继续用公司总量增速替代。",
            trend="投资者关系和客户侧材料显示需求线索存在，但订单转化、价格和产能利用仍需逐季交叉验证。",
            mechanism="订单储备先转化为交付量，产品结构和价格决定单位收入，产能利用与良率再决定毛利率。",
            impact="驱动拆分将决定收入预测的可解释性，并揭示毛利改善来自真实产品升级还是短期费用波动。",
            support=["ISS-IR", "CUSTOMER-CHECK"],
            metrics=["M-ORDER", "M-CUSTOMER-DEMAND"],
            counter=["CUSTOMER-CHECK"],
            watch_source="ISS-IR",
            watch_metric="M-ORDER",
            dependencies=["AN-CORE"],
        ),
        unit(
            "AN-SEGMENT",
            "segment_economics",
            judgment="分业务经济性必须以披露口径为底座，并把未披露的液冷收入与利润贡献保留为显式缺口。",
            trend="现有披露能够支持主要产品线的收入和毛利变化，但客户、订单及独立液冷盈利口径仍不完整。",
            mechanism="各业务的收入规模、毛利率、客户结构和产能约束共同决定公司利润结构，缺失口径不能由产品线索直接推算。",
            impact="明确披露边界可避免高估新业务利润，同时为后续分业务预测提供可审计的基准和置信区间。",
            support=["ISS-ANNUAL", "ISS-IR"],
            metrics=["M-SEGMENT", "M-GM"],
            counter=["CUSTOMER-CHECK"],
            watch_source="ISS-ANNUAL",
            watch_metric="M-SEGMENT",
            dependencies=["AN-DRIVER"],
        ),
        unit(
            "AN-INDUSTRY",
            "industry_context",
            judgment="行业需求增长只有在供给扩张和价格竞争可控时，才会转化为公司可持续的收入与利润机会。",
            trend="独立需求数据指向应用渗透提升，但供给端扩产和价格压力也在同步变化，行业景气并非单向。",
            mechanism="需求增量先影响订单和利用率，供给与竞争再决定价格、份额和毛利率，因此两侧必须联合判断。",
            impact="行业供需的净结果会改变公司收入上限、毛利中枢以及资本开支回收周期，是预测的外生约束。",
            support=["IND-DEMAND-1", "IND-SUPPLY-1"],
            metrics=["M-IND-DEMAND", "M-IND-SUPPLY"],
            counter=["IND-SUPPLY-2"],
            watch_source="IND-DEMAND-1",
            watch_metric="M-IND-DEMAND",
            dependencies=["AN-CORE"],
        ),
        unit(
            "AN-PEER",
            "competitive_position",
            judgment="竞争优势必须由至少三家同业的收入结构、毛利率和业务暴露差异验证，而非只比较估值倍数。",
            trend="同业经营数据呈现不同的产品组合和盈利水平，说明简单横向倍数比较会掩盖可比性差异。",
            mechanism="产品结构、客户质量、规模和研发投入共同影响同业毛利与增长，只有经营口径可比后才能讨论溢价或折价。",
            impact="可信同业矩阵将约束公司利润率假设和后续估值区间，减少使用低可比样本造成的偏差。",
            support=["PEER-A", "PEER-B", "PEER-C"],
            metrics=["M-PEER-A-GM", "M-PEER-B-GM", "M-PEER-C-GM"],
            counter=["IND-SUPPLY-2"],
            watch_source="PEER-A",
            watch_metric="M-PEER-A-GM",
            dependencies=["AN-INDUSTRY"],
        ),
        unit(
            "AN-RISK",
            "risk_counterevidence",
            judgment="核心论点的最大风险是需求线索无法转化为订单和利润，或竞争加剧使收入增长继续伴随毛利承压。",
            trend="反向材料显示客户需求、行业供给和价格压力可能同时波动，当前证据不足以排除盈利修复延迟。",
            mechanism="需求不及预期会压低订单与利用率，竞争加剧会压低价格和毛利，两者叠加会削弱经营现金流。",
            impact="风险兑现将下调利润修复斜率并延后估值切换，因此必须用订单、毛利率和现金流阈值持续验证。",
            support=["RISK-1", "IND-DEMAND-2"],
            metrics=[],
            counter=["IND-DEMAND-2"],
            watch_source="RISK-1",
            watch_metric="M-RISK-TRIGGER",
            dependencies=["AN-CORE", "AN-INDUSTRY"],
        ),
    ]
    return {
        "schema_version": "v0.1",
        "workflow_id": "wf_test",
        "company_id": "cn_test",
        "analysis_date": "2026-07-12",
        "units": units,
    }


def build_complete_pack() -> tuple[dict, dict, dict, dict]:
    config = load_config()
    catalog = complete_catalog()
    matrix = build_coverage_matrix(
        config,
        catalog,
        workflow_id="wf_test",
        as_of_date="2026-07-12",
        source_catalog_path="fixture.yaml",
    )
    inputs = complete_inputs()
    pack = build_analysis_pack(
        config,
        catalog,
        matrix,
        inputs,
        source_catalog_path="fixture.yaml",
        coverage_matrix_path="matrix.yaml",
        analysis_inputs_path="inputs.yaml",
    )
    return config, catalog, matrix, pack


def test_complete_analysis_pack_passes() -> None:
    config, _, _, pack = build_complete_pack()
    result = validate_analysis_pack(pack, config)
    assert pack["summary"]["decision"] == "analysis_inputs_ready"
    assert pack["summary"]["complete_units"] == 7
    assert result["decision"] == "pass"


def test_generic_nonempty_text_is_blocked() -> None:
    config = load_config()
    catalog = complete_catalog()
    matrix = build_coverage_matrix(config, catalog, as_of_date="2026-07-12")
    inputs = complete_inputs()
    inputs["units"][0]["judgment"] = "公司具备竞争优势"
    pack = build_analysis_pack(config, catalog, matrix, inputs)
    unit = next(row for row in pack["analysis_units"] if row["analysis_id"] == "AN-CORE")
    assert unit["status"] == "blocked"
    assert any(item.startswith("generic_analysis_text") for item in unit["blockers"])


def test_unknown_evidence_reference_is_blocked() -> None:
    config = load_config()
    catalog = complete_catalog()
    matrix = build_coverage_matrix(config, catalog, as_of_date="2026-07-12")
    inputs = complete_inputs()
    inputs["units"][1]["supporting_source_ids"] = ["UNKNOWN-SOURCE"]
    pack = build_analysis_pack(config, catalog, matrix, inputs)
    unit = next(row for row in pack["analysis_units"] if row["analysis_id"] == "AN-FIN")
    assert any(item.startswith("unknown_supporting_source") for item in unit["blockers"])
    assert pack["summary"]["decision"] == "analysis_inputs_blocked"


def test_missing_counterevidence_blocks_unit() -> None:
    config = load_config()
    catalog = complete_catalog()
    matrix = build_coverage_matrix(config, catalog, as_of_date="2026-07-12")
    inputs = complete_inputs()
    inputs["units"][4]["counter_evidence_source_ids"] = []
    pack = build_analysis_pack(config, catalog, matrix, inputs)
    unit = next(row for row in pack["analysis_units"] if row["analysis_id"] == "AN-INDUSTRY")
    assert "counterevidence_source_below_minimum:AN-INDUSTRY" in unit["blockers"]


def test_duplicate_core_text_is_rejected() -> None:
    config = load_config()
    catalog = complete_catalog()
    matrix = build_coverage_matrix(config, catalog, as_of_date="2026-07-12")
    inputs = complete_inputs()
    inputs["units"][2]["judgment"] = inputs["units"][1]["judgment"]
    pack = build_analysis_pack(config, catalog, matrix, inputs)
    driver = next(row for row in pack["analysis_units"] if row["analysis_id"] == "AN-DRIVER")
    assert any(item.startswith("duplicate_core_text:judgment") for item in driver["blockers"])


def test_failed_evidence_coverage_blocks_dependent_units() -> None:
    config = load_config()
    catalog = complete_catalog()
    catalog["sources"] = [
        row for row in catalog["sources"] if not row["source_id"].startswith("IND-DEMAND")
    ]
    matrix = build_coverage_matrix(config, catalog, as_of_date="2026-07-12")
    inputs = complete_inputs()
    pack = build_analysis_pack(config, catalog, matrix, inputs)
    industry = next(row for row in pack["analysis_units"] if row["analysis_id"] == "AN-INDUSTRY")
    assert any(item.startswith("evidence_coverage_not_ready") for item in industry["blockers"])
    assert "evidence_coverage_gate_not_passed" in pack["summary"]["pack_blockers"]


def test_subpacks_only_include_complete_units() -> None:
    _, _, _, pack = build_complete_pack()
    subpacks = build_analysis_subpacks(pack)
    assert subpacks["thesis_tree"]["unit_count"] == 2
    assert subpacks["segment_economics"]["unit_count"] == 1
    assert all(
        unit["status"] == "complete"
        for artifact in subpacks.values()
        for unit in artifact["analysis_units"]
    )


def test_deep_validator_rebuilds_pack_from_inputs() -> None:
    config = load_config()
    catalog = complete_catalog()
    matrix = build_coverage_matrix(
        config,
        catalog,
        workflow_id="wf_test",
        as_of_date="2026-07-12",
        source_catalog_path="fixture.yaml",
    )
    inputs = complete_inputs()
    pack = build_analysis_pack(
        config,
        catalog,
        matrix,
        inputs,
        source_catalog_path="fixture.yaml",
        coverage_matrix_path="matrix.yaml",
        analysis_inputs_path="inputs.yaml",
    )
    pack["analysis_units"][0]["judgment"] = "被手工改写但仍保留 complete 状态"
    result = validate_analysis_pack(pack, config, catalog, matrix, inputs)
    assert result["decision"] == "fail"
    assert "analysis_units_not_reproducible" in result["errors"]


def test_standalone_validator_rejects_empty_complete_unit() -> None:
    config, _, _, pack = build_complete_pack()
    pack["analysis_units"][0]["causal_mechanism"] = ""
    result = validate_analysis_pack(pack, config)
    assert result["decision"] == "fail"
    assert any(
        item.startswith("complete_required_field_missing:AN-CORE:causal_mechanism")
        for item in result["errors"]
    )


def test_stale_counterevidence_cannot_support_complete_unit() -> None:
    config = load_config()
    catalog = complete_catalog()
    stale = {
        "source_id": "STALE-COUNTER",
        "underlying_source_id": "STALE-COUNTER",
        "title": "stale counter",
        "owner_type": "research_institution",
        "source_type": "test_fixture",
        "review_status": "reviewed",
        "as_of_date": "2020-01-01",
        "evidence_classes": ["risk_counterevidence"],
        "sections": ["risk_counterevidence"],
        "peer_ids": [],
        "counterevidence_for": ["all"],
        "claim_ids": ["CLAIM-STALE"],
        "metric_ids": ["M-STALE"],
        "source_path": "fixtures/stale.yaml",
    }
    catalog["sources"].append(stale)
    matrix = build_coverage_matrix(config, catalog, as_of_date="2026-07-12")
    inputs = complete_inputs()
    inputs["units"][0]["counter_evidence_source_ids"] = ["STALE-COUNTER"]
    pack = build_analysis_pack(config, catalog, matrix, inputs)
    core = next(row for row in pack["analysis_units"] if row["analysis_id"] == "AN-CORE")
    assert any(
        item.startswith("counterevidence_source_not_coverage_valid")
        for item in core["blockers"]
    )
