# R5 V1 Convergence Readout

## Contract and baseline

- task_id: `r5_v1_convergence`
- contract: `docs/codex_tasks/r5_v1_convergence/CONTRACT.md`
- contract_sha256: `5e4a52f8eff0792810a8b0255089a01359a47bafc549edb0bffacb1f4335d163`
- source_baseline: `a96c1b717bf15905d72fd142efd946fa01bce666`
- execution_branch: `codex/r5-v1-convergence`
- setup_checkpoint: `bb5514ba390a90b5426719ab1b14d6bf5afc20c7`
- ancestry: `git merge-base --is-ancestor a96c1b717bf15905d72fd142efd946fa01bce666 bb5514ba390a90b5426719ab1b14d6bf5afc20c7` returned exit 0.
- setup scope: baseline to setup checkpoint adds only `CONTRACT.md` and `START_HERE.md`; `git diff --check` passed.

## V1 truth model

| fact | current value | authority | evidence / unresolved condition |
|---|---:|---|---|
| `system_v1_complete` | true | engineering validation | P1–P5, final V-001–V-010, scope and active-root criteria pass; this does not imply sample, P2 or release readiness. |
| `sample_quality_ready` | false | current sample evidence and required human review | The canonical 002837 material gaps remain external truth; no value is fabricated. |
| `p2_ready` | false | `comparison_readiness_gate` | P2 is outside this stage and is not entered. |
| `release_ready` | false | exact-head remote and CI evidence | The first candidate failed standard CI on checkout-dependent hashes; the repaired candidate has not yet been pushed or verified. |

The long-term Goal `r5_bundle17r_bf2_four_case_activation` remains open. Night mission outcome
`review_intake_ready` is historical mission evidence only and is not a canonical workflow status.

## Active implementation and control plane

| role | canonical owner / entrypoint | classification | evidence / decision |
|---|---|---|---|
| Global workflow interface | `docs/workflows/RESEARCH_WORKFLOW.md` | canonical | Owns workflow types, stages, G0–G10, backflow and V1 truth semantics. |
| Runtime orchestration | `.agents/skills/research-orchestrator/SKILL.md` | canonical execution entry | Creates/updates one run, routes lower skills and closes the current readout. |
| Current state fields and validation | `.agents/skills/research-orchestrator/references/workflow_state_schema.md` and `scripts/validate_workflow_state.py` beneath that skill | canonical state owner | Marked `r5_v1` states strictly enforce canonical G0–G10 IDs/statuses and mapped local checks; unmarked protected states remain read-only legacy compatibility. |
| Operating-research inner loop | `scripts/run_r5_bundle11r_runtime.py` → `src/research/r5_bundle11r_runtime.py` | active local runtime | Used only after the orchestrator reaches the local post-10R profile; it is not a second workflow entrypoint. |
| Isolated 002837 V1 replay | `scripts/run_r5_v1_replay_002837.py` | run-scoped proof entry | Requires the frozen old source run and new target run explicitly, reuses only Bundle13R pure computation, and cannot target the protected source workflow. |
| Night mission CLI | `scripts/run_r5_night_shift.py` | historical compatibility entry | Retained for Night03–Night05 replay/verification; it does not own current V1 workflow state. |
| Bundle/Night reports and mission states | existing `reports/p1_6/r5_bundle17r/**` and `reports/p1_6/r5_night_shift/**` | historical read-only evidence | They may prove lineage and behavior but never become current V1 state. |

### Duplicate / guard decision table

| observed overlap | evidence | convergence decision |
|---|---|---|
| `research-orchestrator` vs Bundle11R runtime | skill routes to the script only inside a stock-report local profile | keep both; owner/delegate relationship, not duplicate implementations. |
| current workflow state vs Night05 mission outcome | canonical validator excludes `review_intake_ready`; Night05 uses it only as `mission_outcome` | keep compatibility output but never persist it as canonical workflow status. |
| Night05 scope allowlist vs descendant V1 branch | `build_scope_audit()` compares Night04 source to current HEAD, so legal setup/P1 paths fail a historical mission allowlist | freeze mission-scope comparison at exact Night05 delivery commit; continue checking protected historical roots through current HEAD. |
| Night04 determinism proof vs historical immutability | `build_determinism_receipt()` materializes the dashboard twice into the historical Night04 directory | render identical dashboard bytes in memory for comparison; do not rewrite historical output. |
| orchestration runtime reference duplication | `references/orchestration_contract.md` repeated runtime/readout fields and old limited-P2 wording | replaced in P3 by a thin compatibility pointer to the canonical runtime, state and handoff owners. |

