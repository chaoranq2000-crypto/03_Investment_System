# Workflow Orchestration Spec — research-orchestrator 运行时规范

> 本文件定义 `research-orchestrator` 如何消费全局 workflow kernel 并创建可审计 workflow run。它不定义新的 `workflow_type`、global `stage_id` 或 global `gate_id`。

全局接口唯一事实源：

```text
docs/workflows/RESEARCH_WORKFLOW.md
```

## 1. 编排目标

`research-orchestrator` 把用户请求转化为可审计的 workflow run：

```text
识别工作流类型
→ 创建或更新 workflow_state
→ 判断当前阶段
→ 路由到下层 skill
→ 生成 handoff packet
→ 调度质量门禁
→ 必要时进入 fix loop
→ 输出 workflow_readout
```

它不直接承担行业研究、个股研究、证据抽取或质量审查的全部内容。

## 2. 用户意图分类

收到用户请求后，先分类为 canonical workflow type 或 diagnostic run mode。

| 用户意图 | workflow_type | run_mode | 说明 |
|---|---|---|---|
| 输入一个细分，希望找公司池和样本个股 | `segment_to_stock_closed_loop` | `normal` | 当前主工作流。 |
| 输入一个股票，希望做个股深度并映射细分 | `stock_first_closed_loop` | `normal` | P2 前必须补齐。 |
| 要处理细分和个股之间的回写、冲突或 exposure 变更 | `segment_stock_interlock` | `normal` | 两个主闭环的连接层。 |
| 要更新已有报告或 watchlist | `refresh_existing_research` | `normal` | P3 前先做轻量接口。 |
| 要比较多个细分/个股 | `comparison_readiness_gate` | `normal` | 进入 P2 前只做 readiness gate。 |
| 只问当前状态、缺口或下一步 | 使用相关 canonical workflow type 或留空 | `diagnostic` | 只读检查，可不创建 run。 |

分类后应记录：

```yaml
workflow_type:
run_mode: normal | diagnostic
reason:
object_type: segment | company | mixed | system
object_id:
recommended_start_stage:
blocked_by:
```

## 3. Workflow run 创建规则

当用户要求启动、续跑、调试或完整检查闭环时，创建或更新：

```text
reports/workflow_runs/<workflow_id>/
```

必须生成或更新：

1. `workflow_state.yaml`
2. `run_log.md`
3. `artifact_manifest.csv`
4. `open_todos.csv`
5. `quality_gate_report.md`
6. `workflow_readout.md`，可在收尾阶段生成
7. `handoffs/`，用于保存给下层 skill 的交接包

如果只是一次简短诊断，可以不创建 workflow run，但最终回答必须说明“未创建运行目录”。

## 4. Handoff packet

每次将任务交给下层 skill 前，必须准备 handoff packet：

```text
reports/workflow_runs/<workflow_id>/handoffs/<nn>_to_<skill>.md
```

标准格式：

```md
# Handoff: <from_skill> → <to_skill>

## Workflow

- workflow_id:
- workflow_type:
- run_mode:
- current_stage:
- requested_skill:

## Objective

本次交给该 skill 要完成什么。

## Inputs

- 用户输入：
- 必读文档：
- 必读数据/报告：
- 可选参考：

## Expected Outputs

- 路径：
- 格式：
- 必填字段：

## Guardrails

- 不能做什么：
- 缺证据时如何处理：
- 是否允许新增文件：

## Completion Criteria

- 完成标准：
- 下一步门禁：
```

## 5. 路由原则

具体全局阶段见 `RESEARCH_WORKFLOW.md`。本文件只说明运行时路由原则：

| need | 默认 skill | 辅助 skill |
|---|---|---|
| Intake / Scope | `research-orchestrator` | `quality-review` |
| Segment Definition | `segment-research` | `quality-review` |
| Evidence Plan / Ingest | `evidence-ingest` | `quality-review` |
| Claims / Metrics Draft | `evidence-ingest` | `quality-review` |
| Segment Report | `segment-research` | `company-universe` |
| Company Universe | `company-universe` | `segment-company-mapping` |
| Exposure Mapping | `segment-company-mapping` | `quality-review` |
| Stock Sample Selection | `research-orchestrator` | `quality-review` |
| Stock Evidence | `evidence-ingest` | `stock-deep-dive` |
| Stock Deep Dive | `stock-deep-dive` | `evidence-ingest` |
| Segment-Stock Backflow | `segment-company-mapping` | `segment-research` / `stock-deep-dive` |
| Scorecard / Watchlist | `segment-research` / `stock-deep-dive` | `memo-writer` |
| Quality Gate | `quality-review` | `research-orchestrator` |
| Refresh | `refresh-research` | `quality-review` |
| Comparison Readiness | `research-orchestrator` | `quality-review` |
| Readout | `research-orchestrator` | - |

如果路由矩阵和 `RESEARCH_WORKFLOW.md` 冲突，以 `RESEARCH_WORKFLOW.md` 为准，并记录 TODO。

## 6. 质量门禁调度规则

全局 gate id 见 `RESEARCH_WORKFLOW.md`。

编排器只判断门禁是否需要调用、是否通过、失败后回到哪个 stage；具体质量检查由 `quality-review` 执行。

门禁失败时，`workflow_state.yaml` 必须更新：

```yaml
status: needs_fix
current_stage: quality_gate
next_stage:
required_next_skill:
open_todos:
  - issue_id:
    severity: high | medium | low
    stage:
    gate_id:
    target_artifact:
    fix_owner_skill:
    status: open
```

只要存在 high severity issue，不得标记为 `accepted`。

## 7. Artifact manifest 格式

```csv
artifact_id,artifact_type,path,created_by_skill,stage,required,exists,status,notes
```

示例：

```csv
art_001,workflow_state,reports/workflow_runs/wf_20260701_segment_to_stock_ai_server_liquid_cooling/workflow_state.yaml,research-orchestrator,S0,true,true,current,
```

## 8. Open TODO 格式

```csv
issue_id,severity,stage,gate_id,target_artifact,description,fix_owner_skill,status,created_at,resolved_at,notes
```

Severity：

| severity | 定义 |
|---|---|
| high | 影响核心结论、证据追溯、对象身份、暴露映射或禁止事项。 |
| medium | 影响口径完整性、置信度、评分解释或关键 TODO。 |
| low | 格式、命名、补充说明、非关键字段。 |

## 9. Close readout

完整 workflow 的 `workflow_readout.md` 至少说明：

```text
workflow_id
workflow_type
run_mode
final_status
scope
skills_used
artifacts_produced
quality_gates
backflow_decisions
unresolved_todos
blocked_items
p2_readiness_if_relevant
```

## 10. 禁止事项

`research-orchestrator` 不得：

1. 新增 canonical workflow type。
2. 新增 global gate id。
3. 把 diagnostic 当成永久 workflow_type。
4. 直接写长篇研究结论替代下层 skill。
5. 跳过 `quality-review` 直接 accepted。
6. 将 scorecard / watchlist / memo 写成交易建议。
