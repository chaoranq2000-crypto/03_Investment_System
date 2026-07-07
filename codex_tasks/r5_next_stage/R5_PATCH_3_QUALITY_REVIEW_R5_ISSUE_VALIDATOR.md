# R5 Patch 3：quality-review R5 issue validator

## 背景

R5 需要明确 issue gate，而不是主观点评。当前 `quality-review` 已有 R5 gate 文档，但 scripts/assets 基本为空。本 patch 将 R5 issue schema 变成可执行校验。

## 目标

1. 固化 R5 issue schema。
2. 新增 R5 quality issues example。
3. 新增 `validate_quality_issues.py`。
4. 新增 pytest，确保 high issue 阻断 accepted、no-advice gate 存在、隐藏 TODO / unsupported numbers 被识别。
5. 输出 readout。

## 允许修改文件

- `.agents/skills/quality-review/SKILL.md`
- `.agents/skills/quality-review/references/issue_schema.md`
- `.agents/skills/quality-review/references/r5_quality_gate.md`
- `.agents/skills/quality-review/assets/r5_quality_issues.example.csv`
- `.agents/skills/quality-review/scripts/validate_quality_issues.py`
- `tests/test_validate_quality_issues.py`
- `reports/p1_6/R5_PATCH_3_QUALITY_REVIEW_READOUT.md`

## 禁止事项

- 不生成真实质量审查结论。
- 不修改历史 workflow run。
- 不把 `accepted_with_todos` 改写成 `accepted`。
- 不删除 TODO / source gap。
- 不输出交易建议。

## 交付物

- issue schema 更新。
- R5 quality gate 更新。
- example CSV。
- validator。
- tests。
- readout。

## 验收标准

1. issue schema 至少包含：`issue_id`、`severity`、`gate_id`、`stage`、`target_artifact`、`section`、`description`、`fix_owner_skill`、`blocking_decision`、`next_action`、`status`。
2. severity 枚举：`critical`、`high`、`medium`、`low`。
3. gate_id 至少覆盖：R5-G1 Evidence、R5-G2 Financial、R5-G3 Business、R5-G4 Industry、R5-G5 Forecast、R5-G6 Valuation、R5-G7 Technical、R5-G8 Sentiment/Event、R5-G9 Narrative、R5-G10 No-Advice、R5-G11 Benchmark。
4. high/critical issue 存在时，overall decision 不得为 `accepted`。
5. 缺 R5-G10 No-Advice gate 时 validator 失败。
6. issue status 枚举至少包括：`open`、`resolved`、`accepted_todo`、`waived_with_reason`。
7. pytest 通过。

## 测试命令

```bash
python .agents/skills/quality-review/scripts/validate_quality_issues.py .agents/skills/quality-review/assets/r5_quality_issues.example.csv --expected-decision accepted_with_todos
pytest tests/test_validate_quality_issues.py
```

## 输出要求

1. 列出修改文件。
2. 粘贴测试结果。
3. 说明 high issue 阻断逻辑。
4. 输出 readout 文件。
