# Data Layer Next Tasks Master Plan

> 本文件用于承接 DL-1 之后的数据层建设任务。
> 当前阶段仍属于 P1.6，不进入 P2，不生成买入/卖出/持有建议，不接自动交易，不把结构化数据直接升级为业务暴露事实。

## 0. 当前状态

截至 DL-1 完成后，数据层建设状态如下：

```text
DL-0 Execution Sanity Check: PASS
DL-1 Quality State Reconciliation: PASS

当前 data-layer-only workflow:
reports/workflow_runs/wf_20260703_data_layer_002837_invic/

当前状态:
accepted_with_todos

blocking issues:
0

accepted TODO:
3
```

当前已经完成：

```text
1. 数据层已被定义为 evidence-ingest 的子系统，而不是平级 data skill。
2. docs/workflows/DATA_LAYER_WORKFLOW.md 已成为数据层事实源。
3. evidence-ingest 已接入 source adapter / structured data / market context / data quality gate references。
4. source_registry.yaml 已纳入 Tushare、Baostock、Tencent、mootdx、Eastmoney、THS 等数据源分层。
5. fixture-based data-layer run 已能生成 financial / valuation / technical 等初步 data packs。
6. quality-review 已加入 G10 Data Layer Pack Gate。
7. stock-deep-dive 已能识别 data-layer packs 作为输入，但不得把它们用作业务暴露事实。
8. DL-0 已验证 Python / YAML / TOML / CI 可执行。
9. DL-1 已修正 data layer quality status，从 accepted 调整为 accepted_with_todos。
```

当前仍未完成：

```text
1. 部分 data-layer artifacts 的格式可读性仍需规范化。
2. technical snapshot 中部分缺失标签仍误用 MISSING_DISCLOSURE。
3. peer_market_snapshot.csv 尚未生成。
4. structured financial metrics 尚未完成 official disclosure reconciliation。
5. Tushare / Baostock 仍处于 fixture / dry-run / blocked wrapper 阶段，尚未进入 live adapter hardening。
6. stock-deep-dive 尚未真正基于 data-layer packs 生成 R4 bridge draft。
7. data layer acceptance checklist 尚未同步最新状态。
```

## 1. 总体目标

本轮总目标不是扩展更多数据源，而是让数据层具备以下能力：

```text
1. 产物格式稳定、可读、可 diff、可被下游消费；
2. market / technical / valuation / financial pack 的语义准确；
3. peer snapshot 和 official disclosure reconciliation stub 补齐；
4. data-layer packs 能被 stock-deep-dive 安全消费；
5. 所有 TODO 明确暴露，不被 quality gate 隐藏；
6. 为后续 Tushare / Baostock live adapter hardening 做准备。
```

## 2. 总执行顺序

推荐按以下顺序执行：

```text
DL-1.5  Artifact Formatting Normalization
DL-2    Technical / Market Pack Semantics Repair
DL-3    Peer Snapshot + Official Disclosure Reconciliation Stub
DL-6    Data Layer Acceptance Checklist Update
DL-5    Stock Report Readiness Bridge Draft
DL-7    Stock-first Data-layer Integrated Debug
DL-4    Tushare / Baostock Live Adapter Hardening
```

说明：

```text
DL-4 虽然编号靠前提出过，但建议放后执行。
原因是：在真实 API 接入之前，必须先确保 artifact 格式、语义、质量状态、下游消费桥接都稳定。
```

---

# DL-1.5 Artifact Formatting Normalization

## 目标

让 data-layer artifacts 成为人类可审阅、机器可解析、Git diff 友好的文件。

当前部分生成物可能存在单行化、flow-style YAML、CSV 行数异常、Windows path 等问题。本任务只修格式，不改变研究结论。

## 需要检查的文件

