# 2026-07-02 Docs Authority Alignment Log

## date

2026-07-02

## scope

docs authority alignment / P1.6 workflow documentation cleanup.

## status

PASS

## changed_paths

Modified:

- `AGENTS.md`
- `README.md`
- `docs/playbooks/OPERATING_PLAYBOOK.md`

Unchanged after check:

- `docs/index.md`

## summary

Aligned top-level documentation with P1.6 workflow buildout:

- `AGENTS.md` now includes `docs/workflows/`, `research-orchestrator`, workflow run package rules, and documentation priority.
- `README.md` now states the current stage as P1.6 and lists workflows as the permanent workflow documentation layer.
- `docs/playbooks/OPERATING_PLAYBOOK.md` is now a lightweight command index and quick entry, not a workflow fact source.

No research conclusions, evidence records, scorecards, watchlist changes, or trading instructions were added.

## verification

Checked:

```text
git diff --check
rg -n "P1\.5|P1\.6|docs/workflows|research-orchestrator|workflow run|事实源" AGENTS.md README.md docs\playbooks\OPERATING_PLAYBOOK.md docs\index.md
```

Result:

- No whitespace errors from `git diff --check`.
- `docs/index.md` already lists Workflows, P1.6 plan, and P1.6 log; it was not modified.

## open_risks

- `research_workflow_foundation_patch.zip` remains an untracked local file from the earlier workflow foundation import; it was not touched.
