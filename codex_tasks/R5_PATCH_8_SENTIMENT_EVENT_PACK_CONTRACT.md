# Codex Task Card — R5 Patch 8：sentiment_event_pack contract

## 任务名称

sentiment_event_pack contract

## 目标

1. 定义 macro / industry / company 三层情绪 schema。
2. 定义 1m / 3m / 6m catalyst calendar。
3. 每个事件必须有 date、impact_path、verification_metric、counter_condition 或 TODO。

## 允许新增 / 修改文件

- `.agents/skills/stock-deep-dive/references/r5_sentiment_event_pack_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_sentiment_event_pack.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_sentiment_event_pack.py`
- `tests/test_r5_sentiment_event_pack.py`
- `reports/p1_6/R5_PATCH_8_SENTIMENT_EVENT_PACK_CONTRACT_READOUT.md`

## 禁止事项

- 不修改 `reports/workflow_runs/` 历史 run。
- 不修改已有 R4 报告正文产物，除非本任务明确要求兼容指针。
- 不新增真实 API 调用，不执行联网下载。
- 不生成任何真实股票研究报告。
- 不计算真实 forecast 或真实 valuation，除非本任务明确只做 schema fixture。
- 不把 `TODO_SOURCE_REQUIRED`、`MISSING_DISCLOSURE`、`TODO_MODEL_INPUT` 写成事实。
- 不输出买入、卖出、持有、建仓、减仓、仓位建议、保证收益或自动交易指令。
- 不让 writer / composer 创造研究结论。

## 交付物 / 规则要求

- 情绪数据缺 `as_of_date` 时不得写强判断。
- 新闻和舆情不得单独证明财务事实。
- 事件章节不得输出交易行动。

## 测试命令

~~~bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_sentiment_event_pack.py
pytest tests/test_r5_sentiment_event_pack.py
~~~

## 输出要求

完成后请输出：

1. 新增 / 修改文件列表；
2. 测试命令和结果；
3. 简短 diff summary；
4. 未完成项和 source gap；
5. 一个 readout 文件，放入 `reports/p1_6/`。
