# A-share Research OS / A股投研工作区

> 这是一个证据驱动的 A 股投研工作区，不是自动交易系统，也不直接提供买入、卖出或持有建议。

## 项目定位

A-share Research OS 的目标是把 A 股投研过程拆成可维护、可复用、可审查的工作流：

```text
用户输入：细分方向 / 股票 / 对比任务 / 更新任务
        ↓
Codex Skills：标准化投研动作
        ↓
研究对象库 + 证据库：沉淀证据、事实、指标、映射关系和状态
        ↓
产出层：细分报告、个股深度、对比矩阵、观察清单、投资备忘录
```

核心原则：

- 证据库是核心。
- 报告是某一时点的可再生产物。
- 细分方向和上市公司是多对多关系。
- 投研结论必须能追溯到 evidence / claim / metric / TODO。
- 更新研究时必须输出变化记录。

## 当前阶段

当前处于 **P1.6：workflow buildout / 进入 P2 前的工作流制度化**。

P1.6 是项目总阶段标签；具体 R5 Bundle、当前 gate 与允许的产出级别，以 `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md` 中最新 canonical close readout 为准，README 不作为运行时状态事实源。

P1.6 的重点是：

1. 固化 `docs/workflows/RESEARCH_WORKFLOW.md` 作为唯一全局 workflow kernel。
2. 启用 `research-orchestrator` 作为总编排入口。
3. 补强 evidence ingest、stock deep dive、mapping、quality review 等下层契约。
4. 通过 stock-led、segment-led、segment-stock interlock 调试。
5. 执行 P2 readiness gate，只判断是否进入 limited P2 pilot。

P1.6 不做：扩展新细分、P2 横向比较、批量扩大公司池、自动交易、实时行情监控或买卖建议生成。

## 文档入口

| 文件 | 用途 |
|---|---|
| `AGENTS.md` | Codex 项目级长期规则和投研纪律。 |
| `docs/index.md` | 文档总索引；只导航，不承载事实源正文。 |
| `docs/project/PROJECT_CHARTER.md` | 项目目标、边界、路线图和暂停点。 |
| `docs/architecture/WORKSPACE_STRUCTURE.md` | 目录结构、文件归位和命名规则。 |
| `docs/architecture/RESEARCH_OBJECT_MODEL.md` | Segment、Company、Evidence、Claim、Metric 等对象模型。 |
| `docs/policies/EVIDENCE_AND_CITATION_POLICY.md` | 证据、引用、来源等级和新鲜度规则。 |
| `docs/policies/QUALITY_GUARDRAILS.md` | 质量检查、反幻觉、反证和 no-advice 纪律。 |
| `docs/workflows/README.md` | workflow 文档入口。 |
| `docs/workflows/RESEARCH_WORKFLOW.md` | 唯一全局 workflow kernel；定义 `workflow_type`、global stage、global gate、backflow decision。 |
| `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | `research-orchestrator` 运行时规范；消费全局接口，不重新定义全局接口。 |
| `docs/workflows/DATA_LAYER_WORKFLOW.md` | 数据层 source adapter、manifest、candidate、data pack 边界。 |
| `.agents/skills/stock-deep-dive/references/report_production_profile.md` | 个股报告生产 profile；属于 `stock-deep-dive` 执行细节。 |
| `docs/meta/DOC_OWNERSHIP_MATRIX.md` | 文档职责边界和去重矩阵。 |

`docs/plans/`、`docs/logs/`、`docs/codex_tasks/` 是阶段性材料，不作为当前事实源阅读路径。

## Skills

P1.6 后，`research-orchestrator` 是总编排入口，下层 skills 执行具体研究动作：

```text
research-orchestrator
evidence-ingest
segment-research
company-universe
segment-company-mapping
stock-deep-dive
quality-review
refresh-research
compare-segments
compare-stocks
memo-writer
```

个股深度研究统一使用 `stock-deep-dive`。如果存在未启用或待合并的旧 skill 目录，应先按 `.codex/config.toml` 和 `docs/meta/DOC_OWNERSHIP_MATRIX.md` 判断是否仍可路由；不要让历史 skill 覆盖当前主工作流。

## 最小使用方式

```text
$research-orchestrator 启动个股优先闭环：002837 英维克。
目标：消费 evidence-ingest 产物，输出 stock package、segment_exposure、quality gate 和 close readout。
```

```text
$research-orchestrator 启动细分到个股闭环：AI服务器液冷。
目标：输出 segment package、company_universe、exposure mapping、stock sample 和 quality readout。
```

## 研究边界

本项目可以输出研究框架、证据地图、风险清单、评分卡、观察清单、情景假设和 refresh log。

本项目不输出直接买卖建议、仓位建议、保证收益判断或自动交易指令。

## 本地持仓记录

项目提供独立的本地持仓台账和可视化页面，可用期初快照记录持仓、通过 Tushare 刷新最新可得收盘价，并用券商交割单按移动加权平均成本重算数量、成本和盈亏。页面同时提供带来源的行业透视和从成交台账自动重放的清仓收益；主题 ETF 在行业属性明确时参与行业汇总，宽基或跨行业 ETF 保留未分类。运行 `.\.conda\investment-system\python.exe -m src.portfolio web` 后可在 `http://127.0.0.1:8765/` 查看；个人数据库及导入文件位于 `data/db/`，默认不进入 Git。

