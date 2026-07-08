# Patch 19：Readout truthfulness gate

任务文件：`R5_PATCH_19_READOUT_TRUTHFULNESS_GATE.md`


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

当前 readout 声称测试通过，但 raw 文件显示可执行性异常。需要防止 readout 只写“通过”而没有可核验命令和结果。

## 目标

新增 readout truthfulness gate，检查 R5 patch readout 是否包含可审计测试证据。

## 建议新增文件

```text
scripts/check_r5_readout_truthfulness.py
configs/r5_readout_truthfulness_rules.yaml
tests/test_r5_readout_truthfulness.py
reports/p1_6/R5_PATCH_19_READOUT_TRUTHFULNESS_GATE_READOUT.md
```

## 规则

每份 R5 patch readout 必须包含：

```text
status
files_added
files_modified
commands_run
exit_code for each command
stdout_or_stderr_summary
pytest summary if pytest was run
artifact hash or line count for critical files
known_todos
```

禁止仅出现：

```text
pytest passed
all tests passed
validation ok
```

而没有命令和退出码。

## 验收标准

1. 对缺少 commands_run 的 readout 报 fail。
2. 对只有“passed”但没有 exit code 的 readout 报 fail。
3. 对合法 readout 报 pass。
4. 可以检查 `reports/p1_6/R5_PATCH_*_READOUT.md`。

## 建议测试命令

```text
python -m py_compile scripts/check_r5_readout_truthfulness.py
python scripts/check_r5_readout_truthfulness.py --glob 'reports/p1_6/R5_PATCH_*_READOUT.md'
pytest -q tests/test_r5_readout_truthfulness.py --tb=short
```
