---
name: evidence-ingest
description: A股投研证据导入、归档、解析、登记与候选生成。当用户要求导入公告、年报、研报、网页、CSV/XLSX、行情/财务结构化数据或手动材料时使用。不得用于投资结论、评分、watchlist 决策或报告叙事写作。
---

# Evidence Ingest Skill

## Goal

Turn raw materials and structured data snapshots into auditable evidence records, processed outputs, draft claim/metric candidates and ingest logs.

The output of this skill is not a research conclusion. It is an evidence package that later skills may review.

## When to use

- importing or registering local files, URLs, PDFs, CSV/XLSX, Markdown/TXT or HTML snapshots;
- pulling structured market/financial data snapshots from approved adapters such as Tushare or Baostock;
- deduplicating evidence by hash;
- validating `data/manifests/evidence_manifest.csv`;
- generating draft `claim_candidates` or `metric_candidates` for later review.

## Responsibilities

- classify input materials into evidence, metric snapshots or clues;
- compute hashes and enforce duplicate handling;
- preserve raw files or snapshots according to archive policy;
- write processed text, table, page-map or parse-log outputs when applicable;
- register manifest rows and draft candidates;
- validate manifest, path, candidate and no-advice gates;
- report missing metadata, parse failures and follow-up TODOs explicitly.

## Out of scope

Do not use when the requested task is:

- writing segment reports or stock reports;
- scoring segments or companies;
- deciding watchlist inclusion/exclusion;
- making buy/sell/hold recommendations;
- converting clues directly into material claims.

## Required references

Read these before execution:

- `references/source_types.md`
- `references/source_registry_contract.md`
- `references/ingest_modes.md`
- `references/storage_manifest_contract.md`
- `references/field_dictionary.md`
- `references/parsing_outputs_contract.md`
- `references/candidate_generation_contract.md`
- `references/ingest_quality_gate.md`
- `references/failure_handling.md`
- `references/structured_data_sources.md`

Read adapter notes only when relevant:

- `references/adapter_notes/cninfo_sse_szse.md`
- `references/adapter_notes/tushare.md`
- `references/adapter_notes/baostock.md`

## Supported ingest modes

- `manual_file`
- `local_dir_batch`
- `url_file`
- `official_disclosure_search`
- `structured_api_pull`
- `web_page_snapshot`
- `clue_search`
- `refresh_watchlist`

B1 must implement contracts and validation for `manual_file`, `local_dir_batch`, `url_file` and `structured_api_pull`. Other modes may remain interface definitions.

## Standard workflow

Every ingest mode follows this chain:

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

## Output contract

Write only evidence-layer outputs:

- raw files or snapshots under `data/raw/`;
- processed text/tables/page maps/logs under `data/processed/`;
- manifest rows under `data/manifests/evidence_manifest.csv`;
- draft candidates under `data/processed/candidates/` or `data/manifests/*_draft.csv`;
- clue rows under `data/manifests/clue_log.csv`;
- ingest run logs under `data/manifests/ingest_runs.csv` or `data/processed/logs/`.

Do not write final reports, scorecards, watchlist decisions or investment memos.

## Validation scripts

Use these scripts from `scripts/`:

```text
compute_hash.py          Calculate file hash for raw files or snapshots.
validate_manifest.py     Validate manifest fields, enums, dates, hashes and source/rank rules.
check_paths.py           Validate raw/processed/table/page-map paths and URL/path separation.
validate_candidates.py   Validate claim and metric candidate schemas and claim-type guardrails.
write_ingest_log.py      Write standardized ingest run logs.
run_debug_cases.py       Execute B1 debug fixtures and output PASS/FAIL/TODO readout.
```

## Guardrails

- Raw files are immutable. Never overwrite raw evidence.
- Every import must produce or update a manifest row.
- Tushare and Baostock outputs are metric snapshots by default; they do not replace official filings for business-exposure claims.
- D-level sources may only produce clues or TODOs.
- Candidate rows are draft until promoted by quality review.
- Missing data must be explicit. Do not invent page numbers, URLs, dates, revenue shares or evidence IDs.
- No buy/sell/hold language, target-price calls or trading instructions.

## Quality checklist

- [ ] Raw archive policy is valid and raw evidence is not overwritten.
- [ ] Manifest row has required fields, valid enums and stable hashes.
- [ ] Source rank and material-claim permission are compatible.
- [ ] URL fields and repository-relative local paths are separated.
- [ ] Processed outputs exist when paths are filled.
- [ ] Claim and metric candidates remain draft and respect source-rank limits.
- [ ] D-level sources produce only clues or TODOs.
- [ ] No buy/sell/hold recommendations or trading instructions are present.

## Readout format

After each run, report:

```text
run_id:
ingest_mode:
input_count:
result: SUCCESS | PARTIAL_SUCCESS | SKIPPED_DUPLICATE | FAILED
manifest_rows_created:
manifest_rows_updated:
duplicates_skipped:
processed_outputs:
claim_candidates:
metric_candidates:
clues:
issues_by_severity:
blocking_issues:
next_todos:
```
