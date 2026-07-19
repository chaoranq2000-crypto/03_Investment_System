# R5 Overnight Mission 03

## Mission

**Reviewed-decision intake, targeted backflow execution, and immutable candidate closure**

Night02 已交付稳定的夜班运行时与 69 项 occurrence-level 队列。
Night03 的任务不是再证明 runner 能跑，而是把研究回流从“准备包”推进到：

- 能安全读取真实批准；
- 能执行批准的 pointer 修复；
- 能把 evidence/analysis/human 决定映射到 occurrence；
- 能正确解锁 dependency；
- 能生成不可伪造的 resolution receipt；
- 能在没有批准时仍产出可审、可续跑的候选闭环。

## Starting truth

```yaml
night02_mission: complete
night02_outcome: delivered
night02_final_sha: 069da527452def6c59c3772750e933d8611ccadf
wrapper_tasks: 40/40 passed
authoritative_night03_queue: 69
occurrence_blockers: 63
resolved: 0
parent_work_orders: 6
research_goal: open_needs_targeted_backflow
sample_quality_allowed: false
p2_allowed: false
```

## Imported taxonomy

| 类型 | 数量 | Night03 行为 |
|---|---:|---|
| engineering-local pointer | 8 | 只执行 exact-hash approved 合同；每波最多 2 项 |
| evidence-required | 8 | 生成/刷新候选证据包；只有 reviewer acceptance 才解除 |
| analysis-required | 24 | 生成公司特异候选判断包；只有 reviewer acceptance 才解除 |
| dependency-blocked | 20 | 只由真实前置 resolution receipt 解锁 |
| human/exact-hash gate | 3 | 只消费真实人工决定，不自动填写 |
| parent work orders | 6 | 所有必需 occurrence resolved 后才关闭 |

## Outcome truth table

| Mission outcome | 条件 | 研究含义 |
|---|---|---|
| delivered_with_resolution_delta | 所有 delivery tasks 通过，且 resolved delta > 0 | 有真实 blocker 进展，Goal 仍通常开放 |
| delivered_candidate_ready | 所有 delivery tasks 通过，resolved delta = 0，候选/交接闭环完成 | 研究仍为 0/63，等待外部决定 |
| partial | 截止时仍有可继续的 delivery tasks | 续跑 |
| blocked | 关键工程前置不可执行且无安全 fallback | 不得包装成 delivered |
| failed | 安全、完整性、测试或发布失败 | 不得推送“成功”结论 |
| cutoff | 06:15 后停止领取，完成在途验收 | 生成 partial readout |

## Non-negotiable boundaries

- 不修改 Night02 历史产物；
- 不修改 Bundle17R 历史产物；
- 不自动批准 evidence、analysis、human 或 pointer contract；
- candidate-ready、packet-generated、no-input 都不等于 resolved；
- 不创建 PR，不合并 main，不 force push；
- 不开放 canonical/sample quality/P2；
- 所有 material claim 继续遵守 evidence-first 与缺失可见原则。
