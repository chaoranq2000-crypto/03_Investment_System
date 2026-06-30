# Research Object Model — 研究对象模型

## 1. 为什么先定义对象

A 股投研最容易混乱的地方不是报告格式，而是对象关系：一个细分可能对应很多公司，一家公司也可能同时暴露在多个细分里。若用文件夹层级强行表达，会导致研究无法更新、无法比较、无法复盘。

因此，本项目先定义对象模型，再生成报告。

---

## 2. 核心对象

| 对象 | 中文 | 含义 |
|---|---|---|
| `Segment` | 细分方向 | 产业链细分、主题、产品、工艺、应用或商业模式 |
| `Company` | 上市公司主体 | 业务经营实体 |
| `Security` | 证券 | 股票代码、交易所、证券简称等 |
| `Evidence` | 证据 | 公告、年报、政策、数据、纪要、报告等原始或结构化证据 |
| `Claim` | 事实/结论单元 | 从证据中抽取出的事实、估计、推断或观点 |
| `Metric` | 指标 | 财务、产业、运营、估值等指标观测值 |
| `Report` | 报告 | 细分报告、个股报告、对比报告、刷新报告 |
| `Thesis` | 研究假设 | 可被证据支持或证伪的观察假设 |
| `WatchItem` | 跟踪项 | 需要跟踪的细分、个股、指标、催化剂或风险 |

---

## 3. 核心关系

```text
Segment  ←→  Company        多对多，通过 segment_company_exposure 表达
Company  ←→  Security       一对一或一对多
Evidence → Claim            一份证据可产生多条 claim
Claim    → Segment/Company  一条 claim 可挂到细分、公司或两者
Metric   → Segment/Company  指标可属于细分，也可属于公司
Report   → Evidence/Claim   报告必须回溯证据和 claim
Thesis   → Evidence/Claim   假设必须可被证据支持或证伪
WatchItem→ Segment/Company  跟踪项可绑定细分、公司、指标或催化剂
```

---

## 4. Segment

### 4.1 最小字段

```yaml
segment_id:
name_cn:
name_en:
aliases: []
definition:
scope_in: []
scope_out: []
parent_theme:
industry_chain_role: upstream | midstream | downstream | equipment | material | service | application | unknown
related_segments: []
created_at:
updated_at:
status: active | watch | archived
```

### 4.2 设计规则

- `segment_id` 必须稳定，不随市场热词频繁变化。
- `scope_in` 和 `scope_out` 必须写清楚。
- 相邻细分要显式列出，避免混淆。
- 一个细分可以跨行业分类，但要说明产业链位置。

---

## 5. Company / Security

### 5.1 Company 最小字段

```yaml
company_id:
stock_code:
stock_name:
exchange: SSE | SZSE | BSE | HKEX | NASDAQ | NYSE | other
business_summary:
created_at:
updated_at:
status: active | watch | archived
```

### 5.2 Security 最小字段

```yaml
security_id:
stock_code:
exchange:
stock_name:
listing_status:
currency:
```

### 5.3 设计规则

- 公司主体和股票代码不要混淆。
- 同一公司可能有多个证券；P0 可以先简化为 A 股一对一。
- 个股报告必须列出 linked_segments。

---

## 6. Segment-company exposure

这是本系统最关键的关系对象。

### 6.1 最小字段

```yaml
segment_company_exposure:
  segment_id:
  company_id:
  stock_code:
  stock_name:
  exposure_type: revenue | capacity | product | technology | customer | project | narrative | unknown
  exposure_score: 0
  revenue_pct:
  profit_pct:
  evidence_ids: []
  confidence: high | medium | low
  valid_from:
  valid_to:
  notes:
```

### 6.2 暴露类型说明

| exposure_type | 含义 | 证据要求 |
|---|---|---|
| `revenue` | 已披露收入或收入占比 | 年报、定期报告、官方公告等优先 |
| `capacity` | 产能、募投、产线、交付能力 | 公告、环评、募投文件、年报 |
| `product` | 产品明确属于该细分 | 产品手册、公告、年报、客户资料 |
| `technology` | 技术储备或专利布局 | 年报、专利、研发项目披露 |
| `customer` | 客户或下游场景暴露 | 年报、公告、客户认证、订单披露 |
| `project` | 订单、项目、中标、合作 | 公告、中标文件、合同披露 |
| `narrative` | 市场叙事或概念映射 | 低置信度，必须标记 |
| `unknown` | 尚无法判断 | 必须写 TODO |

