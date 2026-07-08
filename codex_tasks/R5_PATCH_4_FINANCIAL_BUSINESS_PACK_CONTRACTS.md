# Codex Task Card — R5 Patch 4：financial + business breakdown pack contracts

## 任务名称

建立 R5 财务历史包与业务拆分包 contract、模板和校验器。

## 背景

样例级报告的核心差异在于财务穿透和业务拆分。本 patch 让 R5 至少能结构化承载收入、毛利率、利润贡献、客户、产能、订单、异常项和现金流质量。

## 目标

1. 新增 `financial_history_pack` contract。
2. 新增 `business_breakdown_pack` contract。
3. 新增利润桥、现金流质量、业务利润池模板。
4. 新增 validator 与 pytest。

## 允许新增 / 修改文件

- `.agents/skills/stock-deep-dive/references/r5_financial_history_pack_contract.md`
- `.agents/skills/stock-deep-dive/references/r5_business_breakdown_pack_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_financial_history_pack.example.yaml`
- `.agents/skills/stock-deep-dive/assets/r5_business_breakdown_pack.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_financial_business_packs.py`
- `tests/test_r5_financial_business_packs.py`
- `reports/p1_6/R5_PATCH_4_FINANCIAL_BUSINESS_PACK_CONTRACTS_READOUT.md`

## 禁止事项

- 不修改 `reports/workflow_runs/` 历史 run。
- 不修改已有 R4 报告正文产物，除非本任务明确要求兼容指针。
- 不新增真实 API 调用，不执行联网下载。
- 不生成任何真实股票研究报告。
- 不计算真实 forecast 或真实 valuation，除非本任务明确只做 schema fixture。
- 不把 `TODO_SOURCE_REQUIRED`、`MISSING_DISCLOSURE`、`TODO_MODEL_INPUT` 写成事实。
- 不输出买入、卖出、持有、建仓、减仓、仓位建议、保证收益或自动交易指令。
- 不让 writer / composer 创造研究结论。

## 字段要求

`financial_history_pack` 至少覆盖：

- 3 年历史 + latest quarter；
- revenue、gross_profit、operating_profit、net_profit_attributable、扣非或 adjusted profit 字段；
- operating_cashflow、capex、net_cash/debt；
- gross_margin、net_margin、ROE、ROIC、turnover、leverage；
- non_recurring_items 与 adjusted_profit_bridge；
- cashflow_quality judgement，但必须区分事实和判断。

`business_breakdown_pack` 每条业务线至少覆盖：

- revenue、revenue_pct、growth_rate、gross_margin、gross_profit、gross_profit_pct；
- products、customers、capacity、orders；
- pricing_driver、cost_driver、linked_segments；
- evidence_ids、confidence、missing_reason。

## 验收标准

1. 缺业务收入或毛利率时允许 MISSING，但必须有 `missing_reason`。
2. 不得用公司整体收入替代业务线收入。
3. 不得用市场新闻证明业务利润贡献。
4. 所有判断必须回到 evidence / metric / source_gap。

## 测试命令

~~~bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_financial_business_packs.py
pytest tests/test_r5_financial_business_packs.py
~~~

## 输出要求

完成后请输出：

1. 新增 / 修改文件列表；
2. 测试命令和结果；
3. 简短 diff summary；
4. 未完成项和 source gap；
5. 一个 readout 文件，放入 `reports/p1_6/`。
