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
| Current state fields and validation | `.agents/skills/research-orchestrator/references/workflow_state_schema.md` and `scripts/validate_workflow_state.py` beneath that skill | canonical state owner | `review_intake_ready` is not a canonical status. Gate-ID validation remains a P3 control-simplification gap. |
| Operating-research inner loop | `scripts/run_r5_bundle11r_runtime.py` → `src/research/r5_bundle11r_runtime.py` | active local runtime | Used only after the orchestrator reaches the local post-10R profile; it is not a second workflow entrypoint. |
| Night mission CLI | `scripts/run_r5_night_shift.py` | historical compatibility entry | Retained for Night03–Night05 replay/verification; it does not own current V1 workflow state. |
| Bundle/Night reports and mission states | existing `reports/p1_6/r5_bundle17r/**` and `reports/p1_6/r5_night_shift/**` | historical read-only evidence | They may prove lineage and behavior but never become current V1 state. |

### Duplicate / guard decision table

| observed overlap | evidence | P2 decision |
|---|---|---|
| `research-orchestrator` vs Bundle11R runtime | skill routes to the script only inside a stock-report local profile | keep both; owner/delegate relationship, not duplicate implementations. |
| current workflow state vs Night05 mission outcome | canonical validator excludes `review_intake_ready`; Night05 uses it only as `mission_outcome` | keep compatibility output but never persist it as canonical workflow status. |
| Night05 scope allowlist vs descendant V1 branch | `build_scope_audit()` compares Night04 source to current HEAD, so legal setup/P1 paths fail a historical mission allowlist | freeze mission-scope comparison at exact Night05 delivery commit; continue checking protected historical roots through current HEAD. |
| Night04 determinism proof vs historical immutability | `build_determinism_receipt()` materializes the dashboard twice into the historical Night04 directory | render identical dashboard bytes in memory for comparison; do not rewrite historical output. |
| orchestration runtime reference duplication | `references/orchestration_contract.md` repeats runtime/readout fields and includes old limited-P2 wording | record as P3 compatibility-pointer work; do not enlarge P2 scope. |

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

## Scope and historical immutability

No `data/raw/**`, Night/Bundle17R history, old 002837 run, `AGENTS.md`, `.github/**`, dependency file or other worktree is authorized for mutation. P2 has no tracked change in any protected path. Four ignored test-created bytecode files remain outside the checkpoint because the contract forbids deletion; subsequent validation proved they were not rewritten. Final scope audit remains pending.

## External truth and publication

No reviewer identity, reviewer authority, human decision, issuer-undisclosed metric or acceptance state has been generated. Publication has not started; PR, main merge, tag, release and deployment remain forbidden.
