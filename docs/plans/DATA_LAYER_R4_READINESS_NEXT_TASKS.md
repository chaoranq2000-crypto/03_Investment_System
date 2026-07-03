# Data Layer R4 Readiness Next Tasks

> 本文件用于承接上一轮 data-layer master plan 执行结果。
> 当前阶段仍属于 P1.6，不进入 P2，不生成买入/卖出/持有建议，不接自动交易，不把结构化数据直接升级为业务暴露事实。
> 本轮重点从“数据层工程闭环”转向“官方披露核对、业务分部证据补强、R4 个股报告发布门槛”。

## 0. 当前状态

当前数据层建设已经完成主要工程闭环：

```text
Data Layer Master Plan: FUNCTIONAL_PASS_WITH_FORMAT_AND_DISCLOSURE_TODOS

工程闭环: 基本通过
数据层状态: accepted_with_todos
下游桥接: 已跑通
真实 API: hardening 完成，manual live smoke 未跑
正式个股报告: 未生成
P2 readiness: 不允许
```

已完成：

```text
1. data-layer-only workflow 已能生成 financial / valuation / technical / peer 等 data packs。
2. stock-deep-dive 已能消费 data-layer packs。
3. quality-review 已能通过 G10 Data Layer Pack Gate 审查数据层输入。
4. R4_stock_report_data_layer_bridge_draft.md 已生成。
5. integrated data-layer debug 已跑通。
6. Tushare / Baostock live adapter hardening 已完成默认安全门，但真实服务 smoke 尚未执行。
7. data-layer master readout 已生成。
```

仍未完成：

```text
1. 部分 CSV / YAML / Markdown artifacts 在 GitHub raw 视图中仍呈现单行或近似单行，需要重新修复物理换行。
2. DATA_LAYER_ACCEPTANCE_CHECKLIST.md 与最新 master readout 状态不一致。
3. official disclosure reconciliation 仍停留在 stub，尚未进行正式财务指标核对。
4. 英维克业务分部、液冷收入占比、液冷毛利率、客户/订单/产能等核心业务证据仍未补齐。
5. R4 publishable stock report gate 尚未制度化。
6. R4_stock_deep_dive_v0_1.md 尚未生成。
7. P2 readiness 只能做 precheck，不能正式放行。
```

## 1. 本轮总体目标

本轮目标不是继续扩展更多行情源，也不是立刻生成发布级报告，而是完成 R4 个股深度报告前置条件：

```text
1. 修复 artifacts 物理格式，确保 GitHub raw、diff、grep、parser 均可用。
2. 对齐 checklist、readout、workflow 状态。
3. 建立 official disclosure reconciliation MVP。
4. 建立 business segment disclosure extraction MVP。
5. 定义 R4 publishable stock deep dive gate。
6. 生成 R4_stock_deep_dive_v0_1.md。
7. 准备 manual live smoke playbook，但不自动执行真实 API。
8. 做一次 P2 readiness precheck，但结论预计仍为 not_ready_for_p2。
```

## 2. 推荐执行顺序

```text
Next-0  Reopen DL-1.5 Artifact Physical Line Formatting
Next-1  Acceptance Checklist Reconciliation After Master Completion
Next-2  Official Disclosure Reconciliation MVP
Next-3  Business Segment Disclosure Extraction MVP
Next-4  R4 Publishable Stock Deep Dive Gate Definition
Next-5  R4 Stock Report Draft v0.1
Next-6  Manual Live Smoke Preparation, Not Execution
Next-7  P2 Readiness Precheck, Not Gate
```

建议先执行前三项：

```text
Next-0 artifact 物理换行修复
Next-1 checklist 状态对齐
Next-2 official disclosure reconciliation MVP
```

这三项完成后，系统才真正从“数据层工程打通”进入“能支撑正式个股研究”的阶段。

---

# Next-0 Reopen DL-1.5 Artifact Physical Line Formatting

## 目标

修复当前部分 artifacts 在 GitHub raw 中仍呈现单行或近似单行的问题。

本任务只修格式，不改变研究结论，不改变 accepted TODO 数量，不接真实 API。

