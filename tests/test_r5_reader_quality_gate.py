from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from scripts.run_r5_reader_quality_gate import evaluate


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def load(name: str):
    return yaml.safe_load((RUN / name).read_text(encoding="utf-8"))


@pytest.fixture
def current_reader_inputs():
    return (
        (RUN / "R5_stock_research_report_reader_v2.md").read_text(encoding="utf-8"),
        load("R5_stock_research_report_traceability_v2.yaml"),
        load("R5_bundle6_forecast_bridge.yaml"),
        load("R5_bundle6_valuation_reasoning_pack.yaml"),
        yaml.safe_load((ROOT / "config/r5_reader_quality_rubric.yaml").read_text(encoding="utf-8")),
        yaml.safe_load((ROOT / "benchmarks/r5_section_density_targets.yaml").read_text(encoding="utf-8")),
        yaml.safe_load((ROOT / "benchmarks/r5_report_quality_rubric.yaml").read_text(encoding="utf-8")),
    )


def test_current_reader_v2_is_rebaselined_as_research_draft(current_reader_inputs):
    result = evaluate(*current_reader_inputs)

    assert result["decision"] == "rejected"
    assert result["quality_band"] == "research_draft"
    assert 40 <= result["score"] <= 60
    assert result["truthfulness_status"] == "pass"
    assert result["human_review_status"] == "not_ready"
    assert not result["sample_quality_report_allowed"] and not result["p2_allowed"]

    codes = {item["code"] for item in result["candidate_blockers"]}
    assert "independent_industry_evidence_missing" in codes
    assert "forecast_not_bottom_up_or_segment_driven" in codes
    assert "valuation_lacks_reverse_or_scenario_value_range" in codes
    assert "technical_analysis_inputs_missing" in codes
    assert "sentiment_analysis_inputs_missing" in codes


def test_nine_headings_plus_nine_shallow_sentences_fails_closed(current_reader_inputs):
    _, appendix, bridge, valuation, rubric, density, benchmark = current_reader_inputs
    headings = [
        "## 一、核心研究观点",
        "## 二、公司背景与研究边界",
        "## 三、财务历史与现金流质量",
        "## 四、业务拆分与细分经济性",
        "## 五、行业结构与竞争",
        "## 六、预测与情景",
        "## 七、估值与市场预期",
        "## 八、有日期的公司事件",
        "## 九、风险、反证与观察条件",
        "## 十、研究结论与跟踪清单",
    ]
    thin = "# 极薄报告\n\n" + "\n\n".join(f"{heading}\n\n本节有一个结论，但没有展开分析。[E1]" for heading in headings)

    result = evaluate(thin, appendix, bridge, valuation, rubric, density, benchmark)

    assert result["decision"] == "rejected"
    assert result["quality_band"] in {"source_gapped_draft", "research_draft"}
    codes = {item["code"] for item in result["candidate_blockers"]}
    assert "extremely_thin_report" in codes
    assert "insufficient_analytical_unit_coverage" in codes
    assert result["score"] < result["threshold"]


def _record(ref: str, source_id: str, summary: str) -> dict:
    return {
        "display_reference_id": ref,
        "claim_type": "fact_and_inference",
        "claim_summary": summary,
        "raw_evidence_ids": [source_id],
        "source_path": f"reviewed/{source_id}.yaml",
        "method": "direct_review",
        "confidence": "high",
        "limitation": "口径与边界已在正文说明",
        "reviewer_state": "accepted",
    }


