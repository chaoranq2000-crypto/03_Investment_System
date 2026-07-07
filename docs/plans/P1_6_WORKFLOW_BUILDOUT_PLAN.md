# P1.6 Workflow Buildout Plan — 进入 P2 前的工作流制度化计划

> 本文件是阶段性建设计划，不是永久 SOP。永久事实源见 `docs/workflows/RESEARCH_WORKFLOW.md` 和 `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md`。
>
> 2026-07-02 update：当前实施顺序调整为 **先跑通 stock-led evidence-to-report MVP，同时完善 `evidence-ingest` 下载执行层**；完整 `segment-research` 和 `company-universe` 契约在 stock-led MVP 之后补齐。

## 0. 从 workflow kernel 迁入的建设顺序

以下内容原位于 `docs/workflows/RESEARCH_WORKFLOW.md` 的
“现在到 P2 前的建设顺序”。它是阶段性建设计划，不定义
canonical `workflow_type`、`stage_id`、`gate_id` 或
`backflow_decision`。

| 原顺序 | 建设事项 | 当前计划归属 |
|---|---|---|
| A | 固化 `RESEARCH_WORKFLOW.md` 作为全局 kernel | Phase A |
| B | 瘦身 `research-orchestrator` skill | Phase A |
| C | 补齐 `segment_to_stock_closed_loop` 的下层步骤和 skill 契约 | Phase C / B2 / B3 |
| D | 补齐 `stock_first_closed_loop` 的下层步骤和 skill 契约 | Phase B / B5-lite |
| E | 补齐 `segment_stock_interlock` 的回写和冲突处理契约 | Phase D / B4-lite |
| F | 做一次 segment-led 调试 | Phase C |
| G | 做一次 stock-led 调试 | Phase B5-debug |
| H | 做一次 interlock 调试 | Phase D |
| I | 执行 `comparison_readiness_gate`，只判断是否进入 P2，不直接做 P2 | Phase E |

若本迁入表与 2026-07-02 update 后的执行顺序存在差异，以本计划
Phase B-E 和第 8 节的当前顺序为准。

## 1. 总目标

进入 P2 前，先完成：

```text
1. 永久总工作流文档；
2. 总工作流编排 skill；
3. evidence-ingest 的下载、归档、manifest、candidate、ingest_log 可执行子层；
4. 个股研究 workflow 的下层步骤和 skill 契约；
5. 细分 ↔ 个股 interlock workflow 的回写和冲突处理；
6. 核心下层 skills 的 SKILL.md / references / scripts / assets 补强；
7. 一次 stock-led 调试；
8. 一次 segment-led 调试；
9. 一次 interlock 调试；
10. P2 readiness gate。
```

## 2. Phase A：总体工作流说明与编排框架

目标：先让“事实源”和“执行入口”成型。

交付物：

```text
docs/workflows/README.md
docs/workflows/RESEARCH_WORKFLOW.md
docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md
.agents/skills/research-orchestrator/SKILL.md
.agents/skills/research-orchestrator/references/skill_routing_matrix.md
.agents/skills/research-orchestrator/references/workflow_state_schema.md
.agents/skills/research-orchestrator/assets/workflow_state_template.yaml
.agents/skills/research-orchestrator/assets/handoff_template.md
.agents/skills/research-orchestrator/scripts/validate_workflow_state.py
.codex/config.research_orchestrator.snippet.toml
```

验收：

```text
- 能解释 workflow_type；
- 能解释 segment-led 和 stock-led 的阶段；
- 能解释细分和个股如何互相回写；
- 能解释每个阶段的主 skill；
- 能解释质量门和 P2 前置条件；
- research-orchestrator 可以作为统一入口路由下层 skill。
```

## 3. Phase B：逐个下层 workflow 的步骤搭建与调试

这一阶段不一次性展开每个步骤的细节，而是按“先 stock-led 消化证据层产物，再回头补完整细分研究”的顺序逐个补强。

### B1. Evidence workflow / `evidence-ingest` 收尾确认

目标：把证据导入从“描述性流程”变成可执行契约，并确认基础 manifest/candidate/debug scripts 能跑。

必须确认：

