# Field Dictionary

## Manifest fields

| Field | Definition |
|---|---|
| `evidence_id` | Stable evidence key, generated according to `evidence_id_naming.md`. |
| `source_type` | Source type enum from `source_types.md`. |
| `source_name` | Registry key, such as `cninfo`, `sse`, `szse`, `tushare`, `baostock`, `news`. |
| `source_group` | Broad source group: official disclosure, structured database, clue, etc. |
| `title` | Source title or generated snapshot title. |
| `publisher` | Original publisher or provider. |
| `publish_date` | Publication date of the source, if applicable. |
| `retrieved_at` | Date/time when the source was retrieved. |
| `ingested_at` | Date/time when the evidence was registered. |
| `as_of_date` | Effective date for structured snapshots or market data. |
| `entity_type` | `segment`, `company`, `security`, `market`, `macro`, `policy`, `unknown`. |
| `entity_id` | Canonical entity ID if known. |
| `segment_id` | Segment ID if evidence is segment-scoped. |
| `company_id` | Company ID if company-scoped. |
| `stock_code` | A-share stock code if known. |
| `source_url` | URL of source page/file/API documentation/query endpoint. |
| `raw_file_path` | Repository-relative path to archived raw source/snapshot. |
| `raw_archive_policy` | Archive policy enum. |
| `file_hash` | Hash of raw file bytes. |
| `content_hash` | Hash of normalized content or extracted text. |
| `api_params_hash` | Hash of API source/endpoint/params/fields. |
| `processed_text_path` | Path to extracted text or Markdown snapshot. |
| `processed_table_path` | Path or directory/pattern for extracted tables. |
| `page_map_path` | Locator map from processed output to source page/section/table. |
| `page_count` | Page count or sheet count where applicable. |
| `language` | Primary language, usually `zh-CN`. |
| `file_format` | `pdf`, `html`, `csv`, `xlsx`, `md`, `txt`, `json`, `parquet`, `unknown`. |
| `ingest_mode` | Mode from `ingest_modes.md`. |
| `reliability_rank` | `A`, `B`, `C`, `D`, `unknown`. |
| `material_claim_allowed` | `true`, `false` or `metric_only`. |
| `allowed_claim_types` | Pipe-separated or semicolon-separated claim type list. |
| `license_note` | License, copyright or archiving limitation note. |
| `stale_after` | Duration/date when source should be refreshed or reviewed. |
| `status` | Evidence lifecycle state. |
| `parse_status` | Parsing state. |
| `candidate_status` | Candidate generation state. |
| `review_status` | Review state. |
| `previous_evidence_id` | Prior version if this supersedes an earlier source. |
| `superseded_by` | Later evidence ID if this row is superseded. |
| `notes` | Free-text limitations, TODOs or manual review comments. |

## Date format

Prefer ISO-8601:

- Date: `YYYY-MM-DD`
- Datetime: `YYYY-MM-DDTHH:MM:SSZ`

Do not use unexplained future dates for `ingested_at`, `retrieved_at` or `generated_at`.
