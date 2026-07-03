# DATA_LAYER_DL2_TECHNICAL_MARKET_SEMANTICS_READOUT

date: 2026-07-03
scope: DL-2 Technical / Market Pack Semantics Repair
status: PASS

## Changes

- `src/research/technical_snapshot_builder.py`
  - Replaced price-window-related `MISSING_DISCLOSURE` outputs with `INSUFFICIENT_PRICE_WINDOW`.
  - Replaced missing non-price market data outputs with `TODO_MARKET_DATA`.
  - Normalized technical snapshot source paths to POSIX path format.
- `reports/workflow_runs/wf_20260703_data_layer_002837_invic/technical_snapshot.yaml`
  - Regenerated from the Baostock fixture.
  - `MA20`, `MA60`, `pct_chg_20d`, `pct_chg_60d`, and weekly MA fields now use `INSUFFICIENT_PRICE_WINDOW`.
  - No-advice note preserved.
- `reports/workflow_runs/wf_20260703_data_layer_002837_invic/source_gap_report.md`
  - Updated technical gap wording to describe insufficient fixture price window without using disclosure language.
- `tests/test_technical_snapshot_builder.py`
  - Added assertions for `INSUFFICIENT_PRICE_WINDOW`, no `MISSING_DISCLOSURE`, POSIX paths, and no-advice note preservation.

## Current Technical Snapshot State

- `technical_snapshot.yaml` contains no `MISSING_DISCLOSURE`.
- `technical_snapshot.yaml` contains no Windows backslash paths.
- Missing 20/60-day fields are labeled `INSUFFICIENT_PRICE_WINDOW`.
- `source_gap_report.md` no longer states that short fixture windows remain `MISSING_DISCLOSURE`.

## Verification

```text
python -m py_compile $(git ls-files '*.py')
PASS

python -m pytest -q tests/test_technical_snapshot_builder.py
1 passed in 0.06s

python -m pytest -q tests/test_data_layer_quality_gate.py
4 passed in 0.18s

python -m pytest -q
56 passed in 3.02s
```

## Boundary Review

- No trading advice was generated.
- No buy/sell/hold language was added.
- Technical snapshot remains market-state observation only.
- No real market API was called.
- No structured snapshot was promoted to a business exposure fact.
