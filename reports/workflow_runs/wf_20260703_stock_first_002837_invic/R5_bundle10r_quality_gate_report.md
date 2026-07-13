# R5 Bundle 10R Reader 质量门报告

## 判定

`decision: candidate_ready_for_human_review`

Reader v4 自动质量门得分 `100/82`，`truthfulness_blockers=0`、`core_section_blockers=0`、`candidate_blockers=0`。这只证明锁定版本具备提交精确哈希人工审阅的条件，不等于人工审阅通过，也不恢复 sample-quality 或 P2 许可。

## 输入与代际

| field | value |
|---|---|
| evidence generation | `evidence_gen_r5_bundle8r_231a51f4673156df` |
| model generation | `model_gen_r5_bundle9r_1cd42241e6a38fb3` |
| reader generation | `reader_gen_r5_bundle10r_1e8a14b47d9426a4` |
| reader aggregate SHA256 | `1e8a14b47d9426a4d95d9097df9f05aa177cc506a75e8f6287974d74a0bdd2e2` |
| Reader v4 SHA256 | `7c7286fb96f075016bbc8e3721a396392a392e7e7f4599e0dc45a04a225d9762` |

代际绑定校验通过，Reader 输入只消费当前 9R 模型代际；历史 Bundle 10 / Reader v3 及其人工签署保持原样，但不得迁移到 Reader v4。

## 非补偿式检查

| check | result |
|---|---|
| 10 个必需章节 | pass；10/10 |
| 显示引用 | pass；22 个唯一引用，未解析 0，重复 0 |
| 来源覆盖 | pass；issuer 10、industry 3、peer 4、market 4、consensus 1 |
| 核心章节 | pass；7/7，无章节可用总分补偿 |
| 技术/情绪/事件日期边界 | pass；未来事件为条件性 estimate，不写成已确认事实 |
| 建议与目标价边界 | pass；无直接交易指令、仓位建议或保证性结论 |
| 确定性重建 | pass；5 个锁定产物连续两次构建，hash change=0 |
| 10R close validator | pass；issues=0 |
| 兼容性状态回归 | pass；17 passed |
| 全仓库回归 | pass；691 passed，2 skipped，28.85 秒 |

## 保留 TODO

| issue_id | severity | owner | next action |
|---|---|---|---|
| `R5B10R-DCF-001` | medium | `company-valuation` | 补齐净债务、折现率与终值输入后重检 DCF 方法资格。 |
| `R5B10R-SOTP-001` | medium | `company-valuation` | 取得液冷分部经济性、未分配成本与消除关系后重检 SOTP。 |
| `R5B10R-HUMAN-001` | medium | `quality-review` | 外部人工审阅者对锁定 Reader v4 哈希完成审阅并回填 handoff。 |
| `R5B10R-CI-001` | low | `research-orchestrator` | 仅在用户明确授权发布后提交、推送并核验远端 CI。 |

上述项目不遮蔽自动候选质量，但人工审阅 TODO 明确阻止 sample-quality。当前无需 evidence backflow；新披露或审阅结论改变现状时应另行生成 refresh/change log。

## 边界

- `human_review_status: pending`
- `sample_quality_allowed: false`
- `p2_allowed: false`
- `remote_ci: TODO_AFTER_EXPLICIT_PUBLISH`
