# R5 Patch 4：forecast / valuation schema validators

## 背景

样例级个股报告的关键差距是盈利预测和估值。当前已有 forecast/valuation contract 雏形，但缺独立 example 与 validator。本 patch 只定义字段、校验和降级规则，不做预测模型。

## 目标

1. 新增 R5 forecast model contract / example / validator。
2. 新增 R5 valuation pack contract / example / validator。
3. 新增 pytest，覆盖 2026E-2028E、assumption/missing_reason、market_snapshot、peer context。
4. 输出 readout。

## 允许修改文件

- `.agents/skills/stock-deep-dive/references/r5_forecast_model_contract.md`
- `.agents/skills/stock-deep-dive/references/r5_valuation_pack_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_forecast_model.example.yaml`
- `.agents/skills/stock-deep-dive/assets/r5_valuation_pack.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_forecast_model.py`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_valuation_pack.py`
- `tests/test_validate_r5_forecast_model.py`
- `tests/test_validate_r5_valuation_pack.py`
- `reports/p1_6/R5_PATCH_4_FORECAST_VALUATION_READOUT.md`

## 禁止事项

- 不做真实盈利预测。
- 不填真实股票数字。
- 不接行情 API。
- 不输出交易建议。
- 不把同业估值缺失写成已完成。
- 不修改 `reports/workflow_runs/`。

## 交付物

- forecast contract / example / validator / test。
- valuation contract / example / validator / test。
- readout。

## 验收标准

### Forecast

1. forecast 至少覆盖 `2026E`、`2027E`、`2028E`。
2. 每年必须有 `revenue`、`gross_margin`、`net_profit_attributable`、`eps`。
3. 每个预测值必须有 `assumption_id` 或 `missing_reason`。
4. 至少支持 `base_case`、`bull_case`、`bear_case`，但允许 bull/bear 为 TODO；base_case 必须存在。
5. 敏感性表字段至少包括 `driver`、`change`、`impact_metric`、`impact_value`、`assumption_id_or_missing_reason`。

### Valuation

1. valuation pack 必须有 `market_snapshot`：`as_of_date`、`current_price`、`market_cap`、`share_count`。
2. multiples 至少支持 `PE_TTM`、`forward_PE`、`PB`、`PS`。
3. peer context 必须有 `peer_set`、`peer_multiples` 或 `missing_reason`。
4. 缺 market_snapshot 时，不允许 sample-quality。
5. valuation scenario 必须标明 `method`、`key_assumptions`、`source_ids_or_missing_reason`。
6. pytest 通过。

## 测试命令

```bash
python .agents/skills/stock-deep-dive/scripts/validate_r5_forecast_model.py .agents/skills/stock-deep-dive/assets/r5_forecast_model.example.yaml
python .agents/skills/stock-deep-dive/scripts/validate_r5_valuation_pack.py .agents/skills/stock-deep-dive/assets/r5_valuation_pack.example.yaml
pytest tests/test_validate_r5_forecast_model.py tests/test_validate_r5_valuation_pack.py
```

## 输出要求

1. 列出修改文件。
2. 粘贴测试结果。
3. 说明本 patch 不做真实预测和估值判断。
4. 输出 readout 文件。