## 背景问题

上一轮 DL-1.5 声称部分 CSV / YAML / Markdown 已格式化，但实际 raw 文件中仍可能出现：

```text
1. CSV header 与多条 issue/todo 被挤在同一物理行；
2. YAML 被 dump 成单行；
3. Markdown section 不清晰；
4. Windows backslash path 出现在 artifacts 中；
5. readout 声称的物理行数与实际文件不一致。
```

## 需要检查的文件

```text
reports/workflow_runs/wf_20260703_data_layer_002837_invic/data_layer_issue_list.csv
reports/workflow_runs/wf_20260703_data_layer_002837_invic/open_todos.csv
reports/workflow_runs/wf_20260703_data_layer_002837_invic/workflow_state.yaml
reports/workflow_runs/wf_20260703_data_layer_002837_invic/technical_snapshot.yaml
reports/workflow_runs/wf_20260703_data_layer_002837_invic/valuation_snapshot.yaml

reports/workflow_runs/wf_20260703_stock_first_002837_invic/quality_gate_report_after_data_layer_bridge.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/data_layer_bridge_issue_list.csv
reports/workflow_runs/wf_20260703_stock_first_002837_invic/data_layer_bridge_readout.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/integrated_data_layer_readout.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/remaining_source_gaps_after_data_layer_bridge.md
```

## 任务

```text
1. 检查上述 artifacts 的真实物理行数。
2. 修复相关生成器，避免下次 run 再次生成单行文件。
3. CSV 使用 csv.writer，并显式设置 lineterminator="\n"。
4. YAML 使用 block style：
   - allow_unicode=True
   - sort_keys=False
   - default_flow_style=False
5. Markdown 使用标题、段落、表格、列表分行输出。
6. 所有 artifact path 使用 repo-relative POSIX path。
7. 不允许出现 reports\workflow_runs\... 这类 Windows path。
8. 重新生成当前 data-layer run 和 stock-first bridge run 的相关 artifacts。
```

## 测试要求

新增或更新测试：

```text
1. data_layer_issue_list.csv 至少 4 行：header + 3 issue/todo rows。
2. open_todos.csv 至少 4 行：header + 3 todo rows。
3. workflow_state.yaml 至少 20 行，且可被 yaml.safe_load 读取。
4. technical_snapshot.yaml 至少 15 行，且可被 yaml.safe_load 读取。
5. valuation_snapshot.yaml 至少 10 行，且可被 yaml.safe_load 读取。
6. data_layer_bridge_issue_list.csv 至少 1 header + issue rows。
7. integrated_data_layer_readout.md 至少包含多个 Markdown section。
8. 生成物中不得出现 Windows backslash path。
```

## 验收命令

```bash
python -m py_compile $(git ls-files '*.py')
python -m pytest -q tests/test_data_layer_quality_gate.py
python -m pytest -q tests/test_data_layer_bridge_draft.py
python -m pytest -q
```

## 输出

```text
reports/p1_6/DATA_LAYER_DL1_5B_PHYSICAL_FORMATTING_READOUT.md
```

## 验收标准

```text
1. GitHub raw 中 CSV / YAML artifacts 不再显示为单行。
2. DL-1.5B readout 中记录的行数与实际文件一致。
3. accepted TODO 数量不变。
4. 研究结论不变。
5. pytest 全量通过。
```

## 边界

```text
- 不改变研究结论；
- 不接真实 API；
- 不新增数据；
- 不把 accepted_todo 改成 resolved；
- 不隐藏 medium TODO；
- 不覆盖 raw evidence。
```

---

# Next-1 Acceptance Checklist Reconciliation After Master Completion

## 目标

修正 `DATA_LAYER_ACCEPTANCE_CHECKLIST.md` 与最新 master readout 的状态冲突。

## 当前问题

最新 master readout 已显示 DL-5、DL-7 已完成，但 checklist 中可能仍把它们标记为 pending，导致后续 Codex 判断混乱。

## 任务

