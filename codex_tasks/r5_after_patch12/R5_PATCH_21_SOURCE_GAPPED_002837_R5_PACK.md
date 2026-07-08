# Patch 21：002837 source-gapped R5 pack pilot

任务文件：`R5_PATCH_21_SOURCE_GAPPED_002837_R5_PACK.md`


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

只有在 Patch 13-20 通过后，才允许做一个受控真实样本前置 pilot。该 pilot 使用已有 002837 工作流资产，不新增真实 API 抓取，不生成 sample-quality 投资报告。

## 目标

基于已有 002837 / 英维克 R4 及质量门产物，生成一个 `source-gapped` 的 R5 research pack 草案，用于验证 pack schema 和缺口显示。

## 建议新增文件

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_pack_source_gapped.yaml
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_source_gap_report.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_open_questions.md
reports/p1_6/R5_PATCH_21_SOURCE_GAPPED_002837_PACK_READOUT.md
```

## 限制

- 只能使用仓库已有产物。
- 缺 forecast / valuation / market / sentiment 时必须显式 MISSING。
- 不生成 `R5_stock_research_note.md` 正文报告，除非命名为 draft 且缺口显式展示。
- 不写买入 / 卖出 / 持有 / 仓位建议。

## 验收标准

1. pack 能通过 R5 validator。
2. pack 的 status 不得为 sample-quality。
3. source gap report 列出缺失 forecast、valuation、market、sentiment 的数据项。
4. open questions 可以直接变成 evidence-ingest 下一步任务。

## 建议测试命令

```text
python .agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_pack_source_gapped.yaml
python scripts/run_r5_mvp_smoke.py --strict
```
