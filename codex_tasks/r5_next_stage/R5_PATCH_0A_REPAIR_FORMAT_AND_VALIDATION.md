# R5 Patch 0A：修复 Patch 0 格式与可解析性

## 背景

当前仓库已经有 R5-MVP spec、templates、rubric 和 patch task card，但 raw 视图显示部分 Markdown / YAML 文件被压缩成单行，可能无法满足原 Patch 0 的 `yaml.safe_load` 验收要求。本 patch 只修格式、补最小格式测试，不改变 R5 的语义范围。

## 目标

1. 将 R5-MVP 相关 Markdown 文件整理为可读多行格式。
2. 将 R5 YAML 模板和 rubric 整理为标准 YAML，可被 `yaml.safe_load` 解析。
3. 新增一个最小 regression test，防止 R5 Patch 0 artifact 再次退化成单行不可读/不可解析状态。
4. 输出 readout，说明本 patch 只修格式和可解析性，不实现后续 R5 功能。

## 允许修改文件

- `docs/workflows/R5_SAMPLE_QUALITY_STOCK_REPORT_SPEC.md`
- `docs/workflows/R5_MVP_RESTRUCTURE_PLAN.md`
- `templates/r5_stock_research_pack.yaml`
- `templates/r5_stock_research_note.md`
- `benchmarks/r5_report_quality_rubric.yaml`
- `reports/p1_6/R5_MVP_PATCH_0_PLAN.md`
- `codex_tasks/R5_PATCH_0_TASK_CARD.md`
- `tests/test_r5_patch0_artifacts_parse.py`
- `reports/p1_6/R5_PATCH_0A_REPAIR_READOUT.md`

## 禁止事项

- 不新增 R5 validator 业务逻辑。
- 不新增真实个股报告。
- 不修改历史 `reports/workflow_runs/`。
- 不引入真实 API 调用。
- 不改变 R5 的章节、12 个 research subpack、降级规则和 no-advice 边界。
- 不把 TODO / MISSING_DISCLOSURE 写成事实。

## 交付物

- 格式化后的 R5 spec / plan / templates / rubric。
- `tests/test_r5_patch0_artifacts_parse.py`
- `reports/p1_6/R5_PATCH_0A_REPAIR_READOUT.md`

## 验收标准

1. `templates/r5_stock_research_pack.yaml` 可被 `yaml.safe_load` 解析。
2. `benchmarks/r5_report_quality_rubric.yaml` 可被 `yaml.safe_load` 解析。
3. `templates/r5_stock_research_note.md` 至少包含 8 个二级或一级 Markdown 标题。
4. R5 spec 明确保留 R4 与 R5 的区别、research pack 是事实源、12 个 subpack、10 个报告章节、降级规则、no-advice 边界。
5. readout 列出修改文件、测试命令、测试结果、未完成项、下一步建议。

## 测试命令

```bash
python - <<'PY'
import yaml
for p in ["templates/r5_stock_research_pack.yaml", "benchmarks/r5_report_quality_rubric.yaml"]:
    with open(p, "r", encoding="utf-8") as f:
        yaml.safe_load(f)
print("yaml ok")
PY
pytest tests/test_r5_patch0_artifacts_parse.py
```

## 输出要求

1. 列出新增/修改文件。
2. 粘贴测试命令和结果。
3. 给出 diff summary。
4. 明确说明没有实现 R5 validator / composer / dry-run。
