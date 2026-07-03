# P1.6 R4 → P2 Readiness：工作区审阅与 Codex 下一步任务计划

> 生成日期：2026-07-03
> 适用仓库：`chaoranq2000-crypto/03_Investment_System`
> 当前判定：`P1.6 / R4-readiness bridge_only / Pre-P2 disclosure review`
> 执行边界：本计划只推进 P1.6 收尾与 P2 readiness gate；不得直接进入 P2，不得生成买入/卖出/持有建议，不得把结构化行情/财务数据直接升级为业务暴露事实。

---

## 0. Codex 执行总指令

请 Codex 将本文件作为下一轮实施计划。执行时先读取以下事实源和最新 readout：

```text
README.md
docs/workflows/RESEARCH_WORKFLOW.md
docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md
docs/plans/P1_6_WORKFLOW_BUILDOUT_PLAN.md
docs/plans/DATA_LAYER_R4_READINESS_NEXT_TASKS.md
reports/p1_6/STOCK_LED_EVIDENCE_DOWNLOAD_MVP_READOUT.md
reports/p1_6/DATA_LAYER_NEXT_TASKS_MASTER_READOUT.md
reports/p1_6/R4_READINESS_NEXT_TASKS_MASTER_READOUT.md
reports/p1_6/P2_READINESS_PRECHECK_AFTER_DATA_LAYER.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_quality_gate_report.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_source_gap_report.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_stock_deep_dive_v0_1.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/business_segment_metric_pack.csv
```

本轮最高优先级不是“继续写更长的个股报告”，而是把 R4 从 `bridge_only` 推进到可审查的下一状态：

```text
目标状态优先级：
1. publishable_ready_with_disclosure_todos
2. bridge_only_with_review_decisions
3. needs_fix
4. blocked
```

如无法达到 `publishable_ready_with_disclosure_todos`，必须明确说明保留哪些 blocker，不得把缺口伪装成已解决。

---

## 1. 审阅结论

### 1.1 当前阶段判断

当前系统仍处于 P1.6，尚未进入 P2。更准确的状态是：

```text
P1.6 / R4-readiness bridge_only / Pre-P2 Disclosure Review Stage
```

含义：

```text
1. 工作区骨架、长期规则、workflow 文档、skills 目录、数据层桥接已经建立。
2. stock-led evidence download MVP、data-layer bridge、R4 readiness draft 已经跑通。
3. R4 v0.1 已生成，但质量门状态为 bridge_only。
4. P2 readiness 只做了 precheck，结论为 not_ready_for_p2。
5. 当前剩余核心工作是披露复核、业务暴露补证、segment-stock 回写和 artifact 格式修复。
```

### 1.2 计划完成情况总览

| 模块 / 阶段 | 当前状态 | 判断 |
|---|---:|---|
| P0 工作区骨架 | completed / conditional pass | 已完成，仓库结构、AGENTS、docs、skills、templates、reports、tests 都已存在。 |
| P1 试点闭环 | conditional pass with todos | 已跑通过 `ai_server_liquid_cooling` 与 002837 样本，但仍有披露与回写 TODO。 |
| P1.6 Phase A 工作流事实源 | mostly completed | `RESEARCH_WORKFLOW.md` 与 `WORKFLOW_ORCHESTRATION_SPEC.md` 已成为事实源。 |
| research-orchestrator 编排入口 | completed enough for P1.6 | 已定义 workflow_type、routing、handoff、quality gate、readout 规则。 |
| evidence-ingest B1/B1.5 | completed with accepted TODOs | 证据计划、下载/登记层、structured API runner、official disclosure runner 已搭建；真实 API smoke 未执行。 |
| stock-deep-dive B5-lite | completed for bridge / not publishable | 能生成 stock-first run 和 R4 v0.1，但报告仍为 bridge_only。 |
| segment-company-mapping B4-lite | partial | 有 segment_exposure 和 exposure_change_note 产物，但 global exposure registry 回写尚未放行。 |
| quality-review B6-lite | partial completed | 能输出 R4 quality gate 和 issue list，但 official reconciliation review 尚未完成。 |
| official disclosure reconciliation | partial_done_with_review_todos | 已从 stub 变成 partial MVP；仍有 mismatch / official_missing / structured_missing。 |
| business segment extraction | done_with_missing_disclosure | 已生成 business segment pack；液冷收入占比和利润占比仍为 MISSING_DISCLOSURE。 |
| R4 publishable gate | defined | gate 文档已存在，明确区分 `bridge_only` 与 `publishable_ready`。 |
| R4 v0.1 stock report | bridge_only_done | 已生成，包含财务、业务、暴露、估值、技术、催化剂、风险和 gaps；不是发布级报告。 |
| segment-led replay | not completed in latest R4 flow | 仍需在 R4 v0.2 或回写后复跑。 |
| interlock debug | blocked / pending | 当前 local product clue 尚未更新 global exposure registry。 |
| P2 readiness gate | not opened | precheck 结果为 not_ready_for_p2。 |

---

## 2. 已完成搭建工作清单

### 2.1 工作区与规则层

已完成：

