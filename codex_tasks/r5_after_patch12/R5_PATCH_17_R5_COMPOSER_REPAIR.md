# Patch 17：R5 composer 修复与 no-new-number 约束

任务文件：`R5_PATCH_17_R5_COMPOSER_REPAIR.md`


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

raw 检查显示 composer 文件存在疑似语法破坏。即使格式修复，也必须确保 composer 只是转译 R5 pack，不创造研究事实。

## 目标

修复 `src/report/stock_report_writer.py` 或现有 R5 composer，使其具备最小可执行能力：

```text
R5_stock_research_pack.yaml -> R5_stock_research_note.md
```

但 composer 不允许生成 pack 中不存在的新数字、新结论或交易建议。

## 功能要求

1. 读取 source-gapped R5 pack。
2. 生成九/十章结构 note。
3. 对缺失 pack 写入 `MISSING_DISCLOSURE` 或 `TODO_SOURCE_GAP`。
4. 自动附加 source gap appendix。
5. 自动附加 evidence id appendix。
6. no-advice sanitizer 阻断买入、卖出、持有、仓位、目标仓位等词。
7. 数字守门：报告中的关键数字必须来自 pack 原文或 pack 的 allowed_render_values。

## 禁止事项

- 不调用 LLM。
- 不生成真实个股观点。
- 不隐藏缺口。
- 不把 sample rubric 分数写成投资评级。

## 验收标准

1. valid fixture 可生成 note。
2. missing forecast fixture 降级为 research draft。
3. pack 外新增数字 fixture 被测试捕获。
4. no-advice fixture 被阻断。
5. 输出 note 章节完整，缺口可见。

## 建议测试命令

```text
python -m py_compile src/report/stock_report_writer.py
pytest -q tests/test_stock_report_writer.py --tb=short
```

## 交付物

```text
reports/p1_6/R5_PATCH_17_COMPOSER_REPAIR_READOUT.md
```
