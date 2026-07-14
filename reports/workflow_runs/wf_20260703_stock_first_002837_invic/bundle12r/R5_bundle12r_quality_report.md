# R5 Bundle 12R 质量复核报告

## 结论

`RP-12R-OE` 结论为 `needs_backflow`。14 个 high blocker 与 3 个 medium 方法资格问题均可追溯；本轮没有资格重算模型或生成 Reader。旧 Bundle 11R Reader 及其精确哈希人审状态保持不变。

## 非补偿检查

| 检查项 | 结果 | 证据或限制 |
|---|---|---|
| 官方证据可追溯 | pass | 年报、半年报、CNINFO投资者关系记录及截至2026-07-13的官方快照均登记了 `evidence_id`、路径和定位。 |
| claim type 分离 | pass | 年报值为 `fact`；IR数值为 `management_comment`；毛利差额为可复算 `estimate`；未披露项为 `missing`。 |
| 指标定义 | pass_with_gaps | 已用指标均含期间、单位、来源和计算方法；公司级销量未冒充机房或机柜分部销量。 |
| 关键驱动覆盖 | fail_closed | 1/10，10.00%，低于80%门槛。 |
| 收入覆盖 | numeric_pass_but_not_sufficient | 89.42%；2024A液冷管理层口径未与2025A总量混算，且宽口径扣减仍未解决。 |
| 毛利覆盖 | numeric_pass_but_not_sufficient | 89.70%，但液冷独立毛利和重叠扣减缺失。 |
| 重叠与独立暴露 | fail_closed | 液冷跨机房、算力设备口径；两组收入和毛利扣减均为 `missing`。 |
| 同业、DCF、SOTP | all_not_eligible | 合格同业0家；capex仅2期且营运资金桥/关键参数缺失；SOTP重大分部均失败。 |
| 风险与反证 | pass | 新IR快照未提供关闭缺口的量化证据；“产能不是瓶颈”等管理层表述未升级为事实指标。 |
| Reader与人审边界 | pass | 没有新Reader，因此不创建新人工审核状态；旧11R人审不迁移到12R。 |
| generation lock | pass | `op_evidence_gen_r5_bundle12r_fd5d23c5eb35ac27` 两次运行一致，锁校验通过。 |
| 回归验证 | pass | Bundle 12R聚焦30项通过；全仓754 passed、2 skipped、28.91s。 |
| 独立子agent复核 | pass | 0 blocker、0 advisory；实现、负向变异、锁、状态与旧Reader边界均通过。 |
| 安全边界 | pass | `sample_quality_allowed=false`、`p2_allowed=false`，无买卖建议或确定性收益表达。 |

## 关闭方式

三个 backflow 已分别路由到 `evidence-ingest`、`stock-deep-dive` 和 `company-valuation`。现有官方来源复核完毕后仍不能关闭缺口，因此本轮按 `closed_until_new_official_evidence` 结束，而不是把缺失项伪装为通过。