```text
1. README 明确项目是 evidence-first A 股投研工作区，不是交易系统。
2. docs/workflows/RESEARCH_WORKFLOW.md 已定义总原则、工作流类型、共享对象、workflow run 目录、状态字段、质量门和 P2 前置条件。
3. docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md 已定义 research-orchestrator 的职责、workflow 分类、run 创建规则、handoff packet、routing matrix、quality gate、artifact manifest 和 open TODO schema。
4. .agents/skills/ 下已有核心 skills：research-orchestrator、evidence-ingest、segment-research、company-universe、segment-company-mapping、stock-deep-dive、quality-review、memo-writer、refresh-research、compare-segments、compare-stocks 等。
5. src/ 目录已按 ingest / extract / normalize / qa / report / research / review / scoring / utils 等分层。
```

### 2.2 Evidence / data layer 工程层

已完成：

```text
1. stock-led evidence download MVP 已补入 evidence-ingest 体系，而不是新建平级 data-downloader skill。
2. 新增或强化：
   - stock_evidence_plan_template.yaml
   - stock_evidence_plan.md
   - official_disclosure_download.md
   - structured_api_pull_runner.md
   - evidence_io.py
   - stock_evidence_plan_runner.py
   - official_disclosure_pull.py
   - structured_api_pull.py
3. Tushare / Baostock adapter hardening 已完成默认安全门：fixture / dry-run / live 模式，live 需要显式 allow-network，token 不写入 tracked artifacts。
4. Data-layer bridge 能生成或消费 financial / valuation / technical / peer 等 data packs。
5. structured snapshots 保持 metric-only，不用于证明业务暴露。
```

### 2.3 Stock-first / R4 工作流层

已完成：

```text
1. 创建了 stock-first workflow run：wf_20260703_stock_first_002837_invic。
2. 已生成丰富的 run artifacts，包括：
   - workflow_state.yaml
   - artifact_manifest.csv
   - stock_evidence_plan.yaml
   - evidence_manifest_delta.csv
   - metrics_registry.csv
   - claims_registry.csv
   - business_breakdown.yaml
   - financial_quality.yaml
   - segment_exposure.yaml
   - backflow_decision.yaml
   - exposure_change_note.md
   - risk_counter_evidence.yaml
   - catalyst_calendar.yaml
   - R4_stock_deep_dive_v0_1.md
   - R4_quality_gate_report.md
   - R4_source_gap_report.md
3. R4 v0.1 已经从纯 data-layer bridge draft 进化为一版内部 readiness draft。
4. R4 report 已包含：metadata、一句话结论、财务质量、业务拆分、细分暴露、估值上下文、技术/市场观察、催化剂、风险与反证、source gaps、跟踪清单。
```

### 2.4 Official reconciliation / business segment extraction

已完成但有 TODO：

```text
1. official_financial_reconciliation.csv 已存在，不再只是 stub。
2. official reconciliation 当前结果：mismatch_rows=3，official_missing_rows=4，structured_missing_rows=3。
3. 未把结构化财务指标 promote 为 reported fact。
4. 未用公司级财务指标推导业务暴露。
5. business_segment_metric_pack.csv 已存在，包含 reviewed_official、product_line_clue、narrative_only、missing_disclosure 等状态。
6. 储能应用收入约 17 亿元作为 reviewed_official 记录，但明确不是数据中心液冷收入。
7. 液冷收入占比、液冷毛利率、液冷利润占比仍保持 MISSING_DISCLOSURE。
```

### 2.5 测试和边界

已完成：

```text
1. 最新 R4 master readout 记录全量 pytest：79 passed, 2 skipped。
2. targeted tests、py_compile、restricted-language scan、git diff --check 均通过或仅剩 line-ending warning。
3. no-advice gate 通过。
4. 没有进入 P2。
5. 没有执行真实 live API smoke。
6. 没有把 structured data 写成业务暴露事实。
```

---

## 3. 当前主要缺口和风险

### 3.1 P2 仍被阻塞

当前 `P2_READINESS_PRECHECK_AFTER_DATA_LAYER.md` 的结论是：

```text
not_ready_for_p2
```

阻塞项：

```text
P2-BLOCK-001：official reconciliation mismatch rows 需要 quality-review。
P2-BLOCK-002：业务分部收入/利润披露仍需补证或保持 MISSING_DISCLOSURE。
P2-BLOCK-003：local product_line_clue 是否能回写 global exposure registry 尚未解决。
P2-BLOCK-004：manual live smoke 未执行；低优先级，不阻塞 P2 本身，但不能被误称已完成。
```

### 3.2 R4 v0.1 不是发布级报告

当前 R4 quality gate：

```text
r4_publishable_gate_status: bridge_only
high_issues: 0
medium_issues: 3
low_issues: 0
```

三个 medium issue：

```text
1. 3 条 official reconciliation mismatch rows 需要 review。
2. 4 个 company-level fields remain official_missing。
3. liquid-cooling revenue_pct / profit_pct remain MISSING_DISCLOSURE。
```

### 3.3 液冷暴露仍只有产品线索

当前只能说：

```text
英维克存在数据中心、算力设备、液冷相关产品线索。
```

还不能说：

