# Documentation Index

本页是文档导航入口，不是工作流事实源。具体规则以对应目录下的事实源文件为准。

## Project

- `project/PROJECT_CHARTER.md` — 项目目标、边界、路线图、暂停点。

## Architecture

- `architecture/WORKSPACE_STRUCTURE.md` — 目录结构、文件归位、命名规则。
- `architecture/RESEARCH_OBJECT_MODEL.md` — Segment、Company、Evidence、Claim、Metric 等对象模型。

## ADR

- `adr/ADR_0002_data_layer_as_evidence_ingest_subsystem.md` — 数据层作为 evidence-ingest 子系统的架构决策。

## Policies

- `policies/EVIDENCE_AND_CITATION_POLICY.md` — 证据、引用、来源等级、新鲜度和冲突处理。
- `policies/QUALITY_GUARDRAILS.md` — 质量门、反幻觉、反证和 no-advice 纪律。

## Workflows

- `workflows/README.md` — workflow 文档入口。
- `workflows/RESEARCH_WORKFLOW.md` — 唯一全局 workflow kernel。
- `workflows/WORKFLOW_ORCHESTRATION_SPEC.md` — orchestrator 运行时规范，消费全局接口。
- `workflows/DATA_LAYER_WORKFLOW.md` — 数据层发现、拉取、归档、候选化和交接。
- `workflows/STOCK_REPORT_PRODUCTION_WORKFLOW.md` — 兼容性指针；实际 profile 已迁移到 `.agents/skills/stock-deep-dive/references/report_production_profile.md`。

## Reporting

- `reporting/STOCK_REPORT_TARGET_STANDARD.md` — 样例级个股报告目标标准。
- `reporting/STOCK_REPORT_EVIDENCE_TO_NARRATIVE_CONTRACT.md` — 从证据到叙事的转换契约。
- `reporting/STOCK_REPORT_EXPRESSION_GUIDE.md` — 个股报告表达指南。

## Playbooks

- `playbooks/OPERATING_PLAYBOOK.md` — 日常命令索引和轻量操作指南；不是工作流事实源。
- `playbooks/PORTFOLIO_TRACKER.md` — 本地私有持仓、交割单成本重算和收盘价更新手册。
- `playbooks/INVESTMENT_REVIEW_P2C.md` — 交易周期确定性重构、时点快照链接和 artifact 查询手册。
- `playbooks/INVESTMENT_REVIEW_P2E_3.md` — 交易周期事件锚点、双时间组合上下文和指标证据绑定手册。
- `playbooks/INVESTMENT_REVIEW_P2F_DRAFT.md` — 单笔交易双视角复盘的冻结输入、事实/解释分层和修订门禁手册。
- `playbooks/INVESTMENT_REVIEW_P2G_1.md` — 跨 Trade Episode facts-only cohort 的双时间、修订、排除原因和 source replay 手册。
- `playbooks/INVESTMENT_REVIEW_P2G_2.md` — 确定性跨 episode observation ledger、五态结果和 detector 门禁手册。
- `playbooks/INVESTMENT_REVIEW_P2G_3.md` — recorded JSON 候选行为假设、attempt receipt、护栏和 source replay 手册。
- `playbooks/INVESTMENT_REVIEW_P2G_4.md` — 候选假设 accept/reject/correct、不可变 revision 和审计工具手册。
- `playbooks/INVESTMENT_REVIEW_BEHAVIOR_HYPOTHESIS_LEDGER.md` — 已审核假设的 active/audit 台账、exact dedup、查询和重放手册。
- `playbooks/stock_report_case_study_shengyi_tech.md` — 个股报告案例研究。
- `playbooks/stock_report_samples/README.md` — 样例报告目录说明。

样例报告可作为表达风格参考，但不定义 workflow、gate 或 skill 路由。

## Investment review readouts

- `../reports/investment_review/p2g_stage3/P2G_STAGE3_CLOSE_READOUT.md` — P2G 阶段三行为假设闭环的 canonical 功能关闭回执。

## Skill references

- `.agents/skills/research-orchestrator/references/` — workflow state、routing、handoff 的执行参考。
- `.agents/skills/stock-deep-dive/references/report_production_profile.md` — 个股报告生产 profile。
- `.agents/skills/evidence-ingest/references/` — manifest、source、adapter、字段级契约。
- `.agents/skills/quality-review/` — issue schema 和质量审查执行契约。

## Meta

- `meta/DOC_OWNERSHIP_MATRIX.md` — 文档职责边界和去重矩阵。
- `meta/TOP_LEVEL_DOCS_INDEX.md` — 兼容性指针；不再作为主索引维护。
- `meta/GENERATED_FILE_MANIFEST.txt` — 生成文件清单。

## Historical material

以下目录保留为历史和任务记录，不作为当前事实源：

```text
docs/plans/
docs/logs/
docs/codex_tasks/
```

需要查历史时再进入这些目录；日常执行不应把其中内容作为上位规则。
