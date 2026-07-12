# R5 Bundle 5.2 — Official Disclosure and Financial History Readout

status: accepted_with_visible_disclosure_gaps

## result

- workflow_id: `wf_20260703_stock_first_002837_invic`
- stock_code: `002837`
- reviewer: `codex`
- reviewed_at: `2026-07-12T01:17:59.6225085+08:00`
- accepted_business_disclosure_records: `9`
- financial_history_candidate: `accepted`
- business_breakdown_candidate: `accepted_with_todos`
- canonical_registry_changed: `false`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`

Three immutable source-rank A filings were verified by physical path and SHA256. The 2025 annual report supports 2023-2025 company financial history and broad product-line revenue/margin tables; the 2026 Q1 report supplies the latest company totals. Reported facts and arithmetic derivations are labeled separately.

## reconciliation

- 2025 reported company revenue: `6,067,759,091.55 CNY`.
- Sum of the five reported product revenue rows: `6,067,759,091.55 CNY`.
- Reconciliation residual: `0.00 CNY`.
- Room-cooling and cabinet-cooling gross profit are arithmetic derivations from reported revenue minus reported cost.

## disclosure_boundary

The issuer's financial tables use broad room-cooling and cabinet-cooling categories. They do not separately disclose liquid-cooling revenue share, gross margin, or profit contribution. Those three fields remain visible as `MISSING_DISCLOSURE`; no broad category was relabeled as liquid cooling.

## outputs

- `data/reviewed_inputs/wf_20260703_stock_first_002837_invic/business_disclosure/official_2025_annual_report.yaml`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_financial_history_candidate.yaml`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_business_breakdown_candidate.yaml`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_core_preflight_after_disclosure.yaml`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_business_disclosure_validation.json`

## next_card

Proceed to Card 5.3 for dated market and peer inputs. Canonical registries remain read-only.

## owner_card_truthfulness_recheck_2026_07_12

status: pass_with_visible_disclosure_gap

### files_added

- `scripts/build_r5_bundle5_official_disclosure_onboarding.py`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_financial_history_candidate.yaml`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_business_breakdown_candidate.yaml`
- `tests/test_r5_bundle5_official_disclosure_onboarding.py`

### files_modified

- `data/manifests/evidence_manifest.csv` gained reviewed official-disclosure provenance rows.

### commands_run

- `.\\.conda\\investment-system\\python.exe -m pytest -q tests\\test_r5_bundle5_official_disclosure_onboarding.py --tb=short -p no:cacheprovider`

### exit_code

- focused_test_exit_code: `0`

### stdout_or_stderr_summary

- `5 passed in 0.07s`
- financial_history_sha256: `2152703e713365ffe2ffd09c343e2204b9c820438c7e8ce6bcee11aceba220d6`
- business_breakdown_sha256: `c9fadb05b547baaed15a04eb2ab2b9d1397214dd84ff74c3cabd0b8b405afdf`
- reconciliation_checked=5 product revenue rows; residual `0.00 CNY`.

### known_todos

- The issuer does not separately disclose liquid-cooling revenue share, margin or profit contribution.

### next_recommended_patch

- Preserve the disclosure gap while consuming the accepted broad product-line facts in later Bundle 5 cards.