```text
液冷收入占比是多少；
液冷毛利率是多少；
AI 服务器液冷贡献多少收入或利润；
客户/订单/产能对收入有多少量化贡献。
```

原因：

```text
business_segment_metric_pack.csv 中 liquid_cooling_revenue_pct 和 liquid_cooling_gross_margin 均为 MISSING_DISCLOSURE；product_line_clue 不能生成 revenue_pct 或 profit_pct。
```

### 3.4 segment-stock interlock 还没真正完成

当前 `segment_exposure.yaml` 与 `business_segment_metric_pack.csv` 只支持 local product exposure clue。global `segment_company_exposure.csv` 是否允许更新仍待 mapping gate 决定。

必须避免：

```text
把 local product_line_clue 直接升级成 revenue exposure；
把 exposure_score 提高到类似“收入暴露”的级别；
让 R4 个股发现孤立存在、不回写或不明确 blocked reason。
```

### 3.5 Artifact 物理格式仍需再次修复

虽然前序 readout 记录已做格式化，但最新 R4 相关 artifacts 在 raw 视图中仍有明显单行/近似单行问题。需要重新修生成器，不只手改文件。

重点问题：

```text
R4_stock_deep_dive_v0_1.md 只有约 11 个物理行，多个章节挤在同一行。
business_segment_metric_pack.csv 只有约 3 个物理行，多条记录挤在同一行。
R4_quality_gate_report.md 和 R4_source_gap_report.md 也存在压缩行问题。
```

---

## 4. Codex 下一步执行计划

## Phase 0：创建本轮执行状态与边界

### 目标

让 Codex 在动手前固化本轮不是 P2，不做扩展研究，不生成交易建议。

### Owner skill

```text
research-orchestrator
```

### 输入

```text
本计划文件
reports/p1_6/R4_READINESS_NEXT_TASKS_MASTER_READOUT.md
reports/p1_6/P2_READINESS_PRECHECK_AFTER_DATA_LAYER.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/workflow_state.yaml
```

### 任务

```text
1. 新增本轮计划文件到 docs/plans/，建议路径：
   docs/plans/R4_DISCLOSURE_BACKFLOW_NEXT_TASKS.md

2. 创建或更新 workflow run 状态：
   reports/workflow_runs/wf_20260703_stock_first_002837_invic/workflow_state.yaml

3. 设置：
   current_stage: R4_disclosure_review_and_backflow
   required_next_skill: research-orchestrator
   status: in_progress

4. 新增 run log 记录：
   reports/workflow_runs/wf_20260703_stock_first_002837_invic/run_log.md

5. 新增 handoff：
   reports/workflow_runs/wf_20260703_stock_first_002837_invic/handoffs/<next>_to_quality-review_official_reconciliation_review.md
```

### 输出

```text
reports/p1_6/R4_DISCLOSURE_BACKFLOW_NEXT_TASKS_PLAN_READOUT.md
```

### 验收标准

```text
1. 明确本轮不是 P2 gate。
2. 明确不新增细分、不扩公司池、不做比较报告。
3. workflow_state.yaml 的 next_stage 指向 Phase 1 或 Phase 2。
4. open_todos.csv 包含 P2-BLOCK-001/002/003/004 的当前状态。
```

---

## Phase 1：R4 artifact physical formatting cleanup

### 目标

修复 R4 相关 artifacts 的物理换行和可读性，并修复对应生成器，避免下一次 run 复发。

### Owner skill

```text
research-orchestrator + quality-review + src/report generator owner
```

### 重点输入

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_stock_deep_dive_v0_1.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_quality_gate_report.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_source_gap_report.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/business_segment_metric_pack.csv
reports/p1_6/R4_READINESS_NEXT_TASKS_MASTER_READOUT.md
reports/p1_6/OFFICIAL_DISCLOSURE_RECONCILIATION_MVP_READOUT.md
reports/p1_6/BUSINESS_SEGMENT_DISCLOSURE_EXTRACTION_MVP_READOUT.md
```

### 任务

```text
1. 找出生成 R4 report / quality gate / source gap / business segment CSV 的脚本或 helper。
2. 修复 Markdown 输出：
   - 每个 H1/H2/H3 独立物理行；
   - 表格 header、separator、每条 row 独立物理行；
   - 段落之间保留空行；
   - 中文章节不与表格挤在同一行。
3. 修复 CSV 输出：
   - 使用 csv.writer；
   - lineterminator="\n"；
   - 每条业务记录一行；
   - 字段内逗号必须正确 quote。
4. 修复 YAML 输出：
   - allow_unicode=True；
   - sort_keys=False；
   - default_flow_style=False。
