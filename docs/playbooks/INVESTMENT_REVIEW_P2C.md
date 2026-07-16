# 投资复盘 P2C：可审计交易周期重构

## 1. 范围

P2C 把 Phase 1 已审核的规范化事件组织为可重建的 `TradeEpisode`，并只读消费 P2B 时点快照引用：

```text
review sidecar trade_events + explicit decision_event_links
                         +
read-only P2B portfolio_snapshots / position_snapshots
                         ↓
portfolio.trade_episode.collection.v1
```

P2C 不修改 portfolio SQLite，不升级 v2 review sidecar，不复制完整快照负载，也不生成盈亏归因、市场解释、行为标签、建议、信号或交易动作。

## 2. 契约

单个 episode 继续使用可扩展容器 `portfolio.trade_episode.v1`，集合使用
`portfolio.trade_episode.collection.v1`；当前 validator 为
`portfolio.trade_episode.validation.v2`，builder/projection 为 `p2c_v1_1`，
Decision 链接子契约为 `p2c.decision_linkage.v2`。旧 `p2c_v1` artifact
仍可由 P2C validator 识别并给出 legacy warning，但不能进入 P2F，必须先重建。

`episode_id` 由 schema、显式账户、显式证券、币种和 opening event ID 的规范化内容哈希生成；生成时间、输入列表顺序和字典字段顺序不参与身份。集合与单 episode 都保存 canonical SHA-256。

允许状态：

- `open`：从 flat 进入非零，截止时仍非零；
- `closed`：从 flat 进入非零并回到 flat；
- `data_gap`：首个可见数量来自期初、转入、公司行动或修正，缺少完整起点；
- `ambiguous`：边界无法在不猜测的情况下拆分，例如单一事件跨越多空符号。

事件按 `(account, market, symbol, currency)` 显式分区，并按
`occurred_at → source sequence → source_record_id/event_id` 排序。每个 accepted event 必须被消费一次、分类为非数量事件、带原因排除/拒绝，或显式阻断；不能静默丢失。

## 3. 时间与链接

- `occurred_at`、`known_at` 和 cutoff 必须带时区；
- `occurred_at > cutoff` 或 `known_at > cutoff` 的事件保留在 consumption ledger，但不进入当次 episode；
- P2B 快照仅通过 SQLite read-only URI 读取；
- before 链接要求 `knowledge_cutoff_at <= event.occurred_at`，并显式标记 `latest_at_or_before` 与时间距离；
- after 链接只有在 lineage 能证明目标事件已包含、且没有更晚事件混入时才使用 `exact_event_cursor`；否则为 `missing`；
- 没有独立 knowledge cutoff 的历史快照不能冒充决策时点可用事实；
- Decision 只消费 `decision_event_links` 的显式关系；无链接为 `unlinked`，冲突为 `ambiguous`，时间或身份无效为 `invalid`。
- 一条 Decision 可以显式关联多条 partial-fill execution；只要各关系的 Decision
  身份与双时间一致，就保持 `linked`。同一执行槽存在互斥 Decision，或同一关系事实互相冲突时才标记 `ambiguous`。
- `decision_refs` 仅是向后兼容的 Decision ID 投影；`decision_links` 必须同时冻结每条关系的
  `decision_id/container_event_id/event_id/relation/effective_at/known_at/symbol/market/status/link_source`；
  `container_event_id` 必须等于 `event_id`，且可用关系必须明确为 `execution`，
  并进入 episode 与 collection digest。缺少该闭包证据的旧 artifact 必须重建，不能供 P2F 使用。

## 4. 命令

从 review sidecar 重建本地 artifact：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  --db data/db/investment_review.sqlite3 `
  episode-build `
  --cutoff-at "2026-07-15T15:00:00+08:00" `
  --account portfolio `
  --portfolio-db data/db/portfolio.sqlite3 `
  --output data/processed/normalized/trade_episodes.local.json
```

查询与验证：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  episode-query data/processed/normalized/trade_episodes.local.json `
  --account portfolio --status closed

.\.conda\investment-system\python.exe -m src.investment_review `
  episode-validate data/processed/normalized/trade_episodes.local.json
```

输出 JSON 包含 episodes、snapshot catalog 引用、event consumption ledger、覆盖计数、blocker/warning/info 和 canonical digest。查询只返回事实投影及 lineage，不生成叙事分析。

## 5. 验收

```powershell
python -m pytest -q `
  tests/test_investment_review_trade_episodes.py `
  tests/test_investment_review_phase1.py `
  tests/test_investment_review_portfolio_context.py `
  tests/test_portfolio_snapshots.py `
  tests/test_portfolio_snapshot_cli.py `
  tests/test_portfolio_tracker.py
```

完整场景映射见 `tests/fixtures/investment_review_p2c/scenario_manifest.json`。P2C 完成后仍不自动进入 P2D。
