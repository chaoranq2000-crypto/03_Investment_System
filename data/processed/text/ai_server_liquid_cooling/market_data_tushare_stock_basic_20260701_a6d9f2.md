# Evidence Card: market_data_tushare_stock_basic_20260701_a6d9f2

- source_type: exchange_data
- source_name: Tushare Pro API via xiaodefa proxy
- title: P1 company stock_basic snapshot for AI服务器液冷候选池
- publisher: Tushare Pro API via configured proxy
- publish_date: 2026-07-01
- raw_file_path: data/raw/market_data/tushare_stock_basic_ai_server_liquid_cooling_2026-07-01.csv
- reliability_rank: C
- status: fresh
- license_note: 本地结构化数据快照；不含token；用于校验股票代码、简称、上市板块和行业字段。

## Summary

- 按配置指南设置 pro._DataApi__http_url=https://fast.xiaodefa.cn 后，stock_basic 查询成功返回5家公司基础信息。
- 该快照可用于校验候选公司代码、简称、上市板块和Tushare行业字段。

## Limitations

- Tushare为第三方结构化数据源，公司披露和财务结论仍需回到公告/年报核验。

## Related Claims

- claim_data_tushare_20260701_002
