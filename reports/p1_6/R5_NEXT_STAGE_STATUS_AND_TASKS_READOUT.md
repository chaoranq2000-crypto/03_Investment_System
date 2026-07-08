# R5 下一阶段完成情况检查与任务包总览

生成日期：2026-07-07  
适用仓库：`chaoranq2000-crypto/03_Investment_System`  
范围：基于 GitHub main 分支公开页面检查。由于当前执行环境无法解析 `github.com`，本地未完成 `git clone` 与 pytest 全量运行；本包只生成可交给 Codex 执行的任务卡，不直接写实现代码。

## 1. 当前完成情况判断

### 已完成 / 已入仓

- R5-MVP 的方向已钉住：`docs/workflows/R5_MVP_RESTRUCTURE_PLAN.md` 已定义 R5 是“研究资产包生成器 + 报告转译器”，不是简单扩写报告。
- R5 sample-quality spec 已存在：`docs/workflows/R5_SAMPLE_QUALITY_STOCK_REPORT_SPEC.md` 已定义 `R5_stock_research_pack.yaml` 是事实源，`R5_stock_research_note.md` 是转译产物。
- R5 pack 的 12 个子包已经在 spec 和模板层出现。
- R5 九章报告模板已经在 `templates/r5_stock_research_note.md` 出现。
- R5 quality rubric 已在 `benchmarks/r5_report_quality_rubric.yaml` 出现。
- `stock-deep-dive` 已经是个股研究统一入口，并已有 `stock_analysis_pack.yaml`、估值 subagent handoff、`segment_exposure.yaml` 与 quality-review handoff 的 R4/R4+ 基础。
- data-layer 与 valuation 相关测试、readout、模板已较厚，说明 R5 可以继续沿现有 P1.6 路径加契约，而不是另起炉灶。

### 尚未完成 / 下一阶段核心缺口

- R5 仍停留在目标说明和模板骨架；还没有稳定的 R5 skill-local 契约。
- `stock-deep-dive` 当前主产物仍是 `stock_analysis_pack.yaml`，还没有正式升级/映射到 `R5_stock_research_pack.yaml` 的 contract 与 validator。
- R5 pack schema validator、quality gate validator、report composer skeleton、sample benchmark regression、dry-run harness 还未入仓。
- 业务拆分、forecast、valuation、technical、sentiment、event 这些样例质量核心资产还需要从“字段存在”推进到“可校验、可降级、可交接”。
- 现有 tests 目录已经有 R4、valuation、technical、peer snapshot、stock writer 等测试，但未观察到以 `test_r5_*` 命名的 R5 专项测试。

## 2. 下一阶段建议

不要一次让 Codex “实现完整 R5”。建议把下一阶段拆成 14 个 patch，分三批连续执行：

- Batch A：R5 契约与输入资产层，Patch 1-4。
- Batch B：forecast / valuation / market / sentiment / source-gap 资产层，Patch 5-9。
- Batch C：quality gate / composer / benchmark / dry-run / docs interlock，Patch 10-14。

每个 patch 都要求 Codex：单独修改、单独测试、单独输出 readout。这样任务数量足够，不必频繁重新拆任务；同时每个 patch 仍可独立验收。

## 3. 本补丁包内容

```text
r5_next_stage_patch_package/
  README.md
  reports/p1_6/R5_NEXT_STAGE_STATUS_AND_TASKS_READOUT.md
  codex_tasks/R5_PATCH_1_STOCK_DEEP_DIVE_R5_PACK_CONTRACT.md
  codex_tasks/R5_PATCH_2_R5_PACK_SCHEMA_VALIDATOR.md
  codex_tasks/R5_PATCH_3_EVIDENCE_INGEST_R5_SNAPSHOT_PLAN.md
  codex_tasks/R5_PATCH_4_FINANCIAL_BUSINESS_PACK_CONTRACTS.md
  codex_tasks/R5_PATCH_5_FORECAST_MODEL_CONTRACT_AND_VALIDATOR.md
  codex_tasks/R5_PATCH_6_VALUATION_PACK_CONTRACT_AND_HANDOFF.md
  codex_tasks/R5_PATCH_7_TECHNICAL_MARKET_PACK_CONTRACT.md
  codex_tasks/R5_PATCH_8_SENTIMENT_EVENT_PACK_CONTRACT.md
  codex_tasks/R5_PATCH_9_RISK_COUNTEREVIDENCE_SOURCE_GAP_PACK.md
  codex_tasks/R5_PATCH_10_R5_QUALITY_GATE.md
  codex_tasks/R5_PATCH_11_REPORT_PLANNER_COMPOSER_SKELETON.md
  codex_tasks/R5_PATCH_12_SAMPLE_BENCHMARK_REGRESSION.md
  codex_tasks/R5_PATCH_13_R5_DRY_RUN_FIXTURE_HARNESS.md
  codex_tasks/R5_PATCH_14_ORCHESTRATOR_INTERLOCK_DOC_INDEX.md
  batch_prompts/BATCH_A_PATCH_1_TO_4_PROMPT.md
  batch_prompts/BATCH_B_PATCH_5_TO_9_PROMPT.md
  batch_prompts/BATCH_C_PATCH_10_TO_14_PROMPT.md
```

## 4. 使用建议

把 `codex_tasks/` 中的任务卡复制进仓库同名目录，然后让 Codex 按 batch prompt 顺序执行。每个 patch 完成后，要求 Codex 提交 readout 到 `reports/p1_6/`，并列出测试结果、修改文件、未完成项和后续建议。

## 5. 重要边界

- 不修改 `reports/workflow_runs/` 历史 run。
- 不直接生成股票研究结论。
- 不引入真实 API 调用。
- 不把 `TODO_SOURCE_REQUIRED` / `MISSING_DISCLOSURE` 写成事实。
- 不输出直接交易指令、仓位建议或保证收益表达。
- writer / composer 只能转译已审查研究资产，不能创造研究结论。
