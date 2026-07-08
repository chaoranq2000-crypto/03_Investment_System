# R5 Patch 24 后补充任务执行顺序

status: `NEXT_PATCHES_25_36_DEFINED`

## 总原则

Patch 25-30 是阻断修复，不得跳过。
Patch 31-36 是在阻断修复后的 R5 source-gapped pilot 准备，不得提前执行。

## 推荐顺序

```text
25. R5_PATCH_25_RAW_FORMAT_RECOVERY_AND_REBASE
26. R5_PATCH_26_EXECUTABLE_GUARD_OF_GUARDS
27. R5_PATCH_27_INVENTORY_V2_RECONCILIATION
28. R5_PATCH_28_TRUTHFULNESS_CANONICAL_READOUTS
29. R5_PATCH_29_SMOKE_RESULT_TRUST_BOUNDARY
30. R5_PATCH_30_READINESS_GATE_REBASE_ON_REAL_SMOKE
31. R5_PATCH_31_SOURCE_GAPPED_002837_PACK_NORMALIZATION
32. R5_PATCH_32_EVIDENCE_REQUEST_QUEUE_FROM_R5_GAPS
33. R5_PATCH_33_MARKET_PEER_INPUT_STUBS_AND_VALIDATORS
34. R5_PATCH_34_FORECAST_VALUATION_INPUT_INTERLOCK
35. R5_PATCH_35_REPORT_COMPOSER_DEGRADATION_TESTS
36. R5_PATCH_36_R5_CONTRACTS_CLOSE_READOUT_AND_NEXT_PILOT_GATE
```

## 阶段门

### Gate A：执行完 Patch 25-26 后

必须证明：

```text
- Python / YAML / Markdown / pytest 文件物理换行恢复；
- guard scripts 自己也被检查；
- shebang 吞代码、comment-only module、empty-AST module 能被检测；
- 所有 CLI gate 至少 `--help` 可执行。
```

### Gate B：执行完 Patch 27-30 后

必须证明：

```text
- inventory accepted；
- truthfulness gate pass 或历史 readout 被显式归档为 legacy_noncanonical；
- strict R5 smoke 不再产生假阳性；
- readiness gate 至多允许 source-gapped pilot，不允许 sample-quality 或 P2。
```

### Gate C：执行完 Patch 31-36 后

必须证明：

```text
- 002837 R5 pack/source gap/evidence plan 多行可解析；
- evidence request queue 可执行但不调用 live API；
- market/peer/forecast/valuation 输入边界明确；
- composer 在缺输入时只能输出 source-gapped research draft；
- close readout 给出真实命令、exit_code、stdout/stderr 摘要。
```

## 禁止事项

- 不生成买入、卖出、持有、仓位建议。
- 不把 TODO / MISSING_DISCLOSURE 写成事实。
- 不把历史 readout 事后伪造成当时已执行通过。
- 不用 py_compile 单独作为可执行性证明。
- 不让 format guard 只检查别人、不检查自己。
- 不进入 P2。
