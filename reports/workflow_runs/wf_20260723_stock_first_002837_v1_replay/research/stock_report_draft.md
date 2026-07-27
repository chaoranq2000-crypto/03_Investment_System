# 002837 V1 隔离重放研究稿

## 重放结论

本 run 在离线、只读来源边界内完成 T0–T10 自动链。Bundle13R 纯计算结果与归档结果一致：6 项已解决、11 项未解决、输入校验阻断 0。研究质量状态为 `needs_fix`，不是样本质量或 P2 准入结论。

## 证据事实

- 年报全文：`ev_annual_report_002837_20260421_2cbfc5`，原件 `data/raw/annual_reports/cninfo_2025_annual_report_full_002837_2026-04-21.pdf`。
- 2026 年一季报：`ev_quarterly_report_002837_20260421_2f00c7`，原件 `data/raw/announcements/szse_2026_q1_report_002837_2026-04-21.pdf`。
- 两份 Tushare 结构化快照已归档并生成 136 条候选；它们仍是 `draft`、`metric_only`，本 run 未提升为正式 metric，也未用于证明液冷业务暴露。

## 研究边界

`ai_server_liquid_cooling` 只保留为产品线索。液冷独立收入、毛利、项目量、单位价值、验收率，以及与机房/机柜宽口径的收入和毛利扣减均为 `MISSING_DISCLOSURE`。因此不形成同业估值或可执行交易结论。

## 风险、反证与下一步

若后续正式披露仍不能提供同期间量价与重叠分配，当前产品线索不能升级为收入或利润暴露。下一步由 `evidence-ingest` 在 T1 获取并审阅可定位的发行人正式经营披露，再由 `stock-deep-dive` 重做重叠分配。

本文是工程重放产物，不构成投资建议。
