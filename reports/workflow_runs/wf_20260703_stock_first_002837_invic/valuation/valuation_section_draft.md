# Valuation Section Draft - company-valuation

## Context Boundary

本节仅提供估值上下文，不形成交易或配置语言。`company-valuation` 已接收 parseable 输入文件，但 `market_snapshot.csv` 与 `peer_market_snapshot.csv` 仍是 TODO 占位，`forecast_model.yaml` 仍缺前瞻净利、EPS 与利润率假设。

## Static Valuation

- `unknown / TODO`: 当前价格、市值、PE TTM、PB、PS、EV/EBITDA 仍为 `TODO_MARKET_DATA`。
- source: `reports/workflow_runs/wf_20260703_stock_first_002837_invic/market_snapshot.csv`
- boundary: 市场估值字段只能作为 market context，不能作为业务暴露证明。

## Dynamic Valuation

- `estimate`: 收入预测继续使用历史收入 metric anchor，并标注为 estimate。
- `TODO`: 前瞻净利、EPS、利润率与对应倍数仍为 `TODO_FORECAST_MODEL_NET_PROFIT`。
- source: `reports/workflow_runs/wf_20260703_stock_first_002837_invic/forecast_model.yaml`
- source: `reports/workflow_runs/wf_20260703_stock_first_002837_invic/financial_metric_pack.csv`

## Peer Comparison

- `TODO`: 未形成 reviewed peer set，也没有 dated peer multiples，因此 peer 中位数、相对位置与溢价/折价均为 `TODO_PEER_DATA`。
- source: `reports/workflow_runs/wf_20260703_stock_first_002837_invic/peer_market_snapshot.csv`

## Remaining Gaps

| gap_id | status | next input |
|---|---|---|
| TODO_MARKET_DATA | open | reviewed market_snapshot.csv with price, market cap and multiples |
| TODO_PEER_DATA | open | reviewed peer_market_snapshot.csv with peer selection reasons and dated multiples |
| TODO_FORECAST_MODEL_NET_PROFIT | open | forecast_model.yaml with supported net profit, EPS and margin assumptions |
| MISSING_DISCLOSURE | open | official segment revenue or margin disclosure |

`TODO_FINANCIAL_METRIC_PACK` is resolved to partial input because `financial_metric_pack.csv` now exists, but it remains company-level metric-only support and does not support segment attribution.
