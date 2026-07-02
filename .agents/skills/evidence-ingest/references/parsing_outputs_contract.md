# Parsing Outputs Contract

## Purpose

Parsing converts source material into reviewable and locatable text/tables/page maps. It does not generate research judgments.

## Standard chain

```text
detect_format
→ extract_metadata
→ extract_text_or_snapshot
→ extract_tables_if_possible
→ build_page_or_section_map
→ normalize_units_and_dates_if_safe
→ write_processed_outputs
→ update_manifest_parse_status
→ write_parse_log
```

`normalize_units_and_dates_if_safe` means low-risk normalization only. Do not infer business exposure, revenue attribution or investment implications.

## File naming

```text
data/processed/text/<evidence_id>.md
data/processed/tables/<evidence_id>__table_<n>.csv
data/processed/page_maps/<evidence_id>__page_map.csv
data/processed/logs/<evidence_id>__parse_log.json
```

## Format handling

| Format | Required behavior |
|---|---|
| Text PDF | Extract text and page locators; table extraction optional but must be logged. |
| Scanned PDF | Mark `parse_status=ocr_required` or `manual_required`; do not pretend full parse. |
| HTML/webpage | Save raw snapshot; extract readable text; keep `source_url` separate from snapshot path. |
| CSV | Preserve raw file; produce normalized copy only if schema is clear. |
| XLSX | Preserve sheet names; each sheet/table should retain workbook locator. |
| MD/TXT | Preserve raw and section/paragraph locators. |
| API snapshot | Save raw response and API params; generate normalized metrics only when fields are explicit. |
| user note | Default to C/unknown until reviewed. |

## Page map fields

```csv
evidence_id,locator_type,page_no,section_title,paragraph_id,table_id,char_start,char_end,text_excerpt,processed_text_path,processed_table_path
```

## Table rules

1. Save tables as separate files, not only embedded in Markdown.
2. Every table needs `table_id`, source evidence ID, and page/sheet locator.
3. If table parse is partial, set parse status or parse log accordingly.
4. Preserve table titles, units and footnotes where available.
5. Do not convert units unless the original unit is explicit.
