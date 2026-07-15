# 17R-0 — Baseline and scope

- Require Bundle 16R ancestor `7ab395283f432faac7bbc0e83a0b0cf4976ed5dc`.
- Record and preserve all 262 pre-existing worktree entries.
- Apply only the add-only Bundle 17R patch.
- Do not stage local reviewed mappings, generated 16R/15R/14R outputs, ZIPs, caches, backups or unrelated files.
- Stop if a target path already exists or `git apply --check` fails.
