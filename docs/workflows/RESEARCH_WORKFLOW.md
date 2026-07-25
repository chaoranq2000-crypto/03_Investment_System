# Research Workflow — 全局工作流内核

> 本文件是 A-share Research OS 的唯一全局 workflow kernel。
> 它定义永久 `workflow_type`、global `stage_id`、global `gate_id`、
> backflow decision、交接资产和 P2 readiness 条件。

本文件不是项目建设计划，不是某次 readout，也不是任何单一 skill 的执行手册。

## 0. 总原则

本系统的目标是把 A 股投研动作拆成可维护、可复用、可审查的闭环。

核心原则：

1. 证据库是核心，报告只是某一时点的可再生产物。
2. 细分方向和上市公司是多对多关系，通过 `segment_company_exposure` 连接。
3. 任何关键结论必须能追溯到 `evidence_id`、`claim_id`、`metric_id`，或显式标记 `TODO` / `MISSING` / `UNKNOWN`。
4. 事实、估计、推断、管理层表述、券商观点和个人观点必须分离。
5. 不输出买入、卖出、持有等直接投资建议；评分卡和观察清单不是交易指令。
6. 缺数据时记录缺口和下一步验证方式，不编造收入占比、订单、客户、市场规模或估值数字。
7. 新证据影响旧结论时，必须通过 refresh / quality 机制记录变化，不能静默覆盖。

## 1. Canonical interface ownership

只在本文件定义以下全局接口：

```text
workflow_type
global stage_id
global gate_id
backflow_decision
P2 readiness criteria
```

其他文件可以引用这些接口，但不得重新定义或扩展。

Detailed workflow_state schema is owned by
`.agents/skills/research-orchestrator/references/workflow_state_schema.md`.

Skill-local 步骤和检查必须使用局部前缀：

```text
DL-*   data layer local checks
SDD-*  stock-deep-dive local steps
QR-*   quality-review local subchecks
RP-*   report-production profile steps
```

## 2. 系统层级

```text
用户请求
  ↓
research-orchestrator：总工作流编排、状态管理、skill 路由、门禁调度、readout
  ↓
下层 skills：
evidence-ingest / segment-research / company-universe /
segment-company-mapping / stock-deep-dive / quality-review /
memo-writer / refresh-research
  ↓
研究状态资产：evidence / claims / metrics / segment taxonomy / segment-company exposure / scorecards / watchlist
  ↓
报告产物：segment report / stock deep dive / evidence map / refresh log / memo / workflow readout
```

`research-orchestrator` 是执行入口，但不是研究内容来源。它回答：

```text
现在是什么 workflow_type？
现在处于哪一步？
下一步该调用哪个 skill？
下层 skill 需要哪些输入？
产物是否满足门禁？
质量问题应该回到哪一步修复？
当前是否能进入 P2？
```

## 3. 永久 workflow_type

当前永久 workflow 类型只有五类：

| workflow_type | 触发场景 | 当前用途 |
|---|---|---|
| `segment_to_stock_closed_loop` | 从一个细分、产业链环节、主题或产品开始 | P1/P1.6 主闭环 |
| `stock_first_closed_loop` | 从一个股票、公司或公司研究问题开始 | P2 前必须补齐 |
| `segment_stock_interlock` | 专门处理细分和个股之间的双向回写、冲突和更新 | 两个主闭环的连接层 |
| `refresh_existing_research` | 更新已有细分、个股、watchlist 或旧结论 | P3 前保留接口，P2 前可做轻量刷新 |
| `comparison_readiness_gate` | 准备进入 P2 的横向比较 | 进入 P2 前必须执行 |

| workflow_type | 主线 |
|---|---|
| `segment_to_stock_closed_loop` | 细分定义 → 证据 → claims/metrics → 公司池 → exposure → 个股样本 → 回写 → 质量审查 |
| `stock_first_closed_loop` | 公司身份 → 证据 → 业务/财务 → linked_segments → exposure → 个股报告 → 回写细分 |
| `segment_stock_interlock` | exposure / company_universe / segment_taxonomy / scorecard 的同步 |
| `refresh_existing_research` | 新证据 → stale/superseded/contradicted claims → scorecard/watchlist 变化 → refresh log |
| `comparison_readiness_gate` | 检查多个细分/个股是否具备可比性 |

`workflow_diagnostic` 不是永久 `workflow_type`。如需要只读诊断，使用：

```yaml
run_mode: diagnostic
```

