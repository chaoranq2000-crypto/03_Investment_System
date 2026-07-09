# R5 After Patch36 Apply Order

按顺序执行，不得跳步；每张任务卡完成后必须提交 readout，并运行任务卡内测试。

## Phase A：把 TODO 输入转为可审查输入层

1. `R5_PATCH_37_REVIEWED_MARKET_PEER_INPUT_REGISTRY.md`
2. `R5_PATCH_38_FORECAST_ASSUMPTION_REGISTRY.md`
3. `R5_PATCH_39_EVIDENCE_REQUEST_QUEUE_REVIEW_LEDGER.md`

## Phase B：重新运行 gate，但不得强行放行

4. `R5_PATCH_40_REAL_SAMPLE_PILOT_GATE_RECHECK.md`
5. `R5_PATCH_41_COMPOSER_DEGRADATION_WITH_REVIEWED_INPUTS.md`

## Phase C：关闭本轮并冻结状态

6. `R5_PATCH_42_CLOSE_READOUT_AND_STATUS_FREEZE.md`

## 禁止事项

- 不直接进入 sample-quality report。
- 不进入 P2。
- 不把 `TODO_MODEL_INPUT`、`TODO_MARKET_DATA`、`TODO_PEER_DATA`、`TODO_SOURCE_REQUIRED` 写成事实。
- 不新增真实 API 调用。
- 不输出买入、卖出、持有、建仓、减仓、仓位建议、目标价或保证收益。
- 不修改历史 R4/R5 run 的事实性正文，除非任务卡明确要求新增状态文件或 readout。
