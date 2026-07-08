# R5 Patch 22 Evidence Plan Bridge Readout

status: `PASS`

## Scope

Patch 22 added a plan-only bridge from R5 source gaps to evidence-ingest requests. It does not download evidence, does not call live APIs, does not add external data dependencies, and does not promote TODO/MISSING/source-gap items into facts.

## Files Added

```text
.agents/skills/evidence-ingest/references/r5_stock_evidence_plan_contract.md
.agents/skills/evidence-ingest/assets/r5_evidence_plan_bridge.example.yaml
scripts/build_r5_evidence_plan_from_gaps.py
tests/test_build_r5_evidence_plan_from_gaps.py
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_plan_from_gaps.yaml
reports/p1_6/R5_PATCH_22_EVIDENCE_PLAN_BRIDGE_READOUT.md
```

## Files Modified

```text
None.
```

## Artifact Evidence

```text
line_count build_r5_evidence_plan_from_gaps.py: 318
line_count test_build_r5_evidence_plan_from_gaps.py: 64
line_count R5_evidence_plan_from_gaps.yaml: 249
checked=6 source-gap rows
checked=7 evidence request families
```

## Commands Run

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m py_compile scripts/build_r5_evidence_plan_from_gaps.py
```

exit_code: `0`

stdout_or_stderr_summary:

```text
build_r5_evidence_plan_from_gaps.py compiled successfully.
```

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe scripts/build_r5_evidence_plan_from_gaps.py --pack reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_pack_source_gapped.yaml --source-gap-report reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_source_gap_report.md --out reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_plan_from_gaps.yaml
```

exit_code: `0`

stdout_or_stderr_summary:

```text
wrote reports\workflow_runs\wf_20260703_stock_first_002837_invic\R5_evidence_plan_from_gaps.yaml
gap_rows=6 request_families=7
```

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m pytest -q tests/test_build_r5_evidence_plan_from_gaps.py --tb=short
```

exit_code: `0`

stdout_or_stderr_summary:

```text
4 passed in 0.11s
```

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe .agents/skills/evidence-ingest/scripts/validate_r5_evidence_plan.py reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_plan_from_gaps.yaml
```

exit_code: `0`

stdout_or_stderr_summary:

```json
{
  "decision": "accepted",
  "issues": []
}
```

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe .agents/skills/evidence-ingest/scripts/validate_r5_evidence_plan.py .agents/skills/evidence-ingest/assets/r5_evidence_plan_bridge.example.yaml
```

exit_code: `0`

stdout_or_stderr_summary:

```json
{
  "decision": "accepted",
  "issues": []
}
```

## Known TODOs

- The bridge creates planned evidence requests only; evidence-ingest must still acquire, archive, parse, and manifest actual sources in a later task.
- Analyst consensus remains an empty top-level list because no reviewed consensus input exists in the current source gaps.
- Patch 15 inventory and Patch 19 historical readout gates still block strict all-green smoke.

## Next Recommended Patch

```text
R5_PATCH_23_VALUATION_HANDOFF_INTERLOCK.md
```
