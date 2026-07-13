# R5 Bundle 8A/8B Local Close Readout

- workflow_id: `wf_20260703_stock_first_002837_invic`
- close_date: `2026-07-13`
- decision: `accepted_with_todos`
- bundle_closed: `true`
- reader_regenerated: `false`
- reader_state: `59/82, research_draft, rejected`
- repository_publish: `not_authorized_not_performed`
- remote_ci: `TODO_AFTER_EXPLICIT_PUBLISH`

## Outcome

Bundle 8 已在本地完成证据韧性集成、真实抓取、字段与代理诊断、液冷披露边界、同业输入和质量关闭。Canonical workflow 仍为 `needs_fix`，但第一回流从 `evidence-ingest` 前移到 Bundle 9 的 `stock-deep-dive`；这不是 Reader 或样例质量许可。

## Close Evidence

| item | result |
|---|---|
| latest patch integrity | 25/25 checksums; 19/19 overlay hashes |
| route quality | pass; 12 capabilities; 0 blocking |
| live evidence delta | 46 rows; 46 unique; 0 missing paths |
| structured candidates | 25,586 new retained after unit/code normalization; all draft |
| official IR | 4 archived and parsed; selected management comments reviewed |
| peer operating inputs | 5 companies; 45 metrics reconciled to normalized snapshots |
| technical and valuation | 250-day technical input and 2026-07-10 valuation snapshot |
| event metadata | 2026H1 planned disclosure 2026-08-25; issuer verification TODO |
| research metadata | 14 rows; analyst_view/estimate only |
| quality decision | accepted_with_todos; no active critical/high issue |
| full regression | 605 passed, 2 skipped |

## Material Evidence Change

此前“液冷收入完全缺失”的判断已被细化：发行人 IR 给出 2024 年数据中心机房及算力设备液冷技术相关收入约 3 亿元，因此该字段成为 B 类近似 `management_comment`。它不是审计分部数据；2025 年液冷收入、数值毛利率、具体客户订单及液冷项目回款仍为 `MISSING_DISCLOSURE`。

## Proxy Findings

- 全局 `HTTP_PROXY/HTTPS_PROXY=http://127.0.0.1:6382` 未修改。
- Tushare、Baostock、CNINFO、SZSE、Tencent 与 Eastmoney `reportapi` 未被阻断。
- Eastmoney `push2` 经代理失败，但分源直连探测成功；状态保持 `degraded`，未声称 live adapter 已实现。

## Accepted TODOs Carried Forward

1. 2025 液冷收入、液冷毛利、订单和项目回款缺失。
2. Baostock 财务字段映射只作 draft fallback。
3. 四家同业需在 Bundle 9 逐项完成 official reconciliation 后再进入估值比较。
4. 未来披露日和分析师 EPS 股本口径需复核。
5. push2 live adapter、IR 2025-004 官方原件和远端 CI 仍待完成。
6. Reader、forecast、valuation、跨公司回归和人工验收尚未完成。

## Next Route

`research-orchestrator -> stock-deep-dive -> company-valuation`，进入 Bundle 9；Reader 保持不变，直到 Bundle 10。

## Research Boundary

本 readout 是工作流状态与证据变更记录，不构成交易建议。
