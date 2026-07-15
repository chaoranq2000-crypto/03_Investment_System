# 16R-1 — Inventory reviewed evidence and emit queues

1. Run Bundle 16R in preview mode against the real Bundle 14R case contracts.
2. Point `--catalog`/`--catalog-dir` only at reviewed repository catalogs.
3. Do not treat the four narrative samples, generated Readers or model output as evidence.
4. Review the catalog inventory, source-request queue, mapping queue and backflow queue.
5. Keep every missing source, driver and question visible.

Exit when every catalog conflict has an owner and every missing source/record has
a concrete owner/stage request.
