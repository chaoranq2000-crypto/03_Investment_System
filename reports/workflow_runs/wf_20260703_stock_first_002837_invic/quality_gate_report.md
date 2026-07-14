# Current Quality Gate Routing

> **Current-state notice:** `R5_bundle10r_quality_gate_report_v5.md` 只记录自动门历史结果。Reader v5 的前次 `revision_required` 记录继续保留，随后外部人工复审已对同一精确哈希 8/8 项签署通过；当前 canonical 状态为 `accepted_with_todos`。`sample_quality_allowed=false`、`p2_allowed=false`。

| gate | current status |
|---|---|
| Bundle 10R Reader v5 automated gate | candidate_ready_for_human_review；100/82 |
| Truthfulness / core / candidate blockers | 0 / 0 / 0 |
| Narrative anti-template diagnostics | 6 chapters；31 paragraphs；0 repeated scaffold / process terms / similar pairs / thin sections |
| Human review | accepted；8/8；绑定 Reader v5 SHA256 `cb261412…1e6090` |
| Prior failed review | historical revision_required；独立记录保留，不覆盖 |
| Fix route | none；`R5B10R-V5-HUMAN-FAIL-001` 已由同一锁定 Reader 的复审通过关闭 |
| Workflow state schema | pass；0 open high；当前关闭项已统一为 `status=closed` |
| Required artifact resolution | 250/250；实际缺失 0 |
| Final-close remote CI | pass；commit `80f01fdf`；Actions run `29315103198` |
| Remaining TODOs | `R5B10R-DCF-001`、`R5B10R-SOTP-001` |
| Sample quality / P2 | false / false |

## Historical pre-Bundle 7 snapshot

> **Current-state notice:** this is a historical pre-Bundle 7 quality snapshot and is `historical_snapshot_superseded_by_bundle7_quality_rebaseline`. The current quality decision is recorded in `R5_bundle7_quality_gate_report.md`.

final_status: accepted_sample_quality
high_issues: 0
medium_issues: 0

| gate | status |
|---|---|
| G1 Evidence Completeness | pass |
| G2 Claim Locator | pass |
| G3 Metric Normalization | pass |
| G4 Business Breakdown | pass |
| G5 Segment Exposure | pass |
| G6/G7 Forecast Valuation | pass |
| G8 Technical Sentiment Event | pass |
| G10 No Unsupported Advice | pass |
| G11 Backflow Maintenance | pass |
