# P2E-3 下一阶段执行计划：Trade Episode 组合上下文绑定

- **计划类型**：spec-first / planning gate
- **目标仓库**：`chaoranq2000-crypto/03_Investment_System`
- **目标分支**：`codex/portfolio-tracker`
- **预期基线**：`fa6680c8b5e6cfe23a03cc95b6c77800a3d27650`
- **生成日期**：2026-07-15（Europe/London）
- **计划状态**：待在精确基线检出中实现与验证

## 1. 结论

下一阶段建议定为 **P2E-3：Trade Episode Portfolio Context Integration**。

P2C 已把成交和已审核事件重构成确定性的 `Trade Episode` 事实 artifact；P2E-2 已提供组合指标、方法标识、双时间、缺失数据警告和 Decimal 精度。两者之间仍缺一个稳定、只读、可追溯的连接层：在每个交易周期的关键操作时点，记录“操作前”和“操作后”的组合状态、指标变化、数据可用性和来源链。

P2E-3 不做交易评价，也不推断心理原因。它只产出可复现的组合上下文事实，为后续单笔双视角复盘、行为序列分析和市场环境分析提供可信输入。

## 2. 为什么现在做这一层

当前能力分别回答：

1. `Trade Episode`：这次交易周期发生了什么；
2. P2E-2 指标：某个组合快照呈现什么可追溯指标；
3. P2E-3：这些组合指标在该交易周期的关键决策锚点上是什么，以及操作造成了哪些可证明的变化。

若直接进入行为归因或自然语言复盘，会出现三类风险：

- 指标与具体操作时点没有稳定绑定，容易发生事后信息泄漏；
- 同秒成交、现金快照和修订记录可能因隐式数据库顺序而产生非确定结果；
- 缺失、陈旧、未定价或链接不确定性可能被上层叙述吞掉。

因此，P2E-3 应先把“事实连接层”做成版本化契约。

## 3. 目标产物

新增一个确定性 artifact，建议逻辑名称为：

```text
trade_episode_portfolio_context
```

建议 schema 标识：

```text
p2e3.trade_episode_portfolio_context.v1
```

每个 artifact 至少包含：

- 源 `episode_artifact` 的内容标识、schema 版本和只读引用；
- 请求的 `as_of` 与 `knowledge_cutoff`；
- 每个 episode 的关键锚点；
- 每个锚点的组合快照引用；
- P2E-2 指标及方法/输入来源；
- 可比较锚点之间的 Decimal 差值；
- 缺失、模糊、陈旧、未定价和链接状态警告；
- canonical 内容哈希和稳定排序规则。

## 4. 锚点模型

### 4.1 最小锚点集合

对每个 episode 生成：

- `episode_open / pre`
- `episode_open / post`
- 每个会改变持仓或现金的 material event：`position_change / pre` 与 `position_change / post`
- 已关闭 episode：`episode_close / pre` 与 `episode_close / post`

重复语义的锚点可以合并，但必须保存原始 event 引用，不能因合并丢失来源。

### 4.2 前后边界

- `pre`：严格位于当前 event 排序键之前的可见状态；
- `post`：包含当前 event 后的可见状态；
- 不得只用秒级时间比较来判断前后；
- 同一时间戳的多个事件必须使用确定性顺序键。

建议顺序键优先级：

```text
occurred_at_utc
→ broker/order/fill sequence（存在时）
→ source event type rank
→ stable source event id
```

现金或组合快照的候选修订建议使用：

```text
effective_at_utc
→ knowledge_at_utc
→ revision_number
→ stable snapshot id
```

不得依赖 SQLite 未声明顺序、物理插入位置或 `rowid` 作为业务语义。若来源无法提供足够信息建立顺序，输出 `ambiguous`，不要猜测。

## 5. 双时间与防止未来信息泄漏

每次解析必须同时满足：

```text
source_effective_time <= anchor.as_of
source_knowledge_time <= anchor.knowledge_cutoff
```

规则：

