# 13R.0 — Baseline and hash binding

## Goal

Bind implementation to commit `64f6787b` or a compatible descendant and to the exact Bundle 12R generation.

## Required work

- run `scripts/audit_r5_bundle13r_baseline.py`;
- verify Bundle 12R generation ID, workflow ID, decision and physical artifact hashes;
- confirm that the latest docs-only package-hash correction does not alter runtime semantics;
- do not rewrite Bundle 11R or Bundle 12R history.

## Acceptance

- audit decision `pass`;
- no hash drift;
- canonical promotion boundaries remain false.