P2 之前，重点不是批量比较，而是把 `segment_to_stock_closed_loop`、`stock_first_closed_loop` 和 `segment_stock_interlock` 制度化并调试通过。

## 4. 共享对象与交接资产

| 对象 | 作用 | 主要存放位置 |
|---|---|---|
| Segment | 细分定义、边界、别名、上级主题、相邻细分 | `config/segment_taxonomy.yaml`、`reports/segments/` |
| Company | 上市公司身份、证券代码、名称、基础信息 | `config/`、`data/processed/normalized/`、`reports/stocks/` |
| Evidence | 原始证据和来源登记 | `data/raw/`、`data/processed/`、`data/manifests/evidence_manifest.csv` |
| Claim | 从证据摘出的事实、估计、推断、管理层表述等 | `data/manifests/claims_draft.csv`、`data/manifests/claims_registry.csv` |
| Metric | 结构化指标观察值 | `data/manifests/metrics_draft.csv`、`data/manifests/metrics_registry.csv` |
| Exposure | 细分与公司的多对多暴露关系 | `data/processed/normalized/segment_company_exposure.csv` |
| Report | 某一时点的可再生产物 | `reports/segments/`、`reports/stocks/` |
| Scorecard | 结构化评分，服务于比较前的统一口径 | `reports/**/scorecard.yaml` |
| WatchItem | 观察对象、原因、证据、触发条件、复核日期 | `config/watchlist.yaml`、`reports/**/watchlist*` |
| WorkflowRun | 某次工作流执行状态和交接记录 | `reports/workflow_runs/` |

## 5. Workflow run 标准目录

完整闭环建议创建 workflow run 目录：

```text
reports/workflow_runs/<workflow_id>/
├── workflow_state.yaml
├── run_log.md
├── artifact_manifest.csv
├── open_todos.csv
├── quality_gate_report.md
├── workflow_readout.md
└── handoffs/
    ├── 01_intake_to_research-orchestrator.md
    ├── 02_to_evidence-ingest.md
    └── ...
```

`workflow_id` 命名：

```text
wf_<YYYYMMDD>_<workflow_type>_<slug>
```

示例：

```text
wf_20260701_segment_to_stock_ai_server_liquid_cooling
wf_20260701_stock_first_cn_002837_invic
```

## 6. Workflow state ownership

`workflow_state.yaml` 记录一次 workflow run 的当前状态。

本 kernel 只要求完整运行在 `reports/workflow_runs/<workflow_id>/`
维护一个当前 `workflow_state.yaml`，并消费本文件定义的
canonical `workflow_type`、global `stage_id`、global `gate_id`
和 `backflow_decision`。

Detailed workflow_state schema is owned by
`.agents/skills/research-orchestrator/references/workflow_state_schema.md`.

### 6.1 V1 四类完成事实

V1 必须同时报告四个互不替代的布尔事实。四者的语义只在本 kernel 定义；
运行时、局部 profile、Bundle、Night mission 和 readout 只能消费并附证据，
不得改变定义或用一个事实推导另一个事实。

| fact | canonical meaning | evidence boundary |
|---|---|---|
| `system_v1_complete` | 工程接口、活动控制面、隔离真实重放、根因归并和工程验证均已闭环，且活动 V1 路径没有 open `engineering_defect`。 | 由版本化实现、测试、scope audit、历史不可变检查和可复跑工件证明。 |
| `sample_quality_ready` | 当前研究样本已通过全部必要自动质量条件，且唯一最终报告通过真实 reviewer 的有效审核；这些是必要条件，不表示任何单项条件自动充分。 | 由当前样本的 research pack、自动质量结论、最终报告当前字节的机器 SHA-256 和真实 reviewer 决定共同证明；工程测试或中间产物状态不得自动提升。 |
| `p2_ready` | canonical comparison-readiness 决定已经独立通过。 | 只能由 `comparison_readiness_gate` 按本文件第 13 节判定；工程完成或样例质量不能代替。 |
| `release_ready` | 候选版本已按获批发布边界发布，且最终精确 HEAD 的必需 CI/验证成功。 | 由 remote SHA、exact-head CI 和发布凭证证明；本地测试或预发布提交不得代替。 |

`system_v1_complete=true` 至少要求：

1. 本文件的 canonical interface 和 G0–G10 保持唯一 owner；
2. 活动 run 只有一套当前状态、TODO、质量结论和 readout；
3. 真实归档输入可以在隔离 run 中可追溯、可重复地完成自动化闭环；
4. 影响活动 V1 路径的 open `engineering_defect` 为零；
5. 合同要求的 targeted/full tests、文档漂移、scope 和历史不可变检查全部通过。

