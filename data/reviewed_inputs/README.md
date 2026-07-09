# R5 Reviewed Inputs

This directory is a manual reviewed-input dropzone.

Path pattern:

```text
data/reviewed_inputs/<workflow_id>/<input_type>/
```

Allowed input types:

- `market_snapshot`
- `peer_snapshot`
- `forecast_assumptions`
- `business_disclosure`
- `valuation_inputs`
- `sentiment_event_sources`

Templates are stored under `templates/` and are not evidence. Accepted rows must
carry reviewed metadata and evidence anchors before registry promotion can use
them.
