# R5 Bundle 4.4 Post-Promotion Dry Run Readout

status: accepted_with_todos

## decision

- derivation_source: `validated_physical_registries`
- accepted_dropzone_presence_used_as_readiness_source: `false`
- core_complete_fixture: `pass`
- all_complete_fixture: `pass`
- invalid_or_tampered_registry_behavior: `fail_closed`
- real_002837_workflow_changed: `false`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`
- next_card_allowed: `true`

## readiness_derivation_rules

- Market and peer flags require every physical section field to be non-TODO and evidence-anchored after the market/peer validator passes.
- Forecast readiness requires validator acceptance plus all five reviewed core drivers with evidence or metric anchors.
- Valuation readiness requires accepted `valuation_input_refs`, validator acceptance and reviewed market, peer and forecast prerequisites.
- Business readiness requires a reviewed business block plus matching accepted ledger provenance.
- Cross-registry workflow or stock identity mismatch forces every reviewed flag false.
- When a promotion result is supplied, every physical registry SHA-256 must equal its recorded `after_hash`.

## todo_reconciliation

- `TODO_MARKET_DATA` resolves only from reviewed physical `market_inputs`.
- `TODO_PEER_DATA` resolves only from reviewed physical `peer_inputs`.
- `TODO_MODEL_INPUT` resolves only from the five reviewed forecast drivers.
- `MISSING_DISCLOSURE` resolves only from reviewed business disclosure plus accepted ledger provenance.
- `TODO_SOURCE_REQUIRED` resolves only from evidence-anchored `valuation_input_refs`.

Each `todo_trace` row records status, resolving input IDs, registry path/field, evidence IDs and a remaining reason.

## core_complete_decision

- reviewed flags: market=`true`, peer=`true`, forecast=`true`, valuation=`true`, business=`false`.
- remaining_todos: `MISSING_DISCLOSURE` only.
- allowed_report_level: `reviewed_input_research_draft`.
- sample-quality and P2: `false`.

## all_complete_decision

- all five reviewed flags: `true`.
- remaining_todos: none.
- internal fixture completeness: `all_complete`.
- externally allowed level remains capped at `reviewed_input_research_draft`.
- sample-quality and P2: `false`.

## invalid_registry_decision

- Missing files, validator failure, changed promotion hash, empty valuation refs and cross-registry identity mismatch all produce blockers.
- A tampered market evidence anchor turns market and dependent valuation readiness false.
- Repeated builds serialize byte-identically after path normalization.

## files_added

- `scripts/build_r5_reviewed_input_dry_run_from_registries.py`
- `tests/test_r5_bundle4_post_promotion_dry_run.py`
- `reports/p1_6/R5_BUNDLE_4_4_POST_PROMOTION_DRY_RUN_READOUT.md`

## files_modified

- `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md`

## commands_run

- `$env:PYTHONDONTWRITEBYTECODE='1'; .\\.conda\\investment-system\\python.exe -B -m py_compile scripts\\build_r5_reviewed_input_dry_run_from_registries.py`
- `$env:PYTHONDONTWRITEBYTECODE='1'; .\\.conda\\investment-system\\python.exe -B -m pytest -q tests\\test_r5_bundle4_post_promotion_dry_run.py tests\\test_r5_002837_reviewed_input_staging.py --tb=short -p no:cacheprovider`
- `.\\.conda\\investment-system\\python.exe scripts\\promote_r5_reviewed_inputs_to_registries.py --repo-root . --workflow-id wf_fixture_r5_bundle4 --stock-code 000000 --dropzone-root tests\\fixtures\\r5_reviewed_inputs\\accepted_core_complete --output-run-dir $env:TEMP\\r5_bundle4_card44_core_run --fixture-mode --json $env:TEMP\\r5_bundle4_card44_promotion.json`
- `.\\.conda\\investment-system\\python.exe scripts\\build_r5_reviewed_input_dry_run_from_registries.py --repo-root . --run-dir $env:TEMP\\r5_bundle4_card44_core_run --promotion-result $env:TEMP\\r5_bundle4_card44_promotion.json --fixture-mode --json $env:TEMP\\r5_bundle4_card44_dry.json`
- `git diff --check`
- `$tmp=Join-Path $env:TEMP 'r5_bundle4_4_truthfulness.json'; & .\\.conda\\investment-system\\python.exe scripts\\check_r5_readout_truthfulness.py --rules config\\r5_readout_truthfulness_rules.yaml --glob reports/p1_6/R5_BUNDLE_4_4_POST_PROMOTION_DRY_RUN_READOUT.md --strict --json $tmp`

## exit_code

- py_compile: `0`
- targeted pytest: `0`
- fixture promotion CLI: `0`
- registry-derived dry-run CLI: `0`
- git diff check: `0`
- truthfulness check: `0`

## stdout_or_stderr_summary

- targeted pytest: `13 passed in 1.62s`.
- dry-run CLI: `status=pass`, level=`reviewed_input_research_draft`, market/peer/forecast/valuation=`true`, business=`false`, blockers=`0`.
- git diff check: no whitespace errors reported.
- truthfulness check: `truthfulness_status=pass checked=1 failed=0`.

## artifact_evidence

- inventory_status: `pass`
- critical_evidence: `checked=4` physical registry hashes and validator decisions plus five independent TODO trace rows.
- The real 002837 read-only test hashes all registry, promotion and dry-run targets before and after and observes no changes.

## blockers

- none for Card 4.5.

## known_todos

- The real 002837 workflow remains source-gapped and does not gain fixture readiness.
- Legacy dropzone-derived staging behavior remains for backward compatibility, but Bundle 4 readiness uses the new registry-derived builder.

## next_recommended_patch

- R5 Bundle 4.5 - End-to-end reviewed-input fixture smoke gate.
