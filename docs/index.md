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

- `workflows/README.md` — 永久工作流文档入口。
- `workflows/RESEARCH_WORKFLOW.md` — 总研究工作流事实源。
- `workflows/WORKFLOW_ORCHESTRATION_SPEC.md` — `research-orchestrator` 编排、状态、handoff 和门禁。
- `workflows/DATA_LAYER_WORKFLOW.md` — 数据层发现、拉取、归档、候选化和交接。
- `workflows/STOCK_REPORT_PRODUCTION_WORKFLOW.md` — 样例级个股报告生产流程。

## Reporting

- `reporting/STOCK_REPORT_TARGET_STANDARD.md` — 样例级个股报告目标标准。
- `reporting/STOCK_REPORT_EVIDENCE_TO_NARRATIVE_CONTRACT.md` — 从证据到叙事的转换契约。
- `reporting/STOCK_REPORT_EXPRESSION_GUIDE.md` — 个股报告表达指南。

## Playbooks

- `playbooks/OPERATING_PLAYBOOK.md` — 日常命令索引和轻量操作指南；不是工作流事实源。
- `playbooks/stock_report_case_study_shengyi_tech.md` — 个股报告案例研究。
- `playbooks/stock_report_samples/README.md` — 样例报告目录说明。
- `playbooks/stock_report_samples/stock_report_sample_chifeng_gold.md` — 赤峰黄金样例。
- `playbooks/stock_report_samples/stock_report_sample_dongyangguang.md` — 东阳光样例。
- `playbooks/stock_report_samples/stock_report_sample_wuxi_apptec.md` — 药明康德样例。
- `playbooks/stock_report_samples/stock_report_sample_tongguan_copper_foil.md` — 铜冠铜箔样例。
- local-only: `playbooks/tushare_configuration_guide.pdf` — 本地配置指南，忽略上传到公开 GitHub。

## References

- `references/external_skill_review/a_stock_data_for_evidence_pipeline.md` — 外部 A 股数据 skill 参考，不是主工作流入口。

## Plans

计划文件是阶段建设计划，不应覆盖永久事实源。

- `plans/plan_template.md`
- `plans/p0_acceptance_checklist.md`
- `plans/p0_execution_plan.md`
- `plans/p1_execution_plan.md`
- `plans/p1_1_revision_plan.md`
- `plans/P1_6_WORKFLOW_BUILDOUT_PLAN.md`
- `plans/DATA_LAYER_CODEX_EXECUTION_PLAN.md`
- `plans/DATA_LAYER_ACCEPTANCE_CHECKLIST.md`
- `plans/DATA_LAYER_DEV_TASK_BREAKDOWN.md`
- `plans/DOCS_AND_AGENTS_CLEANUP_PLAN.md`

## Codex Tasks

`docs/codex_tasks/` 放给 Codex 执行的阶段性任务，不是长期事实源。

- `codex_tasks/TASK_01_MINERU_PDF_PIPELINE.md`
- `codex_tasks/TASK_02_STRUCTURED_MARKET_DATA_PIPELINE.md`
- `codex_tasks/TASK_03_CLAIM_METRIC_PROMOTION.md`
- `codex_tasks/TASK_04_STOCK_ANALYSIS_PACK.md`
- `codex_tasks/TASK_05_REPORT_WRITER_AND_TEMPLATE.md`
- `codex_tasks/TASK_06_QUALITY_REVIEW_AND_BACKFLOW.md`
- `codex_tasks/TASK_07_002837_REGRESSION_RUN.md`

## Logs

日志记录阶段执行结果和历史 readout，不应覆盖当前工作流事实源。

- `logs/README.md`
- `logs/2026-07-02_p1_6_workflow_foundation_log.md`
- `logs/2026-07-01_plan_completion_log.md`
- `logs/2026-07-01_docs_structure_cleanup_log.md`
- `logs/p0/2026-07-01_p0_preplanning_confirmation.md`
- `logs/p0/2026-07-01_p0_smoke_test.md`
- `logs/p0/2026-07-01_p0_closeout.md`

## Meta

- `meta/TOP_LEVEL_DOCS_INDEX.md` — 顶层文档元索引。
- `meta/DOC_OWNERSHIP_MATRIX.md` — 文档职责边界和去重矩阵。
- `meta/GENERATED_FILE_MANIFEST.txt` — 生成文件清单。
