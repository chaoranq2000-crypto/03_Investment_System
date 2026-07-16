# P2F 全阶段一次性交付计划：单笔交易双视角复盘闭环

- **计划类型**：full-stage / spec-first / planning gate
- **目标仓库**：`chaoranq2000-crypto/03_Investment_System`
- **目标分支**：`codex/portfolio-tracker`
- **规划补丁基线**：`fa6680c8b5e6cfe23a03cc95b6c77800a3d27650`
- **生产实现依赖**：P2E-3 `trade_episode_portfolio_context` 完成并通过发布门禁
- **生成日期**：2026-07-15（Europe/London）
- **阶段代号**：P2F — Single-Episode Dual-View Review

## 1. 结论

P2F 可以采用“**一次性交付整个阶段**”的方式完成，但“一次性交付”只表示最终以一个统一补丁包、一个总验收门和一个发布说明收口，不表示把所有代码压成一个不可审查的大提交。

推荐做法是：

1. 对外只有一个 P2F 发布包；
2. 对内保留五个可独立回滚、可独立测试的实现提交；
3. 先完成确定性的输入与事实层，再接入受约束的解释层；
4. 所有 AI 生成内容必须建立在已冻结的输入 bundle 上；
5. 任何缺失、模糊、陈旧、未定价或未来信息风险都不得被自然语言掩盖。

P2F 的目标不是给交易打分，也不是生成买卖或仓位建议，而是对一个 `Trade Episode` 形成可追溯、可修订、事实与解释分离的单笔复盘 artifact。

## 2. P2F 在总体路线中的位置

P2F 消费以下事实层：

```text
P2C Trade Episode
      +
P2E-3 Episode Portfolio Context
      +
可选 Decision / 研究笔记 / 市场与结果事实
      ↓
P2F Review Input Bundle
      ↓
事实复盘 sections
      ↓
受约束解释与替代解释
      ↓
人工审核、修订、渲染与发布
```

P2F 只处理单个 episode 或明确的 episode 集合。跨交易行为统计、长期个人画像和干预效果验证不在本阶段内；这些属于后续跨交易分析与改进闭环。

## 3. 阶段总目标

P2F 必须稳定回答：

1. 这次交易周期发生了什么；
2. 当时可见的个股逻辑、组合状态和市场事实是什么；
3. 操作与已记录计划之间有哪些一致、偏离、矛盾或信息缺口；
4. 哪些判断属于事实，哪些只是解释或待验证假设；
5. 是否存在合理的替代解释；
6. 当时有哪些现实可执行的替代处理方案及其代价；
7. 复盘结果如何被人工纠正、形成新修订并保留审计链。

## 4. 阶段不可破坏的原则

### 4.1 事实与解释硬分层

- `fact_sections` 只能包含可由来源证明的陈述；
- `interpretation_sections` 必须引用事实 ID，不能直接引用未经登记的自由文本；
- 解释必须带不确定性、假设和替代解释；
- 事实缺失时不得用常识或模型猜测补齐。

### 4.2 双时间与事后信息隔离

所有输入必须保留：

- `effective_at`：信息对应的现实时间；
- `knowledge_at`：系统或用户何时可见；
- `review_cutoff`：本次复盘允许消费信息的截止点。

“结果复盘”可以在独立 outcome section 中使用事后信息，但不得把这些信息回填为事前决策依据。每条事实必须声明其 temporal role：`known_at_decision`、`learned_during_episode` 或 `known_after_episode`。

### 4.3 来源可追溯

每个事实、解释、替代解释和反事实选项都必须能追溯到：

- source reference；
- 输入 artifact content ID；
- 适用的时间边界；
- 生成或人工修订记录。

### 4.4 不机械评分、不直接建议

P2F 不输出：

- 单一总分；
- “好交易/坏交易”的机械标签；
- 买入、卖出、持有、仓位或收益建议；
- 心理诊断；
- 以事后最佳价格倒推的“唯一正确操作”。

### 4.5 不确定性必须结构化

至少支持：

```text
available
missing
unlinked
ambiguous
stale
unpriced
invalid
not_applicable
withheld_by_cutoff
```

未知值不能写成 `0`，没有证据不能写成“无影响”。

## 5. P2F 的统一 artifact 体系

### 5.1 Review Input Bundle

建议 schema：

```text
p2f.review_input_bundle.v1
```

它是确定性、只读、可哈希的输入冻结层，至少包含：

- episode 引用；
- P2E-3 portfolio context 引用；
- Decision / 笔记 /市场 / 结果来源清单；
- `as_of` 与 `knowledge_cutoff`；
- section availability；
- warnings；
- canonicalization version；
- stable `content_id`。

Input Bundle 不包含模型生成的解释。

### 5.2 Episode Review Artifact

建议 schema：

```text
p2f.episode_review.v1
```

顶层分为：

```text
identity
input_bundle_ref
revision
fact_sections
interpretation_sections
governance
warnings
```

