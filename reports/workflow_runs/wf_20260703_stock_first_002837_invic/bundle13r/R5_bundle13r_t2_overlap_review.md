# R5 Bundle 13R — T2 独立暴露与重叠复核

## 运行信息

- workflow_id: `wf_20260703_stock_first_002837_invic`
- source_generation: `op_evidence_gen_r5_bundle12r_fd5d23c5eb35ac27`
- review_owner: `stock-deep-dive`
- review_date: `2026-07-15`
- result: `PARTIAL_SUCCESS_WITH_UNRESOLVED_NUMERIC_ADJUSTMENTS`

## 独立量化暴露

| segment_id | status | quantitative exposure | period | metric / evidence | claim boundary |
|---|---|---:|---|---|---|
| `room_cooling` | confirmed | revenue_share `0.5683` | 2025A | `metric_company_cn_002837_invic_room_cooling_revenue_share_2025A_12r`; `ev_annual_report_002837_20260421_2cbfc5`, lines 497-502 | fact；年报直接披露的宽产品线口径 |
| `cabinet_cooling` | confirmed | revenue_share `0.3259` | 2025A | `metric_company_cn_002837_invic_cabinet_cooling_revenue_share_2025A_12r`; `ev_annual_report_002837_20260421_2cbfc5`, lines 497-502 | fact；年报直接披露的宽产品线口径 |
| `data_center_liquid_cooling_related` | bounded_estimate | revenue `250-350 CNY_mn` | 2024A | `metric_company_cn_002837_invic_liquid_cooling_related_revenue_2024A_12r`; `ev_official_disclosure_002837_20250423_e78396`, lines 84-88 | management_comment；非审计分部值，且与 2025A 分母不同期 |

机房和机柜产品线可分别对照 2025A 公司收入分母 `6067.75909155 CNY_mn`。液冷仅证明独立业务暴露存在；因期间、口径及重叠扣减不一致，不计算三者合计覆盖率，也不把液冷区间加到机房或机柜收入上。

## 两两关系与 allocation method

| pair | relation | evidence-backed allocation | numeric adjustment status | resolution |
|---|---|---|---|---|
| `room_cooling` / `cabinet_cooling` | disjoint | 年报在同一产品表分别披露两条产品线收入与成本，各自保留报告值，不做跨线扣减；`ev_annual_report_002837_20260421_2cbfc5`, lines 500-502, 526-528 | not required | resolved |
| `room_cooling` / `data_center_liquid_cooling_related` | overlaps | 液冷管理层口径包含“数据中心机房”来源，属于宽产品线中的主题性横切口径；保持未分配，禁止相加；`ev_official_disclosure_002837_20250423_e78396`, lines 84-88，与年报 lines 500-502 联合约束 | revenue adjustment `missing`; gross-profit adjustment `missing` | unresolved |
| `cabinet_cooling` / `data_center_liquid_cooling_related` | overlaps | 液冷管理层口径同时包含“算力设备”来源，属于宽产品线中的主题性横切口径；保持未分配，禁止相加；`ev_official_disclosure_002837_20250423_e78396`, lines 84-88，与年报 lines 500-502 联合约束 | revenue adjustment `missing`; gross-profit adjustment `missing` | unresolved |

两项 `overlaps` 分类属于基于发行人业务定义的审阅后 inference；现有证据没有提供可把液冷 2024A 管理层口径拆回 2025A 机房/机柜产品线的收入或毛利数值。因此，关系可分类，但不能完成数值 reconciliation。

## Residual 与 overcoverage 边界

- 2025A 机房与机柜收入占比合计为 `0.8942`，剩余部分仍按发行人其他产品线保留，不改写为液冷 residual。
- 液冷区间不参与 2025A coverage 或 overcoverage 计算；把它与两条宽产品线相加会造成潜在双计。
- 未披露的 room/liquid 与 cabinet/liquid 收入、毛利扣减均继续为 `MISSING`，replacement review date 为 `2026-08-31`。

## T2 决策

- `BF12R-003`: `PARTIALLY_RESOLVED`。
- 三组关系均已分类；其中 room/cabinet 已解决，两组液冷重叠因收入与毛利扣减缺失而未解决。
- Bundle 13R 可以进入严格回流执行以固化真实状态，但不满足 `ready_for_bundle12r_rerun` 前提。
- 不进入估值卡、Reader 或 P2；`sample_quality_allowed=false`，`p2_allowed=false`。
