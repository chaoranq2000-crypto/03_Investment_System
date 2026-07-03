# Data Layer Workflow — A 股投研数据层工作流

> 本文件定义 A-share Research OS 的数据层如何发现、拉取、归档、标准化、候选化和交接。它是 `evidence-ingest` 的下层 workflow，不是新的平级研究 skill。

## 0. 目标

数据层解决三个问题：

```text
1. 从哪里取数据？
2. 取到后如何保存为可追溯证据？
3. 哪些数据可以支持事实、哪些只能支持指标、哪些只能作为线索？
```

数据层不是报告层。它不写投资结论、不写买卖建议、不做 watchlist 决策。

## 1. 总体结构

```text
用户 / 下游 skill 的数据需求
        ↓
research-orchestrator 识别 workflow stage
        ↓
evidence-ingest 创建 data_request_plan
        ↓
source adapter runners 拉取或登记原始文件/快照
        ↓
raw archive + normalized tables + manifests
        ↓
claim_candidates / metric_candidates / clue_log
        ↓
data quality gate
        ↓
交给 stock-deep-dive / segment-research / compare-* / refresh-research
```

## 2. 数据层不另建平级 skill

当前选择：

```text
不建议：.agents/skills/a-share-data/
不建议：.agents/skills/market-data-agent/
不建议：让 stock-deep-dive 直接调用外部 API

建议：.agents/skills/evidence-ingest/references/*
建议：src/ingest/* adapter runners
建议：data/manifests/* run/candidate/registry files
```

理由：

1. 所有数据必须先进入 evidence manifest 或 run log。
2. 结构化数据库默认只能生成 metric candidates。
3. 新闻、热榜、题材、研报默认只能生成 clue 或 analyst_view / estimate。
4. 公司业务暴露、收入占比、客户订单、产能必须优先由公告、年报、交易所披露支持。

## 3. 源分层

### 3.1 Layer A — 官方披露层

用途：公司事实、财报原文、公告事件、问询回复、管理层正式披露。

优先来源：

```text
cninfo
sse
szse
bse
```

默认输出：

```text
source_group: official_disclosure
reliability_rank: A
material_claim_allowed: requires_extraction_and_review
raw_archive_policy: full_file_archived
```

约束：

- 必须保存原始 PDF/HTML/公告文件或 metadata-only 失败记录。
- 必须在解析后提供 page_map / table_inventory / locators。
- 只有经过 claim review 后才能支持 material company fact。

### 3.2 Layer B — 结构化财务/行情数据库层

用途：财务报表三表、财务指标、日行情、估值指标、基础证券信息。

优先来源：

```text
Tushare Pro: primary structured adapter
Baostock: fallback structured adapter
```

默认输出：

```text
source_group: structured_database | structured_database_fallback
reliability_rank: B
material_claim_allowed: metric_only
raw_archive_policy: snapshot_archived
```

约束：

- 必须记录 API 名称、参数、字段、token_env、as_of_date、retrieved_at、api_params_hash。
- 必须保存 raw response 或 raw CSV snapshot。
- 只能生成 metric_candidates，不能证明业务暴露。
- 与年报口径冲突时，以官方披露为准，结构化库进入 reconciliation issue。

### 3.3 Layer C — 市场上下文层

用途：行情、估值、资金流、技术指标、板块归属、热榜、市场情绪。

可参考来源类型：

```text
mootdx / 通达信
腾讯财经
百度 K 线
东财 push2 / datacenter / reportapi
同花顺热点 / 一致预期
新浪财经
巨潮互动易
```

默认输出：

```text
source_group: market_context | market_signal | clue
reliability_rank: B/C/D by endpoint
material_claim_allowed: metric_only | clue_only
raw_archive_policy: snapshot_archived | metadata_only
```

约束：

- 行情和估值字段可作为 market metric。
- 热榜、概念命中、资金流、新闻默认不能成为公司事实。
- 东财/同花顺等公开 HTTP 源必须记录 rate_limit、retry、network_env、fallback。
- 字段映射必须可审计，避免字段误读。

### 3.4 Layer D — 第三方研究/新闻/线索层

用途：行业估算、卖方观点、事件线索、新闻触发、情绪补充。

默认输出：

```text
source_group: third_party_analysis | clue
reliability_rank: C/D
material_claim_allowed: false
allowed_claim_types: analyst_view | estimate | clue
```

约束：

- 不能单独支撑公司财务事实。
- 不能把券商预测写成已发生事实。
- 不能把新闻和热榜写成业务收入或订单事实。

## 4. 数据请求计划

所有数据层运行应先生成 `data_request_plan.yaml`，至少包含：

```yaml
workflow_id:
request_id:
request_type: stock_first | segment_first | refresh | comparison | ad_hoc
object:
  stock_code:
  company_id:
  segment_id:
time_range:
  start_date:
  end_date:
required_outputs:
  - evidence_manifest_rows
  - metric_candidates
  - normalized_tables
  - data_pack
source_layers:
  official_disclosure:
  structured_database:
  market_context:
  third_party_clues:
quality_gates:
  - source_permission
  - raw_archive
  - api_params_hash
  - metric_only_boundary
  - freshness
  - license
```

## 5. 标准 workflow

### DL0 Intake

输入来自 research-orchestrator 或下游 skill。

输出：

```text
data_request_plan.yaml
handoff_to_evidence_ingest.md
```

门禁：对象、时间范围、输出需求清楚。

### DL1 Source Routing

读取：

