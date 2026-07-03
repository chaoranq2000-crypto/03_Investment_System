# Structured Data Adapter Contract — Tushare / Baostock 结构化数据契约

## 1. 适用范围

本契约适用于：

```text
Tushare Pro
Baostock
local CSV/JSON fixtures that mimic structured API snapshots
```

目标是把结构化数据转化为可追溯的 metric candidates，而不是直接写研究结论。

## 2. 统一输入

每个 adapter run 必须有：

```yaml
run_id:
workflow_id:
source_name: tushare | baostock | local_fixture
api_name:
object:
  stock_code:
  ts_code:
  company_id:
  company_name:
params:
  start_date:
  end_date:
  trade_date:
  period:
  fields:
as_of_date:
retrieved_at:
token_env:
permission_note:
retry_policy:
license_note:
```

## 3. 统一输出

必须输出：

```text
raw snapshot:
  data/raw/market_data/<source>_<api>_<stock>_<date>_<hash>.(csv|json)

normalized table:
  data/processed/normalized/<source>_<api>_<stock>_<date>_<hash>.csv

manifest row:
  data/manifests/evidence_manifest.csv

metric candidates:
  data/manifests/metrics_draft.csv
  or workflow-local metrics_registry.csv after quality review

run log:
  data/manifests/ingest_runs.csv
  data/processed/logs/<evidence_id>__ingest_log.json
```

## 4. Evidence manifest defaults

```yaml
source_group: structured_database | structured_database_fallback
source_type: structured_financial_data | structured_market_data
reliability_rank: B
material_claim_allowed: metric_only
allowed_claim_types: metric_snapshot
raw_archive_policy: snapshot_archived
parse_status: snapshot_normalized
candidate_status: metric_candidates_generated
review_status: draft
stale_after: 90d
```

## 5. Tushare first-batch API list

### 5.1 Company identity and securities

| api_name | use | output |
|---|---|---|
| stock_basic | 股票代码、名称、上市日期、行业、市场、状态 | company_identity_pack seed |
| daily_basic | PE/PB/PS、总市值、流通市值、换手等每日指标 | valuation_snapshot |
| daily / pro_bar | OHLCV、复权行情 | technical_snapshot |

### 5.2 Financial statements and indicators

| api_name | use | output |
|---|---|---|
| income | 利润表 | financial_metric_pack |
| balancesheet | 资产负债表 | financial_metric_pack |
| cashflow | 现金流量表 | financial_metric_pack |
| fina_indicator | ROE、毛利率、净利率、周转、偿债等财务指标 | financial_metric_pack |
| fina_mainbz | 主营业务构成，产品/地区/行业 | business_segment_metric_pack candidate |
| forecast | 业绩预告 | event/estimate candidate |
| express | 业绩快报 | event/metric candidate |
| dividend | 分红送转 | shareholder_return metrics |
| disclosure_date | 财报披露计划 | catalyst_calendar seed |

### 5.3 Tushare constraints

- 读取 token from environment only；不得把 token 写入仓库。
- 保存 token_env 字段，例如 `TUSHARE_TOKEN`，不保存 token value。
- 记录积分/权限/frequency issue。
- 接口返回空数据时，写 issue，不补值。
- 单股票历史接口优先按 stock_code 循环，批量接口留到后续。
- 财务报表可能存在 report_type / comp_type / update_flag 差异，不能静默去重。

## 6. Baostock first-batch API list

### 6.1 Market and basic fallback

| api_name | use | output |
|---|---|---|
| login/logout | 会话管理 | adapter run log |
| query_all_stock | 某日全市场证券列表 | universe seed |
| query_stock_basic | 股票基础信息 | company_identity fallback |
| query_history_k_data_plus | K 线、成交量、复权行情 | technical_snapshot |

### 6.2 Financial fallback

| api_name | use | output |
|---|---|---|
| query_profit_data | 季频盈利能力 | metric candidates |
| query_operation_data | 季频营运能力 | metric candidates |
| query_growth_data | 季频成长能力 | metric candidates |
| query_balance_data | 季频偿债能力 | metric candidates |
| query_cash_flow_data | 季频现金流量 | metric candidates |
| query_dupont_data | 杜邦指数 | metric candidates |

### 6.3 Baostock constraints

- 每个 run 必须显式 login 和 logout。
- login 失败则 run status = FAILED。
- empty result 则 PARTIAL_SUCCESS，并保留 raw empty snapshot / issue。
- Baostock fallback 不提升 Tushare 缺失字段为公司事实。
- 历史行情必须记录 frequency、adjustflag、start_date、end_date。

## 7. Metric candidate rules

每条 metric candidate 至少需要：

```yaml
metric_candidate_id:
source_evidence_id:
source_name:
source_type:
entity_type: company
entity_id:
company_id:
stock_code:
metric_name:
metric_category:
period:
period_type:
value:
unit:
original_value_text:
table_id:
calculation_method:
is_estimate:
is_reported:
confidence:
review_status: draft
created_at:
notes:
```

## 8. Reconciliation rules

结构化源与官方披露冲突时：

```text
1. 不覆盖旧 metric。
2. 创建 reconciliation issue。
3. 保留 source_evidence_id 和 api_params_hash。
4. 优先用官方披露原文/表格作为 reported fact。
5. 将结构化源作为 convenience metric 或 cross-check。
```

## 9. Codex implementation notes

适合 Codex 实现的任务：

```text
- 把当前 structured_api_pull.py 从 offline fixture 升级为 adapter runner interface；
- 新增 tushare_adapter.py 和 baostock_adapter.py；
- 增加 YAML plan reader；
- 增加 dry-run mode；
- 增加 fixture-based tests；
- 不在没有 token/网络时阻塞 CI。
```

本文件不包含真实代码实现。