以下事实不得抬高或否定 `system_v1_complete`：发行人未披露数据、最终报告审核
`not_requested` / `pending`、`sample_quality_ready=false`、`p2_ready=false`，
或尚未授权的发布。
这些外部事实必须保留为显式缺口，但不得被工程自动化补造。反过来，
`system_v1_complete=true` 也不得自动把后三项改为 true。

历史 Night mission outcome `review_intake_ready` 与长期 Goal
`r5_bundle17r_bf2_four_case_activation` 只作为原运行的只读追溯事实保留；原长期
Goal 记录在历史快照中保持 open。它们不能写入 canonical `workflow_state.status`，
不能参与当前 dispatch、当前 Goal 的关闭条件或 V1 完成判定，也不得形成最终报告审核
之外的活动人工授权边界。

### 6.2 活动 run 的单一当前控制面

每个活动 `reports/workflow_runs/<workflow_id>/` 只维护以下一套当前资产：

```text
workflow_state.yaml
open_todos.csv
quality_gate_report.md
workflow_readout.md
```

`run_log.md` 和 `artifact_manifest.csv` 记录执行与追溯，但不得形成第二套当前状态或质量结论。
Bundle、Night、旧 close readout、历史 quality report 和 generation snapshot 可以保留为只读证据，
不得覆盖或支配上述当前资产。新一轮输出必须写入新的 run-scoped 路径，不能覆盖历史 run。

### 6.3 当前目标范围内的 issue 与 outcome

活动 issue 必须把风险描述和工作流决定分开。每条 issue 至少记录：

| field | canonical meaning |
|---|---|
| `impact_scope` | `workflow`、`report`、`section`、`claim`、`method` 或 `none`。 |
| `active_disposition` | `active_defect`、`unknown`、`method_unavailable`、`report_limitation`、`historical_backlog`、`policy_retired` 或 `not_required_for_active_v1`。 |
| `affected_capabilities` | 被该 issue 关闭或降级的具体结论、章节、计算或方法；无影响时为空列表。 |
| `blocks_current_goal` | 是否阻断当前 run 明确要求的目标；必须由 disposition、impact scope 和实际依赖推导。 |

`severity` 只描述风险和修复优先级，不能单独决定 `blocks_current_goal` 或
canonical `workflow_state.status`。历史 `blocking_decision`、Bundle gate 或 R5
local check 也不能覆盖当前目标依赖判断。

确定性状态推导如下：

| active_disposition | 当前目标依赖 | `blocks_current_goal` | canonical outcome |
|---|---|---:|---|
| `active_defect` | 当前产物使用 unsupported number、存在错误计算、真实 double-count、引用断裂、hidden TODO 或 no-advice 违规 | `true` | `needs_fix` |
| `active_defect` | identity、path、parse、source identity 或必要输入损坏，导致任何诚实目标产物都无法生成 | `true` | `blocked` |
| `unknown` | 当前 material claim、section 或 calculation 实际使用该未知字段 | `true` | `needs_fix`，先降级、移除或取得证据 |
| `unknown` | 未被当前产物使用且显式可见 | `false` | `accepted_with_todos` 可用 |
| `method_unavailable` | 当前目标明确要求该方法，必要输入不可获得，且没有获准 fallback | `true` | `blocked` |
| `method_unavailable` | 当前目标不要求该方法，或已采用可见 fallback / unknown / omit | `false` | `accepted_with_todos` 可用 |
| `report_limitation` | 限制显式可见，且没有无依据使用 | `false` | `accepted_with_todos` 可用 |
| `historical_backlog`、`policy_retired`、`not_required_for_active_v1` | `impact_scope=none` | `false` | 不影响 canonical outcome |

四个 canonical workflow outcome 的边界是：

| outcome | meaning |
|---|---|
| `accepted` | 自动质量通过，且没有活动限制或 TODO。 |
| `accepted_with_todos` | 自动研究和质量检查完成；未使用的 unknown、不可用的非必需方法或可见限制仍在。 |
| `needs_fix` | 当前产物存在可修复的活动缺陷，或实际使用了没有证据的未知字段。 |
| `blocked` | identity、path、parse、source identity 或当前目标不可替代的必要输入失败，导致任何诚实目标产物都无法生成。 |

缺失信息必须按以下降级阶梯处理：

