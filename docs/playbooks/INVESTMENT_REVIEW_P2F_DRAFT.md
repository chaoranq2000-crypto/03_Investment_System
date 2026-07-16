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
  --output <path>
```

facts-only 输出不得包含：

- 心理归因；
- 交易评分；
- 建议；
- 无来源结论；
- 使用结果倒推事前理由。

## 6. 可选解释层

模型解释应消费冻结 input bundle 与 facts artifact，而不是直接查询数据库。必须记录：

- model ID；
- prompt template ID/hash；
- input content ID；
- output hash；
- 参数；
- 失败状态。

模型失败时，facts-only artifact 仍然有效。

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
