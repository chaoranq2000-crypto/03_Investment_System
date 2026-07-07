# R5 Patch 12：company-valuation mini validator

## 背景

`company-valuation` skill 已存在，R5 valuation pack 可以交给该 skill 作为子任务。但当前缺少输出 validator。本 patch 只做 company-valuation output 的最小校验，不做真实估值。

## 目标

1. 新增 company valuation output example。
2. 新增 validator。
3. 新增 pytest。
4. 将 valuation output 与 R5 valuation pack 字段对齐。
5. 输出 readout。

## 允许修改文件

- `.agents/skills/company-valuation/references/valuation_model_contract.md`
- `.agents/skills/company-valuation/assets/valuation_output.example.yaml`
- `.agents/skills/company-valuation/scripts/validate_valuation_output.py`
- `tests/test_validate_company_valuation_output.py`
- `reports/p1_6/R5_PATCH_12_COMPANY_VALUATION_VALIDATOR_READOUT.md`

## 禁止事项

- 不填真实估值数字。
- 不输出投资评级、交易动作或仓位建议。
- 不接行情 API。
- 不修改真实 valuation artifacts。
- 不把 missing market snapshot 写成已完成。

## 交付物

- valuation output example。
- validator。
- tests。
- readout。

## 验收标准

1. valuation output 至少包含：`valuation_as_of_date`、`input_status`、`market_snapshot`、`peer_set`、`method_selection`、`scenario_outputs`、`sensitivity`、`source_gap`、`no_advice_disclaimer`。
2. `input_status` 枚举至少包括：`complete`、`partial_with_todos`、`blocked`。
3. 缺 market snapshot 时，`input_status` 不得为 `complete`。
4. scenario 输出必须有 `base`，bull/bear 可 TODO。
5. 每个估值数字必须有 `assumption_id` 或 `missing_reason`。
6. pytest 通过。

## 测试命令

```bash
python .agents/skills/company-valuation/scripts/validate_valuation_output.py .agents/skills/company-valuation/assets/valuation_output.example.yaml
pytest tests/test_validate_company_valuation_output.py
```

## 输出要求

1. 列出修改文件。
2. 粘贴测试结果。
3. 明确说明未做真实估值。
4. 输出 readout 文件。