1. `knowledge_cutoff` 不得晚于调用方明确传入的 cutoff；
2. 价格、行业分类、成交修订和现金修订分别执行双时间过滤；
3. 未来补录的数据可产生新 artifact 修订，但不得重写旧 artifact；
4. `pre` 与 `post` 必须记录各自实际消费的源修订 ID；
5. timezone 统一转换为 UTC canonical 表达，展示层可保留原时区。

## 6. 指标复用原则

P2E-3 不重新实现 P2E-2 公式。它通过现有公开服务/查询接口调用指标，并原样保留：

- `metric_key`
- Decimal 字符串值；
- 单位；
- `method_id` 与 `method_version`；
- 输入源引用；
- 可用性状态；
- warning codes。

首版至少覆盖以下类别；执行时应映射到 P2E-2 的实际 registry key，不在 P2E-3 私自创造同义公式：

- 组合净值与定价覆盖；
- 现金比例；
- 总体投入/暴露；
- 目标标的权重；
- 单一标的集中度；
- Top-N 集中度；
- 行业集中度（分类可用时）；
- 未定价与陈旧价格计数/比例。

差值仅在两端指标都可用、单位相同、方法版本兼容时计算。否则保留 `null` 并给出结构化原因。

## 7. 数据契约要点

### 7.1 顶层

```json
{
  "schema_version": "p2e3.trade_episode_portfolio_context.v1",
  "content_id": "sha256:<canonical-payload-hash>",
  "episode_artifact_ref": {
    "content_id": "...",
    "schema_version": "..."
  },
  "as_of": "2026-07-15T15:00:00+08:00",
  "knowledge_cutoff": "2026-07-15T15:00:00+08:00",
  "contexts": [],
  "deltas": [],
  "warnings": []
}
```

### 7.2 确定性约束

- canonical JSON 使用 UTF-8、固定字段语义、稳定数组排序；
- Decimal 只序列化为字符串，不写二进制浮点；
- wall-clock `generated_at` 不进入内容哈希；
- 相同输入引用、cutoff、算法版本和源数据修订必须得到相同 `content_id`；
- 输入顺序变化不得改变输出；
- 原子写入，失败时不留下半成品。

完整草案见 `P2E-3_CONTRACT_DRAFT.schema.json`。

## 8. 建议实现步骤

### P2E-3a：契约与边界

1. 在精确基线检出中盘点 P2C episode schema、P2E-2 metric registry/repository、CLI 组织方式和测试 fixture；
2. 把本包 schema 草案映射到现有命名；
3. 新增 validator、canonical serializer 和稳定 content ID；
4. 新增最小 fixture 与 schema 测试；
5. 不接数据库、不新增 CLI。

建议单独提交，便于在接口不匹配时回滚。

### P2E-3b：构建器与双时间查询

1. 只读加载 episode artifact；
2. 生成锚点并应用确定性同秒顺序；
3. 通过现有 portfolio snapshot/metric API 获取上下文；
4. 保留每个指标的 source refs、method 和 warnings；
5. 计算兼容的 pre/post delta；
6. canonicalize、validate、hash、atomic write；
7. 验证源数据库没有写入。

### P2E-3c：CLI、查询、文档和发布门禁

建议命令形态（最终名称服从现有 CLI 风格）：

```powershell
python -m src.investment_review `
  --db data/db/investment_review.sqlite3 `
  episode-portfolio-context `
  --episode-artifact data/processed/normalized/trade_episodes.local.json `
  --portfolio-db data/db/portfolio.sqlite3 `
  --cutoff-at "2026-07-15T15:00:00+08:00" `
  --knowledge-cutoff "2026-07-15T15:00:00+08:00" `
  --output data/processed/normalized/trade_episode_portfolio_context.local.json
