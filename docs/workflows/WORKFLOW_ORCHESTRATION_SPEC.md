# Workflow Orchestration Spec — research-orchestrator 运行时规范

> 本文件定义 `research-orchestrator` 如何消费全局 workflow kernel，
> 并创建可审计 workflow run。

This spec consumes canonical workflow_type/stage_id/gate_id/backflow_decision
from RESEARCH_WORKFLOW.md and MUST NOT redefine or extend them.

全局接口唯一事实源：

```text
docs/workflows/RESEARCH_WORKFLOW.md
```

字段级 schema 和唯一模板：

```text
.agents/skills/research-orchestrator/references/workflow_state_schema.md
.agents/skills/research-orchestrator/references/skill_routing_matrix.md
.agents/skills/research-orchestrator/assets/handoff_template.md
```

## 1. 编排目标

`research-orchestrator` 把用户请求转化为可审计的 workflow run：

```text
识别 workflow_type
→ 创建或更新 workflow_state
→ 判断 current_stage / next_stage
→ 选择 target_skill
→ 生成 handoff packet
→ 调度质量门禁
→ 必要时进入 fix loop
→ 输出 workflow_readout
```

它不直接承担行业研究、个股研究、证据抽取或质量审查的全部内容。

## 2. 用户意图分类

收到用户请求后，先分类为 canonical workflow type 或 diagnostic run mode。
`workflow_type` 的可选值来自 `RESEARCH_WORKFLOW.md`。

| 用户意图 | classification output | run_mode | 说明 |
|---|---|---|---|
| 输入一个细分，希望找公司池和样本个股 | canonical segment-led workflow | `normal` | 从细分启动闭环。 |
| 输入一个股票，希望做个股深度并映射细分 | canonical stock-led workflow | `normal` | 从股票或公司启动闭环。 |
| 处理细分和个股之间的回写、冲突或 exposure 变更 | canonical interlock workflow | `normal` | 维护连接层。 |
| 更新已有报告、watchlist 或旧结论 | canonical refresh workflow | `normal` | 新证据驱动刷新。 |
| 判断多个细分或个股是否可比较 | canonical readiness workflow | `normal` | 只做 P2 readiness 判断。 |
| 只问当前状态、缺口或下一步 | related workflow or blank | `diagnostic` | 可不创建 run。 |

分类记录至少说明：

| field | runtime requirement |
|---|---|
| `workflow_type` | 使用 `RESEARCH_WORKFLOW.md` 的 canonical 值，或在只读诊断中留空。 |
| `run_mode` | `normal` 或 `diagnostic`。 |
| `reason` | 说明为何选择该 workflow。 |
| `object_type` | `segment`、`company`、`mixed` 或 `system`。 |
| `object_id` | 可定位对象；缺失时写 `TODO` 或 `MISSING`。 |
| `recommended_start_stage` | 使用 canonical stage，不能新增全局 stage。 |
| `blocked_by` | 无法启动时列明缺口。 |

## 3. Workflow run 创建规则

当用户要求启动、续跑、调试或完整检查闭环时，创建或更新：

```text
reports/workflow_runs/<workflow_id>/
```

运行目录至少维护以下资产：

| asset | purpose |
|---|---|
| `workflow_state.yaml` | 记录当前状态，schema 见 `workflow_state_schema.md`。 |
| `run_log.md` | 记录关键执行步骤、跳过原因和唯一最终报告人工审核决定；不得记录或要求中间人工批准。 |
| `artifact_manifest.csv` | 登记 run 相关产物，字段见 `workflow_state_schema.md`。 |
| `open_todos.csv` | 登记未解决问题，字段见 `workflow_state_schema.md`。 |
| `quality_gate_report.md` | 记录质量审查结果或未执行原因。 |
| `workflow_readout.md` | 收尾阶段生成最终 readout。 |
| `handoffs/` | 保存下层 skill 交接包。 |

如果只是一次简短诊断，可以不创建 workflow run，但最终回答必须说明：

```text
未创建运行目录
```