```text
发行人直接披露
→ 经审计的聚合口径
→ 明示假设、边界和不确定性的有界估计 / 情景
→ unknown 或省略依赖该字段的结论
```

低一级不得伪装成高一级。走到 `unknown` 或 omit 时，只关闭真正依赖该字段的
claim、section、calculation 或 method；不得把一个 capability 的缺口提升为全局 blocker。

### 6.4 机器验证与唯一最终报告人工审核

活动 V1 的 evidence、claim、metric、字段、候选、计算、research pack、
generation lock 和中间 receipt 全部由机器验证，不是人工审批对象。文档或字段名中
保留的 `reviewed` 只表示已通过适用的 provenance、schema、claim-type、metric、
citation、hash 和 no-advice 机器检查；它不表示 reviewer 已逐项批准。

每个新建或更新的活动 run 使用：

```yaml
final_report_review_semantics_version: final_report_review_v1
automated_report_quality_passed: false
final_report_review_status: not_requested
final_report_review:
  report_path: null
  report_sha256: null
  reviewer: null
  reviewed_at: null
  decision: not_requested
  notes: null
  change_scope: null
```

字段级约束由
`.agents/skills/research-orchestrator/references/workflow_state_schema.md`
和 `schemas/r5_final_report_review.schema.json` 实现。canonical 行为是：

`automated_report_quality_passed=true` 只在活动状态列出 G0–G10 全部
canonical gates，且每项均为 `pass` 或 `not_applicable` 时成立。
局部 Bundle/R5 pass、最终人工决定或历史 accepted 记录都不能代替该全集。

| `final_report_review_status` | record requirement | automatic workflow effect | sample-quality effect |
|---|---|---|---|
| `not_requested` | 路径、hash、reviewer、时间、备注和 `change_scope` 均为空；`decision` 必须同值。 | 不改变自动 outcome，也不阻止 `system_v1_complete`。 | 必须为 false。 |
| `pending` | 绑定 `reports/stocks/<id>/` 或 `reports/segments/<id>/` 下的最终报告路径和机器计算 SHA-256；该路径必须与 `artifacts[]` 中唯一 required/current `artifact_type: final_report` 一致；reviewer、时间、备注、`change_scope` 为空；`decision` 必须同值。 | 不改变自动 outcome，也不阻止 `system_v1_complete`。 | 必须为 false。 |
| `approved` | 绑定当前最终报告路径与当前字节 SHA-256；包含真实非机器 reviewer、ISO 时间、非空备注；`decision` 必须同值，`change_scope` 为空。 | 不得覆盖自动质量 failure。 | 只有全部必要自动质量条件也通过时才允许为 true；仍须满足其他样例质量条件。 |
| `changes_requested` | 与 `approved` 使用相同身份、时间、路径、hash 和备注约束；`change_scope` 只能为 `automated_quality_defect` 或 `report_revision`。 | 前者把 workflow 路由为 `needs_fix`；后者只进入最终报告修订，不改变已推导的自动 outcome。 | 必须为 false。 |

`final_report_review.decision` 必须等于顶层 status。最终报告字节变化后，
机器重算 hash 必须使旧 `approved` / `changes_requested` 失效，不能把旧 reviewer
决定迁移到新报告。若替换已提交的人审记录，新的有效人审事件必须使用严格更晚的
`reviewed_at`；只更新 hash 不能迁移旧决定。机器不得生成 reviewer 身份、审核时间、批准或修改决定。
人工审核也不能批准伪造数据、绕过自动质量失败或把 unsupported-used 变成可接受事实。

只有最终报告的 SHA-256 绑定人工审核。evidence、claim、metric、pack、计算、
generation lock、candidate 和 receipt 的 hash 继续用于机器完整性与重放，
不得转化为并行人审、authority 或逐项 candidate decision。历史 Bundle/Night 的
多份 exact-hash 人审和 reviewer-authority 记录保持只读兼容证据，退出活动 routing，
也不能满足当前最终报告审核。

## 7. Skill 角色分工