```text
reports/workflow_runs/wf_20260703_data_layer_002837_invic/data_layer_quality_report.md
reports/workflow_runs/wf_20260703_data_layer_002837_invic/data_layer_issue_list.csv
reports/workflow_runs/wf_20260703_data_layer_002837_invic/open_todos.csv
reports/workflow_runs/wf_20260703_data_layer_002837_invic/source_gap_report.md
reports/workflow_runs/wf_20260703_data_layer_002837_invic/workflow_readout.md
reports/workflow_runs/wf_20260703_data_layer_002837_invic/workflow_state.yaml
reports/workflow_runs/wf_20260703_data_layer_002837_invic/valuation_snapshot.yaml
reports/workflow_runs/wf_20260703_data_layer_002837_invic/technical_snapshot.yaml
```

## 任务

```text
1. 检查上述文件的物理行数和可读性。
2. Markdown 文件必须使用清晰标题、段落和表格。
3. CSV 文件必须是 header + 每条 issue/todo 一行。
4. YAML 文件必须使用 block style，不使用难以阅读的 flow style。
5. 所有 artifact path 使用 repo-relative POSIX path。
6. 不允许无意出现 reports\workflow_runs\... 这类 Windows path。
7. 修正相关生成器，避免下次 run 再次生成单行文件。
8. 重新生成当前 workflow run 的格式化 artifacts。
```

## 测试要求

新增或更新测试：

```text
1. data_layer_quality_report.md 至少包含：
   - 标题
   - Summary
   - Blocking Issues
   - Accepted TODOs

2. data_layer_issue_list.csv 行数应等于：
   1 header + issue rows

3. workflow_state.yaml / valuation_snapshot.yaml / technical_snapshot.yaml 可被 yaml.safe_load 读取。

4. 生成物中不应出现 Windows backslash path，除非是在专门说明 Windows 示例。
```

## 验收命令

```bash
python -m py_compile $(git ls-files '*.py')
python -m pytest -q tests/test_data_layer_quality_gate.py
python -m pytest -q
```

## 输出

```text
reports/p1_6/DATA_LAYER_DL1_5_ARTIFACT_FORMATTING_READOUT.md
```

## 验收标准

```text
1. data_layer_quality_report.md 是多行 Markdown。
2. data_layer_issue_list.csv 至少 4 行：header + 3 issues。
3. workflow_state.yaml 是可读 block YAML。
4. valuation_snapshot.yaml / technical_snapshot.yaml 是可读 block YAML。
5. pytest 全量通过。
```

## 边界

```text
- 不改变研究结论；
- 不接真实 API；
- 不新增数据；
- 不把 accepted_todo 改成 resolved；
- 不隐藏 medium TODO。
```

---

# DL-2 Technical / Market Pack Semantics Repair

## 目标

修正 technical / market pack 中错误的缺失标签和路径问题。

当前问题：

```text
MA20 / MA60 / pct_chg_20d / pct_chg_60d / weekly MA 缺失，
是因为 fixture 行情窗口不足，
不应标为 MISSING_DISCLOSURE。
```

正确标签应为：

```text
INSUFFICIENT_PRICE_WINDOW
或
TODO_MARKET_DATA
```

## 任务

```text
1. 修改 technical snapshot builder。

2. 当 MA20 / MA60 / pct_chg_20d / pct_chg_60d / weekly MA 因行情窗口不足而缺失时：
   - 使用 INSUFFICIENT_PRICE_WINDOW；
   - 或使用 TODO_MARKET_DATA；
   - 不得使用 MISSING_DISCLOSURE。

3. technical snapshot 中所有 source path 改为 repo-relative POSIX path。

4. notes 必须保留：
   "Technical snapshot is a market-state observation, not trading advice."

5. 修改 source_gap_report 生成逻辑：
   - fixture 行情窗口不足时，写 INSUFFICIENT_PRICE_WINDOW；
   - 不再写 “MA20/MA60 remain MISSING_DISCLOSURE because fixture window is short”。

6. 重新生成：
   - technical_snapshot.yaml
   - source_gap_report.md
   - data_layer_quality_report.md 如有必要
   - workflow_readout.md 如有必要
```

## 测试要求

新增或更新测试：

```text
1. fixture price series 行数不足 20/60 日时，缺失原因必须是 INSUFFICIENT_PRICE_WINDOW。
2. technical_snapshot.yaml 不得出现 MISSING_DISCLOSURE。
3. technical_snapshot.yaml 不得出现反斜杠路径。
4. technical_snapshot.yaml 必须保留 no-advice note。
```

