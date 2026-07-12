# R5 Bundle 5.1 — Real Input Inventory and Provenance Readout

status: completed_official_anchor_ready_for_card_5_2

## close_decision

- workflow_id: `wf_20260703_stock_first_002837_invic`
- stock_code: `002837`
- reviewed_input_dropzone_files: `0`
- reviewed_input_records: `0`
- valid_accepted_core_input_types: `0/5`
- card_5_1_inventory_completed: `true`
- card_5_1_stop_condition_triggered: `false`
- card_5_2_allowed: `true`
- broad_core_G1_evidence_gate: `fail`
- promotion_allowed: `false`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`

Card 5.1 is closed as an inventory card. The five reviewed-input types are not yet accepted, so the broad core-input G1 gate remains failed. The card's narrower transition gate now passes because a real source-rank A official-disclosure chain has immutable physical evidence. This authorizes Card 5.2 onboarding only; it does not authorize registry promotion.

## authorization_boundary

- authorized_by: `workspace_user`
- authorization_text: `授权`
- authorization_date: `2026-07-12`
- reviewer_identity_for_actual_reviews: `codex`
- audit_handoff: `reports/workflow_runs/wf_20260703_stock_first_002837_invic/handoffs/08_to_evidence-ingest_bundle5_authorized_restart.md`

Authorization permits acquisition and review of project-approved official disclosures and structured data. It does not permit fabricated evidence, automatic acceptance, sample-quality publication, P2 work, or trading advice.

## newly_archived_official_evidence

| evidence_id | disclosure | publication_date | physical_path | SHA256 | verification |
|---|---|---|---|---|---|
| `ev_annual_report_002837_20260421_2cbfc5` | 2025 annual report full text | 2026-04-21 | `data/raw/annual_reports/cninfo_2025_annual_report_full_002837_2026-04-21.pdf` | `2CBFC5DC8A60B01212B68D930FB06D0A25BD74563CD1942BD87161246C3A1472` | 196 pages, unencrypted |
| `ev_interim_report_002837_20250819_47054e` | 2025 interim report full text | 2025-08-19 | `data/raw/announcements/cninfo_2025_interim_report_full_002837_2025-08-19.pdf` | `47054E736C74130385E4CAB67F04708599C4BAE0DF5599B4446614039B3F0FFB` | 162 pages, unencrypted |
| `ev_quarterly_report_002837_20260421_2f00c7` | 2026 Q1 report | 2026-04-21 | `data/raw/announcements/szse_2026_q1_report_002837_2026-04-21.pdf` | `2F00C78F33E04EE476F633E57CA74DE635F090A91E7C238B2251E5F1B19ABD5C` | 11 pages, unencrypted |

All three files were downloaded from official CNINFO/SZSE disclosure URLs through `official_disclosure_pull.py`, registered in the global evidence manifest, and preserved under immutable raw paths. Download and PDF validation do not by themselves constitute reviewed-input acceptance.

## provenance_and_scope_review

- The two pre-existing 7-page PDFs remain annual-report summaries, not the 196-page annual report. Their identical SHA256 values are recorded as one provenance-alias group rather than independent evidence.
- Visual review confirmed the 2025 annual report's 2023–2025 company financial table and the 2025/2024 broad product-line revenue and gross-margin tables.
- The official tables disclose `机房温控节能产品` and `机柜温控节能产品`; they do not separately disclose liquid-cooling revenue share, liquid-cooling gross margin, or liquid-cooling profit contribution.
- Those liquid-cooling-specific fields therefore remain explicit `MISSING_DISCLOSURE`. Broader product categories must not be relabeled as liquid cooling.

## input_matrix

| input_type | accepted | current state | Card 5.1 decision |
|---|---:|---|---|
| `business_disclosure` | 0 | five official candidates resolve physically; three are newly archived full/current filings | Card 5.2 authorized for manual review and onboarding |
| `market_snapshot` | 0 | no reviewed record yet | remains blocking for later core completion |
| `peer_snapshot` | 0 | no reviewed record yet | remains blocking for later core completion |
| `forecast_assumptions` | 0 | no reviewed record yet | remains blocking for later core completion |
| `valuation_inputs` | 0 | no reviewed record yet | remains blocking for later core completion |
| `sentiment_event_sources` | 0 | optional, no reviewed record | non-blocking optional gap |

The complete record-level matrix, source request IDs, physical-path status, duplicate-hash aliases, registry targets, missing fields, and hard-boundary flags are in `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_real_input_inventory.yaml`.

## focused_contract_fix

The initial Bundle 5.1 implementation incorrectly required all five accepted core input types before setting `card_5_2_allowed`, creating a circular prerequisite across Cards 5.2–5.4. The focused fix now follows the task card:

- annual, interim, quarterly, announcement, and official-disclosure source types are eligible candidates;
- transition to Card 5.2 requires at least one source-rank A, non-fixture, physically resolved official candidate;
- an empty dropzone triggers the stop condition only when no such real official anchor exists;
- G1, promotion, sample-quality, and P2 gates remain unchanged.

## validation

- dropzone validator: `pass checked_files=0 accepted=0 accepted_degraded=0 pending=0 rejected=0 failed=0`; this is a format result, not an acceptance result.
- inventory: `status=blocked_source_gapped core=0/5 records=0`, with `stop_condition=false` and `card_5_2_allowed=true`.
- focused tests: `19 passed`.
- `git diff --check`: pass.

## active_issues

| issue_id | severity | owner | next_action |
|---|---|---|---|
| `B5-G1-BUSINESS-001` | high | `evidence-ingest` + `codex` reviewer | Review the newly archived filings, create accepted business-disclosure records, and rebuild candidate subpacks in Card 5.2. |
| `B5-G1-MARKET-001` | high | `evidence-ingest` + `codex` reviewer | Archive and review a dated, unit-safe market snapshot in Card 5.3. |
| `B5-G1-PEER-001` | high | `evidence-ingest` + `codex` reviewer | Review an evidence-backed peer set and same-date metrics in Card 5.3. |
| `B5-G1-FORECAST-001` | high | `stock-deep-dive` + `codex` reviewer | Derive transparent forecast assumptions only after Cards 5.2–5.3 pass. |
| `B5-G1-VALUATION-001` | high | `company-valuation` + `codex` reviewer | Apply fail-closed method eligibility after upstream inputs are reviewed. |
| `B5-G1-LIQUID-SPLIT-001` | medium | `evidence-ingest` | Keep liquid-cooling-specific revenue, margin, and profit fields visible as `MISSING_DISCLOSURE`. |

## next_card

Proceed to Card 5.2 only. Canonical registries remain read-only until Card 5.5.

## owner_card_truthfulness_recheck_2026_07_12

status: pass_after_real_input_onboarding

### files_added

- `scripts/build_r5_bundle5_real_input_inventory.py`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_real_input_inventory.yaml`
- `tests/test_r5_bundle5_real_input_inventory.py`

### files_modified

- `tests/test_r5_bundle5_real_input_inventory.py` was reconciled to the post-promotion ledger state of 22 accepted inputs.

### commands_run

- `.\\.conda\\investment-system\\python.exe -m pytest -q tests\\test_r5_bundle5_real_input_inventory.py --tb=short -p no:cacheprovider`

### exit_code

- focused_test_exit_code: `0`

### stdout_or_stderr_summary

- `8 passed in 0.52s`
- inventory_sha256: `0f792fd5c3863b429bb91a3d7f87a2e0acb205254c79184f9b91cd8ab773680e`
- inventory_status: `ready_for_later_promotion_card`
- Final reconciliation: 5/5 core input types, 22 accepted records and 22 accepted ledger rows. Earlier zero-record lines above describe the initial Card 5.1 snapshot before Cards 5.2-5.5 supplied and promoted the inputs.

### known_todos

- Liquid-cooling-specific revenue, margin and profit fields remain `MISSING_DISCLOSURE`.

### next_recommended_patch

- Continue through the already authorized Bundle 5 task order; do not infer sample-quality or P2 readiness from inventory completeness.
