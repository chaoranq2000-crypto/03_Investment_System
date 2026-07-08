# R5 Patch 33 Market Peer Inputs Readout

status: `PASS_SOURCE_GAPPED_STUBS_ACCEPTED`

## Summary

Market/peer validator accepts source-gapped TODO stubs and blocks sample-quality candidates without reviewed inputs.

## files_added

- `.agents/skills/stock-deep-dive/references/r5_market_peer_input_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_market_snapshot.example.yaml`
- `.agents/skills/stock-deep-dive/assets/r5_peer_snapshot.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_market_peer_inputs.py`
- `tests/test_validate_r5_market_peer_inputs.py`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_market_snapshot_stub.yaml`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_peer_snapshot_stub.yaml`
- `reports/p1_6/R5_PATCH_33_MARKET_PEER_INPUTS_READOUT.md`

## files_modified

- None

## commands_run

1. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_market_peer_inputs.py`
   exit_code: `0`
   duration_seconds: `0.058`

   stdout_or_stderr_summary:

```text
(no stdout/stderr)
```

2. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m pytest -q tests/test_validate_r5_market_peer_inputs.py --tb=short`
   exit_code: `0`
   duration_seconds: `0.374`

   stdout_or_stderr_summary:

```text
....                                                                     [100%]
4 passed in 0.04s
```

3. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe .agents/skills/stock-deep-dive/scripts/validate_r5_market_peer_inputs.py --market reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_market_snapshot_stub.yaml --peer reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_peer_snapshot_stub.yaml`
   exit_code: `0`
   duration_seconds: `0.065`

   stdout_or_stderr_summary:

```text
{
  "outcome": "accepted_with_todos",
  "level": "source_gapped_research_draft",
  "errors": []
}
```

## artifact_evidence

| path | exists | line_count | sha256 |
|---|---:|---:|---|
| `.agents/skills/stock-deep-dive/references/r5_market_peer_input_contract.md` | yes | 30 | `3987d8728e8fe8c1f2f16e0daa02fd9f66537ab2575eca40bd405d3f61c43325` |
| `.agents/skills/stock-deep-dive/scripts/validate_r5_market_peer_inputs.py` | yes | 90 | `d64ff3827dd2000585069d8d926847c5860ca130f6be9282db5753911d8edba1` |
| `tests/test_validate_r5_market_peer_inputs.py` | yes | 61 | `c27e1d78392f390f65d61904e57c4dbceff72561a25b9409cfe763c280a1cbfb` |
| `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_market_snapshot_stub.yaml` | yes | 18 | `b711d5cb70eb8d8b9a936f7909b79eda96f4d9edd49089086b0ce7f4e4acadea` |
| `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_peer_snapshot_stub.yaml` | yes | 14 | `1c1ce090aad1d3694ae091d26a86147574691450ffbece55438acf8cf35d3813` |

## known_todos

- Market and peer stubs intentionally carry TODO_MARKET_DATA / TODO_PEER_DATA and no numeric prices or multiples.

## next_recommended_patch

`R5_PATCH_34_FORECAST_VALUATION_INPUT_INTERLOCK`