```text
1. 更新 docs/plans/DATA_LAYER_ACCEPTANCE_CHECKLIST.md。

2. 将以下状态改为 done：
   - DL-0 execution sanity；
   - DL-1 quality state reconciliation；
   - DL-1.5 artifact formatting，如 Next-0 完成后；
   - DL-2 technical / market semantics repair；
   - DL-3 peer snapshot + reconciliation stub；
   - DL-5 stock report bridge draft；
   - DL-7 integrated debug；
   - DATA_LAYER_NEXT_TASKS_MASTER_READOUT produced。

3. 保留以下状态为 pending：
   - official disclosure reconciliation beyond stub；
   - business segment disclosure extraction；
   - R4 publishable stock deep dive gate；
   - R4 stock deep dive v0.1；
   - manual real-service Tushare / Baostock smoke；
   - P2 readiness gate。

4. 新增 “Current True State” 表：
   - engineering_data_layer_bridge: done
   - data_layer_status: accepted_with_todos
   - stock_bridge_status: accepted_with_todos
   - disclosure_reconciliation: pending
   - business_segment_disclosure: pending
   - publishable_r4: blocked
   - p2_readiness: blocked

5. 明确：
   - data-layer bridge 完成不等于 R4 publishable report 完成；
   - fixture peer snapshot 完成不等于真实 API peer data 完成；
   - reconciliation stub 完成不等于 official reconciliation 完成。
```

## 输出

```text
reports/p1_6/DATA_LAYER_CHECKLIST_RECONCILIATION_AFTER_MASTER_READOUT.md
```

## 验收标准

```text
1. checklist 与 master readout 状态一致。
2. DL-5 / DL-7 不再被误标为 pending。
3. official disclosure reconciliation 仍为 pending。
4. R4 publishable stock deep dive 仍为 blocked / pending。
5. P2 readiness 仍为 blocked / not ready。
```

## 边界

```text
- 不进入 P2；
- 不改变 workflow artifacts；
- 不生成新报告；
- 不接真实 API。
```

---

# Next-2 Official Disclosure Reconciliation MVP

## 目标

把结构化财务数据与官方披露表格做第一次最小核对，关闭或降级 DLBR-001 的一部分。

本任务只针对 002837 英维克，不扩股票池。

## 输入

```text
reports/workflow_runs/wf_20260703_data_layer_002837_invic/financial_metric_pack.csv
reports/workflow_runs/wf_20260703_data_layer_002837_invic/evidence_manifest.csv
reports/workflow_runs/wf_20260703_data_layer_002837_invic/source_gap_report.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_stock_report_data_layer_bridge_draft.md
```

如当前 workflow run 中没有足够官方披露文件，则生成 evidence acquisition TODO，不得编造。

## 需要优先核对的官方披露

```text
1. 2025 年年度报告；
2. 最近一期季报或半年报；
3. 已登记的官方公告 / 定期报告；
4. 如已存在 PDF / text / table extraction，优先复用；
5. 如不存在，输出 evidence acquisition TODO。
```

## 输出

```text
reports/workflow_runs/wf_20260703_data_layer_002837_invic/official_financial_reconciliation.csv
reports/workflow_runs/wf_20260703_data_layer_002837_invic/official_financial_reconciliation_readout.md
```

## reconciliation table 字段

```text
metric_name
period
structured_value
official_value
unit
source_structured_evidence_id
official_evidence_id
official_page_or_table_locator
difference
tolerance
reconciliation_status
notes
```

## reconciliation_status 枚举

```text
matched
matched_with_rounding
mismatch
official_missing
structured_missing
needs_manual_review
```

## 优先覆盖字段

至少覆盖 bridge draft 已使用的公司级财务字段：

```text
total_revenue
n_income_attr_p
gross_margin
net_margin
basic_eps
operating_cash_flow
total_assets
total_liabilities
roe
debt_to_asset
```

字段名称可根据当前 metric pack 实际字段做映射，但必须保留原始 metric_name 与 normalized_metric_name。

## 任务

