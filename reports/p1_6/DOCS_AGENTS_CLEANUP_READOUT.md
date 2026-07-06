# Docs and AGENTS Cleanup Readout

date: 2026-07-06
patch_package: `docs_agents_cleanup_patch.zip`
status: accepted
scope: docs_agents_cleanup

## Scope Boundary

- Applied the latest docs / AGENTS cleanup patch package.
- Did not delete old files, old skill directories, raw evidence, source code, or workflow-run outputs.
- Did not enter P2.
- Did not change research conclusions.

## Files Changed

Patch replacement files applied:

| File | Change |
|---|---|
| `AGENTS.md` | Replaced with shorter repo-level rules and restored legacy acceptance keywords. |
| `README.md` | Replaced with quick-entry README and restored P1.5 hardening compatibility note. |
| `docs/index.md` | Replaced with current documentation index covering workflows, reporting, references, codex tasks, plans, logs, and meta docs. |
| `docs/workflows/README.md` | Replaced with current workflow fact-source entry and active stock workflow routing note. |
| `docs/workflows/STOCK_REPORT_PRODUCTION_WORKFLOW.md` | Replaced with stock report production workflow routed through `stock-deep-dive`. |
| `docs/meta/DOC_OWNERSHIP_MATRIX.md` | Added document ownership and deduplication matrix. |
| `docs/plans/DOCS_AND_AGENTS_CLEANUP_PLAN.md` | Added cleanup plan from the patch package. |

Compatibility fixes made during acceptance:

| File | Change |
|---|---|
| `.agents/skills/stock-deep-dive/SKILL.md` | Added / renamed heading markers required by existing P0 acceptance tests: `When to use`, `Responsibilities`, `Out of scope`, `Guardrails`, and `Quality checklist`. |
| `docs/references/project_learning/deep_dives/tests/test_p1_5_hardening.py.learn.md` | Local ignored learning note only: removed literal placeholder-path examples that triggered the repo-wide placeholder scan. |

## Checks Performed

| Check | Result | Notes |
|---|---:|---|
| Patch file list inspection | PASS | Confirmed `replacement_files/` and `codex_tasks/APPLY_DOCS_AGENTS_CLEANUP.md`. |
| Replacement file copy | PASS | Copied only entries under `replacement_files/` after path-safety checks. |
| `git diff -- ...` on requested docs | PASS | Main diff shows AGENTS / README slimming and workflow-routing cleanup. |
| Markdown physical-line check | PASS | Long-term docs are multi-line Markdown; no compressed one-line documents found. |
| `docs/index.md` path existence check | PASS | Checked 51 indexed paths; missing path list is empty. |
| `docs/workflows/README.md` file-list check | PASS | Current workflow files are listed, including `STOCK_REPORT_PRODUCTION_WORKFLOW.md`. |
| Old skill default-routing search | PASS | Old names appear only as retired / pending-merge references in long-term docs. |
| `.codex/config.toml` active skill check | PASS | Active config enables `stock-deep-dive`; it does not enable `stock-research-analyst` or `stock-report-writer`. |
| `git diff --check` | PASS | Only LF-to-CRLF Git warnings; no whitespace errors reported. |
| Targeted pytest | PASS | `28 passed` for P0, P1, P1.5 hardening, and Phase B1 tests. |
| Full pytest | PASS | `107 passed, 2 skipped`. |

## Old Stock Skill Cleanup

Old stock skill cleanup should be a separate task.

Current finding:

- `.codex/config.toml` does not enable `stock-research-analyst` or `stock-report-writer`.
- `.codex/config.stock_report_quality_upgrade.snippet.toml` still contains inactive snippet references to both old skill paths.
- Long-term docs now describe those names as retired / pending-merge references, not default routes.

Recommended separate task:

1. Search old skill directories and all references.
2. Migrate any still-useful analysis or writing guidance into `stock-deep-dive/references/`.
3. Decide whether to archive or delete old skill directories.
4. Update or remove inactive `.codex` snippet references.
5. Re-run full pytest after cleanup.

## Remaining TODOs

| Severity | TODO | Owner | Next step |
|---|---|---|---|
| low | Decide whether to keep, update, or remove `.codex/config.stock_report_quality_upgrade.snippet.toml`. | Codex / user | Handle with old stock skill cleanup task. |
| low | Decide whether old `stock-research-analyst` and `stock-report-writer` directories should be archived or deleted. | Codex / user | Do not batch delete; perform in a separate approved cleanup task. |

## Decision

`docs_agents_cleanup_patch.zip` has been applied and accepted.

This pass completed the docs / AGENTS cleanup, preserved the no-delete and no-P2 boundaries, and verified the repo with full pytest.
