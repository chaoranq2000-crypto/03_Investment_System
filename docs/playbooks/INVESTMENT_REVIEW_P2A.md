# 投资复盘 P2A：组合上下文底座

## 1. 范围

P2A 在 Phase 1 旁路库之上增加只读组合上下文能力：

- `PositionSnapshot`：标的、数量、成本、价格、市值、币种、行业/标签、来源与双时间；
- `PortfolioSnapshot`：现金、总资产、净资产、融资、持仓集合、来源与双时间；
- `PortfolioContext`：把决策或 `TradeEpisode` 与事前快照、可选事后快照关联；
- 单快照确定性指标与独立的“组合仓位分析”输出块。

本阶段不重建完整 `TradeEpisode`，不计算相关性/风格/流动性压力，不做心理诊断、机械评分、交易建议或券商写操作。

## 2. 时间与来源边界

组合事实必须同时保留：

- `observed_at`：事实发生或快照形成时间；
- `known_at`：该事实进入复盘系统、可被当时决策使用的时间。

决策时点快照要求 `observed_at <= decision.occurred_at` 且
`known_at <= decision.occurred_at`。事后快照放在
`post_event_observation`，并明确标记 `not_available_at_reference_time`，不得回填进事前事实。

每个快照还必须包含 `source_id`、`source_path`、`payload_sha256`。来源定义必须是 `read_only=true`。

## 3. 指标口径

所有比例以 `net_asset_value` 为分母；分母为 0 时保留 `null`，不猜值。

| 指标 | 公式 |
|---|---|
| `cash_ratio` | `cash / net_asset_value` |
| `total_position_ratio` | `sum(abs(base_market_value)) / net_asset_value` |
| `gross_exposure` | 同上 |
| `net_exposure` | `sum(base_market_value) / net_asset_value` |
| `position_weights` | `position_base_market_value / net_asset_value` |
| `top1/top5_concentration` | 最大 1/5 个绝对持仓市值占 gross 持仓市值之和 |
| `hhi_concentration` | `sum((abs(position_value) / gross_market_value)^2)` |

行业和标签同时输出净暴露与 gross 暴露。非基础币种持仓只有在提供
`fx_rate_to_base` 时才进入定量汇总；否则保留
`CURRENCY_NOT_CONVERTED` 并列入 `excluded_position_keys`。

负数量按空头计算 gross/net，但会保留
`NEGATIVE_QUANTITY_INTERPRETED_AS_SHORT`，提示复核来源语义。零价格、未知行业、币种未换算和净值对账差额都保留显式质量标记。

## 4. 写入快照

先复制合成示例，不要把真实账户导出或数据库纳入 Git：

```powershell
Copy-Item config/investment_review.portfolio_snapshot.example.json `
  data/processed/normalized/portfolio_snapshot.local.json
```

人工核对来源、账户、时间、现金、净值、持仓、行业和币种后写入旁路库：

```powershell
.\scripts\start_investment_review.ps1 snapshot-add `
  data/processed/normalized/portfolio_snapshot.local.json
```

同一内容重复写入返回 `SKIPPED`；相同 `snapshot_id` 内容发生变化时返回冲突，不静默覆盖。

## 5. 生成决策组合上下文

已有 `decision_id` 时：

```powershell
.\scripts\start_investment_review.ps1 portfolio-context `
  --decision-id dec_xxx `
  --before-snapshot snap_before `
  --after-snapshot snap_after `
  --out-json reports/investment_review/p2a/dec_xxx_portfolio_context.json `
  --out-markdown reports/investment_review/p2a/dec_xxx_portfolio_context.md
```

已有外部 episode 标识但尚未持久化 episode 对象时：

```powershell
.\scripts\start_investment_review.ps1 portfolio-context `
  --episode-id episode_xxx `
  --symbol 600000.SH `
  --occurred-at "2026-07-15 10:00:00" `
  --before-snapshot snap_before `
  --after-snapshot snap_after
```

输出固定分为：事前组合事实、确定性指标、事后观察、解释候选、替代解释、不确定性和来源。解释候选不会把组合再平衡直接归因为个股逻辑变化。

## 6. 验收

```powershell
python -m pytest -q `
  tests/test_investment_review_phase1.py `
  tests/test_investment_review_portfolio_context.py
```

专项测试覆盖全现金、单/多持仓集中度、多空 gross/net、零价格、负数量、未知行业、币种不一致、时间截断、确定性输出、幂等快照和内容冲突。

P2A 只完成 Gate 2 中的“快照契约 + 单快照指标 + 输出接线”子集；完整事件重放、episode 重构和历史时点对账仍是后续任务。
