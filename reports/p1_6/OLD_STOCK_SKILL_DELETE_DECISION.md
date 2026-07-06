# OLD_STOCK_SKILL_DELETE_DECISION

date: 2026-07-06
approval: user_approved_delete_old_skill
decision: no_active_skill_deletion_needed
delete_performed: false

## Scope

Approved deletion target:

```text
.agents/skills/stock-research-analyst
.agents/skills/stock-report-writer
.agents/skills/stock-report-write
```

## Result

No active old stock skill directory exists under `.agents/skills/`, so there was
no active skill directory to delete.

Confirmed absent:

```text
.agents/skills/stock-research-analyst
.agents/skills/stock-report-writer
.agents/skills/stock-report-write
```

## Remaining Historical Snapshots

The only old-name directories found are project-learning snapshots:

```text
docs/references/project_learning/deep_dives/.agents/skills/stock-research-analyst
docs/references/project_learning/deep_dives/.agents/skills/stock-report-writer
```

These are not active skills and are referenced by generated learning indexes.
They were not deleted in this pass because project instructions prohibit batch
directory deletion and recursive deletion. If they should also be removed, the
safe path is a separate manual cleanup of those snapshot files and related
project-learning indexes.

## Rationale

- `.codex/config.toml` does not enable old stock skills.
- `stock-deep-dive` already contains the migrated analysis and writing rules.
- Active workflow docs route stock work through `stock-deep-dive`.
- Historical workflow outputs were left unchanged as provenance.
- No raw evidence, source data, workflow run outputs, or research conclusions
  were changed.

## Final State

```yaml
old_stock_skill_active_route: false
active_old_skill_dirs_exist: false
active_old_skill_delete_performed: false
project_learning_snapshots_exist: true
project_learning_snapshots_deleted: false
requires_manual_snapshot_cleanup_if_desired: true
```
