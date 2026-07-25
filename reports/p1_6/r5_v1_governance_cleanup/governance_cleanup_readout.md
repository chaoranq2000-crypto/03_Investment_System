# V1 Governance Integration Cleanup Readout

## P1 — Blocker scope and degradation semantics

- State: complete at checkpoint `0906a5fa8c785da1a74326aa19dbf0abc58ddd2e`.
- Package: `docs/codex_tasks/v1_governance_integration_cleanup_v2`.
- Frozen contract SHA-256: `c160ea2d676d5ba9a9893070be1a6e4418193cc508db07e71dd48cd0394a642f`.
- Package setup checkpoint: `f41d99dc3685da6b1317da58b73beb23fc95135c`.
- Preflight: pass; dedicated worktree was clean, required remote refs matched, and the dirty user main worktree remains read-only.
- Baseline V-003 P1 result: 61 passed, 0 failed.
- Implemented `decision_semantics_version: current_goal_v1` for new or updated active state while preserving unmarked historical V1 states as explicit read-only compatibility.
- Implemented `impact_scope`, `active_disposition`, `affected_capabilities`, and `blocks_current_goal` in the workflow and quality issue contracts.
- Implemented deterministic `accepted`, `accepted_with_todos`, `needs_fix`, and `blocked` derivation. Severity is descriptive and cannot decide the outcome alone.
- Implemented the direct disclosure → audited aggregate → bounded estimate/scenario → unknown/omit degradation ladder.
- Removed Bundle11R–16R and R5-G1–R5-G11 from ordinary routing. Retained Bundle11/12/13 runtime modules are explicit-input, local-output evaluators and do not write workflow state.
- Preserved inactive legacy adapters in the P5 inventory instead of changing them outside the P1 allowlist.
- V-002: pass.
- V-003 P1: 90 passed.
- Compatibility tests: 63 passed.
- V-009: pass; no protected or out-of-scope path changed.

## P2 — Final-report-only human review

- State: complete at checkpoint `aa73859ddf8dbef2ad94b8c72dbf0ffc3931b851`.
- Phase parent: `0906a5fa8c785da1a74326aa19dbf0abc58ddd2e`.
- The only active human boundary is the final report. Its record binds a canonical report path, unique required/current artifact, machine-recomputed SHA-256, real reviewer, timezone-aware time, decision, notes, and conditional change scope.
- Automatic workflow outcome and `system_v1_complete` remain machine-derived. `not_requested|pending` do not block them. `sample_quality_ready=true` additionally requires a current `approved` report and all other applicable sample-quality conditions; approval is necessary, not sufficient.
- Report-byte changes invalidate prior human decisions. Replacing a committed human decision requires a strictly later event, including an approved → pending → approved sequence.
- `changes_requested` routes to `needs_fix` only when it reveals an automated-quality defect; report-only revision preserves the machine-quality outcome.
- Evidence, claim, metric, candidate, calculation, generation lock, and receipt hashes remain machine controls. Parallel human-review aliases are rejected.
- Historical Bundle/Night/Reader review artifacts, old Goal authorizations, and generation locks are read-only compatibility inputs and have exited active routing.
- Unmarked legacy V1 replay remains read-only compatible only while completion truth fields are absent or false; an unmarked truth claim is rejected.
- V-002: pass.
- V-003 P2: 178 passed.
- Compatibility tests: 75 passed.
- Adversarial review: no blocker.
- V-009: pass; 26 phase paths, all authorized, and the user main worktree status vector exactly matches preflight.

## P3 — 002837 official-disclosure policy refresh

- State: implementation and required validators pass; awaiting the specified P3 checkpoint commit.
- Phase parent: `aa73859ddf8dbef2ad94b8c72dbf0ffc3931b851`.
- New canonical run: `reports/workflow_runs/wf_20260725_stock_first_002837_v1_policy_refresh`.
- The standalone runner reads only `data/manifests/evidence_manifest.csv` and the fixed annual/interim PDF plus processed-text pairs. It does not import the old replay, read a historical workflow directory, use network access, or overwrite raw data.
- The 2025 annual report PDF/text hashes resolve pages 15–16. The 2025 interim report PDF/text hashes resolve page 9.
- Room/cabinet revenue, revenue share, cost, and gross margin are preserved as direct disclosures. The 324,058-unit industry total is display-only and is not split across product lines.
- Line-level gross-profit amounts and gross-profit contribution percentages remain explicit `MISSING_DISCLOSURE`; gross-margin percentages are not reused as either field.
- The interim liquid-cooling revenue is represented as strictly greater than CNY 200,000,000 for 2025H1, not as an exact value.
- Room/liquid partial classification overlap is confirmed while its amount remains unknown. Cabinet/liquid remains unknown; neither overlap nor never-overlap is asserted.
- Four historical high issues are reclassified into new current issue IDs. They remain high/open and historically unresolved, but are visible, unused, scoped below workflow, and nonblocking.
- The current automatic status is derived as `accepted_with_todos`; all automatic gates pass except `G5=not_applicable`. Final-report review remains `not_requested`; all sample/P2/release truth fields remain false.
- V-003 P3: 194 passed.
- V-004: 16 passed; two unique temp outputs have semantic digest `2d8487beb46f10b6df103a9a2808998870a19556ef6879959ed15c6eb90cbcc6` and byte-identical 17-file trees.
- V-008: pass; 17 capabilities, 20 sources, zero blocking issues.
- V-009: pass; 26 phase paths, all authorized, with frozen sources and the user main worktree unchanged.

Later phases append their own sections. Publication evidence is never written here after the sealed candidate commit.
