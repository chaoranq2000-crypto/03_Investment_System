# ADR 0002: 将数据层作为 evidence-ingest 的子系统，而不是新建平级研究 skill

## Status

Proposed

## Context

当前项目已经确立 evidence-first 结构：证据库是事实源，报告只是某一时点的派生产物。`evidence-ingest` 已经负责导入公告、年报、网页、CSV/XLSX、行情/财务结构化数据，并要求产出 raw evidence、processed outputs、manifest rows、claim/metric candidates 和 ingest logs。

同时，外部 `a-stock-data` 体现了 A 股数据获取的实战复杂性：不同源覆盖行情、研报、信号、资金、公告、F10、新闻、互动等；且需要源优先级、限流、防封、fallback 和字段坑记录。Tushare / Baostock 则更适合作为结构化数据适配器，而不是研究结论来源。

如果把数据下载能力做成与 `evidence-ingest` 并列的 `a-share-data` 或 `market-data-agent` skill，容易形成错误路径：

```text
data skill 下载数据
→ stock-deep-dive 直接读取并写结论
→ 没有 evidence_manifest / candidate / quality gate
→ 无法追溯和刷新
```

## Decision

数据层不新建平级研究 skill。数据层作为 `evidence-ingest` 的子系统，由以下四部分组成：

```text
1. source adapter matrix
2. adapter runner contracts
3. snapshot / manifest / candidate output contracts
4. data quality gates
```

所有真实 API 或爬取类工具都必须输出到 `evidence-ingest` 标准产物：

```text
raw snapshot/file
processed normalized table
manifest row
metric_candidates / claim_candidates / clue_log
adapter run log
quality issue list
```

## Consequences

### Good

- 所有数据都有 evidence_id 或至少 run_id / api_params_hash。
- Tushare / Baostock / market context 都不会绕过证据层。
- 后续 stock-deep-dive、segment-research、compare-stocks 可以消费统一的 data packs。
- 质量门能检查 source rank、freshness、field drift、license、metric-only 边界。

### Trade-offs

- 早期开发速度比“直接查数据写报告”慢。
- 需要维护较多 manifest / run log / normalized schema。
- 真正的研究报告质量要等数据层、claim 层、writer 层都补齐后才显著提升。

## Non-goals

- 不做自动交易。
- 不做实时行情系统。
- 不把评分卡转化为交易信号。
- 不把第三方研报、新闻、热榜、资金流直接作为公司事实。
