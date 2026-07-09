# R5 After Patch36 下一步任务包

本任务包用于当前工作区已经达到 `R5_CONTRACTS_EXECUTABLE_WITH_TODOS_ONLY` 之后的下一轮推进。

核心判断：当前 R5 已具备可解析、可校验、可 dry-run 的合约闭环；但真实 source-gapped pilot、sample-quality report 和 P2 仍被 gate 正确关闭。下一步不能直接写样例级个股报告，也不能让 writer 创造研究结论，而应先把 `R5_evidence_request_queue.yaml` 中的缺口转成可审查的 reviewed input registry、forecast assumption registry 和 queue acceptance ledger。

## 包含文件

- `R5_AFTER_PATCH36_COMPLETION_REVIEW.md`
- `APPLY_ORDER.md`
- `R5_PATCH_37_REVIEWED_MARKET_PEER_INPUT_REGISTRY.md`
- `R5_PATCH_38_FORECAST_ASSUMPTION_REGISTRY.md`
- `R5_PATCH_39_EVIDENCE_REQUEST_QUEUE_REVIEW_LEDGER.md`
- `R5_PATCH_40_REAL_SAMPLE_PILOT_GATE_RECHECK.md`
- `R5_PATCH_41_COMPOSER_DEGRADATION_WITH_REVIEWED_INPUTS.md`
- `R5_PATCH_42_CLOSE_READOUT_AND_STATUS_FREEZE.md`

## 已续接任务卡

Patch 43-48 已作为本任务包的后续 reviewed-input pilot 边界执行，并由
`reports/p1_6/r5_after_patch48_status_matrix.yaml` 跟踪状态：

- `R5_PATCH_43_VALUATION_INPUT_REGISTRY_AND_INTERLOCK.md`
- `R5_PATCH_44_002837_REVIEWED_INPUT_DRY_RUN.md`
- `R5_PATCH_45_R5_PACK_PROMOTION_GATE.md`
- `R5_PATCH_46_QUALITY_GATE_SCORECARD_V2.md`
- `R5_PATCH_47_COMPOSER_RESEARCH_DRAFT_PLUS_MODE.md`
- `R5_PATCH_48_PILOT_READINESS_DECISION.md`

## 使用方式

先应用补丁包：

```bash
git apply r5_after_patch36_next_input_registration.patch
```

然后按 `APPLY_ORDER.md` 顺序把任务卡交给 Codex。第一张任务卡必须是：

```text
codex_tasks/r5_after_patch36/R5_PATCH_37_REVIEWED_MARKET_PEER_INPUT_REGISTRY.md
```

## 边界

本补丁包只新增 Codex 任务卡与检查报告，不直接修复代码、不生成真实个股报告、不接入实时 API、不输出交易建议。真正适合 Codex 写的脚本、validator、fixture、readout 由 Codex 按任务卡逐张执行。
