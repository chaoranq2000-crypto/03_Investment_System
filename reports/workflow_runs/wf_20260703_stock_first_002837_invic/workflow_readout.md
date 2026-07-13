# Workflow Readout: wf_20260703_stock_first_002837_invic

## Final state

| field | value |
|---|---|
| workflow_type | `stock_first_closed_loop` |
| object | `002837 英维克` |
| final_status | `accepted_with_todos` |
| quality_target | `R5_sample_quality_ready` |
| current_stage | `T10_close_readout` |
| external_human_review | `passed`; reviewer `Q`; `2026-07-13T14:07:11+08:00` |
| sample_quality_allowed | `true` |
| P2 | `false`; 未进入 |
| patch_plan | `complete_with_documented_todos` |

本文件是当前 canonical workflow readout。早期 R3/R4、Bundle 7、Bundle 8 与 Bundle 9 readout 继续作为历史快照保留；它们不得覆盖本次 Bundle 10 最终关闭状态。

## Skills used

- `research-orchestrator`：补丁阶段编排、状态同步、handoff、requirement matrix 与最终 readout。
- `evidence-ingest`：Bundle 8A/8B 多源抓取、归档、解析、source health 与披露缺口登记。
- `segment-research`、`segment-company-mapping`：行业证据与 product-only exposure backflow。
- `stock-deep-dive`：分析包、预测模型、技术/情绪/事件 pack 与 Reader v3。
- `company-valuation`：同业、情景与反向估值；DCF/SOTP 因输入不足保持 TODO。
- `quality-review`：truthfulness、Reader gate、三域子 agent 评审、人工提交校验和最终关闭。

## Current artifacts

| artifact | status |
|---|---|
| `R5_stock_research_report_reader_v3.md` | `R5_sample_quality_ready`; SHA256 `eff6f0a3d27243dc18a2fa9a144fcb4226805a1420d070b1233a9cfe08b97a83` |
| `R5_stock_research_report_traceability_v3.yaml` | 18 个 display references；全部解析 |
| `R5_stock_research_report_reader_v3_quality_scorecard.yaml` | 98/82；truthfulness pass；0 blockers |
| `R5_bundle10_independent_subagent_review.yaml` | 三域评审 `recommend_pass`；不替代人工身份 |
| `R5_stock_research_report_reader_v3_human_review_submission.yaml` | reviewer `Q`；HR-1 至 HR-6 全部 pass |
| `R5_bundle10_human_review_submission_validation.json` | `pass`; eligible for final close |
| `R5_bundle10_final_close_validation.json` | `pass`; sample quality true；P2 false |
| `R5_patch_plan_requirement_matrix.yaml` | D-1 至 D-9 已闭环；保留披露/方法 TODO |
| `R5_bundle8a_to_bundle10_execution_audit.yaml` | patch plan complete with documented TODOs |

完整路径与状态以 `artifact_manifest.csv` 为准；当前 178 个 artifact_id 与 path 均唯一。

## Quality and validation

| gate/check | result |
|---|---|
| truthfulness | `pass`; 0 blockers |
| Reader quality | `98/82`; automated candidate gate passed |
| external human review | `pass`; exact Reader hash confirmed |
| Bundle 10 final close | `pass` |
| cross-industry Writer regression | 2 个合成行业样本；identity/narrative checks passed |
| focused lifecycle regression | `22 passed` |
| full repository pytest | `642 passed, 2 skipped` |
| direct-advice boundary | `pass`; 不包含买卖、仓位、目标价或收益承诺 |

## Backflow and remaining TODOs

R4 exposure backflow 已执行 `update_exposure_product_only`；只更新产品线线索和 reviewer note，不提升 revenue/profit/order/customer exposure。2025 年液冷收入、毛利率、订单、客户与项目回款继续为 `MISSING_DISCLOSURE`。

`workflow_state.yaml` 当前保留 8 个 TODO（5 medium、3 low），覆盖披露缺口、事件日期/分析师股本口径、Baostock 字段映射、LOW_CONFIDENCE_PEER_SET、Eastmoney push2 代理故障、缺失 IR 原文与未授权远端 CI。每项均保留 owner、severity 与 next action；当前 Bundle 10 quality issue 表没有活动 critical/high issue。

## Close boundary

补丁包计划在本地已经执行并验证完成。P2 是独立的 `comparison_readiness_gate`，本次未启动。未执行 stage、commit、push 或远端 CI；这些发布动作不属于本次授权范围。
