# R5 Bundle 6.1 — Reader-facing report contract

## Goal

Define the first-class contract for a reader-facing research report and keep it separate from the audit contract.

## Required architecture

Introduce two outputs:

```text
reader report: analysis for human readers
traceability appendix: machine audit and provenance
```

The reader report is not a prettier rendering of the old audit note. It is a distinct output contract consuming structured section payloads.

## Required contract fields

Each report must carry machine metadata outside the visible body or in a compact front-matter block that the writer does not render as prose:

- workflow ID;
- stock code/name;
- cutoff date;
- output level;
- source pack digest;
- traceability appendix path;
- quality scorecard path;
- human-review status;
- fixed sample-quality/P2 flags.

## Required main sections

Use `TARGET_READER_FACING_REPORT_SURFACE.md` as the structural contract.

The following are mandatory for a candidate:

- core research view;
- company context and boundary;
- financial history and quality;
- business breakdown and economics;
- industry structure and competition;
- forecast and scenarios;
- valuation and market expectations;
- risks/counter-evidence;
- research conclusion and watchlist.

Technical state and sentiment are optional when unsupported. Dated company events are not optional when material reviewed events exist.

## Main-body exclusion rules

Main-body critical blockers include:

- raw claim/evidence/metric IDs;
- registry/workflow paths;
- `readiness`, `visible_gap`, `next_action` machine labels;
- raw TODO or missing tokens;
- duplicate audit blocks;
- raw method names;
- unrounded CNY dumps;
- direct investment advice.

## Traceability rules

The appendix must preserve every material claim, including:

- display reference ID (`E1`, `E2`, ...);
- claim type;
- claim text or deterministic digest;
- period and units;
- raw evidence IDs;
- source path;
- method;
- confidence;
- limitation;
- reviewer state;
- conflict/staleness status.

Every display reference used in the main report must resolve exactly once.

## Required implementation targets

- `.agents/skills/stock-deep-dive/references/r5_reader_facing_report_contract.md`
- `.agents/skills/quality-review/references/r5_reader_quality_gate_contract.md`
- `config/r5_reader_quality_rubric.yaml`
- focused contract tests

## Acceptance gate

- contract validates;
- main report and appendix schemas are separate;
- appendix can represent all current Bundle 5 claim/evidence metadata;
- main-body exclusion patterns are executable;
- no sample fact is embedded in the contract;
- sample-quality and P2 remain false.
