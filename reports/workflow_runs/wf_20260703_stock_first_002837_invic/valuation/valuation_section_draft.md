## 五、估值分析

> 本节为估值情景与研究假设整理，仅用于研究记录，不构成 direct trading advice。

### 5.1 静态估值

- `unknown / TODO`: 本次 dry-run 未发现符合新 handoff 契约的 `market_snapshot.csv`，因此 PE TTM、PB、PS、EV/EBITDA、总市值和当前股价均保留为 `TODO_MARKET_DATA`。
- `fact`: 已有工作流包含公司层面结构化财务指标，路径见 `reports/workflow_runs/wf_20260703_stock_first_002837_invic/metrics_registry.csv`；这些指标不能替代当前市场估值快照。
- `boundary`: 市场估值数据不证明液冷业务收入或利润暴露。

### 5.2 动态估值

- `estimate`: `forecast_model.yaml` 已包含 2026E / 2027E / 2028E 收入预测和 `revenue_growth` 敏感变量，支持指标为 `metric_cn_002837_invic_revenue_20260331_4f7f22`。
- `TODO`: 毛利率、归母净利、EPS、估值倍数和市值锚仍是 `TODO_MODEL_INPUT` / `TODO_MARKET_DATA`，因此不能形成确定性动态估值判断。
- `inference`: 当前只能记录为 `TODO_VALUATION_CONTEXT`，不能从收入预测外推出利润或估值倍数。

### 5.3 同业估值对比

- `TODO`: 本次 dry-run 未发现 `peer_market_snapshot.csv`，因此同业倍数、可比公司中位数和溢价/折价位置均为 `TODO_PEER_DATA`。
- `limitation`: 现有 `peer_comparison.csv` 只有主体公司与 TODO 字段，不足以支持可比公司估值结论。

### 5.4 情景估值与敏感性

- `estimate`: 可保留 `bear/base/bull` 的收入增速情景框架，但输出区间为 `TODO_VALUATION_CONTEXT`。
- `TODO`: 缺少当前市值、净利润预测和同业倍数，敏感性表只能记录待补变量，不能输出价格或市值区间。

### 5.5 估值分歧、反证与后续验证

| 待验证事项 | 为什么重要 | 需要的数据 / 证据 | owner_skill | blocking_level |
|---|---|---|---|---|
| TODO_MARKET_DATA | 静态估值和市值锚缺失 | `market_snapshot.csv`，含日期、价格、市值、PE/PB/PS 等字段 | evidence-ingest | medium |
| TODO_PEER_DATA | 同业估值位置不可判断 | `peer_market_snapshot.csv`，含可比理由、同期间倍数和限制 | evidence-ingest | medium |
| TODO_FINANCIAL_METRIC_PACK | 新 handoff 期望的财务 pack 缺失 | `financial_metric_pack.csv` 或等价 reviewed metric pack 路径映射 | stock-deep-dive | medium |
| TODO_FORECAST_MODEL_NET_PROFIT | 动态估值缺少利润锚 | 归母净利、EPS、毛利率/净利率假设及支持 metric_id | stock-deep-dive | medium |