### Local control mapping

| local control | mapped global owner gates | active treatment |
|---|---|---|
| `R5-G1` | `G1` | R5 evidence completeness remains local. |
| `R5-G2` | `G3`, `G7` | Financial-model checks route to metric/report owners. |
| `R5-G3` | `G2`, `G3`, `G7` | Business-breakdown checks route to claim/metric/report owners. |
| `R5-G4` | `G4`, `G7` | Industry context remains a stock-report local check. |
| `R5-G5`–`R5-G7` | `G3`, `G7` | Forecast, valuation and dated market checks remain local. |
| `R5-G8` | `G1`, `G2`, `G7` | Event/sentiment checks route to evidence, claim and report owners. |
| `R5-G9` | `G2`, `G7` | Narrative coherence routes to claim/report owners. |
| `R5-G10` | `G9` | No-advice remains owned by the canonical no-advice gate. |
| `R5-G11` | `G7` | Sample benchmark remains a local stock-report check and cannot set sample/P2 truth. |
| `DLQ-1`–`DLQ-8` | `G1`/`G2`/`G3`/`G7`/`G9`/`G10` as declared in `quality-review/SKILL.md` | Data-layer reports are supporting quality artifacts, not a second current decision. |
| Bundle close checks | `G10` | Compatibility close evidence; never a new global gate. |
| Night mission outcome | none as a status; relevant evidence is consumed by the owning G gate | Historical mission result only; never canonical workflow status. |

Active issue rows now keep the canonical owner in `gate_id`, the local id in
`local_check_id`, and the complete owner list in `mapped_global_gate_ids`.

## Phase record

### P1 — Freeze V1 engineering completion semantics

- status: `complete`
- planned paths: `docs/workflows/RESEARCH_WORKFLOW.md`, `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md`, `docs/meta/DOC_OWNERSHIP_MATRIX.md`, `tests/test_r5_v1_completion_semantics.py`, this readout, and `START_HERE.md`.
- change: define four independent V1 facts, the positive and negative boundary of `system_v1_complete`, current-run singleton assets, the long-term Goal boundary, and local-check ownership under G0–G10.
- validation: doc drift passed; five V1 semantic tests passed; the combined V1/doc compatibility selection passed 16 tests; whitespace and phase-scope checks passed.
- checkpoint: `9789c6ebedae4d71247a7d9b68b33523788e0add` (`docs(v1): freeze engineering completion semantics`).

### P2 — Converge the Night05 implementation baseline

- status: `complete`
- ancestry: Night05 source baseline `a96c1b717bf15905d72fd142efd946fa01bce666` remains an ancestor; no merge or cherry-pick is required.
- changed paths: `src/maintenance/night_shift/night05.py`, `src/maintenance/night_shift/night04_validation.py`, the two matching Night tests, `tests/test_r5_v1_active_control_plane.py`, four Bundle CLI isolation tests, P2 source-route report, this readout, and `START_HERE.md`.
- baseline guard result: targeted state/guard selection passed 10 tests and failed only the Night05 scope audit, which reported the seven legitimate package/P1 paths as out of Night05 mission scope.
- control-plane result: the canonical user entry remains `research-orchestrator`; Bundle11R remains its delegated local runtime; Night CLI remains a historical compatibility entry. A new guard test makes those owner/delegate boundaries explicit.
- scope-guard result: Night05's mission allowlist is evaluated only through delivery commit `a96c1b717bf15905d72fd142efd946fa01bce666`; protected Night/Bundle17R/002837 history is still checked through current HEAD. No allowlist was widened.
- historical-write result: Night04 determinism and Night05 bootstrap validation now build and compare bytes in memory. Tests assert the checked-in historical dashboard bytes are unchanged before and after validation.
- child-process isolation result: four Bundle CLI tests now invoke child Python with explicit `-B`; the corrected V-004 rerun left the four previously created, ignored `.pyc` timestamps unchanged. They remain untracked because the frozen contract prohibits deletion.
- validation: targeted controls 18 passed; V-002 source-route quality passed with 17 capabilities, 20 sources and zero blocking issues; V-003 210 passed; V-004 160 passed; canonical 002837 state validation passed; ancestry, V-009, whitespace and exact phase-scope checks passed.
- checkpoint: `c30152eb5efffbcc2a5b951b0a6c6f030b8852b9` (`refactor(v1): converge Night05 implementation baseline`).

