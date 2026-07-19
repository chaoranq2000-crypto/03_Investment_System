# 四个 golden case 运行时代际盘点

本盘点只读取 Bundle14R fixture 与 Bundle16R generated artifacts，不修改历史产物。

| Case | Ticker | Bundle16R case_id | generation_id 完整 | 人审 | 质量/P2 |
|---|---|---|---|---|---|
| `golden_copper_foil_product_generation` | `301217.SZ` | `301217_high_end_copper_foil` | `false` | `pending` | `sample=false, p2=false` |
| `golden_crdmo_backlog_conversion` | `603259.SH` | `603259_crdmo_backlog_funnel` | `false` | `pending` | `sample=false, p2=false` |
| `golden_gold_mining_cycle` | `600988.SH` | `600988_cycle_resource_gold` | `false` | `pending` | `sample=false, p2=false` |
| `golden_multi_business_ai_infrastructure` | `600673.SH` | `600673_multi_business_ma` | `false` | `pending` | `sample=false, p2=false` |

## 结论

- Bundle16R 物理产物存在，但 golden case ID 与 runtime case ID 属于不同代际命名。
- 上游产物没有完整 `generation_id`；质量产物也缺少 Bundle17R 所需的候选就绪布尔字段。
- `decision: pass` 不等于 exact-hash 人审通过，也不允许自动开放 sample quality 或 P2。
