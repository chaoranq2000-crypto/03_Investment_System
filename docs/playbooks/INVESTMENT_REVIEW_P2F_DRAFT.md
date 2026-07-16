# Investment Review P2F Draft Playbook

> 本文件从规划门禁持续升级为 P2F 生产手册。各单元只有在对应提交、定向测试、
> 全仓测试和发布门通过后才视为可用。

## 1. 目的

P2F 将单个 `Trade Episode`、组合上下文以及可选 Decision/市场/结果来源，组织为事实与解释分离的单笔复盘 artifact。

## 2. 默认工作流

```text
依赖检查
→ review input bundle
→ facts-only review
→ 可选模型解释
→ policy validation
→ 人工审核/纠正
→ revision render
```

默认先运行 facts-only。模型解释必须显式启用。

## 3. 依赖检查

生产实现必须确认：

- P2C episode artifact 可验证；
- P2E-3 portfolio context artifact 可验证；
- P2E-3 使用原 P2C artifact 与只读 P2B SQLite 执行 source replay，且结果为
  `source_verification.status=verified`；
- 两者 episode ID 与 cutoff 可对齐；
- 所有来源只读；
- 输出目录与源数据库分离。

P2E-3 缺失时，只允许显式 contract-only bundle；其
`release_readiness.status` 必须为 `blocked`，完整 P2F release gate 必须失败。

## 4. 构建输入包

建议能力：

```powershell
python -m src.investment_review review-input-build `
  --episode-artifact <path> `
  --portfolio-context <path> `
  --portfolio-db <read-only-p2b-sqlite> `
  --episode-id <id> `
  --review-cutoff <timestamp> `
  --output <path>
```

输入包必须可重复构建、可验证、可哈希，并明确每个 section 的 availability。
它必须内嵌所选 P2C episode、该 episode 实际引用的 P2C `snapshot_catalog`
精确子集、P2E-3 的 material events/contexts/deltas/warnings 切片以及
cutoff-safe 的显式 Decision/补充来源。只保存 locator 或 content ID 不构成
冻结输入；后续 facts/model 阶段不得重新查询源数据库。

P2F-1 不信任调用方自行声明的 Decision 绑定。P2C episode 必须先包含 canonical
`decision_links`；Decision source 的 `event_id/event_ids`、`relation`、`effective_at`、
`knowledge_at` 必须逐字段匹配该 Decision 的全部 canonical links，并冻结排序唯一的
`decision_link_refs[]`（逐 link 保存 event、relation、content ID、availability 与 warnings）。
只含旧式 `decision_refs` 的 P2C artifact 必须重建。

被 `review_cutoff` 排除的可选来源不得冻结 payload，但必须进入
`source_requests` / `excluded_sources` 元数据清单；顶层 warnings 必须由冻结来源、
排除清单与 upstream findings 精确派生，不能自报或静默删除。

`review-input-validate` 默认验证内部契约；进入后续阶段或发布前必须提供原始
P2C、P2E-3 和 P2B SQLite 执行 source replay。artifact 自报的
`source_verification` 不能替代真实重放。

## 5. 构建事实复盘

```powershell
python -m src.investment_review episode-review-build `
  --input-bundle <path> `
  --facts-only `
  --output <path> `
  --markdown-output <optional-path>
```

P2F-2 只接受 `release_readiness.status=ready` 且
`source_verification.status=verified` 的 P2F-1 bundle。它不会接收数据库、网络或
模型参数，也不会在构建过程中重新读取来源。输出固定为
`p2f.episode_review.v1` 的 revision 1/draft，并包含六个事实区：

- `timeline`：episode lifecycle 与 canonical execution events；
- `security_context`：标的身份、显式 Decision 与记录型 note；
- `portfolio_context`：P2E-3 anchors、metrics 与可比较 deltas；
- `market_context`：cutoff-safe market/price/classification 来源记录；
- `outcome_context`：结果来源及其实际双时间角色；
- `execution_consistency`：显式 Decision link 与结构化计划字段比较。

