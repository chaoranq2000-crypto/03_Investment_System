# R5 Bundle 8R.2 — Adapter contracts and operational gate

## Goal
Replace route-exists semantics with operational proof semantics.

## Required work
- Complete source-level bindings for every enabled route.
- Add import/CLI resolution checks.
- Add fixture, live-smoke, raw, manifest, schema, boundary and fallback receipts.
- Integrate `run_adapter_operational_gate.py` into CI and the normal route-quality gate.

## Acceptance
- `market_snapshot_pull` cannot pass as live mootdx/Tencent.
- planned/manual/offline adapters on enabled live routes fail closed.
- a binding cannot become operational merely by changing one status string.
