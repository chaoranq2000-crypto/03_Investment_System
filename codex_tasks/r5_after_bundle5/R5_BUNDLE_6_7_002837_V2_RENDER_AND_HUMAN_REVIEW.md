# R5 Bundle 6.7 — 002837 v2 render and human-review handoff

## Goal

Render the first reader-facing v2 candidate for `002837 英维克`, generate its traceability appendix and quality scorecard, and hand it off for genuine human review.

## Required outputs

1. `R5_stock_research_report_reader_v2.md`
2. `R5_stock_research_report_traceability_v2.yaml`
3. `R5_stock_research_report_reader_v2_quality_scorecard.yaml`
4. `R5_stock_research_report_reader_v2_human_review.yaml`
5. render result and hashes

## Main-report acceptance criteria

### Surface

- Chinese reader-facing prose;
- no raw internal IDs or paths;
- no machine readiness blocks;
- no raw gap tokens;
- no duplicate audit appendix;
- normalized numbers and units;
- clear report cutoff date;
- no direct investment advice.

### Content

- coherent core thesis;
- financial trend and quality analysis;
- business economics with disclosure boundary;
- populated industry/competition section using reviewed evidence;
- explicit forecast bridge and scenarios;
- valuation and market-implied expectations;
- risks and disconfirming evidence;
- measurable watch conditions.

### Traceability

- every material display citation resolves;
- facts/estimates/inferences remain distinguishable;
- full machine limitations remain in the appendix;
- source gaps are not lost.

### Quality

- reader-quality score >= 82;
- critical blockers = 0;
- truthfulness gate passes;
- full focused regression passes;
- deterministic rerender hash is stable.

## Human-review file

Create a blank/pending form containing:

```yaml
schema_version:
report_path:
report_sha256:
reviewer: null
reviewed_at: null
status: pending
blocking_comments: []
nonblocking_comments: []
```

The implementation must never populate reviewer identity, timestamp or accepted status automatically.

## Required comparison artifact

Produce a concise before/after readout comparing:

- machine-token leakage;
- raw path/ID leakage;
- numeric-format violations;
- section coverage;
- analytical payload completeness;
- reader-quality score;
- remaining limitations.

Do not compare factual conclusions against user samples. Compare only structure, density and presentation behavior.

## Close state for this card

```text
reader_report_candidate_rendered = true
reader_quality_gate_passed = true
human_review_required = true
human_review_status = pending
sample_quality_report_allowed = false
p2_allowed = false
```
