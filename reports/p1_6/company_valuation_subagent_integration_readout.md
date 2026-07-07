# P1.6 Company Valuation Subagent Integration Readout

```yaml
status: applied
files_added:
  - .agents/skills/company-valuation/SKILL.md
  - .agents/skills/company-valuation/README.md
  - .agents/skills/company-valuation/references/valuation_model_contract.md
  - .agents/skills/company-valuation/references/method_selection.md
  - .agents/skills/company-valuation/references/output_writing_rules.md
  - .agents/skills/company-valuation/assets/valuation_request_template.yaml
  - .agents/skills/company-valuation/assets/valuation_snapshot_template.yaml
  - .agents/skills/company-valuation/assets/valuation_section_template.md
  - .agents/skills/stock-deep-dive/references/valuation_subagent_handoff.md
  - .agents/skills/stock-deep-dive/assets/valuation_request_template.yaml
  - docs/plans/P1_6_COMPANY_VALUATION_SUBAGENT_INTEGRATION_PLAN.md
  - reports/workflow_runs/wf_20260703_stock_first_002837_invic/valuation_request.yaml
  - reports/workflow_runs/wf_20260703_stock_first_002837_invic/valuation/valuation_model.yaml
  - reports/workflow_runs/wf_20260703_stock_first_002837_invic/valuation/valuation_snapshot.yaml
  - reports/workflow_runs/wf_20260703_stock_first_002837_invic/valuation/peer_comparison.csv
  - reports/workflow_runs/wf_20260703_stock_first_002837_invic/valuation/sensitivity_table.csv
  - reports/workflow_runs/wf_20260703_stock_first_002837_invic/valuation/valuation_section_draft.md
  - reports/workflow_runs/wf_20260703_stock_first_002837_invic/valuation/valuation_gap_requests.yaml
  - reports/workflow_runs/wf_20260703_stock_first_002837_invic/valuation/valuation_quality_handoff.yaml
  - reports/p1_6/company_valuation_subagent_integration_readout.md
files_modified:
  - .codex/config.toml
  - .agents/skills/stock-deep-dive/SKILL.md
  - .agents/skills/stock-deep-dive/references/report_production_profile.md
  - .agents/skills/stock-deep-dive/references/forecast_valuation_contract.md
  - .agents/skills/stock-deep-dive/references/analysis_pack_contract.md
  - .agents/skills/stock-deep-dive/assets/stock_analysis_pack_template.yaml
  - .agents/skills/quality-review/SKILL.md
skill_enabled: true
stock_deep_dive_handoff_added: true
quality_review_updated: true
no_advice_boundary: pass
open_todos:
  - TODO_MARKET_DATA: existing 002837 run has no market_snapshot.csv under the new handoff contract.
  - TODO_PEER_DATA: existing 002837 run has no peer_market_snapshot.csv under the new handoff contract.
  - TODO_FINANCIAL_METRIC_PACK: metrics_registry.csv exists, but financial_metric_pack.csv is not materialized.
  - TODO_FORECAST_MODEL_NET_PROFIT: forecast_model.yaml has revenue estimates, but profit and margin fields remain TODO_MODEL_INPUT.
```

## Summary

`company-valuation` is now configured as a skill-local valuation sub-skill for `stock-deep-dive`. The integration keeps valuation inside the evidence-first stock workflow:

```text
research-orchestrator -> stock-deep-dive -> company-valuation -> stock-deep-dive report assembly -> quality-review
```

No live market data acquisition, external dependency install, evidence-ingest rewrite, segment exposure update, P2 workflow, or direct trading advice was added.

## Dry-run

Dry-run target:

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/
```

Result:

```text
valuation_request.yaml created.
valuation/valuation_gap_requests.yaml created.
valuation/valuation_model.yaml created as TODO / not_assessable context.
valuation/valuation_section_draft.md created with visible TODO_VALUATION_CONTEXT.
valuation/valuation_quality_handoff.yaml created with QR-VAL checks and high_issues: 0.
```

Medium TODOs are intentionally visible because the existing run lacks the new handoff's market, peer, financial metric pack and net-profit forecast inputs.

## Validation

```text
stock-deep-dive merge validation PASS
pytest tests/test_stock_deep_dive_skill_merge.py tests/test_valuation_snapshot_builder.py tests/test_stock_report_quality_review.py -q: 12 passed
pytest tests/test_data_layer_quality_gate.py -q: 4 passed
YAML parse PASS: 9 files
git diff --check: PASS, with CRLF normalization warnings only
```

No high severity issue is hidden in the dry-run output. The no-advice scan matches only prohibited-language sections, boundary statements, and negative guardrails.