| skill | 主要职责 |
|---|---|
| `research-orchestrator` | 识别工作流、维护状态、路由 skill、生成 handoff、调度门禁、输出 readout |
| `evidence-ingest` | 证据导入、去重、解析、登记，维护 evidence manifest 和候选 claims/metrics |
| `segment-research` | 细分定义、边界、产业链、需求/供给/利润池、指标体系、细分报告、scorecard |
| `company-universe` | 从细分建立 A 股公司池，区分 revenue/product/technology/customer/project/narrative 等暴露 |
| `segment-company-mapping` | 维护 `segment_company_exposure`，管理暴露类型、评分、置信度、证据和有效期 |
| `stock-deep-dive` | 个股业务、财务、linked_segments、风险、反证、估值场景和 evidence map |
| `quality-review` | 检查证据追溯、claim 类型、指标口径、过期证据、风险反证和禁止事项 |
| `memo-writer` | 将已通过机器质量审查的研究转为 memo、watchlist note 或 thesis note |
| `refresh-research` | 新证据驱动旧结论更新，输出 refresh log、stale claims、reports_to_regenerate |
| `compare-segments` | P2 以后多细分横向比较 |
| `compare-stocks` | P2 以后同细分个股横向比较 |

| skill | 不负责 |
|---|---|
| `research-orchestrator` | 不直接写研究结论、不虚构证据、不替代下层 skill |
| `evidence-ingest` | 不写完整细分或个股报告 |
| `segment-research` | 不做单一个股完整深度 |
| `company-universe` | 不做完整个股研究 |
| `segment-company-mapping` | 不写行业或个股长文报告 |
| `stock-deep-dive` | 不替代细分研究，不做多股排序 |
| `quality-review` | 不作为新增结论来源 |
| `memo-writer` | 不创造未经证据支持的新研究结论 |
| `refresh-research` | 不静默重写旧报告 |
| `compare-segments` | 不在 readiness gate 前使用 |
| `compare-stocks` | 不在基础闭环未通过时使用 |

## 8. 主闭环一：segment_to_stock_closed_loop

### 8.1 适用场景

用户从一个细分方向开始，希望形成可追溯的细分研究、公司池、个股样本和观察项。

### 8.2 全局阶段表

| stage_id | 目标 | 主要 gate |
|---|---|---|
| S0 Intake | 明确对象、范围、深度、是否 P2 前置 | G0 |
| S1 Segment Definition | 定义 segment_id、scope_in/out、相邻细分 | G0 |
| S2 Evidence Plan & Ingest | 制定证据计划并登记证据 | G1 |
| S3 Claims & Metrics Draft | 拆 facts/comments/estimates/inferences 与指标 | G2, G3 |
| S4 Segment Report Draft | 生成细分研究初稿 | G4 |
| S5 Company Universe | 找 A 股公司池并区分暴露层级 | G5 |
| S6 Exposure Mapping | 建立多对多暴露映射 | G6 |
| S7 Stock Sample Selection | 选择 1–2 家样本进入个股深度 | G0, G6 |
| S8 Stock Deep Dive | 生成个股深度样本 | G7 |
| S9 Backflow | 个股发现回写细分、公司池和 exposure | G8 |
| S10 Scorecard & Watchlist Draft | 形成评分和观察项 | G9 |
| S11 Quality Review | 自动总审查 | G1-G9 |
| S12 Fix Loop | 根据质量问题回到对应阶段 | target gate |
| S13 Close Readout | 固化成果、TODO 和状态 | G10 |

| stage_id | 主 skill | 关键输出 |
|---|---|---|
| S0 Intake | `research-orchestrator` | `workflow_state.yaml`、`run_log.md` |
| S1 Segment Definition | `segment-research` | segment definition / boundary note |
| S2 Evidence Plan & Ingest | `evidence-ingest` | raw/processed evidence、`evidence_manifest.csv` |
| S3 Claims & Metrics Draft | `evidence-ingest` + `quality-review` | `claims_draft.csv`、`metrics_draft.csv` |
| S4 Segment Report Draft | `segment-research` | segment report、evidence map |
| S5 Company Universe | `company-universe` | `company_universe.csv` |
| S6 Exposure Mapping | `segment-company-mapping` | `segment_company_exposure.csv` |
| S7 Stock Sample Selection | `research-orchestrator` | sample selection note |
| S8 Stock Deep Dive | `stock-deep-dive` | stock report、segment_exposure、evidence map |
| S9 Backflow | `segment-company-mapping` + `segment-research` | updated exposure / taxonomy candidate / segment TODO |
| S10 Scorecard & Watchlist Draft | `segment-research` + `stock-deep-dive` + `memo-writer` | scorecard、watchlist draft |
| S11 Quality Review | `quality-review` | quality gate report、quality issues |
| S12 Fix Loop | `research-orchestrator` | handoff to target skill |
| S13 Close Readout | `research-orchestrator` | workflow readout |

