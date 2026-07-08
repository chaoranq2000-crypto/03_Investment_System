# Patch 14：R5 格式守门脚本与 smoke 命令

任务文件：`R5_PATCH_14_R5_FORMAT_GUARD_AND_SMOKE_COMMAND.md`


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

Patch 13 修复的是当前文件。Patch 14 要防止同类“物理单行文件”“惰化脚本”“空测试”再次进入仓库。

## 目标

新增持久化格式守门脚本，检查 R5 关键文件的物理换行、YAML 可解析性、Python 可编译性、Markdown 标题密度和 pytest 测试可收集性。

## 建议新增文件

```text
scripts/check_r5_artifact_format.py
tests/test_check_r5_artifact_format.py
reports/p1_6/R5_PATCH_14_FORMAT_GUARD_READOUT.md
```

## 守门规则

脚本至少检查：

1. R5 关键 YAML 文件不允许只有 1 行。
2. R5 关键 Python 文件不允许只有 1 行。
3. shebang 行之后必须有真实换行。
4. Python 文件必须能 `py_compile`。
5. YAML 文件必须能 `yaml.safe_load`。
6. Markdown 模板必须至少包含指定数量的 `#` 标题行。
7. 测试文件必须包含至少一个 `def test_` 或等价 pytest 测试类。
8. 文件中不得出现大规模字面量 `\n` 代替真实换行。

## CLI 建议

```text
python scripts/check_r5_artifact_format.py --strict
python scripts/check_r5_artifact_format.py --json reports/p1_6/r5_format_guard.json
```

## 禁止事项

- 不修复业务逻辑。
- 不扩大到全仓库所有文件，只检查 R5 关键文件清单。
- 不把 guard 做成只打印 warning；strict 模式必须用非 0 退出码阻断。

## 验收标准

1. 在当前修复后的仓库中 strict 模式通过。
2. 单元测试覆盖至少 3 类失败样例：one-line python、one-line yaml、empty test。
3. readout 包含命令、退出码、输出摘要。

## 建议测试命令

```text
python -m py_compile scripts/check_r5_artifact_format.py
python scripts/check_r5_artifact_format.py --strict
pytest -q tests/test_check_r5_artifact_format.py --tb=short
```