5. 禁止 Windows backslash path 出现在新增 artifacts 中。
6. 重新生成 R4 v0.1 格式化版，或生成 R4 v0.1.1 formatting-only 版。
7. 不改变任何研究判断、issue severity、TODO 数量、gate status。
```

### 新增/更新测试

```text
tests/test_r4_artifact_formatting.py
```

建议断言：

```text
1. R4_stock_deep_dive_v0_1.md 物理行数 >= 80。
2. R4_quality_gate_report.md 物理行数 >= 20。
3. R4_source_gap_report.md 物理行数 >= 30。
4. business_segment_metric_pack.csv 行数 = header + 6 data rows 或与实际记录数一致。
5. Markdown 中 `## 2.`、`## 3.` 等章节不出现在同一物理行。
6. 新增 artifacts 不含 `reports\\workflow_runs`。
```

### 输出

```text
reports/p1_6/R4_ARTIFACT_FORMATTING_CLEANUP_READOUT.md
```

### 验收命令

```bash
python -m py_compile $(git ls-files '*.py')
python -m pytest -q tests/test_r4_artifact_formatting.py
python -m pytest -q
```

### 验收标准

```text
1. Raw 视图不再近似单行。
2. diff 可读。
3. parser / grep 可稳定处理。
4. 研究内容、R4 gate、TODO 均不改变。
```

---

## Phase 2：Official reconciliation review decision

### 目标

处理 `official_financial_reconciliation.csv` 中的 mismatch / official_missing / structured_missing，不要求全部 matched，但要求每条都有明确 review decision。

### Owner skill

```text
quality-review
```

### 辅助 skill

```text
evidence-ingest
stock-deep-dive
```

### 输入

```text
reports/workflow_runs/wf_20260703_data_layer_002837_invic/official_financial_reconciliation.csv
reports/workflow_runs/wf_20260703_data_layer_002837_invic/financial_metric_pack.csv
reports/workflow_runs/wf_20260703_data_layer_002837_invic/evidence_manifest.csv
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_stock_deep_dive_v0_1.md
```

### 任务

```text
1. 对 3 条 mismatch rows 逐条判断原因：
   - period mismatch；
   - metric definition mismatch；
   - unit mismatch；
   - fixture value stale；
   - official table extraction locator issue；
   - structured provider field mismatch。

2. 对 4 条 official_missing rows 逐条判断：
   - 是否官方披露确实缺失；
   - 是否已在年报表格中但 extractor 未覆盖；
   - 是否应加入 evidence acquisition TODO；
   - 是否可保留为 explicit official_missing。

3. 对 3 条 structured_missing rows 逐条判断：
   - 是否结构化源未提供；
   - 是否字段未映射；
   - 是否影响 R4 report 的公司级财务结论。

4. 输出 review decision 表，字段建议：
   metric_name
   period
   current_status
   review_decision
   root_cause
   action
   promotion_allowed
   owner_skill
   notes

5. promotion_allowed 默认 false。只有在 official evidence 与结构化字段口径一致，且 quality-review 明确允许时才可 true。

6. 更新 R4_quality_gate_report：
   - R4-G1 不再泛写 “mismatch rows require review”；
   - 改为逐条 issue 或已处理 decision。
```

### 输出

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/official_reconciliation_review_decision.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/official_reconciliation_review_decision.csv
reports/p1_6/OFFICIAL_RECONCILIATION_REVIEW_DECISION_READOUT.md
```

### 新增/更新测试

```text
tests/test_official_reconciliation_review_decision.py
```

建议断言：

```text
1. 每条 mismatch 都有 review_decision。
2. official_missing 不得被当作 matched。
3. promotion_allowed=true 的行必须有 official_evidence_id 和 locator。
4. review decision 不得生成 business exposure claim。
5. R4 gate 能读取 review_decision 并更新 issue 状态。
```

### 验收命令

```bash
python -m py_compile $(git ls-files '*.py')
python -m pytest -q tests/test_official_financial_reconciliation.py tests/test_official_reconciliation_review_decision.py
python -m pytest -q tests/test_r4_publishable_stock_report_gate.py
python -m pytest -q
```

### 验收标准

```text
1. P2-BLOCK-001 从 “open” 变为 resolved 或 explicitly_blocked_with_reason。
2. R4-G1 具备逐条处理结论。
3. 没有结构化数据被自动 promote。
4. 不把公司级财务 reconciliation 用于证明液冷业务暴露。
```

---

## Phase 3：Liquid-cooling exposure evidence escalation

### 目标

围绕英维克液冷业务暴露做一次专门证据升级审查。目标不是强行找到收入占比，而是把“找过什么、找到什么、没找到什么、能支持什么 exposure_type”写清楚。

### Owner skill

```text
evidence-ingest
```

### 辅助 skill

```text
stock-deep-dive
quality-review
```

### 输入

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/business_segment_metric_pack.csv
reports/workflow_runs/wf_20260703_stock_first_002837_invic/segment_exposure.yaml
reports/workflow_runs/wf_20260703_stock_first_002837_invic/evidence_manifest_delta.csv
reports/workflow_runs/wf_20260703_stock_first_002837_invic/evidence_gap_requests.yaml
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_source_gap_report.md
```

### 证据优先级

只允许以下来源用于升级业务暴露：

```text
A. 官方定期报告：年报、半年报、季报。
B. 官方公告：业务合同、订单、产能、募投、重大事项。
C. 交易所互动 / 投资者关系记录：只能作为 management_comment 或 product/customer clue，不能直接作为收入事实。
D. 公司官网/新闻：最多作为 clue，不得直接用于 revenue/profit exposure。
E. Tushare / Baostock：只能作为公司级 metric 或 market context，不得证明液冷收入占比。
```

### 任务

```text
1. 检查现有 evidence_manifest 是否已有：
   - 2025 年年报全文或摘要；
   - 最近一期季报/半年报；
   - 与液冷、电子散热、机房温控、数据中心、算力设备相关公告；
   - 投资者关系记录或互动问答。