```text
1. 建立 official disclosure reconciliation workflow。
2. 读取 financial_metric_pack.csv。
3. 查找对应 official filing evidence。
4. 如果官方披露已存在 processed table/text：
   - 提取对应指标；
   - 做数值核对；
   - 记录 official evidence locator。
5. 如果官方披露缺失：
   - 写 official_missing；
   - 同时生成 evidence acquisition TODO。
6. 输出 official_financial_reconciliation.csv。
7. 输出 official_financial_reconciliation_readout.md。
8. 更新 source_gap_report.md：
   - DLBR-001 从 reconciliation required 调整为 partial reconciliation completed，或继续标记 pending，并说明原因。
9. 更新 data_layer_quality_report.md / workflow_readout.md 如有必要。
```

## 验收标准

```text
1. 至少覆盖 total_revenue、n_income_attr_p、basic_eps。
2. 每个字段都有 official_evidence_id 或 official_missing。
3. mismatch 不被静默忽略。
4. official_missing 不会被当作 matched。
5. DLBR-001 状态得到更精确表达。
6. 结构化财务数据仍不得自动 promote 为 reported fact。
```

## 边界

```text
- 不自动 promote 为 reported fact；
- 只生成 reconciliation result；
- promote 必须交给 quality-review；
- 不用结构化数据证明液冷收入占比；
- 不把财务三表 reconciliation 和业务分部 reconciliation 混为一谈；
- 不接真实 API，除非用户另行显式要求。
```

## 测试要求

新增或更新测试：

```text
1. official_financial_reconciliation.csv schema 正确。
2. official_missing 不会被判定为 matched。
3. mismatch 会出现在 readout 中。
4. reconciliation result 不会生成 business exposure claim。
5. financial metric 只有在 official matched 后才允许进入 promoted candidate，且仍需 quality-review。
```

## 验收命令

```bash
python -m py_compile $(git ls-files '*.py')
python -m pytest -q tests/test_official_financial_reconciliation.py
python -m pytest -q tests/test_data_layer_quality_gate.py
python -m pytest -q
```

## 输出 readout

```text
reports/p1_6/OFFICIAL_DISCLOSURE_RECONCILIATION_MVP_READOUT.md
```

---

# Next-3 Business Segment Disclosure Extraction MVP

## 目标

补齐样例报告真正需要的业务拆分与细分暴露证据。

当前 data bridge 只能补公司级财务、估值、技术和 peer context，不能证明液冷业务收入占比、液冷毛利率、客户订单、产能和 segment profitability。

## 输入

```text
官方年报 / 半年报 / 季报 / 公告 / 投资者关系记录
reports/workflow_runs/wf_20260703_stock_first_002837_invic/segment_exposure.yaml
reports/workflow_runs/wf_20260703_stock_first_002837_invic/remaining_source_gaps_after_data_layer_bridge.md
```

## 输出

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/business_segment_metric_pack.csv
reports/workflow_runs/wf_20260703_stock_first_002837_invic/business_segment_extraction_readout.md
```

## business_segment_metric_pack.csv 字段

```text
company_id
stock_code
period
segment_name_reported
mapped_internal_segment
metric_name
value
unit
official_evidence_id
page_or_table_locator
mapping_confidence
review_status
notes
```

## review_status 枚举

```text
reviewed_official
needs_manual_review
missing_disclosure
narrative_only
product_line_clue
not_applicable
```

## 液冷相关证据分类

对“液冷”相关表述必须区分：

```text
disclosed_revenue:
  官方直接披露液冷相关收入或可明确归属的分部收入。

disclosed_margin:
  官方直接披露液冷相关毛利率或可明确归属的分部毛利率。

product_line_clue:
  官方披露产品线、解决方案、客户测试、产能建设等，但没有量化收入。

narrative_only:
  仅有战略叙事或行业描述，不能用于收入/利润测算。

missing_disclosure:
  没有可核验披露。
