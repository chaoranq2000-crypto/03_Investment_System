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
| `system_v1_complete` | false | engineering validation | P1–P5 and final validation are not yet complete. |
| `sample_quality_ready` | false | current sample evidence and required human review | The canonical 002837 material gaps remain external truth; no value is fabricated. |
| `p2_ready` | false | `comparison_readiness_gate` | P2 is outside this stage and is not entered. |
| `release_ready` | false | exact-head remote and CI evidence | Candidate branch has not been pushed or verified yet. |

The long-term Goal `r5_bundle17r_bf2_four_case_activation` remains open. Night mission outcome
`review_intake_ready` is historical mission evidence only and is not a canonical workflow status.

## Active implementation and control plane

| role | canonical owner / entrypoint | classification | evidence / decision |
|---|---|---|---|
| Global workflow interface | `docs/workflows/RESEARCH_WORKFLOW.md` | canonical | Owns workflow types, stages, G0–G10, backflow and V1 truth semantics. |
| Runtime orchestration | `.agents/skills/research-orchestrator/SKILL.md` | canonical execution entry | Creates/updates one run, routes lower skills and closes the current readout. |
| Current state fields and validation | `.agents/skills/research-orchestrator/references/workflow_state_schema.md` and `scripts/validate_workflow_state.py` beneath that skill | canonical state owner | Marked `r5_v1` states strictly enforce canonical G0–G10 IDs/statuses and mapped local checks; unmarked protected states remain read-only legacy compatibility. |
| Operating-research inner loop | `scripts/run_r5_bundle11r_runtime.py` → `src/research/r5_bundle11r_runtime.py` | active local runtime | Used only after the orchestrator reaches the local post-10R profile; it is not a second workflow entrypoint. |
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

## Scope and historical immutability

No `data/raw/**`, Night/Bundle17R history, old 002837 run, `AGENTS.md`, `.github/**`, dependency file or other worktree is authorized for mutation. P2 has no tracked change in any protected path. Four ignored test-created bytecode files remain outside the checkpoint because the contract forbids deletion; subsequent validation proved they were not rewritten. Final scope audit remains pending.

## External truth and publication

No reviewer identity, reviewer authority, human decision, issuer-undisclosed metric or acceptance state has been generated. Publication has not started; PR, main merge, tag, release and deployment remain forbidden.
