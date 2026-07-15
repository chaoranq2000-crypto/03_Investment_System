# 15R-0 — Baseline and scope lock

## Required baseline

```text
60f3e24af8572faaf1c7a9b12a37b4ac085d7b36
```

## Actions

1. Record `git rev-parse HEAD`, `git branch --show-current`, and
   `git status --short`.
2. Confirm the exact baseline; do not silently use a descendant.
3. Record all pre-existing modified, deleted, and untracked paths.
4. Create `codex/r5-bundle15r-reviewed-evidence-qualification`.
5. Run `git apply --check` on the supplied patch.
6. Apply only the patch and verify all pre-existing paths remain unchanged.
7. Do not stage evidence-manifest edits, deleted ZIPs, local evidence, generated
   folders, caches, or unrelated files.

## Exit criteria

- only declared add-only paths appear from Bundle 15R;
- Bundle 14R files are unchanged;
- the issuer-specific canonical workflow state is unchanged;
- pre-existing worktree changes remain present and unstaged.
