# Codex Task Card — R5 Patch 6：valuation_pack contract and company-valuation handoff

## 任务名称

valuation_pack contract and company-valuation handoff

## 目标

1. 定义 current_price、market_cap、PE/PB/PS/EV、peer context、scenario valuation 字段。
2. 将 R5 valuation pack 与 `company-valuation` handoff 对齐。
3. 缺 market snapshot 或 peer context 时不得 sample-quality。
4. 估值只能输出研究语境，不输出交易指令。

## 允许新增 / 修改文件

- `.agents/skills/stock-deep-dive/references/r5_valuation_pack_contract.md`
- `.agents/skills/company-valuation/references/r5_valuation_handoff_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_valuation_pack.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_valuation_pack.py`
- `tests/test_r5_valuation_pack.py`
- `reports/p1_6/R5_PATCH_6_VALUATION_PACK_CONTRACT_AND_HANDOFF_READOUT.md`

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

- forward multiple 必须依赖 forecast_model_pack 或 TODO。
- SOTP/DCF 需有 applicability flag 和 reason。
- 所有估值来源缺口进入 valuation source gap。

## 测试命令

~~~bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_valuation_pack.py
pytest tests/test_r5_valuation_pack.py
~~~

## 输出要求

完成后请输出：

1. 新增 / 修改文件列表；
2. 测试命令和结果；
3. 简短 diff summary；
4. 未完成项和 source gap；
5. 一个 readout 文件，放入 `reports/p1_6/`。
