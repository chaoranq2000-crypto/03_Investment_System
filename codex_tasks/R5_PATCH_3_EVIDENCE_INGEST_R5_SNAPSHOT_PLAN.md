# Codex Task Card — R5 Patch 3：evidence-ingest R5 snapshot plan

## 任务名称

补强 `evidence-ingest` 的 R5 evidence snapshot plan 与 handoff contract。

## 背景

R5 样例质量取决于证据密度。当前 data-layer 已有 evidence ingest 与 adapter 基础，但 R5 需要明确 official filings、financial tables、market snapshot、peer snapshot、news/event clues 的最小证据计划。本 patch 只做计划、契约、模板和 validator；不写真实下载器。

## 目标

1. 定义 R5 stock evidence plan 模板。
2. 定义 evidence snapshot handoff 到 `stock-deep-dive` 的字段。
3. 明确不同 source type 的可靠性等级与用途边界。
4. 定义缺证据时如何进入 `source_gap_register`。

## 允许新增 / 修改文件

- `.agents/skills/evidence-ingest/references/r5_stock_evidence_snapshot_contract.md`
- `.agents/skills/evidence-ingest/assets/r5_stock_evidence_plan_template.yaml`
- `.agents/skills/evidence-ingest/scripts/validate_r5_evidence_plan.py`
- `tests/test_r5_evidence_snapshot_plan.py`
- `reports/p1_6/R5_PATCH_3_EVIDENCE_INGEST_R5_SNAPSHOT_PLAN_READOUT.md`

## 禁止事项

- 不修改 `reports/workflow_runs/` 历史 run。
- 不修改已有 R4 报告正文产物，除非本任务明确要求兼容指针。
- 不新增真实 API 调用，不执行联网下载。
- 不生成任何真实股票研究报告。
- 不计算真实 forecast 或真实 valuation，除非本任务明确只做 schema fixture。
- 不把 `TODO_SOURCE_REQUIRED`、`MISSING_DISCLOSURE`、`TODO_MODEL_INPUT` 写成事实。
- 不输出买入、卖出、持有、建仓、减仓、仓位建议、保证收益或自动交易指令。
- 不让 writer / composer 创造研究结论。

## 契约必须覆盖

- 最近 3 年年报、最近季报 / 半年报 / 三季报；
- 最近 12-18 个月重大公告、问询函、投资者关系记录；
- structured financial metrics；
- market snapshot；
- peer snapshot；
- industry price / supply-demand clues；
- news / event clues；
- 每个 evidence item 的 `source_type`、`source_rank`、`as_of_date`、`freshness_policy`、`allowed_usage`。

## 验收标准

1. evidence plan YAML 可解析。
2. 缺 official filing 时必须 high issue。
3. market / peer / news 只能作为 context，不能单独证明业务暴露。
4. 输出 handoff 字段能被 R5 pack 消费。
5. 不引入真实 API 调用。

## 测试命令

~~~bash
python -m py_compile .agents/skills/evidence-ingest/scripts/validate_r5_evidence_plan.py
pytest tests/test_r5_evidence_snapshot_plan.py
~~~

## 输出要求

完成后请输出：

1. 新增 / 修改文件列表；
2. 测试命令和结果；
3. 简短 diff summary；
4. 未完成项和 source gap；
5. 一个 readout 文件，放入 `reports/p1_6/`。