## 验收命令

```bash
python -m py_compile $(git ls-files '*.py')
python -m pytest -q tests/test_technical_snapshot_builder.py
python -m pytest -q tests/test_data_layer_quality_gate.py
python -m pytest -q
```

## 输出

```text
reports/p1_6/DATA_LAYER_DL2_TECHNICAL_MARKET_SEMANTICS_READOUT.md
```

## 验收标准

```text
1. technical_snapshot.yaml 中不出现 MISSING_DISCLOSURE。
2. source_gap_report.md 中不出现 “fixture window is short → MISSING_DISCLOSURE”。
3. technical 缺失项使用 INSUFFICIENT_PRICE_WINDOW 或 TODO_MARKET_DATA。
4. 所有路径为 reports/workflow_runs/... 格式。
5. no-advice note 保留。
```

## 边界

```text
- 不根据技术指标生成交易建议；
- 不新增 buy/sell/hold；
- 不把 technical snapshot 作为公司基本面事实；
- 不接真实行情 API。
```

---

# DL-3 Peer Snapshot + Official Disclosure Reconciliation Stub

## 目标

补齐当前两个 medium TODO 的可见 artifact：

```text
1. peer_market_snapshot.csv 未生成；
2. structured financial metrics 仍需 official disclosure reconciliation。
```

本任务只做 fixture / stub，不接真实 API，不做自动年报解析。

---

## 目标 A：peer_market_snapshot.csv

### 任务

```text
1. 新增 fixture-only peer_market_snapshot builder。
2. 支持从配置或 data_request_plan.yaml 读取 peer list。
3. 输出 peer_market_snapshot.csv。
4. 第一版不接真实 API。
```

### 输出路径

```text
reports/workflow_runs/wf_20260703_data_layer_002837_invic/peer_market_snapshot.csv
```

### 建议字段

```text
as_of_date
stock_code
company_id
company_name
peer_group
price
market_cap
pe_ttm
pe_forward
pb
ps
revenue_ttm
net_profit_ttm
source_name
source_evidence_id
api_params_hash
missing_fields
notes
```

### 规则

```text
1. 如果 peer 的 pe_forward 缺失，写 TODO_MARKET_DATA，不得空白。
2. peer valuation 只能作为估值上下文，不能作为投资建议。
3. peer table 不能生成 buy/sell/hold。
```

---

## 目标 B：official_disclosure_reconciliation_stub

### 任务

新增以下二选一：

```text
reports/workflow_runs/wf_20260703_data_layer_002837_invic/official_disclosure_reconciliation_stub.md
```

或：

```text
reports/workflow_runs/wf_20260703_data_layer_002837_invic/reconciliation_issue.csv
```

### stub 必须说明

```text
1. 哪些 structured financial metrics 还没有和年报/季报核对；
2. 哪些指标可以作为 metric_candidate；
3. 哪些指标不得作为 business exposure fact；
4. 需要补哪些官方披露文件；
5. 谁负责后续 reconciliation；
6. 后续完成 reconciliation 前，不得 promote 为 reported fact。
```

---

## 目标 C：状态更新

### 任务

```text
1. 更新 source_gap_report.md：
   - 如果 peer snapshot 已生成，DL-GAP-001 改为 resolved 或 lowered_to_low_todo；
   - DL-GAP-002 保留为 accepted_todo，直到真正完成官方披露 reconciliation；
   - DL-GAP-003 根据 pe_forward 是否仍缺失决定是否保留 low todo。

2. 更新：
   - data_layer_quality_report.md
   - data_layer_issue_list.csv
   - workflow_readout.md
   - open_todos.csv
   - workflow_state.yaml

3. workflow_state.yaml artifacts 列表加入：
   - peer_market_snapshot.csv
   - official_disclosure_reconciliation_stub.md
     或 reconciliation_issue.csv
```

## 测试要求

新增或更新测试：

