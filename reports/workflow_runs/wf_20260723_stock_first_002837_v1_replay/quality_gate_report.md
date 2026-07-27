# 002837 V1 replay quality gate report

## 结论

离线闭环可复现，canonical 研究状态为 `needs_fix`。G3 与 G6 非补偿失败；其余门禁不能抵消这四项 high 研究缺口。

## G0-G10

| gate | status | evidence / limitation |
|---|---|---|
| G0 | pass | stock, scope, source run, target run and offline boundary are explicit |
| G1 | pass | two official and two structured sources exist and match frozen hashes |
| G2 | pass | no new claim is promoted; claim-type boundary remains explicit |
| G3 | fail | nine operating drivers remain unqualified; structured candidates remain draft |
| G4 | pass | existing ai_server_liquid_cooling segment definition is hash-bound |
| G5 | not_applicable | stock-first replay does not rebuild the company universe |
| G6 | fail | two liquid-cooling overlap adjustments remain missing |
| G7 | pass | the run-scoped report exposes gaps and source boundaries without unsupported conclusions |
| G8 | pass | all high gaps have owner, target and next step; no global state is changed |
| G9 | pass | no trading instruction, position sizing or certainty claim is present |
| G10 | pass | canonical state, TODOs, manifest, quality report and readout are materialized |

## Open high issues

- `R5B13R-G3-001` / G3 / owner `evidence-ingest`: room_cooling 与 cabinet_cooling 的 volume、unit_price、product_mix 共六项缺少同期间同口径量化证据。 Next: source_local_check=QR-B13R-DRIVER-ROOM-CABINET; next_step=等待发行人定期报告、IR或产品附注披露；公司级销量和混合单价不得替代。
- `R5B13R-G3-002` / G3 / owner `evidence-ingest`: data_center_liquid_cooling_related 的 unit_value、acceptance_rate、gross_margin 共三项缺失。 Next: source_local_check=QR-B13R-DRIVER-LIQUID; next_step=等待合同/招标、验收会计口径和独立毛利披露；累计1.2GW及2024A约3亿元不能推导这些驱动。
- `R5B13R-G6-001` / G6 / owner `stock-deep-dive`: room_cooling 与 data_center_liquid_cooling_related 已分类为 overlaps，但收入和毛利扣减均为 missing。 Next: source_local_check=QR-B13R-OVERLAP-ROOM-LIQUID; next_step=先由evidence-ingest取得同期间可核验分配证据，再由stock-deep-dive更新allocation；当前禁止相加。
- `R5B13R-G6-002` / G6 / owner `stock-deep-dive`: cabinet_cooling 与 data_center_liquid_cooling_related 已分类为 overlaps，但收入和毛利扣减均为 missing。 Next: source_local_check=QR-B13R-OVERLAP-CABINET-LIQUID; next_step=先由evidence-ingest取得同期间可核验分配证据，再由stock-deep-dive更新allocation；当前禁止相加。

## Boundaries

No historical human decision is transferred. `sample_quality_ready=false`, `p2_ready=false`, `release_ready=false`. No direct trading instruction is produced.