def _high_quality_fixture(rubric: dict):
    refs = [f"E{i}" for i in range(1, 16)]
    sources = [
        "ev_annual_report_company",
        "ev_quarterly_report_company",
        "ev_interim_report_company",
        "ev_industry_association_demand_supply",
        "ev_peer_alpha_annual_report",
        "ev_peer_beta_annual_report",
        "ev_peer_gamma_annual_report",
        "ev_company_operating_ir_order_capacity",
        "ev_structured_market_data_ohlcv",
        "ev_consensus_broker_forecast",
        "ev_industry_policy_technology",
        "ev_peer_operating_margin_dataset",
        "ev_company_operating_customer_project",
        "ev_market_sentiment_fund_flow",
        "ev_future_event_exchange_calendar",
    ]
    appendix = {
        "records": [_record(ref, source, f"独立审阅材料{idx}") for idx, (ref, source) in enumerate(zip(refs, sources), 1)]
    }

    report = """# 示例公司读者型研究报告

## 一、核心研究观点

核心判断是，公司收入扩张正在从单一产品放量转向产品结构与客户结构共同改善，但利润和现金流仍是决定估值能否兑现的关键约束。[E1][E4][E8] 过去三年收入、毛利率和经营现金流呈现不同方向，意味着市场争议并非有没有需求，而是需求能否通过订单、交付和价格传导形成可持续盈利。若后续两个季度毛利率、回款和订单同时改善，当前判断获得支持；但若收入增长继续伴随现金流恶化，应撤销利润修复假设并降低结论置信度。[E2][E3][E13]

## 二、公司背景与研究边界

公司覆盖设备、系统和服务三类业务，核心研究边界是只把已披露的产品、客户和项目作为事实，不把行业增长直接等同于公司收入。[E1][E8] 这一边界说明研究需要区分公司总收入、分业务收入与新产品收入；尚未披露的独立利润贡献只能作为待验证假设，不能用市场规模替代公司事实。与此同时，公司在多个环节具备交付能力，但客户集中、扩产节奏和服务成本仍构成反证，因此后续关注订单转化、产能利用率与售后费用。[E8][E13]

## 三、财务历史与现金流质量

2023—2025年收入从40亿元增长至70亿元，复合增速超过30%，归母净利润从4亿元增长至7亿元，但经营现金流从6亿元降至3亿元，收入增长与现金转换出现背离。[E1][E2][E3] 同比与环比拆分显示，增长主要由销量、产品升级和新客户共同驱动，而应收账款与存货增加导致现金回收慢于利润确认；这会抬高营运资金占用并降低资本回报。2026年一季度毛利率回落、费用率上升，意味着全年不能机械年化收入增速。[E2][E3][E8] 然而，若合同负债、回款率和库存周转在未来两个季度改善，现金流压力可能只是交付节奏造成；若应收继续快于收入增长，则利润质量假设不成立。后续验证毛利率、费用率、应收周转、存货周转、合同负债和经营现金流，并给出季度阈值。[E3][E13]

## 四、业务拆分与细分经济性

业务拆分显示，设备业务收入35亿元、系统业务25亿元、服务业务10亿元，收入占比分别为50%、36%和14%；三项毛利率分别为24%、31%和42%。[E1][E8][E13] 设备业务增长来自销量和客户扩张，系统业务由项目单价和产品结构驱动，服务业务依赖存量装机与续约率，因此三条业务线的收入公式和利润池不同。系统与服务毛利率较高，若收入占比提升，将带动公司毛利率和现金流改善；但系统交付周期长、服务人员投入前置，可能抵消结构升级收益。[E8][E12][E13] 产能、订单、客户和价格证据表明未来增长仍有基础，不过若在手订单转化率低于70%或新增产能利用率低于60%，分业务预测需要下调。后续跟踪销量、单位价值、订单转化率、产能利用率、客户集中度和分业务毛利率。[E8][E13]

## 五、行业结构与竞争

独立行业资料显示，需求由算力密度、能效要求和设备更新驱动，未来三年需求保持增长；供给端则受到核心部件、认证周期和服务网络约束。[E4][E10][E11] 竞争格局中，前三家公司在规模、毛利率和客户结构上差异明显，公司位置处于第二梯队上沿，优势是产品链和交付能力，短板是海外客户占比与软件能力。[E5][E6][E7] 需求增长通过订单数量、项目单价和产品结构传导至收入与毛利，但价格竞争和同业扩产会压低单位盈利，因此行业景气并不自动等于公司利润增长。[E4][E12] 若行业新增供给快于需求、同业毛利率连续下降或公司份额停滞，竞争优势判断应下调；后续验证行业订单、供给增量、价格、同业份额、客户认证和公司中标率。[E4][E11][E12]

## 六、预测与情景

基准情景按设备销量×单价、系统项目量×单位价值、服务装机量×续约收入分别预测三条业务线，并将销售、管理、研发、财务费用、所得税和少数股东损益单独桥接。[E8][E10][E13] 2026E—2028E收入分别为85亿元、105亿元和128亿元，归母净利润分别为8亿元、11亿元和15亿元；收入增长由订单转化和产品结构驱动，利润增长还取决于毛利率与费用率改善。[E2][E8][E10] 上行情景假设订单转化更快、系统占比提升，下行情景假设价格竞争和产能利用率偏低；敏感性显示毛利率每变化1个百分点，对净利润的影响大于收入增速变化。与一致预期相比，基准利润略低，原因是对回款、服务成本和研发投入更保守。[E10][E13] 若订单转化率、毛利率或经营现金流连续两个季度低于阈值，预测应下调；若高毛利业务占比和回款同时超预期，才可上调。后续按季度验证销量、单价、项目量、续约率、费用率、税率和现金流。[E8][E10][E13]

## 七、估值与市场预期

截至2026-07-12，当前市值对应较高的远期市盈率和市销率，核心判断是市场已经隐含收入持续增长、净利率恢复与高毛利业务占比提升。[E9][E10][E12] 同业比较选择三家业务和盈利结构可比公司，并按收入增速、毛利率、现金流和研发强度解释溢价或折价，而不是只比较市盈率。[E5][E6][E7] 反向估值显示，当前市值隐含2028年收入需要达到130亿元、净利率需要达到12%，或新业务需要贡献约6亿元利润才能被支撑；基准、上行和下行情景价值区间分别对应不同经营假设。[E9][E10][E12] 然而，若现金流不改善、同业估值下移或新业务利润低于反推要求，估值压力会放大。后续观察收入、净利率、自由现金流、同业倍数和市场隐含利润，并在同一日期和分母口径下复核。[E9][E10][E12]

## 八、有日期的公司事件

公司将于2026-08-20披露半年报，并计划在2026-09-15举行投资者交流；两个未来事件的影响路径是订单、毛利率和现金流数据更新后，市场会重新评估利润修复速度。[E13][E15] 半年报验证指标包括分业务收入、综合毛利率、经营现金流、应收和存货；交流会验证订单、产能、客户和价格趋势。[E8][E15] 若毛利率高于28%、经营现金流转正且订单转化率改善，基准情景获得支持；但若利润率继续下降或应收快于收入增长，应视为反证并触发预测降级。后续还要关注2026-10-25三季报窗口及同业披露，避免只依据单一事件形成结论。[E12][E15]

## 九、风险、反证与观察条件

第一，需求增长可能被价格竞争抵消，若系统业务毛利率低于28%，利润池判断需要下调。[E4][E12][E13] 第二，订单可能无法按期转化，若未来两个季度转化率低于70%，收入预测失效。第三，扩产可能造成利用率不足，若产能利用率低于60%，折旧和费用会压低利润。第四，回款和库存可能继续恶化，若经营现金流连续为负，盈利质量反证成立。[E2][E3][E8] 反向证据也必须保留：若高毛利业务占比、回款率和客户分散度同步改善，当前谨慎假设应被上调。所有风险均绑定指标、阈值和观察期限，不能只列风险名称。[E8][E13]

## 十、研究结论与跟踪清单

研究结论是，公司具备需求增长和产品结构升级机会，但估值兑现依赖分业务利润与现金流同步改善。[E1][E9][E13] 基准假设包括订单持续增长、系统与服务占比提升、费用率受控和回款改善；然而，若订单转化率低于70%、毛利率低于28%或经营现金流连续两个季度为负，核心判断不成立并触发降级。[E2][E8][E13] 跟踪清单依次验证行业需求与供给、分业务销量和单价、订单和产能、毛利率与费用率、现金流、同业估值以及未来事件。任何结论只在证据和假设范围内有效，不构成交易指令。[E4][E10][E15]
"""

    extensions = {
        "## 一、核心研究观点": "进一步看，订单质量而非单纯订单金额决定利润兑现，客户集中度、项目验收周期和服务成本会改变现金流节奏。[E8][E13] 因此研究判断还要与同业毛利率、自由现金流和研发效率交叉验证，任何单项指标改善都不足以单独确认拐点。",
        "## 二、公司背景与研究边界": "公司身份、业务范围和会计披露口径已经明确，但新产品可能横跨多个分部，不能把产品宣传口径当作分部会计口径。[E1][E8] 后续若公司提供客户、订单、产能和分产品利润证据，研究边界才可扩展；在此之前，所有估算都保留置信区间和失效条件。",
        "## 三、财务历史与现金流质量": "利润表之外，资产负债表显示应收、存货和固定资产的变化速度快于净利润，说明增长需要更多营运资金与资本开支。[E2][E3][E8] 其因果机制是订单确认、采购备货、验收和回款存在时间差，短期会压低经营现金流并抬高融资需求；如果回款周期缩短、库存周转恢复且资本开支强度下降，现金转换率才可能回升。反之，若净利润增长而自由现金流持续为负，应把利润质量降级。还应比较净现比、自由现金流率和资本回报率的历史分位，避免单季波动掩盖长期趋势。[E2][E3]",
        "## 四、业务拆分与细分经济性": "核心判断还要落到单位经济性：设备业务观察单位售价、材料成本和良率，系统业务观察项目单价、交付周期和验收率，服务业务观察续约率、人均产出和客户留存。[E8][E12][E13] 价格上涨只有在销量与客户留存不受损时才会改善毛利；扩产只有在利用率超过盈亏平衡点时才会增厚利润。若客户集中度上升、质保费用增加或系统验收延期，利润池可能从高毛利业务转回低毛利设备，因此需要季度滚动验证。分业务资本开支与折旧也要单独跟踪，因为重资产扩张会改变盈亏平衡点和现金回收周期。[E8][E13]",
        "## 五、行业结构与竞争": "供需之外，技术路线和认证标准决定竞争门槛。独立政策与技术资料显示，能效、可靠性和全生命周期服务要求提高，会延长客户认证并强化头部厂商优势。[E10][E11][E12] 但标准开放、核心部件通用化和新进入者扩产也可能降低壁垒，导致价格与服务竞争加剧。公司能否获得溢价，最终要由中标率、单位价格、故障率、交付周期和客户复购证明；若这些指标未优于同业，产品链完整不能自动转化为市场份额。进一步比较三家同业的研发投入、海外收入、服务网络和现金流，可以判断竞争优势来自规模、技术还是客户关系；若公司只在收入增速领先而利润率、回款和复购落后，则行业位置需要重新评估。[E5][E6][E7][E12]",
        "## 六、预测与情景": "模型同时建立2025A至2026E利润桥，把销量、单价、业务组合、材料成本、人工成本、折旧、销售费用、管理费用、研发费用、财务费用、税率和少数股东损益逐项勾稽。[E2][E8][E10] 每个假设对应证据来源、置信度和更新频率，情景差异不代表概率。若实际分业务收入与模型偏差超过10%、毛利率偏差超过2个百分点或现金流偏差超过20%，模型应重估而不是机械滚动。",
        "## 七、估值与市场预期": "估值争议还可通过市销率—净利率转换检验：相同市销率下，净利率越低，所需远期市盈率越高；相同市盈率下，增长持续期越短，合理市值越低。[E9][E10][E12] 基准价值区间使用分业务利润与可比倍数，上行情景要求高毛利业务加速、下行情景反映价格竞争与现金流折价。若无风险利率、同业估值或资本开支发生显著变化，估值区间也应同步调整。",
        "## 八、有日期的公司事件": "截至2026-07-12，技术序列显示MA5高于MA20但成交量未明显放大，前高构成阻力位、长期均线构成支撑位；这只描述趋势状态，不构成操作指令。[E9][E14] 宏观情绪受利率与风险偏好影响，行业情绪取决于算力资本开支和液冷渗透，公司情绪则由订单、业绩与估值分歧共同决定。[E10][E14] 若事件后价格上涨但盈利预期和资金流没有改善，应视为情绪脉冲而非基本面确认。",
        "## 九、风险、反证与观察条件": "此外，技术迭代可能使现有产品组合失去优势，供应链波动可能抬高材料成本，海外拓展可能增加认证与汇率风险。[E4][E10][E13] 每项风险都需要对照同业和历史分位：当故障率、质保费用、客户集中度或资本开支强度超过阈值时，模型假设应被下调；当这些指标改善且订单质量提升时，反证才可能解除。",
        "## 十、研究结论与跟踪清单": "研究结论的置信度为中等，原因是财务、分业务、行业、同业、市场和事件证据已经形成闭环，但未来结果仍受价格、交付和现金流影响。[E4][E10][E12] 结论的证伪条件明确：若行业需求不增长、公司份额下降、分业务毛利率低于阈值或自由现金流持续为负，应撤销成长假设；若全部关键指标连续两个季度改善，再提高置信度。",
    }
    ordered_headings = list(extensions)
    for index, heading in enumerate(ordered_headings):
        extension = extensions[heading]
        if index + 1 < len(ordered_headings):
            next_heading = ordered_headings[index + 1]
            report = report.replace(next_heading, extension + "\n\n" + next_heading, 1)
        else:
            report = report.rstrip() + "\n\n" + extension + "\n"

    bridge = {
        "driver_assumptions": [
            {"driver": "机房_segment_volume", "values": {"2026E": 1}},
            {"driver": "机柜_segment_unit_value", "values": {"2026E": 1}},
            {"driver": "液冷_segment_mix", "values": {"2026E": 1}},
            {"driver": "sales_expense", "values": {"2026E": 1}},
            {"driver": "admin_expense", "values": {"2026E": 1}},
            {"driver": "r&d_expense", "values": {"2026E": 1}},
            {"driver": "finance_expense", "values": {"2026E": 1}},
            {"driver": "tax_rate", "values": {"2026E": 1}},
            {"driver": "minority_interest", "values": {"2026E": 1}},
        ],
        "base_case_bridge": [
            {"period": "2026E", "reconciliation_difference": 0.0},
            {"period": "2027E", "reconciliation_difference": 0.0},
            {"period": "2028E", "reconciliation_difference": 0.0},
        ],
        "scenarios": {"base_case": {}, "bull_case": {}, "bear_case": {}},
        "consensus_used": True,
    }
    valuation = {
        "as_of_date": "2026-07-12",
        "dated_snapshot": {"price_cny": 50, "denominator_control": "PE/PS use TTM denominators"},
        "method_eligibility": [
            {"method": "forward_pe", "status": "active", "reason": "盈利已形成分业务预测"},
            {"method": "reverse_valuation", "status": "active", "reason": "可反推收入与利润率"},
        ],
        "peer_matrix": [
            {"name": "同业甲", "confidence": "high"},
            {"name": "同业乙", "confidence": "medium"},
            {"name": "同业丙", "confidence": "high"},
        ],
        "scenario_context": [{"period": "2026E", "forward_pe": 30}],
        "reverse_valuation": {"implied_revenue": 130},
        "scenario_valuation": {"bear": 50, "base": 80, "bull": 110},
    }
    return report, appendix, bridge, valuation, rubric


