# Document Ownership Matrix — 文档职责边界

本文件用于防止 `AGENTS.md`、README、workflow docs、plans、playbooks 和 skill docs 之间重复、漂移或互相覆盖。

## 总原则

1. 一个事实只应有一个主事实源。
2. README 只做入口，不承载详细规则。
3. `AGENTS.md` 只放不可妥协的长期纪律，不放完整 workflow 表。
4. `docs/workflows/` 承载永久工作流事实源。
5. `docs/plans/`、`docs/codex_tasks/` 和 `docs/logs/` 只记录阶段计划、执行任务和历史结果。
6. Skill 的 `SKILL.md` 是执行契约，不是项目路线图。
7. reporting docs 只定义个股报告质量和表达，不重新定义整个工作流。

## Workflow interface ownership addendum

以下接口事实只能有一个 owner。

| Interface fact | Owner | Allowed elsewhere |
|---|---|---|
| `workflow_type` enum | `docs/workflows/RESEARCH_WORKFLOW.md` | 只引用，不复制 enum 表 |
| Global `stage_id` and stage sequence | `docs/workflows/RESEARCH_WORKFLOW.md` | 下层 skill 可定义本地 step ID，但不得定义全局 stage |
| Global `gate_id` enum | `docs/workflows/RESEARCH_WORKFLOW.md` | `quality-review` 可定义 checklist 和 `subcheck_id` |
| `backflow_decision` enum | `docs/workflows/RESEARCH_WORKFLOW.md` | skills 可产出 decision，但不得重定义 enum |
| Run status enum | `docs/workflows/RESEARCH_WORKFLOW.md` | `workflow_state_schema.md` 可引用，不另列新枚举 |
| Orchestrator runtime contract | `.agents/skills/research-orchestrator/references/orchestration_contract.md` | `research-orchestrator/SKILL.md` 只摘要动作 |
| Handoff packet format | `.agents/skills/research-orchestrator/references/orchestration_contract.md` | handoff 文件实例化该格式 |
| Stock report production profile | `.agents/skills/stock-deep-dive/references/report_production_profile.md` | 使用 `profile_id`，不得作为 `workflow_type` |
| Stock report expression and style | `docs/reporting/` 或 `stock-deep-dive/references/` | workflow docs 不复制表达指南 |
| Quality issue schema | `.agents/skills/quality-review/SKILL.md`，后续可抽到 reference | 其他文件只消费 issue 输出 |

以下模式属于漂移，除非出现在历史目录或迁移任务说明中：

```text
stock_report_production used as workflow_type
global gate IDs beyond the canonical close gate
full global gate table outside RESEARCH_WORKFLOW.md
Full workflow stage table inside any SKILL.md
```

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
| `docs/policies/QUALITY_GUARDRAILS.md` | 质量门、反幻觉、反证、no-advice | 具体工作流执行步骤 | `AGENTS.md` |
| `docs/workflows/RESEARCH_WORKFLOW.md` | 唯一 global workflow kernel：workflow_type、global stage、global gate、backflow、run status、P2 readiness | 阶段计划、执行日志、单个 skill 的内部 schema | `AGENTS.md` |
| `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | compatibility pointer，指向 orchestrator runtime contract | workflow_type / stage / gate enum、下层 skill 的全部业务细节 | `RESEARCH_WORKFLOW.md` |
| `docs/workflows/DATA_LAYER_WORKFLOW.md` | 数据层 source adapter、manifest、candidate、data pack、quality gate | 投研结论、报告写作风格 | `RESEARCH_WORKFLOW.md` |
| `docs/workflows/STOCK_REPORT_PRODUCTION_WORKFLOW.md` | compatibility pointer，指向 stock report production profile | workflow_type、全局 stage、买卖建议 | `RESEARCH_WORKFLOW.md` |
| `docs/reporting/` | 个股报告质量标准、证据到叙事契约、表达指南 | 编排路由、run 状态、source adapter 规则 | `stock-deep-dive/references/report_production_profile.md` |
| `docs/playbooks/` | 日常操作提示和命令入口 | 永久事实定义、阶段验收标准 | workflow docs |
| `docs/plans/` | 建设计划和验收清单 | 当前事实源定义 | project / workflow docs |
| `docs/codex_tasks/` | 给 Codex 的一次性任务说明 | 永久规则、当前事实源 | plans / workflow docs |
| `docs/logs/` | 执行记录、readout、历史 closeout | 新规则定义 | current docs |
| `.agents/skills/<skill>/SKILL.md` | 单个 skill 的触发、输入、输出、边界、guardrails | 项目总路线图、其它 skill 的完整契约 | workflow docs |

## 重复内容处理规则

| 重复内容 | 保留主事实源 | 其他文件处理方式 |
|---|---|---|
| 项目使命和 no-advice | `AGENTS.md` + `PROJECT_CHARTER.md` | README 只摘要一句 |
| 目录结构 | `WORKSPACE_STRUCTURE.md` | AGENTS / README 只列关键路径 |
| 对象模型 | `RESEARCH_OBJECT_MODEL.md` | workflow docs 只引用对象名称和交接资产 |
| evidence / claim 规则 | `EVIDENCE_AND_CITATION_POLICY.md` | AGENTS 只保留纪律，quality docs 只检查 |
| workflow 类型和阶段 | `RESEARCH_WORKFLOW.md` | playbook 只给调用示例 |
| orchestrator run / handoff | `.agents/skills/research-orchestrator/references/orchestration_contract.md` | skill docs 只写本 skill 交接点 |
| 数据下载 / source adapter | `DATA_LAYER_WORKFLOW.md` + evidence-ingest references | stock-deep-dive 不直接定义下载器 |
| stock report production profile | `.agents/skills/stock-deep-dive/references/report_production_profile.md` | workflow docs 只保留 compatibility pointer |
| 个股报告质量标准 | `docs/reporting/` | workflow docs 和 profile 不复制表达样式 |
| 阶段计划 | `docs/plans/` | README 只写当前阶段一句话 |

## 个股 skill 合并状态

个股分析包构建和报告写作已经统一合并到 `stock-deep-dive`。如果发现拆分式个股 skill 目录或路由，默认处理为：

```text
status: merged_into_stock_deep_dive
routing_allowed: false
replacement: stock-deep-dive
```

后续可由 Codex 单独执行合并一致性检查：

1. 搜索所有引用。
2. 将有效内容并入 `stock-deep-dive/references/`。
3. 更新 workflow 文档。
4. 逐一处理不再需要的目录或文件，禁止批量删除。
5. 确认 `.codex/config.toml` 只启用 `stock-deep-dive` 作为个股深度入口。

## Markdown 格式纪律

所有长期文档应满足：

- 一级 / 二级标题独立成行。
- Markdown 表格每行独立。
- 代码块使用 fenced code block。
- 避免把整篇文档压成 1-20 条超长物理行。
- 建议普通段落单行不超过 120-160 字符；表格和长 URL 可例外。
- 修改长期文档时优先保持 diff 可读。