### P3 — Simplify active workflow controls

- status: `complete`
- state model: new or updated active runs use `state_schema_version: r5_v1`; the validator strictly enforces canonical G0–G10 IDs, four canonical gate statuses, unique owner gates, local mapping fields, TODO enums and high-issue fail-closed behavior. Unknown versions fail.
- legacy compatibility: the protected 002837 state is unmarked and remains validator-readable without modification. Its legacy combined/local gate IDs do not become a template for the P4 replay.
- singleton controls: `workflow_state.yaml`, `open_todos.csv`, `quality_gate_report.md` and `workflow_readout.md` are the only current control assets. Bundle/data-layer readouts are supporting evidence in the manifest.
- runtime deduplication: `references/orchestration_contract.md` is now a thin compatibility pointer and no longer contains a second run tree, readout schema or limited-P2 field.
- quality mapping: active R5 issue examples and fixtures use canonical `gate_id` plus `local_check_id` and `mapped_global_gate_ids`; G0 is accepted; R5 completeness is required only when the R5 rubric is present. Data-layer `DLQ-*` checks emit the same mapping fields.
- compatibility guard: the Bundle7 reconciliation CLI has no default run, requires an explicit run plus `--legacy-compatibility`, rejects marked V1 states, maps its local reader check to G7/G9, uses canonical status values and leaves its auxiliary readout non-current.
- control boundaries: exact-hash is limited to frozen human-review inputs; rollback to mutable non-idempotent writes; remote receipts to publication and `release_ready`.
- validation: P3 control/quality targeted selections passed 45 and 27 tests; V-001 passed; V-002 passed with 17 capabilities and zero blocking issues; V-003 passed 210; V-004 passed 160; strict template and legacy 002837 validators passed; V-009, whitespace, package integrity and exact allowlist review passed.
- checkpoint: `b64b83b5f3c15bd1c3c7d9a6777fc24d5828f685` (`refactor(v1): simplify active workflow controls`).

### P4 — Replay the real 002837 stock-first closed loop

- status: `complete`
- isolation: the explicit source is `reports/workflow_runs/wf_20260703_stock_first_002837_invic/`; the only write target is `reports/workflow_runs/wf_20260723_stock_first_002837_v1_replay/`. The hardcoded Bundle11R close, legacy backflow writer, live adapters, raw copies and historical human-review artifacts were not used.
- real inputs: two reviewed official disclosures and two real Tushare structured snapshots are bound by raw and processed paths/hashes. Raw and structured files use `file_bytes`; processed text uses `canonical_lf_text_bytes`, so equivalent LF/CRLF checkouts retain one explicit content hash. The structured rows remain `draft` and `metric_only`; 136 candidates are copied run-locally and none is promoted.
- recomputation: the Bundle13R pure chain revalidated the Bundle12R context, rebuilt the 21-item queue, validated the reviewed backfill and exactly matched the archived result: `backflow_execution_in_progress`, 6 resolved, 11 unresolved, validation issue/blocker count 0.
- research truth: the new canonical state is `needs_fix`; G3 and G6 fail non-compensating checks. The exact four source high issues remain open with owners and next steps. No old reviewer decision, Reader acceptance, sample-quality or P2 state is inherited.
- control plane: the standard six files plus run-scoped provenance, research, exposure, backflow and validation artifacts are indexed in a 16-row manifest. Every non-self-recursive artifact has a verifiable hash.
- determinism: each command performs two internal materializations with zero drift. Two independent command invocations also produced an identical 16-file tree without timestamp normalization; the digest binds both hash values and their declared scopes and is `100b45bcac21f1bbcb12bce0028f9c46635fddd579eadd4ad85f32a639beb9ba`.
- validation: replay contract 7 passed, including explicit LF/CRLF equivalence; exact V-005 14-path selection 38 passed; V-006 returned `OK`; package integrity, old-run no-diff, V-009 and `git diff --check` passed. Machine summary: `reports/p1_6/r5_v1_convergence/validation/p4_replay_validation.yaml`.
- checkpoint: `a256d6e1afed85642f96a4427a55d7492bb62cd4` (`test(v1): replay 002837 closed loop`).

