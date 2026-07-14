# research-orchestrator — Bundle 12R backflow profile

Bundle 12R 只使用局部 gate `RP-12R-OE`。编排器应读取：

- `R5_bundle12r_operating_evidence_result.yaml`
- `R5_bundle12r_backflow_plan.yaml`
- `R5_bundle12r_generation_lock.yaml`

规则：

1. `needs_backflow` 时按 action 的 `target_stage` 和 `required_next_skill` 路由；
2. 不得把 11R 人审状态复制到 12R；
3. 不得在 12R 自动设置 `sample_quality_allowed=true` 或 `p2_allowed=true`；
4. 只有输入与输出精确哈希验证通过后，才可登记 12R generation；
5. Bundle 12R 关闭只说明经营证据门的状态，不说明 P2 readiness。
