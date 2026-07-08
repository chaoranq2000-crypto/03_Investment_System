# R5 Source Gap Report — 002837 英维克

status: `source_gapped_draft`

本文件只记录 R5 pack 的缺口，不生成投资结论，不进入 sample-quality，不提供交易动作或配置建议。

| gap_id | section | missing_data | impact_on_conclusion | owner_skill | next_action |
|---|---|---|---|---|---|
| R5_002837_GAP_BUSINESS_001 | business_breakdown | `MISSING_DISCLOSURE`: 液冷收入占比、毛利率、利润贡献 | 产品线索不能证明收入或利润暴露 | evidence-ingest | 继续查找官方分业务披露、公告或表格证据 |
| R5_002837_GAP_FORECAST_001 | forecast | `TODO_MODEL_INPUT`: reviewed forecast assumptions | forecast_model_pack 不能进入 sample-quality | stock-deep-dive | 用已审查 metrics 构建假设，或保持 TODO |
| R5_002837_GAP_VALUATION_001 | valuation | `TODO_MARKET_DATA` / `TODO_PEER_DATA`: reviewed market and peer snapshots | valuation_pack 不能进入 sample-quality | company-valuation | 提供已审查 market / peer context，或保持 TODO |
| R5_002837_GAP_MARKET_001 | technical_market | `TODO_MARKET_DATA`: dated price history and market state | technical_market_pack 不得写交易状态判断 | stock-deep-dive | 补 dated market snapshot；未补前不写趋势判断 |
| R5_002837_GAP_SENTIMENT_001 | sentiment_event | `TODO_SOURCE_REQUIRED`: dated sentiment, catalyst, event sources | sentiment_event_pack 不得写短期情绪判断 | evidence-ingest | 收集 dated sources；未补前保持 TODO |
| R5_002837_GAP_EXPOSURE_001 | segment_exposure | `LOW_CONFIDENCE_CLUE_ONLY`: 产品线索仍需收入/利润证据审查 | exposure remains needs_review | quality-review | 审查 exposure before promotion |

## Boundary

- `TODO_*`、`MISSING_DISCLOSURE`、`source_gap` 均为缺口标记，不是事实。
- 本文件不覆盖 P2 readiness，也不声明 R5 sample-quality ready。
