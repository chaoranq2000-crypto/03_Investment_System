# Data Layer Codex Execution Plan

> 本计划列出适合 Codex 在仓库中执行、编码、调试和测试的任务。本补丁包不直接完成这些编程工作。

## Phase DL-A: 文档合并与路由更新

### Task DL-A1: 合并数据层文档

输入：

```text
proposed_files/docs/workflows/DATA_LAYER_WORKFLOW.md
proposed_files/.agents/skills/evidence-ingest/references/*.md
proposed_files/.agents/skills/evidence-ingest/assets/*.yaml|*.md
proposed_files/docs/adr/ADR_0002_*.md
```

动作：

```text
1. 按 repo 相对路径复制文档。
2. 检查是否已有同名文件；若有，先 diff 再合并。
3. 不修改 Python 代码。
```

验收：

```text
rg "Data Layer Workflow" docs .agents/skills/evidence-ingest
rg "structured_data_metric_only" .agents/skills/evidence-ingest docs
```

### Task DL-A2: 更新 evidence-ingest/SKILL.md references

动作：把新参考文件加入 Required references：

```text
references/source_adapter_matrix.md
references/structured_data_adapter_contract.md
references/market_context_snapshot_contract.md
references/data_layer_quality_gate.md
```

验收：

```text
rg "source_adapter_matrix|structured_data_adapter_contract|market_context_snapshot_contract|data_layer_quality_gate" .agents/skills/evidence-ingest/SKILL.md
```

### Task DL-A3: source registry overlay review

动作：

```text
1. 读取 config/data_source_registry_overlay.yaml。
2. 判断哪些条目应合并到 config/source_registry.yaml。
3. 保留当前已存在的 cninfo/sse/szse/bse/tushare/baostock 基础条目。
4. 添加 tencent_finance/mootdx/eastmoney_push2/ths 等 market context entries。
5. 不提高 D/C 源的 material 权限。
```

验收：

```text
python .agents/skills/evidence-ingest/scripts/validate_manifest.py --help
# 或现有 registry 校验脚本，如有
```

## Phase DL-B: 适配器接口抽象

### Task DL-B1: 统一 adapter run plan reader

目标：新增或改造一个轻量 reader，使 `structured_api_pull.py` 能读取：

```text
--plan data_request_plan.yaml
--source-name tushare|baostock|local_fixture
--api-name <api>
--dry-run
```

要求：

```text
1. 保留现有 --input-csv / --input-json 离线 fixture 兼容性。
2. dry-run 只输出将要调用的 endpoint / params / output paths，不访问网络。
3. 所有真实调用都必须写 api_params_hash。
4. 无 token 时不失败整个测试，只生成 BLOCKED run log 或 dry-run report。
```

不在本补丁中实现。

### Task DL-B2: Tushare adapter module

建议新增：

```text
src/ingest/adapters/tushare_adapter.py
```

功能范围第一版：

```text
stock_basic
daily_basic
income
balancesheet
cashflow
fina_indicator
fina_mainbz
```

实现要求：

```text
1. 从环境变量读取 TUSHARE_TOKEN。
2. token 缺失时返回 BLOCKED，不抛未处理异常。
3. 支持 dry-run 和 fixture-run。
4. 每个 API 保存 raw JSON 或 raw CSV。
5. 字段列表写入 snapshot metadata。
6. 生成 metric_candidates；fina_mainbz 只能生成 business_segment_metric candidates，不得直接生成 exposure claim。
7. 记录权限/积分/频率错误。
```

测试：

```text
tests/test_tushare_adapter_contract.py
- no token dry-run passes
- fixture income generates manifest + metric candidates
- fina_mainbz does not create claim_candidates
- api_params_hash changes when params change
```

### Task DL-B3: Baostock adapter module

建议新增：

```text
src/ingest/adapters/baostock_adapter.py
```

功能范围第一版：

```text
login/logout
query_stock_basic
query_history_k_data_plus
query_profit_data
query_balance_data
query_cash_flow_data
```

实现要求：