### P5 — Consolidate 63 blocker occurrences into actionable roots

- status: `complete`
- immutable baseline: Night02 has 63 unique unresolved occurrence IDs, 20 dependency-blocked occurrence nodes, six parent work orders, 69 DAG nodes and 532 edges. The 19 historical source bindings are SHA-256 values of `source_baseline:path` Git blob bytes, independent of checkout EOL conversion. Night04/Night05 preserve 43 candidate-ready, 20 dependency-blocked, six parent-pending and zero resolved; candidate classification, review packets and pointer dry-runs remain non-resolution evidence.
- root result: every occurrence has exactly one primary root while all original `BF17R-I-*`, `BF17R-WO-*` and `ns02_t30_*` IDs remain present. Seven roots replace occurrence counting: three human-judgment roots, one obtainable-evidence root and three historical engineering roots. The `issuer_not_disclosed` root count is zero because zero reviewed official sources cannot prove issuer non-disclosure.
- relationship result: the 20 dependency occurrences remain downstream nodes with their exact 10/43 prerequisites; the six parents remain separate aggregators. All 532 `blocked_by` edges match the frozen DAG and are acyclic. Six `duplicate_of` edges capture the two pointer semantic variants proven by Night04 without dropping any occurrence.
- engineering result: the quality-case alias mismatch and the two pointer-contract variants remain openly recorded, not falsely resolved. Their source artifacts are historical unmarked Bundle16R/17R compatibility outputs; P3 active-control tests and the isolated P4 replay prove `affects_system_v1=false`. Therefore open active-V1 engineering root count is zero while open historical engineering root count is three.
- external truth: authority/accepted decisions/independent receipts, case analysis, reviewed evidence and suite exact-hash review remain open with explicit owners and next steps. The long-term Goal remains `open_needs_targeted_backflow`; sample quality and P2 remain false.
- validation: strict dependency-free schema and V-007 passed 7; doc drift passed; source-route passed with 17 capabilities and zero blocking; V-003 passed 210; V-004 passed 160; V-005 passed 38; V-006 returned `OK`; full repository pytest passed 1184 with two existing skips and zero failures/errors. All protected-path, ancestry, whitespace, contract-hash and phase-allowlist guards passed. Machine summary: `reports/p1_6/r5_v1_convergence/validation/p5_blocker_root_cause_validation.yaml`.
- checkpoint: `7598801a291b288d1c0d9e78f3b9037a629ed17e` (`docs(v1): classify blockers and close convergence`).

### Open root causes retained after P5

