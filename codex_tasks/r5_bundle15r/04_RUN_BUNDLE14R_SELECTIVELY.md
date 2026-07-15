# 15R-4 — Selective Bundle 14R execution

## Actions

1. Invoke the existing Bundle 14R runner with Bundle 15R's generated
   `qualification/` directory.
2. Confirm a case advances only when all required operating drivers, overlap,
   forecast, valuation, semantic, and deterministic gates pass.
3. Confirm blocked cases retain targeted T1/T2/T5/T6/T8/T9 backflow.
4. Re-run identical inputs and compare all Bundle 14R output hashes.
5. Keep human review pending unless a real exact-hash review artifact exists.

## Exit criteria

The reported ready count matches the physical evidence state. No threshold is
weakened and no missing evidence is converted into an estimate merely to pass.
