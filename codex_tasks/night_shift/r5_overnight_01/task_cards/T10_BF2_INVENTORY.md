# ns01_t10_bf2_inventory — BF2 Inventory

## Goal

在不改写输入的前提下，识别六个 work order、63 个 blocker occurrence 和兼容字段。

## Required mapping

- work_order_id
- case_id（包括 `__suite__`）
- blocker_occurrence_id
- blocker_code / owner step / severity
- source artifact path and SHA
- source generation ID / generation-lock form
- current status
- dependencies
- allowed paths
- acceptance checks

## Acceptance

- 精确读数为 6 / 63 / 0 resolved；
- 每个 occurrence 可追溯回原 work order；
- suite case 未被丢弃；
- BF1 generation-lock shape 有专门兼容记录；
- 输出 compatibility map 和机器可读 inventory。
