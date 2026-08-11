# Document Ownership Matrix — 文档职责边界

本文件用于防止 `AGENTS.md`、README、workflow docs、plans、playbooks 和 skill docs 之间重复、漂移或互相覆盖。

## 总原则

1. 一个事实只应有一个主事实源。
2. README 只做入口，不承载详细规则。
3. `AGENTS.md` 只放不可妥协的长期纪律，不放完整 workflow 表。
4. `docs/workflows/RESEARCH_WORKFLOW.md` 是唯一全局 workflow kernel。
5. `docs/plans/`、`docs/codex_tasks/` 和 `docs/logs/` 只记录阶段计划、执行任务和历史结果。
6. Skill 的 `SKILL.md` 是执行契约，不是项目路线图。
7. reporting docs 只定义个股报告质量和表达，不重新定义整个工作流。

## 全局接口唯一 owner

| 接口事实 | 唯一 owner | 其他文件如何使用 |
|---|---|---|
| `workflow_type` enum | `docs/workflows/RESEARCH_WORKFLOW.md` | 只能引用，不得新增。 |
| global `stage_id` | `docs/workflows/RESEARCH_WORKFLOW.md` | 下层 skill 可定义 `SDD-*`、`DL-*`、`QR-*`、`RP-*` 局部步骤。 |
| global `gate_id` G0-G10 | `docs/workflows/RESEARCH_WORKFLOW.md` | 其他文件只能引用 gate id，不得定义完整全局 gate 表。 |
| `backflow_decision` enum | `docs/workflows/RESEARCH_WORKFLOW.md` | `stock-deep-dive` 和 mapping 只能消费或输出该 enum。 |
| ordinary run outcome and sample-quality meaning | `docs/workflows/RESEARCH_WORKFLOW.md` | 普通 run 只保存本轮 status/G0-G10/TODO/backflow 与适用的 sample-quality；不得复制项目完成、P2 或发布结论。 |
| project integration and release evidence | 对应 convergence / exact-head CI / release artifact | `system_v1_complete` 与 `release_ready` 不写入普通研究 run；历史字段只读兼容。 |
| P2 readiness | `docs/workflows/RESEARCH_WORKFLOW.md` 的 comparison-readiness 章节 | 只有 `comparison_readiness_gate` 可以形成 `p2_ready`；普通 run 不保存全局副本。 |
| canonical workflow outcomes | `docs/workflows/RESEARCH_WORKFLOW.md` | `accepted`、`accepted_with_todos`、`needs_fix`、`blocked` 的当前目标范围 truth table 只能引用，不得按 severity 重定义。 |
| issue scope / disposition semantics | `docs/workflows/RESEARCH_WORKFLOW.md` | `impact_scope`、`active_disposition`、`affected_capabilities`、`blocks_current_goal` 由 schema/quality skill 实现，但语义不得漂移。 |
| missing-data degradation ladder | `docs/workflows/RESEARCH_WORKFLOW.md` | 其他文档可解释本地降级，不得把局部缺口提升为新的全局 blocker。 |
| final-report review fields and transitions | `research-orchestrator/references/workflow_state_schema.md` + `schemas/r5_final_report_review.schema.json` | workflow/policy/skills 只说明本地动作与人工边界，不复制字段表、状态真值表或 legacy 兼容规则。 |
| intermediate machine-qualification semantics | `docs/workflows/RESEARCH_WORKFLOW.md` + `quality-review` | evidence、claim、metric、candidate、计算、generation lock 和 receipt 的 `reviewed` 只表示机器验证，不得改成并行人工 approval。 |
| workflow state fields | `research-orchestrator/references/workflow_state_schema.md` | 必须使用 canonical `workflow_type`。 |
| active-run current asset ownership | `docs/workflows/RESEARCH_WORKFLOW.md` + `WORKFLOW_ORCHESTRATION_SPEC.md` | 每个活动 run 只保留一份当前 state、TODO、quality 和 readout；历史产物只读。 |
| cross-run current pointer | `config/r5_readout_canonical_index.yaml.current_runs` | README 和文档索引只链接 pointer，不复制当前 workflow ID/status；历史 R5 readout 目录不得选择 current run。 |
| handoff packet format | `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | skill 可补充本 skill 的 handoff 要求。 |
| source rank / citation principle | `docs/policies/EVIDENCE_AND_CITATION_POLICY.md` | evidence-ingest references 承担字段级执行契约。 |
| quality issue schema | `.agents/skills/quality-review/references/issue_schema.md` | skill 与 policy 只消费该字段合同；不得创造全局 gate id。 |
| stock report production profile | `.agents/skills/stock-deep-dive/references/report_production_profile.md` | 不得作为平级 workflow。 |
| local check to global gate mapping | 对应 capability-local evaluator reference | `RESEARCH_WORKFLOW.md` 只持有通用映射原则与 canonical G0–G10；各 reference 持有本 capability 的 local ID 和映射，不得产生第二套 global gate。 |
| legacy Bundle/R5 capability evaluator routing | `docs/workflows/RESEARCH_WORKFLOW.md` + `WORKFLOW_ORCHESTRATION_SPEC.md` | Bundle11R–16R、`R5-G1`–`R5-G11` 只能显式调用并影响 `affected_capabilities`；不得成为默认 routing 或直接写 canonical outcome。 |

## 职责矩阵

| 文件 / 目录 | 主职责 | 不应包含 | 上位文件 |
|---|---|---|---|
| `AGENTS.md` | repo-level 规则、证据纪律、no-advice、安全边界、完成门槛 | 完整目录百科、完整 workflow 阶段表、长期计划全文 | system / project instructions |
| `README.md` | 给人看的快速入口、当前阶段摘要、核心链接 | 大段规则、完整路线图、长表格 | `AGENTS.md` |
| `docs/index.md` | 文档导航 | 规则正文、计划正文、workflow 阶段表 | `AGENTS.md` |
| `docs/project/PROJECT_CHARTER.md` | 项目使命、范围、非目标、阶段框架 | skill 细节、具体执行任务 | `AGENTS.md` |
| `docs/architecture/WORKSPACE_STRUCTURE.md` | 文件放置、目录结构、命名规则 | workflow 阶段细节、报告表达标准 | `AGENTS.md` |
| `docs/architecture/RESEARCH_OBJECT_MODEL.md` | Segment / Company / Evidence / Claim / Metric 等对象模型 | 具体报告模板、阶段计划 | `AGENTS.md` |
| `docs/policies/EVIDENCE_AND_CITATION_POLICY.md` | evidence / claim / citation / freshness / conflict rules | workflow 编排细节、样例报告语言风格 | `AGENTS.md` |
| `docs/policies/QUALITY_GUARDRAILS.md` | 质量门原则、反幻觉、反证、no-advice | 具体工作流执行步骤、全局 gate id 表 | `AGENTS.md` |
| `docs/workflows/RESEARCH_WORKFLOW.md` | 全局 workflow kernel | 阶段计划、执行日志、skill 局部实现细节 | `AGENTS.md` |
| `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | orchestrator 运行时状态、路由、handoff、门禁调度 | 新增全局 workflow_type、stage_id 或 gate_id | `RESEARCH_WORKFLOW.md` |
| `docs/workflows/DATA_LAYER_WORKFLOW.md` | 数据层 source adapter、manifest、candidate、data pack、局部 DL checks | 投研结论、报告写作风格、全局 gate id 定义 | `RESEARCH_WORKFLOW.md` |
| `docs/workflows/STOCK_REPORT_PRODUCTION_WORKFLOW.md` | 兼容性指针 | active profile、workflow_type 定义 | `RESEARCH_WORKFLOW.md` |
| `docs/workflows/R5_SAMPLE_QUALITY_STOCK_REPORT_SPEC.md` | 显式 R5 report-capability profile、局部降级和 legacy evaluator 说明 | canonical outcome 重定义、默认 Bundle/R5 routing | `RESEARCH_WORKFLOW.md` |
| `docs/workflows/R5_REAL_COMPANY_REGRESSION_CONTRACT.md` | 显式调用的 automated legacy four-case capability evaluator；历史 per-case 人审只读 | 活动 reviewer authority、release gate、canonical status owner、普通 T0–T10 前置条件 | `RESEARCH_WORKFLOW.md` |
| `docs/reporting/` | 个股报告质量标准、证据到叙事契约、表达指南 | 编排路由、run 状态、source adapter 规则 | `stock-deep-dive` profile |
| `docs/playbooks/` | 日常操作提示和命令入口 | 永久事实定义、阶段验收标准 | workflow docs |
| `docs/plans/` | 建设计划和验收清单 | 当前事实源定义 | project / workflow docs |
| `docs/codex_tasks/` | 给 Codex 的一次性任务说明 | 永久规则、当前事实源 | plans / workflow docs |
| `docs/logs/` | 执行记录、readout、历史 closeout | 新规则定义 | current docs |
| `.agents/skills/<skill>/SKILL.md` | 单个 skill 的触发、输入、输出、边界、guardrails | 项目总路线图、其它 skill 的完整契约、全局接口定义 | workflow docs |

