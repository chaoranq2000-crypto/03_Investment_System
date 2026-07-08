# R5 Patch 32 Evidence Request Queue Readout

status: `PASS_PLANNED_QUEUE_BUILT`

## Summary

Evidence plan was flattened into a no_live_api request queue with 10 planned requests.

## files_added

- `.agents/skills/evidence-ingest/references/r5_evidence_request_queue_contract.md`
- `.agents/skills/evidence-ingest/scripts/build_r5_evidence_request_queue.py`
- `tests/test_build_r5_evidence_request_queue.py`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_request_queue.yaml`
- `reports/p1_6/R5_PATCH_32_EVIDENCE_REQUEST_QUEUE_READOUT.md`

## files_modified

- None

## commands_run

1. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m py_compile .agents/skills/evidence-ingest/scripts/build_r5_evidence_request_queue.py`
   exit_code: `0`
   duration_seconds: `0.046`

   stdout_or_stderr_summary:

```text
(no stdout/stderr)
```

2. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m pytest -q tests/test_build_r5_evidence_request_queue.py --tb=short`
   exit_code: `0`
   duration_seconds: `0.413`

   stdout_or_stderr_summary:

```text
...                                                                      [100%]
3 passed in 0.09s
```

3. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe .agents/skills/evidence-ingest/scripts/build_r5_evidence_request_queue.py --plan reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_plan_from_gaps.yaml --out reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_request_queue.yaml`
   exit_code: `0`
   duration_seconds: `0.077`

   stdout_or_stderr_summary:

```text
r5_evidence_request_queue status=planned requests=10 no_live_api=true
```

## artifact_evidence

| path | exists | line_count | sha256 |
|---|---:|---:|---|
| `.agents/skills/evidence-ingest/references/r5_evidence_request_queue_contract.md` | yes | 32 | `b2c36c4f7d4b63512e4e049cc67a7364be80a0178e57a0fed84fd990a2c66c2c` |
| `.agents/skills/evidence-ingest/scripts/build_r5_evidence_request_queue.py` | yes | 133 | `b24c71d62728b6eb988673020f3ba8f5aa6a72f5e06abd72c04c76cf3ee4cbd1` |
| `tests/test_build_r5_evidence_request_queue.py` | yes | 72 | `343be2adb794ac43af29b40ff58e494434d66ea13cbd773aed4ec395a07b64b5` |
| `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_request_queue.yaml` | yes | 227 | `04594cc390164770215d9be69c384766838689cba349ece8a0037eb5852225f5` |

## known_todos

- Queue status is planned and every request keeps evidence_id null until evidence-ingest registers real evidence.

## next_recommended_patch

`R5_PATCH_33_MARKET_PEER_INPUT_STUBS_AND_VALIDATORS`