| root | category | owner | severity | active V1 impact | next step |
|---|---|---|---|---:|---|
| `external_approval_and_independent_receipts_absent` | `human_judgment_pending` | `external_review_lead` | high | false | Register real authority, obtain exact-hash decisions for 43 candidates, then execute and independently receipt accepted records. |
| `analyst_conclusions_pending` | `human_judgment_pending` | `research_owner` | high | false | Complete the four case-specific driver, forecast, overlap, semantic and valuation analyses after evidence review. |
| `reviewed_evidence_acceptance_absent` | `obtainable_evidence_gap` | `evidence-ingest` | high | false | Acquire/review missing official source classes, then distinguish obtainable facts from genuinely undisclosed data. |
| `suite_exact_hash_review_pending` | `human_judgment_pending` | `typed_external_reviewers` | high | false | Record separate real decisions for the three historical stage locks. |
| `legacy_quality_case_id_contract_gap` | `engineering_defect` | `quality-review` | medium | false | If the long-term Goal resumes, regenerate a new run with explicit case aliases; do not rewrite history. |
| `legacy_generation_id_pointer_contract_gap` | `engineering_defect` | `engineering_executor` | medium | false | If historical execution resumes, apply one run-scoped semantic repair and validate all four occurrences. |
| `legacy_quality_ready_pointer_contract_gap` | `engineering_defect` | `engineering_executor` | medium | false | If historical execution resumes, apply one run-scoped semantic repair and validate all four occurrences. |

## Final local validation

- decision: `pass`
- exact matrix after the cross-platform repair: V-001 doc drift passed; V-002 final source-route passed with 17 capabilities and zero blocking issues; V-003 Night passed 210; V-004 Bundle14R–17R passed 160; V-005 exact 14-path 002837 selection passed 38; V-006 returned `OK`; V-007 passed 7; V-008 and V-009 are empty/pass; V-010 passed 1184 with two existing skips and zero failures/errors.
- lineage and scope: Night05 baseline remains an ancestor. The seven commits currently after it are setup, P1–P5 and the first final-validation checkpoint; the pending repair checkpoint will be the eighth. Protected history, raw data, old 002837 state, AGENTS, CI workflows and dependencies have no diff or worktree change.
- engineering completion: all C-ENG and C-SCOPE criteria pass; the root map has zero open active-V1 engineering defects. Therefore `system_v1_complete=true` independently of the external facts.
- external facts: `sample_quality_ready=false`, `p2_ready=false`, and the long-term four-case Goal remains open. These are truthful retained states, not validation failures.
- release boundary: `release_ready=false` until the candidate checkpoint and completion-only checkpoint both pass exact-head GitHub CI. CI receipts and the final remote SHA are deliberately kept out of Git and will be reported in the external handoff.
- machine summary: `reports/p1_6/r5_v1_convergence/validation/final_validation_summary.yaml`.

## Validation summary

