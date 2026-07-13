# Operational adoption rule for a-stock-data-derived capabilities

Use `config/a_stock_data_capability_catalog.yaml` as the complete accounting surface and `config/adapter_contract_registry.yaml` as the execution truth.

Never infer operational readiness from `enabled: true` in a route catalog. A capability may be described as operational only after the adapter gate proves its entrypoint, endpoint hint, fixture, live receipt, raw archive, manifest write, schema fingerprint, claim boundary and independent fallback where required.

Trading pools, options and popularity rankings remain explicitly catalogued but do not block the non-trading research workflow. News, fund flow, rankings and investor interaction are clues or management comments; they cannot directly become reported revenue, order, customer or profit facts.