```

## 任务

```text
1. 从英维克官方披露中提取业务分部 / 产品分部表。
2. 尝试识别与液冷、机房温控、机柜温控、数据中心温控相关的披露。
3. 将披露中的业务名称映射到内部 linked_segments。
4. 对每条映射给出 mapping_confidence。
5. 如果只有温控总收入，没有液冷拆分，必须写明口径不等同。
6. 如果只有产品叙事，不得推收入占比。
7. 更新 remaining_source_gaps_after_data_layer_bridge.md。
8. 如有必要，更新 segment_exposure.yaml，但只能写 reviewed evidence 或 TODO。
```

## 验收标准

```text
1. 如果官方披露没有液冷收入占比，继续 MISSING_DISCLOSURE。
2. 如果只有产品叙事，不得推收入占比。
3. 如果有温控/机房/机柜温控收入，但没有液冷拆分，需要标注口径不等同。
4. business_segment_metric_pack.csv 不得由 Tushare/Baostock 直接生成。
5. segment exposure 不得因为 narrative_only 自动升级。
6. 所有业务分部数据必须有 official_evidence_id 或 missing_disclosure。
```

## 边界

```text
- 不用新闻或市场线索证明业务暴露；
- 不用 Tushare/Baostock 证明业务分部；
- 不把客户测试、合作意向、产品线叙事等同于收入；
- 不把订单框架协议等同于收入；
- 不生成买卖建议。
```

## 测试要求

新增或更新测试：

```text
1. business_segment_metric_pack.csv schema 正确。
2. narrative_only 不会生成 revenue_pct。
3. product_line_clue 不会生成 profit_pct。
4. missing_disclosure 继续进入 source_gap_report。
5. reviewed_official 必须有 official_evidence_id。
```

## 验收命令

```bash
python -m py_compile $(git ls-files '*.py')
python -m pytest -q tests/test_business_segment_extraction.py
python -m pytest -q tests/test_segment_exposure_gate.py
python -m pytest -q
```

## 输出 readout

```text
reports/p1_6/BUSINESS_SEGMENT_DISCLOSURE_EXTRACTION_MVP_READOUT.md
```

---

# Next-4 R4 Publishable Stock Deep Dive Gate Definition

## 目标

建立“什么时候可以从 bridge draft 进入发布级个股深度”的制度化质量门。

本任务只定义 gate，不生成正式报告。

## 新增文档

```text
.agents/skills/stock-deep-dive/references/publishable_stock_report_gate.md
```

## gate 输入

```text
stock_report_draft
financial_metric_pack.csv
official_financial_reconciliation.csv
business_segment_metric_pack.csv
valuation_snapshot.yaml
technical_snapshot.yaml
peer_market_snapshot.csv
catalyst_calendar.yaml
risk_counterevidence_pack.md 或等价文件
source_gap_report.md
quality_gate_report.md
```

## R4 publishable stock report 必备条件

```text
1. official financial reconciliation 至少 partial pass；
2. 公司级核心财务指标有 official evidence 或明确 official_missing；
3. business segment metric pack 已生成；
4. 业务分部缺失被明确标记为 MISSING_DISCLOSURE；
5. valuation context 有 source_evidence_id 或 metric_candidate_id；
6. peer context 有 peer_market_snapshot.csv 或 TODO_PEER_DATA；
7. technical snapshot 只作为市场状态观察；
8. 风险和反证清单存在；
9. source gaps 不得隐藏；
10. no-advice gate 通过。
```

## 不允许发布的条件

```text
1. 公司级财务未核对；
2. 分部业务全部 MISSING 且报告仍写确定性业务拆分；
3. 估值没有 source_evidence_id / metric_candidate_id；
4. peer table 全是 TODO 却被写成同业结论；
5. source gaps 被隐藏；
6. 出现买入/卖出/持有；
7. 出现目标价交易建议；
8. technical snapshot 被写成交易指令；
9. Tushare/Baostock 数据被写成业务暴露事实；
10. 管理层表述、券商预测、新闻线索被写成事实。
```

## 输出状态

```text
publishable_ready
publishable_ready_with_disclosure_todos
bridge_only
blocked
```

## 状态解释

```text
publishable_ready:
  所有关键财务、业务分部、估值、风险、source gaps 均满足发布级要求。

publishable_ready_with_disclosure_todos:
  报告可作为研究草案发布给内部使用，但必须显式保留披露缺口。