## 4. Handoff packet 规则

每次将任务交给下层 skill 前，必须准备 handoff packet：

```text
reports/workflow_runs/<workflow_id>/handoffs/<nn>_to_<skill>.md
```

唯一模板位于：

```text
.agents/skills/research-orchestrator/assets/handoff_template.md
```

本规范只保留必填字段清单，不内嵌完整模板。

| required field | requirement |
|---|---|
| `workflow_id` | 当前 run id。 |
| `workflow_type` | 来自 `RESEARCH_WORKFLOW.md`。 |
| `current_stage` | 来自 canonical stage。 |
| `target_skill` | 本次接收 handoff 的 skill。 |
| `objective` | 本次要完成的动作。 |
| `inputs` | 用户输入、必读文档、必读数据或报告。 |
| `expected_outputs` | 预期产物、路径和格式。 |
| `guardrails` | 本次禁止事项和缺证据处理规则。 |
| `completion_criteria` | 完成标准。 |
| `next_gate` | 下一步调度的 canonical gate。 |

## 5. 路由原则

具体全局阶段见 `RESEARCH_WORKFLOW.md`。

运行时只做三件事：

1. 根据 `current_stage` 和用户目标选择 `target_skill`。
2. 用 handoff packet 说明输入、输出、边界和完成标准。
3. 当 quick reference 与 kernel 冲突时，以 kernel 为准并记录 TODO。

快速路由矩阵唯一 reference：

```text
.agents/skills/research-orchestrator/references/skill_routing_matrix.md
```

## 6. Gate dispatch 规则

全局 gate id 和通过条件只在 `RESEARCH_WORKFLOW.md` 定义。

编排器只负责 gate dispatch：

| action | owner |
|---|---|
| 判断当前产物需要哪个 gate | `research-orchestrator` |
| 生成质量审查 handoff | `research-orchestrator` |
| 执行证据、claim、metric、报告、回写等质量检查 | `quality-review` |
| 记录 gate status 和 open TODO | `research-orchestrator` 或 `quality-review` |

每条活动 issue 必须携带 `impact_scope`、`active_disposition`、
`affected_capabilities` 和 `blocks_current_goal`。`severity` 只描述风险与
修复优先级；open high issue 不得仅凭 severity 阻止 `accepted_with_todos`。
canonical outcome 必须按 `RESEARCH_WORKFLOW.md` 第 6.3 节的当前目标依赖表推导。

这里的 evidence / claim / metric / candidate `reviewed` 或“晋升”表示机器
provenance、schema、claim-type、metric、citation、hash 和 no-advice 验证，
不需要 reviewer 身份、签名、authority、receipt 或逐项人工决定。

典型结果：

- 显式可见且未被产物使用的 unknown 可以得到 `accepted_with_todos`；
- unsupported-used number、错误计算、真实 double-count、引用断裂、hidden TODO
  或 no-advice 违规必须得到 `needs_fix`；
- 只有 identity、path、parse、source identity 或不可替代必要输入失败，导致任何
  诚实目标产物都无法生成时，才使用 `blocked`；
- `accepted` 只用于自动质量通过且没有活动限制或 TODO。

## 7. Fix loop 规则

门禁失败时，`workflow_state.yaml` 必须进入 fix loop：

| field | expected update |
|---|---|
| `status` | `needs_fix` 或 `blocked`。 |
| `current_stage` | 当前质量门或发现问题的 stage。 |
| `next_stage` | 需要返回修复的 canonical stage。 |
| `required_next_skill` | 修复 owner skill。 |
| `open_todos` | 记录 issue、severity、target artifact 和 next action。 |

`needs_fix` 只接收可修复的当前产物 defect，或实际使用 unknown 的 scope。
`blocked` 不是更高一级的 severity；它只表示基础身份/路径/解析/来源或不可替代输入
失败，使任何诚实目标产物都无法生成。非必需方法不可用、可见限制或未使用 unknown
保留在 TODO 和 `affected_capabilities` 中，不进入永久 fix loop。

