# Workflow Readout: wf_20260703_stock_first_002837_invic

## 当前状态

| field | value |
|---|---|
| workflow_type | `stock_first_closed_loop` |
| object | `002837 英维克` |
| status | `accepted_with_todos` |
| quality_target | `R5_bundle10r_reader_v5_candidate_ready_for_human_review` |
| current_stage | `T10_close_readout` |
| evidence generation | `evidence_gen_r5_bundle8r_231a51f4673156df` |
| model generation | `model_gen_r5_bundle9r_1cd42241e6a38fb3` |
| Reader generation | `reader_gen_r5_bundle10r_v5_574937bd3943edc1` |
| canonical Reader | `reader_v5_candidate_ready_for_human_review_pending` |
| human review | `pending` |
| sample quality | `false` |
| P2 | `false`；未进入 |

本文件是当前 canonical workflow readout。Reader v4 在自动真值检查上通过，但用户指出正文机械化、干涩；本轮保留 v4 锁定历史，新增 Reader v5，把 10 个结构化分析单元编排为 6 个读者章节，并用新的反机械化非补偿质量门重新验证。自动候选通过不等于人工审阅通过。

## 当前核心产物

| artifact | status |
|---|---|
| `R5_bundle10r_generation_binding_validation.yaml` | pass；绑定 9R model generation |
| `R5_bundle10r_reader_input_pack.yaml` | reviewed；10 sections；22 display references |
| `R5_bundle10r_human_feedback_v4.yaml` | revision_required；仅叙事范围；full_review_attested=false |
| `R5_bundle10r_reader_narrative_plan_v5.yaml` | 6 reader-facing chapters |
| `R5_bundle10r_reader_payload_v5.yaml` | current；底层仍保留 10 analysis units |
| `R5_bundle10r_reader_v5.md` | candidate_ready_for_human_review；SHA256 `cb261412…1e6090` |
| `R5_bundle10r_traceability_v5.yaml` | 22/22 references resolved |
| `R5_bundle10r_reader_v5_quality_scorecard.yaml` | 100/82；三类 blocker 均为 0 |
| `R5_bundle10r_human_review_handoff_v5.yaml` | pending；绑定 Reader v5 精确哈希 |
| `R5_bundle10r_reader_generation_lock_v5.yaml` | 6 artifacts；missing 0；aggregate `574937bd…50ba70a` |
| `R5_bundle10r_quality_gate_report_v5.md` | current quality decision |
| `R5_bundle10r_close_readout_v5.md` | accepted_with_todos |

完整路径、owner、stage 与状态以 `artifact_manifest.csv` 为准。

## 质量与验证

| check | result |
|---|---|
| package | `R5_BUNDLE_10R_READER_REBUILD_PATCH_2026-07-13.zip`；SHA256 `CD32691FA652607BBCBCB3669D4B6EEF75A319DD4B7E32E54CCAC7BA038F47C0` |
| package integrity | 48/48 checksums pass |
| package verification | 13 checks pass；18 focused tests pass |
| generation binding | pass；13 current model artifacts |
| Reader v5 gate | 100/82；truthfulness/core/candidate blockers = 0/0/0 |
| narrative diagnostics | 4151 body Han chars；6 H2；31 paragraphs；四类反机械化问题均为 0 |
| determinism | 6 locked outputs rebuilt twice；hash change=0 |
| focused v5 and lifecycle regression | 35 passed |
| full repository pytest | 704 passed，2 skipped，28.78 秒 |

## 保留缺口

`R5B10R-NARRATIVE-001` 已解决。当前保留 `R5B10R-DCF-001`、`R5B10R-SOTP-001`、`R5B10R-V5-HUMAN-001`、`R5B10R-CI-001`；分别覆盖 DCF 输入、SOTP 输入、Reader v5 精确哈希人工审阅和未授权远端 CI。当前没有 critical/high blocker。

## 历史状态说明

旧 Bundle 10、Reader v3 及其精确哈希人工审阅继续作为历史快照保留。Reader v4 的报告、附录、scorecard、handoff 与 generation lock 也保持原字节；用户的 v4 叙事反馈另存为独立记录。历史签署和 v4 的局部反馈均不能转移到 Reader v5。历史 close 对象未被改写。

## 关闭边界

本轮完成 Reader v5 叙事重构的自动范围。未伪造或代填人工审阅，未恢复 sample-quality，未进入 P2，未暂存、提交、推送，也未声明远端 CI。
