# Storage and Manifest Contract

## Directory layout

```text
data/
├── raw/
│   ├── official_disclosure/
│   ├── annual_reports/
│   ├── announcements/
│   ├── regulator_policy/
│   ├── industry_reports/
│   ├── company_ir_product/
│   ├── market_data/
│   ├── financial_data/
│   ├── web_snapshots/
│   └── user_uploaded/
├── processed/
│   ├── text/
│   ├── tables/
│   ├── page_maps/
│   ├── normalized/
│   ├── candidates/
│   │   ├── claim_candidates/
│   │   └── metric_candidates/
│   └── logs/
└── manifests/
    ├── evidence_manifest.csv
    ├── evidence_manifest.parquet
    ├── claims_draft.csv
    ├── claims_registry.csv
    ├── metrics_draft.csv
    ├── metrics_registry.csv
    ├── clue_log.csv
    └── ingest_runs.csv
```

CSV files must be normal multi-row CSV files, not a single long line.

## Evidence manifest fields

Use these fields in `data/manifests/evidence_manifest.csv`:

```csv
evidence_id,source_type,source_name,source_group,title,publisher,publish_date,retrieved_at,ingested_at,as_of_date,entity_type,entity_id,segment_id,company_id,stock_code,source_url,raw_file_path,raw_archive_policy,file_hash,content_hash,api_params_hash,processed_text_path,processed_table_path,page_map_path,page_count,language,file_format,ingest_mode,reliability_rank,material_claim_allowed,allowed_claim_types,license_note,stale_after,status,parse_status,candidate_status,review_status,previous_evidence_id,superseded_by,notes
```

## Required fields for every row

- `evidence_id`
- `source_type`
- `source_name`
- `title`
- `publish_date` or `as_of_date`
- `ingested_at`
- `raw_archive_policy`
- `file_hash` or `content_hash` or `api_params_hash`
- `ingest_mode`
- `reliability_rank`
- `material_claim_allowed`
- `status`
- `parse_status`
- `candidate_status`
- `review_status`
- `license_note`

## State enums

### status

```text
registered
active
duplicate
superseded
stale
contradicted
archived
failed
```

### parse_status

```text
not_required
pending
parsed
partial
failed
ocr_required
manual_required
```

### candidate_status

```text
not_generated
generated
partial
blocked
not_allowed
```

### review_status

```text
draft
needs_review
reviewed
accepted
accepted_with_todos
rejected
blocked
```

## Archive policy enum

```text
full_file_archived
snapshot_archived
metadata_only
evidence_card_only
not_archived_license
```

Rules:

1. A-level official disclosures should be `full_file_archived` whenever possible.
2. API pulls must be `snapshot_archived` and include `api_params_hash`.
3. Third-party reports with license restrictions must use metadata/evidence cards and cannot support high-confidence material claims alone.
4. `metadata_only` rows require `license_note` and `notes` explaining the limitation.

## Path rules

- `source_url` must be a URL or blank.
- `raw_file_path`, `processed_text_path`, `processed_table_path`, `page_map_path` must be repository-relative local paths or blank.
- Never store a URL in `raw_file_path`.
- If a processed path is filled, the file must exist.
- If `raw_archive_policy` is `full_file_archived` or `snapshot_archived`, `raw_file_path` should exist unless the row is `failed`.
