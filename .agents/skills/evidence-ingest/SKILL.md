---
name: evidence-ingest
description: A股投研证据导入、下载、归档、解析、登记与候选生成。当用户要求导入公告、年报、研报、网页、CSV/XLSX、行情/财务结构化数据、URL 或手动材料时使用。不得用于投资结论、评分、watchlist 决策或报告叙事写作。
---

# Evidence Ingest Skill

## Goal

Turn raw materials, official disclosures, URLs and structured data snapshots into auditable evidence records, processed outputs, draft claim/metric candidates and ingest logs.

The output of this skill is **not** a research conclusion. It is an evidence package that later skills may review.

## When to use

Use this skill for:

- importing or registering local files, URLs, PDFs, CSV/XLSX, Markdown/TXT or HTML snapshots;
- downloading or registering official disclosures such as annual reports, interim reports, quarterly reports, announcements and exchange inquiry replies;
- pulling structured market/financial data snapshots from approved adapters such as Tushare or Baostock;
- creating a stock evidence plan for `stock_first_closed_loop`;
- deduplicating evidence by hash;
- validating `data/manifests/evidence_manifest.csv`;
- generating draft `claim_candidates` or `metric_candidates` for later review.

## Responsibilities

- classify input materials into evidence, metric snapshots or clues;
- discover and acquire raw files or snapshots;
- compute hashes and enforce duplicate handling;
- preserve raw files or snapshots according to archive policy;
- write processed text, table, page-map or parse-log outputs when applicable;
- register manifest rows and draft candidates;
- validate manifest, path, candidate and no-advice gates;
- report missing metadata, parse failures and follow-up TODOs explicitly.

## Out of scope

Do not use when the requested task is a research conclusion rather than evidence-layer work.

Do not use this skill for:

- writing segment reports or stock reports;
- scoring segments or companies;
- deciding watchlist inclusion/exclusion;
- making buy/sell/hold recommendations;
- converting clues directly into material claims;
- proving business exposure from structured API snapshots alone.

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

Read these for data-layer and source-adapter routing tasks:

- `references/source_adapter_matrix.md`
- `references/evidence_acquisition_resilience.md`
- `references/a_stock_data_method_adoption.md`
- `references/structured_data_adapter_contract.md`
- `references/market_context_snapshot_contract.md`
- `references/data_layer_quality_gate.md`

Read these for stock-led evidence download tasks:

- `references/stock_evidence_plan.md`
- `references/official_disclosure_download.md`
- `references/structured_api_pull_runner.md`

Read adapter notes only when relevant:

- `references/adapter_notes/cninfo_sse_szse.md`
- `references/adapter_notes/tushare.md`
- `references/adapter_notes/baostock.md`

## Supported ingest modes

| ingest_mode | Use | First implementation status |
|---|---|---|
| `manual_file` | Register a local file with metadata | B1 supported |
| `local_dir_batch` | Batch register a local folder | B1 supported |
| `url_file` | Download or snapshot URL material | B1 supported |
| `official_disclosure_search` | Find/download/register official filings | B1.5/B2 focused |
| `structured_api_pull` | Pull or register structured market/financial snapshots | B1/B1.5 supported |
| `web_page_snapshot` | Save a webpage snapshot | Interface definition |
| `clue_search` | Log news/social/search clues | Interface definition |
| `refresh_watchlist` | Discover new evidence for existing watchlist | Interface definition |

## Standard workflow

Every ingest mode follows this chain:

```text
discover → capability_route → source_health_check → acquire_with_independent_fallback
→ schema_fingerprint → hash_dedup → archive_raw → parse_or_snapshot
→ classify_source → assign_reliability_rank → register_manifest
→ generate_candidates → validate_manifest → output_ingest_log
```

Routing and acquisition rules:

- Build `adapter_run_queue.yaml` from `config/evidence_source_routes.yaml`; do not let a
  report writer or research analyst call public endpoints directly.
- Use official sources for material company facts; structured databases remain metric-only;
  fund flow, hotlists, news and social data remain context or clues.
- Prefer independent fallback domains instead of multiple endpoints with the same failure mode.
- Public HTTP adapters are serial by default, reuse a session/opener, apply bounded retry with
  jitter, respect `Retry-After`, and do not immediately retry `401/403/404`.
- Record source health and schema drift. A circuit-open or quarantined source must be skipped
  until the ledger permits another attempt.
- Live acquisition must be explicitly enabled. Dry-run planning is the safe default.

## Stock-first evidence workflow

For `stock_first_closed_loop`, use this sequence:

```text
stock_evidence_plan
→ official_disclosure_download_or_register
→ structured_api_pull_snapshot
→ manifest / candidates / ingest_log
→ handoff to stock-deep-dive
```

Minimum stock evidence package:

```text
1. latest annual report or explicit TODO;
2. latest interim/quarterly report or explicit TODO;
3. material announcements within date range or explicit TODO;
4. structured financial snapshots as metric candidates;
5. optional IR/company website/news clues marked with their source rank.
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

Use scripts from `scripts/` and `src/ingest/` as applicable:

```text
compute_hash.py
validate_manifest.py
check_paths.py
validate_candidates.py
write_ingest_log.py
run_debug_cases.py
src/ingest/stock_evidence_plan_runner.py
src/ingest/official_disclosure_pull.py
src/ingest/structured_api_pull.py
src/ingest/source_routing.py
src/ingest/source_health.py
src/ingest/acquisition_orchestrator.py
scripts/build_evidence_acquisition_plan.py
scripts/run_source_route_quality_gate.py
```

## Guardrails

- Raw files are immutable. Never overwrite raw evidence with different content.
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
- [ ] Structured API snapshots are metric-only unless separately verified by official disclosure.
- [ ] D-level sources produce only clues or TODOs.
- [ ] Source routes have independent fallbacks and no circuit-open source is scheduled.
- [ ] Observed fields match the endpoint schema fingerprint or a schema-drift issue is emitted.
- [ ] Live public HTTP acquisition is serial, bounded and explicitly enabled.
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