def test_positive_scoring_has_a_real_passing_path(current_reader_inputs):
    rubric = current_reader_inputs[4]
    report, appendix, bridge, valuation, rubric = _high_quality_fixture(rubric)

    result = evaluate(report, appendix, bridge, valuation, rubric)

    assert result["decision"] == "candidate_ready_for_human_review"
    assert result["quality_band"] == "candidate_ready_for_human_review"
    assert result["score"] >= result["threshold"]
    assert result["critical_blocker_count"] == 0
    assert result["analysis_unit_coverage"]["complete"] >= 7
    assert result["human_review_status"] == "pending"


MUTATIONS = [
    (
        "unknown_reference",
        lambda r, a, b, v: (r + "\n未经支持。[E99]", a, b, v),
        "unresolved_traceability_reference",
    ),
    (
        "raw_evidence_id",
        lambda r, a, b, v: (r + "\nev_bad_123", a, b, v),
        "raw_internal_evidence_id_in_main_report",
    ),
    (
        "raw_path",
        lambda r, a, b, v: (r + "\nreports/workflow_runs/x/file.yaml", a, b, v),
        "raw_registry_or_workflow_path_in_main_report",
    ),
    (
        "todo_token",
        lambda r, a, b, v: (r + "\nTODO_SOURCE_REQUIRED", a, b, v),
        "raw_todo_missing_or_unreviewed_token_in_main_report",
    ),
    (
        "raw_currency",
        lambda r, a, b, v: (r + "\n收入123456789.123元", a, b, v),
        "unrounded_raw_cny_dump",
    ),
    (
        "missing_bridge",
        lambda r, a, b, v: (r, a, {**b, "base_case_bridge": []}, v),
        "forecast_without_driver_bridge",
    ),
    (
        "forecast_mismatch",
        lambda r, a, b, v: (
            r,
            a,
            {**b, "base_case_bridge": [{**b["base_case_bridge"][0], "reconciliation_difference": 0.1}]},
            v,
        ),
        "forecast_arithmetic_mismatch",
    ),
    (
        "valuation_date",
        lambda r, a, b, v: (r, a, b, {**v, "as_of_date": None}),
        "valuation_without_date_or_denominator_control",
    ),
    (
        "direct_advice",
        lambda r, a, b, v: (r + "\n建议仓位五成", a, b, v),
        "direct_buy_sell_hold_or_position_instruction",
    ),
    (
        "sample_fact",
        lambda r, a, b, v: (r + "\nSAMPLE_FACT", a, b, v),
        "sample_fact_used_as_evidence",
    ),
    (
        "fake_human_review",
        lambda r, a, b, v: (r + "\nhuman_review_status: accepted", a, b, v),
        "fabricated_human_review_acceptance",
    ),
    (
        "duplicate_appendix_ref",
        lambda r, a, b, v: (r, {**a, "records": a["records"] + [deepcopy(a["records"][0])]}, b, v),
        "unresolved_traceability_reference",
    ),
]


@pytest.mark.parametrize("name,mutate,expected", MUTATIONS, ids=[item[0] for item in MUTATIONS])
def test_truthfulness_negative_cases_still_fail_closed(current_reader_inputs, name, mutate, expected):
    report, appendix, bridge, valuation, rubric, density, benchmark = current_reader_inputs
    result = evaluate(*mutate(report, appendix, bridge, valuation), rubric, density, benchmark)

    assert result["decision"] == "rejected", name
    assert expected in {item["code"] for item in result["truthfulness_blockers"]}
    assert result["truthfulness_status"] == "fail"