事实 sections 建议覆盖：

1. `timeline`；
2. `security_context`；
3. `portfolio_context`；
4. `market_context`；
5. `outcome_context`；
6. `execution_consistency`。

解释 sections 建议覆盖：

1. `main_tensions`；
2. `hypotheses`；
3. `alternative_explanations`；
4. `counterfactual_options`；
5. `history_links`（仅在已有可靠相似案例输入时可用）。

## 6. P2F 内部五个实施单元

## P2F-1：Review Input Bundle 与依赖门禁

### 目标

把 P2C、P2E-3 和可选来源冻结为一个确定性的输入包，防止后续解释阶段读取漂移数据。

### 必须实现

- 精确 schema validator；
- canonical JSON 与 stable content ID；
- source inventory；
- 双时间过滤；
- section availability；
- warning propagation；
- 原子写入；
- 源数据库只读验证；
- `build / validate / show` CLI 或仓库现有等价入口。

### 门禁

若 P2E-3 不可用，允许构建 `portfolio_context = missing` 的事实输入包用于接口测试，但不得把 P2F 标记为完整发布。

## P2F-2：确定性事实复盘引擎

### 目标

从冻结输入中生成只包含可证明事实的复盘 sections。

### 必须实现

- 事件时间线；
- 个股/标的事实摘要；
- 操作前后组合变化；
- 计划与执行的可证明一致/偏离；
- 市场与结果 sections 的时序隔离；
- source refs；
- gap/contradiction detection；
- 稳定排序；
- facts-only rendering。

### 禁止

- 心理归因；
- “纪律差”“恐惧”“贪婪”等诊断；
- 自动推断未记录的投资逻辑；
- 通过盈利或亏损直接判断决策质量。

## P2F-3：受约束解释与反方审查

### 目标

在事实层之上生成可审核的解释，而非自由叙事。

### 必须实现

- interpretation schema；
- 每条 finding 引用事实 ID；
- assumptions；
- uncertainty；
- counterevidence；
- alternative explanations；
- no-advice policy check；
- prompt/template/model provenance；
- 输入/输出 hash；
- facts-only fallback；
- 模型失败时不破坏事实 artifact。

### 解释强度

使用离散置信度 `low / medium / high`，但置信度不是交易评分。`high` 仍必须保留反证或说明其缺失。

## P2F-4：人工审核、纠正、修订与渲染

### 目标

允许用户纠正 AI 或事实链接，并形成不可变的新修订。

### 必须实现

- review state：`draft / reviewed / corrected / superseded`；
- human review event；
- correction reason；
- supersedes chain；
- 不覆盖旧 artifact；
- JSON 与 Markdown render；
- show/diff/revision-list；
- correction 后重新验证；
- 修订不回写源交易数据库。

## P2F-5：全阶段加固与发布

### 目标

把前四个单元收口为一个可发布补丁。

### 必须实现

- 端到端 fixture；
- 双时间无泄漏证明；
- 模糊/缺失降级；
- no-advice/no-score regression；
- AI unavailable fallback；
- 人工纠正审计链；
- clean checkout 全仓测试；
- CI；
- base..target patch；
- manifest 与 SHA256；
- 发布说明和已知限制。

## 7. 推荐内部提交序列

最终对外是一包，但建议保留以下提交：

1. `P2F-1: freeze deterministic episode review inputs`
2. `P2F-2: build traceable facts-only episode reviews`
3. `P2F-3: add bounded interpretations and counter-review`
4. `P2F-4: add human correction, revisions, and rendering`
5. `P2F-5: harden end-to-end review release gates`

每个提交必须可独立运行定向测试。最终补丁从明确的生产基线 SHA 到 P2F 最终提交生成。

## 8. 预计实现触点

实际路径必须在 P2E-3 完成后的精确 checkout 中确认，逻辑触点为：

- `src/investment_review/`：bundle、facts、interpretation、revision、render、CLI；
- `src/portfolio/`：只复用公开 context/metric 查询，不复制公式；
- `tests/`：contract、temporal、provenance、policy、revision、CLI、E2E；
- `docs/contracts/`：输入与复盘 schema；
- `docs/playbooks/`：P2F 操作手册；
- `docs/plans/` / `codex_tasks/`：阶段记录。

禁止在接口盘点前创建第二套平行 episode、snapshot 或 metric 模型。

## 9. CLI 建议形态

最终命令名服从现有 CLI 风格，建议能力如下：

```powershell
python -m src.investment_review review-input-build `
  --episode-artifact data/processed/normalized/trade_episodes.local.json `
  --portfolio-context data/processed/normalized/trade_episode_portfolio_context.local.json `
  --episode-id EPISODE_ID `
  --review-cutoff "2026-07-15T15:00:00+08:00" `
  --output data/processed/reviews/review_input.local.json

python -m src.investment_review episode-review-build `
  --input-bundle data/processed/reviews/review_input.local.json `
  --facts-only `
  --output data/processed/reviews/episode_review.local.json

python -m src.investment_review episode-review-validate `
  --artifact data/processed/reviews/episode_review.local.json

