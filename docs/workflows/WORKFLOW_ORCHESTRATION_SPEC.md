# Workflow Orchestration Spec — 总工作流编排规范

> 本文件定义 `.agents/skills/research-orchestrator/SKILL.md` 如何执行总工作流编排。它服务于日常研究执行，不是项目阶段计划。

## 1. 编排目标

`research-orchestrator` 把用户请求转化为可审计的 workflow run：

```text
识别工作流类型
→ 创建或更新 workflow_state
→ 判断当前阶段
→ 路由到下层 skill
→ 生成 handoff packet
→ 检查产物和质量门禁
→ 必要时进入 fix loop
→ 输出 workflow_readout
```

它不直接承担行业研究、个股研究、证据抽取或质量审查的全部内容。它的价值是让研究过程不再依赖临时提示词。

## 2. 用户意图分类

收到用户请求后，先分类：

| 用户意图 | workflow_type | 说明 |
|---|---|---|
| 输入一个细分，希望找公司池和样本个股 | `segment_to_stock_closed_loop` | 当前主工作流 |
| 输入一个股票，希望做个股深度并映射细分 | `stock_first_closed_loop` | P2 前必须补齐 |
| 要处理细分和个股之间的回写、冲突或 exposure 变更 | `segment_stock_interlock` | 两个主闭环的连接层 |
| 要更新已有报告或 watchlist | `refresh_existing_research` | P3 前先做轻量接口 |
| 要比较多个细分/个股 | `comparison_readiness_gate` | 进入 P2 前只做 readiness gate |
| 只问当前状态、缺口或下一步 | `workflow_diagnostic` | 只读检查，可不创建 run |

分类后应记录：

```yaml
workflow_type:
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

`workflow_id`：

```text
wf_<YYYYMMDD>_<workflow_type>_<object_id>
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
reports/workflow_runs/<workflow_id>/handoffs/<stage>_to_<skill>.md
```

标准格式：

```md
# Handoff: <stage> → <skill>

## Workflow
- workflow_id:
- workflow_type:
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

## 5. 路由矩阵

| stage / need | 默认 skill | 辅助 skill | 触发条件 |
|---|---|---|---|
| Intake / Scope | `research-orchestrator` | `quality-review` | 新请求、续跑、范围不清 |
| Segment Definition | `segment-research` | `quality-review` | 新细分、边界不清、相邻细分混淆 |
| Evidence Plan / Ingest | `evidence-ingest` | `quality-review` | 缺证据、证据未登记、需要 hash/manifest |
| Claims / Metrics Draft | `evidence-ingest` | `quality-review` | 需要从证据拆事实、估计、指标 |
| Segment Report | `segment-research` | `company-universe` | 需要输出细分报告和指标体系 |
| Company Universe | `company-universe` | `segment-company-mapping` | 需要公司池和暴露候选 |
| Exposure Mapping | `segment-company-mapping` | `quality-review` | 需要维护多对多关系 |
| Stock Sample Selection | `research-orchestrator` | `quality-review` | 需要选择 1–2 家样本 |
| Stock Evidence | `evidence-ingest` | `stock-deep-dive` | 个股证据不足 |
| Stock Deep Dive | `stock-deep-dive` | `evidence-ingest` | 需要个股深度和 linked_segments |
| Segment-Stock Backflow | `segment-company-mapping` | `segment-research` / `stock-deep-dive` | 个股发现需要回写细分/公司池/暴露 |
| Scorecard / Watchlist | `segment-research` / `stock-deep-dive` | `memo-writer` | 需要结构化跟踪项 |
| Quality Gate | `quality-review` | `research-orchestrator` | 进入 accepted / P2 前 |
| Refresh | `refresh-research` | `quality-review` | 新证据影响旧结论 |
| Comparison Readiness | `research-orchestrator` | `quality-review` | 用户要求进入 P2 比较 |
| Readout | `research-orchestrator` | - | 闭环收尾、复盘、状态输出 |

## 6. 质量门禁执行规则

编排器只判断门禁是否需要调用、是否通过、失败后回到哪个 stage；具体质量检查由 `quality-review` 执行。

门禁失败时，`workflow_state.yaml` 必须更新：

```yaml
status: needs_fix
current_stage: quality_gate
next_stage: <stage_to_fix>
required_next_skill: <skill_to_fix>
open_todos:
  - issue_id:
    severity: high | medium | low
    stage:
    target_artifact:
    fix_owner_skill:
    status: open
```