台账还可把指定日期的组合状态保存为不可变、可修订的审计快照：

```powershell
.\.conda\investment-system\python.exe -m src.portfolio snapshot --as-of 2026-07-14
.\.conda\investment-system\python.exe -m src.portfolio snapshot-list
.\.conda\investment-system\python.exe -m src.portfolio snapshot-show --as-of 2026-07-14
```

历史快照只消费不晚于 `as_of` 的交易和收盘价；需要按当时可见信息重放时，可额外传入带时区的 `--knowledge-cutoff`。未定价和陈旧价格会显式保留，重复输入保持同一修订，补录历史交易或行情后产生新修订且旧版本仍可查询。完整命令、字段口径和限制见 `docs/playbooks/PORTFOLIO_TRACKER.md`。

在已审核的 review sidecar 事件和 P2B 快照之上，可生成确定性的交易周期事实 artifact：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  --db data/db/investment_review.sqlite3 `
  episode-build --cutoff-at "2026-07-15T15:00:00+08:00" `
  --portfolio-db data/db/portfolio.sqlite3 `
  --output data/processed/normalized/trade_episodes.local.json
```

该命令只读源库，不推断决策原因；无法证明的快照/Decision 链接会保留为 missing、unlinked、ambiguous 或 invalid。契约、查询和验证命令见 `docs/playbooks/INVESTMENT_REVIEW_P2C.md`。

P2E-3 可进一步把 P2C 的逐事件 `pre/post` 锚点绑定到可证明的组合快照和
P2E-2 指标：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  episode-portfolio-context-build `
  --episode-artifact data/processed/normalized/trade_episodes.local.json `
  --portfolio-db data/db/portfolio.sqlite3 `
  --cutoff-at "2026-07-15T15:00:00+08:00" `
  --knowledge-cutoff "2026-07-15T15:00:00+08:00" `
  --output data/processed/normalized/trade_episode_portfolio_context.local.json
```

该入口保持源库只读；无法证明盘中顺序或双时间可见性的状态不会被猜测补齐。
进入下游阶段前还应使用同一 P2C artifact 与 P2B 数据库执行带源重放验证；单独重算
artifact 的 SHA-256 只能证明内部内容一致，不能证明外部来源真实：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  episode-portfolio-context-validate `
  data/processed/normalized/trade_episode_portfolio_context.local.json `
  --source-replay `
  --episode-artifact data/processed/normalized/trade_episodes.local.json `
  --portfolio-db data/db/portfolio.sqlite3
```

完整边界见 `docs/playbooks/INVESTMENT_REVIEW_P2E_3.md`。

P2F-1 会在事实复盘前冻结单个 episode 的全部可用输入。输入包内嵌已验证的
P2C episode、P2E-3 episode slice 和显式链接来源；后续 facts/interpretation
阶段不再重新查询漂移数据：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  review-input-build `
  --episode-artifact data/processed/normalized/trade_episodes.local.json `
  --portfolio-context data/processed/normalized/trade_episode_portfolio_context.local.json `
  --portfolio-db data/db/portfolio.sqlite3 `
  --episode-id <episode_id> `
  --review-cutoff "2026-07-15T15:00:00+08:00" `
  --output data/processed/normalized/review_input_bundle.local.json
```

构建过程会再次执行 P2E-3 source replay，并核对组合数据库构建前后的
SHA-256。Decision、市场或结果来源只能通过显式 JSON source 文档传入；超过
双时间截止点的来源会被排除并留下 warning，缺失值不会被补成 `0`。

P2F-2 只从上述冻结 bundle 构建六节可追溯事实复盘；它不再查询源库，也不调用模型：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  episode-review-build `
  --input-bundle data/processed/normalized/review_input_bundle.local.json `
  --facts-only `
  --output data/processed/normalized/episode_review.local.json `
  --markdown-output reports/investment_review/p2f/episode_review.local.md