python -m src.investment_review episode-review-correct `
  --artifact data/processed/reviews/episode_review.local.json `
  --correction corrections.local.json `
  --output data/processed/reviews/episode_review.rev2.local.json

python -m src.investment_review episode-review-render `
  --artifact data/processed/reviews/episode_review.rev2.local.json `
  --format markdown `
  --output reports/investment_review/episode_review.local.md
```

“带模型解释”的命令必须显式启用，默认可采用 facts-only，避免无意触发外部模型调用。

## 10. 测试门阵摘要

完整矩阵见 `P2F_FULL_STAGE_TEST_MATRIX_20260715.md`。全阶段至少覆盖：

1. 输入 canonical hash 稳定；
2. 输入顺序无关；
3. future information 被 cutoff 排除；
4. outcome 信息不回填 decision facts；
5. P2E-3 warning 原样传播；
6. missing 不变成 0；
7. facts 不包含无来源文本；
8. interpretations 必须引用 fact IDs；
9. 替代解释不可为空（适用时）；
10. no-advice/no-score policy；
11. 模型不可用时 facts-only 成功；
12. 模型输出 provenance 完整；
13. 人工纠正形成新修订；
14. 旧修订保持不变；
15. revision chain 无环；
16. CLI 原子写入；
17. 源数据库只读；
18. Markdown render 不丢 source refs；
19. invalid schema 拒绝发布；
20. clean checkout 全仓回归。

全阶段最低要求为 **64 个定向用例**（14 + 16 + 14 + 12 + 8）。
最终实现可以增加更多语义与 mutation 用例，但不得用较小数量包装完成度。

## 11. 发布验收标准

P2F 只有同时满足以下条件才可标记为完成：

- P2E-3 已完成且生产基线 SHA 明确；
- P2F-1 至 P2F-5 定向测试全部通过；
- `compileall` 通过；
- 全仓测试无回归；
- 干净检出复验通过；
- 远端 CI 成功；
- facts/interpretations schema 分离；
- 双时间测试证明无未来信息泄漏；
- 所有非空事实有来源；
- 所有解释有事实引用、假设和不确定性；
- no-advice/no-score gate 通过；
- 人工纠正和 supersedes 链可审计；
- 生成单一 P2F 实现 ZIP、manifest、base/target SHA 与 SHA256。

## 12. 明确不做

P2F 不包含：

- 跨多笔交易的稳定行为模式统计；
- 长期个人画像自动更新；
- 干预试验和方法库效果评估；
- 自动交易、下单权限或仓位建议；
- 实时行情监控；
- 用 LLM 代替确定性指标计算；
- 未经人工审核直接把解释写入长期画像。

## 13. 依赖与基线策略

### 13.1 本规划补丁

本规划补丁只新增文档、schema 草案和任务卡，可在 `fa6680c8b5e6cfe23a03cc95b6c77800a3d27650` 上通过 `git apply` 预检。

### 13.2 生产实现补丁

生产实现不得直接假定 `fa6680c8b5e6cfe23a03cc95b6c77800a3d27650` 已具备 P2E-3。开始 P2F 代码前必须：

1. 确认 P2E-3 最终提交 SHA；
2. 确认 `p2e3.trade_episode_portfolio_context.v1` 或其最终命名；
3. 盘点真实 registry、CLI、repository 和 fixture；
4. 将本草案字段映射到真实接口；
5. 在独立 clean checkout/worktree 中实现。

若 P2E-3 最终契约与草案不同，应修订 P2F schema，而不是复制或绕过 P2E-3。

## 14. 风险与降级

| 风险 | 处理 |
|---|---|
| P2E-3 未完成 | 只允许 contract/fixture 开发，不发布完整 P2F |
| 市场或 Decision 来源缺失 | section 标记 missing，不生成伪事实 |
| 模型服务不可用 | 输出 facts-only artifact，保留解释缺失 warning |
| 模型叙事越界 | policy validator 拒绝发布解释层，事实层仍保留 |
| 事后信息污染事前判断 | temporal role + cutoff 测试 + section 隔离 |
| 人工纠正覆盖旧结果 | append-only revision + supersedes chain |
| 同秒事件顺序不足 | 继承 P2E-3 ambiguous，不自行猜测 |
| 大包难审查 | 内部五提交、单元门禁、最终统一 ZIP |

## 15. 一次性交付包应包含

生产完成时，最终 P2F ZIP 至少包含：

- `base..target` git patch；
- 变更文件副本；
- master plan；
- 两份正式 schema；
- 示例输入与示例复盘；
- 测试矩阵与实际测试结果；
- CI 链接；
- release notes；
- known limitations；
- apply/verify 脚本；
- manifest；
- SHA256SUMS。

本包先提供上述结构的规划门禁版，防止在缺少精确源码和 P2E-3 生产接口时伪造“已完成实现”。
