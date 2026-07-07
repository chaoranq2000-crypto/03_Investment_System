# P1.6 Company Valuation Subagent Integration Plan

## 1. 目标

把外部 `agent-agnostic-stock-skills/skills/company-valuation` 的估值方法论改造成当前 A-share Research OS 的内部估值写作子 skill，使 `stock-deep-dive` 在写估值部分时可以调用 `company-valuation`，但不改变当前工作流的证据优先、质量门和 no-advice 边界。

最终架构：

```text
research-orchestrator
  → stock-deep-dive
      → evidence / claims / metrics / forecast pack
      → company-valuation  # sub-skill for valuation context only
      → stock-deep-dive report assembly
      → quality-review
```

## 2. 为什么可行

当前 `stock-deep-dive` 已经有：

```text
forecast_model.yaml
valuation_model.yaml
peer_comparison.csv
sensitivity_table.csv
stock_analysis_pack.yaml
stock_deep_dive_report_template.md
publishable_stock_report_gate.md
```

因此不需要新增顶层 workflow，只需要补足估值子 skill 的输入契约、输出契约、写作边界和 quality handoff。

## 3. 改造边界

### 3.1 保留的外部 skill 思路

```text
DCF / DDM / NAV / SOTP / relative valuation 的方法选择
peer multiples 的口径要求
WACC / terminal growth / margin / revenue growth 的敏感性分析
bull / base / bear 情景
估值假设和风险清单
```

### 3.2 必须删除或降级的外部 skill 行为

```text
独立拉取 yfinance 数据
自动安装依赖
直接输出 fair value / implied share price headline
直接计算 upside / downside 作为结论
回答“是否低估/高估”作为投资判断
输出 price target / buy / sell / hold / position sizing
```

### 3.3 新定位

`company-valuation` 在本项目中只做：

```text
reviewed inputs → valuation_model / valuation_snapshot / section draft / gaps
```

不做：

```text
source acquisition
claim promotion
business exposure proof
segment mapping
report assembly
quality gate final decision
investment advice
```

## 4. 文件变更计划

### 4.1 新增 skill

```text
.agents/skills/company-valuation/SKILL.md
.agents/skills/company-valuation/README.md
.agents/skills/company-valuation/references/valuation_model_contract.md
.agents/skills/company-valuation/references/method_selection.md
.agents/skills/company-valuation/references/output_writing_rules.md
.agents/skills/company-valuation/assets/valuation_request_template.yaml
.agents/skills/company-valuation/assets/valuation_snapshot_template.yaml
.agents/skills/company-valuation/assets/valuation_section_template.md
```

### 4.2 stock-deep-dive 新增 handoff reference

```text
.agents/skills/stock-deep-dive/references/valuation_subagent_handoff.md
.agents/skills/stock-deep-dive/assets/valuation_request_template.yaml
```

### 4.3 合并进现有文件

```text
.codex/config.toml
.agents/skills/stock-deep-dive/SKILL.md
.agents/skills/stock-deep-dive/references/report_production_profile.md
.agents/skills/stock-deep-dive/references/forecast_valuation_contract.md
.agents/skills/stock-deep-dive/references/analysis_pack_contract.md
.agents/skills/stock-deep-dive/assets/stock_analysis_pack_template.yaml
```

可选追加：

```text
.agents/skills/quality-review/SKILL.md
```

只允许追加 `QR-VAL-*` 局部检查，不新增全局 gate 编号。

## 5. 调用流程

### CV-call-0 触发条件

`stock-deep-dive` 在以下情况调用 `company-valuation`：

```text
- 需要写“估值分析”章节；
- forecast_model 已有基本结构，或明确缺口；
- 至少有 market valuation snapshot 或 TODO_MARKET_DATA；
- peer context 可用，或明确 TODO_PEER_DATA；
- 估值必须作为 estimate / inference / analyst_view，不作为 fact。
```

### CV-call-1 输入

```text
reports/workflow_runs/<workflow_id>/stock_analysis_pack.yaml
reports/workflow_runs/<workflow_id>/forecast_model.yaml
reports/workflow_runs/<workflow_id>/financial_metric_pack.csv
reports/workflow_runs/<workflow_id>/valuation_request.yaml
reports/workflow_runs/<workflow_id>/peer_market_snapshot.csv 或 TODO_PEER_DATA
reports/workflow_runs/<workflow_id>/market_snapshot.csv 或 TODO_MARKET_DATA
```

### CV-call-2 输出

```text
reports/workflow_runs/<workflow_id>/valuation/valuation_model.yaml
reports/workflow_runs/<workflow_id>/valuation/valuation_snapshot.yaml
reports/workflow_runs/<workflow_id>/valuation/peer_comparison.csv
reports/workflow_runs/<workflow_id>/valuation/sensitivity_table.csv
reports/workflow_runs/<workflow_id>/valuation/valuation_section_draft.md
reports/workflow_runs/<workflow_id>/valuation/valuation_gap_requests.yaml
reports/workflow_runs/<workflow_id>/valuation/valuation_quality_handoff.yaml
```

### CV-call-3 回收

`stock-deep-dive` 只从 `valuation_section_draft.md` 和 `valuation_model.yaml` 回收估值部分，不得在报告写作阶段自由新增估值事实。

## 6. 质量门

估值输出至少满足：

```text
1. 所有估值倍数有 as_of_date、period、source_path 或 metric_id。
2. peer comparison 有可比理由和不可比限制。
3. 估值情景只写成 scenario，不写成 price target instruction。
4. DCF / SOTP / NAV / DDM 仅在输入足够时启用；否则写 TODO。
5. 不把券商预测、管理层展望或新闻线索写成事实。
6. 不输出买入 / 卖出 / 持有 / 仓位 / 保证收益。
7. 敏感变量和反证可见。
```

## 7. 验收标准

```text
- company-valuation 被 .codex/config.toml 启用；
- stock-deep-dive 明确在 RP6 / SDD-2.5 调用 company-valuation；
- valuation_subagent_handoff.md 成为 stock-deep-dive must-read reference；
- 估值输出可以独立进入 quality-review；
- 缺 market / peer / forecast 数据时输出 TODO，而不是编写确定性估值判断；
- no-advice gate 通过；
- 能用一个已有 stock workflow run dry-run 出 valuation_gap_requests.yaml。
```

## 8. 不做事项

本补丁不做：

```text
- 不导入外部 yfinance 代码；
- 不新增实时行情下载器；
- 不更改 evidence-ingest 的数据下载职责；
- 不改写全局 workflow gate；
- 不进入 P2；
- 不把估值结论变成 watchlist 或买卖建议。
```
