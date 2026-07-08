# Patch 13：R5 格式、换行与语法恢复

任务文件：`R5_PATCH_13_FORMAT_SYNTAX_RECOVERY.md`


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

Patch 1-12 已经推送，但 GitHub raw 检查显示多个关键文件为物理单行或近似单行文件。R5 当前最大风险不是功能缺失，而是脚本、模板、测试不可解析或不可执行。

## 目标

本 patch 只做格式恢复和语法恢复，不新增 R5 业务逻辑。

需要恢复的重点文件包括但不限于：

```text
templates/r5_stock_research_pack.yaml
templates/r5_stock_research_note.md
benchmarks/r5_report_quality_rubric.yaml
.agents/skills/stock-deep-dive/assets/r5_stock_research_pack.valid.example.yaml
.agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py
.agents/skills/segment-company-mapping/scripts/validate_segment_exposure.py
.agents/skills/quality-review/scripts/validate_quality_issues.py
src/research/forecast_model_builder.py
src/research/valuation_pack_builder.py
src/research/technical_snapshot_builder.py
src/research/sentiment_event_pack_builder.py
src/report/stock_report_writer.py
src/qa/stock_report_quality_review.py
tests/test_r5_patch0_artifacts_parse.py
tests/test_validate_r5_stock_research_pack.py
tests/test_validate_segment_exposure.py
tests/test_stock_report_writer.py
tests/test_stock_report_quality_review.py
tests/test_valuation_input_contract.py
tests/test_technical_snapshot_builder.py
```

## 允许修改

- 上述文件。
- 与上述文件一一对应的 readout。
- 仅为修复 import path 或测试收集所必需的轻量配置。

## 禁止修改

- 不新增真实数据抓取。
- 不改研究结论。
- 不改变 R5 schema 的语义字段，除非原文件因折行丢失而无法表达原意。
- 不把 formatter / linter 引入为仓库强制依赖。

## 验收标准

1. 关键 Markdown 文件具有真实标题换行，不再是一行塞满全部章节。
2. 关键 YAML 文件可以 `yaml.safe_load`。
3. 关键 Python 文件可以 `python -m py_compile`。
4. pytest 能收集到 R5 相关测试，不允许空测试文件伪通过。
5. 修复 readout 明确列出每个修复文件的 before / after line count。

## 建议测试命令

```text
python -c "from pathlib import Path; files=['templates/r5_stock_research_pack.yaml','templates/r5_stock_research_note.md','benchmarks/r5_report_quality_rubric.yaml']; [print(p, len(Path(p).read_text(encoding='utf-8').splitlines())) for p in files]"
python -c "import yaml, pathlib; [yaml.safe_load(pathlib.Path(p).read_text(encoding='utf-8')) for p in ['templates/r5_stock_research_pack.yaml','benchmarks/r5_report_quality_rubric.yaml']]; print('yaml ok')"
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py .agents/skills/segment-company-mapping/scripts/validate_segment_exposure.py .agents/skills/quality-review/scripts/validate_quality_issues.py src/research/forecast_model_builder.py src/report/stock_report_writer.py src/qa/stock_report_quality_review.py
pytest -q tests/test_r5_patch0_artifacts_parse.py tests/test_validate_r5_stock_research_pack.py tests/test_validate_segment_exposure.py tests/test_stock_report_writer.py tests/test_stock_report_quality_review.py --tb=short
```

## 交付物

```text
reports/p1_6/R5_PATCH_13_FORMAT_SYNTAX_RECOVERY_READOUT.md
```