```text
- SKILL.md：输入、来源优先级、hash 去重、manifest 字段、失败处理；
- references/：source_type、reliability_rank、evidence_id 命名、字段字典；
- scripts/：manifest 校验、hash 计算、路径存在检查；
- assets/：evidence_manifest 示例、evidence card 模板；
- structured_api_pull 只进入 metric candidates，不证明业务暴露；
- official disclosure / URL / local file 进入 manifest 后才能被报告引用。
```

调试标准：能导入或登记一组证据，并通过 manifest 校验。

### B1.5. Stock evidence download layer / `evidence-ingest` acquire 子层

目标：补齐个股研究所需的证据下载/登记执行层，但不新建平级数据下载 skill。

待搭建：

```text
.agents/skills/evidence-ingest/assets/stock_evidence_plan_template.yaml
.agents/skills/evidence-ingest/references/stock_evidence_plan.md
.agents/skills/evidence-ingest/references/official_disclosure_download.md
.agents/skills/evidence-ingest/references/structured_api_pull_runner.md
src/ingest/evidence_io.py
src/ingest/stock_evidence_plan_runner.py
src/ingest/official_disclosure_pull.py
src/ingest/structured_api_pull.py
```

边界：

```text
- 下载器只做 acquire / archive / manifest / candidates / log；
- 不写个股报告；
- 不生成投资结论；
- 不绕过 evidence_manifest；
- Tushare / Baostock 结构化数据默认 metric-only。
```

调试标准：用本地 CSV fixture 或本地 PDF/URL metadata 能生成 `evidence_manifest.csv`、`metrics_draft.csv`、ingest log。

### B5-lite. Stock deep dive workflow / `stock-deep-dive`

目标：不是一次性完成终态个股深度系统，而是让单个股票能消费 B1/B1.5 证据产物，跑通 evidence-to-report MVP。

待搭建：

```text
- company_identity_gate；
- stock_evidence_plan；
- business_breakdown_contract；
- financial_metric_contract；
- linked_segments_discovery；
- mini segment context card handoff；
- segment_exposure.yaml；
- stock_report_contract；
- backflow_decision。
```

调试标准：输入一个 stock_code，可形成个股研究 run，输出 stock report draft、segment_exposure.yaml、evidence_map，并明确回写或不回写原因。

### B4-lite. Mapping workflow / `segment-company-mapping`

目标：先让 mapping 能接住个股研究产出的 `segment_exposure.yaml`，形成稳定 exposure 状态层。

待搭建：

```text
- segment_exposure.yaml 输入契约；
- segment_company_exposure.csv 字段规则；
- exposure_type 枚举；
- exposure_score 证据/TODO 规则；
- confidence 规则；
- revenue_pct / profit_pct MISSING 规则；
- backflow decision 处理；
- exposure_change_note.md 格式。
```

调试标准：输入 `segment_exposure.yaml` 后，能输出或更新 `data/processed/normalized/segment_company_exposure.csv`，或输出 `exposure_change_note.md` 并说明 blocked/TODO。

### B6-lite. Quality review workflow / `quality-review`

目标：把个股闭环质量检查从“泛泛检查”变成明确 issue gate。

待搭建：

```text
- severity 定义；
- issue schema；
- G1 Evidence Gate；
- G2 Claim Gate；
- G3 Metric Gate；
- G6 Exposure Gate；
- G7 Stock Report Gate；
- G8 Backflow Gate；
- G9 No Advice Gate；
- accepted / accepted_with_todos / needs_fix / blocked 判定。
```

调试标准：能对 stock package 输出可修复 issue list，而不是只输出“通过/不通过”。

### B5-debug. Stock-led 调试

目标：用已有 P1 样本公司复跑流程，不追求新增研究量。

推荐样本：

```text
002837 英维克
```

检查：

```text
- research-orchestrator 能创建 stock_first_closed_loop workflow run；
- evidence-ingest 能形成个股证据快照；
- official disclosure 能下载或登记；
- structured_api_pull 能形成 metric candidates；
- stock-deep-dive 能输出 stock package；
- mapping 能接住 segment_exposure.yaml；
- quality-review 能输出具体 issue list；
- readout 能列明 skills、输入、输出、TODO。
```

### B2. Segment research workflow / `segment-research`

目标：在 stock-led MVP 的底层能力已经跑通后，把细分研究拆成可执行步骤，而不是粗略“写报告”。

待搭建：