```text
1. peer_market_snapshot.csv 存在且 schema 正确。
2. peer snapshot 缺字段不得被静默省略。
3. reconciliation stub 存在时，structured metrics 仍保持 metric-only。
4. peer snapshot 不生成买卖建议。
5. data_layer_quality_report 能正确反映 DL-GAP-001 的状态变化。
```

## 验收命令

```bash
python -m py_compile $(git ls-files '*.py')
python -m pytest -q tests/test_peer_market_snapshot_builder.py
python -m pytest -q tests/test_data_layer_quality_gate.py
python -m pytest -q
```

## 输出

```text
reports/p1_6/DATA_LAYER_DL3_PEER_AND_RECONCILIATION_READOUT.md
```

## 验收标准

```text
1. peer_market_snapshot.csv 存在。
2. official_disclosure_reconciliation_stub.md 或 reconciliation_issue.csv 存在。
3. DL-GAP-001 不再是 artifact missing。
4. DL-GAP-002 仍保留为 accepted_todo，除非真正完成官方披露核对。
5. stock-deep-dive 可以看到 peer pack，但必须保留 disclosure reconciliation TODO。
```

## 边界

```text
- 不接真实 API；
- 不自动 promote metric candidates；
- 不把 peer valuation 变成推荐/评级；
- 不把 Tushare/Baostock 数据写成业务暴露事实。
```

---

# DL-6 Data Layer Acceptance Checklist Update

## 目标

同步计划文档和真实状态，避免 checklist 与 workflow readout 脱节。

## 任务

```text
1. 更新 docs/plans/DATA_LAYER_ACCEPTANCE_CHECKLIST.md。

2. 将已完成项标记为 done：
   - DL-0 execution sanity；
   - DL-1 quality state reconciliation；
   - data-layer workflow facts source；
   - evidence-ingest references；
   - stock-deep-dive / quality-review bridge rules。

3. 将未完成项标记为 pending：
   - DL-1.5 artifact formatting；
   - DL-2 technical semantics；
   - DL-3 peer snapshot；
   - official disclosure reconciliation；
   - DL-4 live adapter hardening；
   - DL-5 stock report bridge draft；
   - DL-7 integrated debug。

4. 增加 Current State 表，字段包括：
   - item
   - status
   - blocker
   - accepted_todo
   - next_owner_skill
   - next_artifact
```

## 输出

```text
reports/p1_6/DATA_LAYER_ACCEPTANCE_CHECKLIST_UPDATE_READOUT.md
```

## 验收标准

```text
1. checklist 与 DL-0 / DL-1 readout 状态一致。
2. 未完成项不会被误标为 done。
3. checklist 能告诉下一步由哪个 skill 或模块负责。
```

---

# DL-5 Stock Report Readiness Bridge Draft

## 执行前置条件

执行 DL-5 前，建议先完成：

```text
DL-1.5
DL-2
DL-3
DL-6
```

如果 DL-3 未完成，则 DL-5 必须保留：

```text
TODO_PEER_DATA
TODO_DISCLOSURE_RECONCILIATION
```

## 目标

让 data-layer packs 真正进入 stock-deep-dive，但只生成 R4 bridge draft，不追求一次达到样例报告标准。

## 输入

```text
reports/workflow_runs/wf_20260703_data_layer_002837_invic/financial_metric_pack.csv
reports/workflow_runs/wf_20260703_data_layer_002837_invic/valuation_snapshot.yaml
reports/workflow_runs/wf_20260703_data_layer_002837_invic/technical_snapshot.yaml
reports/workflow_runs/wf_20260703_data_layer_002837_invic/peer_market_snapshot.csv
reports/workflow_runs/wf_20260703_data_layer_002837_invic/source_gap_report.md
reports/workflow_runs/wf_20260703_data_layer_002837_invic/data_layer_quality_report.md
```