最终报告的 `changes_requested` 只有在
`final_report_review.change_scope=automated_quality_defect` 时进入
`needs_fix`；`change_scope=report_revision` 只回到最终报告写作，不改写已完成的
自动质量 outcome。`not_requested` / `pending` 不进入 fix loop。

fix loop 不新增 `workflow_type`、global `stage_id` 或 global `gate_id`。

## 8. Close readout 规则

完整 workflow 的 `workflow_readout.md` 应说明：

| topic | requirement |
|---|---|
| final state | `workflow_id`、`workflow_type`、`run_mode`、`final_status`。 |
| scope | 本轮对象、范围、out_of_scope。 |
| skills used | 实际调用或明确跳过的 skills。 |
| artifacts | 产物路径和状态，细节来自 `artifact_manifest.csv`。 |
| quality | gates dispatched、open issues、blocked items。 |
| final report review | 自动质量布尔值、review status、绑定报告路径和当前 hash；真实 reviewer 信息只在已提供时记录。 |
| backflow | 使用 `RESEARCH_WORKFLOW.md` 的 canonical decision。 |
| unresolved TODOs | owner、severity、next action。 |
| P2 readiness | 仅在 readiness 任务中判断，不直接进入 P2。 |

### 8.1 V1 truth reporting

编排器消费 `RESEARCH_WORKFLOW.md` 定义的四类完成事实，不在本文件或 runtime 中重定义：

```text
system_v1_complete
sample_quality_ready
p2_ready
release_ready
```

系统级 readout 必须分别给出四个布尔值、证据路径、未满足条件和判定 owner。
不得用 `accepted`、`accepted_with_todos`、`review_intake_ready`、本地测试通过或某个
Bundle/Night mission outcome 代替其中任一事实。只有
`comparison_readiness_gate` 可以形成 `p2_ready` 决定；只有最终 exact-head 发布证据
可以形成 `release_ready` 决定。

`final_report_review_status=not_requested|pending` 不得阻止自动 workflow close
或 `system_v1_complete=true`，但 `sample_quality_ready` 必须保持 false。
`sample_quality_ready=true` 的必要条件包括全部必要自动质量条件通过、状态为
`approved`、最终报告当前字节 SHA-256 与审核记录一致，以及其他适用样例质量条件；
不得把这三项写成充分条件。

### 8.2 Current-run singleton assets

编排器对一个活动 run 只维护一份当前 `workflow_state.yaml`、`open_todos.csv`、
`quality_gate_report.md` 和 `workflow_readout.md`。历史 Bundle/Night 产物、旧 readout 和
旧质量报告只作为 manifest 中的只读来源，不得成为平行 current state。

局部检查或兼容 gate 必须把 `local_check_id` 映射到 `RESEARCH_WORKFLOW.md` 的 G0–G10；
只有 canonical gate id 可以写入 `workflow_state.quality_gates[].gate_id`。活动人工审核只
绑定最终报告当前字节的 SHA-256；generation lock、evidence、claim、metric、candidate、
计算和 receipt 的 hash 只用于机器完整性与重放，不能把中间产物变成人工授权对象。
rollback 只用于可变、非幂等写入，不要求只读检查或幂等生成预设回滚；remote receipt
只用于 publication 与 `release_ready` 边界，不得写成普通研究阶段或质量 gate 的通过条件。

Bundle11R–16R 与 `R5-G1`–`R5-G11` 不在普通 orchestration 的默认 dispatch 图中。
只有 handoff 明确列出待评估 capability 时，才可调用相应 local evaluator。其输出必须
声明 `affected_capabilities` 并映射到 G0–G10；编排器随后按当前目标依赖推导 outcome，
不得消费 Bundle-local pass/fail 直接覆盖 canonical state。

### 8.3 Final-report review runtime

新建或更新的活动状态必须设置
`final_report_review_semantics_version: final_report_review_v1`，并使用：

