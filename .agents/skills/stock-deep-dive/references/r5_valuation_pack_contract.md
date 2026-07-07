# R5 Valuation Pack Contract

## Purpose

`r5_valuation_pack` carries valuation context for R5 stock research. It can describe source status, scenario structure, peer context, and missing market inputs. It must not output trading instructions.

## Required shape

```yaml
artifact_type: R5_valuation_pack
status: TODO | partial | ready | blocked
sample_quality_allowed: false
market_snapshot:
  as_of_date:
  current_price:
  market_cap:
  share_count:
  missing_reason:
multiples:
  PE_TTM:
  forward_PE:
  PB:
  PS:
peer_context:
  peer_set:
  peer_multiples:
  missing_reason:
valuation_scenarios: []
```

Missing `market_snapshot` or missing peer context prevents sample-quality status. Null values are allowed only when the nearby object carries `missing_reason`.

## Scenario fields

Each scenario must include:

```text
method
key_assumptions
source_ids_or_missing_reason
```

## Boundaries

- Do not fetch live market data.
- Do not calculate real valuation.
- Do not produce buy/sell/hold language, target-price instructions, position sizing, or guaranteed-return statements.
