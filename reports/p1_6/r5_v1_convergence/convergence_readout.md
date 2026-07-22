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

P2 will record the canonical entrypoint, compatibility entrypoints, implementation owner and duplicate-decision table before any behavior change.

## Phase record

### P1 — Freeze V1 engineering completion semantics

- status: `complete`
- planned paths: `docs/workflows/RESEARCH_WORKFLOW.md`, `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md`, `docs/meta/DOC_OWNERSHIP_MATRIX.md`, `tests/test_r5_v1_completion_semantics.py`, this readout, and `START_HERE.md`.
- change: define four independent V1 facts, the positive and negative boundary of `system_v1_complete`, current-run singleton assets, the long-term Goal boundary, and local-check ownership under G0–G10.
- validation: doc drift passed; five V1 semantic tests passed; the combined V1/doc compatibility selection passed 16 tests; whitespace and phase-scope checks passed.

## Validation summary

| validation | result | evidence |
|---|---|---|
| V-012 package integrity | pass | validator returned `ok: true`, expected contract SHA-256, phases P1–P5, and no warnings. |
| branch / baseline preflight | pass | clean target worktree; setup checkpoint is the only commit after source baseline. |
| P1 V1 semantics | pass | `tests/test_r5_v1_completion_semantics.py`: 5 passed. |
| P1 compatibility selection | pass | Bundle11R doc integration, stock-skill merge and V1 semantics: 16 passed. The first sandboxed attempt had two tmp-path setup errors caused by denied Windows temp access; the identical command passed outside that sandbox restriction. |
| V-001 doc drift | pass | `Doc drift check passed.` |
| P1 whitespace / scope | pass | `git diff --check` returned no errors; all changed paths are in the recorded P1 allowlist. |

## Scope and historical immutability

No `data/raw/**`, Night/Bundle17R history, old 002837 run, `AGENTS.md`, `.github/**`, dependency file or other worktree is authorized for mutation. Final scope audit remains pending.

## External truth and publication

No reviewer identity, reviewer authority, human decision, issuer-undisclosed metric or acceptance state has been generated. Publication has not started; PR, main merge, tag, release and deployment remain forbidden.
