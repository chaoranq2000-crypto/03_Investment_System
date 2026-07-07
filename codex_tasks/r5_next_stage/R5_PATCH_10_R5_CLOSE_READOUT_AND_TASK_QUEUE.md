# R5 Patch 10：R5 close readout 与 task queue 模板

## 背景

R5 任务较多，必须避免 Codex 完成某个 patch 后没有清晰收口。每个 patch 和每次 dry-run 都应输出 readout、source gap、open questions、next task queue。

## 目标

1. 新增 R5 workflow close readout 模板。
2. 新增 R5 source gap report 模板。
3. 新增 R5 open questions 模板。
4. 新增 R5 task queue 模板。
5. 新增简单测试，确保模板包含必需章节。
6. 输出 readout。

## 允许修改文件

- `templates/r5_workflow_close_readout.md`
- `templates/r5_source_gap_report.md`
- `templates/r5_open_questions.md`
- `templates/r5_task_queue.md`
- `tests/test_r5_close_readout_templates.py`
- `reports/p1_6/R5_PATCH_10_CLOSE_READOUT_TEMPLATE_READOUT.md`

## 禁止事项

- 不关闭真实 workflow。
- 不修改历史 workflow run。
- 不生成真实股票报告。
- 不隐藏 source gap。
- 不输出交易建议。

## 交付物

- close readout 模板。
- source gap 模板。
- open questions 模板。
- task queue 模板。
- tests。
- readout。

## 验收标准

1. close readout 模板必须包含：scope、artifacts、tests、quality decision、open issues、source gaps、next tasks、rollback notes。
2. source gap 模板必须包含：gap_id、section、missing_metric_or_claim、searched_sources、current_status、downgrade_effect、next_action。
3. open questions 模板必须包含：question_id、owner_skill、blocking_stage、evidence_needed、fallback_decision。
4. task queue 模板必须包含：task_id、patch_name、allowed_files、blocked_files、tests、acceptance、status。
5. pytest 通过。

## 测试命令

```bash
pytest tests/test_r5_close_readout_templates.py
```

## 输出要求

1. 列出修改文件。
2. 粘贴测试结果。
3. 输出 readout 文件。