只要存在 high severity issue，不得标记为 `accepted`。

## 7. 质量门禁列表

| gate_id | 检查目标 | 默认 owner |
|---|---|---|
| G0 Scope Gate | 范围、对象、深度和不做事项是否明确 | `research-orchestrator` |
| G1 Evidence Gate | 证据是否登记、来源是否可追溯、关键证据是否可定位 | `evidence-ingest` + `quality-review` |
| G2 Claim Gate | fact / estimate / inference / management_comment 是否分离 | `quality-review` |
| G3 Metric Gate | 指标口径、单位、周期、来源是否明确 | `quality-review` |
| G4 Segment Report Gate | 细分报告关键结论是否可追溯 | `segment-research` + `quality-review` |
| G5 Company Universe Gate | 公司池是否区分真实暴露和叙事暴露 | `company-universe` + `quality-review` |
| G6 Exposure Gate | exposure_type、score、confidence、evidence_ids 是否完整 | `segment-company-mapping` + `quality-review` |
| G7 Stock Report Gate | 个股报告是否可独立阅读且可追溯 | `stock-deep-dive` + `quality-review` |
| G8 Backflow Gate | 个股发现是否已回写或明确不回写理由 | `research-orchestrator` + `segment-company-mapping` |
| G9 No Advice Gate | 是否避免直接买卖建议和评分替代交易判断 | `quality-review` |
| G10 Close Gate | readout 是否说明产物、TODO、状态和下一步 | `research-orchestrator` |

## 8. Artifact manifest 格式

```csv
artifact_id,artifact_type,path,created_by_skill,stage,required,exists,status,notes
```

示例：

```csv
art_001,workflow_state,reports/workflow_runs/wf_20260701_segment_to_stock_ai_server_liquid_cooling/workflow_state.yaml,research-orchestrator,S0,true,true,current,
art_002,segment_report,reports/segments/ai_server_liquid_cooling/2026-07-01_segment_report.md,segment-research,S4,true,true,current,
```

## 9. Open TODO 格式

```csv
issue_id,severity,stage,target_artifact,description,fix_owner_skill,status,created_at,resolved_at,notes
```

Severity：

| severity | 定义 |
|---|---|
| high | 影响核心结论、证据追溯、对象身份、暴露映射或禁止事项 |
| medium | 影响口径完整性、置信度、评分解释或关键 TODO |
| low | 格式、命名、补充说明、非关键字段 |

## 10. Readout 格式

闭环结束时输出：

```md
# Workflow Readout: <workflow_id>

## Status
accepted / accepted_with_todos / needs_fix / blocked

## Scope
- workflow_type:
- object:
- date_range:
- depth:

## Skills Used
| skill | stages | outputs |

## Artifacts
| artifact | path | status |

## Quality Gates
| gate | status | notes |

## Backflow Decisions
| decision | target | action | status |

## Remaining TODOs
| issue | severity | owner_skill | next_action |

## P2 Readiness
- ready_for_limited_p2: true/false
- reasons:
- blockers:
```

## 11. 允许与禁止的编排行为

允许：

1. 创建 workflow run 目录；
2. 创建 handoff packet；
3. 更新 run_log、artifact_manifest、open_todos、workflow_state；
4. 根据质量问题路由到对应 skill；
5. 输出 accepted / accepted_with_todos / needs_fix / blocked 的 readout。

禁止：

1. 直接编造证据、claim、metric 或结论；
2. 绕过 `quality-review` 标记 accepted；
3. 在 P2 readiness gate 前调用 `compare-segments` 做正式 P2 对比；
4. 把 `memo-writer` 用作新增研究结论来源；
5. 静默覆盖旧报告或原始证据；
6. 把评分卡解释成买卖建议。

## 12. 进入 P2 前的编排检查

调用 `compare-segments` 或 `compare-stocks` 前，必须执行 `comparison_readiness_gate`：

1. 至少一个 segment-led workflow run 为 `accepted` 或 `accepted_with_todos`；
2. 至少一个 stock-led 或 stock sample workflow run 为 `accepted` 或 `accepted_with_todos`；
3. 细分和个股之间的 exposure 已回写；
4. scorecard 维度一致；
5. quality-review 无 high severity issue；
6. P2 输入对象不是临时聊天结论，而是仓库内产物；
7. unresolved medium TODO 已说明是否阻塞 P2 pilot。
