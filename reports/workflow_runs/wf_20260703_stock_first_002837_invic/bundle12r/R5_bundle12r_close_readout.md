# R5 Bundle 12R 关闭读数

## 执行结果

- 补丁：`R5_BUNDLE_12R_OPERATING_EVIDENCE_QUALIFICATION_PATCH_2026-07-14.zip`
- 包 SHA256：`1429f3b11f9891f5be974e1c91af4990877a0684feedeed6f07f679d57dd2ff4`
- 真实门禁 generation：`op_evidence_gen_r5_bundle12r_fd5d23c5eb35ac27`
- 门禁结论：`needs_backflow`
- blocker：14 high；方法资格问题：3 medium
- 收入覆盖：89.42%；毛利覆盖：89.70%；关键驱动覆盖：10.00%
- 同业、DCF、SOTP：全部 `not_eligible`
- 回归：Bundle 12R聚焦30项通过；全仓754 passed、2 skipped、28.91s
- 独立子agent复核：pass；0 blocker、0 advisory

## 条件阶段 4

`decision=operating_evidence_ready` 未满足，因此未更新预测模型、估值或 Reader；未产生新 Reader 精确哈希，也未触发新人工审核。Bundle 11R 已接受 Reader 与其人审记录保持不可变。

## Backflow 关闭状态

已审阅现有年报、半年报、官方投资者关系记录、CNINFO IRM 快照及交易所公告快照。仍缺分部量价/组合、液冷单位价值、验收率、独立毛利、宽口径扣减、营运资金桥及方法资格输入。三个 backflow 记录为 `closed_until_new_official_evidence`，新正式证据出现后从 T1 重新运行。

## 固定边界

- `sample_quality_allowed=false`
- `p2_allowed=false`
- 不构成投资建议