### 8.3 进入个股深度的条件

进入 S8 前，必须满足：

1. `company_universe.csv` 已存在。
2. 候选公司至少有一条 evidence 或明确 TODO。
3. 候选公司的 `exposure_type`、`exposure_score`、`confidence` 已初步标注。
4. 样本选择目的清楚：核心暴露、争议暴露、边界案例或反证案例。
5. 没有把 `narrative` 暴露直接升级成 `revenue` 暴露。

## 9. 主闭环二：stock_first_closed_loop

### 9.1 适用场景

用户从股票代码、公司名称或公司研究问题开始，希望形成独立个股深度，并将其映射到一个或多个细分。

### 9.2 全局阶段表

| stage_id | 目标 | 主要 gate |
|---|---|---|
| T0 Intake | 明确股票、公司、范围、是否已有 linked_segments | G0 |
| T1 Company Evidence | 收集年报、公告、财务数据、IR、新闻等证据 | G1 |
| T2 Business & Financial Skeleton | 搭业务和财务骨架 | G2, G3 |
| T3 Linked Segment Discovery | 识别公司可能关联的细分 | G6 |
| T4 Segment Context Check | 检查 linked segments 是否已有定义 | G0 |
| T5 Mini Segment Card | 对缺失但重要的细分建立最小定义卡 | G4 |
| T6 Exposure Mapping | 更新该公司在多个细分中的 exposure | G6 |
| T7 Stock Report Draft | 写个股深度报告 | G7 |
| T8 Backflow | 回写 segment taxonomy / company universe / exposure | G8 |
| T9 Quality Review | 自动审查个股报告和映射 | G1-G9 |
| T10 Close Readout | 输出个股闭环 readout | G10 |

| stage_id | 主 skill | 关键输出 |
|---|---|---|
| T0 Intake | `research-orchestrator` | `workflow_state.yaml` |
| T1 Company Evidence | `evidence-ingest` | evidence manifest 更新 |
| T2 Business & Financial Skeleton | `stock-deep-dive` | business table、financial skeleton |
| T3 Linked Segment Discovery | `stock-deep-dive` + `segment-company-mapping` | linked_segments draft |
| T4 Segment Context Check | `research-orchestrator` | existing links / segment candidates |
| T5 Mini Segment Card | `segment-research` | segment definition candidate |
| T6 Exposure Mapping | `segment-company-mapping` | `segment_exposure.yaml`、`segment_company_exposure.csv` |
| T7 Stock Report Draft | `stock-deep-dive` | stock deep dive、evidence map |
| T8 Backflow | `segment-company-mapping` + `segment-research` | updated segment assets |
| T9 Quality Review | `quality-review` | quality report |
| T10 Close Readout | `research-orchestrator` | workflow readout |

### 9.3 个股研究的独立性和依赖性

个股研究可以独立启动，因为它能从股票代码直接开始，先完成公司业务、财务、治理、风险和证据地图。

但它不能脱离细分体系，因为：

1. 业务线和产品最终需要判断是否对应已有或候选细分。
2. `segment_exposure.yaml` 和 `segment_company_exposure.csv` 是个股结论进入系统状态层的入口。
3. 如果个股发现新细分或推翻已有暴露关系，必须回写细分资产或形成 TODO。

## 10. 连接闭环：segment_stock_interlock

### 10.1 二者关系

| 关系 | 说明 |
|---|---|
| 细分研究可以独立存在 | 可以先研究市场结构、产业链和指标，即使尚未完成个股深度。 |
| 个股研究可以独立启动 | 可以从股票代码开始，再反向识别 linked_segments。 |
| 二者通过 exposure 连接 | `segment_company_exposure` 是正式连接层。 |
| 二者共享 evidence / claims / metrics | 同一证据可支持细分 claim，也可支持个股 claim。 |
| 二者通过 backflow 互相更新 | 个股发现要回写细分，公司池变化要触发个股复核。 |

### 10.2 backflow_decision

个股研究完成后，必须给出 backflow decision：

| decision | 含义 | 典型动作 |
|---|---|---|
| `update_exposure` | 个股证据改变了暴露类型、分数或置信度 | 更新 `segment_company_exposure.csv`。 |
| `update_company_universe` | 公司池中该公司的备注、暴露层级或证据需要更新 | 更新 `company_universe.csv`。 |
| `update_segment_taxonomy` | 发现新细分、相邻细分或边界问题 | 更新 `segment_taxonomy.yaml` 或新增 candidate。 |
| `update_scorecard` | 个股发现影响细分评分 | 更新 scorecard 或 scorecard TODO。 |
| `no_backflow_needed` | 个股研究没有改变细分状态 | 写明原因，不默默跳过。 |
| `blocked` | identity、path、parse 或 source identity 损坏，导致任何诚实的回写决定都无法生成 | 修复基础输入后重跑。证据不足但仍能诚实输出限制时，使用可见 TODO，而不是 `blocked`。 |

