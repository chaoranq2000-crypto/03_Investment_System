from __future__ import annotations

import csv
from pathlib import Path
from typing import Mapping

import yaml


def _load_yaml(path: Path) -> object:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def _table(rows: list[list[object]]) -> str:
    if not rows:
        return ""
    header = rows[0]
    body = rows[1:]
    lines = [
        "| " + " | ".join(str(cell) for cell in header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    lines.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in body)
    return "\n".join(lines)


def _metric_rows(financial_quality: Mapping[str, object]) -> list[list[object]]:
    rows = [["指标", "期间", "数值", "单位", "metric_id / evidence"]]
    for item in financial_quality.get("ratios", []) if isinstance(financial_quality.get("ratios"), list) else []:
        rows.append(
            [
                item.get("metric_name", ""),
                item.get("period", ""),
                item.get("value", ""),
                item.get("unit", ""),
                item.get("metric_id", "") or item.get("source_evidence_id", ""),
            ]
        )
    return rows


def _business_rows(business_breakdown: Mapping[str, object]) -> list[list[object]]:
    rows = [["业务", "收入", "占比", "毛利率", "增长驱动", "证据", "置信度"]]
    for item in business_breakdown.get("business_lines", []) if isinstance(business_breakdown.get("business_lines"), list) else []:
        rows.append(
            [
                item.get("name", ""),
                item.get("revenue", "MISSING_DISCLOSURE"),
                item.get("revenue_pct", "MISSING_DISCLOSURE"),
                item.get("gross_margin", "MISSING_DISCLOSURE"),
                item.get("growth_driver", ""),
                ",".join(item.get("claim_ids", []) or ["TODO"]),
                item.get("confidence", ""),
            ]
        )
    return rows


def _forecast_rows(forecast_model: Mapping[str, object]) -> list[list[object]]:
    rows = [["指标", "2026E", "2027E", "2028E", "核心假设", "证据/模型"]]
    revenue = forecast_model.get("revenue_forecast", [])
    values = {item.get("period"): item for item in revenue} if isinstance(revenue, list) else {}
    rows.append(
        [
            "收入",
            values.get("2026E", {}).get("value", "TODO"),
            values.get("2027E", {}).get("value", "TODO"),
            values.get("2028E", {}).get("value", "TODO"),
            "估计值，基于公司层面历史收入，不归因到液冷业务",
            ",".join(values.get("2026E", {}).get("supporting_metric_ids", []) or ["TODO"]),
        ]
    )
    return rows


def _peer_rows(peer_csv: Path) -> list[list[object]]:
    rows = [["公司", "代码", "业务相关性", "PE TTM", "2026E PE", "2027E PE", "备注"]]
    if peer_csv.exists():
        for row in csv.DictReader(peer_csv.open("r", encoding="utf-8", newline="")):
            rows.append(
                [
                    row.get("company", ""),
                    row.get("code", ""),
                    row.get("business_relevance", ""),
                    row.get("pe_ttm", ""),
                    row.get("2026E_PE", ""),
                    row.get("2027E_PE", ""),
                    row.get("notes", ""),
                ]
            )
    return rows


def render_report(
    *,
    run_dir: Path,
    template_path: Path,
    output_path: Path,
) -> dict[str, object]:
    pack = _load_yaml(run_dir / "stock_analysis_pack.yaml")
    financial_quality = _load_yaml(run_dir / "financial_quality.yaml")
    business_breakdown = _load_yaml(run_dir / "business_breakdown.yaml")
    industry_context = _load_yaml(run_dir / "industry_context_card.yaml")
    forecast_model = _load_yaml(run_dir / "forecast_model.yaml")
    valuation_model = _load_yaml(run_dir / "valuation_model.yaml")
    risk_counter = _load_yaml(run_dir / "risk_counter_evidence.yaml")
    gaps = _load_yaml(run_dir / "evidence_gap_requests.yaml")
    metadata = pack.get("metadata", {}) if isinstance(pack, dict) else {}
    stock_name = metadata.get("stock_name", "")
    stock_code = metadata.get("stock_code", "")
    claim_ids = metadata.get("claim_ids", []) or []
    metric_ids = metadata.get("metric_ids", []) or []
    peer_csv = Path(str(valuation_model.get("peer_comparison", run_dir / "peer_comparison.csv")))

    evidence_rows = [["结论", "claim_id / metric_id", "evidence_id", "来源", "日期", "页码/表格", "置信度"]]
    for claim_id in claim_ids[:8]:
        evidence_rows.append(["业务/产品暴露候选", claim_id, "见 claims_registry", "annual_report", metadata.get("analysis_date", ""), "page locator", "medium"])
    for metric_id in metric_ids[:8]:
        evidence_rows.append(["公司层面财务指标", metric_id, "见 metrics_registry", "structured_data", metadata.get("analysis_date", ""), "csv", "medium"])

    open_questions = "\n".join(
        f"- {gap.get('gap_id', 'gap')}: {gap.get('missing_claim_or_metric', '')}"
        for gap in gaps
        if isinstance(gap, dict)
    )
    if not open_questions:
        open_questions = "- TODO: 需要补充证据"

    report = f"""# 价值发现：{stock_code} {stock_name}

## 0. Metadata

| 字段 | 内容 |
|---|---|
| stock_code | {stock_code} |
| company_id | {metadata.get('company_id', '')} |
| report_date | {metadata.get('analysis_date', '')} |
| quality_target | {metadata.get('quality_target', '')} |
| evidence_snapshot | {metadata.get('evidence_snapshot', '')} |
| report_status | draft_for_quality_review |

## 前言

{pack.get('core_thesis', {}).get('one_sentence', '')} 当前可支持的事实是产品/业务线索与公司层面财务指标，最大的证据缺口是液冷收入占比和毛利率仍未完成表格化披露核验。

## 一、财务概览

公司层面财务数据已进入指标注册表，但这些指标只支持公司整体观察，不支持直接推导液冷业务收入。

{_table(_metric_rows(financial_quality))}

## 二、业务拆分

业务拆分的当前结论是：可以识别数据中心温控/液冷相关产品暴露，但收入、利润和客户订单贡献必须保持 MISSING，等待官方表格或公告补证。

{_table(_business_rows(business_breakdown))}

## 三、行业分析

AI算力密度提升使数据中心热管理成为需要跟踪的细分变量。公司处在价值链的位置暂按“数据中心/机房温控及液冷相关解决方案”处理，关键验证指标包括分业务收入、毛利率、订单和经营现金流。行业供给格局仍为 TODO_SOURCE_REQUIRED，不能用情绪线索替代事实。

## 四、盈利预测

以下预测是估计和情景模型，不是事实；模型基准来自公司整体历史收入，暂不把预测收入归因到液冷业务。

{_table(_forecast_rows(forecast_model))}

## 五、估值分析

估值部分仅形成场景框架和同业表占位，不输出价格指令或交易动作。当前缺少实时 PE/PB/PS 等结构化行情字段，因此估值结论保持观察口径。

{_table(_peer_rows(peer_csv))}

估值结论：{valuation_model.get('conclusion', 'TODO_MODEL_INPUT')}

## 六、技术分析

技术面只作为市场状态观察。数据日期为 {metadata.get('analysis_date', '')}；若缺少行情快照，则本节保持 TODO_MARKET_DATA，不影响基本面证据判断。

## 七、情绪分析

宏观、行业和公司情绪当前均为线索层信息，必须标注为 clue 或 TODO_SOURCE_REQUIRED，不能写成事实结论。

## 八、事件驱动

| 日期/窗口 | 事件 | 影响变量 | 超预期条件 | 低于预期风险 | 证据 |
|---|---|---|---|---|---|
| next_reporting_window | 下一期定期报告或经营更新 | 收入、毛利率、现金流、分业务披露 | 分业务或订单证据改善 | 收入兑现或现金流弱于模型 | {','.join(claim_ids[:3]) or 'TODO_SOURCE_REQUIRED'} |

## 九、研究结论、风险与跟踪清单

研究状态：watch_for_evidence。事实层面，公司已具备数据中心温控/液冷相关产品线索和公司层面财务指标；推断层面，产品暴露值得继续跟踪，但收入暴露不能升级，直到分业务收入、订单或客户证据被审查。

### 风险与反证

{'; '.join(risk_counter.get('risks', [])) if isinstance(risk_counter, dict) else 'TODO: 需要补充证据'}

### 后续跟踪指标

| 指标 | 为什么重要 | 频率 | 来源 | 触发动作 |
|---|---|---|---|---|
| 分业务收入/毛利率 | 验证产品暴露是否转化为财务贡献 | 定期报告 | annual_report / interim_report | 更新 analysis_pack |
| 订单/客户/产能公告 | 验证需求兑现 | 事件驱动 | announcement | 更新 evidence_gap |
| 经营现金流 | 验证利润质量 | 季度 | structured_financial_data | 更新 financial_quality |

## 附录 A：Evidence Map

{_table(evidence_rows)}

## 附录 B：Open Questions / Evidence Gaps

{open_questions}
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    (run_dir / "report_evidence_map.md").write_text(_table(evidence_rows) + "\n", encoding="utf-8")
    (run_dir / "report_open_questions.md").write_text(open_questions + "\n", encoding="utf-8")
    (run_dir / "writer_gap_requests.yaml").write_text(yaml.safe_dump(gaps, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"output_path": str(output_path), "evidence_rows": len(evidence_rows) - 1}
