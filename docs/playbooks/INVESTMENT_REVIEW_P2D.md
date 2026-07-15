# Investment Review P2D：可审计复盘事实包

## 1. 目标

P2D 把 P2C 的 `trade episodes` 转换为适合查询、展示和后续复盘编排的**事实包（review fact pack）**。

P2D 仍处于确定性数据层，不生成投资评价，不推断交易动机，不输出心理标签，也不提供买卖或仓位建议。

输入：

- P2C 交易周期 JSON artifact；
- 可选的明确 `cutoff_at`；
- 可选的 episode 选择器。

输出：

- 每个 episode 一个不可歧义的 JSON 事实包；
- 一个 `index.json`；
- 输入 artifact、episode 与输出文件的 SHA-256 provenance；
- 稳定排序的事实时间线；
- 对 `missing / unlinked / ambiguous / invalid` 的显式诊断；
- 明确的 `interpretation.status = not_inferred` 边界。

## 2. 为什么在 P2C 之后先做事实包

P2C 已经解决“如何从成交与已审核 sidecar 重构交易周期”。后续若直接进入自然语言复盘，会把以下职责混在一起：

1. 读取不同版本的 P2C schema；
2. 组织事实时间线；
3. 发现缺失或歧义链接；
4. 形成解释与行为假设。

P2D 将前三项固化为可重复、可校验的 read model。解释层以后只消费事实包，不能绕开 provenance 直接读取个人数据库。

## 3. 命令

从仓库根目录运行：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review.review_pack build `
  --episodes data/processed/normalized/trade_episodes.local.json `
  --output-dir data/processed/review_fact_packs/2026-07-15
```

也可使用脚本入口：

```powershell
.\.conda\investment-system\python.exe scripts/investment_review_p2d_review_pack.py build `
  --episodes data/processed/normalized/trade_episodes.local.json `
  --output-dir data/processed/review_fact_packs/2026-07-15
```

只构建指定 episode：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review.review_pack build `
  --episodes data/processed/normalized/trade_episodes.local.json `
  --output-dir data/processed/review_fact_packs/one_episode `
  --episode-id "ep:600519:20260701"
```

验证：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review.review_pack validate `
  --bundle-dir data/processed/review_fact_packs/2026-07-15 `
  --episodes data/processed/normalized/trade_episodes.local.json
```

## 4. 输入兼容面

支持以下 P2C JSON 根结构：

- episode 数组；
- 单个 episode 对象；
- 包含 `episodes`、`trade_episodes` 或 `items` 数组的对象。

episode 标识优先读取：

1. `episode_id`；
2. `trade_episode_id`；
3. `id`。

若源 episode 没有显式标识，P2D 使用源 episode 的 canonical SHA-256 生成稳定的 `synthetic:*` 标识，并把 `episode_id` 记录到 `missing_core_fields`。这不会把合成标识伪装成已证实的业务主键。

## 5. 确定性保证

同一输入字节、同一选择器和同一 cutoff 应产生字节一致的输出：

- JSON key 排序固定；
- 时间线排序固定；
- bundle id 由 schema、源 artifact hash、episode hash 与 episode id 派生；
- 不写入当前时间；
- 不写入源文件绝对路径；
- 输出目录非空时默认拒绝覆盖。

注意：源 artifact 的 SHA-256 以原始文件字节计算。即使 JSON 语义相同，重新格式化输入也会产生新的 source hash；这是 provenance 设计，不是缺陷。

## 6. 时间线

若源 episode 已有非空 `timeline`，P2D 将其视为 canonical 时间线，不再从其他集合重复派生。否则，P2D 从以下已知集合派生时间线：

- `events`；
- `event_refs`（当前 `portfolio.trade_episode.v1` 的 canonical 事件引用集合）；
- `fills` / `trades` / `executions`；
- `orders`；
- `snapshots` / `portfolio_snapshots` / `position_snapshots`；
- `snapshot_links`（当前 P2C 的快照链接集合）；
- `decisions` / `decision_links`；
- `information_events`。

每个派生条目保留：

- `source_collection`；
- JSON Pointer `source_pointer`；
- `source_sequence`；
- 原始 `facts`。

P2D 只进行可逆的组织与排序，不删改 `source_episode` 的原始顺序。

当前 P2C 的 `event_refs[].effective_at` 作为事件时间，
`snapshot_links[].event_time` 作为链接对应的事件时间；缺少前者时才使用
`snapshot_as_of`。这些兼容字段只用于事实时间线排序，不改变源对象。

## 7. 未解决链接

P2D 递归扫描 status 型字段，显式保留以下状态：

- `missing`；
- `unlinked`；
- `ambiguous`；
- `invalid`。

每条诊断包含 JSON Pointer。后续 UI 或 AI 复盘必须把这些状态展示为证据缺口，不得把缺失链接自动解释为“没有决策理由”或“没有组合约束”。

## 8. 解释边界

每个事实包必须包含：

```json
{
  "interpretation": {
    "status": "not_inferred"
  }
}
```

以下字段不得在 P2D 产生：

- 恐惧、贪婪、报复性交易等心理结论；
- 交易好坏分数；
- 买卖或仓位建议；
- 事后最优价格反推；
- 无证据的 Decision 或 snapshot 链接。

## 9. 验收门槛

P2D 可合并的最低门槛：

1. 全部新增测试通过；
2. 同输入双构建目录逐字节一致；
3. `validate` 能发现 bundle 篡改、episode 篡改和源 artifact 不一致；
4. P2C 的 unresolved 状态在事实包中不丢失；
5. 不增加第三方运行时依赖；
6. 不读取或写入 SQLite 源库；
7. 不修改 P2C artifact。

## 10. 后续接口

P2D 稳定后，下一层只允许消费：

- `index.json`；
- 对应 episode fact pack；
- 经审核的补充证据引用。

自然语言复盘应把句子分为 `fact / interpretation / alternative explanation / unknown`，并把事实句绑定到 `source_pointer`。这一解释层属于后续阶段，不在本补丁内。
