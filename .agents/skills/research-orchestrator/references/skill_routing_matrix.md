# Skill Routing Matrix — research-orchestrator quick reference

本文件是 `research-orchestrator` 的快速路由参考，不是 canonical workflow fact source。

Canonical workflow type、stage 和 gate 以以下文件为准：

```text
docs/workflows/RESEARCH_WORKFLOW.md
```

如果本文件和 `RESEARCH_WORKFLOW.md` 冲突，执行时以 `RESEARCH_WORKFLOW.md` 为准，并记录 TODO 修正本文件。

## Routine routing

| 用户请求 / 当前需要 | canonical workflow | 主 skill | 输出 |
|---|---|---|---|
| 研究一个细分并找公司池 / 个股样本 | `segment_to_stock_closed_loop` | `research-orchestrator` 编排 | workflow run + segment package + stock samples |
| 定义一个细分边界 | `segment_to_stock_closed_loop` | `segment-research` | segment definition / boundary note |
| 导入证据 | current workflow | `evidence-ingest` | evidence manifest / processed evidence |
| 从证据拆 claims / metrics | current workflow | `evidence-ingest` + `quality-review` | claims_draft / metrics_draft |
| 找细分 A 股公司池 | `segment_to_stock_closed_loop` | `company-universe` | company_universe.csv |
| 维护公司-细分暴露 | `segment_stock_interlock` | `segment-company-mapping` | segment_company_exposure.csv / segment_exposure.yaml |
| 深挖一只股票 | `stock_first_closed_loop` or segment sample | `stock-deep-dive` | stock_deep_dive.md + segment_exposure.yaml + evidence_map |
| 个股发现需要回写细分 | `segment_stock_interlock` | `segment-company-mapping` + `segment-research` | updated exposure / taxonomy / scorecard TODO |
| 检查报告质量 | current workflow | `quality-review` | quality_gate_report / quality issues |
| 写观察备忘录 | after accepted review | `memo-writer` | memo / watchlist note |
| 刷新已有研究 | `refresh_existing_research` | `refresh-research` | refresh_log / stale_claims / reports_to_regenerate |
| 用户要求比较多个细分 / 个股 | `comparison_readiness_gate` first | `research-orchestrator` + `quality-review` | P2 readiness decision |
| 用户只问状态 / 缺口 / 下一步 | use related workflow or omit | `research-orchestrator` with `run_mode: diagnostic` | diagnostic answer; run directory optional |

## P1.6 current build routing

| 当前建设意图 | recommended start | 主 skill | 辅助 skill | 输出 |
|---|---|---|---|---|
| 给一个股票跑个股闭环 | stock-first intake | `research-orchestrator` | `evidence-ingest` / `stock-deep-dive` / `segment-company-mapping` / `quality-review` | stock package + exposure + readout |
| 完善证据下载功能 | evidence stage | `evidence-ingest` | `quality-review` | manifest / candidates / ingest_log |
| 官方披露下载或登记 | evidence stage | `evidence-ingest` | - | raw official disclosure + manifest row |
| Tushare / Baostock / CSV 结构化快照 | evidence / metric draft | `evidence-ingest` | `quality-review` | raw snapshot + metrics_draft |
| `segment_exposure.yaml` 回写 | backflow | `segment-company-mapping` | `quality-review` | `segment_company_exposure.csv` 或 change note |
| 个股闭环质量门 | quality stage | `quality-review` | `research-orchestrator` | issue list + accepted / needs_fix / blocked |

## Absolute routing rules

1. 没有 evidence，不得直接进入结论性报告。
2. 下载器不得绕过 `evidence-ingest`；所有 raw file / snapshot 必须登记到 `evidence_manifest.csv`。
3. 结构化 API 快照默认只能生成 `metric_candidates`，不得直接支撑业务暴露或收入占比结论。
4. 没有 `segment_exposure.yaml` 或 no-backflow reason，不得关闭 stock-first workflow。
5. 个股深度完成后，必须给出 backflow decision。
6. 进入 P2 前，必须先执行 `comparison_readiness_gate`。
7. high severity quality issue 未关闭，不得 accepted。