```

同时提供：

- `...-show` 或等价查询入口；
- `...-validate` 或等价验证入口；
- playbook、schema 字段说明和缺失状态说明；
- 定向测试、全仓测试、干净检出复验和 CI。

## 9. 预计代码触点

以下是“逻辑触点”，实际路径必须在 `fa6680c` 精确树中确认后再定：

- `src/investment_review/`：artifact model、builder、canonicalization、CLI wiring；
- `src/portfolio/`：只复用公开 snapshot/metric query，不复制公式；
- `tests/`：contract、builder、temporal boundary、CLI、read-only；
- `docs/playbooks/`：操作手册；
- `docs/plans/` / `codex_tasks/`：阶段记录。

禁止在未检查现有接口前直接按上述建议路径创建平行实现。

## 10. 定向测试门阵

最低要求见 `P2E-3_TEST_MATRIX.md`，核心门禁包括：

1. canonical hash 稳定；
2. 输入顺序无关；
3. Decimal 不落入 float；
4. 双时间排除未来成交、价格、分类和修订；
5. 同秒成交使用稳定顺序；
6. 同秒现金/快照修订不依赖隐式数据库顺序；
7. missing / ambiguous / stale / unpriced / invalid 状态完整传播；
8. partial/open episode 可生成而不伪造 close；
9. 方法版本不兼容时不计算 delta；
10. 源数据库只读；
11. 历史补录产生新内容 ID 且旧 artifact 不变；
12. CLI 原子写入、验证失败不留半文件；
13. 时区归一化；
14. 零或负 NAV 的明确处理；
15. clean checkout 全仓回归。

特别加入同秒排序用例，用于覆盖已观察到的现金快照偶发排序风险。

## 11. 验收标准

P2E-3 只有同时满足以下条件才可发布：

- HEAD 与远端目标基线/实现提交一致；
- 所有新增定向测试通过；
- 全仓测试无回归；
- 干净检出复验通过；
- CI 成功；
- artifact 对同一输入完全确定；
- 双时间测试证明无未来信息泄漏；
- 源库 hash 或事务审计证明构建过程只读；
- 每个非空指标能追溯到方法与输入；
- 每个缺失值有结构化状态，不以 `0` 代替未知；
- 生成补丁 ZIP、manifest 和 SHA256。

全仓通过数应以执行时实际收集结果记录，不预先假定等于“既有 771 + 新测试数”。

## 12. 明确不做

P2E-3 不包含：

- 行为模式或心理状态推断；
- “好/坏交易”评分；
- 买卖、仓位或收益建议；
- 市场环境/因子归因；
- 相关性矩阵和压力测试；
- 自然语言复盘生成；
- Web UI；
- 自动下单或交易权限。

这些能力只能消费 P2E-3 事实，不得反向污染事实 artifact。

## 13. 风险与应对

| 风险 | 应对 |
|---|---|
| P2E-2 实际接口与草案命名不同 | 先做接口盘点和 registry 映射，不复制公式 |
| 同秒事件无法证明顺序 | 输出 `ambiguous`，保留候选源引用 |
| 快照粒度不足以给每笔 fill 生成 post 状态 | 使用已有 replay API；仍不足时降低锚点粒度并显式 warning |
| 分类数据在 knowledge cutoff 时不可见 | 指标置为 missing/not_applicable，不使用当前分类回填 |
| 生成时间破坏幂等 | wall-clock metadata 与 canonical payload 分离 |
| 脏工作区混入历史改动 | 在独立 worktree/clean checkout 实现和打包；本包脚本仅记录脏状态，不擅自清理 |

## 14. 推荐提交序列

1. `P2E-3a: define trade episode portfolio context contract`
2. `P2E-3b: build deterministic dual-time portfolio contexts`
3. `P2E-3c: add CLI, validation, documentation, and release gates`

每次提交都应可独立测试；最终补丁从用户确认的基线 SHA 到最终提交生成，不夹带原有未提交 portfolio 改动。

## 15. 发布清单

- [ ] 基线 SHA 门禁通过；
- [ ] 远端分支 SHA 与本地一致；
- [ ] 精确接口盘点完成；
- [ ] schema 与 validator 完成；
- [ ] builder 与同秒排序完成；
- [ ] 双时间和缺失状态完成；
- [ ] 定向测试完成；
- [ ] 全仓测试完成；
- [ ] 干净检出复验完成；
- [ ] CI 成功；
- [ ] 生成实现补丁 ZIP；
- [ ] 写入 manifest、基线/目标 SHA 和 SHA256；
- [ ] 保留旧修订和用户现有脏工作区。
