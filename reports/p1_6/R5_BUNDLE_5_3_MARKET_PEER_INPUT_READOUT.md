# R5 Bundle 5.3 — Market and Peer Input Readout

status: accepted_low_confidence_peer_set

## result

- workflow_id: `wf_20260703_stock_first_002837_invic`
- stock_code: `002837`
- market_date: `2026-07-10`
- reviewer: `codex`
- reviewed_at: `2026-07-12T01:30:52.1451973+08:00`
- source_evidence_id: `ev_structured_market_data_002837_20260710_eb0c08`
- market_snapshot_records: `1`
- peer_snapshot_records: `6`
- peer_set_quality: `low`
- canonical_registry_changed: `false`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`

## normalization

- Close is stored as CNY/share.
- Tushare `total_share`, `float_share` and `free_share` are multiplied by 10,000 to produce shares.
- Tushare `total_mv` and `circ_mv` are multiplied by 10,000 to produce CNY.
- PE, PE TTM, PB, PS and PS TTM remain multiples.
- Market capitalization uses source-reported `total_mv * 10,000`; it is not silently recomputed from rounded close and shares.

## peer_selection

- Included: `301018 申菱环境` (product exposure score 4), `300499 高澜股份` (product exposure score 3).
- Excluded: `300731 科创新源`, `300602 飞荣达` because the current local universe records lower-scored technology-level exposure.
- Selection was completed from the exposure universe before inspecting valuation multiples.
- Two peers are insufficient for a high-confidence relative-valuation set; downstream use must retain the low-confidence label.

## boundaries

The snapshot is a dated market context, not a live/current quote beyond 2026-07-10. Trailing multiples are not forward estimates. No registry promotion or transaction instruction was produced.

## owner_card_truthfulness_recheck_2026_07_12

status: pass_with_low_confidence_peer_set

### files_added

- `scripts/build_r5_bundle5_market_peer_onboarding.py`
- `data/raw/market_data/tushare_daily_basic_peer_set_2026-07-10_eb0c080a.json`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_peer_set_review.yaml`
- `tests/test_r5_bundle5_market_peer_onboarding.py`

### files_modified

- none; the raw snapshot is immutable and the candidate records were added under their owned paths.

### commands_run

- `.\\.conda\\investment-system\\python.exe -m pytest -q tests\\test_r5_bundle5_market_peer_onboarding.py --tb=short -p no:cacheprovider`

### exit_code

- focused_test_exit_code: `0`

### stdout_or_stderr_summary

- `5 passed in 0.71s`
- raw_market_sha256: `eb0c080aeee371d92ae9fe9212a373fb6a2944a350c226e291bdc41ad226766e`
- peer_review_sha256: `8e0f51d1d3da5bd88e99fd50d5e2ff80993b4b5e3eda07917fe284bac521a7ac`
- inventory_status: `1 accepted market record; 6 accepted peer-metric records; 2 included peers`.

### known_todos

- The two-company peer set remains low confidence; PS and PS TTM must remain separate definitions.

### next_recommended_patch

- Use the same-date inputs only as dated context and retain peer comparability limitations.
