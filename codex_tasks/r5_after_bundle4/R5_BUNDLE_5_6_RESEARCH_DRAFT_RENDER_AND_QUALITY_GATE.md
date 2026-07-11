# R5 Bundle 5.6 — Research-draft render and quality gate

## Background

Registry promotion does not itself prove that a truthful report can be rendered. The real pilot gate, composer and quality review must independently consume the promoted state.

## Goal

Rerun the real reviewed-input pilot gate, render the highest allowed draft, and complete evidence, claim, metric, source-gap, counter-evidence and no-advice checks.

## Allowed files

- real workflow gate, composer, render and quality artifacts
- existing scripts and focused fixes owned by discovered defects
- `reports/stocks/002837_invic/**` only when the existing workflow contract selects that output path
- focused tests
- `reports/p1_6/R5_BUNDLE_5_6_RESEARCH_DRAFT_RENDER_QUALITY_READOUT.md`

## Forbidden scope

- Do not force `reviewed_input_research_draft` when the gate returns blocked.
- Do not remove source-gap appendix, open questions, risks, counter-evidence or limitations to improve presentation.
- Do not promote the output to sample-quality.
- Do not introduce buy/sell/hold, position sizing, trade timing, guaranteed returns or certainty claims.

## Required work

1. Run the real pilot/readiness gate from physical registries.
2. Render through `render_r5_reviewed_input_output.py` or the current canonical composer path.
3. Confirm output type matches the gate:
   - allowed -> `reviewed_input_research_draft`;
   - blocked -> only `source_gapped_research_draft`.
4. Run quality review for:
   - every material claim linked to evidence/claim/metric/TODO;
   - fact/estimate/inference separation;
   - period/unit/source/method completeness;
   - exposure evidence/confidence/missing state;
   - risks and counter-evidence;
   - staleness/conflict handling;
   - forbidden language.
5. Produce a scorecard that cannot set sample-quality or P2 true.

## Acceptance gate

A successful target close requires:

```text
rendered_output_type = reviewed_input_research_draft
forbidden_language_check = pass
critical_quality_blockers = 0
sample_quality_report_allowed = false
p2_allowed = false
```

Non-critical TODOs may remain only when visible and compatible with the existing draft-level gate.

## Suggested commands

```bash
python scripts/r5_reviewed_input_pilot_gate.py --help
python scripts/render_r5_reviewed_input_output.py --repo-root . --workflow-id wf_20260703_stock_first_002837_invic --output reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_note_reviewed_input_draft.md --json reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_reviewed_input_render_result.yaml
python -m pytest -q tests/test_r5_bundle5_real_pilot_gate.py tests/test_r5_reviewed_input_output_writer.py tests/test_r5_quality_gate_scorecard_v2.py tests/test_r5_composer_research_draft_plus.py --tb=short -p no:cacheprovider
git diff --check
```
