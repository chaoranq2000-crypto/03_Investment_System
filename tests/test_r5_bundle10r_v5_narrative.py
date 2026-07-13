from src.quality.r5_bundle10r_reader_gate import evaluate_reader_candidate
from src.report.r5_reader_writer_v4 import render_reader_report as render_v4
from src.report.r5_reader_writer_v5 import render_reader_report as render_v5
from src.report.r5_traceability_v4 import build_traceability_appendix
from tests.r5_bundle10r_test_fixtures import binding, payload, quality_contract, reader_contract


def _style_contract():
    contract = quality_contract(min_han=500)
    contract["narrative_quality"] = {
        "applies_to_report_schema_versions": ["v5"],
        "template_repetition": {
            "labels": ["本节判断", "关键事实", "因果机制", "经济含义", "反向证据", "不确定性边界", "后续验证与触发条件"],
            "min_section_ratio": 0.60,
            "min_sections": 3,
            "max_repeated_label_types": 2,
        },
        "process_audit_language": {
            "max_occurrences": 0,
            "patterns": {"quality_state": "(?:自动质量门|质量门|核心章节阻断|候选状态边界)"},
        },
        "opening_repetition": {
            "min_paragraph_han_chars": 45,
            "opening_han_chars": 12,
            "max_same_opening_occurrences": 2,
        },
        "paragraph_similarity": {
            "min_paragraph_han_chars": 60,
            "shingle_han_chars": 4,
            "similarity_threshold": 0.72,
            "max_similar_pairs": 1,
        },
        "heading_fragmentation": {
            "max_h2_per_1000_han": 8.0,
            "min_section_han_chars": 80,
            "max_thin_section_ratio": 0.40,
        },
    }
    return contract


def _v5_payload():
    p = payload()
    p["schema_version"] = "v5"
    p["narrative_chapters"] = [
        {
            "title": "先看经营结果",
            "paragraphs": [
                {"text": "收入扩张只说明订单和交付规模在变化，真正决定经营质量的仍是毛利、费用与现金回收。把三者放在一起观察，可以避免因单一增长数字而高估公司的盈利弹性。", "refs": ["E1", "E2"]},
                {"text": "季度波动可能来自采购、验收和回款错配，因此短期现金承压不能直接外推为长期趋势。后续披露若显示营运资金占用下降，当前谨慎结论应随之更新。", "refs": ["E1", "E2"]},
            ],
        },
        {
            "title": "业务能力如何兑现",
            "paragraphs": [
                {"text": "产品范围越完整，理论上越容易覆盖客户从设备到服务的需求，但产品出现并不等于形成批量收入。验证、交付、验收与回款必须连续成立，平台能力才会转成可复算的经济贡献。", "refs": ["E1", "E3"]},
                {"text": "同业资料说明竞争并非静态，替代方案、价格压力和执行成本都可能削弱项目价值。现阶段更可靠的做法是跟踪分项出货和毛利披露，而不是提前给业务能力定价。", "refs": ["E4", "E5", "E8", "E9", "E10"]},
            ],
        },
        {
            "title": "预测需要哪些条件",
            "paragraphs": [
                {"text": "预测不是对历史增速的机械延长，而是对销量、价格、毛利和费用组合的条件表达。只要其中一个关键变量偏离，利润与自由现金流路径就需要重新计算。", "refs": ["E1", "E6"]},
                {"text": "外部预期可用来理解市场关注点，却不能替代内部情景。两套口径存在差异时，应把差异保留下来，并等待实际经营数据决定哪组假设更接近现实。", "refs": ["E6", "E7"]},
            ],
        },
        {
            "title": "风险怎样被证伪",
            "paragraphs": [
                {"text": "判断失效通常不是因为某个叙事突然消失，而是因为经营指标持续朝相反方向发展。利润率、现金转换和客户验证若不能同步改善，就应降低对增长质量的评价。", "refs": ["E2", "E5"]},
                {"text": "反过来，连续报告期出现盈利修复、现金回正和明确的分项披露，也会构成正向证据。研究结论应允许这类证据改变原有看法，而不是为了保持一致而忽略新信息。", "refs": ["E1", "E10"]},
            ],
        },
    ]
    return p