2. 如果证据文件已有，复用 processed text/table。
3. 如果证据文件没有，生成 evidence_gap_requests.yaml，不直接联网补数据，除非用户明确允许。
4. 从官方证据中提取液冷相关字段，分类为：
   - disclosed_revenue
   - disclosed_margin
   - product_line_clue
   - customer_clue
   - order_clue
   - capacity_clue
   - narrative_only
   - missing_disclosure

5. 严格区分：
   - 机房温控收入 ≠ 液冷收入；
   - 储能应用收入 ≠ 数据中心液冷收入；
   - 电子散热产品线索 ≠ 液冷收入占比；
   - 客户测试/平台验证 ≠ 订单收入。

6. 更新或新增：
   liquid_cooling_exposure_evidence_review.md

7. 如有确凿官方披露，更新 business_segment_metric_pack.csv；否则继续保持 MISSING_DISCLOSURE。

8. 生成新的 source gap decision：
   - DISCLOSURE-SEGMENT-001 resolved / still_missing_disclosure
   - DISCLOSURE-SEGMENT-002 resolved / still_todo_source_required
   - R4-GAP-001 resolved / still_missing_disclosure
```

### 输出

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/liquid_cooling_exposure_evidence_review.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/liquid_cooling_exposure_evidence_review.csv
reports/p1_6/LIQUID_COOLING_EXPOSURE_EVIDENCE_REVIEW_READOUT.md
```

### 新增/更新测试

```text
tests/test_liquid_cooling_exposure_evidence_review.py
```

建议断言：

```text
1. product_line_clue 不生成 revenue_pct。
2. customer_clue 不生成 revenue_pct。
3. order_clue 不生成收入，除非官方披露金额和确认规则明确。
4. missing_disclosure 必须进入 R4_source_gap_report。
5. disclosed_revenue 必须有 official_evidence_id 和 locator。
6. 储能应用收入不得映射成 ai_server_liquid_cooling revenue_pct。
```

### 验收命令

```bash
python -m py_compile $(git ls-files '*.py')
python -m pytest -q tests/test_business_segment_extraction.py tests/test_liquid_cooling_exposure_evidence_review.py
python -m pytest -q tests/test_segment_exposure_gate.py
python -m pytest -q
```

### 验收标准

```text
1. P2-BLOCK-002 被 resolved 或明确保留为 still_missing_disclosure。
2. R4_source_gap_report 更新为可审查状态。
3. 不新增无证据的液冷收入/利润数据。
4. 不把产品线索升级成收入暴露。
```

---

## Phase 4：Segment-stock interlock backflow review

### 目标

决定当前 002837 英维克的 local product_line_clue 是否可以回写到 global exposure registry；如果不能，必须输出 blocked reason 和 TODO。

### Owner skill

```text
segment-company-mapping
```

### 辅助 skill

```text
quality-review
research-orchestrator
```

### 输入

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/segment_exposure.yaml
reports/workflow_runs/wf_20260703_stock_first_002837_invic/business_segment_metric_pack.csv
reports/workflow_runs/wf_20260703_stock_first_002837_invic/exposure_change_note.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/backflow_decision.yaml
data/processed/normalized/segment_company_exposure.csv
config/segment_taxonomy.yaml
reports/segments/ai_server_liquid_cooling/company_universe.csv
```

### 任务

```text
1. 读取当前 local segment_exposure.yaml。
2. 读取 business_segment_metric_pack.csv 的 evidence_class / review_status。
3. 执行 exposure gate：
   - exposure_type 是否允许；
   - exposure_score 是否有证据或 TODO；
   - revenue_pct / profit_pct 是否缺失且显式为 MISSING_DISCLOSURE；
   - evidence_ids 是否指向 official evidence；
   - confidence 是否与证据类型一致。

4. 生成 backflow decision：
   - update_exposure
   - update_company_universe
   - update_segment_taxonomy
   - no_backflow_needed
   - blocked

5. 当前默认建议：
   - 允许 product exposure 回写，前提是 evidence_id / locator / confidence / notes 完整；
   - 不允许 revenue exposure 回写；
   - 不允许 profit exposure 回写；
   - exposure_score 不能因叙事热度上调；
   - 若 product exposure 已存在，仅更新 notes / evidence_ids / valid_from。

6. 如允许回写，更新：
   data/processed/normalized/segment_company_exposure.csv
   reports/segments/ai_server_liquid_cooling/company_universe.csv

7. 如不允许回写，输出：
   exposure_backflow_review.md
   exposure_change_note.md
   open_todos.csv 更新 P2-BLOCK-003。
```

### 输出

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/exposure_backflow_review.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/exposure_backflow_review.yaml
reports/p1_6/SEGMENT_STOCK_BACKFLOW_REVIEW_READOUT.md
```

### 新增/更新测试

```text
tests/test_segment_stock_backflow_review.py
```

建议断言：

