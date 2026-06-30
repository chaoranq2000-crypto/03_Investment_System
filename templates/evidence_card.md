# Evidence Card

## Metadata

| Field | Value |
|---|---|
| evidence_id | <source_type>_<entity>_<date>_<short_hash> |
| source_type | annual_report / announcement / exchange_data / regulator_statistics / industry_report / brokerage_report / transcript / news / other |
| source_name | <source> |
| title | <title> |
| publisher | <publisher> |
| publish_date | <YYYY-MM-DD> |
| ingested_at | <YYYY-MM-DD> |
| file_hash | <hash> |
| raw_file_path | data/raw/<category>/<file> |
| processed_text_path | data/processed/text/<file> |
| reliability_rank | A / B / C / D |
| status | fresh / stale / superseded / contradicted / low_confidence |
| license_note | <license or usage note> |

## Evidence Snapshot

- 原始文件：
- 加工文本：
- 表格路径：
- 关联对象：
- 证据摘要：

## Extracted Facts

| claim_id | claim_text | claim_type | page_no / locator | confidence |
|---|---|---|---|---|
| <claim_id> | <fact> | fact | <page/section> | high/medium/low |

## Estimates / Inferences

| claim_id | claim_text | claim_type | Method / Basis | confidence |
|---|---|---|---|---|
| <claim_id> | <estimate or inference> | estimate/inference | <method> | <level> |

## Metrics

| metric_id | metric_name | period | value | unit | calculation_method | is_estimate |
|---|---|---|---:|---|---|---|
| <metric_id> | <metric> | <period> | <value> | <unit> | <method> | true/false |

## Risks / Counter-evidence

| Issue | Related claim_id | Evidence | Notes |
|---|---|---|---|
| <risk or conflict> | <claim_id> | <evidence_id> | <notes> |

## TODO / Missing Data

- TODO: 需要补充证据 - <item>
- MISSING: 暂无直接披露 - <item>
- LOW_CONFIDENCE: 当前证据质量不足 - <item>
- UNVERIFIED: 尚未核验 - <item>

## Evidence Map

| Object | Object ID | Link type | Notes |
|---|---|---|---|
| Segment / Company / Claim / Metric | <id> | supports / contradicts / updates | <notes> |
