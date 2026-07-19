# ns01_t50_bf2_seed_adapter — BF2 Seed Adapter

## Goal

把真实 BF2 work orders 转为夜班队列任务，同时保持研究真值。

## Required behavior

- 只读消费 input set；
- 保留原 ID 和 source generation；
- occurrence 级去重仅防止重复导入，不合并真实 occurrence；
- 分类规则可解释；
- 导入两次输出逐字节一致；
- 6 个工作单仍为 pending，除非后续 pilot 真正完成；
- 0/63 resolved 不因导入改变；
- suite work order 正常生成任务；
- 需要外部证据或人审的任务状态明确。

## Outputs

- `.local/night_shift/seeded_queue.yaml`
- `.local/night_shift/bf2_seed_receipt.json`
- tracked summary readout（不包含大体积运行产物）
