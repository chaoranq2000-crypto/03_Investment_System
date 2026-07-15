# 16R-3 — Run existing 15R and selective 14R

1. Inspect preview candidates and queues.
2. Publish candidates atomically with `--apply-packs` only after review.
3. Invoke the existing Bundle 15R runner; do not reimplement its gates.
4. Let Bundle 15R invoke Bundle 14R only for its generated qualification directory.
5. Preserve blocked cases and their exact backflow routes.
6. Do not regenerate a Reader or claim sample-level completion in this bundle.

Exit criteria are deterministic execution, correct owner/stage backflow and zero
release-boundary violations—not four forced passes.
