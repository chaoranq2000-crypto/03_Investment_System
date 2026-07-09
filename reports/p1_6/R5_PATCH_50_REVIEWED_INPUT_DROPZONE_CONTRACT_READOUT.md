# R5 Patch 50 Reviewed Input Dropzone Contract Readout

status: accepted_with_todos

## files_added

- `docs/workflows/R5_REVIEWED_INPUT_DROPZONE_SPEC.md`
- `.agents/skills/evidence-ingest/references/r5_reviewed_input_dropzone_contract.md`
- `templates/r5_reviewed_market_snapshot.template.csv`
- `templates/r5_reviewed_peer_snapshot.template.csv`
- `templates/r5_reviewed_forecast_assumptions.template.yaml`
- `templates/r5_reviewed_business_disclosure.template.yaml`
- `templates/r5_reviewed_valuation_inputs.template.yaml`
- `data/reviewed_inputs/README.md`
- `reports/p1_6/R5_PATCH_50_REVIEWED_INPUT_DROPZONE_CONTRACT_READOUT.md`

## files_modified

- none

## commands_run

- `.\\.conda\\investment-system\\python.exe -c "from pathlib import Path; required=[...]; missing=[p for p in required if not Path(p).exists()]; assert not missing, missing; print('dropzone_contract_files_ok')"`
- `.\\.conda\\investment-system\\python.exe -c "import yaml; from pathlib import Path; paths=[...]; [yaml.safe_load(Path(p).read_text(encoding='utf-8')) for p in paths]; print('yaml_templates_ok')"`

## exit_code

- contract file existence check: 0
- YAML template parse check: 0

## stdout_or_stderr_summary

- existence check: `dropzone_contract_files_ok`
- YAML parse check: `yaml_templates_ok`
- stderr: none observed

## artifact_evidence

- critical_evidence: checked=8 declared Patch 50 contract/template files.
- Dropzone path pattern is `data/reviewed_inputs/<workflow_id>/<input_type>/`.
- Allowed input types are `market_snapshot`, `peer_snapshot`, `forecast_assumptions`, `business_disclosure`, `valuation_inputs`, and `sentiment_event_sources`.
- Accepted reviewed inputs require evidence/date/reviewer metadata and `no_live_api: true`.
- Templates are explicitly marked as `template_only` / `not_evidence` and do not unblock gates.

## known_todos

- No real market, peer, forecast, business-disclosure, valuation, or sentiment inputs were added.
- Current 002837 gate state is unchanged and remains source-gapped.

## next_recommended_patch

- R5 Patch 51 - Reviewed Input Dropzone Validators
