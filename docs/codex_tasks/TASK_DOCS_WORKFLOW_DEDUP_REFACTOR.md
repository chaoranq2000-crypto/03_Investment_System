# TASK — Docs / Skills Workflow 去重重构

## 任务目标

执行一次低复杂度重构，解决当前 `docs/workflows/` 与 `.agents/skills/*/SKILL.md` 同时定义 workflow 的问题。

目标不是增加新文档，而是落实：

```text
RESEARCH_WORKFLOW.md = global workflow kernel
SKILL.md = local execution contract
references/ = runtime schema / local profile / field-level detail
```

## 必须遵守

1. 不修改样例个股报告观点。
2. 不删除 `docs/plans/`、`docs/logs/`、`docs/codex_tasks/`。
3. 不新增新的 `workflow_type`。
4. 不让 skill docs 定义 global `workflow_type`、global `stage_id`、global `gate_id`。
5. 不输出直接买卖建议、仓位建议或交易指令。
6. 长期 Markdown 文档要保持可读 diff，避免整篇压成超长行。

## 输入材料

先阅读：

```text
AGENTS.md
docs/meta/DOC_OWNERSHIP_MATRIX.md
docs/workflows/RESEARCH_WORKFLOW.md
docs/workflows/README.md
docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md
docs/workflows/STOCK_REPORT_PRODUCTION_WORKFLOW.md
.agents/skills/research-orchestrator/SKILL.md
.agents/skills/stock-deep-dive/SKILL.md
.agents/skills/quality-review/SKILL.md
docs/index.md
docs/meta/TOP_LEVEL_DOCS_INDEX.md
```

然后参考补丁包：

```text
02_CODEX_EXECUTION_PLAN.md
03_ACCEPTANCE_CHECKLIST.md
04_FILE_MOVE_PLAN.md
overlays/
replacement_sections/
```

## 具体执行步骤

### Step 1 — 基线扫描

运行并记录：

```bash
git grep -n "workflow_type:" -- . ':!docs/plans' ':!docs/logs'
git grep -n "stock_report_production" -- . ':!docs/plans' ':!docs/logs'
git grep -n "G1[1-9]" -- docs .agents ':!docs/plans' ':!docs/logs' ':!docs/codex_tasks'
git grep -n "WORKFLOW_ORCHESTRATION_SPEC" -- . ':!docs/plans' ':!docs/logs'
```

### Step 2 — 更新 ownership

修改 `docs/meta/DOC_OWNERSHIP_MATRIX.md`，明确：

```text
workflow_type / stage_id / gate_id / backflow_decision / run status enum
只由 docs/workflows/RESEARCH_WORKFLOW.md 定义。
```

### Step 3 — 更新 `RESEARCH_WORKFLOW.md`

将其收敛为 workflow kernel：

```text
- 五类永久 workflow_type
- 明确 stock_report_production 是 profile_id，不是 workflow_type
- 明确 workflow_diagnostic 是 non-run mode，不是永久 workflow_type
- 用 G0-G10 作为唯一 global gate 表
```

使用 `replacement_sections/RESEARCH_WORKFLOW_quality_gates_G0_G10.md` 替换旧 gate 段落。

### Step 4 — 降级 `WORKFLOW_ORCHESTRATION_SPEC.md`

新建：

```text
.agents/skills/research-orchestrator/references/orchestration_contract.md
```

将 runtime contract 内容迁入该文件。

将原文件改为 compatibility pointer：

```text
docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md
```

不得在 pointer 中定义 workflow_type / stage_id / gate_id。

### Step 5 — 精简 `research-orchestrator/SKILL.md`

按 `overlays/.agents/skills/research-orchestrator/SKILL.md` 重写或局部重构。

要求：

```text
- 只保留执行入口、读取事实源、创建/更新 run、写 handoff、路由、close readout。
- 不复制完整 schema、stage table、gate table。
- Must-read 改为 Always read / Read when needed。
```

### Step 6 — 将 stock report production 迁移为 profile

新建：

```text
.agents/skills/stock-deep-dive/references/report_production_profile.md
```

使用 overlay 草案。

将旧文件：

```text
docs/workflows/STOCK_REPORT_PRODUCTION_WORKFLOW.md
```

改为 compatibility pointer。

更新 `stock-deep-dive/SKILL.md` must-read references，加入：

```text
references/report_production_profile.md
```

### Step 7 — 修正 quality gate 漂移

更新：

```text
.agents/skills/quality-review/SKILL.md
```

要求：

```text
- 不定义新的 global G 编号。
- G10 只保留为 `RESEARCH_WORKFLOW.md` 的 Close Gate。
- 原 data-layer pack 局部检查改为 `subcheck_id: G7-DL`。
- 原 R4 publishable stock report 局部检查改为 `subcheck_id: G7-R4`。
```

### Step 8 — 更新导航

更新：

```text
docs/workflows/README.md
docs/index.md
docs/meta/TOP_LEVEL_DOCS_INDEX.md
```

要求：

```text
- 默认入口：README.md + docs/index.md。
- workflow kernel：RESEARCH_WORKFLOW.md。
- 不再把 plans/logs 放入推荐阅读路径。
```

### Step 9 — 可选实现 drift 检查脚本

如执行代码任务，按：

```text
docs/codex_tasks/TASK_DOC_DRIFT_CHECK_SCRIPT.md
```

实现：

```text
scripts/check_doc_drift.py
```

代码必须小而可维护，不引入重依赖。

## 输出 readout

完成后创建：

```text
docs/codex_tasks/TASK_DOCS_WORKFLOW_DEDUP_REFACTOR_READOUT.md
```

内容包括：

```text
1. Summary
2. Files changed
3. Files created
4. Compatibility pointers left in place
5. Before/after grep summary
6. Acceptance checklist result
7. Remaining TODOs
```

## 验收

按补丁包的 `03_ACCEPTANCE_CHECKLIST.md` 全部检查。