```text
1. baostock package 不存在时测试不失败，进入 BLOCKED 或 fixture mode。
2. 真实调用必须 login → query → logout。
3. login failure 写 run log。
4. historical K line 记录 frequency / adjustflag。
5. 所有输出 metric_only。
```

测试：

```text
tests/test_baostock_adapter_contract.py
- fixture K line creates technical snapshot seed
- login failure maps to FAILED/BLOCKED run status
- no business exposure claim created
```

## Phase DL-C: Market context packs

### Task DL-C1: valuation_snapshot builder

建议新增或扩展：

```text
src/ingest/build_valuation_snapshot.py
```

输入：

```text
metric_candidates / normalized daily_basic / Tencent fixture
```

输出：

```text
reports/workflow_runs/<workflow_id>/valuation_snapshot.yaml
```

必备字段：price, market_cap, pe_ttm, pb, ps, turnover_rate, trade_date, source_evidence_id。

### Task DL-C2: technical_snapshot builder

输入：K line normalized table。

输出：

```text
technical_snapshot.yaml
```

第一版只做：MA5/MA10/MA20/MA60、20d/60d pct change、volume trend。

### Task DL-C3: market_sentiment_pack builder

第一版只接受 fixture 或已登记 market_context rows。

输出：

```text
market_sentiment_pack.yaml
```

强制：hotlist/news/fund-flow conclusions 默认 clue-only。

## Phase DL-D: Data quality gate

### Task DL-D1: data_layer_quality_review.py

建议新增：

```text
src/qa/data_layer_quality_review.py
```

检查：

```text
G-DL1 source permission
G-DL2 raw archive
G-DL3 reproducibility
G-DL4 field schema
G-DL5 metric-only boundary
G-DL6 freshness
G-DL7 license / token leak
G-DL8 downstream pack completeness
```

输出：

```text
data_layer_quality_report.md
data_layer_issue_list.csv
```

测试：

```text
tests/test_data_layer_quality_gate.py
```

## Phase DL-E: Stock-first integration debug

### Task DL-E1: 002837 data-layer run

基于已有 002837 run，新增一次 data-layer-only workflow：

```text
reports/workflow_runs/wf_20260703_data_layer_002837_invic/
```

要求：

```text
1. data_request_plan.yaml
2. adapter_run_queue.yaml
3. fixture or real snapshot registration
4. valuation_snapshot.yaml
5. technical_snapshot.yaml
6. financial_metric_pack.csv
7. source_gap_report.md
8. data_layer_quality_report.md
9. workflow_readout.md
```

验收：

```text
status: accepted_with_todos 或 accepted
high issues: 0
no advice language: pass
```

## Phase DL-F: Publishable stock report readiness bridge

目标：让 `stock-deep-dive` 能消费数据层 packs。

需要 Codex 更新：

```text
.agents/skills/stock-deep-dive/references/stock_report_contract.md  # 如存在
.agents/skills/stock-deep-dive/SKILL.md
quality-review gates
```

规则：

```text
1. 没有 valuation_snapshot，不写估值结论，只写 TODO_MARKET_DATA。
2. 没有 technical_snapshot，不写技术分析，只写 TODO_MARKET_DATA。
3. 没有 peer_market_snapshot，不写同行估值比较，只写 TODO_PEER_DATA。
4. 没有 official disclosure，不写 business exposure fact。
```

## Recommended order

```text
DL-A 文档合并
DL-B1 adapter plan reader
DL-B2 Tushare fixture/dry-run
DL-B3 Baostock fixture/dry-run
DL-C1 valuation snapshot
DL-C2 technical snapshot
DL-D data quality gate
DL-E 002837 data-layer run
DL-F stock-deep-dive pack consumption
```

## Stop conditions

不继续后续阶段，如果出现：

```text
- API token 被写入文件；
- adapter 直接写报告；
- Tushare/Baostock 生成 business exposure claim；
- raw snapshot 可被覆盖；
- 无 api_params_hash 仍 promoted metric；
- quality gate 不能指出具体 target artifact；
- no-advice gate 失败。
```