| validation | result | evidence |
|---|---|---|
| V-012 package integrity | pass | validator returned `ok: true`, expected contract SHA-256, phases P1–P5, and no warnings. |
| branch / baseline preflight | pass | clean target worktree; setup checkpoint is the only commit after source baseline. |
| P1 V1 semantics | pass | `tests/test_r5_v1_completion_semantics.py`: 5 passed. |
| P1 compatibility selection | pass | Bundle11R doc integration, stock-skill merge and V1 semantics: 16 passed. The first sandboxed attempt had two tmp-path setup errors caused by denied Windows temp access; the identical command passed outside that sandbox restriction. |
| V-001 doc drift | pass | `Doc drift check passed.` |
| P1 whitespace / scope | pass | `git diff --check` returned no errors; all changed paths are in the recorded P1 allowlist. |
| P2 targeted control guards | pass | Night04 determinism, Night05 intake, V1 active-control-plane and V1 completion semantics: 18 passed. |
| V-002 source-route quality | pass | P2 report: decision `pass`, 17 capabilities, 20 sources, adapter gate/import checks true, zero blocking issues. |
| V-003 Night baseline | pass | Full Night/Baseline suite: 210 passed in 43.85 seconds. |
| V-004 Bundle baseline | pass | Full Bundle suite: 160 passed in 13.86 seconds. |
| P2 canonical state / scope | pass | Canonical 002837 workflow state validator returned OK; source ancestry, V-009 protected paths, `git diff --check` and exact P2 allowlist review passed. |
| P3 control-plane targeted | pass | V1 semantics, active-control, strict state validator, quality issue mapping, data-layer mapping and legacy backflow compatibility: 45 passed. |
| P3 quality-boundary targeted | pass | Scorecard, stock-report quality, reader gate, generation lock, reviewed-input promotion and Bundle11R integration: 27 passed. |
| V-001 P3 doc drift | pass | `Doc drift check passed.` after local IDs were kept out of the global-gate detector. |
| V-002 P3 source-route quality | pass | P3 report: decision `pass`, 17 capabilities, 20 sources, adapter checks true and zero blocking issues. The sandbox denied the first output write; the identical allowlisted command passed with filesystem permission. |
| V-003 P3 Night baseline | pass | Full Night/Baseline suite: 210 passed in 44.25 seconds. One approval attempt timed out before launch; the retry completed with zero failures. |
| V-004 P3 Bundle baseline | pass | Full Bundle14R–17R suite: 160 passed in 14.50 seconds. |
| P3 state / scope | pass | Strict V1 template returned OK; protected 002837 state returned OK in legacy compatibility mode with identical hash; V-009, `git diff --check`, package integrity and exact phase allowlist passed. |
| P4 replay contract | pass | Replay tests: 7 passed in 1.58s; source hash scopes, scope-bound semantic digest, LF/CRLF equivalence, six-piece control plane, honest gaps, manifest completeness, source isolation and checked-in determinism were proven. |
| V-005 002837 focused selection | pass | All 14 exact contract paths existed and passed: 38 passed in 4.13s. |
| V-006 replay canonical state | pass | Strict validator returned `OK`; state is `needs_fix`, with unique G0–G10 rows and four open high G3/G6 issues. |
| P4 second replay / scope | pass | Two independent invocations produced the same semantic digest and identical 16-file tree; old-run worktree/baseline diffs and V-009 were empty; `git diff --check` passed. |
| V-007 blocker root map | pass | Dependency-free strict schema and seven tests validate 63/20/6/69/43/0, 69 nodes, 532 exact edges, six proven duplicate references, frozen-baseline Git-blob source hashes, no cycles/orphans/fake resolutions and zero open active-V1 engineering roots. |
| P5 source route | pass | Distinct P5 report: decision `pass`, 17 capabilities and zero blocking issues. |
| V-003/V-004/V-005 P5 | pass | Night 210, Bundle14R–17R 160, and exact 14-path 002837 selection 38 passed with zero failures/errors. |
| V-001/V-006 P5 | pass | Doc drift passed and the isolated replay canonical state returned `OK`. |
| P5 full repository | pass | 1184 passed, two existing skips, zero failures/errors in 94.42 seconds. |
| P5 scope and integrity | pass | Baseline ancestry, V-008, V-009, protected worktree status, contract hash, package validation and exact P5 allowlist passed. |
| V-001–V-002 final | pass | Doc drift passed; final source-route report passed with 17 capabilities and zero blocking issues. |
| V-003–V-007 final | pass | Night 210, Bundle 160, exact 002837 38 and root-map 7 passed; canonical replay state returned `OK`. |
| V-008–V-010 final | pass | Baseline whitespace/protected-path audits are empty; full pytest passed 1184 with two existing skips and zero failures/errors in 94.42 seconds. |
| V-012 final package | pass | `--require-ready` returned `ok: true`, state `running`, expected contract hash, P1–P5 and no warnings/errors. |
| V-011 release | pending | First exact-head candidate `a7da7fcf70fae3cf5a25454b91043590792b8f7b` had three successful focused workflows but standard CI exposed two CRLF/LF hash defects (1181 passed, two failed, two skipped). That failure was not rerun; the repaired candidate still requires an ordinary push and fresh exact-head CI. URLs remain external to this readout. |

## Scope and historical immutability

No `data/raw/**`, Night/Bundle17R history, old 002837 run, `AGENTS.md`, `.github/**`, dependency file or other worktree was modified. Final baseline-to-HEAD and worktree audits are empty for every protected path. Four ignored test-created bytecode files remain outside all checkpoints because deletion is forbidden; bytecode-suppressed validation did not rewrite them.

## External truth and publication

No reviewer identity, reviewer authority, human decision, issuer-undisclosed metric or acceptance state has been generated. The evidence supports zero `issuer_not_disclosed` roots at this stage, not a claim that issuers disclosed the missing fields. Ordinary candidate-branch publication is the only next authorized write; PR, main merge, tag, release and deployment remain forbidden.