```text
automated_report_quality_passed
final_report_review_status
final_report_review.report_path
final_report_review.report_sha256
final_report_review.reviewer
final_report_review.reviewed_at
final_report_review.decision
final_report_review.notes
final_report_review.change_scope
```

`not_requested` 的绑定字段和人员字段均为空。`pending` 由机器绑定
`reports/stocks/<id>/` 或 `reports/segments/<id>/` 下的最终报告路径和 SHA-256；
该路径必须与 `artifacts[]` 中唯一 required/current
`artifact_type: final_report` 一致，但 reviewer、时间、备注、`change_scope` 为空。
`approved|changes_requested` 还要求真实非机器 reviewer、ISO 时间和非空备注；
`decision` 必须等于顶层 status。`change_scope` 只在 `changes_requested` 中取
`automated_quality_defect|report_revision`，其他状态必须为空。

编排器必须从仓库中的报告字节重算 SHA-256。字节变化立即使已有决定失效，
不得迁移旧 reviewer 身份或历史 accepted 记录，也不得由机器合成审批。
历史 Bundle14/15/16、Reader 或 Night 的多份 reviewer-authority、独立 receipt、
candidate decision 与 exact-hash 人审只能作为只读兼容证据，退出活动 dispatch。

## 9. 禁止事项

`research-orchestrator` 不得：

1. 新增 canonical workflow type。
2. 新增 global stage id 或 global gate id。
3. 把 diagnostic 当成永久 workflow_type。
4. 直接写长篇研究结论替代下层 skill。
5. 跳过 `quality-review` 直接 accepted。
6. 将 scorecard / watchlist / memo 写成交易建议。
7. 默认调用 Bundle11R–16R、`R5-G1`–`R5-G11` 或用其 local result 直接决定 canonical outcome。
8. 为 evidence、claim、metric、字段、candidate、generation lock、计算或中间 receipt
   请求人工批准，或伪造最终报告 reviewer / approval。

## 10. Legacy capability-evaluator routing

Legacy Bundle11R–16R evaluators may be used only through an explicit capability
handoff. They are not a post-10R default stage. If invoked, the orchestrator
may consume their backflow suggestions only after converting each local issue
to the active scoped issue contract. Typical owner routes remain:

- missing operating drivers or excessive proxy share → `RP2_operating_evidence` / `evidence-ingest`;
- broken operating equation or missing model link → `RP4_operating_model` / `stock-deep-dive`;
- ineligible peer set → `RP5_peer_valuation` / `compare-stocks`;
- generic analysis or non-falsifiable watchpoints → `RP6_analysis_synthesis` / `stock-deep-dive`;
- duplicated narrative or flat emphasis → `RP7_report_planning` / `memo-writer`;
- direct trading language → `RP8_quality_review` / `quality-review`;
- generation mismatch → `T0_orchestration` / `research-orchestrator`.

Routing priority comes from `blocks_current_goal` and the affected capability,
not from highest severity alone. A passing structure score cannot offset an
active defect, while a high-severity visible unknown that is not used by the
current output does not become a global blocker.

<!-- BEGIN R5_NIGHT_SHIFT_MISSION_GOAL_POLICY -->
## 11. 历史 Night-shift Mission 与长期 Goal 记录

历史夜间运行的终止状态 `delivered / partial / blocked / failed / cutoff`、Night02
长期 Goal `r5_bundle17r_bf2_four_case_activation` 及其 `close_allowed`、
`this_mission_may_close_goal`、上层授权字段只作为原运行的只读追溯事实保留。
当前编排器不得据此维持或关闭当前 Goal，不得将其送入活动 dispatch、canonical close
或 V1 完成判定，也不得把它们解释为最终报告审核之外的活动人工授权边界。

发布凭证采用两阶段身份：tracked 实现凭证绑定 implementation commit/tree，
推送后的独立凭证绑定最终 remote HEAD 与 CI。不得试图在一个提交内写入该提交
自己的 SHA，也不得把预发布 SHA 当作下一夜最终基线。
<!-- END R5_NIGHT_SHIFT_MISSION_GOAL_POLICY -->
