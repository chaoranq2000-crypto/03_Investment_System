# Handoff: stock-deep-dive -> quality-review

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| source_stage | `T7_stock_report_draft` |
| target_stage | `T9_quality_review` |
| target_skill | `quality-review` |

## Objective

对 Reader v5 执行证据边界、10 个结构化分析单元和新增反机械化叙事门的非补偿审查；不得用总分抵消任何真值、核心章节或叙事 high issue。

## Inputs

| input | path | status |
|---|---|---|
| human feedback | `R5_bundle10r_human_feedback_v4.yaml` | revision_required；仅叙事范围 |
| narrative plan | `R5_bundle10r_reader_narrative_plan_v5.yaml` | 6 reader-facing chapters |
| payload | `R5_bundle10r_reader_payload_v5.yaml` | 10 analysis units；绑定 9R model generation |
| report | `R5_bundle10r_reader_v5.md` | SHA256 `cb261412…1e6090` |
| appendix | `R5_bundle10r_traceability_v5.yaml` | 22 references |
| contracts | `config/r5_bundle10r_reader_contract_v5.yaml`、`config/r5_bundle10r_quality_contract_v5.yaml` | v5 fail-closed |

## Required Checks

- 所有显示引用唯一解析，正文无内部 ID、路径、原始缺口 token 或行动建议。
- 10 个分析单元分别满足 facts、mechanism、implications、counterevidence、uncertainty、watchpoints。
- 液冷独立经济性保持 non-additive / unknown；外部盈利保持 analyst_view；低置信度同业不排名。
- 正文不重复七组审计标签，不泄漏工作流术语，不存在高相似段落或碎片化标题。
- 技术状态与待确认事件均有日期和条件边界。

## Result

自动检查结果为 `candidate_ready_for_human_review`，score 100，三类 blocker 均为 0；叙事诊断为 4151 个正文汉字、6 个 H2、31 个叙事段落，模板重复、流程术语、近重复段落和过薄章节均为 0。

## Remaining Boundary

此 handoff 只证明自动质量门已通过。Reader v5 仍需对精确哈希进行新的人工审阅；v4 的局部修订反馈和历史 Reader v3 的签署都不能转移。sample quality 与 P2 继续为 false。
