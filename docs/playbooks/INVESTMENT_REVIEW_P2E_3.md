# 投资复盘 P2E-3：交易周期组合上下文

## 1. 范围

P2E-3 把 P2C `TradeEpisode` 的 material event 锚点，与在双时间边界内可证明的
P2B 快照和 P2E-2 指标绑定，生成只读事实 artifact：

```text
portfolio.trade_episode.collection.v1
                +
read-only portfolio snapshot SQLite
                +
P2E-2 versioned metric registry
                ↓
p2e3.trade_episode_portfolio_context.v1
```

它不评价交易、不推断动机、不输出建议，也不把当前价格、当前行业分类或后来修订
回填为历史决策时点事实。

## 2. 锚点与证明标准

每个 episode 的 material event 生成 `pre` 与 `post` 两个锚点；首个事件为
`episode_open`，明确关闭事件为 `episode_close`，其余为 `position_change`。

- `pre` 只消费 P2C 已有的 `before_* / latest_at_or_before` 链接，不自行改选另一个
  快照；
- `post` 只消费 P2C 的 `after_* / exact_event_cursor` 链接，并再次核对当前事件已
  包含、账户内更晚的可见事件未包含；
- 当前 P2C cursor 是标的 partition 级，不是账户组合级。若 catalog 没有同时声明
  `cursor_scope=account` 与 `included_event_set_complete=true`，同业务日快照只能标为
  `replayed`，全部指标降为 `partial` 并带
  `PORTFOLIO_CURSOR_SCOPE_LIMITED`，不能写成 `exact`；
- 同秒事件缺少业务序列、同秒现金记录缺少显式 revision，或日级快照不能证明盘中
  边界时，状态必须降级为 `ambiguous` 或 `missing`；
- 不依赖 SQLite `rowid`、物理插入顺序或随机 UUID 排序解释业务先后。

所有来源同时满足：

```text
effective_at <= anchor.as_of
knowledge_at <= anchor.knowledge_cutoff
```

## 3. 指标与缺失值

指标直接调用 P2E-2 的版本化 registry，保留 Decimal 字符串、单位、方法版本、
source refs 和 warning codes。P2E-3 不复制指标公式。

缺失、陈旧、未定价、行业不可追溯、非正 NAV 或方法不兼容都保留结构化状态。
未知值为 `null`，不能写成 `0`。只有来源能够证明数值确实为零时才允许字符串
`"0"`。

P2B 没有直接观测 NAV 字段。只有现金可用、所有持仓估值完整且汇总值与明细精确
对账时，适配层才以 `cash + complete market_value` 生成 P2E-2 所需 NAV 输入，并
记录 `P2B_NAV_DERIVED`。只要存在未定价或被双时间规则剔除的价格，该快照即
`invalid`、指标为空，并记录 `PARTIAL_NAV_UNAVAILABLE`；不会把缺失持仓按零计入。

delta 仅在两端指标均为 `available`、单位一致且方法版本相同时计算；`partial` 端点
不会升级成数值 delta。

validator 先执行 production JSON Schema（包括 required、additionalProperties、
Decimal、方法/registry 版本），再检查 content ID、双时间、source refs、context/
delta 引用与精确差值。P2C 若有结构性 blocker 会拒绝构建；仅
`DECISION_LINK_AMBIGUOUS` 与 `DECISION_LINK_INVALID` 可作为显式决策链接状态保留。
语义校验还会重算 context/delta 的 canonical ID，要求每个 material event 恰有一组
身份一致的 `pre/post` context、可用快照覆盖 P2E-2 全部核心 registry 指标、delta
完整覆盖两端指标并且不多不少。P2C 的 snapshot/episode ID 必须唯一，catalog 中的
instrument/event cursor 也必须与只读数据库和完整账户事件集合一致；不能靠重算
artifact hash 掩盖删行、换标的或来源漂移。

校验分为两层：

- `offline_structural` 使用 artifact 内嵌的 `source_binding` 检查 material-event
  覆盖、context/source/cursor 绑定、registry 单位和值域、availability ceiling、
  canonical 时间/数组和 delta 状态机；
- `source_replay` 额外读取原 P2C artifact 和 P2B SQLite，使用同一 cutoff 与 selection
  重建 artifact 并逐字节比较。P2-F 只能消费 `source_replay` 返回
  `source_verification.status=verified` 的产物。

没有可信源输入、外部签名或不可变承诺时，任何离线 SHA-256 都只能证明当前对象
自洽，不能证明它对应真实且完整的外部历史；因此不能用离线 `accepted` 替代带源重放。

仓库中的 schema 文件为保持 planning package 路径兼容仍保留 `_DRAFT` 文件名；运行时
已把其中收紧后的内容作为 `p2e3.trade_episode_portfolio_context.v1` production contract。

## 4. 命令

构建：

```powershell
conda run -p C:\Projects\03_Investment_System\.conda\investment-system `
  python -m src.investment_review `
  episode-portfolio-context-build `
  --episode-artifact data/processed/normalized/trade_episodes.local.json `
  --portfolio-db data/db/portfolio.sqlite3 `
  --cutoff-at "2026-07-15T15:00:00+08:00" `
  --knowledge-cutoff "2026-07-15T15:00:00+08:00" `
  --output data/processed/normalized/trade_episode_portfolio_context.local.json
```

查询与验证：

```powershell
conda run -p C:\Projects\03_Investment_System\.conda\investment-system `
  python -m src.investment_review episode-portfolio-context-show `
  data/processed/normalized/trade_episode_portfolio_context.local.json `
  --episode-id <episode_id> `
  --content-id sha256:<artifact_content_id>

conda run -p C:\Projects\03_Investment_System\.conda\investment-system `
  python -m src.investment_review episode-portfolio-context-validate `
  data/processed/normalized/trade_episode_portfolio_context.local.json `
  --source-replay `
  --episode-artifact data/processed/normalized/trade_episodes.local.json `
  --portfolio-db data/db/portfolio.sqlite3
```

构建器以 SQLite `mode=ro` 和 `PRAGMA query_only=ON` 读取源库；artifact 使用同目录
临时文件与原子替换写入。相同输入、cutoff、registry 版本和源修订应产生相同字节
与 `content_id`。

## 5. 验收

```powershell
conda run -p C:\Projects\03_Investment_System\.conda\investment-system `
  python -m pytest -q tests/test_investment_review_episode_portfolio_context.py

conda run -p C:\Projects\03_Investment_System\.conda\investment-system `
  python -m pytest -q
```

完整发布还要求在干净检出中复跑全仓测试、记录实现基线/目标 SHA、生成
`base..target` 补丁包和 SHA256，并在获得明确推送授权后确认远端 CI。
