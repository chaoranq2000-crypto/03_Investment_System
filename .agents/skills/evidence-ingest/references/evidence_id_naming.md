# Evidence ID Naming

## Format

```text
ev_<source_type>_<entity_or_scope>_<date>_<short_hash>
```

Examples:

```text
ev_annual_report_002837_2025_8f3a91
ev_announcement_300731_20240618_a9c204
ev_structured_market_data_tushare_002837_20260630_7bd2aa
ev_third_party_research_liquid_cooling_20250520_4ab883
```

## Components

- `source_type`: normalized source type enum.
- `entity_or_scope`: stock code, company ID, segment ID, source name or `market`/`macro`.
- `date`: `publish_date`, `as_of_date` or `retrieved_at` date.
- `short_hash`: first 6-10 characters of SHA-256 from raw file, content or API parameter hash.

## Rules

1. Do not derive identity only from title text.
2. Same raw content must not create multiple active evidence IDs.
3. If the same URL changes content, create a new evidence ID and set `previous_evidence_id`.
4. API snapshots must include `api_params_hash` in the hash source.
5. If an evidence row is a duplicate, set `status=duplicate` and record duplicate details in ingest log.
