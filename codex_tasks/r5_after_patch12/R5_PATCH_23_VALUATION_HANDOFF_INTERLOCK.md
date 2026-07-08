# Patch 23：company-valuation 到 R5 valuation_pack 的交接门

任务文件：`R5_PATCH_23_VALUATION_HANDOFF_INTERLOCK.md`


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

R5 valuation pack 不应该由 writer 自由生成。需要把 company-valuation skill 的输出接入 R5 valuation_pack，同时保持 no-advice 和 source-gap 边界。

## 目标

新增 valuation handoff interlock 契约和 validator。

## 建议新增文件

```text
.agents/skills/company-valuation/references/r5_valuation_handoff_contract.md
.agents/skills/company-valuation/assets/r5_valuation_handoff.example.yaml
scripts/validate_r5_valuation_handoff.py
tests/test_validate_r5_valuation_handoff.py
reports/p1_6/R5_PATCH_23_VALUATION_HANDOFF_INTERLOCK_READOUT.md
```

## 契约字段

```yaml
valuation_as_of_date:
market_snapshot:
peer_context:
method_used:
scenario_values:
assumptions:
sensitivity:
source_evidence_ids:
missing_items:
no_advice_statement:
```

## 规则

- 缺 current price / market cap / share count 时不得通过 R5 valuation gate。
- 缺 peer context 时必须降级。
- target price 只能作为 valuation scenario，不得变成买卖建议。
- 所有 valuation numbers 必须有 evidence_id、assumption_id 或 missing_reason。

## 建议测试命令

```text
python -m py_compile scripts/validate_r5_valuation_handoff.py
pytest -q tests/test_validate_r5_valuation_handoff.py --tb=short
```
