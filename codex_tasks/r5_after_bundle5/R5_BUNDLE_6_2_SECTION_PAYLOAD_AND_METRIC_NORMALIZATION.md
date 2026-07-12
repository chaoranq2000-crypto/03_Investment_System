# R5 Bundle 6.2 — Section payloads and metric normalization

## Goal

Insert an analytical payload layer between the R5 research pack and prose rendering.

Current anti-pattern:

```text
raw pack -> generic note writer -> audit-style report
```

Required path:

```text
raw pack
  -> validated section payloads
  -> reader narrative writer
  -> main report
  -> separate traceability appendix
```

## Section payload contract

Every major section payload must include:

```yaml
section_id:
title:
one_sentence_judgment:
material_facts: []
trend_calculations: []
causal_chain: []
economic_implications: []
counterpoints: []
uncertainties: []
watchpoints: []
display_references: []
readiness_for_reader_report:
```

A section cannot be marked ready merely because a table exists.

## Required calculated analytics

For the existing 002837 data, calculate and validate where inputs permit:

- 2023A-2025A revenue CAGR;
- annual revenue and net-profit growth;
- net margin by period;
- operating cash flow / net profit;
- operating cash flow / revenue;
- latest-quarter revenue/profit divergence;
- broad product-line revenue shares and gross-margin differences;
- forecast growth, margin and EPS changes;
- valuation changes across forecast scenarios.

All calculations must retain raw precision in payloads and use formatted values in the report.

## Metric formatter

Implement a single formatter used by all reader-facing sections:

- CNY absolute values: default to `亿元`, two decimals;
- smaller values: `万元` or `百万元` only when explicitly configured;
- percentages: one or two decimals;
- multiples: one decimal;
- EPS: two or three decimals;
- dates: ISO or Chinese date, consistent within report;
- negative values: use minus sign, not parentheses unless configured;
- table units: in column headers, not repeated in every cell;
- no output with more than four decimal places unless a documented exception exists.

## Analytical synthesis requirements

The payload builder must not invent causes. A causal explanation may be emitted only when:

- directly supported by reviewed evidence; or
- marked as an inference and linked to the supporting facts and limitations.

Where a cause is unknown, state that the divergence is observable but the driver is not yet verified.

## Required implementation targets

- `src/report/r5_section_payload_builder.py`
- `src/report/r5_metric_formatter.py`
- `scripts/build_r5_reader_section_payloads.py`
- payload schemas/examples
- deterministic unit tests

## Acceptance gate

- payloads validate deterministically;
- calculations reconcile with raw inputs;
- display values are normalized;
- no section is ready without judgment, facts, analysis, uncertainty and watchpoint;
- unsupported causes fail closed;
- sample-quality and P2 remain false.
