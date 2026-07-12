# R5 Bundle 5.4 — Forecast and Valuation Input Readout

status: accepted_reviewed_input_research_draft

## result

- workflow_id: `wf_20260703_stock_first_002837_invic`
- stock_code: `002837`
- reviewer: `codex`
- reviewed_at: `2026-07-12T01:40:06.1796355+08:00`
- accepted_forecast_assumptions: `5`
- accepted_valuation_inputs: `1`
- forecast_periods: `2026E, 2027E, 2028E`
- canonical_registry_changed: `false`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`

## base_case_estimates

| metric | 2026E | 2027E | 2028E | type |
|---|---:|---:|---:|---|
| revenue growth | 26.0291% | 20.00% | 15.00% | estimate |
| gross margin | 24.2935% | 25.50% | 26.50% | estimate |
| attributable profit | 94115513.02 | 321179929.40 | 580418015.27 | estimate, CNY |
| EPS | 0.073854 | 0.252034 | 0.455462 | estimate, CNY/share |

The 2026 path is a mechanical Q1 carry-forward and prior-year seasonality calculation. The 2027-2028 path is an explicit model assumption with visible sensitivity ranges. None of these values is a reported fact, management guidance or consensus.

## method_eligibility

- `relative_pe`: eligible only as low-confidence context; two same-date exposure-grounded peers are available.
- `dcf`: excluded because FCFF, tax, capex, working-capital, discount-rate and terminal inputs are not sufficiently reviewed.
- `sotp`: excluded because liquid-cooling-specific revenue and profit splits are not separately disclosed.
- The valuation candidate contains relative-multiple context and forward-PE sensitivity only; it contains no price output.

## net_debt_bridge

- Q1 cash: `917,139,183.43 CNY`.
- Gross debt and lease-related components: `1,615,274,513.10 CNY`.
- Derived net-debt proxy: `698,135,329.67 CNY`, low confidence because restricted cash and trading financial assets were not reclassified.
- Source: `ev_quarterly_report_002837_20260421_2f00c7`, consolidated balance sheet.

## next_card

Cards 5.2-5.4 now have accepted reviewed inputs. Proceed to Card 5.5 only after full dropzone validation, pre-hash inventory, backups, dry-run and hard-boundary fixes pass.

## owner_card_truthfulness_recheck_2026_07_12

status: pass_reviewed_estimates_with_method_limits

### files_added

- `scripts/build_r5_bundle5_forecast_valuation_onboarding.py`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_forecast_model_candidate.yaml`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_valuation_pack_candidate.yaml`
- `tests/test_r5_bundle5_forecast_valuation_onboarding.py`

### files_modified

- none outside the owned reviewed-input candidate and validation paths.

### commands_run

- `.\\.conda\\investment-system\\python.exe -m pytest -q tests\\test_r5_bundle5_forecast_valuation_onboarding.py --tb=short -p no:cacheprovider`

### exit_code

- focused_test_exit_code: `0`

### stdout_or_stderr_summary

- `6 passed in 0.06s`
- forecast_pack_sha256: `702847ba4bf99e07ca2713bc1ff1a571bfffb7f7e95f689d6878f0c266ea5868`
- valuation_pack_sha256: `4e9d17cb010cd6266e4a3248f64c701ddc9ec2f21b8adf512eea941db42a6571`
- assumptions_checked=5 across `2026E-2028E`; method eligibility retained one low-confidence relative context and excluded two ineligible methods.

### known_todos

- Intrinsic and segment-sum methods remain ineligible; forecast uncertainty is wide and the peer set is low confidence.

### next_recommended_patch

- Promote only after backup, dry-run, validator and idempotency gates pass; keep sample-quality and P2 closed.