def _run(p, report, contract=None):
    appendix = build_traceability_appendix(p, report, schema_version="v5")
    return evaluate_reader_candidate(p, report, appendix, binding(), reader_contract(), contract or _style_contract())


def test_natural_v5_narrative_passes_non_compensating_style_gate():
    p = _v5_payload()
    report = render_v5(p)
    result = _run(p, report)
    assert result["decision"] == "candidate_ready_for_human_review"
    assert result["narrative_style_diagnostics"]["decision"] == "pass"
    assert "本节判断" not in report


def test_repeated_audit_scaffold_is_rejected_for_v5():
    p = payload()
    p["schema_version"] = "v5"
    result = _run(p, render_v4(p))
    assert any(item["code"] == "reader_template_scaffolding_excessive" for item in result["candidate_blockers"])


def test_process_audit_language_in_body_is_rejected():
    p = _v5_payload()
    report = render_v5(p).replace("收入扩张只说明", "自动质量门通过也不能替代判断，收入扩张只说明", 1)
    result = _run(p, report)
    assert any(item["code"] == "reader_process_audit_language_leaked" for item in result["candidate_blockers"])


def test_repeated_paragraph_opening_is_rejected():
    p = _v5_payload()
    repeated = "需要特别说明的是这个判断仍然依赖后续经营数据，只有利润、现金和交付同时改善，当前研究结论才有充分理由获得上调。"
    for chapter in p["narrative_chapters"][:3]:
        chapter["paragraphs"][0]["text"] = repeated + chapter["title"]
    result = _run(p, render_v5(p))
    assert any(item["code"] == "reader_opening_repetition_excessive" for item in result["candidate_blockers"])


def test_near_duplicate_paragraphs_are_rejected():
    p = _v5_payload()
    base = "经营结果需要把收入、毛利、费用和现金放在同一条分析链上，因为任何单项指标都不足以说明增长已经转化为可以持续的股东回报。"
    for index, chapter in enumerate(p["narrative_chapters"][:3]):
        chapter["paragraphs"][0]["text"] = base + f"第{index + 1}个观察窗口仍需等待定期报告确认。"
    result = _run(p, render_v5(p))
    assert any(item["code"] == "reader_paragraph_similarity_excessive" for item in result["candidate_blockers"])


def test_v5_cannot_bypass_missing_narrative_policy():
    p = _v5_payload()
    report = render_v5(p)
    result = _run(p, report, quality_contract(min_han=500))
    assert any(item["code"] == "reader_narrative_gate_config_missing" for item in result["candidate_blockers"])


def test_fragmented_h2_sections_are_rejected():
    p = _v5_payload()
    report = render_v5(p).replace(
        "## 2、业务能力如何兑现",
        "\n".join(f"## 空标题{index}\n\n短句。" for index in range(1, 9)) + "\n\n## 2、业务能力如何兑现",
        1,
    )
    result = _run(p, report)
    assert any(item["code"] == "reader_heading_fragmentation_excessive" for item in result["candidate_blockers"])


def test_process_language_after_audit_separator_is_not_body_leakage():
    p = _v5_payload()
    report = render_v5(p) + "\n自动质量门仅用于尾注说明。\n"
    result = _run(p, report)
    assert not any(item["code"] == "reader_process_audit_language_leaked" for item in result["candidate_blockers"])


def test_v4_keeps_historical_scoring_compatibility():
    p = payload()
    report = render_v4(p)
    appendix = build_traceability_appendix(p, report)
    result = evaluate_reader_candidate(p, report, appendix, binding(), reader_contract(), quality_contract())
    assert result["decision"] == "candidate_ready_for_human_review"
    assert "narrative_style_diagnostics" not in result
