# Research Workflow — 细分/个股研究永久总工作流

> 本文件是 A-share Research OS 的永久总工作流事实源。它说明日常研究系统如何运转、细分研究与个股研究如何互相调用和回写、总编排 skill 如何组织下层 skills。它不是项目建设计划，也不是某次 P1/P1.5 readout。

本文件是唯一 global workflow kernel。以下接口事实只在本文件定义：

```text
workflow_type enum
global stage sequence
global gate_id enum
backflow_decision enum
workflow run status enum
P2 readiness conditions
```

其他 docs、skill docs、references、scripts 和 reports 只能引用这些全局 ID，不能复制或扩展全局枚举。

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

## 1. 系统层级

```text
用户请求
  ↓
research-orchestrator：总工作流编排、状态管理、skill 路由、门禁判断、readout
  ↓
下层 skills：evidence-ingest / segment-research / company-universe / segment-company-mapping / stock-deep-dive / quality-review / memo-writer / refresh-research
  ↓
研究状态资产：evidence / claims / metrics / segment taxonomy / segment-company exposure / scorecards / watchlist
  ↓
报告产物：segment report / stock deep dive / evidence map / refresh log / memo / workflow readout
```

`research-orchestrator` 是执行入口，但不是研究内容来源。它负责回答：

```text
现在是什么工作流？
现在处于哪一步？
下一步该调用哪个 skill？
下层 skill 需要哪些输入？
产物是否满足门禁？
质量问题应该回到哪一步修复？
当前是否能进入 P2？
```

## 2. 永久工作流类型

当前永久工作流分为五类：

| workflow_type | 触发场景 | 主线 | 当前用途 |
|---|---|---|---|
| `segment_to_stock_closed_loop` | 从一个细分、产业链环节、主题或产品开始 | 细分定义 → 证据 → claims/metrics → 公司池 → exposure → 个股样本 → 回写 → 质量审查 | P1/P1.5 主闭环 |
| `stock_first_closed_loop` | 从一个股票、公司或公司研究问题开始 | 公司身份 → 证据 → 业务/财务 → linked_segments → exposure → 个股报告 → 回写细分 | P2 前必须补齐 |
| `segment_stock_interlock` | 专门处理细分和个股之间的双向回写、冲突和更新 | exposure / company_universe / segment_taxonomy / scorecard 的同步 | 两个主闭环的连接层 |
| `refresh_existing_research` | 更新已有细分、个股、watchlist 或旧结论 | 新证据 → stale/superseded/contradicted claims → scorecard/watchlist 变化 → refresh log | P3 前保留接口，P2 前可做轻量刷新 |
| `comparison_readiness_gate` | 准备进入 P2 的横向比较 | 检查多个细分/个股是否具备可比性 | 进入 P2 前必须执行 |

P2 之前，重点不是批量比较，而是把 `segment_to_stock_closed_loop`、`stock_first_closed_loop` 和 `segment_stock_interlock` 制度化并调试通过。

以下标识不是永久 `workflow_type`：

| 标识 | 正确身份 | 事实源 |
|---|---|---|
| `stock_report_production` | `stock-deep-dive` 下的 `profile_id` | `.agents/skills/stock-deep-dive/references/report_production_profile.md` |
| `workflow_diagnostic` | non-run diagnostic mode，可不创建 workflow run | `.agents/skills/research-orchestrator/references/orchestration_contract.md` |

## 3. 共享对象与交接资产

| 对象 | 作用 | 主要存放位置 |
|---|---|---|
| Segment | 细分定义、边界、别名、上级主题、相邻细分 | `config/segment_taxonomy.yaml`、`reports/segments/<segment_id>/` |
| Company | 上市公司身份、证券代码、名称、基础信息 | `config/`、`data/processed/normalized/`、`reports/stocks/` |
| Evidence | 原始证据和来源登记 | `data/raw/`、`data/processed/`、`data/manifests/evidence_manifest.csv` |
| Claim | 从证据摘出的事实、估计、推断、管理层表述等 | `data/manifests/claims_draft.csv`、`data/manifests/claims_registry.csv` |
| Metric | 结构化指标观察值 | `data/manifests/metrics_draft.csv`、`data/manifests/metrics_registry.csv` |
| Exposure | 细分与公司的多对多暴露关系 | `data/processed/normalized/segment_company_exposure.csv` |
| Report | 某一时点的可再生产物 | `reports/segments/`、`reports/stocks/` |
| Scorecard | 结构化评分，服务于比较前的统一口径 | `reports/**/scorecard.yaml` |
| WatchItem | 观察对象、原因、证据、触发条件、复核日期 | `config/watchlist.yaml`、`reports/**/watchlist*` |
| WorkflowRun | 某次工作流执行状态和交接记录 | `reports/workflow_runs/<workflow_id>/` |

