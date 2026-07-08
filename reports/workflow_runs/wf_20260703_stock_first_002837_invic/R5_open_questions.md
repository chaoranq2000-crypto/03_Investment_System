# R5 Open Questions — 002837 英维克

status: `source_gapped_follow_up`

| task_id | owner_skill | question | required_source_type | blocking_level | next_action |
|---|---|---|---|---|---|
| R5_OQ_002837_001 | evidence-ingest | 是否存在官方披露的液冷或数据中心温控分业务收入、毛利率、利润贡献？ | annual_report_or_announcement_table | high | 归档并登记对应 evidence / metric；没有则保持 `MISSING_DISCLOSURE` |
| R5_OQ_002837_002 | stock-deep-dive | 2026E-2028E forecast assumptions 是否已由 reviewed metrics 和显式 assumption_id 支撑？ | reviewed_metric_pack_and_assumption_register | high | 未完成前保持 `TODO_MODEL_INPUT` |
| R5_OQ_002837_003 | company-valuation | market snapshot 与 peer valuation context 是否已有日期、来源、单位、口径？ | reviewed_market_snapshot_and_peer_snapshot | high | 未完成前保持 `TODO_MARKET_DATA` / `TODO_PEER_DATA` |
| R5_OQ_002837_004 | evidence-ingest | sentiment / catalyst 是否有 dated sources，且没有被写成事实结论？ | dated_news_or_official_event_source | medium | 未完成前保持 `TODO_SOURCE_REQUIRED` |
| R5_OQ_002837_005 | quality-review | segment exposure 是否能从 product clue 升级，还是继续 `LOW_CONFIDENCE_CLUE_ONLY`？ | exposure_review_with_evidence_ids | high | 审查后写 exposure change note |

## Boundary

这些问题可直接转成 evidence-ingest / stock-deep-dive / company-valuation / quality-review 后续任务。未完成前不得声明 sample-quality，也不得输出交易建议。
