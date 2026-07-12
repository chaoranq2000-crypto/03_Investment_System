# R5 Bundle 6.3 — Narrative composer and traceability split

## Goal

Build a real reader-facing composer rather than adding another prefix to the legacy note.

## Required work

1. Add a dedicated `r5_reader_report_writer` that consumes section payloads.
2. Keep the existing audit-note path intact for backward compatibility.
3. Render a separate traceability appendix.
4. Add stable display citations such as `[E1]` in the reader report.
5. Ensure every display citation resolves to exactly one appendix record.
6. Move all of the following out of the main body:
   - evidence IDs;
   - claim IDs;
   - source paths;
   - method names;
   - readiness tokens;
   - gap tokens;
   - reviewer metadata;
   - conflict/staleness machine states.
7. Translate disclosure gaps into natural reader language, for example:

```text
公司年报披露液冷相关产品，但未单列该业务的收入、毛利率和利润贡献；因此本文只确认产品暴露，不对液冷独立盈利规模作估算。
```

Do not render:

```text
MISSING_DISCLOSURE
TODO_SOURCE_REQUIRED
```

## Narrative standards

- Start each major section with a judgment, not a metadata block.
- Follow facts with interpretation.
- Include counterpoints in the same section rather than only in an appendix.
- Use transitions between sections so that the report has a coherent thesis.
- Avoid generic phrases unsupported by evidence.
- Avoid repeating the same limitation more than twice in the main report.
- Keep the full limitation in the traceability appendix.

## Required implementation targets

- `src/report/r5_reader_report_writer.py`
- `scripts/render_r5_reader_report_v2.py`
- `scripts/render_r5_traceability_appendix_v2.py`
- reader-report fixture tests
- citation-resolution tests
- deterministic-output tests

## Acceptance gate

The synthetic supported fixture must render:

- one reader report;
- one appendix;
- no raw IDs or paths in the main report;
- all citation references resolved;
- no duplicate audit sections;
- no forbidden advice language;
- stable output hash across identical runs.

The existing Bundle 5 draft path must continue to work and remain explicitly classified as an audit-oriented draft.