```text
1. product_line_clue 只能回写 product exposure。
2. missing revenue_pct 不阻止 product exposure，但必须保持 MISSING_DISCLOSURE。
3. missing profit_pct 不阻止 product exposure，但必须保持 MISSING_DISCLOSURE。
4. narrative_only 不允许回写 revenue/product exposure。
5. update_exposure 必须生成 change note。
6. blocked 必须生成 owner 和 next_action。
```

### 验收命令

```bash
python -m py_compile $(git ls-files '*.py')
python -m pytest -q tests/test_segment_exposure_gate.py tests/test_segment_stock_backflow_review.py
python -m pytest -q
```

### 验收标准

```text
1. P2-BLOCK-003 被 resolved 或明确 blocked_with_reason。
2. global registry 不会被无证据 revenue/profit 暴露污染。
3. 个股发现不再孤立存在。
```

---

## Phase 5：R4 v0.2 draft and quality gate rerun

### 目标

在 Phase 1–4 完成后，生成 R4 v0.2。目标是把 R4 从 `bridge_only` 推进到 `publishable_ready_with_disclosure_todos`；如不能达到，必须给出明确阻塞。

### Owner skill

```text
stock-deep-dive
```

### 辅助 skill

```text
quality-review
research-orchestrator
```

### 输入

```text
R4_stock_deep_dive_v0_1.md
R4_quality_gate_report.md
R4_source_gap_report.md
official_reconciliation_review_decision.md
liquid_cooling_exposure_evidence_review.md
exposure_backflow_review.md
valuation_snapshot.yaml
technical_snapshot.yaml
peer_market_snapshot.csv
risk_counter_evidence.yaml
catalyst_calendar.yaml
```

### 任务

```text
1. 生成 R4_stock_deep_dive_v0_2.md。
2. 保留 v0.1 已有章节结构，但强化：
   - official reconciliation review decisions；
   - business exposure evidence review；
   - backflow decision；
   - source gaps 状态；
   - TODO/watch items 的 owner 与 next evidence。

3. 禁止：
   - 买入/卖出/持有；
   - 交易目标价；
   - 仓位建议；
   - 用技术快照写操作信号；
   - 用 peer context 写推荐排序；
   - 用结构化财务数据证明液冷收入；
   - 隐藏 MISSING_DISCLOSURE。

4. 重新生成：
   - R4_quality_gate_report_v0_2.md
   - R4_source_gap_report_v0_2.md
   - R4_open_questions_v0_2.md

5. 质量门重新判断：
   - publishable_ready
   - publishable_ready_with_disclosure_todos
   - bridge_only
   - blocked
```

### 输出

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_stock_deep_dive_v0_2.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_quality_gate_report_v0_2.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_source_gap_report_v0_2.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_open_questions_v0_2.md
reports/p1_6/R4_STOCK_REPORT_DRAFT_V0_2_READOUT.md
```

### 新增/更新测试

```text
tests/test_r4_stock_report_v0_2_gate.py
```

建议断言：

```text
1. R4 v0.2 引用 official review decision。
2. R4 v0.2 引用 liquid cooling exposure review。
3. R4 v0.2 引用 backflow review。
4. source gaps 不被隐藏。
5. no-advice gate 通过。
6. 若 liquid-cooling revenue_pct 仍 MISSING_DISCLOSURE，则报告不得写液冷收入占比。
7. gate status 只能是允许枚举。
```

### 验收命令

```bash
python -m py_compile $(git ls-files '*.py')
python -m pytest -q tests/test_r4_publishable_stock_report_gate.py tests/test_r4_stock_report_v0_2_gate.py
python -m pytest -q
```

### 验收标准

```text
1. high_issues = 0。
2. medium issues 均有 owner、next_action、blocking_decision。
3. R4 status 不再含糊。
4. 如果仍 bridge_only，必须说明阻塞路径。
```

---

## Phase 6：Segment-led replay preparation

### 触发条件

只有当 Phase 5 达到以下任一状态，才执行 Phase 6：

```text
publishable_ready
publishable_ready_with_disclosure_todos
bridge_only_with_review_decisions
```

如果 Phase 5 为 `blocked`，不得进入 Phase 6。

### 目标

用 R4 v0.2 的审查结果反哺 `ai_server_liquid_cooling` 细分资产，为后续 segment-led replay 做准备。

### Owner skill

```text
research-orchestrator
segment-research
segment-company-mapping
```

### 任务

```text
1. 生成 segment-led replay handoff。
2. 检查 002837 对 ai_server_liquid_cooling scorecard / company_universe 的影响。
3. 不重写完整细分报告，只输出 replay preparation note。
4. 明确哪些字段需要 segment-research 后续复跑：
   - company_universe notes；
   - exposure confidence；
   - evidence map；
   - scorecard evidence_quality；
   - A-share purity TODO。
```

### 输出

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/segment_led_replay_preparation_note.md
reports/p1_6/SEGMENT_LED_REPLAY_PREPARATION_READOUT.md
```

### 验收标准

```text
1. 不生成 P2 comparison。
2. 不新增公司池。
3. 只为 segment-led replay 准备输入。
4. 明确下一步该由 segment-research 还是 company-universe 处理。
```

