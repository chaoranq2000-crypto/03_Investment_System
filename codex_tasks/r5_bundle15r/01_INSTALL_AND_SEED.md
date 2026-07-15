# 15R-1 — Install compiler and run fail-closed seed

## Actions

1. Compile the Bundle 15R module and CLI.
2. Run `tests/test_r5_bundle15r_evidence_qualification.py`.
3. Create an empty external pack directory.
4. Generate scaffolds and qualification outputs twice.
5. Compare the two output trees byte-for-byte.
6. Confirm the suite reports four cases, zero packs, zero complete packs, and
   zero Bundle 14R-ready cases.
7. Confirm every generated qualification retains false release flags.
8. Run the existing Bundle 14R focused tests.

## Blockers

Stop if an empty or incomplete input produces a ready case, if any path under a
canonical workflow run changes, or if output hashes differ across identical runs.
