# R5 Bundle 8A Integration Readout

- workflow_id: `wf_20260703_stock_first_002837_invic`
- workflow_type: `stock_first_closed_loop`
- stage: `T2 Company Evidence`
- date: `2026-07-13`
- decision: `bundle8a_stage_a_integrated_local`
- bundle8_closed: `false`
- reader_regenerated: `false`
- next_skill: `evidence-ingest`

## Applied Package

| item | result |
|---|---|
| archive | `R5_BUNDLE_8A_EVIDENCE_ACQUISITION_RESILIENCE_PATCH_2026-07-12.zip` |
| archive SHA256 | `BF2ADD026C981235D563F5D2C909391116AEB0856A95B752F2A435D164A232D7` |
| package checksums | `25 / 25 matched` |
| live overlay hashes | `19 / 19 matched` |
| application mechanism | package `apply_patch.sh`; `git apply --check` and reverse check passed |
| branch | `r5/bundle8a-evidence-acquisition-resilience` |

## Validation

| check | result |
|---|---|
| source route quality gate | `pass`; capabilities=`12`; blocking=`0` |
| focused Bundle 8A tests | `11 passed` |
| full repository pytest | `591 passed, 2 skipped` |
| current workflow dry-run | capabilities=`12`; queue tasks=`29`; blocked=`0` |
| planned adapter boundary | registry planned=`5`; live-enabled=`0` |
| Python syntax check | `6 files passed` |
| `git diff --check` | pass |

The first full-regression attempt observed one transient failure in the concurrently edited, unrelated `portfolio-tracker` skill frontmatter. That external edit completed without modification by this workflow; the targeted rerun and final full regression both passed.

## Boundary

- This readout proves local Bundle 8A integration and queue readiness only.
- No live adapter has been called by the queue builder.
- `sina_finance`, `baidu_finance`, `cls_market`, `hkex` and `cninfo_ir` remain planned and have no live task.
- Structured sources remain metric-only; news and market signals remain clues.
- Missing issuer disclosure for liquid-cooling revenue, margin, customers, orders and cash collection remains `MISSING_DISCLOSURE` until official evidence is found and reviewed.
- No commit, push, GitHub Actions result, Reader regeneration, Bundle 8 close or Bundle 9 dispatch is claimed here.

## Next Action

Execute handoff `17_to_evidence-ingest_bundle8a_live_gap_closure.md`: run only implemented and permitted adapters, archive/register every result, record failures and schema drift separately, and dispatch `G1 Evidence Gate` before Bundle 8 close.
