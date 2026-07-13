# 10R.6 — Regression and negative tests

## Goal

Prove that the new Reader path is not overfit to one company or one report.

## Required tests

- current pilot regression;
- a synthetic simple manufacturer;
- a synthetic multi-segment/cyclical company;
- nine-headings/nine-sentences thin report;
- forecast core-section failure with otherwise high score;
- stale model generation;
- unresolved reference;
- liquid-cooling claim inflation or double counting;
- low-confidence peer ranking;
- consensus relabelled as fact;
- past event presented as future;
- direct action language and target price;
- deterministic rerender and lock generation.

## Acceptance

- All negative fixtures fail for the intended reason.
- Cross-company fixtures require no source-code changes.
- Historical Bundle 6/7/8/9/10 tests remain green.
