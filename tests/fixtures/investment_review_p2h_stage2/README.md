# P2H Stage 2 Slice A synthetic fixture

`protocol_draft.json` 是显式、经人工确认的 observation protocol draft。它只与
`tests/fixtures/investment_review_p2h_stage1/` 中的合成 candidate/source fixture 配合使用。

该目录不含真实账户、证券代码、持仓、成交、broker export、portfolio SQLite、凭证、用户名、
机器名、绝对路径、intervention action、profile 或交易建议。Stage 1 review events 由测试以
固定 UTC whole-second 时间生成，以便同时验证完整事件集绑定、双时间投影和 deterministic
replay。
