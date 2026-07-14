# Workflow Readout: wf_20260703_stock_first_002837_invic

## 当前状态

| field | value |
|---|---|
| workflow_type | `stock_first_closed_loop` |
| object | `002837 英维克` |
| status | `accepted_with_todos` |
| quality_target | `R5_bundle10r_reader_v5_human_review_passed` |
| current_stage | `T10_close_readout`；下一步 `null` |
| evidence generation | `evidence_gen_r5_bundle8r_231a51f4673156df` |
| model generation | `model_gen_r5_bundle9r_1cd42241e6a38fb3` |
| Reader generation | `reader_gen_r5_bundle10r_v5_574937bd3943edc1` |
| canonical Reader | `reader_v5_human_review_passed_with_todos` |
| human review | `passed_external`；8/8 清单通过，绑定精确哈希 |
| sample quality | `false` |
| P2 | `false`；未进入 |

本文件是当前 canonical workflow readout。Reader v5 的自动真值、追溯和反机械化门均通过，外部人工复审又对同一精确哈希完成 8 项清单签署，因此 workflow 已闭环为 `accepted_with_todos`。前一轮“不通过”记录继续作为历史保留；本次通过不覆盖失败记录，也不转移任何旧版本签署。

## 当前核心产物

| artifact | status |
|---|---|
| `R5_bundle10r_generation_binding_validation.yaml` | pass；绑定 9R model generation |
| `R5_bundle10r_reader_input_pack.yaml` | reviewed；10 sections；22 display references |
| `R5_bundle10r_human_feedback_v4.yaml` | revision_required；仅叙事范围；full_review_attested=false |
| `R5_bundle10r_reader_narrative_plan_v5.yaml` | 6 reader-facing chapters |
| `R5_bundle10r_reader_payload_v5.yaml` | current；底层仍保留 10 analysis units |
| `R5_bundle10r_reader_v5.md` | human_review_passed_with_todos；SHA256 `cb261412…1e6090` |
| `R5_bundle10r_traceability_v5.yaml` | 22/22 references resolved |
| `R5_bundle10r_reader_v5_quality_scorecard.yaml` | 100/82；三类 blocker 均为 0 |
| `R5_bundle10r_human_review_handoff_v5.yaml` | historical pending dispatch；原字节保留 |
| `R5_bundle10r_reader_generation_lock_v5.yaml` | historical locked；6 artifacts；aggregate `574937bd…50ba70a` |
| `R5_bundle10r_human_feedback_v5.yaml` | historical revision_required；前次失败记录保留 |
| `R5_bundle10r_human_review_readout_v5.md` | historical needs_fix；前次失败 readout 保留 |
| `R5_bundle10r_human_review_submission_v5.yaml` | accepted；8/8；5/5 输入哈希匹配 |
| `handoffs/32_to_stock-deep-dive_bundle10r_reader_v6_revision.md` | historical route；本次复审通过后不再启动 v6 |
| `R5_bundle10r_quality_gate_report_v5.md` | historical automated pass |
| `R5_bundle10r_close_readout_v5.md` | historical automated close |
| `R5_bundle10r_final_close_readout_v5.md` | accepted_with_todos；最终闭环 |

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
| focused v5 and lifecycle regression | 51 passed |
| full repository pytest | 707 passed，2 skipped，31.30 秒 |
| external human review | accepted；8/8；精确绑定 Reader v5 SHA256 `cb261412…1e6090` |
| locked artifact verification | 6/6 SHA256 匹配 |
| remote CI | pass；commit `3bc55a61`；Actions run `29270619352` |

## 保留缺口

`R5B10R-NARRATIVE-001`、`R5B10R-V5-HUMAN-001`、`R5B10R-V5-HUMAN-FAIL-001` 与 `R5B10R-CI-001` 均已关闭；当前没有 open high issue。`R5B10R-DCF-001` 与 `R5B10R-SOTP-001` 继续作为 medium accepted TODO 保留，分别约束 DCF 与 SOTP 方法资格。

## 历史状态说明

旧 Bundle 10、Reader v3 及其精确哈希人工审阅继续作为历史快照保留。Reader v4 与 Reader v5 的报告、payload、附录、scorecard、handoff 和 generation lock 都保持原字节。Reader v5 的前次失败与本次通过分存在独立文件中；当前通过只适用于 submission 绑定的原 Reader v5 精确哈希。

## 关闭边界

最新补丁包 10R.0—10R.8 已完成，10R.7 的人工复审与状态同步也已闭环。当前结果为 `accepted_with_todos`，不恢复 sample-quality，不进入 P2，也不代表本地最终同步修改已经提交、推送或合并到 `main`。
