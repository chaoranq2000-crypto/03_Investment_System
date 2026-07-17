# P2G-1：确定性跨 Trade Episode 事实样本包

## 目标

在显式 `effective window` 和 `knowledge_cutoff` 下，从 canonical P2F review
修订链中冻结一个确定性、可重放、facts-only 的跨 Episode cohort。该 artifact
是后续跨 Episode 事实信号的输入边界，不是行为结论。

## 权威输入

- `p2f.episode_review.v1` 的完整 append-only 修订链；
- 每条 review 绑定的 `p2f.review_input_bundle.v1`；
- 显式 `effective_from`、`effective_to`、`effective_anchor`、
  `knowledge_cutoff` 和可选 account/instrument filter。

禁止读取可变 `latest` 路径、文件 mtime、网络、模型、向量库、组合 SQLite
或任何 cutoff 后才可见的材料。

## 核心不变量

1. 时间窗口为 `[effective_from, effective_to)`；所有时间写成 UTC 秒级 `Z`。
2. 先按 cutoff 截断修订链，再验证得到唯一 current leaf；不得按 mtime、路径、
   revision number 最大值或输入顺序选“最新”。
3. cutoff 后新增 correction 不改变 cutoff 前 cohort 的 bytes/content ID。
4. 每个入选 leaf 必须通过 P2F review validator、revision-chain validator 和
   `replay_validate_episode_review`。
5. input bundle 必须 `release_readiness=ready` 且
   `source_verification=verified`。
6. cohort 内嵌所选 review 的完整 `facts_only_projection`，不内嵌或消费
   interpretation 文本。
7. `missing`、`partial`、`ambiguous`、`stale`、`unpriced`、warnings、gaps 和
   source refs 原样保留，不转成 `0` / `false`。
8. canonical identity 不含路径、locale、timezone、hash seed、运行时间或
   `created_at`。
9. artifact 默认 create-only；不得静默覆盖。
10. release blocked 时 CLI 返回非零，但结构合法的 blocked artifact 仍可保存、
    查询和审计。

## 当前仓库契约映射

| P2G 语义 | 复用实现 |
|---|---|
| canonical JSON / SHA-256 | `src/investment_review/artifact_io.py` |
| create-only 原子写入 | `atomic_create_bytes` |
| review schema / facts validator | `validate_episode_review` |
| 解释隔离 | `facts_only_projection` |
| append-only 修订链 | `validate_revision_chain` |
| P2F source replay | `replay_validate_episode_review` |
| P2F input release/source 状态 | `validate_review_input_bundle` + frozen fields |
| UTC 解析 | `time_utils.parse_datetime` / `utc_iso` |

P2F 当前的 `accept/reject/correct` 针对 interpretation finding 或 option，
不是整份 facts artifact 的发布投票。因此一个 finding 被 `reject` 时，P2G 仍可
选择该修订的不可变 facts projection；`human_rejected` 原因保留给未来显式的
artifact-level rejection 契约，不从现有 finding-level reject 推断。

## 产物

- `docs/contracts/P2G_BEHAVIOR_COHORT_DRAFT.schema.json`
- `src/investment_review/behavior_cohort.py`
- `tests/test_investment_review_behavior_cohort.py`
- `docs/playbooks/INVESTMENT_REVIEW_P2G_1.md`

## 非目标

- 不生成心理标签、行为模式、置信度、综合分数或相似案例排序；
- 不调用模型、embedding、向量库或外部网络；
- 不输出买入、卖出、持有、仓位或收益建议；
- 不修改 P2F artifact、组合数据库或 review sidecar；
- 不进入 P2G-2/P2G-3/P2G-4/P2G-5。

## 完成门禁

- P2G schema/builder/validator/query/load/save/replay/CLI 完成；
- cutoff、revision、source replay、facts-only、原子写入和 fail-closed 测试通过；
- P2F 定向回归与全仓回归通过；
- clean-checkout、base→target apply、tree equality、reverse check 通过；
- CI 对精确目标 SHA 成功；
- 只发布 P2G-1 文件，不夹带其他并行工作树修改或补丁 ZIP。