bridge_only:
  只能作为 data-layer bridge draft，不应被当作正式个股深度报告。

blocked:
  存在 high issue、证据链断裂、source gap 隐藏、no-advice 违规等问题。
```

## 输出 readout

```text
reports/p1_6/R4_PUBLISHABLE_STOCK_REPORT_GATE_READOUT.md
```

## 验收标准

```text
1. gate 文档存在。
2. stock-deep-dive/SKILL.md 引用该 gate。
3. quality-review/SKILL.md 或 references 中能够识别 R4 publishable gate。
4. gate 明确区分 bridge_only 与 publishable_ready。
5. gate 不放松 no-advice。
```

---

# Next-5 R4 Stock Report Draft v0.1

## 前置条件

必须完成：

```text
Next-0 Artifact Physical Line Formatting
Next-1 Checklist Reconciliation
Next-2 Official Disclosure Reconciliation MVP 至少 partial pass
Next-4 R4 Publishable Stock Deep Dive Gate Definition
```

建议完成：

```text
Next-3 Business Segment Disclosure Extraction MVP
```

如果 Next-3 未完成，R4 draft 必须保留 `MISSING_DISCLOSURE`，不得编写业务拆分数据。

## 目标

生成第一版比 bridge 更接近正式报告的 R4 stock deep dive draft，但仍不要求达到样例报告最终标准。

## 输出

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_stock_deep_dive_v0_1.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_quality_gate_report.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_source_gap_report.md
```

## 章节要求

```text
1. Metadata
2. 一句话结论：事实 / 推断 / 关键假设 / 最大风险
3. 公司财务质量
4. 业务拆分
5. 细分暴露
6. 估值上下文
7. 技术/市场状态观察
8. 催化剂
9. 风险与反证
10. Source gaps
11. 跟踪清单
```

## 章节边界

### 1. Metadata

必须包含：

```text
company_id
stock_code
company_name
report_date
workflow_run_id
evidence_snapshot
data_layer_status
quality_status
linked_segments
```

### 2. 一句话结论

必须拆成：

```text
事实
推断
关键假设
最大风险
```

不得写：

```text
买入
卖出
持有
目标价交易建议
仓位建议
```

### 3. 公司财务质量

来源：

```text
financial_metric_pack.csv
official_financial_reconciliation.csv
```

要求：

```text
1. 公司级收入、利润、现金流、资产负债、ROE 等指标必须有 official reconciliation 状态。
2. 未核对指标必须标注 metric_candidate 或 needs_manual_review。
3. 不得把公司级财务指标推导为液冷业务收入。
```

### 4. 业务拆分

来源：

```text
business_segment_metric_pack.csv
官方披露
```

要求：

```text
1. 有官方披露则写业务分部。
2. 没有液冷拆分则写 MISSING_DISCLOSURE。
3. 只有产品线叙事则写 product_line_clue 或 narrative_only。
```

### 5. 细分暴露

来源：

```text
segment_exposure.yaml
business_segment_metric_pack.csv
official evidence
```

要求：

```text
1. 只写证据支持的 exposure。
2. revenue_pct / profit_pct 缺失时必须写 MISSING_DISCLOSURE。
3. 不得用市场叙事自动提高 exposure_score。
```

### 6. 估值上下文

来源：

```text
valuation_snapshot.yaml
peer_market_snapshot.csv
```

要求：

```text
1. 只写估值上下文，不写投资结论。
2. pe_forward 缺失继续 TODO_MARKET_DATA。
3. peer table 不得生成推荐/评级。
```

### 7. 技术/市场状态观察

来源：

```text
technical_snapshot.yaml
```

要求：

```text
1. 只作为市场状态观察。
2. 不写交易信号。
3. 不写突破/支撑后的交易建议。
```

### 8. 催化剂

来源：

```text
catalyst_calendar.yaml
公告/定期报告窗口
```

要求：

```text
1. 只写事件窗口和待验证事项。
2. 不写确定性行情判断。
```

### 9. 风险与反证

必须包含：

