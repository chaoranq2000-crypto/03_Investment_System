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
| `docs/workflows/RESEARCH_WORKFLOW.md` | 永久总工作流事实源 | 阶段计划、执行日志 | `AGENTS.md` |
| `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | orchestrator 状态、路由、handoff、门禁 | 下层 skill 的全部业务细节 | `RESEARCH_WORKFLOW.md` |
| `docs/workflows/DATA_LAYER_WORKFLOW.md` | 数据层 source adapter、manifest、candidate、data pack、quality gate | 投研结论、报告写作风格 | `RESEARCH_WORKFLOW.md` |
| `docs/workflows/STOCK_REPORT_PRODUCTION_WORKFLOW.md` | 个股报告生产流程、analysis pack、narrative、quality gate | 细分研究总流程、买卖建议 | `RESEARCH_WORKFLOW.md` |
| `docs/reporting/` | 个股报告质量标准、证据到叙事契约、表达指南 | 编排路由、run 状态、source adapter 规则 | `STOCK_REPORT_PRODUCTION_WORKFLOW.md` |
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
| orchestrator run / handoff | `WORKFLOW_ORCHESTRATION_SPEC.md` | skill docs 只写本 skill 交接点 |
| 数据下载 / source adapter | `DATA_LAYER_WORKFLOW.md` + evidence-ingest references | stock-deep-dive 不直接定义下载器 |
| 个股报告质量标准 | `docs/reporting/` | workflow 只定义生产流程，不复制表达样式 |
| 阶段计划 | `docs/plans/` | README 只写当前阶段一句话 |

## 旧 skill 名称处理

`stock-research-analyst` 和 `stock-report-writer` 是历史拆分式个股工作流名称。如果目录仍存在但 `.codex/config.toml` 未启用，默认处理为：

```text
status: retired_after_merge_review
routing_allowed: false
replacement: stock-deep-dive
```

后续可由 Codex 单独执行 skill cleanup：

1. 搜索所有引用。
2. 将有效内容并入 `stock-deep-dive/references/`。
3. 更新 workflow 文档。
4. 删除或归档旧目录。
5. 确认 `.codex/config.toml` 不启用旧 skill。

## Markdown 格式纪律

所有长期文档应满足：

- 一级 / 二级标题独立成行。
- Markdown 表格每行独立。
- 代码块使用 fenced code block。
- 避免把整篇文档压成 1-20 条超长物理行。
- 建议普通段落单行不超过 120-160 字符；表格和长 URL 可例外。
- 修改长期文档时优先保持 diff 可读。