## 输出

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_stock_report_data_layer_bridge_draft.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/data_layer_bridge_issue_list.csv
reports/workflow_runs/wf_20260703_stock_first_002837_invic/data_layer_bridge_readout.md
```

## 报告只补以下部分

```text
1. 财务质量表；
2. 估值上下文；
3. 技术/市场状态观察；
4. peer valuation table 或 TODO_PEER_DATA；
5. source gaps；
6. 哪些指标仍不能写成业务暴露事实；
7. 哪些业务暴露仍必须回到官方披露。
```

## 验收标准

```text
1. 报告里财务/估值/技术部分不再空白。
2. 每个 market / financial 指标都有 evidence_id 或 metric_candidate_id。
3. source_gap_report 中的 TODO 被原样暴露。
4. quality-review G10 通过。
5. 不出现买入/卖出/持有。
6. 不出现目标价交易建议。
```

## 边界

```text
- 不写买入/卖出/持有；
- 不写目标价交易建议；
- 不把 valuation snapshot 当成投资结论；
- 不把 technical snapshot 当成交易信号；
- 不把 structured financial metrics 当成业务暴露事实；
- 不要求达到样例文章风格。
```

---

# DL-7 Stock-first Data-layer Integrated Debug

## 执行前置条件

建议在 DL-5 之后执行。

## 目标

证明 data-layer-only run 可以被 stock-first workflow 稳定消费。

## 流程

```text
1. research-orchestrator 读取 data-layer run 状态。
2. stock-deep-dive 消费 data-layer packs。
3. quality-review 检查：
   - G1 Evidence Gate
   - G2 Claim Gate
   - G3 Metric Gate
   - G6 Exposure Gate
   - G7 Stock Report Gate
   - G8 Backflow Gate
   - G9 No Advice Gate
   - G10 Data Layer Pack Gate
4. 生成 integrated workflow readout。
5. 明确哪些 TODO 进入下一轮 disclosure research。
```

## 输出

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/integrated_data_layer_readout.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/quality_gate_report_after_data_layer_bridge.md
reports/workflow_runs/wf_20260703_stock_first_002837_invic/remaining_source_gaps_after_data_layer_bridge.md
```

## 验收标准

```text
1. stock-first workflow 能读取 data-layer run。
2. G10 Data Layer Pack Gate 通过或 accepted_with_todos。
3. accepted TODO 被保留在 integrated readout。
4. 没有把 market / valuation / technical pack 写成交易建议。
5. 没有把 structured data 写成 business exposure fact。
```

## 边界

```text
- 不进入 P2；
- 不生成正式投资建议；
- 不做真实交易信号；
- 不隐藏 accepted TODO。
```

---

# DL-4 Tushare / Baostock Live Adapter Hardening

## 执行时机

建议放在 DL-1.5、DL-2、DL-3、DL-5、DL-7 之后。

原因：

```text
真实 API 接入前，应先确保 fixture artifacts、质量门、下游消费桥接全部稳定。
```

## 目标

在 fixture mode 稳定基础上，为真实 API 接入做 hardening。live mode 默认不进入 CI。

---

## Tushare 任务

```text
1. 保留 fixture mode。
2. 保留 dry-run no-token blocked mode。
3. 新增 live mode：
   - 必须显式传入 --mode live 或 --allow-network；
   - 必须读取 TUSHARE_TOKEN 环境变量；
   - token 不得进入 raw snapshot、run log、manifest、error log。
4. live 输出必须包含：
   - raw API response snapshot；
   - processed normalized table；
   - evidence_manifest row；
   - metric_candidates draft；
   - api_params_hash；
   - retrieved_at；
   - license_note。
```

## Tushare 首批接口

```text
stock_basic
income
balancesheet
cashflow
fina_indicator
fina_mainbz
daily_basic
```

## Baostock 任务

```text
1. 保留 fixture mode。
2. package 不存在时不失败，进入 BLOCKED 或 fixture mode。
3. live mode 必须 login → query → logout。
4. login/query failure 必须写 run log。
5. K 线字段必须记录：
   - frequency
   - adjustflag
   - date range
   - source evidence id
```

## Baostock 首批接口

```text
query_history_k_data_plus
query_profit_data
query_balance_data
query_cash_flow_data
query_dupont_data
```

## 测试要求

