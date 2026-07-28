# P1 真实日报垂直样板验收说明

生成与验收时间：`2026-07-28T13:35:19+08:00`

## 样本选择

- 报告日：`2026-07-15`
- 组合：`default` / 组合账户
- 无 Decision 标的：`000813.SZ` / 德展健康
- 选择原因：该日账本、收盘价、上一交易日资产和现金锚点均可核对；德展健康有两笔买入和一笔卖出，仓位由 `17200 → 23000 → 17200`，且 review sidecar 没有对应 Decision，适合同时验证系统动机推断、时点边界、手续费缺失和直接仓位建议。

## 两份读者报告

- [组合日报](portfolio_daily_2026-07-15.md)：总资产 `457388 → 472107.1` 元，资产变动 `14719.1` 元（`3.22%`）；现金 `2697` 元、权重 `0.57%`、状态 `LOW_CONFIDENCE`；最大单一标的 `30.4%`，前三大合计 `65.51%`。建议 `reduce`，把超过 `20%` 的单一标的降至 `15%–20%`，并将现金提高至 `5%–10%`。
- [德展健康日报](instrument_daily_000813.SZ_2026-07-15.md)：期末持仓 `17200` 股、收盘价 `3.45` 元、组合权重 `12.57%`；三笔操作均以 `system_inference` 给出最可能动机、替代解释、定性置信度和缺失信息。建议 `reduce`，目标权重 `8%–12%`。

JSON 原始报告：

- [组合日报 JSON](portfolio_daily_2026-07-15.json)
- [德展健康日报 JSON](instrument_daily_000813.SZ_2026-07-15.json)
- [生成与只读校验摘要](validation_summary.json)

## 数据与时间核对

| 检查项 | 结果 | 证据 |
|---|---|---|
| 正式组合库访问 | `ro+immutable+query_only` | `validation_summary.json` |
| 正式库 SHA-256 前后 | 均为 `752e3b87966f23d2e6f3db89cd3a8d5df0ab893504ee4e7e83de793e4aa52f53` | `validation_summary.json` |
| 组合表现与风险 | 与 `ledger_entries`、`close_prices`、`cash_balance_snapshots` 重放结果一致 | 两份报告的 `source_refs` |
| 动机信息边界 | 每笔 `motive.input_cutoff_at` 不晚于该笔 `occurred_at`，`uses_later_information=false` | 标的日报 JSON |
| 事后信息分区 | 收盘价回看只进入 `retrospective_evaluation`，不进入操作时点动机 | 标的日报 JSON |
| 建议信息边界 | `data_timestamp=2026-07-15T15:00:00+08:00`，不晚于 `report_cutoff_at=2026-07-15T20:30:30+08:00` | 两份报告 JSON |
| Decision 状态 | `not_recorded`，未伪装为用户原始陈述 | 标的日报 JSON |

## API 与页面验收

- localhost 只读验收身份通过：`review_acceptance_read_only=true`、`external_network_allowed=false`、`automation_enabled=false`。
- `/api/investment-review/health` 返回 `available`，周期报告计数为 `2`。
- 周期报告列表与详情 API 均能读取两个确定的 `report_id`。
- 页面“周期报告”位于“操作级证据复盘”之前，能直接打开组合日报和德展健康日报。
- 组合详情可见 `3.22%` 资产变动、`reduce`、`15%–20%` 单标的区间、`5%–10%` 现金区间、主要风险和 `MISSING_TRADE_FEES`。
- 标的详情可见三笔真实操作时间、`system_inference`、替代解释、`reduce`、`8%–12%` 目标权重、风险与失效条件。
- 页面明确显示 `RECOMMENDATION · NOT AN ORDER`；浏览器控制台无 warning/error。

## 工程验证

- V-101：`99 passed`。
- V-102：Vitest `23 passed`；Vite production build 成功并更新 `web_assets`。
- V-201：两份真实报告生成成功、字段核对通过、正式组合库 SHA-256 前后不变。

## 已知限制与安全边界

- `MISSING_DECISION`：动机是 `system_inference`，不是用户陈述。
- `MISSING_TRADE_FEES`：毛价差不是净收益，现金精度标为 `LOW_CONFIDENCE`。
- 缺少明确风险预算、基本面和估值上下文；德展健康还缺盘中市场背景，因此标的建议为 `low` confidence。
- `orders_executed=false`、`broker_accessed=false`、`guaranteed_return_claims=false`、`production_released=false`。
- P1 工程验证已经完成；是否具有实际复盘和决策价值仍需用户人工确认。未收到 `accept_p1_sample_and_continue` 前不得进入 P2。