## 4. Workflow run 标准目录

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
wf_<YYYYMMDD>_<workflow_type>_<object_id>
```

示例：

```text
wf_20260701_segment_to_stock_ai_server_liquid_cooling
wf_20260701_stock_first_cn_002837_invic
```

## 5. Workflow state 最小字段

`workflow_state.yaml` 至少包含：

```yaml
workflow_id:
workflow_type:
status: planned | in_progress | blocked | needs_fix | ready_for_review | accepted | accepted_with_todos | archived
created_at:
updated_at:
owner:
active_segment_id:
active_company_id:
current_stage:
completed_stages: []
next_stage:
active_skill:
required_next_skill:
evidence_snapshot:
claims_snapshot:
metrics_snapshot:
artifacts: []
open_todos: []
quality_gates: []
entry_criteria:
exit_criteria:
notes:
```

状态含义：

| status | 含义 |
|---|---|
| `planned` | 工作流已定义，尚未开始 |
| `in_progress` | 正在执行某一步 |
| `blocked` | 缺关键输入、证据、配置或路径，无法继续 |
| `needs_fix` | 产物存在质量问题，需要回到具体 stage 修复 |
| `ready_for_review` | 主要产物完成，等待质量审查或人工复核 |
| `accepted` | 关键门禁通过，无 high severity 问题 |
| `accepted_with_todos` | 无 high severity 问题，但保留 medium/low TODO |
| `archived` | 历史运行，保留但不作为当前状态 |

## 6. Skill 角色分工

| skill | 主要职责 | 不负责 |
|---|---|---|
| `research-orchestrator` | 识别工作流、维护状态、路由 skill、生成 handoff、检查门禁、输出 readout | 不直接写研究结论、不虚构证据、不替代下层 skill |
| `evidence-ingest` | 证据导入、去重、解析、登记，维护 evidence manifest 和候选 claims/metrics | 不写完整细分或个股报告 |
| `segment-research` | 细分定义、边界、产业链、需求/供给/利润池、指标体系、细分报告、scorecard | 不做单一个股完整深度 |
| `company-universe` | 从细分建立 A 股公司池，区分 revenue/product/technology/customer/project/narrative 等暴露 | 不做完整个股研究 |
| `segment-company-mapping` | 维护 `segment_company_exposure`，管理暴露类型、评分、置信度、证据和有效期 | 不写行业或个股长文报告 |
| `stock-deep-dive` | 个股业务、财务、linked_segments、风险、反证、估值场景和 evidence map | 不替代细分研究，不做多股排序 |
| `quality-review` | 检查证据追溯、claim 类型、指标口径、过期证据、风险反证和禁止事项 | 不作为新增结论来源 |
| `memo-writer` | 将已通过审查的研究转为 memo、watchlist note 或 thesis note | 不创造未经证据支持的新研究结论 |
| `refresh-research` | 新证据驱动旧结论更新，输出 refresh log、stale claims、reports_to_regenerate | 不静默重写旧报告 |
| `compare-segments` | P2 以后多细分横向比较 | 不在 readiness gate 前使用 |
| `compare-stocks` | P2 以后同细分个股横向比较 | 不在基础闭环未通过时使用 |

## 7. 主闭环一：`segment_to_stock_closed_loop`

### 7.1 适用场景

用户从一个细分方向开始，希望形成可追溯的细分研究、公司池、个股样本和观察项。

示例：

```text
$research-orchestrator 启动细分到个股闭环：AI服务器液冷，深度=standard。
```

### 7.2 阶段表

| 阶段 | 目标 | 主 skill | 关键输入 | 关键输出 | 门禁 |
|---|---|---|---|---|---|
| S0 Intake | 明确对象、范围、深度、是否 P2 前置 | `research-orchestrator` | 用户请求、AGENTS、README、workflow docs | `workflow_state.yaml`、`run_log.md` | 范围不扩散 |
| S1 Segment Definition | 定义 segment_id、scope_in/out、相邻细分 | `segment-research` | 用户输入、`segment_taxonomy.yaml` | segment definition / boundary note | 边界清楚 |
| S2 Evidence Plan & Ingest | 制定证据计划并登记证据 | `evidence-ingest` | source registry、细分定义、公司线索 | raw/processed evidence、`evidence_manifest.csv` | 证据有 id、来源、日期、路径、等级 |
| S3 Claims & Metrics Draft | 拆 facts/comments/estimates/inferences 与指标 | `evidence-ingest` + `quality-review` | evidence manifest、processed text/tables | `claims_draft.csv`、`metrics_draft.csv` | 类型分离，不把预测当事实 |
| S4 Segment Report Draft | 生成细分研究初稿 | `segment-research` | definition、claims、metrics | segment report、evidence map | 关键结论可追溯 |
| S5 Company Universe | 找 A 股公司池并区分暴露层级 | `company-universe` | segment report、claims、evidence | `company_universe.csv` | 不是简单股票列表 |
| S6 Exposure Mapping | 建立多对多暴露映射 | `segment-company-mapping` | company universe、evidence ids | `segment_company_exposure.csv` | 每条 exposure 有证据、置信度、notes |
| S7 Stock Sample Selection | 选择 1–2 家样本进入个股深度 | `research-orchestrator` | exposure、公司池、TODO | sample selection note | 说明样本选择目的 |
| S8 Stock Deep Dive | 生成个股深度样本 | `stock-deep-dive` | 公司证据、linked_segments、metrics | stock report、segment_exposure、evidence map | 个股可独立阅读且可回溯 |
| S9 Backflow | 个股发现回写细分、公司池和 exposure | `segment-company-mapping` + `segment-research` | stock report、segment exposure | updated exposure / taxonomy candidate / segment TODO | 不让个股结论孤立存在 |
| S10 Scorecard & Watchlist Draft | 形成评分和观察项 | `segment-research` + `stock-deep-dive` + `memo-writer` | reports、claims、metrics、exposure | scorecard、watchlist draft | 评分有依据，不是买卖信号 |
| S11 Quality Review | 总审查 | `quality-review` | 所有产物 | quality gate report、quality issues | 无 high severity issue |
| S12 Fix Loop | 根据质量问题回到对应阶段 | `research-orchestrator` | quality issues | handoff to target skill | 每个 issue 有 owner/stage/status |
| S13 Close Readout | 固化成果、TODO 和状态 | `research-orchestrator` | final artifacts、quality gate | workflow readout | accepted / needs_fix / blocked 明确 |

### 7.3 进入个股深度的条件

进入 S8 前，必须满足：

1. `company_universe.csv` 已存在；
2. 候选公司至少有一条 evidence 或明确 TODO；
3. 候选公司的 `exposure_type`、`exposure_score`、`confidence` 已初步标注；
4. 样本选择目的清楚：核心暴露、争议暴露、边界案例或反证案例；
5. 没有把 `narrative` 暴露直接升级成 `revenue` 暴露。

## 8. 主闭环二：`stock_first_closed_loop`

### 8.1 适用场景

用户从股票代码、公司名称或公司研究问题开始，希望形成独立个股深度，并将其映射到一个或多个细分。

示例：

```text
$research-orchestrator 启动个股优先闭环：002837 英维克，目标=独立个股深度并回写 linked_segments。
```

### 8.2 阶段表

| 阶段 | 目标 | 主 skill | 关键输入 | 关键输出 | 门禁 |
|---|---|---|---|---|---|
| T0 Intake | 明确股票、公司、范围、是否已有 linked_segments | `research-orchestrator` | 用户请求、公司基础信息 | `workflow_state.yaml` | 公司身份唯一 |
| T1 Company Evidence | 收集年报、公告、财务数据、IR、新闻等证据 | `evidence-ingest` | stock_code、source registry | evidence manifest 更新 | 证据覆盖业务、财务、风险 |
| T2 Business & Financial Skeleton | 搭业务和财务骨架 | `stock-deep-dive` | evidence、metrics | business table、financial skeleton | 先搭骨架，不急于结论 |
| T3 Linked Segment Discovery | 识别公司可能关联的细分 | `stock-deep-dive` + `segment-company-mapping` | 业务线、产品、客户、募投、订单 | linked_segments draft | 区分已确认/候选/排除 |
| T4 Segment Context Check | 检查 linked segments 是否已有定义 | `research-orchestrator` | `segment_taxonomy.yaml`、reports/segments | existing links / segment candidates | 不能凭空挂细分 |
| T5 Mini Segment Card | 对缺失但重要的细分建立最小定义卡 | `segment-research` | linked segment candidate | segment definition candidate | 只做最小上下文，不扩成 P2 |
| T6 Exposure Mapping | 更新该公司在多个细分中的 exposure | `segment-company-mapping` | linked_segments、evidence | `segment_exposure.yaml`、`segment_company_exposure.csv` | 每条 exposure 有证据和置信度 |
| T7 Stock Report Draft | 写个股深度报告 | `stock-deep-dive` | evidence、claims、metrics、linked_segments | stock deep dive、evidence map | 个股报告可独立成立 |
| T8 Backflow | 回写 segment taxonomy / company universe / exposure | `segment-company-mapping` + `segment-research` | stock report、exposure | updated segment assets | 个股发现不孤立存在 |
| T9 Quality Review | 审查个股报告和映射 | `quality-review` | stock artifacts | quality report | 无 high severity issue |
| T10 Close Readout | 输出个股闭环 readout | `research-orchestrator` | final artifacts | workflow readout | accepted / needs_fix / blocked 明确 |

### 8.3 个股研究的独立性和依赖性

个股研究可以独立启动，因为它能从股票代码直接开始，先完成公司业务、财务、治理、风险和证据地图。

但它不能脱离细分体系，因为：

1. 业务线和产品最终需要判断是否对应已有或候选细分；
2. `segment_exposure.yaml` 和 `segment_company_exposure.csv` 是个股结论进入系统状态层的入口；
3. 如果个股发现新细分或推翻已有暴露关系，必须回写细分资产或形成 TODO。

## 9. 连接闭环：`segment_stock_interlock`

### 9.1 二者关系

| 关系 | 说明 |
|---|---|
| 细分研究可以独立存在 | 可以先研究市场结构、产业链和指标，即使尚未完成个股深度 |
| 个股研究可以独立启动 | 可以从股票代码开始，再反向识别 linked_segments |
| 二者通过 exposure 连接 | `segment_company_exposure` 是正式连接层 |
| 二者共享 evidence / claims / metrics | 同一证据可支持细分 claim，也可支持个股 claim |
| 二者通过 backflow 互相更新 | 个股发现要回写细分，公司池变化要触发个股复核 |

### 9.2 从细分进入个股

常见触发条件：

1. 某公司 exposure_score 高，需要验证真实收入、订单或客户；
2. 某公司是边界样本，需要验证是否只是叙事暴露；
3. 某公司影响细分 scorecard 的 A 股纯度或业绩可见度；
4. 某公司有反证价值，能帮助检验细分叙事。

### 9.3 从个股回到细分

个股研究完成后，必须给出 backflow decision：

| decision | 含义 | 典型动作 |
|---|---|---|
| `update_exposure` | 个股证据改变了暴露类型、分数或置信度 | 更新 `segment_company_exposure.csv` |
| `update_company_universe` | 公司池中该公司的备注、暴露层级或证据需要更新 | 更新 `company_universe.csv` |
| `update_segment_taxonomy` | 发现新细分、相邻细分或边界问题 | 更新 `segment_taxonomy.yaml` 或新增 candidate |
| `update_scorecard` | 个股发现影响细分评分 | 更新 scorecard 或 scorecard TODO |
| `no_backflow_needed` | 个股研究没有改变细分状态 | 写明原因，不默默跳过 |
| `blocked` | 证据不足，无法判断是否回写 | 进入 TODO / quality issue |

### 9.4 冲突处理

当细分报告和个股报告冲突时：

1. 先比较证据日期、来源等级和 entity 粒度；
2. 个股最新公告优先影响该公司，不自动外推整个细分；
3. 行业数据用于细分层，不能自动推导单家公司收入占比；
4. 管理层表述只能作为 `management_comment`，不能直接覆盖 fact；
5. 冲突必须进入 quality issue，并标记 `needs_review`。

## 10. 质量门禁

本节是唯一 global `gate_id` 表。其他文件可引用这些 gate，但不得重新定义全局 gate enum。

| gate_id | name | scope | pass condition | failed handling |
|---|---|---|---|---|
| G0 | Scope Gate | All workflows | `workflow_type`、对象、深度、out_of_scope 和 start stage 明确 | 回到 intake / orchestrator |
| G1 | Evidence Gate | Evidence and source layer | evidence manifest 存在；关键来源有 id、日期、source rank、路径或 explicit TODO | 回到 evidence-ingest |
| G2 | Claim Gate | Claims and narrative assertions | fact、estimate、inference、management_comment、analyst_view、opinion、unknown 分离 | 回到 claims review 或 source extraction |
| G3 | Metric Gate | Structured metrics | metric period、unit、source、calculation method 和 estimate status 明确 | 回到 metric extraction / review |
| G4 | Segment Report Gate | Segment package | segment definition、scope、关键 claims、metrics、risks 和 evidence map 可追溯 | 回到 segment-research |
| G5 | Company Universe Gate | Segment company pool | 公司纳入 / 排除理由和 exposure level 绑定证据，不只是关键词列表 | 回到 company-universe |
| G6 | Exposure Gate | Segment-company mapping | `exposure_type`、`exposure_score`、confidence、evidence_ids、valid_from / valid_to 或 TODO 存在 | 回到 segment-company-mapping |
| G7 | Stock Report Gate | Stock package | 个股报告可独立阅读；material statements 引用 evidence / claim / metric / TODO；风险和反证可见 | 回到 stock-deep-dive |
| G8 | Backflow Gate | Segment-stock interlock | stock 或 segment findings 已回写，或有明确 `no_backflow_needed` / `blocked` 理由 | 回到 mapping / segment-research / stock-deep-dive |
| G9 | No Advice Gate | All user-facing outputs | 无直接 buy/sell/hold 指令、仓位建议、保证收益或 score-as-trade signal | 交付前修复文本 |
| G10 | Close Gate | Workflow closeout | readout 列出 status、artifacts、quality gates、TODOs、backflow decisions 和 next actions | 修复前不得标记 accepted |

### Skill-level subchecks

单个 skill 可以在 global gate 下定义局部 `subcheck_id`，但不得把 subcheck 当作新的 global `gate_id`。

| subcheck_id | parent_gate_id | name |
|---|---|---|
| G7-DL | G7 | Data Layer Pack Check |
| G7-R4 | G7 | R4 Publishable Stock Report Check |

## 11. 固化产物清单

### 11.1 细分到个股闭环必备产物

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

reports/stocks/<stock_code>_<company_name>/<date>_stock_deep_dive.md
reports/stocks/<stock_code>_<company_name>/segment_exposure.yaml
reports/stocks/<stock_code>_<company_name>/evidence_map.md
```

