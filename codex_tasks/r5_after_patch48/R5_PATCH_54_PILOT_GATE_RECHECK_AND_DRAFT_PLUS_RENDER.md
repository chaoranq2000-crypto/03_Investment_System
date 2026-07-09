# R5 Patch 54 - Pilot gate recheck and draft-plus render

## Goal

Rerun the reviewed-input pilot gate after staging/registry promotion and render the highest allowed report level without exceeding gate permissions.

## Background

Patch 47 added draft-plus composer behavior, but the current pack is still source-gapped. After the accepted-only promotion step, the workflow needs a deterministic recheck and render command.

## Allowed files

- `scripts/render_r5_reviewed_input_output.py`
- `tests/test_r5_pilot_gate_recheck_and_render.py`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_reviewed_input_render_result.yaml`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_note_reviewed_input_draft.md`
- `reports/p1_6/r5_reviewed_input_pilot_gate_result.json`
- `reports/p1_6/R5_PATCH_54_PILOT_GATE_RECHECK_AND_DRAFT_PLUS_RENDER_READOUT.md`

## Required behavior

1. Rerun:

```text
r5_pack_promotion_gate.py
r5_reviewed_input_pilot_gate.py
```

2. If gate state is blocked, render or preserve only `source_gapped_research_draft`.
3. If gate state allows `reviewed_input_research_draft`, render draft-plus sections only for reviewed-ready sections.
4. If sample-quality is not allowed, the output must not contain sample-quality labels.
5. Always preserve:

```text
Source Gap Appendix
Open Questions
No-advice boundary
remaining TODOs
```

6. Reject direct trading language.
7. The render result must include:

```text
input_gate_state
promotion_level
rendered_output_type
sample_quality_report_allowed
p2_allowed
source_gap_count
forbidden_language_check
```

## Tests

```bash
python -m py_compile scripts/render_r5_reviewed_input_output.py scripts/r5_pack_promotion_gate.py scripts/r5_reviewed_input_pilot_gate.py src/report/stock_report_writer.py
python -m pytest -q tests/test_r5_pilot_gate_recheck_and_render.py tests/test_r5_composer_research_draft_plus.py tests/test_r5_report_composer_degradation.py --tb=short
python scripts/render_r5_reviewed_input_output.py --workflow-id wf_20260703_stock_first_002837_invic --json reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_reviewed_input_render_result.yaml
```

## Readout

Add `reports/p1_6/R5_PATCH_54_PILOT_GATE_RECHECK_AND_DRAFT_PLUS_RENDER_READOUT.md`.

## Global boundaries

- Do not call live APIs.
- Do not generate sample-quality unless the gate explicitly allows it.
- Do not enter P2.
- Do not output direct trading advice.
