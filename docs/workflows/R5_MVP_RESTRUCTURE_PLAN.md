# R5 MVP Restructure Plan — 样例质量个股报告重构总计划

> 本文件记录 R5-MVP 的阶段性设计；它当时建立在 P1.6 的 workflow / skill / gate
> 架构基础上，用于描述“样例质量个股深度报告”的最小闭环。
>
> **Legacy compatibility note（2026-08-24）：** 本文件保留 R5-MVP 的设计沿革，
> 不再充当当前 checkpoint、任务队列或运行状态入口。当前全局 workflow 与状态语义以
> `AGENTS.md`、`docs/workflows/RESEARCH_WORKFLOW.md`、
> `docs/meta/DOC_OWNERSHIP_MATRIX.md` 和活动 skill contract 为准；下文 Phase / Patch
> 编号只描述历史实施顺序，不授权恢复或重新执行旧任务包。

## 1. 背景

当前 R4 个股报告更接近“证据可审计的内部草稿”：强调 evidence、claim、metric、TODO 和 source gap 的可追溯性，但还没有稳定具备样例报告中的财务穿透、业务拆分、行业供需、盈利预测、估值锚、技术面、情绪面和事件驱动等完整判断链。

R5 的重构目标不是“让报告变长”，而是把系统从：

```text
报告生成器
```

升级为：

```text
研究资产包生成器 + 报告转译器
```

## 2. R5-MVP 总目标

R5-MVP 先钉住边界，不一次性实现完整 R5：

```text
1. 定义 R5_sample_quality_stock_note 是什么；
2. 定义 R5_stock_research_pack.yaml 作为事实源；
3. 定义 R5 报告章节和降级规则；
4. 定义样例质量 rubric；
5. 定义后续每个 Codex patch 的最小边界；
6. 防止 Codex 一次性大改、隐藏 TODO 或创造无证据结论。
```

## 3. 与 P1.6 的关系

```text
P1.6：让 workflow、skill、evidence、mapping、quality gate 可运行。
R5-MVP：让单篇个股研究报告具备样例质量所需的资产密度。
P2：多细分 / 多公司比较，不等同于单篇个股深度报告质量。
```

R5 不绕过 P1.6 的 evidence / quality / no-advice 约束。证据不足时，R5 必须降级为 `research_draft` 或 `source_gapped_draft`。

## 4. R5 目标产物

每次 R5 个股研究 run 的目标产物为：

```text
reports/workflow_runs/<workflow_id>/
  R5_stock_research_pack.yaml
  R5_stock_research_note.md
  R5_quality_gate_report.md
  R5_source_gap_report.md
  R5_open_questions.md
```

其中：

```text
R5_stock_research_pack.yaml = 事实源 / 结构化研究资产
R5_stock_research_note.md = 面向人阅读的样例风格报告
R5_quality_gate_report.md = 是否达到 R5 的质量判定
R5_source_gap_report.md = 不足以支撑强判断的证据缺口
R5_open_questions.md = 下一轮研究问题清单
```

## 5. R5 研究包的 12 个子包

```text
1. company_identity_pack
2. evidence_snapshot_pack
3. financial_history_pack
4. business_breakdown_pack
5. segment_exposure_pack
6. industry_context_pack
7. peer_comparison_pack
8. forecast_model_pack
9. valuation_pack
10. technical_market_pack
11. sentiment_event_pack
12. risk_counterevidence_pack
```

这些子包共同决定报告能否达到样例质量。报告 writer 不能凭空补足缺失的研究资产。

## 6. 分阶段实施路线

### Phase 0：R5-MVP 目标说明与模板骨架

历史 Phase 0 只新增文档、模板和 rubric，不写运行代码，不生成个股报告。

其仍由当前树保留的设计产物为：

```text
docs/workflows/R5_MVP_RESTRUCTURE_PLAN.md
docs/workflows/R5_SAMPLE_QUALITY_STOCK_REPORT_SPEC.md
templates/r5_stock_research_pack.yaml
templates/r5_stock_research_note.md
benchmarks/r5_report_quality_rubric.yaml
```

### Phase 1：stock-deep-dive B5-lite 契约补强

目标：让 `stock-deep-dive` 先能消费证据并输出 R5 研究包骨架。只做契约和模板，不做盈利预测逻辑。

### Phase 2：evidence-ingest R5 数据计划

目标：把证据输入从“文档登记”升级为 R5 可消费的证据快照计划。重点包括 official filings、financial tables、market snapshot、peer snapshot、news / event clues。

### Phase 3：financial + business breakdown pack

目标：建立财务历史、财务质量、业务拆分、利润池、客户 / 产品 / 产能 / 订单字段。没有证据时必须写 `MISSING_DISCLOSURE`，不得由 writer 补写。

### Phase 4：forecast + valuation schema

目标：建立 2026E-2028E 预测包和估值包字段。先做 schema 与校验，不直接产出真实预测。

### Phase 5：technical + sentiment + catalyst pack

目标：建立技术、资金、情绪和事件日历字段。所有市场数据必须带 `as_of_date`。

### Phase 6：R5 quality-review gate

目标：把质量检查从“是否有问题”升级为“是否达到样例质量”。必须输出具体 issue list，而不是泛泛评价。

### Phase 7：R5 report composer skeleton

目标：把 research pack 转译为样例风格报告。composer 只能转译已通过质量门的资产，不能创造新结论。

### Phase 8：单股票 R5 dry-run

目标：选一个证据披露相对完整的公司做 R5 dry-run，然后再回到英维克等高 source-gap 个股。

## 7. Codex 协作规则

每个 Codex patch 只解决一个问题：

```text
一个 patch = 一个契约 / 一个模板 / 一个校验器 / 一个 readout。
```

禁止：

```text
1. 一个 patch 同时改 evidence、stock-deep-dive、forecast、valuation、writer、quality gate；
2. 修改 reports/workflow_runs/ 历史产物；
3. 引入真实 API 调用或外部数据源依赖；
4. 把 TODO / MISSING_DISCLOSURE 写成事实；
5. 输出直接交易指令或仓位建议；
6. 声称 R5 已完成。
```

## 8. R5 通过 / 降级规则

```text
R5_sample_quality_ready：
  - 12 个子包中核心 8 个通过；
  - forecast_model_pack 通过；
  - valuation_pack 通过；
  - business_breakdown_pack 通过；
  - quality gate 无 high issue；
  - source gap 显式展示；
  - no-advice gate 通过。

R5_research_draft：
  - 财务、业务或行业资产足以形成研究草稿；
  - forecast / valuation / technical / sentiment 中存在明显缺口；
  - 不得标记 sample-quality。

R5_source_gapped_draft：
  - 关键业务拆分、收入占比、利润贡献或市场快照缺失；
  - 只能输出缺口可见的内部研究稿。

blocked：
  - company identity 不清；
  - 关键数据无法追溯；
  - 质量门存在 high issue；
  - 报告试图隐藏 TODO 或创造无证据结论。
```

## 9. 历史后继说明

Phase 0 当时把以下工作列为后继步骤：

```text
Patch 1：stock-deep-dive B5-lite R5 research pack contract
```

这不是当前任务指令。任何后续研究或维护工作均应由当前 Research workflow 和活动
skill contract 重新路由，不得从这里恢复旧 Patch 队列。