```text
1. 无 token / 无 baostock package 环境下 pytest 必须通过。
2. live tests 默认 skip。
3. 有环境变量时可手动 smoke test：
   - TUSHARE_TOKEN
   - ENABLE_LIVE_DATA_TESTS=1
4. 新增 token leak scan。
```

## 输出

```text
reports/p1_6/DATA_LAYER_DL4_ADAPTER_HARDENING_READOUT.md
```

## 验收标准

```text
1. CI 在无 token 环境下通过。
2. fixture mode 继续通过。
3. live mode 需要显式开启。
4. 所有 live / dry-run 输出仍走 evidence-ingest 契约。
5. token 不出现在任何 tracked artifact 中。
```

## 边界

```text
- live API 不直接进入报告；
- live API 只写 evidence / metric candidates / run log；
- 不生成业务 exposure claim；
- 不提交 token；
- 不覆盖 raw snapshots。
```

---

# 3. 总体验收门

本轮所有任务完成后，应满足：

```text
1. data-layer artifacts 格式稳定；
2. technical / market pack 缺失标签语义正确；
3. peer_market_snapshot.csv 已存在；
4. official disclosure reconciliation stub 已存在；
5. data_layer_quality_report 状态准确；
6. source_gap_report 与 open_todos 不冲突；
7. stock-deep-dive 能消费 data-layer packs；
8. quality-review G10 可审查 data-layer packs；
9. data-layer acceptance checklist 已更新；
10. pytest 全量通过；
11. CI 通过；
12. 仍未进入 P2；
13. 仍未生成买卖建议；
14. structured snapshots 仍未被提升为业务暴露事实。
```

## 最终验收命令

```bash
python -m py_compile $(git ls-files '*.py')
python -m pytest -q
```

## 最终 readout

完成本轮所有任务后，新增：

```text
reports/p1_6/DATA_LAYER_NEXT_TASKS_MASTER_READOUT.md
```

该 readout 必须包含：

```text
1. 已完成任务列表；
2. 未完成任务列表；
3. 当前 data-layer workflow status；
4. 当前 stock-first bridge status；
5. high / medium / low issue 数量；
6. accepted TODO 数量；
7. 是否允许进入 live adapter hardening；
8. 是否允许进入 R4 publishable stock deep dive；
9. 是否允许进入 P2 readiness gate。
```

---

# 4. 暂停条件

出现以下任一情况，立即暂停，不继续后续任务：

```text
1. py_compile 失败；
2. pytest 失败且原因不明确；
3. CI 失败；
4. token 被写入 tracked artifact；
5. Tushare / Baostock 数据被直接 promote 为 business exposure fact；
6. market / technical snapshot 被写成交易建议；
7. peer valuation 被写成买入/卖出/持有；
8. accepted TODO 被隐藏；
9. raw snapshot 被覆盖；
10. evidence_manifest 与 source_gap_report / workflow_readout 不一致；
11. stock-deep-dive 绕过 data_layer_quality_report 消费 data packs。
```

---

# 5. 给 Codex 的推荐执行指令

可以直接把以下内容交给 Codex：

```text
请按照 docs/plans/DATA_LAYER_NEXT_TASKS_MASTER_PLAN.md 执行下一阶段数据层建设。

优先执行顺序：
1. DL-1.5 Artifact Formatting Normalization
2. DL-2 Technical / Market Pack Semantics Repair
3. DL-3 Peer Snapshot + Official Disclosure Reconciliation Stub
4. DL-6 Data Layer Acceptance Checklist Update
5. DL-5 Stock Report Readiness Bridge Draft
6. DL-7 Stock-first Data-layer Integrated Debug
7. DL-4 Tushare / Baostock Live Adapter Hardening

要求：
- 每完成一个 DL 子任务，生成对应 reports/p1_6/readout；
- 每个子任务都运行 py_compile 和 pytest；
- 不接真实 API，除非执行到 DL-4 且显式开启；
- 不生成买入/卖出/持有建议；
- 不把 structured snapshots 直接提升为业务暴露事实；
- 不隐藏 accepted TODO；
- 不覆盖 raw evidence；
- 如果出现暂停条件，立即停止并报告。
```