### 11.2 个股优先闭环必备产物

```text
reports/workflow_runs/<workflow_id>/workflow_state.yaml
reports/workflow_runs/<workflow_id>/run_log.md
reports/workflow_runs/<workflow_id>/quality_gate_report.md
reports/workflow_runs/<workflow_id>/workflow_readout.md

reports/stocks/<stock_code>_<company_name>/<date>_stock_deep_dive.md
reports/stocks/<stock_code>_<company_name>/segment_exposure.yaml
reports/stocks/<stock_code>_<company_name>/evidence_map.md
reports/stocks/<stock_code>_<company_name>/open_questions.md

data/processed/normalized/segment_company_exposure.csv 更新
config/segment_taxonomy.yaml 更新或新增 candidate 说明
```

## 12. 进入 P2 的前置条件

正式进入 P2 前，至少满足：

1. `segment_to_stock_closed_loop` 已有永久 workflow，并能用一个试点复跑；
2. `stock_first_closed_loop` 已有永久 workflow，并能用一个股票复跑；
3. `segment_stock_interlock` 已能验证个股结论如何回写细分；
4. `research-orchestrator` 能创建 workflow run、路由下层 skill、检查门禁并输出 readout；
5. `segment-research`、`stock-deep-dive`、`segment-company-mapping`、`quality-review` 的 `SKILL.md` 已强化到可执行粒度；
6. 每个核心 skill 至少有 `references/` 文档或 `assets/` 模板；适合脚本化的 skill 至少有一个 `scripts/` 校验或 helper；
7. 至少一次 workflow run 的 readout 能说明：使用了哪些 skill、读取了哪些输入、产出了哪些文件、哪些 TODO 未解决；
8. quality-review 无 high severity issue；medium TODO 已明确不会阻塞 P2 pilot。

## 13. 现在到 P2 前的建设顺序

建议顺序：

```text
A. 建立总工作流事实源和 research-orchestrator skill
B. 补齐 segment_to_stock_closed_loop 的下层步骤和 skill 契约
C. 补齐 stock_first_closed_loop 的下层步骤和 skill 契约
D. 补齐 segment_stock_interlock 的回写和冲突处理契约
E. 逐个补强 evidence-ingest / segment-research / company-universe / segment-company-mapping / stock-deep-dive / quality-review
F. 做一次 segment-led 调试
G. 做一次 stock-led 调试
H. 做一次 interlock 调试
I. 执行 comparison_readiness_gate，只判断是否进入 P2，不直接做 P2
```
