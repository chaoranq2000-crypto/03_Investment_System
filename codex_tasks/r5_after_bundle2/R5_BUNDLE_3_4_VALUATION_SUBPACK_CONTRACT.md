# R5 Bundle 3.4 — Valuation subpack contract and validator

## Background

Valuation remains blocked because reviewed market and peer snapshots are absent. R5 needs a valuation subpack validator that distinguishes valuation range analysis from direct trading instructions and fails closed when market or peer data is missing.

## Goal

Add a valuation subpack contract, example YAML, validator and pytest coverage.

## Allowed files

- `.agents/skills/stock-deep-dive/references/r5_valuation_pack_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_valuation_pack.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_valuation_pack.py`
- `tests/test_validate_r5_valuation_pack.py`
- `.agents/skills/stock-deep-dive/SKILL.md` only for a minimal reference link
- `reports/p1_6/R5_BUNDLE_3_4_VALUATION_SUBPACK_READOUT.md`

## Forbidden scope

- Do not fetch live market data.
- Do not invent current price, market cap, peer multiples or valuation outputs.
- Do not create direct trading instruction language.
- Do not mark sample-quality ready.

## Required contract behavior

The valuation subpack must define:

```text
artifact_type
schema_version
status
as_of_date
market_snapshot
peer_valuation_context
valuation_methods
valuation_scenarios
valuation_sensitivity
limitations
missing_items
source_gap_register
```

`market_snapshot` must support:

```text
current_price
market_cap
share_count
net_cash_or_net_debt
enterprise_value
pe_ttm
forward_pe
pb
ps
ev_ebitda
as_of_date
evidence_id or metric_id
missing_reason
```

Validator rules:

- Market snapshot values must be evidence-supported when non-null.
- Null market snapshot fields require `TODO_MARKET_DATA` or explicit missing reason.
- Peer context rows with non-null multiples require evidence or metric support.
- `status: ready` requires dated market snapshot, at least one peer context row, and at least one valuation method with supported output.
- If forecast-dependent methods are marked ready, they must reference forecast assumptions or forecast metrics.
- The validator must reject direct trading instruction language and forbidden action phrases.

## Acceptance criteria

- Example YAML parses and validates as `accepted_with_todos` if market and peer data are TODO.
- Validator fails unsupported non-null market or peer valuation values.
- Validator fails `status: ready` when market snapshot or peer context is missing.
- Validator rejects forbidden direct trading phrases.
- Pytest covers valid, TODO and invalid cases.

## Suggested tests

```bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_valuation_pack.py
python .agents/skills/stock-deep-dive/scripts/validate_r5_valuation_pack.py --input .agents/skills/stock-deep-dive/assets/r5_valuation_pack.example.yaml
python -m pytest -q tests/test_validate_r5_valuation_pack.py --tb=short
git diff --check
```

## Output requirements

- List changed files.
- Include validator outcome.
- Include pytest result.
- Write the readout file.