### 6.3 exposure_score

| 分数 | 含义 |
|---:|---|
| 0 | 无证据或不相关 |
| 1 | 仅概念或非常弱的间接关联 |
| 2 | 有产品/技术/项目线索，但收入或利润影响不清 |
| 3 | 有明确业务暴露，但占比或弹性不清 |
| 4 | 有较强业务暴露，收入、订单或客户证据较清楚 |
| 5 | 高纯度核心暴露，财务影响明确且证据强 |

---

## 7. Evidence

### 7.1 最小字段

```yaml
evidence_id:
source_type: annual_report | announcement | exchange_data | industry_report | policy | transcript | news | database | other
source_name:
source_url_or_path:
title:
publisher:
publish_date:
ingested_at:
file_hash:
raw_file_path:
processed_text_path:
reliability_rank: A | B | C | D
license_note:
status: fresh | stale | superseded | contradicted | low_confidence
```

### 7.2 设计规则

- 原始证据必须能从 `raw_file_path` 找回。
- 同一文件重复导入时用 hash 去重。
- 低可信来源可以使用，但必须标记来源等级和置信度。

---

## 8. Claim

### 8.1 最小字段

```yaml
claim_id:
evidence_id:
entity_type: segment | company | security | macro | policy | customer | supplier | other
entity_id:
claim_text:
claim_type: fact | estimate | inference | management_comment | analyst_view | opinion | unknown
quote_or_excerpt:
page_no:
confidence: high | medium | low
created_at:
valid_until:
status: fresh | stale | superseded | contradicted | low_confidence
```

### 8.2 设计规则

- 报告不要只引用整篇资料，应尽可能引用到 claim。
- 管理层说法必须标为 `management_comment`。
- 券商预测必须标为 `analyst_view` 或 `estimate`。
- 研究者推断必须标为 `inference`。

---

## 9. Metric

### 9.1 最小字段

```yaml
metric_id:
entity_type: segment | company | security
entity_id:
metric_name:
period:
value:
unit:
source_evidence_id:
calculation_method:
is_estimate: true | false
confidence: high | medium | low
created_at:
```

### 9.2 指标原则

- 同一指标必须有统一口径。
- 估算值必须标记 `is_estimate: true`。
- 计算方法必须可复现。
- 不同来源口径冲突时必须并列呈现。

---

## 10. Report

### 10.1 报告类型

```yaml
report_type: segment_report | stock_report | segment_comparison | stock_comparison | refresh_log | memo | postmortem
```

### 10.2 最小 metadata

```yaml
report_id:
report_type:
title:
entity_ids: []
report_date:
evidence_snapshot:
claim_ids: []
metric_ids: []
confidence: high | medium | low
status: current | needs_refresh | outdated | archived
```

### 10.3 设计规则

- 报告是 snapshot，不是唯一真相。
- 报告应包含 evidence map。
- 报告更新必须有 refresh log。

---

## 11. Thesis and WatchItem

### 11.1 Thesis

```yaml
thesis_id:
created_at:
entity_type: segment | company | portfolio | other
entity_id:
thesis_text:
supporting_claim_ids: []
contradicting_claim_ids: []
key_assumptions: []
validation_metrics: []
status: active | weakened | strengthened | invalidated | archived
next_review_date:
```

### 11.2 WatchItem

```yaml
watch_item_id:
entity_type:
entity_id:
watch_reason:
trigger:
metric_or_event:
threshold:
source_to_monitor:
status: active | paused | archived
```

---

## 12. 最小落地建议

P0 不需要马上建数据库。先用 YAML / CSV / Markdown 表达对象模型即可。

P1 再逐步将这些对象落到：

```text
data/manifests/evidence_manifest.*
config/segment_taxonomy.yaml
reports/segments/<segment_id>/company_universe.csv
reports/stocks/<stock_code>_<company_slug>/segment_exposure.yaml
```
