# Official Disclosure Download / Register Contract

## Purpose

`official_disclosure_download` is an acquire sublayer of `evidence-ingest`. It downloads or registers official filings and turns them into manifest rows.

It is not a research skill.

## Preferred sources

| Source | Typical use | Default rank |
|---|---|---|
| cninfo | A-share annual reports, interim reports, quarterly reports, announcements | A |
| sse | SSE issuer disclosures and inquiry replies | A |
| szse | SZSE issuer disclosures and inquiry replies | A |
| bse | BSE issuer disclosures | A |
| company_website | IR/product pages and company presentations | C unless official filing copy is clearly identified |
| manual | User-provided official file with metadata | depends on source metadata |

## Inputs

```text
stock_code
company_name
source_name
source_type
filing_type
title
publisher
publish_date
source_url or local_file
date_range
```

## Outputs

```text
data/raw/annual_reports/<file> for annual reports
data/raw/announcements/<file> for announcements, interim reports, quarterly reports and inquiry replies
data/manifests/evidence_manifest.csv
data/processed/logs/<evidence_id>__ingest_log.json
```

Optional after parsing:

```text
data/processed/text/<evidence_id>.md
data/processed/page_maps/<evidence_id>__page_map.csv
data/processed/tables/<evidence_id>__table_<n>.csv
data/manifests/claims_draft.csv
```

## Failure handling

- If URL download fails but metadata is reliable, write a metadata-only raw JSON and set status to `download_todo`.
- If local file exists and has same hash, mark duplicate/skipped rather than overwriting raw evidence.
- If local file exists with different content at target path, fail with high severity.
- If source is not official, do not assign A rank automatically.

## Claim boundary

Official disclosure can support material claims after parsing/review, but registering a filing is not itself a business claim.

Do not generate revenue exposure, customer, order, capacity or product claims unless the quote/page/table is actually extracted and reviewed.
