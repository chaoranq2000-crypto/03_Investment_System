# Night02 可执行合同授权读出

- Source queue：`codex_tasks/night_shift/r5_overnight_02_20260720/task_queue.yaml`
- Source state：`r5_night_shift_queue_v2_proposed`
- Runtime queue：`authorized_task_queue.yaml`
- Runtime state：`r5_night_shift_queue_v2`
- Human-reviewed package digest：
  `236de0bccd04b327f7056bcb79a3c6536c9d5f652d1944c346ceefc3b84420ad`
- Tasks：`40`
- Executable contract lint：`40 passed / 0 failed`
- Path authority：`package:task_queue.yaml#allowed_paths`
- Acceptance authority：`package:ACCEPTANCE_MATRIX.md`

本授权只覆盖包内已经过整体 hash 审阅的 Night02 工程任务。由自动生成器输出的
新合同仍必须是 `review_state: proposed`；特别是 8 个 pointer occurrence 的上游
generation/quality 合同提案，不因本读出而获得执行或 resolution 权限。
