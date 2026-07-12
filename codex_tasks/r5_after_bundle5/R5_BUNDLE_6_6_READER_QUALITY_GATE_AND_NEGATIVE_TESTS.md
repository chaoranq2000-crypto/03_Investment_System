# R5 Bundle 6.6 — Reader-quality gate and negative tests

## Goal

Create a quality gate that measures reader usefulness independently from truthfulness and structural coverage.

## Two-gate model

```text
truthfulness gate
  asks: is every material statement supportable?

reader-quality gate
  asks: is the supported material organized into a coherent, analytical and readable report?
```

Both must pass. A truthfulness pass cannot substitute for a reader-quality pass.

## Required gate dimensions

Use `R5_BUNDLE6_READER_QUALITY_RUBRIC.yaml` as the minimum contract:

- evidence integrity;
- coverage completeness;
- analytical synthesis;
- forecast and valuation;
- narrative/readability;
- presentation hygiene;
- risks/watch conditions.

## Hard negative tests

The gate must fail a report containing any of the following:

1. raw evidence/claim IDs in the main body;
2. internal registry or workflow paths;
3. `readiness:` or `visible_gap:` blocks;
4. raw TODO/MISSING/LOW_CONFIDENCE/UNREVIEWED tokens;
5. duplicate machine-readiness sections;
6. raw CNY values with excessive decimals;
7. a major section with facts but no interpretation;
8. a forecast without a driver bridge;
9. forecast arithmetic mismatch;
10. valuation without a dated denominator;
11. unresolved display citation;
12. unsupported causal language;
13. sample facts used as evidence;
14. buy/sell/hold, position, timing, guaranteed-return or target-price instructions;
15. self-generated human acceptance.

## Required regression fixtures

- a fully supported synthetic reader report that passes;
- a source-gapped but honest report that fails candidate quality without failing truthfulness;
- the current Bundle 5 draft or a frozen equivalent as a negative reader-surface fixture;
- a report with one unresolved citation;
- a report with hidden uncertainty;
- a report with duplicated audit blocks;
- a report with over-precise metrics;
- a report attempting to set human review accepted.

## Scorecard requirements

The scorecard must include:

- total score;
- dimension scores;
- critical blockers;
- warnings;
- missing mandatory sections;
- unresolved citation count;
- machine-token leakage count;
- numeric-format violations;
- conclusion state;
- fixed human/sample-quality/P2 flags.

## Acceptance gate

```text
focused_tests = pass
current_bundle5_draft_reader_gate = fail_as_expected
supported_fixture_reader_gate = pass
critical_blocker_detection = pass
human_review_status = pending
sample_quality_report_allowed = false
p2_allowed = false
```
