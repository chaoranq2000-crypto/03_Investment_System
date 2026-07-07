# R5 Patch 6：R5 report composer skeleton

## 背景

R5 report note 应该由 research pack 转译而来，writer 不应创造事实、数字或判断。本 patch 只做 composer skeleton 和 fixture 测试，不生成真实个股报告。

## 目标

1. 新增 R5 report composer contract。
2. 新增轻量 composer 脚本，从 fixture pack 转译成 Markdown note。
3. composer 必须保留 source gap / TODO，不得隐藏缺口。
4. composer 不得输出交易动作、仓位建议或直接评级。
5. 新增 pytest。
6. 输出 readout。

## 允许修改文件

- `.agents/skills/stock-deep-dive/references/r5_report_composer_contract.md`
- `.agents/skills/stock-deep-dive/scripts/compose_r5_report_from_pack.py`
- `.agents/skills/stock-deep-dive/assets/r5_stock_research_note.fixture.md`
- `tests/test_compose_r5_report_from_pack.py`
- `reports/p1_6/R5_PATCH_6_COMPOSER_READOUT.md`

## 禁止事项

- 不生成真实股票报告。
- 不读取 live 数据。
- 不根据公司名称补充模型自有知识。
- 不在报告中创造 pack 以外的数字。
- 不把 TODO / MISSING_DISCLOSURE 写成事实。
- 不输出交易建议。

## 交付物

- composer contract。
- composer script。
- fixture output。
- tests。
- readout。

## 验收标准

1. composer 输入为 `R5_stock_research_pack.yaml`，输出为 `R5_stock_research_note.md`。
2. 输出章节必须包含：前言、财务概览、业务拆分、行业分析、盈利预测、估值分析、技术分析、情绪分析、事件驱动、研究结论、source gap appendix。
3. 若 pack_status 不为 `sample_quality_candidate`，note 标题或 metadata 必须标记为 `research_draft` 或 `blocked`，不得伪装成 sample-quality。
4. 所有 TODO / MISSING / UNVERIFIED 必须出现在 source gap appendix。
5. composer 不得新增 pack 中不存在的数值。
6. pytest 通过。

## 测试命令

```bash
python .agents/skills/stock-deep-dive/scripts/compose_r5_report_from_pack.py \
  .agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml \
  /tmp/R5_stock_research_note.fixture.md
pytest tests/test_compose_r5_report_from_pack.py
```

## 输出要求

1. 列出修改文件。
2. 粘贴测试结果。
3. 说明 composer 的降级行为。
4. 输出 readout 文件。
