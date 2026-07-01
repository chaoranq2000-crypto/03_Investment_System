---
name: research-orchestrator
description: A股投研总工作流编排。当用户要求研究一个细分、深挖一个股票、刷新已有研究、检查是否能进入 P2、续跑/复盘一个 workflow，或询问下一步应调用哪个 skill 时使用。该 skill 负责按 docs/workflows/ 的事实源路由下层 skills，不替代 evidence-ingest、segment-research、stock-deep-dive、quality-review 等具体研究技能。
---

# Research Orchestrator Skill

## Goal

把用户请求转化为可审计的研究工作流运行：识别 workflow type，创建或更新 workflow state，路由下层 skills，生成 handoff，执行门禁判断，推动 fix loop，并输出 workflow readout。

该 skill 是**执行入口**，不是事实源。事实源在：

```text
docs/workflows/RESEARCH_WORKFLOW.md
docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md
```

## Must-read references

在创建、续跑或修改 workflow run 前，读取或检查：

1. `AGENTS.md`
2. `README.md`
3. `docs/workflows/README.md`
4. `docs/workflows/RESEARCH_WORKFLOW.md`
5. `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md`
6. `docs/architecture/RESEARCH_OBJECT_MODEL.md`
7. `docs/policies/EVIDENCE_AND_CITATION_POLICY.md`
8. `docs/policies/QUALITY_GUARDRAILS.md`
9. 相关下层 skill 的 `.agents/skills/<skill>/SKILL.md`
10. 本 skill 的 `references/skill_routing_matrix.md` 和 `references/workflow_state_schema.md`

如果引用文件不存在，记录 TODO 或 `blocked_by`，不要假装已读取。

## When to use

使用本 skill 当用户要求：

- “研究一个细分”，并希望跑完整细分到个股闭环；
- “深挖一个股票”，并希望独立个股研究后映射/回写细分；
- “刷新已有研究”；
- “检查是否可以进入 P2”；
- “当前下一步该做什么 / 应该调用哪个 skill”；
- “续跑、复盘、诊断某个 workflow”；
- “搭建或调试细分/个股研究总工作流”。

## Do not use as main executor when

如果用户只要求完成单一具体动作，应直接路由到下层 skill：

| 用户只要求 | 主 skill |
|---|---|
| 导入一个公告、PDF、CSV、网页、数据源 | `evidence-ingest` |
| 写一个细分报告 | `segment-research` |
| 找某细分 A 股公司池 | `company-universe` |
| 维护 exposure 映射 | `segment-company-mapping` |
| 写一个个股深度 | `stock-deep-dive` |
| 检查报告证据、幻觉、反证、口径 | `quality-review` |
| 写 memo / watchlist note | `memo-writer` |

本 skill 可以先生成 handoff 或更新 workflow state，但不应替代下层 skill 的专业流程。

## Inputs

可能输入：

```yaml
workflow_type: segment_to_stock_closed_loop | stock_first_closed_loop | segment_stock_interlock | refresh_existing_research | comparison_readiness_gate | workflow_diagnostic
segment_name:
segment_id:
stock_code:
company_name:
company_id:
depth: quick | standard | deep
date_range:
target: build_workflow | run_workflow | resume | diagnose | readout | p2_readiness
workflow_id:
constraints:
out_of_scope:
```

如果缺少可选信息，但任务仍能推进，采用保守假设并记录在 `workflow_state.yaml` 或回答中。不要因为非关键字段缺失而阻塞。

## Workflow

### 1. Classify request

分类为：

```text
segment_to_stock_closed_loop
stock_first_closed_loop
segment_stock_interlock
refresh_existing_research
comparison_readiness_gate
workflow_diagnostic
```

记录：

```yaml
workflow_type:
object_type:
object_id:
reason:
recommended_start_stage:
blocked_by:
```

### 2. Create or locate workflow run

完整闭环、续跑、调试或 readout 任务应创建或更新：

```text
reports/workflow_runs/<workflow_id>/
├── workflow_state.yaml
├── run_log.md
├── artifact_manifest.csv
├── open_todos.csv
├── quality_gate_report.md
├── workflow_readout.md
└── handoffs/
```

命名：

```text
wf_<YYYYMMDD>_<workflow_type>_<object_id>
```

