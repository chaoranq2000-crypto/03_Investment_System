# Ingest Modes

Every ingest mode must stop at evidence outputs: manifest rows, raw/processed files, draft candidates and logs.

## Shared execution chain

```text
discover
→ acquire
→ hash_dedup
→ archive_raw
→ parse_or_snapshot
→ classify_source
→ assign_reliability_rank
→ register_manifest
→ generate_candidates
→ validate_manifest
→ output_ingest_log
```

## Modes

| ingest_mode | Input | Output | B1 status |
|---|---|---|---|
| `manual_file` | Local PDF/CSV/XLSX/MD/TXT + metadata. | raw copy, processed outputs, manifest row, optional candidates. | Must support. |
| `local_dir_batch` | Directory + default metadata. | manifest increment, duplicate skips, logs. | Must support. |
| `url_file` | URL + metadata. | downloaded/snapshotted raw file, manifest row, processed outputs. | Must support contract; implementation can be minimal. |
| `official_disclosure_search` | stock/company/keyword/date/source. | official PDF candidates and manifest candidates. | Define now; strengthen in B1/B2. |
| `structured_api_pull` | source/api/params/fields/date range. | raw snapshot, parameter hash, metric candidates. | Must support contract. |
| `web_page_snapshot` | webpage URL + source_type. | HTML/Markdown snapshot, manifest/clue. | Optional light support. |
| `clue_search` | keyword/segment/company/date. | clue list and TODOs. | Interface only in B1. |
| `refresh_watchlist` | watchlist/segment/company/stale_after. | new/stale evidence candidates. | Interface only in B1; P3 strengthens. |

## Mode-specific rules

### manual_file

- Preserve original file under `data/raw/<bucket>/`.
- Compute `file_hash` and `content_hash`.
- Generate `evidence_id` from source type/entity/date/hash.
- Parse safely based on format.
- Record source metadata explicitly.

### local_dir_batch

- Process files one by one using `manual_file` rules.
- Do not create active duplicate rows for identical hashes.
- Log `SKIPPED_DUPLICATE` with `duplicate_of` in ingest log.

### url_file

- Keep `source_url` separate from `raw_file_path`.
- Save raw downloaded file or snapshot where license allows.
- If download fails but metadata is useful, use `metadata_only` or `evidence_card_only` and block material claim usage.

### official_disclosure_search

- Prefer official disclosures from CNINFO/exchanges/company filings.
- A-level material claim support requires archived original or reliable official URL plus locator.
- Do not rely on third-party summaries when original filings are available.

### structured_api_pull

- Save raw API response as CSV/JSON/Parquet under `data/raw/market_data/`.
- Save API parameters and field list; compute `api_params_hash`.
- Generate `metric_candidates` only.
- Set `material_claim_allowed=metric_only`.

### clue_search

- Store as `clue` or TODO only.
- Add `TODO: verify with official disclosure` when relevant.
