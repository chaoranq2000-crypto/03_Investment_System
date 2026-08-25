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
- `policies/QUALITY_GUARDRAILS.md` — 质量门、反幻觉、反证和三产品投资边界。
- `policies/PERSONAL_HIGH_RISK_EQUITY_STRATEGY_CHARTER.md` — 已确认的个人高风险权益账户定性章程；不是机器参数或当次建议授权。

## Workflows

- `workflows/README.md` — workflow 文档入口。
- `workflows/RESEARCH_WORKFLOW.md` — 唯一全局 workflow kernel。
- `workflows/WORKFLOW_ORCHESTRATION_SPEC.md` — orchestrator 运行时规范，消费全局接口。
- `workflows/DATA_LAYER_WORKFLOW.md` — 数据层发现、拉取、归档、候选化和交接。
- `workflows/STOCK_REPORT_PRODUCTION_WORKFLOW.md` — 兼容性指针；实际 profile 已迁移到 `.agents/skills/stock-deep-dive/references/report_production_profile.md`。

## Current run navigation

- [`current_runs`](../config/r5_readout_canonical_index.yaml) — 跨 run 的当前 state/readout pointer 唯一 owner。
- `reports/workflow_runs/<workflow_id>/` — 从 pointer 的 `state_path` 读取 run 状态，从 `readout_path` 打开人类投影；本索引不复制当前 workflow ID 或 status。

## Reporting

- `reporting/STOCK_REPORT_TARGET_STANDARD.md` — 样例级个股报告目标标准。
- `reporting/STOCK_REPORT_EVIDENCE_TO_NARRATIVE_CONTRACT.md` — 从证据到叙事的转换契约。
- `reporting/STOCK_REPORT_EXPRESSION_GUIDE.md` — 个股报告表达指南。

## Playbooks

- `playbooks/OPERATING_PLAYBOOK.md` — 日常命令索引和轻量操作指南；不是工作流事实源。
- `playbooks/PORTFOLIO_TRACKER.md` — 本地私有持仓、交割单、成本、行情与看板操作手册。
- `playbooks/INVESTMENT_REVIEW_P2G_3.md`、`INVESTMENT_REVIEW_P2G_4.md`、
  `INVESTMENT_REVIEW_BEHAVIOR_HYPOTHESIS_LEDGER.md` — Review 行为假设合同测试依赖；
  不属于 Research workflow，也不授权交易建议。
- `playbooks/stock_report_case_study_shengyi_tech.md` — 个股报告案例研究。
- `playbooks/stock_report_samples/README.md` — 样例报告目录说明。

样例报告可作为表达风格参考，但不定义 workflow、gate 或 skill 路由。

## Skill references

- `.agents/skills/research-orchestrator/references/` — workflow state、routing、handoff 的执行参考。
- `.agents/skills/stock-deep-dive/references/report_production_profile.md` — 个股报告生产 profile。
- `.agents/skills/evidence-ingest/references/` — manifest、source、adapter、字段级契约。
- `.agents/skills/quality-review/` — issue schema 和质量审查执行契约。
- `.agents/skills/portfolio-tracker/` — Portfolio 私有账务工具边界。
- `.agents/skills/investment-review/` — Investment Review、`observation_only` 和 advice 输入门禁。

## Meta

- `meta/DOC_OWNERSHIP_MATRIX.md` — 文档职责边界和去重矩阵。
- `meta/TOP_LEVEL_DOCS_INDEX.md` — 兼容性指针；不再作为主索引维护。
- `meta/GENERATED_FILE_MANIFEST.txt` — 生成文件清单。
- `meta/PORTFOLIO_REVIEW_INTEGRATION_DEPENDENCY_ALLOWLIST.md` — Portfolio / Review
  选择性集成、文档依赖保留与历史材料排除清单。
- `meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml` — docs/reports 的 canonical
  保留、依赖、Git 恢复与手工删除候选清单。

## Historical material

以下目录中的剩余受保护文件只作为历史和任务记录，不作为当前事实源；已退役
文件从 retention manifest 指定的 Git commit 恢复：

```text
docs/plans/
docs/logs/
docs/codex_tasks/
```

需要查历史时先读 retention manifest，再按精确路径进入剩余文件或 Git history；
日常执行不应把其中内容作为上位规则。
旧 R5/Patch/Bundle readout、治理包和清理收据只按 retention manifest 与 Git history
追溯，不作为日常导航入口，也不得被解释为 current/checkpoint。
