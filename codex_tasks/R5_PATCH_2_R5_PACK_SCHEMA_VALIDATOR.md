# Codex Task Card — R5 Patch 2：R5_stock_research_pack schema validator

## 任务名称

新增 R5 research pack schema validator 与最小 pytest。

## 背景

Patch 1 定义了 R5 pack contract，但还不能自动校验。R5 必须先做到“结构可审查”，再进入写作层。本 patch 让 `R5_stock_research_pack.yaml` 可以被脚本校验。

## 目标

1. 新增 `validate_r5_stock_research_pack.py`。
2. 新增正例 / 反例 fixture。
3. 新增 pytest，覆盖核心缺失、缺 source、缺 as_of_date、隐藏 TODO 等失败场景。
4. 校验输出必须是机器可读 issue list，不只是 print 文本。

## 允许新增 / 修改文件

- `.agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py`
- `.agents/skills/stock-deep-dive/assets/r5_stock_research_pack.valid.example.yaml`
- `.agents/skills/stock-deep-dive/assets/r5_stock_research_pack.invalid.example.yaml`
- `tests/test_r5_stock_research_pack_schema.py`
- `reports/p1_6/R5_PATCH_2_R5_PACK_SCHEMA_VALIDATOR_READOUT.md`

## 禁止事项

- 不修改 `reports/workflow_runs/` 历史 run。
- 不修改已有 R4 报告正文产物，除非本任务明确要求兼容指针。
- 不新增真实 API 调用，不执行联网下载。
- 不生成任何真实股票研究报告。
- 不计算真实 forecast 或真实 valuation，除非本任务明确只做 schema fixture。
- 不把 `TODO_SOURCE_REQUIRED`、`MISSING_DISCLOSURE`、`TODO_MODEL_INPUT` 写成事实。
- 不输出买入、卖出、持有、建仓、减仓、仓位建议、保证收益或自动交易指令。
- 不让 writer / composer 创造研究结论。

## Validator 最小规则

必须校验：

- 顶层必须存在 `metadata` 与 12 个 R5 子包；
- `company_identity_pack` 和 `evidence_snapshot_pack` 缺失时 `blocked`；
- material field 必须有 `source_evidence_id` / `metric_id` / `claim_id` / `assumption_id` 或 `missing_reason`；
- `technical_market_pack` 和 `sentiment_event_pack` 必须有 `as_of_date` 才能允许强判断；
- forecast 年份至少覆盖 `2026E`、`2027E`、`2028E`，但值可为 TODO；
- valuation pack 缺 market snapshot 时不得 `sample_quality_ready`；
- 所有 TODO / MISSING 必须进入 `source_gap_register`。

## 输出格式

脚本输出 JSON：

~~~json
{
  "decision": "accepted|accepted_with_todos|needs_fix|blocked",
  "issues": [
    {"issue_id":"R5P-001","severity":"high","path":"...","description":"...","next_action":"..."}
  ]
}
~~~

## 验收标准

1. 正例 fixture 通过，反例 fixture 失败且输出 high issue。
2. 测试覆盖至少 6 个失败场景。
3. high issue 不允许 `accepted`。
4. validator 不依赖联网、不依赖真实股票数据。

## 测试命令

~~~bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py
pytest tests/test_r5_stock_research_pack_schema.py
~~~

## 输出要求

完成后请输出：

1. 新增 / 修改文件列表；
2. 测试命令和结果；
3. 简短 diff summary；
4. 未完成项和 source gap；
5. 一个 readout 文件，放入 `reports/p1_6/`。