每条 fact 都保存稳定 `fact_id`、`claim_type=fact`、availability、
`effective_at/knowledge_at`、temporal role、固定中性 statement、闭合 data 以及
指向 P2F-1 inventory 的五字段 source ref。原始自由文本不晋升为客观事实；市场、
note 与 outcome 只保留来源存在、类型、内容哈希、字段清单和经过白名单的结构化值。

只有显式结构化的 `planned_symbol/planned_market/planned_side/planned_quantity`
（或 `execution_plan` 中的同名语义字段）可以与执行事实比较。输出只使用
`matches/deviates`，不评价交易或决策好坏；没有可比较字段、偏离原因缺失、
多事件数量不可直接比较时均写入 gap code。

时间角色只能是 `known_at_decision / learned_during_episode /
known_after_episode / not_applicable`。execution、post context、delta、outcome 和
consistency 不得回填为事前事实；open episode 不伪造 final outcome。

离线 validator 证明 schema、hash、fact ID、固定模板和内部双时间规则；发布或下游
解释前还必须执行 source replay：

```powershell
python -m src.investment_review episode-review-validate <review.json> `
  --source-replay `
  --input-bundle <review-input.json>
```

facts-only 输出不得包含：

- 心理归因；
- 交易评分；
- 建议；
- 无来源结论；
- 使用结果倒推事前理由。

## 6. 可选解释层

P2F-3 只消费已通过校验和 source replay 的 facts artifact。固定 prompt 只包含
fact ID、中性 statement、availability、双时间角色和 section gap/warning，不包含原始
Decision/note/source payload，也不重新查询 input bundle、数据库或网络。

仓库不内置默认联网 provider。模型解释必须通过显式 provider 注入；CLI 只接受已记录的
UTF-8 provider response，或显式运行 unavailable fallback：

```powershell
python -m src.investment_review episode-review-interpret `
  --artifact <facts-review.json> `
  --model-id <recorded-model-id> `
  --generated-at <canonical-utc-seconds> `
  --model-response <recorded-response.json> `
  --parameters-json '{"temperature":"0"}' `
  --output <model-assisted-review.json> `
  --attempt-output <interpretation-attempt.json>
```

provider response 必须匹配 `p2f.interpretation_output.v1`：每条 finding 具有
fact refs、`decision_time/retrospective` perspective、assumptions、uncertainty、
counterevidence status/refs；counterfactual 具有 `decision_time/episode_time`
scope、可行性、tradeoffs 与 `not_advice=true`。没有 typed history input 时
`history_links` 必须为空。

解释 artifact 必须记录：

- model ID；
- prompt template ID/hash；
- facts-only input content ID；
- 原始 provider output hash；
- normalized interpretation content ID；
- interpretation engine version；
- 参数；
- canonical generated time。

policy/temporal gate 拒绝心理诊断、直接买卖/持有/仓位建议、机械评分、用盈亏判定
决策质量、把 outcome 写入 decision-time finding，以及使用事后最佳价或 episode 结束后
信息的 counterfactual。

provider 超时/不可用、非法 JSON、schema 或 policy 校验失败时，输出必须回退为字节完全
不变的 facts-only artifact；失败原因只进入独立
`p2f.interpretation_attempt.v1` receipt，不污染事实 artifact。模型成功后的 source replay
只重放并比对不可变事实层，不重新调用模型；原始响应 hash 通过 attempt receipt 单独复核。

## 7. 验证

至少包含：

```text
schema validation
temporal validation
source-reference validation
no-advice policy
no-score policy
revision-chain validation
```

任何解释层失败不得破坏已生成事实层。

## 8. 人工纠正

纠正必须生成新修订，保存：

- target IDs；
- action；
- reason；
- actor reference；
- reviewed_at；
- supersedes content ID。

不得覆盖旧文件或修改源交易/组合数据库。

## 9. 渲染

建议支持 JSON 与 Markdown。Markdown 必须显示：

- 事实/解释区分；
- availability；
- warnings；
- source refs；
- revision 状态；
- 模型与人工审核 provenance；
- “非交易建议”边界。

## 10. 发布门禁

只有在定向测试、全仓测试、clean checkout、CI 和包校验全部通过后，才能标记 P2F 完成。