---

## Phase 7：P2 readiness gate rerun, not P2 pilot

### 触发条件

必须满足：

```text
1. Phase 1 完成格式修复。
2. Phase 2 完成 official reconciliation review decision。
3. Phase 3 完成 liquid-cooling exposure evidence review。
4. Phase 4 完成 backflow review。
5. Phase 5 完成 R4 v0.2 gate rerun。
```

### Owner skill

```text
research-orchestrator + quality-review
```

### 任务

```text
1. 生成新的 P2 readiness check，不是 precheck：
   reports/p1_6/P2_READINESS_CHECK_AFTER_R4_V0_2.md

2. 按 P2 前置条件逐项判断：
   - segment_to_stock_closed_loop 是否已有永久 workflow；
   - stock_first_closed_loop 是否已通过一个股票复跑；
   - segment_stock_interlock 是否已验证回写或 blocked reason；
   - research-orchestrator 是否能路由、handoff、gate、readout；
   - 核心 skills 是否具备 executable contract；
   - 每个核心 skill 是否有 references / assets / scripts；
   - workflow run readout 是否列明 skills、inputs、outputs、TODO；
   - high severity issue 是否为 0；
   - medium TODO 是否不阻塞 limited P2 pilot。

3. 输出三种可能结论之一：
   - ready_for_limited_p2_pilot
   - not_ready_for_p2_with_resolved_r4_review
   - not_ready_for_p2_blocked

4. 即使 ready，也不得自动启动 P2 comparison；只给出下一轮 P2 pilot 计划。
```

### 输出

```text
reports/p1_6/P2_READINESS_CHECK_AFTER_R4_V0_2.md
reports/p1_6/R4_DISCLOSURE_BACKFLOW_MASTER_READOUT.md
```

### 验收命令

```bash
python -m py_compile $(git ls-files '*.py')
python -m pytest -q
```

### 验收标准

```text
1. P2 gate 结论有证据支持。
2. 如果 ready，必须说明 limited P2 pilot 的范围和禁止事项。
3. 如果 not ready，必须列 blocker_id、severity、owner、next_action。
4. 不生成 compare-segments / compare-stocks 报告。
```

---

## 5. 本轮禁止事项

Codex 执行本计划时不得做：

```text
1. 不进入 P2。
2. 不生成 compare-segments 或 compare-stocks 正式报告。
3. 不扩展新细分。
4. 不批量扩大公司池。
5. 不把 R4 v0.1 或 v0.2 写成买入/卖出/持有建议。
6. 不写仓位建议、交易计划、止盈止损、目标价操作建议。
7. 不把 Tushare / Baostock 数据作为业务暴露证据。
8. 不把 product_line_clue / narrative_only 升级为 revenue exposure。
9. 不隐藏 MISSING_DISCLOSURE、TODO_MARKET_DATA、official_missing、mismatch。
10. 不执行真实 Tushare / Baostock API smoke，除非用户显式启用。
11. 不提交 token、live raw response 或未脱敏外部响应。
12. 不覆盖 raw evidence。
```

---

## 6. 建议的最终文件变更清单

### 6.1 新增计划 / readout

```text
docs/plans/R4_DISCLOSURE_BACKFLOW_NEXT_TASKS.md
reports/p1_6/R4_DISCLOSURE_BACKFLOW_NEXT_TASKS_PLAN_READOUT.md
reports/p1_6/R4_ARTIFACT_FORMATTING_CLEANUP_READOUT.md
reports/p1_6/OFFICIAL_RECONCILIATION_REVIEW_DECISION_READOUT.md
reports/p1_6/LIQUID_COOLING_EXPOSURE_EVIDENCE_REVIEW_READOUT.md
reports/p1_6/SEGMENT_STOCK_BACKFLOW_REVIEW_READOUT.md
reports/p1_6/R4_STOCK_REPORT_DRAFT_V0_2_READOUT.md
reports/p1_6/P2_READINESS_CHECK_AFTER_R4_V0_2.md
reports/p1_6/R4_DISCLOSURE_BACKFLOW_MASTER_READOUT.md
```

### 6.2 新增或更新 workflow artifacts

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/official_reconciliation_review_decision.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/official_reconciliation_review_decision.csv
reports/workflow_runs/wf_20260703_stock_first_002837_invic/liquid_cooling_exposure_evidence_review.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/liquid_cooling_exposure_evidence_review.csv
reports/workflow_runs/wf_20260703_stock_first_002837_invic/exposure_backflow_review.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/exposure_backflow_review.yaml
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_stock_deep_dive_v0_2.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_quality_gate_report_v0_2.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_source_gap_report_v0_2.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_open_questions_v0_2.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/segment_led_replay_preparation_note.md
```

### 6.3 可能更新的状态资产

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/workflow_state.yaml
reports/workflow_runs/wf_20260703_stock_first_002837_invic/run_log.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/artifact_manifest.csv
reports/workflow_runs/wf_20260703_stock_first_002837_invic/open_todos.csv
reports/workflow_runs/wf_20260703_stock_first_002837_invic/business_segment_metric_pack.csv
reports/workflow_runs/wf_20260703_stock_first_002837_invic/segment_exposure.yaml
data/processed/normalized/segment_company_exposure.csv
reports/segments/ai_server_liquid_cooling/company_universe.csv
```