```text
- 细分定义卡；
- scope_in / scope_out 检查；
- 产业链、需求、供给、利润池、指标体系的字段要求；
- segment_report 输出契约；
- scorecard 字段和评分依据；
- 何时触发 company-universe 和 quality-review。
```

调试标准：用一个已有细分复跑，能稳定生成 segment package 和 TODO。

### B3. Company universe workflow / `company-universe`

目标：让公司池不是关键词列表，而是证据分层的 A 股暴露清单，并复用 stock-led / mapping 的底层规则。

待搭建：

```text
- exposure candidate 分层；
- revenue / product / technology / customer / project / narrative 定义；
- company_universe.csv 字段契约；
- 候选纳入/剔除理由；
- 与 segment-company-mapping 的 handoff。
```

调试标准：能解释为什么某家公司进入公司池、为什么还不是深度研究样本。

### B7. Memo / watchlist workflow / `memo-writer`

目标：memo 只转译已审查研究，不创造新结论。

待搭建：

```text
- memo 输入必须来自 accepted research；
- watchlist note 字段；
- thesis note 字段；
- 纳入/剔除理由；
- 禁止事项。
```

调试标准：从已通过审查的研究生成 watchlist note，且不新增无证据结论。

### B8. Refresh workflow / `refresh-research`

目标：保留 P3 接口，但先做轻量版。

待搭建：

```text
- 新证据发现；
- stale / superseded / contradicted claims；
- scorecard 变化；
- reports_to_regenerate；
- refresh_log。
```

调试标准：给一个已有证据变化样例，能输出 change log，而不是重写全部报告。

## 4. Phase C：Segment-led 调试

目标：在 stock-led MVP 产物可被复用后，用已有试点细分复跑流程，不追求新增研究量。

检查：

```text
- orchestrator 能创建 workflow run；
- evidence-ingest 能形成证据快照；
- segment-research 能按新契约输出 segment package；
- company-universe 能输出公司池；
- mapping 能生成 exposure；
- stock sample selection 能说明选择理由；
- quality-review 能输出 PASS / TODO / FAIL；
- readout 能列明 skills、输入、输出、TODO。
```

## 5. Phase D：Interlock 调试

目标：专门测试“细分 ↔ 个股”的双向交接。

测试：

```text
- 从一个 segment company_universe 选择一家公司进入 stock-deep-dive；
- stock-deep-dive 完成后调整 exposure_score / confidence / notes；
- 回写 company_universe / segment_company_exposure；
- 判断是否影响 scorecard；
- 生成 backflow note；
- quality-review 检查冲突和回写。
```

## 6. Phase E：P2 readiness gate

目标：只判断是否可以进入 P2，不直接做 P2。

检查：

```text
- 永久 workflow 文档是否完成；
- research-orchestrator 是否启用；
- evidence-ingest 下载执行层是否跑通；
- stock-led 是否调试通过；
- segment-led 是否调试通过；
- interlock 是否调试通过；
- quality-review 是否能稳定出具体 issue list；
- high severity issue 是否为 0；
- medium TODO 是否不会阻塞 limited P2 pilot。
```

输出：

```text
reports/p1_6/P1_6_WORKFLOW_BUILDOUT_READOUT.md
reports/p1_6/P2_READINESS_CHECK.md
```

## 7. 不进入 P2 的暂停条件

出现任一情况，不进入 P2：

```text
- evidence-ingest 下载/登记结果没有 manifest row；
- structured API 快照被直接用于业务暴露结论；
- 个股研究 workflow 不能独立启动；
- segment-stock interlock 没有回写验证；
- 下层 SKILL.md 仍只有粗流程；
- references/scripts 仍基本为空壳；
- quality-review 只能泛泛检查，不能输出具体 fix list；
- exposure_score 仍无法追溯 evidence / claim / TODO；
- watchlist / scorecard 容易被误解成交易建议。
```

## 8. 后续逐项讨论顺序

```text
1. B1 收尾确认：evidence-ingest 基础契约与校验；
2. B1.5：stock evidence download layer；
3. B5-lite：stock-deep-dive 最小闭环；
4. B4-lite：segment-company-mapping 最小回写；
5. B6-lite：quality-review 个股质量门；
6. stock-led 调试案例；
7. B2：segment-research 详细搭建；
8. B3：company-universe 详细搭建；
9. segment-led 调试案例；
10. interlock 调试案例；
11. P2 readiness gate。
```
