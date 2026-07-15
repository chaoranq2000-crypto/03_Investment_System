# 16R-0 — Exact baseline and scope

## Baseline

Require exact `HEAD`:

```text
233d0cffbea04b69027d9825954e6d49bd62bfab
```

Record branch, `git status --short`, and SHA-256 of every pre-existing modified or
untracked file before applying the patch. Preserve all 142 pre-existing status
entries without staging or publishing them.

## Scope

Apply only the Bundle 16R add-only patch. Do not change Bundle 14R/15R runtime,
case contracts, canonical workflow state, evidence, existing reports or exact-hash
review artifacts.

## Stop conditions

Stop when HEAD differs, any target path already exists, `git apply --check`
fails, or the before/after worktree inventory differs outside the intended new
paths.
