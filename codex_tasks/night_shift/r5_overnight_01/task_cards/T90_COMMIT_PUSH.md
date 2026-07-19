# ns01_t90_commit_push — Delivery

## Goal

将合格改动提交并推送到目标分支，同时保持仓库和研究状态真实。

## Pre-push checklist

- `git status --short`
- `git diff --check`
- changed path allowlist audit
- full pytest pass
- determinism pass
- `.local/` not tracked
- BF2 local outputs not tracked
- no PR / no merge / no force push
- morning readout complete

## Delivery receipt

记录：

- commit list；
- local HEAD；
- remote branch SHA；
- equality check；
- push output；
- unresolved tasks；
- research gate。