```

事实 ID、双时间角色、availability 和 P2F-1 source refs 都进入 canonical hash。
进入解释或发布阶段前，应使用原 bundle 运行 `episode-review-validate --source-replay`；
盈利/亏损不会自动生成“决策正确/错误”，缺失计划、市场或结果会保留为 gap。

P2F-3 可在不改变事实层的前提下，显式消费一份已记录的模型 JSON 响应：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  episode-review-interpret `
  --artifact data/processed/normalized/episode_review.local.json `
  --model-id <recorded-model-id> `
  --generated-at "2026-07-15T07:10:00Z" `
  --model-response data/processed/normalized/interpretation_response.local.json `
  --output data/processed/normalized/episode_review.model.local.json `
  --attempt-output data/processed/normalized/interpretation_attempt.local.json
```

该入口不会自行联网。所有 finding 必须引用 fact ID 并保留 assumptions、uncertainty、
counterevidence 和 temporal perspective；心理诊断、交易建议、机械评分、结果倒推和
事后最佳价会被拒绝。provider 不可用或响应非法时，输出仍是原 facts-only artifact，
失败只记录在独立 attempt receipt 中。

P2F-4 通过闭合的人工作业请求追加接受、拒绝或事实链接纠正。每次动作都创建新
revision，保留前一 `content_id`、actor、reason、reviewed time 和 target/result ID；
旧 artifact 与源交易/组合数据库保持不变：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  episode-review-correct `
  --artifact data/processed/normalized/episode_review.model.local.json `
  --request data/processed/normalized/human_review_request.local.json `
  --output data/processed/normalized/episode_review.rev2.local.json

.\.conda\investment-system\python.exe -m src.investment_review `
  episode-review-render `
  --artifact data/processed/normalized/episode_review.rev2.local.json `
  --output reports/investment_review/p2f/episode_review.rev2.local.md

.\.conda\investment-system\python.exe -m src.investment_review `
  episode-review-diff `
  data/processed/normalized/episode_review.model.local.json `
  data/processed/normalized/episode_review.rev2.local.json

.\.conda\investment-system\python.exe -m src.investment_review `
  episode-review-revision-list `
  data/processed/normalized/episode_review.model.local.json `
  data/processed/normalized/episode_review.rev2.local.json
```

Markdown 会显示事实/解释分区、来源、availability、warnings、修订与审核 provenance，
并转义注入字符。完整请求 schema、修订链门禁和限制见
`docs/playbooks/INVESTMENT_REVIEW_P2F_DRAFT.md`。

P2G-2 可在一份已验证且 `ready/verified` 的 P2G-1 facts-only cohort 上，
构建四类确定性跨 episode 观察：相邻周期节奏、同标的再进入间隔、可比规模变化和
持有时长变化。它只输出完整 evaluation ledger 与可追溯事实引用，不读取数据库、
不调用模型，也不生成心理诊断、评分或交易建议：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  behavior-observation-build `
  --cohort data/processed/normalized/behavior_cohort.local.json `
  --output data/processed/normalized/behavior_observations.local.json
```

构建、AND 查询、五态结果、规模可比性与 source replay 规则见
`docs/playbooks/INVESTMENT_REVIEW_P2G_2.md`。

P2G-3 可把一份已验证的 P2G-2 observation set 与一份显式记录的本地 JSON
响应编译为只含 `proposed` 状态的候选行为假设，并单独保存 attempt receipt：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  behavior-hypothesis-interpret `
  --artifact data/processed/normalized/behavior_observations.local.json `
  --model-id recorded-model-v1 `
  --generated-at "2026-07-18T12:00:00Z" `
  --model-response data/processed/normalized/behavior_hypothesis_response.local.json `
  --output data/processed/normalized/behavior_hypotheses.model.local.json `
  --attempt-output data/processed/normalized/behavior_hypothesis_attempt.local.json
```

该入口不调用 live model，不读取数据库，不进入 P2G-4，也不生成心理诊断、评分或
交易建议。响应 schema、fallback、护栏与 source replay 见
`docs/playbooks/INVESTMENT_REVIEW_P2G_3.md`。

P2G-4 通过显式人工作业请求，对 `proposed` 候选执行原子化 `accept`、`reject`
或 `correct`。每次操作都创建不可变 revision；correct 会 supersede 旧项并生成新的
`proposed` 候选，必须再次独立审核。`accepted` 仅表示人工确认保留为工作假设，
不是事实证明、心理诊断或交易建议：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  behavior-hypothesis-review `
  --artifact data/processed/normalized/behavior_hypotheses.model.local.json `
  --request data/processed/normalized/behavior_hypothesis_review.local.json `
  --observation-artifact data/processed/normalized/behavior_observations.local.json `
  --output data/processed/normalized/behavior_hypotheses.rev1.local.json

.\.conda\investment-system\python.exe -m src.investment_review `
  behavior-hypothesis-validate `
  data/processed/normalized/behavior_hypotheses.rev1.local.json `
  --source-replay `
  --observation-artifact data/processed/normalized/behavior_observations.local.json
```

