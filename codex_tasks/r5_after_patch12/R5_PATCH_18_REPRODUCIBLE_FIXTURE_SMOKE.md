# Patch 18：R5 可复现 fixture smoke

任务文件：`R5_PATCH_18_REPRODUCIBLE_FIXTURE_SMOKE.md`


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

R5 不能只靠单个脚本测试。需要一个完整但虚拟的 fixture，从 pack validation 到 composer 到 quality review 形成可复现 smoke。

## 目标

新增一个不包含真实投资结论的 R5 fixture workflow。

## 建议新增文件

```text
tests/fixtures/r5_mvp_valid_source_gapped_pack.yaml
tests/fixtures/r5_mvp_invalid_missing_valuation_pack.yaml
tests/fixtures/r5_mvp_invalid_hidden_source_gap.yaml
tests/expected/r5_mvp_valid_source_gapped_note.md
tests/test_r5_mvp_fixture_smoke.py
reports/p1_6/R5_PATCH_18_REPRODUCIBLE_FIXTURE_SMOKE_READOUT.md
```

## Smoke 流程

```text
validate_r5_stock_research_pack
-> validate_forecast_model
-> validate_valuation_pack
-> compose note
-> run stock_report_quality_review
-> compare required sections / visible gaps / no-advice
```

## 验收标准

1. valid source-gapped fixture 通过并生成 note。
2. invalid missing valuation fixture 被阻断或降级。
3. hidden source gap fixture 被阻断。
4. note 中必须显示 source gap appendix。
5. note 中不出现买入、卖出、持有、仓位建议。

## 建议测试命令

```text
pytest -q tests/test_r5_mvp_fixture_smoke.py --tb=short
```
