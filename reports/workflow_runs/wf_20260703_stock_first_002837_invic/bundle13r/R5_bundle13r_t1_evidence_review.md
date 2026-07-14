# R5 Bundle 13R — T1 经营证据回流复核

## 运行信息

- workflow_id: `wf_20260703_stock_first_002837_invic`
- source_generation: `op_evidence_gen_r5_bundle12r_fd5d23c5eb35ac27`
- review_owner: `evidence-ingest`
- review_date: `2026-07-15`
- result: `PARTIAL_SUCCESS_WITH_MATERIAL_GAPS`

## Source-route 与 live acquisition

- source-route quality: `pass`，17 个 capability，0 个 blocking issue。
- 深交所正式公告刷新：`evidence_id=ev_official_disclosure_002837_20260715_bd40f1`，50 行，最新公告日期 `2026-06-05`，`2026-07-13` 后新增为 0。
- CNINFO 互动刷新：`evidence_id=ev_company_ir_product_002837_20260715_2430bf`，49 行；返回记录实际日期范围为 `2026-04-10` 至 `2026-07-03`，没有 7 月 13 日后的新问答。
- manifest validation、path validation、candidate validation 均通过。

## 可继承的 reviewed observations

| item | status | evidence | locator | boundary |
|---|---|---|---|---|
| 2025A 营业收入分母 | confirmed | `ev_annual_report_002837_20260421_2cbfc5` | 年报全文 lines 497-502 | fact |
| 2025A 毛利分母 | confirmed | `ev_annual_report_002837_20260421_2cbfc5` | 年报全文 lines 525-528 | reported revenue minus cost |
| room_cooling 独立暴露 | confirmed | `ev_annual_report_002837_20260421_2cbfc5` | 年报全文 lines 497-502 | 2025A revenue share |
| cabinet_cooling 独立暴露 | confirmed | `ev_annual_report_002837_20260421_2cbfc5` | 年报全文 lines 497-502 | 2025A revenue share |
| liquid_cooling 独立暴露 | bounded_estimate | `ev_official_disclosure_002837_20250423_e78396` | 业绩说明会记录 lines 84-88 | 2024A management_comment，不与宽口径相加 |
| room/cabinet 关系 | disjoint | `ev_annual_report_002837_20260421_2cbfc5` | 年报全文 lines 500-502, 526-528 | 年报分别披露两条产品线 |

## 未资格化的 T1 项

以下九项继续为 `missing`：

1. room_cooling：`volume`、`unit_price`、`product_mix`；
2. cabinet_cooling：`volume`、`unit_price`、`product_mix`；
3. data_center_liquid_cooling_related：`unit_value`、`acceptance_rate`、`gross_margin`。

live 刷新中的相关回答仅说明订单/产能/产品或要求查阅定期报告，没有同口径数值、单位、期间和财务映射。特别是累计 `1.2GW`、2024A 约 3 亿元管理层口径、公司级销量和公司级毛利变化均不得替代上述分部驱动。

## Rejected promotions

- 不把公司级销量升级为 room/cabinet 分部销量。
- 不把公司级混合单价升级为分部 realized unit price。
- 不把“订单充沛”“产能不是瓶颈”升级为项目数、单位价值或收入。
- 不把累计交付容量升级为 2025A 单期项目量。
- 不从产品覆盖、客户合作或市场热点推导收入、毛利或验收率。

## Handoff

T1 reviewed-backfill 已写入 `R5_bundle13r_reviewed_backfill_input.yaml`。下一步由 `stock-deep-dive` 处理三组业务关系；两组涉及液冷的收入/毛利扣减仍须保留 `missing`，不得双计。

`sample_quality_allowed=false`；`p2_allowed=false`。
