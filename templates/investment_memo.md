# Investment Memo / 观察备忘录

> 本备忘录用于记录研究假设、观察清单和后续验证问题，不构成任何买入、卖出、持有或其他交易建议。

## Metadata

| Field | Value |
|---|---|
| memo_id | memo_<topic>_<YYYY-MM-DD> |
| report_type | memo |
| topic | <topic> |
| linked_segments | <segment_id list> |
| linked_companies | <company_id list> |
| report_date | <YYYY-MM-DD> |
| evidence_snapshot | <evidence_id list> |
| claim_ids | <claim_id list> |
| confidence | high / medium / low |
| status | current / needs_refresh / archived |

## Evidence Snapshot

| evidence_id | source_type | title | publish_date | reliability_rank | status | source_path |
|---|---|---|---|---|---|---|
| <evidence_id> | <type> | <title> | <date> | A/B/C/D | fresh/stale | <path> |

## Observation

- fact: <事实；证据：evidence_id=<id>; claim_id=<id>>
- estimate: <估计；证据：evidence_id=<id>; method=<method>>
- inference: <研究推断；confidence=<level>>
- opinion: <观点；说明不确定性和反证>

## Thesis

| thesis_id | thesis_text | supporting_claim_ids | contradicting_claim_ids | key_assumptions | status |
|---|---|---|---|---|---|
| <thesis_id> | <hypothesis> | <claim_ids> | <claim_ids or TODO> | <assumptions> | active/weakened/strengthened/invalidated |

## Facts

| Fact | evidence_id | claim_id | confidence | notes |
|---|---|---|---|---|
| <fact> | <evidence_id> | <claim_id> | <level> | <notes> |

## Estimates / Inferences

| Item | claim_type | Method / Basis | evidence_id | confidence |
|---|---|---|---|---|
| <item> | estimate/inference/opinion | <method> | <evidence_id or TODO> | <level> |

## Risks / Counter-evidence

| Risk / Counter-evidence | Related thesis_id | evidence_id | Impact | Follow-up |
|---|---|---|---|---|
| <risk> | <thesis_id> | <evidence_id or TODO> | <impact> | <task> |

## Watchlist Impact

| Action | Object type | Object ID | Reason | evidence_ids | Reviewer | Notes |
|---|---|---|---|---|---|---|
| add/remove/upgrade/downgrade/pause | segment/company/metric | <id> | <reason> | <ids or TODO> | <name> | <notes> |

## TODO / Missing Data

- TODO: 需要补充证据 - <item>
- MISSING: 暂无直接披露 - <item>
- LOW_CONFIDENCE: 当前证据质量不足 - <item>
- UNVERIFIED: 尚未核验 - <item>

## Evidence Map

| Claim / Memo section | evidence_id | claim_id | metric_id | source_path | status |
|---|---|---|---|---|---|
| <section> | <evidence_id> | <claim_id> | <metric_id> | <path> | fresh/stale |

## Next Review

- next_review_date:
- validation_metrics:
- source_to_monitor:
- refresh_log:
