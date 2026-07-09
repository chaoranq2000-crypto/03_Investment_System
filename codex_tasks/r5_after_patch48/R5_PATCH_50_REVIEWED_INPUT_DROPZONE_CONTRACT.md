# R5 Patch 50 - Reviewed input dropzone contract

## Goal

Define a manual reviewed-input dropzone contract for market, peer, forecast, valuation and business-disclosure inputs. This contract should make it possible to add reviewed data later without using live APIs or silently promoting TODOs.

## Background

The pilot gate is blocked because reviewed market, peer, forecast and valuation inputs are absent. Existing stubs must remain stubs. The next safe step is to define where accepted reviewed inputs may be placed and what metadata they must carry.

## Allowed files

- `docs/workflows/R5_REVIEWED_INPUT_DROPZONE_SPEC.md`
- `.agents/skills/evidence-ingest/references/r5_reviewed_input_dropzone_contract.md`
- `templates/r5_reviewed_market_snapshot.template.csv`
- `templates/r5_reviewed_peer_snapshot.template.csv`
- `templates/r5_reviewed_forecast_assumptions.template.yaml`
- `templates/r5_reviewed_business_disclosure.template.yaml`
- `templates/r5_reviewed_valuation_inputs.template.yaml`
- `data/reviewed_inputs/README.md`
- `reports/p1_6/R5_PATCH_50_REVIEWED_INPUT_DROPZONE_CONTRACT_READOUT.md`

## Required behavior

1. Define the dropzone path pattern:

```text
data/reviewed_inputs/<workflow_id>/<input_type>/
```

2. Define allowed input types:

```text
market_snapshot
peer_snapshot
forecast_assumptions
business_disclosure
valuation_inputs
sentiment_event_sources
```

3. Every accepted reviewed input must include:

```text
input_id
workflow_id
stock_code
input_type
as_of_date
source_evidence_id
source_rank
review_status
reviewer
reviewed_at
capture_method
no_live_api
limitations
```

4. `review_status` must be one of:

```text
pending
accepted
rejected
accepted_degraded
```

5. `accepted` and `accepted_degraded` rows must never include:

```text
TODO_MARKET_DATA
TODO_PEER_DATA
TODO_MODEL_INPUT
TODO_SOURCE_REQUIRED
MISSING_DISCLOSURE
LOW_CONFIDENCE_CLUE_ONLY
evidence_id: null
source_evidence_id: null
```

6. `accepted_degraded` may be used only when the limitation is explicit and the row is not used for sample-quality.

7. Define that templates are empty/contracts only. They are not evidence and must not unblock gates by themselves.

## Tests

```bash
python - <<'PY'
from pathlib import Path
for path in [
  'docs/workflows/R5_REVIEWED_INPUT_DROPZONE_SPEC.md',
  '.agents/skills/evidence-ingest/references/r5_reviewed_input_dropzone_contract.md',
  'templates/r5_reviewed_market_snapshot.template.csv',
  'templates/r5_reviewed_peer_snapshot.template.csv',
  'templates/r5_reviewed_forecast_assumptions.template.yaml',
  'templates/r5_reviewed_business_disclosure.template.yaml',
  'templates/r5_reviewed_valuation_inputs.template.yaml',
  'data/reviewed_inputs/README.md',
]:
    assert Path(path).exists(), path
print('dropzone_contract_files_ok')
PY
python - <<'PY'
import yaml
from pathlib import Path
for path in [
  'templates/r5_reviewed_forecast_assumptions.template.yaml',
  'templates/r5_reviewed_business_disclosure.template.yaml',
  'templates/r5_reviewed_valuation_inputs.template.yaml',
]:
    yaml.safe_load(Path(path).read_text(encoding='utf-8'))
print('yaml_templates_ok')
PY
```

## Readout

Add `reports/p1_6/R5_PATCH_50_REVIEWED_INPUT_DROPZONE_CONTRACT_READOUT.md`.

## Global boundaries

- Do not add real market or peer values in this patch.
- Do not call live APIs.
- Do not generate a report.
- Do not change the current 002837 gate state.
- Do not mark sample-quality or P2 ready.