```text
config/source_registry.yaml
.agents/skills/evidence-ingest/references/source_adapter_matrix.md
```

输出：

```text
adapter_run_queue.yaml
```

门禁：每个 endpoint 有 source_name、source_group、allowed_claim_types、fallback、license_note。

### DL2 Acquire / Register

按源执行：

```text
official_disclosure_download_or_register
structured_api_pull
market_context_snapshot
clue_search_or_register
```

输出：

```text
data/raw/**
data/processed/normalized/**
data/processed/logs/**
```

门禁：raw 不覆盖；失败也要有 metadata-only 或 issue 记录。

### DL3 Manifest / Run Log

写入：

```text
data/manifests/evidence_manifest.csv
data/manifests/ingest_runs.csv
```

必要字段：

```text
evidence_id
source_type
source_name
source_group
title
publish_date / as_of_date / retrieved_at
raw_file_path
file_hash / content_hash / api_params_hash
processed_table_path / processed_text_path
reliability_rank
material_claim_allowed
status
parse_status
candidate_status
review_status
```

### DL4 Candidate Generation

分源生成：

```text
official disclosure parsed text → claim_candidates
structured database snapshot → metric_candidates
market context snapshot → metric_candidates or clue_log
news/hotlist/social → clue_log only
```

门禁：candidate 必须是 draft，不能直接进入正式 registry。

### DL5 Data Packs

为了让报告接近样例质量，数据层应给下游准备标准 packs：

```text
company_identity_pack.yaml
financial_metric_pack.csv
business_segment_metric_pack.csv
valuation_snapshot.yaml
technical_snapshot.yaml
market_sentiment_pack.yaml
peer_market_snapshot.csv
source_gap_report.md
```

其中：

- `financial_metric_pack` 来自 Tushare/Baostock/官方财报 reconciliation。
- `valuation_snapshot` 来自行情/估值源。
- `technical_snapshot` 来自 K 线与均线源。
- `market_sentiment_pack` 来自资金流、热榜、新闻线索，但默认 clue only。
- `source_gap_report` 明确哪些字段仍然 MISSING。

### DL6 Quality Gate

运行数据层质量门：

```text
G-DL1 Source Permission Gate
G-DL2 Raw Archive Gate
G-DL3 Snapshot Reproducibility Gate
G-DL4 Field Schema Gate
G-DL5 Metric-only Boundary Gate
G-DL6 Freshness Gate
G-DL7 License / Terms Gate
G-DL8 Downstream Pack Completeness Gate
```

输出：

```text
data_layer_quality_report.md
data_layer_issue_list.csv
```

### DL7 Handoff

向下游交接：

```text
stock-deep-dive:
  company_identity_pack
  financial_metric_pack
  valuation_snapshot
  technical_snapshot
  market_sentiment_pack
  source_gap_report

segment-research:
  industry_context_clues
  official/statistical data packs
  company_universe metric seeds

compare-stocks:
  peer_market_snapshot
  peer_financial_metric_pack

refresh-research:
  new_evidence_delta
  stale_snapshot_report
```

## 6. Stock-first 数据层最小闭环

```text
T0 stock_first intake
↓
DL0 data_request_plan
↓
DL1 source routing
↓
DL2 annual/interim/quarterly/material announcements registration
↓
DL3 Tushare financial snapshots: stock_basic, income, balancesheet, cashflow, fina_indicator, fina_mainbz, daily_basic
↓
DL4 Baostock fallback: historical K line / basic / selected quarterly financial metrics
↓
DL5 market context snapshots: price, market cap, PE/PB/PS, turnover, sector, technical indicators, fund flow clues
↓
DL6 data packs + quality gate
↓
T2 stock-deep-dive business & financial skeleton
```

## 7. Segment-first 数据层最小闭环

```text
S0 segment intake
↓
DL0 segment data_request_plan
↓
DL1 source routing by segment keywords and candidate companies
↓
DL2 industry/regulator/statistical data registration
↓
DL3 company universe structured snapshots
↓
DL4 market context only for candidate prioritization
↓
DL5 segment_metric_pack + company_universe_seed.csv
↓
S4/S5 segment-research and company-universe
```

## 8. Refresh 数据层最小闭环

```text
existing evidence snapshot
↓
new filing / new structured snapshot / new market context
↓
compare api_params_hash + publish_date + report period
↓
mark fresh / stale / superseded / contradicted / unchanged
↓
output refresh_data_delta.md
```

## 9. 关键边界

1. `Tushare.fina_mainbz` 可以提供主营业务构成指标候选，但仍需年报表格或披露文字核验后才可写成业务暴露结论。
2. Baostock 可作为行情和部分季度财务 fallback；不作为业务线事实来源。
3. 市场热榜、资金流、龙虎榜、概念归因只能进入情绪/线索层。
4. 研报 PDF 可作为 analyst_view / estimate，不可替代公司公告。
5. 同一个指标存在多源差异时，必须生成 reconciliation issue。

## 10. 进入发布级个股报告前的数据层最低要求

```text
[ ] 最新年报或 explicit TODO
[ ] 最新季报/半年报或 explicit TODO
[ ] Tushare/Baostock 或本地 fixture 结构化财务快照
[ ] 市值、PE/PB、成交、区间涨跌幅、均线等 market snapshot
[ ] 主营业务构成候选或年报业务表格定位
[ ] 至少一个 peer_market_snapshot 或 explicit TODO
[ ] data_layer_quality_report 无 high issue
[ ] source_gap_report 明确 MISSING 字段
```
