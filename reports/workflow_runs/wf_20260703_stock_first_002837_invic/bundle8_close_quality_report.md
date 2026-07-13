# Bundle 8B Close Quality Report

- workflow_id: `wf_20260703_stock_first_002837_invic`
- review_date: `2026-07-13`
- reviewer_skill: `quality-review`
- decision: `accepted_with_todos`
- close_recommendation: `bundle8_can_close_locally`
- reader_regenerated: `false`
- sample_quality_allowed: `false`
- remote_ci_claimed: `false`

## 结论

Bundle 8 的真实证据补齐与披露边界可以本地关闭。新增 46 条 evidence row；26,654 条初始 draft metric candidate 经单位规范化并移除 1,068 条日期/状态代码后保留 25,586 条；四份巨潮 IR、五家公司 2025 年同口径经营指标、250 日技术序列、估值快照、未来事件元数据与研报元数据均已归档并可追溯；不存在 active critical/high issue。

该决定不表示 Reader 已完成，也不表示预测、估值或样例质量通过。现有 Reader 仍保持 `59/82`、`research_draft`、`rejected`；Bundle 9 与 Bundle 10 仍必须执行。

## 关键边界判定

1. 2024 年“数据中心机房及算力设备液冷技术相关营业收入约 3 亿元”来自发行人 IR，审查为 `management_comment` 与 B 类近似口径，不得写成审计分部事实。证据：`ev_official_disclosure_002837_20250423_e78396`，第 3 页。
2. 2025 年液冷相关收入、液冷毛利率、具体客户订单金额与液冷项目回款周期继续为 `MISSING_DISCLOSURE`。
3. 1.2GW 是截至 2025 年 3 月的累计交付口径，不是收入、在手订单或产能。
4. 储能热管理收入不能替代数据中心/算力设备液冷收入。
5. Tushare、Baostock 与东方财富新增数据仍为 `draft` 或 `analyst_view/estimate`，本门不执行全局 registry promotion。

## Gate 结果

| gate | status | evidence |
|---|---|---|
| G1 Evidence Gate | pass | manifest validator=`[]`；46/46 delta 唯一且所有 raw/processed path 存在 |
| G2 Claim Gate | pass | 7 条管理层评论经 workflow-local review；3 亿元未升级为 fact |
| G3 Metric Gate | pass_with_todos | 45 项同业指标逐项回算；25,586 条保留的新候选均有显式单位且保持 draft；Baostock 字段映射仍为 TODO |
| G4 Context Gate | pass | 既有两类独立行业来源、政策与技术路线反证继续可用 |
| G7 Market Gate | pass_for_inputs | 250 日技术快照和 2026-07-10 估值快照有日期、单位、来源 |
| G8 Event Gate | pass_with_todos | 2026-08-25 为 Tushare 计划日期，尚需发行人/交易所确认；两家最新券商不称为稳健一致预期 |
| G9 No Advice Gate | pass | 产物不含直接交易指令、目标价、仓位或保证收益 |
| G10 Close Gate | pass_for_local_close | 无 active critical/high issue；远端 CI 保持 low TODO |

## 可重复性与测试

| check | result |
|---|---|
| Bundle 8B close input validator | `pass`; delta=46; peer metrics=45; errors=0 |
| evidence manifest validator | `[]` |
| focused regression | `28 passed` |
| P1 compatibility regression | `10 passed` |
| full repository regression | `605 passed, 2 skipped` |
| metric candidate id migration | `26,654 changed`; company prefix contract restored |
| metric unit/code normalization | `25,526 units normalized`; `1,068 non-metric code rows removed`; retained total=`25,630/25,630 unique` |
| source route gate | retained Stage A pass; rerun required before close readout |

## 来源健康与代理结论

- Tushare、Baostock、CNINFO、SZSE、Tencent 为 `healthy`。
- 东方财富 `reportapi` 经全局 6382 代理抓取成功；`push2` 经该代理出现 TLS EOF/502，但分源直连探测为 200，因此总来源状态保守标记 `degraded`。
- 全局 `C:\Users\Q\.codex\.env` 未被修改；修复策略保持为分来源路由，而不是关闭全局代理。

## Accepted TODOs

- `R5B8B-G3-001`：液冷 2025 收入、数值毛利、订单和项目回款继续缺失。
- `R5B8B-G8-001`：未来披露日期与 EPS 股本口径仍需复核。
- `R5B8B-QR-SCHEMA-001`：Baostock 财务字段映射未晋升。
- `R5B8B-QR-PEER-001`：同业业务组合和液冷纯度不可比。
- `R5B8B-QR-PROXY-001`：push2 live adapter 尚未实现。
- `R5B8B-QR-IR004-001`：IR 2025-004 官方原件待补。
- `R5B8B-QR-CI-001`：只有在用户明确授权发布后才能核验远端 CI。

## Research Boundary

本报告只审查证据、字段、模型输入与工作流状态，不构成任何交易建议。
