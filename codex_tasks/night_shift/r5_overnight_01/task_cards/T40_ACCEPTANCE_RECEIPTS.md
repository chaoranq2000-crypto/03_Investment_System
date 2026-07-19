# ns01_t40_acceptance_receipts — Acceptance and Receipts

## Goal

让每个任务的完成声明绑定可复查的命令和工件。

## Receipt minimum fields

- run_id / task_id / attempt
- started_at / finished_at
- executor
- command list
- cwd
- exit code
- stdout/stderr length and SHA-256
- changed paths
- required artifact paths and SHA-256
- local commit SHA / remote SHA if available
- blocker occurrences claimed/resolved/unchanged
- terminal status and reason

## Failure modes

- `failed_retryable`
- `failed_terminal`
- `dependency_blocked`
- `evidence_required`
- `human_gate`
- `skipped_cutoff`

回执必须 deterministic；时间字段可从比较中规范化或单独排除，但内容哈希逻辑必须稳定。
