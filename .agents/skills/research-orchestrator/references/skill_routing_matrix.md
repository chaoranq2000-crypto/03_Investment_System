# Skill Routing Matrix — research-orchestrator reference

> 本文件是 `research-orchestrator` 的快速路由参考。事实源仍以 `docs/workflows/RESEARCH_WORKFLOW.md` 和 `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` 为准。

## 1. Routine routing

| 用户请求 / 当前需要 | workflow_type | stage | 主 skill | 输出 |
|---|---|---|---|---|
| 研究一个细分并找公司池/个股样本 | `segment_to_stock_closed_loop` | S0-S13 | `research-orchestrator` 编排 | workflow run + segment package + stock samples |
| 定义一个细分边界 | `segment_to_stock_closed_loop` | S1 | `segment-research` | segment definition / boundary note |
| 导入证据 | any | evidence stage | `evidence-ingest` | evidence manifest / processed evidence |
| 从证据拆 claims / metrics | any | claims/metrics stage | `evidence-ingest` + `quality-review` | claims_draft / metrics_draft |
| 找细分 A 股公司池 | `segment_to_stock_closed_loop` | S5 | `company-universe` | company_universe.csv |
| 维护公司-细分暴露 | `segment_stock_interlock` | mapping | `segment-company-mapping` | segment_company_exposure.csv / segment_exposure.yaml |
| 深挖一只股票 | `stock_first_closed_loop` or S8 sample | T0-T10 / S8 | `stock-deep-dive` | stock_deep_dive.md + segment_exposure.yaml + evidence_map |
| 个股发现需要回写细分 | `segment_stock_interlock` | backflow | `segment-company-mapping` + `segment-research` | updated exposure / taxonomy / scorecard TODO |
| 检查报告质量 | any | quality gate | `quality-review` | quality_gate_report / quality issues |
| 写观察备忘录 | after accepted review | memo | `memo-writer` | memo / watchlist note |
| 刷新已有研究 | `refresh_existing_research` | refresh | `refresh-research` | refresh_log / stale_claims / reports_to_regenerate |
| 用户要求比较多个细分/个股 | `comparison_readiness_gate` first | readiness | `research-orchestrator` + `quality-review` | P2 readiness decision |

## 2. P1.6 current build routing

| 当前建设意图 | workflow_type | recommended_start_stage | 主 skill | 辅助 skill | 输出 |
|---|---|---|---|---|---|
| B1 后问“下一步做什么” | `stock_first_closed_loop` | T0/T1 | `research-orchestrator` | `evidence-ingest` | stock-first workflow state + handoff |
| 给一个股票跑个股闭环 | `stock_first_closed_loop` | T0-T10 | `stock-deep-dive` | `evidence-ingest` / `segment-company-mapping` / `quality-review` | stock package + exposure + readout |
| 完善证据下载功能 | any | Evidence Plan / Ingest | `evidence-ingest` | `quality-review` | manifest / candidates / ingest_log |
| 官方披露下载或登记 | any | Evidence Plan / Ingest | `evidence-ingest` | - | raw official disclosure + manifest row |
| Tushare/Baostock/CSV 结构化快照 | any | Claims / Metrics Draft | `evidence-ingest` | `quality-review` | raw snapshot + metrics_draft |
| `segment_exposure.yaml` 回写 | `segment_stock_interlock` | backflow | `segment-company-mapping` | `quality-review` | `segment_company_exposure.csv` 或 change note |
| 个股闭环质量门 | `stock_first_closed_loop` | T9 | `quality-review` | `research-orchestrator` | issue list + accepted/needs_fix/blocked |

## 3. Absolute routing rules

1. 没有 evidence，不得直接进入结论性报告。
2. 下载器不得绕过 `evidence-ingest`；所有 raw file / snapshot 必须登记到 `evidence_manifest.csv`。
3. 结构化 API 快照默认只能生成 `metric_candidates`，不得直接支撑业务暴露或收入占比结论。
4. 没有 `segment_exposure.yaml` 或 no-backflow reason，不得关闭 stock-first workflow。
5. 个股深度完成后，必须做 backflow decision。
6. 进入 P2 前，必须先执行 `comparison_readiness_gate`。
7. high severity quality issue 未关闭，不得 accepted。
