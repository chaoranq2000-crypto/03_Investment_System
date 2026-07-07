# Codex Task Card — R5 Patch 0：目标说明与模板骨架

## 任务名称

R5-MVP 目标说明与模板骨架补丁。

## 背景

当前工作区处于 P1.6 / R4 到 R5 的过渡阶段。目标是生成样例质量的个股研究报告，但不能一次性实现完整 R5。第一步只定义 R5 的目标、边界、研究包模板、报告模板和质量 rubric。

## 目标

请应用本补丁，或按本任务卡创建等价文件：

```text
1. 新增 R5-MVP 总计划；
2. 新增 R5 sample-quality report spec；
3. 新增 R5_stock_research_pack.yaml 模板；
4. 新增 R5_stock_research_note.md 模板；
5. 新增 R5 report quality rubric；
6. 新增 Patch 0 readout / plan。
```

## 允许新增 / 修改文件

```text
docs/workflows/R5_MVP_RESTRUCTURE_PLAN.md
docs/workflows/R5_SAMPLE_QUALITY_STOCK_REPORT_SPEC.md
templates/r5_stock_research_pack.yaml
templates/r5_stock_research_note.md
benchmarks/r5_report_quality_rubric.yaml
reports/p1_6/R5_MVP_PATCH_0_PLAN.md
codex_tasks/R5_PATCH_0_TASK_CARD.md
```

## 禁止事项

```text
1. 不修改 reports/workflow_runs/ 历史 run；
2. 不修改已有 R4 报告产物；
3. 不写 Python 脚本；
4. 不新增真实 API 调用；
5. 不生成任何股票研究报告；
6. 不计算 forecast；
7. 不计算 valuation；
8. 不把 TODO / MISSING_DISCLOSURE 写成事实；
9. 不声称 R5 已完成；
10. 不输出直接交易指令或仓位建议。
```

## R5 spec 必须包含

```text
1. R4_internal_draft 与 R5_sample_quality_note 的区别；
2. R5_stock_research_pack 是事实源，R5_stock_research_note 只是转译；
3. R5 固定章节结构；
4. R5 research pack 的 12 个子包；
5. 降级规则；
6. no-advice 边界；
7. writer 不创造研究结论的原则。
```

## 验收标准

```text
1. 文件存在且路径正确；
2. Markdown 标题层级清晰；
3. YAML 可被解析；
4. 不修改历史产物；
5. readout / plan 列出本 patch 做了什么、没做什么、下一步建议；
6. 如果无法完成某项，保留 TODO，不要编造。
```

## 建议测试命令

```bash
python - <<'PY'
import yaml
for p in [
    "templates/r5_stock_research_pack.yaml",
    "benchmarks/r5_report_quality_rubric.yaml",
]:
    with open(p, "r", encoding="utf-8") as f:
        yaml.safe_load(f)
    print("yaml ok", p)
PY
```

## 输出要求

完成后请输出：

```text
1. 新增 / 修改文件列表；
2. 测试命令和结果；
3. 简短 diff summary；
4. 未完成项；
5. 下一步建议，但不要继续执行下一步。
```
