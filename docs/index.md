# Documentation Index

本页是文档导航入口，不是工作流事实源。具体规则以对应目录下的事实源文件为准。

默认导航入口是仓库根目录 `README.md` 和本文件。`docs/plans/`、`docs/logs/` 和
`docs/codex_tasks/` 是阶段计划、执行记录和一次性任务材料，不属于默认阅读路径。

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

- `workflows/README.md` — workflow docs entry and ownership notes.
- `workflows/RESEARCH_WORKFLOW.md` — canonical global workflow kernel: `workflow_type`, global stages, global gates, backflow, P2 readiness.
- `workflows/DATA_LAYER_WORKFLOW.md` — 数据层发现、拉取、归档、候选化和交接。
- `workflows/WORKFLOW_ORCHESTRATION_SPEC.md` — compatibility pointer；runtime contract now lives in `.agents/skills/research-orchestrator/references/orchestration_contract.md`.
- `workflows/STOCK_REPORT_PRODUCTION_WORKFLOW.md` — compatibility pointer；stock report production profile now lives in `.agents/skills/stock-deep-dive/references/report_production_profile.md`.

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

按需进入 `docs/plans/` 查阶段建设快照；不要把其中内容当作当前 workflow kernel。

## Codex Tasks

`docs/codex_tasks/` 放给 Codex 执行的阶段性任务，不是长期事实源。

按需进入 `docs/codex_tasks/` 查一次性执行说明；完成后的事实应回到正式 docs、skills 或 reports。

## Logs

日志记录阶段执行结果和历史 readout，不应覆盖当前工作流事实源。

按需进入 `docs/logs/` 查历史 readout；日志不覆盖当前事实源。

## Meta

- `meta/TOP_LEVEL_DOCS_INDEX.md` — 顶层文档元索引。
- `meta/DOC_OWNERSHIP_MATRIX.md` — 文档职责边界和去重矩阵。
- `meta/GENERATED_FILE_MANIFEST.txt` — 生成文件清单。
