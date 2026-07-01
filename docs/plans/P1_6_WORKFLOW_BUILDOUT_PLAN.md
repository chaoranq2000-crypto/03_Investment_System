# P1.6 Workflow Buildout Plan — 进入 P2 前的工作流制度化计划

> 本文件是阶段性建设计划，不是永久 SOP。永久事实源见 `docs/workflows/RESEARCH_WORKFLOW.md` 和 `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md`。

## 1. 总目标

进入 P2 前，先完成：

```text
1. 永久总工作流文档；
2. 总工作流编排 skill；
3. 细分研究 workflow 的下层步骤和 skill 契约；
4. 个股研究 workflow 的下层步骤和 skill 契约；
5. 细分 ↔ 个股 interlock workflow 的回写和冲突处理；
6. 核心下层 skills 的 SKILL.md / references / scripts / assets 补强；
7. 一次 segment-led 调试；
8. 一次 stock-led 调试；
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

这一阶段不一次性展开每个步骤的细节，而是按顺序逐个讨论、补强和调试。

### B1. Evidence workflow / `evidence-ingest`

目标：把证据导入从“描述性流程”变成可执行契约。

待搭建：

```text
- SKILL.md：输入、来源优先级、hash 去重、manifest 字段、失败处理；
- references/：source_type、reliability_rank、evidence_id 命名、字段字典；
- scripts/：manifest 校验、hash 计算、路径存在检查；
- assets/：evidence_manifest 示例、evidence card 模板。
```

调试标准：能导入或登记一组证据，并通过 manifest 校验。

### B2. Segment research workflow / `segment-research`

目标：把细分研究拆成可执行步骤，而不是粗略“写报告”。

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

目标：让公司池不是关键词列表，而是证据分层的 A 股暴露清单。

待搭建：

```text
- exposure candidate 分层；
- revenue / product / technology / customer / project / narrative 定义；
- company_universe.csv 字段契约；
- 候选纳入/剔除理由；
- 与 segment-company-mapping 的 handoff。
```

调试标准：能解释为什么某家公司进入公司池、为什么还不是深度研究样本。

### B4. Mapping workflow / `segment-company-mapping`

目标：把细分和公司的多对多关系变成稳定状态层。

待搭建：

```text
- segment_company_exposure.csv 字段规则；
- exposure_score 规则；
- confidence 规则；
- valid_from / valid_to / stale 状态；
- backflow decision 处理；
- 变更日志格式。
```

调试标准：从 company_universe 生成或更新 exposure，并能处理个股回写。

### B5. Stock deep dive workflow / `stock-deep-dive`

目标：建立完整独立个股研究工作流。

待搭建：

```text
- company identity gate；
- 公司证据计划；
- 业务拆解；
- 财务指标；
- linked_segments discovery；
- segment_exposure.yaml；
- valuation scenario 边界；
- 风险和反证；
- 个股报告输出契约；
- 与 mapping / segment-research 的 backflow。
```

调试标准：输入一个 stock_code，可独立完成个股研究 run，并回写或明确不回写细分资产。

### B6. Quality review workflow / `quality-review`

目标：把质量检查从“泛泛检查”变成明确 issue gate。

待搭建：

```text
- severity 定义；
- issue schema；
- evidence gate；
- claim gate；
- metric gate；
- exposure gate；
- no-advice gate；
- accepted / accepted_with_todos / needs_fix / blocked 判定。
```

调试标准：能对 segment package 和 stock package 输出可修复 issue list。

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

目标：用已有试点细分复跑流程，不追求新增研究量。

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

## 5. Phase D：Stock-led 调试

目标：验证个股研究可以独立启动。

检查：

```text
- 输入 stock_code；
- 确认 company_id / security；
- 导入或复用证据；
- 初筛 linked_segments；
- 形成 segment_exposure.yaml；
- 输出个股报告草案或复核现有报告；
- 回写 exposure 或说明 no_backflow_needed；
- quality-review 和 readout。
```

## 6. Phase E：Interlock 调试

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

## 7. Phase F：P2 readiness gate

目标：只判断是否可以进入 P2，不直接做 P2。

检查：

```text
- 永久 workflow 文档是否完成；
- research-orchestrator 是否启用；
- 核心下层 skills 是否补强；
- segment-led 是否调试通过；
- stock-led 是否调试通过；
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

## 8. 不进入 P2 的暂停条件

出现任一情况，不进入 P2：

```text
- 细分研究 workflow 不能说明每步调用什么 skill；
- 个股研究 workflow 不能独立启动；
- segment-stock interlock 没有回写验证；
- 下层 SKILL.md 仍只有粗流程；
- references/scripts 仍基本为空壳；
- quality-review 只能泛泛检查，不能输出具体 fix list；
- exposure_score 仍无法追溯 evidence / claim / TODO；
- watchlist / scorecard 容易被误解成交易建议。
```

## 9. 后续逐项讨论顺序

建议后续逐个讨论：

```text
1. evidence-ingest workflow 详细搭建；
2. segment-research workflow 详细搭建；
3. company-universe workflow 详细搭建；
4. segment-company-mapping workflow 详细搭建；
5. stock-deep-dive workflow 详细搭建；
6. quality-review workflow 详细搭建；
7. memo-writer / refresh-research 最小补强；
8. segment-led 调试案例；
9. stock-led 调试案例；
10. interlock 调试案例；
11. P2 readiness gate。
```
