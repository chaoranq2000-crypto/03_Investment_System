# P1-01 Pilot Segment Selection

> 本内容用于研究流程与证据管理，不构成任何买入、卖出、持有或其他交易建议。

```yaml
p1_pilot_segment:
  segment_name_cn: AI服务器液冷
  segment_id: ai_server_liquid_cooling
  reason:
    - 公开政策、准官方行业报告和A股披露证据可获得
    - A股公司可映射，适合验证company_universe和segment_company_exposure
    - 容易区分收入暴露、产品暴露、技术储备和市场叙事
  date_range: 最近3年 + 最新公告/财报
  depth: standard_to_deep
  out_of_scope:
    - 普通工业液冷
    - 传统空调制冷
    - 非数据中心热管理
```

## Adjacent Segments Deferred

- 数据中心电源
- 储能温控
- 电子导热材料
- 服务器结构件
