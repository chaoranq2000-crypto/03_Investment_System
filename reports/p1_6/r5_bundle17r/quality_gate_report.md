# R5 Bundle 17R 质量审查

## 结论

- 工程实施：`passed`。Bundle 17R 的 14 个 add-only 路径已完成聚焦、兼容和全仓验证。
- 真实激活：`blocked / needs_targeted_backflow`，不是 4/4 激活成功。
- 原因：四案例真实 materialization 为 `0/4`，且上游物理 suite lock 与既有 per-case Reader/quality lock 尚不满足 Bundle 17R exact-hash 合同。
- 下一阶段：`R5_bundle17r_targeted_backflow`。
- `canonical_workflow_state_mutation_allowed=false`、`sample_quality_allowed=false`、`p2_allowed=false`。

## 可重复性证据

| 检查 | 结果 |
|---|---|
| 真实 catalog 16R preview 两轮 | PASS，8/8 文件，字节漂移 0 |
| 16R→15R→14R 完整链两轮 | PASS，26/26 文件，字节漂移 0 |
| Bundle 17R activation 两轮 | PASS，10/10 文件，字节漂移 0 |
| activation generation | `activation_gen_r5_bundle17r_1fb1ea838a59cba3` |
| activation decision | `needs_targeted_backflow`，0/4，63 blockers |

## R5 门禁

| 检查 | 结果 | 说明 |
|---|---|---|
| R5-G1 Evidence Completeness | blocked | 0 packs；12 个来源未被真实 reviewer 接受，且 source class、driver、question 映射仍缺失 |
| R5-G2–R5-G9 | not_triggered | 不允许用旧工程产物或高分补偿未通过的 evidence gate |
| R5-G10 No-Advice | passed | 17R manifest、receipt、handoff 和 readout 中未发现买卖、仓位、目标价或保证收益指令 |
| R5-G11 Sample Benchmark | blocked | 4 个 handoff 均为 `not_ready`；旧 lock/quality 合同不能替代新的 exact-hash 代际 |
| Release boundary | passed | 未写 reviewer/时间/接受结论，未改 canonical workflow state，未开放 sample quality 或 P2 |

## 修复路由

1. `evidence-ingest / T1–T2`：真实 reviewer 对官方来源作接受或拒绝，并补 source class、driver records 与 question mappings。
2. `research-orchestrator`：在不改写历史产物的前提下，协调 16R/15R/14R 生成新的物理 suite hash lock 代际。
3. `quality-review / T9`：上游通过后，生成注册 case_id 对齐、含 `candidate_ready_for_exact_hash_review` 与 `generation_id` 的 per-case quality/Reader lock。
4. 重新运行 16R→15R→14R→17R；只有 4/4 通过后才可进入 Bundle 18R 人工审核。

详细问题见 `quality_issues.csv`，机器回流明细见 `activation_run_a/R5_bundle17r_backflow_queue.csv`。