如果只是简短诊断，可以不创建目录，但必须说明未创建 run。

### 3. Initialize or update workflow state

`workflow_state.yaml` 至少包含：

```yaml
workflow_id:
workflow_type:
status:
created_at:
updated_at:
owner:
active_segment_id:
active_company_id:
current_stage:
completed_stages: []
next_stage:
active_skill:
required_next_skill:
evidence_snapshot:
claims_snapshot:
metrics_snapshot:
artifacts: []
open_todos: []
quality_gates: []
entry_criteria:
exit_criteria:
notes:
```

### 4. Route to lower-level skill

默认路由：

| Need | Route to |
|---|---|
| 定义细分边界 | `segment-research` |
| 导入或登记证据 | `evidence-ingest` |
| 抽取或分类 claims / metrics | `evidence-ingest` + `quality-review` |
| 建立 A 股公司池 | `company-universe` |
| 维护细分-公司 exposure | `segment-company-mapping` |
| 个股深度 | `stock-deep-dive` |
| 检查证据、claim、风险、禁止事项 | `quality-review` |
| 从已审查研究生成 memo/watchlist note | `memo-writer` |
| 刷新已有研究 | `refresh-research` |
| P2 前检查 | `comparison_readiness_gate` via this skill + `quality-review` |

### 5. Write handoff packet

每次交给下层 skill 前，生成或更新：

```text
reports/workflow_runs/<workflow_id>/handoffs/<stage>_to_<skill>.md
```

包含：

- workflow id；
- current stage；
- 目标；
- 必读文档；
- 必读输入文件；
- 预期输出路径；
- guardrails；
- completion criteria；
- 下一步门禁。

### 6. Enforce segment-stock backflow

`segment_to_stock_closed_loop` 中，`stock-deep-dive` 完成后必须给出 backflow decision：

```text
update_exposure
update_company_universe
update_segment_taxonomy
update_scorecard
no_backflow_needed
blocked
```

`stock_first_closed_loop` 中，linked segment discovery 完成后必须给出 segment context decision：

```text
link_existing_segment
create_segment_candidate
exclude_non_material
todo_insufficient_evidence
```

没有 backflow decision，不得关闭 workflow。

### 7. Check quality gates

门禁失败时更新：

```yaml
status: needs_fix
next_stage: <stage_to_fix>
required_next_skill: <skill_to_fix>
```

并写入 `open_todos.csv`。只要存在 high severity issue，不得标记 `accepted`。

### 8. Produce readout

闭环结束时写：

```text
reports/workflow_runs/<workflow_id>/workflow_readout.md
```

包含：

- status；
- scope；
- skills used；
- artifacts produced；
- quality gates；
- backflow decisions；
- unresolved TODOs；
- P2 readiness，如果相关。

## Output style

对用户回答时保持操作性：

```text
当前 workflow_type
当前 stage
下一步 skill
需要读取哪些文件
需要写入哪些文件
质量门禁
阻塞项 / TODO
```

不要从本 skill 直接写长篇投资观点。实质研究内容交给下层 skill。

## Guardrails

- 不编造 evidence_id、claim_id、metric_id、stock data、收入占比、订单、客户、估值数字。
- 不绕过 `quality-review` 标记 workflow accepted。
- 不在 `comparison_readiness_gate` 前进入正式 P2 comparison。
- 不把 `memo-writer` 或 scorecard 当作新增研究结论来源。
- 不静默覆盖 raw evidence 或旧报告。
- 必须分离 fact、estimate、inference、management_comment、analyst_view、opinion。
- 必须记录 uncertainty、missing data 和 TODO。
- 不输出买卖建议。

## Minimal close checklist

关闭任何完整 workflow run 前，检查：

```text
[ ] workflow_state.yaml exists and is current
[ ] run_log.md records major steps
[ ] artifact_manifest.csv lists required artifacts
[ ] open_todos.csv lists unresolved gaps
[ ] quality_gate_report.md exists
[ ] required lower-level skill handoffs are recorded or explicitly skipped
[ ] segment-company exposure is updated or no-update reason is recorded
[ ] no high-severity quality issues remain
[ ] workflow_readout.md states accepted / accepted_with_todos / needs_fix / blocked
```
