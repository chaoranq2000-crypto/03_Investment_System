# R5 Bundle 5.7 — Benchmark coverage precheck with no-advice filter

## Background

User-supplied sample reports provide a useful high-density section pattern, but they also contain direct investment ratings, position/timing language and unverified factual claims. They are style references only.

## Goal

Run a non-promoting coverage precheck against `SAMPLE_REPORT_BENCHMARK_PROFILE.yaml`, while proving that sample facts and advice language are not imported into the real report.

## Allowed files

- `codex_tasks/r5_after_bundle4/SAMPLE_REPORT_BENCHMARK_PROFILE.yaml`
- a benchmark precheck script/test if no equivalent exists
- real draft quality/coverage result files
- `reports/p1_6/R5_BUNDLE_5_7_BENCHMARK_COVERAGE_PRECHECK_READOUT.md`

## Forbidden scope

- Do not copy sample facts, forecasts, prices, events, ratings or citations into the 002837 evidence graph.
- Do not use sample reports to satisfy evidence coverage.
- Do not rename this check as sample-quality acceptance.
- Do not require every sample heading when evidence is absent; preserve TODO/MISSING instead.
- Do not open P2.

## Required work

1. Map safe coverage dimensions to the current reporting standard:
   - company context;
   - financial history and cash-flow quality;
   - business/segment economics;
   - industry and competition;
   - forecast assumptions and sensitivity;
   - valuation methods and comparability;
   - dated market/technical state when supported;
   - dated sentiment/events when supported;
   - risks, counter-evidence and open questions;
   - research conclusion and watch conditions without action instructions.
2. Scan for prohibited sample-derived language and direct advice patterns.
3. Verify that each populated section is supported by repository evidence IDs or explicit TODOs.
4. Output coverage as `covered`, `partial`, `missing`, or `not_applicable`, not as a report-quality promotion decision.
5. Keep `sample_quality_report_allowed: false` and `p2_allowed: false` in the result.

## Acceptance gate

- No sample factual content is registered as evidence.
- No prohibited action language appears in the real draft.
- Coverage gaps remain explicit.
- The result is a precheck only.

## Suggested commands

```bash
python -m pytest -q tests/test_r5_bundle5_benchmark_coverage_precheck.py tests/test_r5_sample_benchmark_policy.py --tb=short -p no:cacheprovider
git diff --check
```