```text
1. 证据缺口风险；
2. 业务拆分缺失风险；
3. 行业景气不及预期；
4. 估值上下文误读风险；
5. 数据源口径差异；
6. 反证清单。
```

### 10. Source gaps

必须原样暴露：

```text
R4_source_gap_report.md
remaining_source_gaps_after_data_layer_bridge.md
```

### 11. 跟踪清单

必须以 TODO / watch item 形式呈现，不得写交易计划。

## 验收标准

```text
1. R4_stock_deep_dive_v0_1.md 存在。
2. R4_quality_gate_report.md 存在。
3. R4_source_gap_report.md 存在。
4. 报告中财务/估值/技术/peer 不再空白。
5. 业务分部缺失被明确标注。
6. source gaps 被完整暴露。
7. no-advice gate 通过。
8. R4 publishable gate 输出 bridge_only / publishable_ready_with_disclosure_todos / blocked 等状态。
```

## 边界

```text
- 不写买入/卖出/持有；
- 不写交易目标价；
- 可以写估值上下文，但不得写交易建议；
- 可以写关键假设，但必须标注 hypothesis；
- 可以写情景，但必须标注 scenario；
- 不要求达到样例文章风格；
- 不隐藏 source gaps。
```

## 验收命令

```bash
python -m py_compile $(git ls-files '*.py')
python -m pytest -q tests/test_r4_publishable_stock_report_gate.py
python -m pytest -q tests/test_stock_report_bridge_draft.py
python -m pytest -q
```

## 输出 readout

```text
reports/p1_6/R4_STOCK_REPORT_DRAFT_V0_1_READOUT.md
```

---

# Next-6 Manual Live Smoke Preparation, Not Execution

## 目标

为未来真实 Tushare / Baostock smoke test 准备 playbook，但本任务不执行真实 API。

## 新增文档

```text
docs/playbooks/MANUAL_LIVE_DATA_SMOKE_PLAYBOOK.md
```

## playbook 必须包含

```text
1. 需要哪些环境变量；
2. 如何确认不会提交 token；
3. 如何设置临时 output dir；
4. 如何跑 Tushare daily_basic smoke；
5. 如何跑 Tushare income / balancesheet / cashflow smoke；
6. 如何跑 Baostock K-line smoke；
7. 如何跑 Baostock financial smoke；
8. 如何检查 raw snapshot / manifest / metric_candidates；
9. 如何删除或隔离临时文件；
10. 如何确认 git status 干净；
11. smoke test 失败时如何回滚；
12. 哪些输出不能提交。
```

## 安全要求

```text
1. 不在 CI 中运行真实 API。
2. 不提交 token。
3. 不提交临时 live raw response，除非经过脱敏和人工确认。
4. 不把 live smoke 结果直接用于报告。
5. live smoke 只验证 adapter execution path。
```

## 输出 readout

```text
reports/p1_6/MANUAL_LIVE_DATA_SMOKE_PLAYBOOK_READOUT.md
```

## 验收标准

```text
1. playbook 存在。
2. playbook 明确 token 安全要求。
3. playbook 明确 git status 检查。
4. playbook 明确不自动接入报告。
```

---

# Next-7 P2 Readiness Precheck, Not Gate

## 目标

做一次 P2 readiness 预检查，但不正式进入 P2。

## 输出

```text
reports/p1_6/P2_READINESS_PRECHECK_AFTER_DATA_LAYER.md
```

## 检查项

```text
1. data layer bridge 是否完成；
2. artifact physical formatting 是否完成；
3. checklist 是否对齐；
4. official financial reconciliation 是否完成；
5. business segment disclosure extraction 是否有结果；
6. R4 stock report gate 是否通过；
7. R4_stock_deep_dive_v0_1.md 是否生成；
8. high issues 是否为 0；
9. medium TODO 是否阻塞 P2；
10. no-advice / scorecard 是否仍有误解风险；
11. segment-stock interlock 回写是否完成；
12. 是否允许 limited P2 pilot。
```

## 当前预期结论

```text
not_ready_for_p2
```

## 预期原因