### 6.4 建议新增测试

```text
tests/test_r4_artifact_formatting.py
tests/test_official_reconciliation_review_decision.py
tests/test_liquid_cooling_exposure_evidence_review.py
tests/test_segment_stock_backflow_review.py
tests/test_r4_stock_report_v0_2_gate.py
```

---

## 7. 本轮总体验收命令

Codex 完成每个 phase 后可局部测试；最终必须运行：

```bash
python -m py_compile $(git ls-files '*.py')
python -m pytest -q tests/test_r4_artifact_formatting.py
python -m pytest -q tests/test_official_financial_reconciliation.py tests/test_official_reconciliation_review_decision.py
python -m pytest -q tests/test_business_segment_extraction.py tests/test_liquid_cooling_exposure_evidence_review.py
python -m pytest -q tests/test_segment_exposure_gate.py tests/test_segment_stock_backflow_review.py
python -m pytest -q tests/test_r4_publishable_stock_report_gate.py tests/test_r4_stock_report_v0_2_gate.py
python -m pytest -q
```

另做文本扫描：

```bash
rg "买入|卖出|持有|仓位|止盈|止损|交易建议|强烈推荐|目标价.*买" reports/workflow_runs/wf_20260703_stock_first_002837_invic reports/p1_6
rg "reports\\\\workflow_runs|data\\\\raw" reports/workflow_runs/wf_20260703_stock_first_002837_invic reports/p1_6
```

预期：

```text
1. pytest 全量通过。
2. 无 high severity issue。
3. no-advice scan 通过。
4. source gaps 可见。
5. R4 gate 给出明确状态。
6. P2 readiness 不被静默放行。
```

---

## 8. Codex 可直接执行的任务提示词

```text
请按照 docs/plans/R4_DISCLOSURE_BACKFLOW_NEXT_TASKS.md 执行 P1.6 R4 → P2 readiness 收尾任务。

范围：只处理 wf_20260703_stock_first_002837_invic 与相关 p1_6 readout，不扩新细分、不扩公司池、不生成 P2 comparison。

第一步先读取：
- README.md
- docs/workflows/RESEARCH_WORKFLOW.md
- docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md
- docs/plans/P1_6_WORKFLOW_BUILDOUT_PLAN.md
- reports/p1_6/R4_READINESS_NEXT_TASKS_MASTER_READOUT.md
- reports/p1_6/P2_READINESS_PRECHECK_AFTER_DATA_LAYER.md
- reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_quality_gate_report.md
- reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_source_gap_report.md

按以下顺序执行：
1. R4 artifact physical formatting cleanup；
2. official reconciliation review decision；
3. liquid-cooling exposure evidence review；
4. segment-stock backflow review；
5. R4_stock_deep_dive_v0_2 + quality gate rerun；
6. P2 readiness check after R4 v0.2，但不启动 P2 pilot。

所有新增结论必须引用 evidence_id / claim_id / metric_id / TODO / MISSING_DISCLOSURE。结构化数据只能作为 metric/market context，不能证明业务暴露。R4 报告不得出现买入、卖出、持有、仓位建议、交易计划或技术操作指令。

完成后输出：
- reports/p1_6/R4_DISCLOSURE_BACKFLOW_MASTER_READOUT.md
- reports/p1_6/P2_READINESS_CHECK_AFTER_R4_V0_2.md
- 必要的 workflow artifacts 和 tests。

最后运行：
python -m py_compile $(git ls-files '*.py')
python -m pytest -q
并在 readout 中记录结果。
```

---

## 9. 完成后的决策树

```text
如果 R4 v0.2 = publishable_ready：
    可以准备 limited P2 pilot 计划，但仍不要自动进入 P2。

如果 R4 v0.2 = publishable_ready_with_disclosure_todos：
    可以进入 P2 readiness gate；若 medium TODO 不阻塞，可建议 limited P2 pilot。

如果 R4 v0.2 = bridge_only_with_review_decisions：
    不进入 P2；下一步继续 disclosure evidence acquisition 或 parser/table extraction。

如果 R4 v0.2 = blocked：
    不进入 P2；根据 high/medium issue 回到对应 skill 修复。
```

---

## 10. 我对下一步优先级的最终建议

最优先的三个任务是：

```text
1. 先修 R4 artifact 物理格式和生成器。
2. 再做 official reconciliation review decision。
3. 再做 liquid-cooling exposure evidence review + backflow review。
```

原因：

```text
1. 格式不修，后续人工审阅、diff、parser、quality gate 都不稳定。
2. official mismatch 不审，R4 财务质量无法从 bridge-only 进阶。
3. 液冷业务暴露不补证或不明确 MISSING_DISCLOSURE，R4 永远不能接近样例级个股研究。
4. backflow 不处理，stock-first 工作不会沉淀到 segment-company exposure 状态层，系统会退化为单篇报告生成器。
```

本轮不要追求“写得像样例报告一样长”。当前更重要的是让每条关键结论、每个缺口、每次回写都能被系统追踪和复核。
