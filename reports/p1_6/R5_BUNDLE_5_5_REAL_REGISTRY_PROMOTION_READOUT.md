# R5 Bundle 5.5 — Real Registry Promotion Readout

status: passed_reviewed_input_research_draft

## close_decision

- workflow_id: `wf_20260703_stock_first_002837_invic`
- stock_code: `002837`
- full_dropzone_validation: `pass`
- accepted_records: `22`
- accepted_degraded_records: `0`
- dry_run_status: `dry_run_ready`
- real_promotion_status: `accepted_inputs_promoted`
- second_identical_promotion: `accepted_inputs_unchanged`
- byte_level_idempotent: `true`
- semantic_idempotent: `true`
- physical_registry_readiness: `5/5 true`
- physical_registry_blockers: `0`
- allowed_report_level: `reviewed_input_research_draft`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`

Card 5.5 is the first Bundle 5 card that wrote the real workflow registries. The write used the existing atomic material writer after a no-write dry-run, pre-hash inventory and verified backups. No registry was hand-edited to simulate promotion.

## prepromotion_and_backup

| registry | pre-state | pre SHA256 | backup decision |
|---|---|---|---|
| `R5_market_peer_input_registry.yaml` | existing | `3363dae35cfbb063baa77ce796144aaa297570fb28adcb54871ff3361aa3d03a` | byte-identical backup created |
| `R5_forecast_assumption_registry.yaml` | existing | `3474d20d5ebc8f1d006088d01d657e565715b6995e5a56071d93a3cd6853ffcc` | byte-identical backup created |
| `R5_valuation_input_registry.yaml` | missing | `null` | missing pre-state recorded for rollback |
| `R5_evidence_request_review_ledger.yaml` | existing | `c3225cee58bc236f994acb8d24c0515c6c5311e8b2f169a10a95484f4b6afc37` | byte-identical backup created |

- prepromotion inventory: `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_prepromotion_inventory.yaml`
- backup manifest: `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_registry_backup_manifest.yaml`
- backup directory: `reports/workflow_runs/wf_20260703_stock_first_002837_invic/backups/r5_bundle5_pre_promotion_c7e2146bff39/`
- rollback test: focused test restored existing targets byte-for-byte and removed only a target explicitly recorded as missing before promotion.

## promotion_sequence

The initial promotion changed every registry relative to the recorded pre-state: market/peer, forecast and ledger were updated; valuation was created. A focused post-write regression then found that the forecast merge preserved a historical `forecast_model_interlock.expected_status: TODO_MODEL_INPUT` even though all five drivers were reviewed. The owned repair now drops that stale interlock when the candidate is fully reviewed and explicitly writes the fixed sample-quality/P2 caps.

The repair sequence was itself run as dry-run, real promotion and identical second promotion. Final hashes are:

| registry | final SHA256 | second action | physical validation |
|---|---|---|---|
| market/peer | `79bca54df269daadd0c956bf0c146ef751fe82f06b5ca6a955461e552b77e100` | unchanged | accepted |
| forecast assumptions | `040353bacb5fd07c223828d894ce764c328cade166173c4166531be9f36d9776` | unchanged | accepted |
| valuation inputs | `091a2c97a3dbf826e28eff9153432d03c016b7aa8c7a8076c52a175fca5928e4` | unchanged | validator-ready but globally capped below sample-quality |
| evidence review ledger | `020f72dfa35d99d4c74a966b9509cbbbf979311b64847bb3c799f439fb9959f6` | unchanged | accepted_with_todos |

The ledger retains optional/unresolved evidence requests and therefore remains `accepted_with_todos`; it does not block the reviewed-input research draft.

## readiness_rebuild

`build_r5_reviewed_input_dry_run_from_registries.py` reconstructed readiness from validated physical registry bytes, not dropzone presence:

- reviewed market inputs: `true`
- reviewed peer inputs: `true`
- reviewed forecast assumptions: `true`
- reviewed valuation inputs: `true`
- reviewed business disclosure: `true`
- remaining critical input TODOs: `0`
- validation status: `pass`
- blockers: `0`
- allowed report level: `reviewed_input_research_draft`

Artifact: `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_reviewed_input_dry_run_result.yaml`.

## core_asset_rebuild

The deterministic financial, business, forecast and valuation builders were rerun after promotion and then passed through the actual four-pack preflight:

- financial history: `accepted`
- business breakdown: `accepted_with_todos`
- forecast model: `accepted`
- valuation: `accepted`
- core state: `partial`
- blockers: `0`
- sample-quality allowed: `false`
- P2 allowed: `false`

The partial state is intentional: official disclosures still do not separately report liquid-cooling revenue share, gross margin or profit contribution.

## focused_contract_repairs

1. Reviewed-input staging and registry promotion are now globally capped at `reviewed_input_research_draft`; accepted inputs alone cannot open sample-quality.
2. Fully reviewed forecast promotion removes the stale source-gapped interlock instead of carrying a contradictory TODO into a reviewed registry.
3. Backup, restore, pre-state verification and two-run idempotency are covered by `tests/test_r5_bundle5_real_registry_promotion.py`.

## validation

- Full dropzone: `pass`, 5 files, 22 accepted, 0 failed.
- Focused Card 5.5 regression: `38 passed` after stale-test updates.
- Core preflight: `partial`, 0 blockers.
- `git diff --check`: pass.

## next_card

Proceed to Card 5.6 research-draft rendering and quality review. Sample-quality and P2 remain closed.

## owner_card_truthfulness_recheck_2026_07_12

status: pass_real_registry_promotion

### files_added

- `scripts/run_r5_bundle5_real_registry_promotion.py`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_registry_backup_manifest.yaml`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_registry_promotion_result.yaml`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_registry_idempotency_result.json`
- `tests/test_r5_bundle5_real_registry_promotion.py`

### files_modified

- `scripts/build_r5_reviewed_input_staging.py`
- `scripts/promote_r5_reviewed_inputs_to_registries.py`
- the four authorized run-local canonical registries listed in the promotion result.

### commands_run

- `.\\.conda\\investment-system\\python.exe -m pytest -q tests\\test_r5_bundle5_real_registry_promotion.py tests\\test_validate_r5_market_peer_input_registry.py tests\\test_validate_r5_forecast_assumption_registry.py tests\\test_validate_r5_valuation_inputs.py tests\\test_r5_forecast_valuation_interlock.py --tb=short -p no:cacheprovider`

### exit_code

- focused_test_exit_code: `0`

### stdout_or_stderr_summary

- `20 passed in 1.16s`
- promotion_result_sha256: `487e6f96d0b599d765af0fedc6aed5b95830718b526188cd98b3fcade52f6243`
- idempotency_result_sha256: `f498c202e39f9caa2897775dde6e6ded778810b42330d4e3e563aeb6c4b05729`
- promotion_checked=22 accepted inputs; second run actions were all `unchanged`; byte-level and semantic idempotency both passed.

### known_todos

- Liquid-cooling-specific disclosure gaps and low-confidence valuation context remain non-blocking at research-draft level.

### next_recommended_patch

- Render and independently quality-check the real reviewed-input research draft; do not infer a higher quality state from promotion success.