### 10.3 冲突处理

当细分报告和个股报告冲突时：

1. 先比较证据日期、来源等级和 entity 粒度。
2. 个股最新公告优先影响该公司，不自动外推整个细分。
3. 行业数据用于细分层，不能自动推导单家公司收入占比。
4. 管理层表述只能作为 `management_comment`，不能直接覆盖 fact。
5. 冲突必须进入 quality issue，并标记 `needs_review`。

## 11. 全局质量门禁

本表是全局 gate id 的唯一事实源。

| gate_id | 名称 | 未通过处理 |
|---|---|---|
| G0 Scope Gate | 范围门禁 | 回到 Intake。 |
| G1 Evidence Gate | 证据门禁 | 回到 Evidence Plan / Ingest。 |
| G2 Claim Gate | Claim 门禁 | 回到 Claims Draft 或报告修复。 |
| G3 Metric Gate | 指标门禁 | 回到 Metrics Draft 或数据层修复。 |
| G4 Segment Report Gate | 细分报告门禁 | 回到 `segment-research`。 |
| G5 Company Universe Gate | 公司池门禁 | 回到 `company-universe`。 |
| G6 Exposure Gate | 暴露门禁 | 回到 `segment-company-mapping`。 |
| G7 Stock Report Gate | 个股报告门禁 | 回到 `stock-deep-dive`。 |
| G8 Backflow Gate | 回写门禁 | 回到 Backflow stage。 |
| G9 No Advice Gate | 投资建议门禁 | 修复文本。 |
| G10 Close Gate | 收尾门禁 | 不能 accepted。 |

| gate_id | 通过条件 |
|---|---|
| G0 Scope Gate | workflow_type、对象、深度、out_of_scope 明确 |
| G1 Evidence Gate | evidence manifest 完整，关键证据可定位，缺口显式标注 |
| G2 Claim Gate | facts / estimates / inferences / management_comment / analyst_view / opinion 分开 |
| G3 Metric Gate | 指标口径、单位、周期、来源、计算方法明确 |
| G4 Segment Report Gate | 细分定义、产业链、关键结论、风险和 evidence map 可追溯 |
| G5 Company Universe Gate | 公司池区分真实暴露、候选暴露、叙事暴露和排除理由 |
| G6 Exposure Gate | exposure_type、score、confidence、evidence_ids、validity 完整 |
| G7 Stock Report Gate | 个股报告可独立阅读，关键结论有 evidence / claim / metric / TODO |
| G8 Backflow Gate | 个股发现已回写或明确 no-backflow 理由 |
| G9 No Advice Gate | 无直接买卖建议，无评分替代交易判断 |
| G10 Close Gate | readout 说明成果、TODO、质量状态和下一步 |

任何 skill-local gate 不得使用新的全局 `G` 编号。

### 11.1 显式 capability-local 检查与兼容别名

R5、Bundle、Night、data-layer、report-production 和 skill-local 检查必须使用明确的局部
前缀或兼容别名，并映射到 G0–G10 中的一个或多个 owner gate。局部控制只在对应风险边界
生效：活动人审只绑定一次最终报告的当前字节 SHA-256；其他 exact-hash、generation lock、
candidate 和 receipt 只保护机器完整性与可重放性；rollback 只保护可变且非幂等的写入事务；
remote receipt 只证明 publication 边界。普通读取、幂等生成和本地质量检查不得因此获得新的
通用门禁。

局部检查不得：

1. 写入新的全局 `G` 编号；
2. 作为 `workflow_state.quality_gates[].gate_id` 的 canonical 值；
3. 重定义工程完成、样例质量、P2 或发布事实；
4. 因历史 Bundle/Night 任务仍 open 而移动活动 V1 的工程终点。

兼容层必须记录 `local_check_id`、`mapped_global_gate_ids`、owner、适用边界和失败回流目标。

Bundle11R–16R 与 legacy R5 sample-quality local checks 已退出普通 orchestrator 的默认 routing。
它们只能在调用方明确请求某个 capability 时作为局部 evaluator 运行，并且必须：

