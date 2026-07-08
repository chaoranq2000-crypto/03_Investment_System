# R5 Patch 12 后续任务执行顺序

## 总原则

先修可执行性，再修合同语义，最后才进入受控真实样本。不要跳过 Patch 13。

## 推荐顺序

```text
13. R5_PATCH_13_FORMAT_SYNTAX_RECOVERY.md
14. R5_PATCH_14_R5_FORMAT_GUARD_AND_SMOKE_COMMAND.md
15. R5_PATCH_15_PATCH_1_12_INVENTORY_RECONCILIATION.md
16. R5_PATCH_16_R5_VALIDATOR_SEMANTIC_HARDENING.md
17. R5_PATCH_17_R5_COMPOSER_REPAIR.md
18. R5_PATCH_18_REPRODUCIBLE_FIXTURE_SMOKE.md
19. R5_PATCH_19_READOUT_TRUTHFULNESS_GATE.md
20. R5_PATCH_20_R5_SINGLE_SMOKE_COMMAND.md
21. R5_PATCH_21_SOURCE_GAPPED_002837_R5_PACK.md
22. R5_PATCH_22_R5_EVIDENCE_PLAN_BRIDGE.md
23. R5_PATCH_23_VALUATION_HANDOFF_INTERLOCK.md
24. R5_PATCH_24_R5_READINESS_GATE.md
```

## 分组执行建议

### 第一批：必须连续执行

```text
Patch 13 -> Patch 14 -> Patch 15
```

目的：把 Patch 1-12 从“文件存在”恢复成“文件可解析、可编译、可验收”。

### 第二批：合同与闭环

```text
Patch 16 -> Patch 17 -> Patch 18 -> Patch 19 -> Patch 20
```

目的：让 R5 pack validator、composer、quality review、readout 和 smoke command 构成可信闭环。

### 第三批：真实样本前置

```text
Patch 21 -> Patch 22 -> Patch 23 -> Patch 24
```

目的：用已有 002837 工作流资产做 source-gapped pilot，但不输出 sample-quality 评级报告，也不输出交易建议。

## 禁止跳跃

- Patch 13 未完成，不得执行 Patch 17。
- Patch 14 未完成，不得声称格式问题已修复。
- Patch 18 未完成，不得声称 R5 可复现。
- Patch 20 未完成，不得进入真实 R5 sample pilot。
- Patch 24 未完成，不得进入 P2。
