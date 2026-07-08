# Patch 16：R5 validators 语义加固

任务文件：`R5_PATCH_16_R5_VALIDATOR_SEMANTIC_HARDENING.md`


## 全局禁止事项

- 不生成任何真实个股的投资结论。
- 不输出买入、卖出、持有、建仓、清仓、目标仓位等建议。
- 不把 `TODO_*`、`MISSING_DISCLOSURE`、`source_gap` 写成事实。
- 不接入真实 API，不新增外部付费数据依赖。
- 不修改历史 workflow run 的研究结论；fixture 文件除外。
- 不把 readout 写成没有命令、没有退出码、没有测试结果的叙述。
- 不在一个 patch 中顺手实现下一张任务卡。

## 全局交付要求

每张任务卡完成后必须新增对应 readout，readout 至少包含：

```text
status
files_added
files_modified
commands_run
exit_codes
stdout_or_stderr_summary
known_todos
next_recommended_patch
```

所有新增 / 修改的 Python 文件必须能通过：

```text
python -m py_compile <file>
```

所有新增 / 修改的 YAML 文件必须能通过：

```text
python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('<file>').read_text(encoding='utf-8'))"
```



## 背景

格式恢复后，需要确认 validators 不是只检查文件存在，而是真正阻断不可信 R5 pack。

## 目标

加固以下 validators 的语义规则：

```text
.agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py
.agents/skills/segment-company-mapping/scripts/validate_segment_exposure.py
.agents/skills/quality-review/scripts/validate_quality_issues.py
.agents/skills/stock-deep-dive/scripts/validate_valuation_pack.py
.agents/skills/stock-deep-dive/scripts/validate_forecast_model.py
```

## 必须覆盖的规则

### R5 stock research pack

- 必须有 12 个 pack。
- `forecast_model_pack` 缺失时不得 sample-quality。
- `valuation_pack.market_snapshot` 缺失时不得 sample-quality。
- `technical_market_pack.as_of_date` 缺失时不能写交易状态判断。
- `sentiment_event_pack.as_of_date` 缺失时不能写短期情绪判断。
- `source_gap` 不得为空白隐藏。

### segment exposure

- `exposure_score` 必须有 evidence、claim 或 TODO。
- `revenue_pct` / `profit_pct` 缺失时必须为显式 MISSING。
- 不允许把公司总收入误当作 segment 收入。

### quality issues

- `severity=high` 时 overall decision 不能为 accepted。
- issue 必须有 fix owner。
- no-advice gate 必须存在。

### forecast / valuation

- 预测值必须有 assumption_id 或 missing_reason。
- valuation 必须标注 as_of_date。
- peer comparison 缺失时必须降级。

## 验收标准

1. 所有 invalid fixture 被 validator 拒绝。
2. 所有 valid source-gapped fixture 被 validator 接受但保留 TODO。
3. readout 写出每类语义规则对应的测试。

## 建议测试命令

```text
pytest -q tests/test_validate_r5_stock_research_pack.py tests/test_validate_segment_exposure.py tests/test_validate_quality_issues.py tests/test_validate_forecast_model.py tests/test_validate_valuation_pack.py --tb=short
```

## 交付物

```text
reports/p1_6/R5_PATCH_16_VALIDATOR_SEMANTIC_HARDENING_READOUT.md
```
