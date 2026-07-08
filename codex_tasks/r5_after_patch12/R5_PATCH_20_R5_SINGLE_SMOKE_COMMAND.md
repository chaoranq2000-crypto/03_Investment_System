# Patch 20：R5 MVP 单命令 smoke

任务文件：`R5_PATCH_20_R5_SINGLE_SMOKE_COMMAND.md`


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

R5 需要一个单一入口，方便每次 patch 后验证“格式、合同、fixture、composer、quality、readout”是否仍能闭环。

## 目标

新增一个 wrapper 命令：

```text
python scripts/run_r5_mvp_smoke.py
```

它按顺序执行：

1. R5 artifact format guard。
2. Patch inventory check。
3. R5 pack validators。
4. Composer fixture smoke。
5. Quality review fixture smoke。
6. Readout truthfulness gate。

## 建议新增文件

```text
scripts/run_r5_mvp_smoke.py
tests/test_run_r5_mvp_smoke.py
reports/p1_6/R5_PATCH_20_SINGLE_SMOKE_COMMAND_READOUT.md
```

## CLI 要求

```text
python scripts/run_r5_mvp_smoke.py --strict
python scripts/run_r5_mvp_smoke.py --json reports/p1_6/r5_mvp_smoke_result.json
```

## 验收标准

1. 任一子检查 fail，wrapper exit code 非 0。
2. JSON 输出包含每个子检查的 command、exit_code、duration、summary。
3. wrapper 不吞掉 stderr。
4. readout 记录完整结果。

## 建议测试命令

```text
python -m py_compile scripts/run_r5_mvp_smoke.py
python scripts/run_r5_mvp_smoke.py --strict --json reports/p1_6/r5_mvp_smoke_result.json
pytest -q tests/test_run_r5_mvp_smoke.py --tb=short
```
