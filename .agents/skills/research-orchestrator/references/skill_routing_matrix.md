# Skill Routing Matrix — research-orchestrator reference

> 本文件是 `research-orchestrator` 的快速路由参考。事实源仍以 `docs/workflows/RESEARCH_WORKFLOW.md` 和 `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` 为准。

| 用户请求 / 当前需要 | workflow_type | stage | 主 skill | 输出 |
|---|---|---|---|---|
| 研究一个细分并找公司池/个股样本 | `segment_to_stock_closed_loop` | S0-S13 | `research-orchestrator` 编排 | workflow run + segment package + stock samples |
| 定义一个细分边界 | `segment_to_stock_closed_loop` | S1 | `segment-research` | segment definition / boundary note |
| 导入证据 | any | evidence stage | `evidence-ingest` | evidence manifest / processed evidence |
| 从证据拆 claims / metrics | any | claims/metrics stage | `evidence-ingest` + `quality-review` | claims_draft / metrics_draft |
| 找细分 A 股公司池 | `segment_to_stock_closed_loop` | S5 | `company-universe` | company_universe.csv |
| 维护公司-细分暴露 | `segment_stock_interlock` | mapping | `segment-company-mapping` | segment_company_exposure.csv / segment_exposure.yaml |
| 深挖一只股票 | `stock_first_closed_loop` or S8 sample | T0-T10 / S8 | `stock-deep-dive` | stock_deep_dive.md + evidence_map |
| 个股发现需要回写细分 | `segment_stock_interlock` | backflow | `segment-company-mapping` + `segment-research` | updated exposure / taxonomy / scorecard TODO |
| 检查报告质量 | any | quality gate | `quality-review` | quality_gate_report / quality issues |
| 写观察备忘录 | after accepted review | memo | `memo-writer` | memo / watchlist note |
| 刷新已有研究 | `refresh_existing_research` | refresh | `refresh-research` | refresh_log / stale_claims / reports_to_regenerate |
| 用户要求比较多个细分/个股 | `comparison_readiness_gate` first | readiness | `research-orchestrator` + `quality-review` | P2 readiness decision |

## 绝对路由规则

1. 没有 evidence，不得直接进入结论性报告。
2. 没有 `company_universe.csv` 或 exposure 候选，不得从细分直接进入正式多股比较。
3. 个股深度完成后，必须做 backflow decision。
4. 进入 P2 前，必须先执行 `comparison_readiness_gate`。
5. high severity quality issue 未关闭，不得 accepted。