```text
1. official disclosure reconciliation 尚未完成或仅 partial；
2. business segment exposure 仍未充分补齐；
3. R4 publishable stock deep dive 尚未达到 publishable_ready；
4. segment-stock interlock 仍需进一步验证；
5. manual live smoke 不是 P2 必需，但仍可选。
```

## 验收标准

```text
1. precheck 明确不是 P2 gate。
2. precheck 不得给出进入 P2 的结论，除非所有必要项确实完成。
3. precheck 必须列出阻塞项和下一步 owner。
```

---

# 3. 总体验收门

本轮全部完成后，应满足：

```text
1. data-layer artifacts 物理格式稳定；
2. checklist 与 master readout 状态一致；
3. official_financial_reconciliation.csv 存在；
4. business_segment_metric_pack.csv 存在或明确 official_missing；
5. publishable_stock_report_gate.md 存在；
6. R4_stock_deep_dive_v0_1.md 存在；
7. R4_quality_gate_report.md 存在；
8. R4_source_gap_report.md 存在；
9. manual live smoke playbook 存在；
10. P2 readiness precheck 存在；
11. pytest 全量通过；
12. CI 通过；
13. 仍不进入 P2；
14. 仍不生成买入/卖出/持有建议；
15. structured data 仍不直接证明业务暴露。
```

## 最终验收命令

```bash
python -m py_compile $(git ls-files '*.py')
python -m pytest -q
```

## 最终 readout

完成全部任务后新增：

```text
reports/p1_6/R4_READINESS_NEXT_TASKS_MASTER_READOUT.md
```

该 readout 必须包含：

```text
1. 已完成任务列表；
2. 未完成任务列表；
3. 当前 data-layer workflow status；
4. 当前 stock-first workflow status；
5. 当前 R4 publishable gate status；
6. high / medium / low issue 数量；
7. accepted TODO 数量；
8. official reconciliation 状态；
9. business segment extraction 状态；
10. 是否允许 manual live smoke；
11. 是否允许 R4 publishable stock deep dive；
12. 是否允许 P2 readiness gate。
```

---

# 4. 暂停条件

出现以下任一情况，立即暂停：

```text
1. py_compile 失败；
2. pytest 失败且原因不明确；
3. CI 失败；
4. artifact 仍单行化且测试未发现；
5. token 被写入 tracked artifact；
6. Tushare / Baostock 数据被直接 promote 为 business exposure fact；
7. market / technical snapshot 被写成交易建议；
8. peer valuation 被写成买入/卖出/持有；
9. accepted TODO 被隐藏；
10. raw snapshot 被覆盖；
11. official reconciliation 没有证据却标记 matched；
12. business segment narrative_only 被写成 disclosed_revenue；
13. stock-deep-dive 绕过 R4 publishable gate；
14. P2 precheck 被误写成 P2 gate。
```

---

# 5. 推荐给 Codex 的执行指令

```text
请按照 docs/plans/DATA_LAYER_R4_READINESS_NEXT_TASKS.md 执行下一阶段任务。

优先执行顺序：
1. Next-0 Reopen DL-1.5 Artifact Physical Line Formatting
2. Next-1 Acceptance Checklist Reconciliation After Master Completion
3. Next-2 Official Disclosure Reconciliation MVP
4. Next-3 Business Segment Disclosure Extraction MVP
5. Next-4 R4 Publishable Stock Deep Dive Gate Definition
6. Next-5 R4 Stock Report Draft v0.1
7. Next-6 Manual Live Smoke Preparation, Not Execution
8. Next-7 P2 Readiness Precheck, Not Gate

要求：
- 每完成一个 Next 子任务，生成对应 reports/p1_6/readout；
- 每个子任务都运行 py_compile 和 pytest；
- 不进入 P2；
- 不生成买入/卖出/持有建议；
- 不把 technical / valuation / peer context 写成交易结论；
- 不把 Tushare / Baostock structured data 直接提升为 business exposure fact；
- 不隐藏 accepted TODO；
- 不覆盖 raw evidence；
- 不执行真实 API，除非用户显式要求且运行 manual live smoke playbook；
- 如果出现暂停条件，立即停止并报告。
```
