# Codex Task Card — R5 Patch 7：technical_market_pack contract

## 任务名称

technical_market_pack contract

## 目标

1. 定义技术面市场快照 schema。
2. 校验 `as_of_date`、MA5/10/20/60/120/250、52w high/low、support/resistance。
3. 技术面只能描述状态和风险，不输出操作建议。

## 允许新增 / 修改文件

- `.agents/skills/stock-deep-dive/references/r5_technical_market_pack_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_technical_market_pack.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_technical_market_pack.py`
- `tests/test_r5_technical_market_pack.py`
- `reports/p1_6/R5_PATCH_7_TECHNICAL_MARKET_PACK_CONTRACT_READOUT.md`

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

- 缺 `as_of_date` 时不能生成交易状态判断。
- 支撑阻力必须标记为 observation。
- validator 不依赖真实行情接口。

## 测试命令

~~~bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_technical_market_pack.py
pytest tests/test_r5_technical_market_pack.py
~~~

## 输出要求

完成后请输出：

1. 新增 / 修改文件列表；
2. 测试命令和结果；
3. 简短 diff summary；
4. 未完成项和 source gap；
5. 一个 readout 文件，放入 `reports/p1_6/`。
