# R5 Patch 5：technical / sentiment / catalyst pack schema validators

## 背景

样例报告包含技术分析、情绪分析和事件驱动。R5 不能让 writer 自由编这些内容，必须先有可校验的 technical_market_pack、sentiment_event_pack、catalyst_calendar。

## 目标

1. 新增 technical_market_pack contract / example / validator。
2. 新增 sentiment_event_pack contract / example / validator。
3. 新增 catalyst_calendar / event_scenario_matrix contract / example / validator。
4. 新增 pytest。
5. 输出 readout。

## 允许修改文件

- `.agents/skills/stock-deep-dive/references/r5_technical_market_pack_contract.md`
- `.agents/skills/stock-deep-dive/references/r5_sentiment_event_pack_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_technical_market_pack.example.yaml`
- `.agents/skills/stock-deep-dive/assets/r5_sentiment_event_pack.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_technical_market_pack.py`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_sentiment_event_pack.py`
- `tests/test_validate_r5_technical_market_pack.py`
- `tests/test_validate_r5_sentiment_event_pack.py`
- `reports/p1_6/R5_PATCH_5_TECH_SENTIMENT_CATALYST_READOUT.md`

## 禁止事项

- 不抓实时行情。
- 不写真实支撑/阻力位。
- 不写真实资金流或新闻判断。
- 不输出交易动作。
- 不把无 `as_of_date` 的信息用于交易状态判断。

## 交付物

- contracts。
- examples。
- validators。
- tests。
- readout。

## 验收标准

### Technical market pack

1. 必须有 `as_of_date`。
2. 至少支持字段：`current_price`、`return_1m`、`return_3m`、`return_6m`、`return_12m`、`ytd_return`、`52w_high`、`52w_low`、`MA5`、`MA10`、`MA20`、`MA60`、`turnover`、`volume_percentile`。
3. `support_levels` / `resistance_levels` 每项必须有 `level`、`basis`、`source_id_or_missing_reason`。
4. 缺 as_of_date 时 validator 应失败或降级。

### Sentiment / event pack

1. sentiment 必须分为 `macro_sentiment`、`industry_sentiment`、`company_sentiment`。
2. 每条 sentiment 判断必须有 `source_id`、`metric_id`、`claim_id` 或 `missing_reason`。
3. catalyst event 必须有 `event_date`、`event_name`、`impact_path`、`verification_metric`、`counterevidence_condition`。
4. event scenario 必须至少支持 `base`、`upside`、`downside`，允许 upside/downside 为 TODO。
5. pytest 通过。

## 测试命令

```bash
python .agents/skills/stock-deep-dive/scripts/validate_r5_technical_market_pack.py .agents/skills/stock-deep-dive/assets/r5_technical_market_pack.example.yaml
python .agents/skills/stock-deep-dive/scripts/validate_r5_sentiment_event_pack.py .agents/skills/stock-deep-dive/assets/r5_sentiment_event_pack.example.yaml
pytest tests/test_validate_r5_technical_market_pack.py tests/test_validate_r5_sentiment_event_pack.py
```

## 输出要求

1. 列出修改文件。
2. 粘贴测试结果。
3. 明确说明未接 live 数据。
4. 输出 readout 文件。
