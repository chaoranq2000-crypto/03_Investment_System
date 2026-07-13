# 10R.4 — Market, technical, sentiment, and event context

## Goal

Integrate only reviewed market context while preserving the difference between market data, sentiment clues, and issuer facts.

## Required work

- Bind technical analysis to a dated, reviewed price series.
- Separate macro, industry, and company sentiment layers and label clue-only inputs.
- Require future events to have dates on or after the Reader as-of date.
- For each future event, record impact path, verification metric, counterevidence condition, and refresh trigger.
- Omit a layer rather than fabricate it when evidence is stale or absent; omission keeps candidate status blocked.

## Acceptance

- No past event is presented as a future catalyst.
- Technical and sentiment statements have display references and as-of dates.
- Event wording remains conditional, not deterministic.
