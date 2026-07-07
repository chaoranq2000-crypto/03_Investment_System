# R5-MVP Patch 0 Plan — 目标说明与模板骨架

## 1. Patch 目标

本 patch 是 R5 重构的第一步，只做“目标、计划、模板、rubric、Codex 任务卡”。

它不实现完整 R5，不生成任何个股报告，不写运行代码，不修改历史 workflow run。

## 2. 为什么先做这个 patch

完整 R5 重构范围很大，直接让 Codex 一次性实现会导致：

```text
1. 改动过大，难以审查；
2. 多个 skill 同时变化，难以定位问题；
3. writer 可能越权创造研究结论；
4. TODO / MISSING_DISCLOSURE 可能被隐藏；
5. 样例质量没有工程化验收标准。
```

因此第一步必须先定义 R5-MVP 的边界。

## 3. 本 patch 新增文件

```text
docs/workflows/R5_MVP_RESTRUCTURE_PLAN.md
docs/workflows/R5_SAMPLE_QUALITY_STOCK_REPORT_SPEC.md
templates/r5_stock_research_pack.yaml
templates/r5_stock_research_note.md
benchmarks/r5_report_quality_rubric.yaml
reports/p1_6/R5_MVP_PATCH_0_PLAN.md
codex_tasks/R5_PATCH_0_TASK_CARD.md
```

## 4. 本 patch 不做什么

```text
1. 不修改 reports/workflow_runs/ 历史产物；
2. 不修改现有 R4 报告；
3. 不写 Python 脚本；
4. 不引入真实 API 调用；
5. 不生成任何股票研究报告；
6. 不计算盈利预测；
7. 不计算估值；
8. 不改 evidence-ingest / stock-deep-dive / quality-review 的执行逻辑；
9. 不声称 R5 已完成。
```

## 5. 验收标准

```text
1. 新增文件路径正确；
2. R5 与 R4 的区别说清楚；
3. R5 research pack 是事实源，R5 report note 是转译层；
4. R5 12 个子包已经定义；
5. R5 报告章节已经定义；
6. 降级规则已经定义；
7. no-advice 边界已经定义；
8. YAML 文件可被 yaml.safe_load 解析；
9. patch 不修改历史产物；
10. patch 没有把 TODO / MISSING_DISCLOSURE 写成事实。
```

## 6. 建议测试命令

```bash
python - <<'PY'
import yaml
for p in [
    "templates/r5_stock_research_pack.yaml",
    "benchmarks/r5_report_quality_rubric.yaml",
]:
    with open(p, "r", encoding="utf-8") as f:
        yaml.safe_load(f)
    print(f"yaml ok: {p}")
PY
```

## 7. 下一步 patch 建议

```text
Patch 1：stock-deep-dive B5-lite R5 research pack contract
```

Patch 1 目标：

```text
让 stock-deep-dive skill 知道如何消费 evidence 并输出 R5_stock_research_pack 的骨架。
```

Patch 1 允许范围建议：

```text
.agents/skills/stock-deep-dive/SKILL.md
.agents/skills/stock-deep-dive/references/r5_stock_deep_dive_contract.md
.agents/skills/stock-deep-dive/references/r5_business_breakdown_contract.md
.agents/skills/stock-deep-dive/references/r5_financial_history_contract.md
.agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml
reports/p1_6/R5_MVP_PATCH_1_PLAN.md
```

Patch 1 禁止范围建议：

```text
不写 forecast 计算；
不写 valuation 计算；
不改 evidence-ingest；
不改 quality-review；
不生成报告正文；
不修改 reports/workflow_runs/ 历史产物。
```