revision 的 create-only、状态机、render/diff/revision-list 和 source replay 规则见
`docs/playbooks/INVESTMENT_REVIEW_P2G_4.md`。

完成审核的 revision chains 可汇总为确定性 Behavior Hypothesis Ledger。台账只做
exact canonical fingerprint 去重和 AND 过滤；active view 只暴露 accepted
occurrences，proposed/rejected/superseded 始终保留在 audit view。它不是新的阶段编号，
也不做语义聚类、心理画像、排名、评分或交易建议：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  behavior-hypothesis-ledger-build `
  --revision data/processed/normalized/behavior_hypotheses.rev1.local.json `
  --observation-artifact data/processed/normalized/behavior_observations.local.json `
  --output data/processed/normalized/behavior_hypothesis_ledger.local.json

.\.conda\investment-system\python.exe -m src.investment_review `
  behavior-hypothesis-ledger-validate `
  data/processed/normalized/behavior_hypothesis_ledger.local.json `
  --source-replay `
  --revision data/processed/normalized/behavior_hypotheses.rev1.local.json `
  --observation-artifact data/processed/normalized/behavior_observations.local.json
```

完整构建、查询、渲染和失败关闭规则见
`docs/playbooks/INVESTMENT_REVIEW_BEHAVIOR_HYPOTHESIS_LEDGER.md`。

P2H Stage 1 在不改写 P2G artifact 的前提下，接收显式提交的行为假设候选，强制绑定
exact source、替代解释以及反证或 source gap，并把候选与不可变人工复核事件写入独立
investment-review sidecar。`accepted_for_observation` 只表示值得继续观察，不表示假设已被
证明，也不构成心理诊断或交易建议：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  behavior-candidate-build `
  --input tests/fixtures/investment_review_p2h_stage1/candidate_draft.json `
  --output data/processed/normalized/behavior_candidate.local.json

.\.conda\investment-system\python.exe -m src.investment_review `
  behavior-candidate-validate `
  data/processed/normalized/behavior_candidate.local.json `
  --source-replay `
  --source-artifact tests/fixtures/investment_review_p2h_stage1/synthetic_observation_source.json
```

create-only 导入、人工事件、按 `as_of` / `knowledge_cutoff` 的确定性状态投影、查询、
错误码与 Stage 2 暂停点见 `docs/playbooks/INVESTMENT_REVIEW_P2H_STAGE1.md`。

P2H Stage 2 Slice A 只在 Stage 1 candidate 已由人工明确
`accepted_for_observation` 后，接收一份显式、经人工确认的 observation protocol draft。
protocol 会绑定 exact candidate/hash、source artifacts、完整 Stage 1 review event set 与指定
双时间 cutoff 下的 accepted projection；它不会由 candidate 状态自动生成或激活：

```powershell
.\.conda\investment-system\python.exe -m src.investment_review `
  observation-protocol-build `
  --input tests/fixtures/investment_review_p2h_stage2/protocol_draft.json `
  --candidate-artifact data/processed/normalized/behavior_candidate.local.json `
  --review-event data/processed/normalized/behavior_candidate_submitted.local.json `
  --review-event data/processed/normalized/behavior_candidate_accepted.local.json `
  --candidate-source-artifact tests/fixtures/investment_review_p2h_stage1/synthetic_observation_source.json `
  --output data/processed/normalized/observation_protocol.local.json

.\.conda\investment-system\python.exe -m src.investment_review `
  observation-protocol-validate `
  data/processed/normalized/observation_protocol.local.json `
  --source-replay `
  --candidate-artifact data/processed/normalized/behavior_candidate.local.json `
  --review-event data/processed/normalized/behavior_candidate_submitted.local.json `
  --review-event data/processed/normalized/behavior_candidate_accepted.local.json `
  --candidate-source-artifact tests/fixtures/investment_review_p2h_stage1/synthetic_observation_source.json
```

create-only sidecar、人工 lifecycle events、双时间状态、expiry、重放和错误码见
`docs/playbooks/INVESTMENT_REVIEW_P2H_STAGE2_OBSERVATION_PROTOCOL.md`。`completed` 或
`expired` 只描述协议治理，不证明 hypothesis；Slice B intervention/experiment、attempt/outcome、
profile/PersonalPlaybook、UI/Web/API、真实数据库和交易建议均未启用。
