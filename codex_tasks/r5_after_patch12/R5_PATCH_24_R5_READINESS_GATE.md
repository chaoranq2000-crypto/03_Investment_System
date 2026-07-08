# Patch 24：R5 readiness gate

任务文件：`R5_PATCH_24_R5_READINESS_GATE.md`


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

完成 Patch 13-23 后，需要一个明确的阶段性验收门，决定是否可以进入真实 R5 source-gapped sample pilot，或继续修复。

## 目标

新增 R5 readiness gate，整合格式、inventory、validator、composer、quality、readout、source-gapped pilot、evidence plan、valuation handoff 的状态。

## 建议新增文件

```text
scripts/r5_readiness_gate.py
configs/r5_readiness_gate_rules.yaml
tests/test_r5_readiness_gate.py
reports/p1_6/R5_PATCH_24_READINESS_GATE_READOUT.md
```

## 决策标签

```text
R5_READY_FOR_SOURCE_GAPPED_REAL_SAMPLE_PILOT
R5_CONTRACTS_EXECUTABLE_WITH_TODOS_ONLY
R5_NEEDS_MORE_REPAIR
R5_BLOCKED
```

## Gate 规则

- Patch 13-20 任一 fail：`R5_BLOCKED`。
- Patch 21 source-gapped pack 通过但缺 forecast / valuation：`R5_CONTRACTS_EXECUTABLE_WITH_TODOS_ONLY`。
- Evidence plan 和 valuation handoff 都可执行，且 source gaps 显式：`R5_READY_FOR_SOURCE_GAPPED_REAL_SAMPLE_PILOT`。
- no-advice gate fail：`R5_BLOCKED`。

## 建议测试命令

```text
python -m py_compile scripts/r5_readiness_gate.py
python scripts/r5_readiness_gate.py --json reports/p1_6/r5_readiness_gate_result.json
pytest -q tests/test_r5_readiness_gate.py --tb=short
```

## 最终 readout 要求

`R5_PATCH_24_READINESS_GATE_READOUT.md` 必须明确说明：

1. 是否可进入真实 R5 source-gapped sample pilot。
2. 是否仍禁止 sample-quality 报告。
3. 是否仍禁止 P2。
4. 哪些 TODO 是 blocker，哪些是 non-blocker。
