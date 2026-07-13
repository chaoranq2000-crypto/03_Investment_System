# Workflow Readout: wf_20260703_stock_first_002837_invic

## 当前状态

| field | value |
|---|---|
| workflow_type | `stock_first_closed_loop` |
| object | `002837 英维克` |
| status | `accepted_with_todos` |
| quality_target | `R5_bundle9r_model_generation_locked` |
| current_stage | `R5_bundle9r_closed` |
| input_evidence_generation | `evidence_gen_r5_bundle8r_231a51f4673156df` |
| model_generation | `model_gen_r5_bundle9r_1cd42241e6a38fb3` |
| canonical_reader | `stale_pending_bundle10r` |
| sample_quality_allowed | `false` |
| P2 | `false`；未进入 |
| next_bundle | `R5_BUNDLE_10R_READER_REBUILD`；允许但未启动 |

本文件是当前 canonical workflow readout。旧 Bundle 9、旧 Bundle 10、Reader v3 及其人工审阅记录继续作为历史快照保留；新 9R 模型代际已改变其输入，因此旧 Reader 不再提供当前 sample-quality 许可。

## 本轮技能路由

- `research-orchestrator`：最新补丁发现、代际纠偏、状态迁移、三次 handoff、关闭锁与台账同步。
- `stock-deep-dive`：输入审阅、45 条预测假设、三分部驱动、完整报表桥、情景与敏感性、集成 model pack。
- `company-valuation`：市场分母、低置信度同业上下文、反向估值、三情景估值和方法资格。
- `quality-review`：代际/算术/claim boundary/无动作建议门、负向变异回归与关闭判定。

## 当前 9R 核心产物

| artifact | status |
|---|---|
| `R5_bundle8r_evidence_generation_lock_v2.yaml` | 6 个输入；缺失 0；当前 forward evidence generation |
| `R5_bundle9r_input_review_ledger.yaml` | 2025A / 2026Q1 官方锚点已核对；缺口显式 |
| `R5_bundle9r_forecast_assumption_registry.yaml` | 45 条 reviewed estimate assumptions |
| `R5_bundle9r_segment_driver_model.yaml` | 3 分部 × 3 情景 × 3 年；液冷分析视图不加总 |
| `R5_bundle9r_financial_statement_bridge.yaml` | 6 个显式经营科目；禁用平衡项不存在 |
| `R5_bundle9r_sensitivity.csv` | 12 条单变量、9 条双变量 |
| `R5_bundle9r_consensus_comparison.csv` | 10—12 家机构；`analyst_view` |
| `R5_bundle9r_peer_operating_reconciliation.yaml` | `LOW_CONFIDENCE_PEER_SET`；禁止排名 |
| `R5_bundle9r_market_snapshot.yaml` | 市值与收盘价×股本核对通过 |
| `R5_bundle9r_reverse_valuation.yaml` | 当前市场值所需经营表现的 inference |
| `R5_bundle9r_scenario_valuation.yaml` | bear/base/bull 研究情景范围 |
| `R5_bundle9r_model_pack.yaml` | 预测与估值统一 contract pack |
| `R5_bundle9r_quality_scorecard.yaml` | `pass`；critical=0；high=0 |
| `R5_bundle9r_model_generation_lock.yaml` | 13 个 artifact；缺失 0；aggregate `1cd42241…acd54cc` |
| `R5_bundle9r_close_readout.md` | `accepted_with_todos` |

完整路径、owner、stage 与状态以 `artifact_manifest.csv` 为准。

## 质量与验证

| gate/check | result |
|---|---|
| package integrity | 34/34 checksums pass |
| evidence-generation binding | pass；6 个锁定输入哈希一致 |
| official anchor reconciliation | 2025A、2026Q1 收入与归母净利润匹配发行人直接披露 |
| model quality | pass；0 critical / 0 high |
| scenario monotonicity | pass；收入、归母利润、情景权益价值均 bear <= base <= bull |
| market denominator | pass；relative difference `0.00006752%` |
| negative mutations | pass；13 类核心错误均 fail-closed |
| deterministic rebuild | 12 个生成文件连续两次重建，hash change=0 |
| focused compatibility regression | 38 passed |
| full repository pytest | 674 passed，2 skipped，28.56 秒 |

## 保留缺口

当前 9R 关闭新增 5 个 medium TODO，均已写入 `open_todos.csv`：独立液冷经济性、驱动转换、同业纯度/官方经营口径、DCF 输入、SOTP 输入。每项均含 owner 和 next action；没有活动 critical/high issue。

## 历史状态说明

旧 Bundle 10 的 Reader v3 曾完成精确哈希人工审阅，该事件与相关 close 对象没有被改写。Bundle 8R 之后的前向证据与 9R 模型代际已经变化，因此旧 Reader 只能作为历史快照；恢复 sample-quality 需要后续 Bundle 10R 基于 `R5_bundle9r_model_generation_lock.yaml` 重建并完成新的精确哈希审阅。

## 关闭边界

本轮只执行最新 Bundle 9R 补丁计划。未启动 Bundle 10R，未进入 P2，未执行暂存、提交、推送或远端 CI，也没有删除或覆盖历史 Bundle 9/10 产物。