## 重复内容处理规则

| 重复内容 | 保留主事实源 | 其他文件处理方式 |
|---|---|---|
| 项目使命和 no-advice | `AGENTS.md` + `PROJECT_CHARTER.md` | README 只摘要一句。 |
| 目录结构 | `WORKSPACE_STRUCTURE.md` | AGENTS / README 只列关键路径。 |
| 对象模型 | `RESEARCH_OBJECT_MODEL.md` | workflow docs 只引用对象名称和交接资产。 |
| evidence / claim 规则 | `EVIDENCE_AND_CITATION_POLICY.md` | AGENTS 只保留纪律，quality docs 只检查。 |
| workflow 类型和阶段 | `RESEARCH_WORKFLOW.md` | skill docs 和 playbook 只引用。 |
| orchestrator run / handoff | `WORKFLOW_ORCHESTRATION_SPEC.md` + orchestrator references | skill docs 只写本 skill 交接点。 |
| 数据下载 / source adapter | `DATA_LAYER_WORKFLOW.md` + evidence-ingest references | stock-deep-dive 不直接定义下载器。 |
| 个股报告 production profile | `stock-deep-dive/references/report_production_profile.md` | workflow docs 只指针，不复制阶段表。 |
| 最终报告人工审核 | `RESEARCH_WORKFLOW.md` + workflow-state / final-review schema | R5、Reader、Bundle、Night 和 skill docs 只引用，不得要求中间人审或迁移历史 reviewer。 |
| 阶段计划 | `docs/plans/` | README 只写当前阶段一句话。 |

## 个股 skill 合并状态

个股分析包构建和报告写作已经统一合并到 `stock-deep-dive`。

如果发现拆分式个股 skill 目录或路由，默认处理为：

```text
status: merged_into_stock_deep_dive
routing_allowed: false
replacement: stock-deep-dive
```

不要批量删除旧目录。先搜索所有引用，将仍有效的规则并入 `stock-deep-dive/references/`，再更新 config 和 workflow 文档。

## Markdown 格式纪律

所有长期文档应满足：

- 一级 / 二级标题独立成行。
- Markdown 表格每行独立。
- 代码块使用 fenced code block。
- 避免把整篇文档压成 1-20 条超长物理行。
- 建议普通段落单行不超过 120-160 字符；表格和长 URL 可例外。
- 修改长期文档时优先保持 diff 可读。
