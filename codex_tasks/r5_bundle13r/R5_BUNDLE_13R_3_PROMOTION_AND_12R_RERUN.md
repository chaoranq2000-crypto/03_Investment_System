# 13R.3 — Promotion and Bundle 12R rerun

## Goal

Create a reviewed Bundle 12R input and rerun the operating-evidence gate.

## Required work

- run `scripts/run_r5_bundle13r_evidence_backflow.py --strict`;
- require decision `ready_for_bundle12r_rerun`;
- execute the generated Bundle 12R rerun command;
- lock the rerun artifacts;
- feed the rerun result back to Bundle 13R.

## Acceptance

- either Bundle 12R returns `operating_evidence_ready`, or the remaining backflow is narrower and truthfully recorded;
- no Reader or sample-quality promotion occurs in this card.
