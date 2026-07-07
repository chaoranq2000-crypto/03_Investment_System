# Skill Routing Matrix — research-orchestrator quick reference

This is a quick reference only. Canonical workflow_type/stage_id/gate_id
are owned by docs/workflows/RESEARCH_WORKFLOW.md.

本文件是 `research-orchestrator` 的唯一 quick routing matrix，
不是 canonical workflow fact source。

如果本文件和 `RESEARCH_WORKFLOW.md` 冲突，执行时以
`RESEARCH_WORKFLOW.md` 为准，并记录 TODO 修正本文件。

## Quick routing matrix

| 用户请求 / 当前需要 | workflow context | target_skill | expected output |
|---|---|---|---|
| 研究一个细分并找公司池 / 个股样本 | `segment_to_stock_closed_loop` | `research-orchestrator` | workflow run + segment package + stock samples |
| 定义一个细分边界 | current segment-led workflow | `segment-research` | segment definition / boundary note |
| 导入证据 | current workflow | `evidence-ingest` | evidence manifest / processed evidence |
| 从证据拆 claims / metrics | current workflow | `evidence-ingest` + `quality-review` | claims_draft / metrics_draft |
| 找细分 A 股公司池 | current segment-led workflow | `company-universe` | company_universe.csv |
| 维护公司-细分暴露 | `segment_stock_interlock` or current workflow | `segment-company-mapping` | segment_company_exposure.csv / segment_exposure.yaml |
| 深挖一只股票 | `stock_first_closed_loop` or segment sample | `stock-deep-dive` | stock_deep_dive.md + segment_exposure.yaml + evidence_map |
| 个股发现需要回写细分 | `segment_stock_interlock` or current workflow | `segment-company-mapping` + `segment-research` | updated exposure / taxonomy / scorecard TODO |
| 检查报告质量 | current workflow | `quality-review` | quality_gate_report / quality issues |
| 写观察备忘录 | after accepted review | `memo-writer` | memo / watchlist note |
| 刷新已有研究 | `refresh_existing_research` | `refresh-research` | refresh_log / stale_claims / reports_to_regenerate |
| 用户要求比较多个细分 / 个股 | `comparison_readiness_gate` first | `research-orchestrator` + `quality-review` | P2 readiness decision |
| 用户只问状态 / 缺口 / 下一步 | related workflow or blank | `research-orchestrator` with `run_mode: diagnostic` | diagnostic answer; run directory optional |

## Absolute routing rules

1. 没有 evidence，不得直接进入结论性报告。
2. 下载器不得绕过 `evidence-ingest`；raw file / snapshot 必须登记到 `evidence_manifest.csv`。
3. 结构化 API 快照默认只能生成 `metric_candidates`，不得直接支撑业务暴露或收入占比结论。
4. 没有 `segment_exposure.yaml` 或 no-backflow reason，不得关闭 stock-first workflow。
5. 个股深度完成后，必须给出 backflow decision。
6. 进入 P2 前，必须先执行 `comparison_readiness_gate`。
7. high severity quality issue 未关闭，不得 accepted。