1. 声明被检查的 `affected_capabilities`；
2. 使用既有 local ID，并映射到 G0–G10；
3. 只返回该 capability 的 pass、limitation 或 defect；
4. 由第 6.3 节按当前目标依赖推导 canonical outcome；
5. 不直接写 `workflow_state.status`，也不设置工程完成、样例质量或 P2 事实。

普通 `stock_first_closed_loop`、报告生成、close 和 quality dispatch 不得默认调用这些
Bundle pipeline。仍有通用价值的算法可以保留为显式 evaluator；专用 routing、配置和
实现属于历史兼容资产，不是 canonical 前置条件。

## 12. 固化产物清单

### 12.1 细分到个股闭环必备产物

```text
reports/workflow_runs/<workflow_id>/workflow_state.yaml
reports/workflow_runs/<workflow_id>/run_log.md
reports/workflow_runs/<workflow_id>/artifact_manifest.csv
reports/workflow_runs/<workflow_id>/open_todos.csv
reports/workflow_runs/<workflow_id>/quality_gate_report.md
reports/workflow_runs/<workflow_id>/workflow_readout.md
reports/segments/<segment_id>/<date>_segment_report.md
reports/segments/<segment_id>/company_universe.csv
reports/segments/<segment_id>/scorecard.yaml
reports/segments/<segment_id>/evidence_map.md
data/manifests/evidence_manifest.csv
data/manifests/claims_draft.csv 或 data/manifests/claims_registry.csv
data/manifests/metrics_draft.csv 或 data/manifests/metrics_registry.csv
data/processed/normalized/segment_company_exposure.csv
reports/stocks/<stock_code>/<date>_stock_deep_dive.md
reports/stocks/<stock_code>/segment_exposure.yaml
reports/stocks/<stock_code>/evidence_map.md
```

### 12.2 个股优先闭环必备产物

```text
reports/workflow_runs/<workflow_id>/workflow_state.yaml
reports/workflow_runs/<workflow_id>/run_log.md
reports/workflow_runs/<workflow_id>/quality_gate_report.md
reports/workflow_runs/<workflow_id>/workflow_readout.md
reports/stocks/<stock_code>/<date>_stock_deep_dive.md
reports/stocks/<stock_code>/segment_exposure.yaml
reports/stocks/<stock_code>/evidence_map.md
reports/stocks/<stock_code>/open_questions.md
data/processed/normalized/segment_company_exposure.csv 更新
config/segment_taxonomy.yaml 更新或新增 candidate 说明
```

## 13. 进入 P2 的前置条件

正式进入 P2 前，至少满足：

1. `segment_to_stock_closed_loop` 已有永久 workflow，并能用一个试点复跑。
2. `stock_first_closed_loop` 已有永久 workflow，并能用一个股票复跑。
3. `segment_stock_interlock` 已能验证个股结论如何回写细分。
4. `research-orchestrator` 能创建 workflow run、路由下层 skill、调度门禁并输出 readout。
5. `segment-research`、`stock-deep-dive`、`segment-company-mapping`、
   `quality-review` 的 `SKILL.md` 已强化到可执行粒度。
6. 每个核心 skill 至少有 `references/` 文档或 `assets/` 模板；
   适合脚本化的 skill 至少有一个 `scripts/` 校验或 helper。
7. 至少一次 workflow run 的 readout 能说明：使用了哪些 skill、
   读取了哪些输入、产出了哪些文件、哪些 TODO 未解决。
8. quality-review 没有 `blocks_current_goal=true` 的活动缺陷；severity 只描述风险，
   可见且未被使用的 unknown / limitation 不得仅因 high 而阻断 readiness 判断。

阶段性建设顺序属于 `docs/plans/P1_6_WORKFLOW_BUILDOUT_PLAN.md`，
不在本 kernel 中维护。

## 14. Legacy Bundle / R5 evaluator boundary

Bundle11R–16R and the legacy R5 sample-quality local-check set are capability evaluators, not a
mandatory operating-research inner loop. A caller may explicitly request a
business-line driver, operating-evidence, peer-eligibility, model-link or
sample-benchmark check. The resulting issue rows must carry
`impact_scope`、`active_disposition`、`affected_capabilities` and
`blocks_current_goal`, and must use the existing local-to-G0–G10 mapping.

No Bundle or R5 evaluator may become a default step between T0 and T10, require
historical Bundle generations, or directly decide the canonical outcome.
